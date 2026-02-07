from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from itertools import combinations
from collections import Counter
import re

from extractors.common import WordBox, Line, DocumentLayout
from extractors.normalizer import AdvancedNoiseNormalizer
from extractors.domain import DomainRules, is_valid_weight_logic

@dataclass
class WeightCandidate:
    """중량 후보 정보"""
    value: int
    source_word: WordBox
    y_position: float
    has_kg_nearby: bool = False
    context_hint: Optional[str] = None  # 'total', 'tare', 'net'

class UnifiedWeightEngine:
    """통합 중량 추출 엔진 (Consolidated)"""
    
    def __init__(self, normalizer: AdvancedNoiseNormalizer):
        self.normalizer = normalizer

    def _normalize_ocr_digits(self, text: str) -> str:
        """OCR 오인식 문자 숫자 변환 (O->0, B->8, I->1, etc)"""
        replacements = {
            'O': '0', 'o': '0', 'D': '0',
            'I': '1', 'l': '1', '|': '1',
            'Z': '2',
            'B': '8',
            'S': '5', 's': '5',
            'g': '9', 'q': '9'
        }
        for char, digit in replacements.items():
            text = text.replace(char, digit)
        return text
    
    def extract_weights(self, word_boxes: List[WordBox], 
                       layout: DocumentLayout) -> Optional[Dict]:
        """
        Ensemble Voting으로 중량 추출
        
        Returns:
            {
                'total_weight': int,
                'tare_weight': int,
                'net_weight': int,
                '_confidence': float,
                '_methods_used': List[str]
            }
        """
        strategies = [
            self._strategy_equation_based,
            self._strategy_spatial_order,
            self._strategy_keyword_proximity,
        ]
        
        results = []
        for strategy in strategies:
            try:
                result = strategy(word_boxes, layout)
                if result and self._validate_weight_triplet(result):
                    results.append(result)
            except Exception:
                continue
        
        if not results:
            return {}
        
        # 투표
        return self._vote_results(results)
    
    def _strategy_equation_based(self, word_boxes: List[WordBox],
                                  layout: DocumentLayout) -> Optional[Dict]:
        """
        전략 A: 방정식 기반 (Total = Tare + Net)
        
        핵심: 크기가 아닌 관계로 판단하되, 후보가 여러 개면 값이 큰 것을 우선함.
        """
        candidates = self._extract_weight_candidates(word_boxes)
        
        if len(candidates) < 3:
            return None
        
        valid_triplets = []
        # 모든 3개 조합 시도
        for triplet in combinations(candidates, 3):
            values = [c.value for c in triplet]
            result = self._try_assign_weights_by_equation(values)
            if result:
                result['_method'] = 'equation_based'
                result['total_score'] = sum(values)
                valid_triplets.append(result)
        
        if not valid_triplets:
            return None
            
        # [Priority] 값이 큰 조합을 우선 (작은 숫자는 차량번호/ID와 겹칠 확률 높음)
        valid_triplets.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        best = valid_triplets[0]
        # total_score 필드는 제거하고 반환
        return {
            'total_weight': best['total_weight'],
            'tare_weight': best['tare_weight'],
            'net_weight': best['net_weight'],
            '_method': best['_method']
        }
    
    def _try_assign_weights_by_equation(self, triplet: List[int]) -> Optional[Dict]:
        """
        3개 숫자를 Total/Tare/Net에 할당 시도
        
        모든 순열 시도 (6가지)
        """
        A, B, C = triplet
        
        scenarios = [
            (A, B, C), (A, C, B),
            (B, A, C), (B, C, A),
            (C, A, B), (C, B, A),
        ]
        
        for total, tare, net in scenarios:
            # 방정식 검증 (오차 50kg)
            if abs(total - (tare + net)) <= 50:
                # 도메인 상식 검증
                if self._validate_weight_logic(total, tare, net):
                    return {
                        'total_weight': total,
                        'tare_weight': tare,
                        'net_weight': net,
                    }
        
        return None
    
    def _validate_weight_logic(self, total: int, tare: int, net: int) -> bool:
        """도메인 상식 검증 (Shared Logic)"""
        return is_valid_weight_logic(total, tare, net)

    
    def _strategy_spatial_order(self, word_boxes: List[WordBox],
                                 layout: DocumentLayout) -> Optional[Dict]:
        """
        전략 B: Y축 순서 기반
        
        가정: 위→아래로 총중량→공차→실중량
        """
        candidates = self._extract_weight_candidates(word_boxes)
        
        # Y축 정렬
        candidates.sort(key=lambda c: c.y_position)
        
        if len(candidates) >= 3:
            top_3 = [c.value for c in candidates[:3]]
            result = self._try_assign_weights_by_equation(top_3)
            
            if result:
                result['_method'] = 'spatial_order'
                return result
        
        return None
    
    def _strategy_keyword_proximity(self, word_boxes: List[WordBox],
                                     layout: DocumentLayout) -> Optional[Dict]:
        """
        전략 C: 키워드 근접성 (개선판)
        
        "총" 근처 → 총중량
        "차" 근처 → 공차중량  
        "실" 근처 → 실중량
        
        개선사항:
        - 분리된 숫자들을 결합 (예: "13" + "460" → 13460)
        - 시간 패턴 필터링 강화
        - kg 키워드 활용
        """
        # 라벨 패턴 정의 (fuzzy 매칭용)
        label_patterns = {
            'total': {
                'keywords': ['총', '합계'],
                'full_labels': ['총중량', '총 중량', '총 중 량', '합계중량']
            },
            'tare': {
                'keywords': ['차중량', '공차', '빈차'],
                'full_labels': ['차중량', '공차중량', '빈차중량', '차 중량', '차 중 량']
            },
            'net': {
                'keywords': ['실', '순', '적'],
                'full_labels': ['실중량', '실 중량', '실 중 량', '순중량']
            }
        }
        
        results = {'total': None, 'tare': None, 'net': None}
        
        for i, word in enumerate(word_boxes):
            clean_text = word.text.replace(' ', '').replace(':', '')
            
            for category, patterns in label_patterns.items():
                is_match = False
                
                # 전체 라벨 매칭
                for label in patterns['full_labels']:
                    if label.replace(' ', '') in clean_text:
                        is_match = True
                        break
                
                # 키워드 매칭 (라벨이 분리된 경우: "총" + "중량:")
                if not is_match:
                    for kw in patterns['keywords']:
                        if kw in word.text:
                            is_match = True
                            break
                
                if is_match:
                    # 근처 단어에서 숫자 수집 및 결합
                    weight = self._extract_combined_weight(word_boxes, i, layout)
                    if weight and weight >= 100:
                        if results[category] is None or weight > results[category]:
                            results[category] = weight
        
        total = results['total']
        tare = results['tare']
        net = results['net']
        
        # 모든 값이 있으면 검증
        if total and tare and net:
            if abs(total - (tare + net)) <= 50:
                return {
                    'total_weight': total,
                    'tare_weight': tare,
                    'net_weight': net,
                    '_method': 'keyword_proximity_v2'
                }
        
        # 2개만 있으면 나머지 계산
        if total and tare and not net:
            net = total - tare
            if net >= 10:
                return {
                    'total_weight': total,
                    'tare_weight': tare,
                    'net_weight': net,
                    '_method': 'keyword_proximity_v2_inferred'
                }
        
        if total and net and not tare:
            tare = total - net
            if tare >= 100:
                return {
                    'total_weight': total,
                    'tare_weight': tare,
                    'net_weight': net,
                    '_method': 'keyword_proximity_v2_inferred'
                }
        
        return None
    
    def _extract_combined_weight(self, word_boxes: List[WordBox], 
                                  label_idx: int, layout: DocumentLayout) -> Optional[int]:
        """
        라벨 오른쪽의 분리된 숫자들을 결합하여 중량 추출
        
        예: "총중량:" 뒤에 "02:07" "13" "460" "kg" → 13460
        """
        label_word = word_boxes[label_idx]
        
        # 같은 라인 오른쪽 단어들 수집
        same_line_words = []
        for j in range(label_idx + 1, min(len(word_boxes), label_idx + 15)):
            w = word_boxes[j]
            
            # Y 좌표가 비슷한지 (같은 라인)
            y_diff = abs(w.centroid[1] - label_word.centroid[1])
            if y_diff > layout.y_threshold_same_line * 2:
                break  # 다른 라인으로 넘어감
            
            # 오른쪽에 있는지
            if w.x_min > label_word.x_max - 50:
                same_line_words.append(w)
        
        if not same_line_words:
            return None
        
        # 숫자 후보 수집
        number_parts = []
        has_kg = False
        
        for w in same_line_words:
            text = w.text.strip()
            
            # kg 확인
            if 'kg' in text.lower() or 'k9' in text.lower():
                has_kg = True
                continue
            
            # 시간 패턴 스킵 (HH:MM)
            if re.match(r'^[0-2]?\d:[0-5]\d$', text):
                continue
            
            # 한글 시간 패턴 스킵 ("11시", "33분")
            if re.match(r'^\d{1,2}시$', text) or re.match(r'^\d{1,2}분$', text):
                continue
            
            # [Fix] O->0 변환 적용 (25 O00 -> 25 000)
            text_norm = self._normalize_ocr_digits(text)
            
            # 숫자 추출
            # .은 유지해야 11. 500 같은거 판단 가능 -> 일단 숫자만 추출해서 합치는 전략1 유지하되
            # 11.500이 11500이 되도록 . 제거.
            digits = re.sub(r'[^\d]', '', text_norm)
            if digits and len(digits) >= 1:
                number_parts.append(digits)
        
        if not number_parts:
            return None
        
        # 숫자들 결합
        # 소수점 포함 결합 시도 (24 . 50)
        combined_raw = "".join(number_parts)
        
        # 만약 number_parts 중 하나라도 '.'을 포함하거나
        # 톤 단위라면 소수점 처리를 해야 함 -> 간단히 float 변환 시도
        
        # 톤 단위 체크 (same_line_words에서)
        is_ton = False
        for w in same_line_words:
            if re.search(r'(ton|t)\b', w.text, re.IGNORECASE):
                is_ton = True
                
        try:
            # 1. 그냥 합쳐서 int (기존 로직)
            val_int = int(combined_raw)
            if self._is_valid_weight_value(val_int, has_kg or is_ton):
                return val_int
        except: pass
            
        try:
             # 2. 소수점 고려 (각 파트를 합칠 때 점이 있었는지 확인 필요하지만
             # 여기선 number_parts가 숫자만 추출된 상태라 점 정보가 유실됨
             # 따라서 same_line_words의 raw text를 다시 봐야 함)
             full_line_text = "".join([w.text for w in same_line_words])
             
             # 실수 추출
             floats = re.findall(r'\d+\.\d+', full_line_text)
             if floats:
                 val_float = float(floats[0])
                 if is_ton and val_float < 100:
                     return int(val_float * 1000)
                 return int(val_float)
        except: pass

        # 전략 1: 모든 숫자 결합 (Fallback)
        combined = ''.join(number_parts)
        combined = combined.lstrip('0')  # 앞자리 0 제거
        
        if not combined:
            return None
        
        try:
            value = int(combined)
            
            # 유효성 검증
            if self._is_valid_weight_value(value, has_kg):
                return value
            
            # 너무 큰 값이면 분리해서 시도
            if value > 200000 and len(number_parts) > 1:
                # 마지막 2-3개만 사용
                for k in range(1, len(number_parts)):
                    partial = ''.join(number_parts[k:])
                    partial_val = int(partial)
                    if self._is_valid_weight_value(partial_val, has_kg):
                        return partial_val
        except ValueError:
            pass
        
        return None
    
    def _extract_weight_candidates(self, word_boxes: List[WordBox]) -> List[WeightCandidate]:
        """중량 후보 추출 (개선판)"""
        candidates = []
        seen_values = set()  # 중복 방지
    
        for i, word in enumerate(word_boxes):
            text = word.text.lower().replace(' ', '')
            
            # 1. 단위 확인
            # [Fix] net 의 t 등을 ton으로 오인하는 문제 방지
            is_ton = bool(re.search(r'(?<![a-z])(ton|t|톤)\b', text))
            has_kg = 'kg' in text or 'k9' in text
            
            # 주변 단어 범위 확대 (±10)
            nearby_start = max(0, i - 10)
            nearby_end = min(len(word_boxes), i + 11)
            
            # 주변에 kg/ton가 있는지 확인 (현재 단어에 없으면)
            if not (is_ton or has_kg):
                for w in word_boxes[nearby_start:nearby_end]:
                    w_text = w.text.lower()
                    if 'kg' in w_text or 'k9' in w_text:
                        has_kg = True
                    if re.search(r'(?<![a-z])(ton|t|톤)\b', w_text):
                        is_ton = True

            # 2. 숫자 파싱 (소수점 고려)
            # [Fix] O, B 등 오인식 보정 적용 후 숫자 추출
            # [Fix] 공백 제거 추가 (25 O00 -> 25000)
            clean_word_text = self._normalize_ocr_digits(word.text.replace(',', '').replace(' ', ''))
            digits = re.findall(r'\d+\.\d+|\d+', clean_word_text)
            
            for digit_str in digits:
                try:
                    val_float = float(digit_str)
                    final_val = 0
                    
                    if is_ton:
                        # 톤 단위: 100 미만이면 * 1000
                        # 예: 24.50 -> 24500, 10 -> 10000
                        # 단, 24500 ton은 아닐테니 작은 값만
                        if val_float < 100:
                            final_val = int(val_float * 1000)
                        else:
                            final_val = int(val_float)
                    else:
                        # kg 단위
                        final_val = int(val_float)
                        # 혹시 소수점으로 kg을 표현한 경우? (드묾)
                        # 예: 24.500 -> 24500 (소수점이 천단위 구분자일 수도 있음)
                        if 10 <= val_float < 100 and '.' in digit_str:
                             # 24.500 처럼 3자리 소수점이면 천단위일 가능성 높음
                             if len(digit_str.split('.')[1]) == 3:
                                 final_val = int(val_float * 1000)
                    
                    if 100 <= final_val <= 100000 and final_val not in seen_values:
                         candidates.append(WeightCandidate(
                            value=final_val,
                            source_word=word,
                            y_position=word.centroid[1],
                            has_kg_nearby=(has_kg or is_ton)
                        ))
                         seen_values.add(final_val)
                         
                except ValueError:
                    continue
        
        return candidates
        
    def _parse_weight_from_text(self, text: str) -> Optional[int]:
        """
        텍스트에서 중량 파싱 (긴급 패치)
        
        핵심 개선:
        1. 시간 패턴 제거 전에 숫자 후보 먼저 추출
        2. 공백/특수문자 모두 제거 후 숫자 결합
        3. 중량 범위 검증 강화
        """
        if not text:
            return None
        
        # 정규화
        normalized = self.normalizer.normalize(text, context='number')
        
        # [NEW] 노이즈 보정 (O->0, B->8)
        # kg 주변이나 숫자처럼 보이는 패턴에 적용
        if re.search(r'[\dOIlBZSBg]{2,}', normalized):
             normalized = self._normalize_ocr_digits(normalized)
        
        # === STEP 1: kg 키워드 확인 ===
        has_kg = 'kg' in normalized.lower()
        
        # === STEP 2: 모든 숫자 조각 추출 (시간 제거 전!) ===
        # "02:07 13 · 460 kg" → ["02", "07", "13", "460"]
        # "7 , 560" → ["7", "560"]
        
        # 먼저 명확한 시간 패턴만 제거 (HH:MM 형태)
        # 단, 뒤에 큰 숫자가 없는 경우만
        temp = re.sub(r'\b([01]?\d|2[0-3]):([0-5]\d)\b(?!\s*\d{3,})', '', normalized)
        
        # 날짜 제거
        temp = re.sub(r'20\d{2}[-./]\d{1,2}[-./]\d{1,2}', '', temp)
        
        # === STEP 3: 숫자 + 구분자 패턴 매칭 ===
        candidates = []
        
        # 패턴 1: "13 · 460" → "13460"
        # 패턴 2: "7 , 560" → "7560"
        # 패턴 3: "5 900" → "5900"
        
        # 모든 숫자 블록을 찾고 주변 특수문자 무시
        # [\d\s,\.·]+: 숫자, 공백, 쉼표, 점, 중점
        for match in re.finditer(r'[\d\s,\.·]+', temp):
            chunk = match.group()
            
            # 숫자만 추출
            digits_only = re.sub(r'[^\d]', '', chunk)
            
            if digits_only and len(digits_only) >= 3:  # 최소 3자리
                val = int(digits_only)
                
                # 유효성 검증
                if self._is_valid_weight_value(val, has_kg):
                    candidates.append(val)
        
        # === STEP 4: 최선의 후보 선택 ===
        if not candidates:
            return None
        
        # kg가 있으면 가장 가까운 큰 값
        if has_kg:
            # 1000 이상 값 우선
            large_vals = [v for v in candidates if v >= 1000]
            if large_vals:
                return max(large_vals)
        
        # 일반적으로 가장 큰 값
        return max(candidates)

    def _is_valid_weight_value(self, val: int, has_kg: bool) -> bool:
        """
        중량 값 유효성 검증
        
        Args:
            val: 숫자 값
            has_kg: kg 키워드 존재 여부
        """
        # 너무 작은 값 제외
        if val < 100:
            return False
        
        # 너무 큰 값 제외 (100톤 = 100,000kg)
        if val > 100000:
            return False
        
        # 연도 필터링 (2000-2099)
        if 2000 <= val <= 2099:
            # kg 키워드 없으면 연도로 간주
            if not has_kg:
                return False
        
        # 4자리 숫자이면서 200x, 201x, 202x 형태는 연도
        if 2000 <= val <= 2029 and len(str(val)) == 4:
            return False
        
        return True
    
    def _vote_results(self, results: List[Dict]) -> Dict:
        """투표로 최종 결과 선택"""
        # 튜플로 변환
        tuples = [
            (r.get('total_weight'), r.get('tare_weight'), r.get('net_weight'))
            for r in results
        ]
        
        # 가장 많이 나온 조합
        counter = Counter(tuples)
        most_common = counter.most_common(1)[0]
        winner_tuple, count = most_common
        
        total, tare, net = winner_tuple
        confidence = (count / len(results)) * 100
        
        methods = [
            r['_method']
            for r in results
            if (r.get('total_weight'), r.get('tare_weight'), r.get('net_weight')) == winner_tuple
        ]
        
        return {
            'total_weight': total,
            'tare_weight': tare,
            'net_weight': net,
            '_confidence': confidence,
            '_methods_used': methods
        }
    
    def _validate_weight_triplet(self, result: Dict) -> bool:
        """결과 검증"""
        tw = result.get('total_weight')
        tare = result.get('tare_weight')
        net = result.get('net_weight')
        if tw and tare and net:
            return abs(tw - (tare + net)) <= 100
        return False

    def extract_weights_from_text(self, text: str) -> Optional[Dict]:
        """텍스트에서 중량 추출 (Fallback)"""
        # 정규화
        normalized = self.normalizer.normalize(text, context='number')
        normalized = self._normalize_ocr_digits(normalized)
        
        # 숫자 후보 모두 추출
        all_numbers = re.findall(r'\d+', normalized.replace(',', ''))
        candidates = [int(n) for n in all_numbers if self._is_valid_weight_value(int(n), False)]
        
        # 상위 3개로 조합 시도
        if len(candidates) >= 3:
            for comb in combinations(sorted(candidates, reverse=True)[:5], 3):
                triplet = self._try_assign_weights_by_equation(list(comb))
                if triplet:
                    return triplet
        return None
