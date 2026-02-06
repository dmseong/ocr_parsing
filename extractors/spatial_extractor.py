import re
from typing import List, Tuple, Optional, Any
from .common import WordBox
from .config import CONSTANTS

class SpatialValueExtractor:
    """
    공간 정보 기반 Value 추출기
    
    라벨을 찾은 후, 공간적 관계(오른쪽, 아래)를 이용해 Value 추출
    """
    
    def __init__(self, normalizer=None):
        self.normalizer = normalizer
    
    def extract_value_near_label(self, label_word: WordBox,
                                   word_boxes: List[WordBox],
                                   field_type: str,
                                   layout_threshold: float = None) -> Optional[Any]:
        if layout_threshold is None:
            layout_threshold = CONSTANTS['SPATIAL_DEFAULT_LAYOUT']
        
        # 후보 수집: 오른쪽 + 아래
        candidates = self._get_nearby_candidates(label_word, word_boxes, layout_threshold)
        
        if not candidates:
            return None
        
        # 타입별 파싱
        if field_type == "weight":
            return self._parse_weight_candidates(candidates)
        elif field_type == "date":
            return self._parse_date_candidates(candidates)
        elif field_type == "vehicle":
            return self._parse_vehicle_candidates(candidates)
        else:
            return self._parse_text_candidates(candidates)
    
    def _get_nearby_candidates(self, anchor: WordBox,
                                 word_boxes: List[WordBox],
                                 threshold: float) -> List[Tuple[float, WordBox]]:
        """
        앵커 근처 후보 수집 (거리순 정렬)
        """
        candidates = []
        
        for word in word_boxes:
            if word is anchor:
                continue
            
            # 조건 0: 앵커와 겹치는지 확인 (병합된 라벨에 속한 단어 제외)
            x_overlap = max(0, min(anchor.x_max, word.x_max) - max(anchor.x_min, word.x_min))
            y_overlap = max(0, min(anchor.y_max, word.y_max) - max(anchor.y_min, word.y_min))
            if x_overlap > 0 and y_overlap > 0:
                overlap_area = x_overlap * y_overlap
                word_area = (word.x_max - word.x_min) * (word.y_max - word.y_min)
                if word_area > 0 and (overlap_area / word_area) > CONSTANTS['OVERLAP_RATIO']:
                    continue
            
            # 조건 1: 오른쪽에 있음 (-20은 겹침/오차를 고려한 마진)
            is_right = word.x_min > anchor.x_max - 20
            
            # 조건 2: 세로 위치가 비슷함 (같은 라인 또는 바로 아래)
            y_diff = word.centroid[1] - anchor.centroid[1]
            is_same_or_below = CONSTANTS['SPATIAL_Y_MIN'] <= y_diff <= CONSTANTS['SPATIAL_Y_MAX']
            
            if is_right and is_same_or_below:
                x_dist = word.x_min - anchor.x_max
                
                # [수정] 같은 라인(Y오차 15이내) 우선순위 강력 부여
                if abs(y_diff) <= 15:
                    dist = x_dist * 0.5
                else:
                    # 줄바꿈 페널티 완화 (Sample 01 대응)
                    dist = x_dist + (abs(y_diff) * 3)
                
                if dist <= threshold:
                    candidates.append((dist, word))
        
        candidates.sort(key=lambda x: x[0])
        return candidates
    
    def _parse_weight_candidates(self, candidates: List[Tuple[float, WordBox]]) -> Optional[int]:
        """중량 파싱 (단위, 소수점 처리 포함)"""
        if not candidates: return None
        
        line_texts = []
        first_y = candidates[0][1].centroid[1]
        
        # 상위 5개 후보 중 같은 라인에 있는 것 수집
        for dist, word in candidates[:5]:
            if abs(word.centroid[1] - first_y) <= 50:
                line_texts.append(word.text)
        
        combined = " ".join(line_texts)
        
        # 단위 감지
        is_ton = bool(re.search(r'\b(ton|t|tons)\b', combined, re.IGNORECASE))
        
        # 숫자 추출 (단순화된 정규식)
        val_match = re.search(r'[\d,]+(\.\d+)?', combined)
        
        if val_match:
            try:
                val_str = val_match.group(0).replace(',', '')
                val_float = float(val_str)
                
                if is_ton or ('.' in val_str and val_float < 100):
                    val_float *= 1000
                
                val_int = int(round(val_float))
                
                if 10 <= val_int <= 100000:
                    return val_int
            except ValueError:
                pass
        return None
    
    def _parse_date_candidates(self, candidates: List[Tuple[float, WordBox]]) -> Optional[str]:
        combined = " ".join(w.text for _, w in candidates[:5])
        
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
            'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        
        mon_match = re.search(r'(\d{4})[-/\.\s]+([A-Za-z]{3})[-/\.\s]+(\d{1,2})', combined)
        if mon_match:
            y, m_str, d = mon_match.groups()
            m = month_map.get(m_str.capitalize())
            if m: return f"{y}-{m}-{d.zfill(2)}"
        
        dot_match = re.search(r'(\d{2,4})[\.\-/]\s*(\d{1,2})[\.\-/]\s*(\d{1,2})', combined)
        if dot_match:
            y, m, d = dot_match.groups()
            if len(y) == 2: y = "20" + y
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        return None
    
    def _parse_vehicle_candidates(self, candidates: List[Tuple[float, WordBox]]) -> Optional[str]:
        # X좌표 정렬 (경기99바1234 순서 보장)
        sorted_candidates = sorted(candidates[:8], key=lambda x: x[1].x_min)
        combined_nospace = "".join(w.text for _, w in sorted_candidates).replace(" ", "")
        
        match = re.search(r'([가-힣]{0,2})\d{2,3}[가-힣]\d{4}', combined_nospace)
        if match: return match.group()
            
        match = re.search(r'[A-Z]{1,3}[-\s]?\d{3,4}', combined_nospace)
        if match: return match.group()
            
        match = re.search(r'(?<!\d)\d{4}(?!\d)', combined_nospace)
        if match:
            num = match.group()
            if not num.startswith('202'): 
                return num
        return None
    
    def _parse_text_candidates(self, candidates: List[Tuple[float, WordBox]]) -> Optional[str]:
        if not candidates: return None
        
        line_texts = []
        first_y = candidates[0][1].centroid[1]
        
        sorted_candidates = sorted(candidates[:5], key=lambda x: x[1].x_min)
        for dist, word in sorted_candidates:
             if abs(word.centroid[1] - first_y) <= 30:
                 line_texts.append(word.text)

        full_text = " ".join(line_texts).strip()
        
        full_text = re.sub(r'^(Supplier|Customer|Vendor|Issuer)[\s:\.]+', '', full_text, flags=re.IGNORECASE)
        full_text = re.sub(r'^(전화|TEL|Tel|FAX|Fax|HP|H\.P)[\s:\.]*', '', full_text).strip()
        full_text = re.sub(r'[\d-]{9,}', '', full_text).strip()
        
        return full_text if len(full_text) > 1 else None
