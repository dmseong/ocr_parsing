import re
from typing import List, Dict, Any, Optional
from .common import WordBox
from .config import CONSTANTS, KEYWORDS
from .base import BaseExtractor

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
                 # [Fix] Spatial 추출 결과에 대해서도 Heuristic 정제 적용 (Sample 03 노이즈 제거)
                 refined = self.heuristic_finder.extract_company(value)
                 if refined: return refined
                 return value
            
        # 전략 2: 특정 키워드 패턴 (귀하 등)
        for i, word in enumerate(word_boxes):
            if "귀하" in word.text and i > 0:
                return word_boxes[i-1].text.strip()
                
        # 전략 3: 휴리스틱 정규식
        full_text = self.get_full_text(word_boxes)
        val = self.heuristic_finder.extract_company(full_text)
        if val: return val
            
        return None

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
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "text", layout_threshold=CONSTANTS['LABEL_MERGE_DIST_X'])
            if value and self._is_valid_product(value): return value
            
        # 전략 2: 휴리스틱
        full_text = self.get_full_text(word_boxes)
        return self.heuristic_finder.extract_product(full_text)
        
    def _is_valid_product(self, text: str) -> bool:
        if re.search(r'\d{1,2}시', text) or re.search(r'\d{1,2}:\d{2}', text): return False
        if re.search(r'\d{4}-\d{2}-\d{2}', text) or re.search(r'\d{4}\.\d{2}\.\d{2}', text): return False
        clean = text.replace(",", "").replace(" ", "").lower()
        if re.match(r'^\d+(\.\d+)?(kg|ton|g|t)?$', clean): return False
        return True

class TicketIdExtractor(BaseExtractor):
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Optional[str]:
        vehicle_num = kwargs.get('vehicle_num')
        full_text = self.get_full_text(word_boxes)
        return self.heuristic_finder.find_ticket_id_in_text(full_text, vehicle_num=vehicle_num)

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
