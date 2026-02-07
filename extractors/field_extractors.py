import re
from typing import List, Dict, Any, Optional
from .common import WordBox
from .config import CONSTANTS, KEYWORDS, NOISE_KEYWORDS, LABEL_CONFIG
from .base import BaseExtractor
from rapidfuzz import fuzz

class WeightExtractor(BaseExtractor):
    """중량 전문 추출기 (UnifiedWrapper)"""
    
    def __init__(self, unified_engine, label_detector, spatial_extractor, heuristic_finder, normalizer=None):
        super().__init__(label_detector, spatial_extractor, heuristic_finder, normalizer)
        self.unified_engine = unified_engine
    
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Dict[str, Any]:
        """UnifiedWeightEngine에 위임"""
        from .common import analyze_layout
        layout = analyze_layout(word_boxes)
        return self.unified_engine.extract_weights(word_boxes, layout)

class DateExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        # 전략 1: 공간 기반 매칭
        label_word = self.label_detector.find_label_in_wordboxes("date", word_boxes)
        if label_word:
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "date")
            if value: return value
        
        # 전략 2: 전체 텍스트 휴리스틱 (정규식)
        full_text = self.get_full_text(word_boxes)
        val = self.heuristic_finder.find_date_in_text(full_text)
        if val: return val

        # 전략 3: 공격적 보정 후 검색
        clean_text = self.normalize_numbers(full_text)
        match = re.search(r'20\d{2}[-./]\d{1,2}[-./]\d{1,2}', clean_text)
        if match:
             return match.group().replace('.', '-').replace('/', '-')
        return None


class VehicleExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        val = self._extract_candidate(word_boxes)
        if val:
            # [Fix] 차량번호 앞 노이즈(상호, 업체명, 상, 체명 등) 제거
            # 예: "상80구8713" -> "80구8713", "체명98바1234" -> "98바1234"
            val = re.sub(r'^(상|체명|차량\s*번호|번호)\s*', '', val).strip()
            return val
        return None

    def _extract_candidate(self, word_boxes: List[WordBox]) -> Optional[str]:
        # 전략 1: 공간 기반
        label_word = self.label_detector.find_label_in_wordboxes("vehicle", word_boxes)
        if label_word:
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "vehicle")
            if value: return value
            
        # 전략 2: 휴리스틱
        full_text = self.get_full_text(word_boxes)
        val = self.heuristic_finder.find_vehicle_in_text(full_text)
        if val: return val
        
        # 전략 3: 4자리 숫자 추출
        clean_text = self.normalize_numbers(full_text)
        candidates = []
        for match in re.finditer(r'(?<![-/])\b\d{4}\b(?![-/])', clean_text):
            num = match.group()
            if not num.startswith('202'): # 날짜와 구분
                candidates.append(num)
        return candidates[0] if candidates else None

class CompanyExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        # 전략 1: 공간 기반 (라벨 근처)
        label_word = self.label_detector.find_label_in_wordboxes("company", word_boxes, threshold=60)
        if label_word:
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "text", layout_threshold=300)
            if value:
                if self._is_label_noise(value):
                    pass # Skip using this value
                else:
                    # [Fix] Spatial 추출 결과에 대해서도 Heuristic 정제 적용 (Sample 03 노이즈 제거)
                    refined = self.heuristic_finder.extract_company(value)
                    if refined: 
                        return refined
                    
                    # [Fix] Fallback: 공백 및 점 제거, 그리고 노이즈 키워드 직접 제거
                    value = value.replace("공육을", "").replace("unle", "")
                    final_val = value.strip().replace(" ", "").replace("..", "").replace("...", "")
                    
                    if not self._is_label_noise(final_val): # 최종 값도 다시 확인
                        # [Fix] "고요환경품명" -> "고요환경" (Sample 02)
                        return self._clean_trailing_label(final_val)
            
        # 전략 2: 특정 키워드 패턴 (귀하 등)
        for i, word in enumerate(word_boxes):
            if "귀하" in word.text and i > 0:
                val = word_boxes[i-1].text.strip()
                if not self._is_label_noise(val):
                    return self._clean_trailing_label(val)
                
        # 전략 3: 휴리스틱 정규식
        full_text = self.get_full_text(word_boxes)
        val = self.heuristic_finder.extract_company(full_text)
        
        # [New] 공간 검증 (Issuer 위치 오탐 방지)
        if val:
             if self._validate_heuristic_location(val, word_boxes):
                 if not self._is_label_noise(val):
                     return self._clean_trailing_label(val)
             
        return None

    def _is_label_noise(self, text: str) -> bool:
        """텍스트가 '품명', '제품', '구분', '날짜' 등 다른 라벨인지 확인"""
        clean = text.replace(" ", "").replace(":", "").replace(".", "")
        # 일부 키워드는 Truncate 용도와 겹치므로 config 공유 또는 별도 정의
        # 여기서는 COMPANY_TRAILING 을 재사용하되, 일부는 제외할 수도 있음.
        # 편의상 COMPANY_TRAILING을 사용 (대부분의 라벨이 포함됨)
        if clean in NOISE_KEYWORDS['COMPANY_TRAILING']:
            return True
        # "품명:" 같은 경우 처리
        if any(clean.startswith(k) and len(clean) <= len(k)+1 for k in NOISE_KEYWORDS['COMPANY_TRAILING']):
            return True
        return False
        
    def _clean_trailing_label(self, text: str) -> str:
        """값 뒤에 붙은 다음 필드 라벨(품명 등) 제거 (Fuzzy Matching)"""
        if not text: return text
        
        # 1. 검사할 라벨 후보 수집 (Config 기반 Dynamic)
        target_labels = set()
        for field, config in LABEL_CONFIG.items():
            if field in ['company', 'issuer', 'vehicle']: continue 
            target_labels.update(config.get('canonical', []))
            target_labels.update(config.get('variants', []))
            target_labels.update(config.get('keywords', []))
            
        # 추가 노이즈 키워드
        target_labels.update(NOISE_KEYWORDS.get('COMPANY_TRAILING', []))
        
        # 짧은 키워드 제거 (오탐 방지)
        sorted_labels = sorted([t for t in target_labels if len(t) >= 2], key=len, reverse=True)

        # 2. Exact Match (Keyword in Text) - 우선 수행
        for k in sorted_labels:
            if k in text:
                idx = text.find(k)
                if idx > 0:
                     return text[:idx].strip()

        # 3. Fuzzy Suffix Match
        # 텍스트 끝부분이 라벨과 유사한지 검사 ("품랑", "제퓸" 등)
        # 마지막 2~4글자 검사
        n = len(text)
        for length in range(2, 5):
            if n < length: continue
            suffix = text[n-length:]
            
            # 너무 짧은 suffix는 검사 스킵
            if len(suffix) < 2: continue
            
            for label in sorted_labels:
                # 길이 차이가 크면 스킵
                if abs(len(label) - len(suffix)) > 1: continue
                
                # 유사도 검사 (80점 이상)
                # "품랑" vs "품명" -> 50점 (fuzz.ratio) -> 안됨
                # "제퓸" vs "제품" -> 50점 -> 안됨
                # 한국어 오타는 자모 단위 분해가 아니면 fuzz.ratio가 낮게 나옴.
                # 하지만 "제품명" vs "제퓸명" -> 66점
                
                # 대안: Character Set Overlap 검사 (간단한 오타)
                # "품랑" vs "품명" -> '품' 일치.
                # 그냥 1글자만 다르고 나머지는 같은 경우 (Levenshtein Distance = 1)
                
                dist = fuzz.ratio(suffix, label)
                
                # Levenshtein Distance가 1 이하인 경우 (글자수 비슷할때)
                # rapidfuzz.distance.Levenshtein.distance 사용 권장되지만, 
                # 여기서는 fuzz.ratio가 100이 아니더라도, 
                # 글자 하나만 틀린 경우를 잡고 싶음.
                
                # 2글자 단어에서 1글자 틀리면 50점.
                # 3글자 단어에서 1글자 틀리면 66점.
                threshold = 0
                if len(label) == 2: threshold = 49 # 1글자만 맞아도.. (위험하긴 함 "품종" vs "품명") -> "품"이 같으면?
                elif len(label) >= 3: threshold = 60
                
                if dist > threshold:
                     # 추가 검증: 첫 글자가 같은가? (한국어 라벨은 보통 첫글자가 중요)
                     if suffix[0] == label[0]:
                         return text[:n-length].strip()
                         
        return text


    def _validate_heuristic_location(self, value: str, word_boxes: List[WordBox]) -> bool:
        """Heuristic으로 찾은 Company 값이 공간적으로 타당한지 검증"""
        if not value or not word_boxes: return True
        
        # 핵심 키워드 추출 ((주) 등 제외)
        core = value.replace("(주)", "").replace(" ", "").strip()
        if len(core) < 2: return True
        
        # 텍스트 위치 찾기
        candidates = []
        for w in word_boxes:
            w_clean = w.text.replace(" ", "")
            if core in w_clean:
                candidates.append(w)
        
        if not candidates: return True
        
        # 문서 하단 55% 이하에만 위치하면 Reject (보통 Company는 상단, Issuer는 하단)
        max_y = max(w.y_max for w in word_boxes)
        bottom_threshold = max_y * 0.55
        
        if all(w.centroid[1] > bottom_threshold for w in candidates):
            return False
            
        return True



class IssuerExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        if not word_boxes: return None
        
        # 전략 1: 휴리스틱 (전체 텍스트 기반 (주) 패턴 탐색)
        full_text = self.get_full_text(word_boxes)
        last_company = getattr(self, 'last_company', None)
        val = self.heuristic_finder.extract_issuer(full_text, company=last_company)
        if val: return val

        # 전략 2: 하단부/상단부 가중치 기반 클러스터링 (Legacy Spatial logic)
        max_y = max(w.y_max for w in word_boxes)
        bottom_threshold = max_y * CONSTANTS['ISSUER_BOTTOM_RATIO']
        top_threshold = max_y * CONSTANTS['ISSUER_TOP_RATIO']
        candidates = []
        for word in word_boxes:
            cy = word.centroid[1]
            text = word.text
            score = 0
            if cy >= bottom_threshold:
                if any(k in text for k in KEYWORDS['ISSUER_CORP']): score += 50
                if any(k in text for k in KEYWORDS['ISSUER_TYPE']): score += 30
                if "장원" in text: score += 40
            elif cy <= top_threshold:
                if any(k in text for k in KEYWORDS['ISSUER_CORP']): score += 50
                if any(k in text for k in KEYWORDS['ISSUER_TYPE']): score += 40
                if any(k in text for k in KEYWORDS['ISSUER_HEADER_SKIP']): score = 0
            if score >= 30:
                candidates.append((score, word))
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates:
            return self._expand_issuer_name(candidates[0][1], word_boxes)
        return None
        
    def set_company_for_validation(self, company: Optional[str]):
        self.last_company = company
        
    def _expand_issuer_name(self, anchor: WordBox, word_boxes: List[WordBox]) -> str:
        if not anchor: return ""
        line_words = []
        c_y = anchor.centroid[1]
        for w in word_boxes:
            if abs(w.centroid[1] - c_y) <= 30: line_words.append(w)
        line_words.sort(key=lambda w: w.x_min)
        try: anchor_idx = line_words.index(anchor)
        except ValueError: return anchor.text
        start_idx = anchor_idx
        while start_idx > 0:
            curr = line_words[start_idx]
            prev = line_words[start_idx - 1]
            if curr.x_min - prev.x_max <= 100: start_idx -= 1
            else: break
        end_idx = anchor_idx
        while end_idx < len(line_words) - 1:
            curr = line_words[end_idx]
            next_w = line_words[end_idx + 1]
            if re.search(r'(전화|TEL|FAX|HP|:\d)', next_w.text, re.IGNORECASE): break
            if next_w.x_min - curr.x_max <= CONSTANTS['ISSUER_MERGE_DIST']: end_idx += 1
            else: break
        combined = " ".join(w.text for w in line_words[start_idx : end_idx + 1]).strip()
        combined = re.sub(r'(전화|TEL|FAX).*$', '', combined, flags=re.IGNORECASE)
        combined = re.sub(r'[\d-]{9,}', '', combined).strip()
        combined = re.sub(r'(?<=[가-힣])\s+(?=[가-힣])', '', combined)
        return combined

class PhoneExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        # 전략 1: 라벨 근처 검색
        for keyword in KEYWORDS['PHONE_LABELS']:
             for w in word_boxes:
                 if keyword in w.text:
                     phone_match = re.search(r'0\d{1,2}[\)-]\d{3,4}-\d{4}', w.text)
                     if phone_match: return phone_match.group()
                     phone_match_paren = re.search(r'\(\d{2,3}\)\d{3,4}-\d{4}', w.text)
                     if phone_match_paren: return phone_match_paren.group()
                     val = self.spatial_extractor.extract_value_near_label(w, word_boxes, "text", layout_threshold=CONSTANTS['SPATIAL_DEFAULT_LAYOUT'])
                     if val:
                         phone_match = re.search(r'[\d()-]{9,}', val)
                         if phone_match: return phone_match.group()
                         
        # 전략 2: 전체 텍스트 휴리스틱
        full_text = self.get_full_text(word_boxes)
        return self.heuristic_finder.extract_phone(full_text)

class ProductExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        # 전략 1: 공간 기반
        label_word = self.label_detector.find_label_in_wordboxes("product", word_boxes, threshold=60)
        if label_word:
            # [Fix] Layout threshold 완화 (Sample 11: 품 .. 목 : ... 혼 합 폐 기 물)
            # colon이 분리되어 있거나 거리가 멀 수 있음
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "text", layout_threshold=400)
            if value and self._is_valid_product(value): 
                return self._clean_product_value(value)
            
        # 전략 2: 휴리스틱
        full_text = self.get_full_text(word_boxes)
        value = self.heuristic_finder.extract_product(full_text)
        if value:
            return self._clean_product_value(value)
        return None

    def _clean_product_value(self, text: str) -> str:
        """한글 사이 공백 제거 및 노이즈 제거 (+ Context-aware splitting)"""
        if not text: return text
        
        # 1. [Fix] Next Field Label 제거 (Context-aware truncation)
        # "국판구분출" -> "국판" ("구분"부터 잘라냄), "폐지 입고" -> "폐지"
        # 공백이 섞여있어도 동작하도록 (구 분, 구  분)
        
        for label in NOISE_KEYWORDS['PRODUCT_NEXT_LABELS']:
            # 글자 사이 공백 유연하게 허용하는 패턴 생성 (예: 구\s*분)
            pattern = r"\s*".join(list(label))
            
            # 해당 패턴이 발견되면 그 시작 위치 앞까지만 사용
            match = re.search(pattern, text)
            if match:
                # 매칭된 라벨 앞부분만 잘라내기
                text = text[:match.start()].strip()
                
        # 2. [Fix] 한글 사이 공백 제거 ("혼 합 폐 기 물" -> "혼합폐기물")
        # 단, 영문 등 다른 문자 사이 공백은 유지 ("Plastic PE")
        text = re.sub(r'(?<=[가-힣])\s+(?=[가-힣])', '', text)
        
        return text.strip()
        
    def _is_valid_product(self, text: str) -> bool:
        if re.search(r'\d{1,2}시', text) or re.search(r'\d{1,2}:\d{2}', text): return False
        if re.search(r'\d{4}-\d{2}-\d{2}', text) or re.search(r'\d{4}\.\d{2}\.\d{2}', text): return False
        clean = text.replace(",", "").replace(" ", "").lower()
        if re.match(r'^\d+(\.\d+)?(kg|ton|g|t)?$', clean): return False
        if len(clean) < 2: return False
        return True

class TicketIdExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        vehicle_num = kwargs.get('vehicle_num')
        full_text = self.get_full_text(word_boxes)
        
        # [Fix] Normalizer 적용하여 "일 련 번 호" -> "일련번호" 변환
        norm_text = self.normalizer.normalize(full_text, 'label')
        
        return self.heuristic_finder.find_ticket_id_in_text(norm_text, vehicle_num=vehicle_num)

class TypeExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        full_text = self.get_full_text(word_boxes)
        return self.heuristic_finder.extract_type(full_text)

class GpsExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[dict]:
        full_text = self.get_full_text(word_boxes)
        return self.heuristic_finder.extract_gps(full_text)

class AddressExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        full_text = self.get_full_text(word_boxes)
        return self.heuristic_finder.extract_address(full_text)


