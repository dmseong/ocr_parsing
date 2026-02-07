import re
from typing import List, Dict, Optional
from .common import WordBox
from .config import CONSTANTS, PATTERNS, KEYWORDS, THRESHOLDS

class HeuristicValueFinder:
    """
    라벨을 찾지 못했을 때, 값의 특성으로 역추론하는 모듈
    
    전략:
    1. 중량: 가장 큰 3개 숫자로 방정식 맞추기
    2. 날짜: 날짜 패턴 검색
    3. 차량번호: 4자리 숫자 또는 한글 포함 패턴
    """
    
    def __init__(self, normalizer=None):
        from .normalizer import AdvancedNoiseNormalizer
        self.normalizer = normalizer or AdvancedNoiseNormalizer()
    
    def _normalize_ocr_digits(self, text: str) -> str:
        """중앙 normalizer 위임"""
        return self.normalizer.normalize(text, context='number')
    
    def infer_weights_by_equation(self, word_boxes: List[WordBox]) -> Dict[str, int]:
        """
        방정식 (Total = Tare + Net) 기반 중량 역추론
        """
        from itertools import combinations, permutations
        
        # 모든 숫자 후보 수집 (좌표 포함)
        candidates = []
        for word in word_boxes:
            nums = self._extract_weight_numbers(word.text)
            for num in nums:
                if 100 <= num <= 100000:
                    candidates.append((num, word))
        
        # 중복 제거 (값 기준)
        seen = set()
        unique_candidates = []
        for num, word in candidates:
            if num not in seen:
                seen.add(num)
                unique_candidates.append((num, word))
        
        if len(unique_candidates) < 3:
            return {}
            
        # 모든 3개 조합에서 방정식 검증
        valid_triplets = []
        for triplet in combinations(unique_candidates, 3):
            # 1. 공간 응집도 검사
            words = [t[1] for t in triplet]
            if not self._check_spatial_coherence(words):
                continue
            
            # 2. 방정식 검증
            nums = [t[0] for t in triplet]
            for perm in permutations(nums):
                total, tare, net = perm
                if abs(total - (tare + net)) <= THRESHOLDS['WEIGHT']['EQUATION_TOLERANCE']:
                    if self._validate_weight_logic(total, tare, net):
                        valid_triplets.append({
                            'total_weight': total,
                            'tare_weight': tare,
                            'net_weight': net,
                            'avg_num': sum(nums)/3
                        })
        
        if not valid_triplets: return {}
        
        # [Priority] 값이 큰 조합을 우선 (작은 숫자는 차량번호/ID와 겹칠 확률 높음)
        # sample_10: 12480, 7470, 5010 vs 8713, 1234, 7470
        valid_triplets.sort(key=lambda x: x['total_weight'], reverse=True)
        best = valid_triplets[0]
        return {
            'total_weight': best['total_weight'],
            'tare_weight': best['tare_weight'],
            'net_weight': best['net_weight'],
        }
        return {}

    def _check_spatial_coherence(self, words: List[WordBox]) -> bool:
        """세 단어가 공간적으로 연관성(응집도)이 있는지 검사"""
        if len(words) < 2: return True
        
        # 중심점 좌표
        xs = [w.centroid[0] for w in words]
        ys = [w.centroid[1] for w in words]
        
        # 1. 최대 거리 검사
        import math
        max_dist = 0
        for i in range(len(words)):
            for j in range(i+1, len(words)):
                dist = math.hypot(words[i].centroid[0] - words[j].centroid[0],
                                  words[i].centroid[1] - words[j].centroid[1])
                max_dist = max(max_dist, dist)
                
        # 최대 거리가 600px 이상이면 무효 (너무 흩어져 있음)
        if max_dist > THRESHOLDS['WEIGHT']['SPATIAL_MAX_DIST']: 
            return False
            
        # 2. 정렬 검사
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        
        # 세로 정렬(X 비슷) 또는 가로 정렬(Y 비슷)
        if x_range <= THRESHOLDS['WEIGHT']['SPATIAL_ALIGN_X'] or y_range <= THRESHOLDS['WEIGHT']['SPATIAL_ALIGN_Y']:
            return True
        
        # 정렬되지 않았더라도 거리가 매우 가까우면(300px 이내) 인정
        if max_dist <= THRESHOLDS['WEIGHT']['SPATIAL_NEAR_DIST']:
            return True
            
        return False
    
    def _extract_weight_numbers(self, text: str) -> List[int]:
        """텍스트에서 중량 숫자 추출 (단위/소수점 고려)"""
        numbers = []
        is_ton = bool(re.search(r'\b(ton|t|tons)\b', text, re.IGNORECASE))
        # 노이즈 보정 적용
        # 단, 텍스트 전체를 바꾸면 단위(g, t)가 9, 7 등으로 바뀔 수 있으므로 주의
        # 여기서는 숫자 패턴 주변만 타겟팅하거나, 추출된 후보 문자열을 보정
        
        text = re.sub(r'\d{4}[-/\.]\d{2}[-/\.]\d{2}', '', text)
        text = re.sub(r'\d{2}:\d{2}', '', text)
        
        # 숫자와 유사한 문자(O, B)도 포함하여 추출 시도
        for match in re.finditer(r'[\dOIlBZSBg,]+(\.\d+)?', text):
            val_str = match.group(0).replace(',', '')
            val_str = self._normalize_ocr_digits(val_str)
            try:
                val_float = float(val_str)
                if is_ton or ('.' in val_str and val_float < 100):
                    val_float *= 1000
                val_int = int(round(val_float))
                if THRESHOLDS['WEIGHT']['MIN'] <= val_int <= THRESHOLDS['WEIGHT']['MAX']:
                    numbers.append(val_int)
            except ValueError:
                pass
        return numbers
    
    def _validate_weight_logic(self, total: int, tare: int, net: int) -> bool:
        """도메인 규칙 검증"""
        if total <= 0 or tare < 500 or net < 10: return False
        if tare >= total or net >= total: return False
        ratio = net / total
        if not (THRESHOLDS['WEIGHT']['RATIO_MIN'] <= ratio <= THRESHOLDS['WEIGHT']['RATIO_MAX']): return False
        return True
    
    def find_date_in_text(self, text: str) -> Optional[str]:
        """전체 텍스트에서 날짜 찾기"""
        month_map = KEYWORDS['MONTH_MAP']
        
        # [Fix] .. 포함 패턴 (2O26. 02.. 06)
        # 1. 텍스트 자체에서 ..을 .으로 치환
        text_norm = text.replace("..", ".").replace("...", ".")
        
        mon_match = re.search(PATTERNS['DATE'][0], text_norm)
        if mon_match:
            y, m_str, d = mon_match.groups()
            m = month_map.get(m_str.capitalize())
            if m: return f"{y}-{m}-{d.zfill(2)}"
        
        dot_match = re.search(PATTERNS['DATE'][1], text_norm)
        if dot_match:
            y, m, d = dot_match.groups()
            if len(y) == 2: y = "20" + y
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        
        # Noisy Date Pattern (e.g., 2026, 02. 01, 2O26-O2-O3)
        # 1. 먼저 숫자 오인식 보정
        clean_text = self._normalize_ocr_digits(text_norm)
        
        # 2. 보정된 텍스트에서 검색
        noisy_match = re.search(PATTERNS['DATE'][2], clean_text)
        if noisy_match:
            y, m, d = noisy_match.groups()
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            
        return None

    def find_vehicle_in_text(self, text: str) -> Optional[str]:
        """전체 텍스트에서 차량번호 찾기"""
        # 1. 표준 패턴 (가장 신뢰도 높음)
        # 12가3456 (신규) / 경기12가3456 (구형) / 서울1가1234 (구형) / 02가1234 (건설)
        # 1. 표준 패턴 (가장 신뢰도 높음)
        # 12가3456 (신규) / 경기12가3456 (구형) / 서울1가1234 (구형) / 02가1234 (건설)
        standard_patterns = PATTERNS['VEHICLE']['STANDARD']
        
        for pat in standard_patterns:
            match = re.search(pat, text)
            if match: return match.group().replace(' ', '')
            
        # 2. 노이즈 보정 패턴 (한글 오인식, 숫자 오인식 복구)
        # 예: 9l구1234 -> 91구1234
        # 예: SH0123 -> null (차량번호 아님)
        clean_text = self._normalize_ocr_digits(text)
        
        # 2-1. [Recovered] 숫자+한글+숫자 (가장 강력한 복구 대상)
        # 56바7B9O -> 56바7890
        match = re.search(PATTERNS['VEHICLE']['NOISE_REC'], clean_text)
        if match:
             prefix = match.group(1)
             char = match.group(2)
             suffix = self._normalize_ocr_digits(match.group(3))
             if suffix.isdigit() and len(suffix) == 4:
                 return f"{prefix}{char}{suffix}"
                 
        # 2-2. [Recovered] 한글+숫자 (구형/지역) - 보수적 접근
        # 예: 경기99바1234 -> "경기99바" 부분을 놓쳤을 때
        # 단순 4자리 숫자나 영어+숫자는 차량번호로 인정하지 않음 (O514 삭제됨)
        
        # 최후의 수단: 4자리 숫자 (202x 제외)는 FieldExtractor에서 처리하므로 여기선 생략
        # 여기서는 "차량번호스러운" 패턴만 리턴
        
        return None

    def find_ticket_id_in_text(self, text: str, vehicle_num: Optional[str] = None) -> Optional[str]:
        # 1. 명시적 라벨 패턴 (No, NO., 전표번호 등)
        # [Fix] 번호, No. 8713, 티켓: 12345 등 지원
        # [Fix] finditer 사용하여 차량번호(No. 0580) 등에 막혀서 진짜 ID(계량횟수 0022)를 못 찾는 현상 방지
        matches = re.finditer(r'(N[O0]\.?|전\s*표(?:번\s*호)?|티\s*켓|계\s*량\s*(?:번\s*호|횟\s*수|회\s*수)|ID[-\s]*N[O0]|번\s*호:?)\s*[:：\.]?\s*([A-Z0-9-]{1,12})', text, re.IGNORECASE)
        
        explicit_labels = ['ID-NO', '계량번', '계량횟', '계량회', '전표', 'TICKET', 'SLIP', 'ID', '번호']
        
        best_val = None
        for label_match in matches:
            val = label_match.group(2).strip().replace('o', '0').replace('O', '0').replace('B', '8')
            # [Fix] "No", "ID" 등 라벨 자체가 값으로 잡히는 것 방지 (sample_10 대응)
            if val.upper() in ['NO', 'ID', 'TEL', 'FAX', 'DATE', 'N0']:
                 label_full_end = label_match.end(2)
                 remaining = text[label_full_end:].strip()
                 next_val_match = re.search(r'^[^\w]*([A-Z0-9-]{2,12})', remaining, re.IGNORECASE)
                 if next_val_match:
                     val = next_val_match.group(1).strip()
            
            if not val or len(val) < 1: continue
            
            # 차량번호와 겹치는지 체크
            is_duplicate = False
            if vehicle_num:
                # [Fix] 차량번호 비교 시 OCR 노이즈(B->8) 정규화 적용 (Sample 08)
                v_clean = self._normalize_ocr_digits(vehicle_num.replace(" ", "").upper())
                val_upper = self._normalize_ocr_digits(val.upper())
                
                # 단순히 포함관계만 보면 '5'가 '5405'에 포함되어 지워질 수 있으므로,
                # 값이 어느 정도 길거나(3+), 완벽히 일치할 때만 중복으로 처리
                if val_upper == v_clean: is_duplicate = True
                elif val_upper in v_clean and len(val_upper) >= 3: is_duplicate = True
                
            label_found = label_match.group(1).upper().replace(" ", "")
            
            # [Fix] "차량번호"에서 "번호"만 잡히는 것 방지 (컨텍스트 확인)
            label_start = label_match.start(1)
            context = text[max(0, label_start-10):label_start] # 컨텍스트 윈도우 확대
            
            vehicle_keywords = ['차량', '차', '차번', 'VEHICLE', 'TRUCK', 'CAR']
            is_vehicle_label = False
            for vk in vehicle_keywords:
                if vk in context.upper() or vk in label_match.group(1).upper():
                    is_vehicle_label = True
                    break
            
            # 구체적 라벨 정의 ('NO' 제거하여 보수적으로 접근)
            explicit_labels = ['ID-NO', '계량번', '계량횟', '계량회', '전표', 'TICKET', 'SLIP', 'ID'] # '번호', 'NO' 제거
            is_explicit = any(el in label_found for el in explicit_labels) and not is_vehicle_label
            
            if is_duplicate:
                if is_explicit:
                    return val # 구체적 라벨이면 차량번호와 같아도 ID로 인정
                else:
                    continue # 단순 No. 차량번호 일치면 다음 매치 시도
            else:
                 if is_vehicle_label: continue
                 if is_explicit: return val
                 # 라벨이 애매한 경우(No. 123) 3글자 이상일 때만 보관
                 if len(val) >= 3:
                      best_val = val
        
        if best_val: return best_val
        
        # 2. 날짜 뒤 짧은 숫자 (보수적)
        # sample_01: 계량일자: 2026-02-02 0016
        # [Fix] 더욱 유연한 공백/패턴 대응
        clean_text = self._normalize_ocr_digits(text)
        # 날짜(20xx-xx-xx) 뒤에 오는 1~8자리 숫자 추출
        # [Fix] 1글자도 허용하되, 같은 줄(공백)에 있는 것만 인정 (Sample 05 GPS 좌표 오매칭 방지)
        # [Fix] (?!\d|:) 추가하여 시간(14:30)의 '14' 등이 잡히는 것 방지
        match = re.search(PATTERNS['TICKET_ID']['DATE_SUFFIX'], clean_text)
        if match:
            val = match.group(1)
            if val.isdigit() and int(val) < 10000:
                # 라벨 없는 "날짜 뒤 숫자"는 차량번호와 겹치면 배제
                if vehicle_num:
                    v_clean = vehicle_num.replace(" ", "").upper()
                    # 전체 일치하거나, 3글자 이상 겹칠 때만 배제 (Sample 03 '5' vs '5405' 대응)
                    if val.upper() == v_clean or (val.upper() in v_clean and len(val) >= 3):
                        return None
                # 어느 정도 의미 있는 길이거나(3+), 00으로 시작하거나, 아주 짧아도 인정(1-2)
                if len(val) >= 1:
                    return val
            
        return None

    def find_ticket_id_in_text(self, text: str, vehicle_num: Optional[str] = None) -> Optional[str]:
        # 1. 명시적 라벨 패턴 (No, NO., 전표번호 등)
        # [Fix] 번호, No. 8713, 티켓: 12345 등 지원
        # [Fix] finditer 사용하여 차량번호(No. 0580) 등에 막혀서 진짜 ID(계량횟수 0022)를 못 찾는 현상 방지
        matches = re.finditer(r'(N[O0]\.?|전\s*표(?:번\s*호)?|티\s*켓|계\s*량\s*(?:번\s*호|횟\s*수|회\s*수)|ID[-\s]*N[O0]|번\s*호:?)\s*[:：\.]?\s*([A-Z0-9-]{1,12})', text, re.IGNORECASE)
        
        explicit_labels = ['ID-NO', '계량번', '계량횟', '계량회', '전표', 'TICKET', 'SLIP', 'ID', '번호']
        
        best_val = None
        for label_match in matches:
            val = label_match.group(2).strip().replace('o', '0').replace('O', '0').replace('B', '8')
            # [Fix] "No", "ID" 등 라벨 자체가 값으로 잡히는 것 방지 (sample_10 대응)
            if val.upper() in ['NO', 'ID', 'TEL', 'FAX', 'DATE', 'N0']:
                 label_full_end = label_match.end(2)
                 remaining = text[label_full_end:].strip()
                 next_val_match = re.search(r'^[^\w]*([A-Z0-9-]{2,12})', remaining, re.IGNORECASE)
                 if next_val_match:
                     val = next_val_match.group(1).strip()
            
            if not val or len(val) < 1: continue
            
            # 차량번호와 겹치는지 체크
            is_duplicate = False
            if vehicle_num:
                # [Fix] 차량번호 비교 시 OCR 노이즈(B->8) 정규화 적용 (Sample 08)
                v_clean = self._normalize_ocr_digits(vehicle_num.replace(" ", "").upper())
                val_upper = self._normalize_ocr_digits(val.upper())
                
                # 단순히 포함관계만 보면 '5'가 '5405'에 포함되어 지워질 수 있으므로,
                # 값이 어느 정도 길거나(3+), 완벽히 일치할 때만 중복으로 처리
                if val_upper == v_clean: is_duplicate = True
                elif val_upper in v_clean and len(val_upper) >= 3: is_duplicate = True
                
            label_found = label_match.group(1).upper().replace(" ", "")
            
            # [Fix] "차량번호"에서 "번호"만 잡히는 것 방지 (컨텍스트 확인)
            label_start = label_match.start(1)
            context = text[max(0, label_start-10):label_start] # 컨텍스트 윈도우 확대
            
            vehicle_keywords = ['차량', '차', '차번', 'VEHICLE', 'TRUCK', 'CAR']
            is_vehicle_label = False
            for vk in vehicle_keywords:
                if vk in context.upper() or vk in label_match.group(1).upper():
                    is_vehicle_label = True
                    break
            
            # 구체적 라벨 정의 ('NO' 제거하여 보수적으로 접근)
            explicit_labels = ['ID-NO', '계량번', '계량횟', '계량회', '전표', 'TICKET', 'SLIP', 'ID'] # '번호', 'NO' 제거
            is_explicit = any(el in label_found for el in explicit_labels) and not is_vehicle_label
            
            if is_duplicate:
                if is_explicit:
                    return val # 구체적 라벨이면 차량번호와 같아도 ID로 인정
                else:
                    continue # 단순 No. 차량번호 일치면 다음 매치 시도
            else:
                 if is_vehicle_label: continue
                 if is_explicit: return val
                 # 라벨이 애매한 경우(No. 123) 3글자 이상일 때만 보관
                 if len(val) >= 3:
                      best_val = val
        
        if best_val: return best_val
        
        # 2. 날짜 뒤 짧은 숫자 (보수적)
        # sample_01: 계량일자: 2026-02-02 0016
        # [Fix] 더욱 유연한 공백/패턴 대응
        clean_text = self._normalize_ocr_digits(text)
        # 날짜(20xx-xx-xx) 뒤에 오는 1~8자리 숫자 추출
        # [Fix] 1글자도 허용하되, 같은 줄(공백)에 있는 것만 인정 (Sample 05 GPS 좌표 오매칭 방지)
        # [Fix] (?!\d|:) 추가하여 시간(14:30)의 '14' 등이 잡히는 것 방지
        match = re.search(r'20\d{2}[-.\s/]*\d{1,2}[-.\s/]*\d{1,2}(?:\s+\d{2}:\d{2}(?::\d{2})?)? +([A-Z0-9]{1,8})(?![\d:])', clean_text)
        if match:
            val = match.group(1)
            if val.isdigit() and int(val) < 10000:
                # 라벨 없는 "날짜 뒤 숫자"는 차량번호와 겹치면 배제
                if vehicle_num:
                    v_clean = vehicle_num.replace(" ", "").upper()
                    # 전체 일치하거나, 3글자 이상 겹칠 때만 배제 (Sample 03 '5' vs '5405' 대응)
                    if val.upper() == v_clean or (val.upper() in v_clean and len(val) >= 3):
                        return None
                # 어느 정도 의미 있는 길이거나(3+), 00으로 시작하거나, 아주 짧아도 인정(1-2)
                if len(val) >= 1:
                    return val
            
        return None

    def extract_gps(self, text: str) -> Optional[dict]:
        """GPS 좌표 추출"""
        # [Fix] 노이즈(B->8 등) 보정 후 추출
        text = self._normalize_ocr_digits(text)
        
        pattern = PATTERNS['GPS']['STANDARD']
        match = re.search(pattern, text)
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            if THRESHOLDS['GPS']['LAT_MIN'] <= lat <= THRESHOLDS['GPS']['LAT_MAX'] and THRESHOLDS['GPS']['LON_MIN'] <= lon <= THRESHOLDS['GPS']['LON_MAX']:
                return {"latitude": lat, "longitude": lon}
        
        # 2. Relaxed Pattern (중간에 공백/특수문자 허용)
        # 37 1234, 127 1234 형태
        relaxed = re.search(PATTERNS['GPS']['RELAXED'], text)
        if relaxed:
            try:
                lat = float(relaxed.group(1).replace(',', '.'))
                lon = float(relaxed.group(2).replace(',', '.'))
                if THRESHOLDS['GPS']['LAT_MIN'] <= lat <= THRESHOLDS['GPS']['LAT_MAX'] and THRESHOLDS['GPS']['LON_MIN'] <= lon <= THRESHOLDS['GPS']['LON_MAX']:
                    return {"latitude": lat, "longitude": lon}
            except: pass
        
        candidates = re.findall(PATTERNS['GPS']['CANDIDATE'], text)
        if len(candidates) >= 2:
            lats = [float(c) for c in candidates if THRESHOLDS['GPS']['LAT_MIN'] <= float(c) <= THRESHOLDS['GPS']['LAT_MAX']]
            lons = [float(c) for c in candidates if THRESHOLDS['GPS']['LON_MIN'] <= float(c) <= THRESHOLDS['GPS']['LON_MAX']]
            if lats and lons:
                return {"latitude": lats[0], "longitude": lons[0]}
        return None

    def extract_phone(self, text: str) -> Optional[str]:
        """전화번호 추출"""
        pattern = PATTERNS['PHONE']
        matches = list(re.finditer(pattern, text))
        for match in matches:
            if match.group(1) != '010':
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        if matches:
            m = matches[0]
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None

    def extract_address(self, text: str) -> Optional[str]:
        """주소 추출"""
        regions = ['경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도',
                   '경상북도', '경상남도', '제주도', '서울', '부산', '대구', '인천',
                   '광주', '대전', '울산', '세종']
        for region in regions:
            if region in text:
                pattern = rf'({region}\s*[가-힣]+(?:시|군|구).*?)(?=\s*(?:Tel|Tel\)|FAX|Fax|\*|20\d{{2}}[-.]|$))'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    addr = match.group(1).strip()
                    if len(addr) > 5: return addr
        return None

    def extract_company(self, text: str) -> Optional[str]:
        """회사명 추출 (Heuristic)"""
        # [Fix] .. 제거 (전처리)
        text = text.replace("..", "").replace("...", "")
        
        # 1. 명시적 라벨
        # 상호: 청정그린, 거래처: 대한리싸이클 등
        # [Fix] 샹호(상호 오타) 추가 및 공백 허용 (거 래 처)
        # 예: "거 래 처 : 대한리싸이클"
        # 1. 명시적 라벨
        # 상호: 청정그린, 거래처: 대한리싸이클 등
        # [Fix] 샹호(상호 오타) 추가 및 공백 허용 (거 래 처)
        # 예: "거 래 처 : 대한리싸이클"
        match = re.search(PATTERNS['COMPANY']['LABEL'], text)
        if match:
            val = match.group(2).strip()
            # 노이즈 제거: 전화, TEL 등 추가
            stoppers = KEYWORDS['COMPANY_STOPPERS']
            for stopper in stoppers:
                if stopper in val:
                    val = val.split(stopper)[0]
            val = val.strip()
            
            # [Fix] 회사명 내부 공백 제거 (태..양 건 설 -> 태양건설)
            val = val.replace(" ", "")
            
            if len(val) >= 2: return val
            
        # 2. 귀하 패턴
        # 2. 귀하 패턴
        match = re.search(PATTERNS['COMPANY']['HONORIFIC'], text)
        if match:
             val = match.group(1).strip()
             # 라인 끝부분만 가져오기 위해 공백으로 분리 후 마지막 2-3어절 체크
             parts = val.split()
             if len(parts) > 3:
                 return " ".join(parts[-3:])
             # 블랙리스트 체크
             if '보관용' in val: return None
             return val

        # 3. (주) 패턴 (주식회사)
        # 그린환경(주), (주) 에코월드 (공백 허용)
        # 중요: (주)만 덜렁 잡히지 않도록 앞뒤로 문자가 있어야 함
        
        # Case 1: (주) 접미사 (예: 그린환경(주), 그린환경 (주))
        # Case 1: (주) 접미사 (예: 그린환경(주), 그린환경 (주))
        matches_suffix = re.finditer(PATTERNS['COMPANY']['CORP_SUFFIX'], text)
        for m in matches_suffix:
             name = m.group(1).strip()
             # 너무 긴 앞부분은 자름 (최근 3어절)
             parts = name.split()
             if len(parts) > 3: name = " ".join(parts[-3:])
             
             val = f"{name}(주)"
             if self._is_valid_company_name(name, val):
                 return val
                 
        # Case 2: (주) 접두사 (예: (주)에코월드, (주) 에코월드)
        # [Fix] 공백 허용 및 숫자만 있는 경우 필터링
        matches_prefix = re.finditer(PATTERNS['COMPANY']['CORP_PREFIX'], text)
        for m in matches_prefix:
            name = m.group(1).strip()
            
            # [Fix] Stoppers 적용 (전화번호 등이 붙어있는 경우 잘라내기)
            stoppers = ['전화', 'TEL', 'FAX', 'HP', '주소']
            for s in stoppers:
                if s in name: name = name.split(s)[0].strip()
            
            val = f"(주){name}"
            val = val.replace(" ", "") # 내부 공백 제거
            
            # 숫자만 있거나, 날짜 패턴(202x)인 경우 제외 (Sample 01 이슈)
            if re.match(r'^[\d\s-]+$', name): continue
            
            if self._is_valid_company_name(name, val):
                return val

        return None

    def _is_valid_company_name(self, core_name: str, full_name: str) -> bool:
        """회사명 유효성 검사 (공통)"""
        if len(core_name) < 2: return False # (주) 제외하고 최소 2글자
        
        # 블랙리스트 체크
        blacklist = ['경기도', '서울', 'Tel', 'TEL', '보관용', '차량', '계량', '전화', 'FAX']
        full_name_clean = full_name.replace(" ", "")
        if any(x in full_name_clean for x in blacklist): return False
        
        # [Fix] 단위 노이즈 철저히 배제 (k9, kg, ton, pe 등)
        # 예: k9(주), (주)pe
        lower_name = full_name.lower().replace(' ', '')
        unit_noise = KEYWORDS['UNIT_NOISE']
        if any(u in lower_name for u in unit_noise): return False
        
        # 너무 긴 경우 (문장일 확률 높음)
        if len(full_name) > 20: return False # 조금 늘림
        
        return True

    def extract_issuer(self, text: str, company: Optional[str] = None) -> Optional[str]:
        """발행처(Issuer) 추출 (Heuristic)"""
        # [Fix] .. 제거 (전처리)
        text = text.replace("..", "").replace("...", "")
        
        # (주) 포함 패턴 모두 찾기
        patterns = [
            r'(\(주\)\s*[가-힣A-Za-z0-9 ]+)',
            r'([가-힣A-Za-z0-9 ]+\s*\(주\))'
        ]
        
        candidates = []
        # 한 줄씩 처리하여 개행을 넘어가는 매칭 방지
        for line in text.split('\n'):
            for pat in patterns:
                for m in re.finditer(pat, line):
                    cand = m.group(1).strip()
                    
                    # (주)만 있는 경우 제외
                    if cand.replace(" ", "") == "(주)": continue
                    
                    # 숫자만 있는 경우 제외 (Sample 01: (주) 2026)
                    core_content = cand.replace("(주)", "").replace(" ", "")
                    if re.match(r'^[\d\.-]+$', core_content): continue
                    
                    # [Fix] 주소/전화번호/품목 혼입 방지 (Sample 03, 04, 10, 11)
                    # [Fix] 주소/전화번호/품목 혼입 방지 (Sample 03, 04, 10, 11)
                    stoppers = KEYWORDS['ISSUER_STOPPERS']
                    
                    has_garbage = False
                    cand_upper_nospace = cand.upper().replace(" ", "")
                    # Stop if any stopper is found (normalized check)
                    for stopper in stoppers:
                        s_clean = stopper.replace(" ", "")
                        if s_clean in cand_upper_nospace:
                            core_match = re.match(PATTERNS['ISSUER']['CORP_ANY'], cand)
                            if core_match:
                                cleaned = core_match.group(0).strip()
                                # 잘린 부분이 stopper를 포함하지 않는지 재확인
                                if not any(s.replace(" ", "") in cleaned.upper().replace(" ", "") for s in stoppers):
                                    cand = cleaned
                                    break
                            
                            has_garbage = True
                            break
                            
                    if has_garbage: continue
                    
                    if len(cand) >= 2: 
                        # [Fix] 최종 후보에 대해 유효성 검사 (kg, ton 등 포함 여부)
                        if self._is_valid_company_name(cand.replace("(주)", "").strip(), cand):
                            candidates.append(cand)
                    
        norm_company = company.replace(" ", "") if company else ""
        
        for cand in candidates:
            norm_cand = cand.replace(" ", "")
            # 이미 찾은 회사명(Company)과 중복되거나 포함되면 패스
            # [Fix] 영어권 Supplier : prefix 제거
            for prefix in ['Supplier:', 'Supplier :']:
                if cand.startswith(prefix):
                    cand = cand[len(prefix):].strip()

            # [Fix] 회사명과 완벽히 중복되면 배제 (Sample 10 대응)
            # 단, 영어권 Supplier : 경우는 예외적으로 발행처로 인정
            if norm_company and cand.replace(" ", "") == norm_company:
                if not any(cand.startswith(p) for p in ['Supplier:', 'Supplier :']):
                     continue
            
            return cand
            
        return None

    def find_ticket_id_in_text(self, text: str, vehicle_num: Optional[str] = None) -> Optional[str]:
        # 1. 명시적 라벨 패턴 (No, NO., 전표번호 등)
        # [Fix] 번호, No. 8713, 티켓: 12345 등 지원
        # [Fix] finditer 사용하여 차량번호(No. 0580) 등에 막혀서 진짜 ID(계량횟수 0022)를 못 찾는 현상 방지
        # [Fix] 세미콜론(;) 구분자 추가
        # [Fix] 길이 12 -> 18 확장
        matches = re.finditer(PATTERNS['TICKET_ID']['LABEL'], text, re.IGNORECASE)
        
        explicit_labels = KEYWORDS['TICKET_LABELS']
        
        best_val = None
        for label_match in matches:
            label_text = label_match.group(1).replace(" ", "").replace(".", "").upper()
            # [Fix] O->0, B->8 치환 복구 (Sample 06 Ticket ID Noise)
            val = label_match.group(2).strip().replace('o', '0').replace('O', '0').replace('B', '8')
            
            # [Fix] 라벨 자체가 값으로 잡히는 경우 제외
            if val.upper() in KEYWORDS['LABEL_NOISE']: continue

            # 차량번호 제외 (차량번호와 겹칠 수 있음)
            if vehicle_num:
                 v_clean = vehicle_num.replace(" ", "").upper()
                 val_clean = val.replace(" ", "").upper()
                 
                 # 1. 단순 포함 관계 (기존)
                 if v_clean == val_clean: continue
                 
                 # 2. 노이즈 고려한 비교 (B <-> 8, Z <-> 2 등)
                 # Sample 08: AB-1234 vs A8-1234
                 def normalize_chars(s):
                     return s.replace('B', '8').replace('Z', '2').replace('O', '0').replace('I', '1').replace('D', '0')
                 
                 if normalize_chars(v_clean) == normalize_chars(val_clean): continue
                 
                 # Sample 03: 차량번호 5405, Ticket 5. 
                 # 5는 5405에 포함됨. 하지만 라벨이 'No' 등으로 명확하면 허용해야 함.
                 # 따라서 여기서 무조건 continue하지 않고, '라벨 점수'가 높으면 통과시킴.

            # 순수 숫자 4자리 이하는 차량번호 뒷자리일 확률 높음 -> 라벨 없으면 제외
            # 명시적 라벨이 있으면 허용 (Sample 03 '5', Sample 01 '0016' 대응)
            is_match_vehicle_partial = False
            if vehicle_num:
                 v_clean = vehicle_num.replace(" ", "")
                 val_clean = val.replace(" ", "")
                 if val_clean in v_clean: is_match_vehicle_partial = True

            # 라벨 점수 계산
            score = 0
            if any(l in label_text for l in explicit_labels):
                 score += 10
            
            # 차량번호 뒷자리 등과 겹치는데 라벨도 없으면 스킵
            # [Fix] 너무 짧은 숫자(<=2)가 차량번호에 포함되면 라벨 있어도 위험하므로 스킵 (Sample 05 '12' in '12가...' 오탐 방지)
            if is_match_vehicle_partial:
                 if len(val) <= 2: continue
                 if score == 0: continue
            
            # 너무 짧은 숫자인데 라벨도 없으면 스킵
            if re.match(r'^\d{1,4}$', val) and score == 0:
                 continue
            
            # 값 점수
            if len(val) >= 5: score += 5
            if '-' in val: score += 5
            
            # 우선순위 갱신
            if best_val is None or score > best_val[0]:
                best_val = (score, val)
        
        return best_val[1] if best_val else None


    def extract_product(self, text: str) -> Optional[str]:
        """품명(Product) 추출"""
    def extract_product(self, text: str) -> Optional[str]:
        """품명(Product) 추출"""
        # [Fix] 영문/숫자 혼용 허용 (플라스틱 PE 등), 제 품 추가, stopper 강화
        match = re.search(PATTERNS['PRODUCT'], text)
        if match:
            val = match.group(2).strip()
            # "총 중 량" 등이 잡히는 것 방지
            stoppers = ['총중량', '실중량', '공차중량', '중량', '계량', '확인', '차중량', '표']
            val_clean = val.replace(" ", "")
            if any(s in val_clean for s in stoppers): return None
            
            # [Fix] 한글 사이 공백 제거 ("혼 합 폐 기 물" -> "혼합폐기물")
            # 단, 영문 등 다른 문자 사이 공백은 유지 ("Plastic PE")
            val = re.sub(r'(?<=[가-힣])\s+(?=[가-힣])', '', val)
            
            if len(val) >= 1: return val
        return None

    def extract_type(self, text: str) -> Optional[str]:
        """구분(Type, 입고/출고) 추출"""
        # [Fix] 입 고, 출 고 등 공백 허용
        # 1. 라벨 기반 추출
        match = re.search(PATTERNS['TYPE']['LABEL'], text)
        if match:
            val = match.group(2).strip().replace(" ", "")
            if '입고' in val: return '입고'
            if '출고' in val: return '출고'
            
        # 2. Standalone 키워드 (보수적)
        # [Fix] 공백 포함 입 고, 출 고 검색
        if re.search(PATTERNS['TYPE']['IN'], text) and not re.search(PATTERNS['TYPE']['OUT'], text): return '입고'
        if re.search(PATTERNS['TYPE']['OUT'], text) and not re.search(PATTERNS['TYPE']['IN'], text): return '출고'
            
        return None
