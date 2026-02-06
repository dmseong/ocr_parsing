import re
from typing import List, Dict, Any, Optional
from .common import WordBox
from .label_detector import SmartLabelDetector
from .spatial_extractor import SpatialValueExtractor
from .heuristic_finder import HeuristicValueFinder
from .config import CONSTANTS, KEYWORDS


def normalize_ocr_digits(text: str) -> str:
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

class WeightExtractor:
    """중량 전문 추출기 (UnifiedWrapper)"""
    
    def __init__(self, unified_engine):
        self.unified_engine = unified_engine
    
    def extract(self, word_boxes: List[WordBox]) -> Dict[str, Any]:
        """UnifiedWeightEngine에 위임"""
        # Layout 정보가 필요한데 현재 인터페이스엔 없음. 
        # UnifiedEngine은 Layout을 요구하므로 계산해서 넘겨줌.
        from .common import analyze_layout
        layout = analyze_layout(word_boxes)
        return self.unified_engine.extract_weights(word_boxes, layout)

class DateExtractor:
    def __init__(self, label_detector, spatial_extractor, heuristic_finder):
        self.label_detector = label_detector
        self.spatial_extractor = spatial_extractor
        self.heuristic_finder = heuristic_finder
        
    def extract(self, word_boxes: List[WordBox]) -> Optional[str]:
        # 전략 1
        label_word = self.label_detector.find_label_in_wordboxes("date", word_boxes)
        if label_word:
            print(f"[DEBUG] Date Label Found: {label_word.text}")
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "date")
            if value: 
                print(f"[DEBUG] Date Spatial Value: {value}")
                return value
        
        print("[DEBUG] Date Label Not Found or Spatial Failed -> Try Heuristic")
        # 전략 2
        full_text = " ".join(w.text for w in word_boxes)
        # print(f"[DEBUG] Full Text: {full_text}")
        return self.heuristic_finder.find_date_in_text(full_text)

        # Fallback 3: Explicit Regex (Legacy Style) with Normalization
        # YYYY-MM-DD or YYYY.MM.DD
        clean_text = normalize_ocr_digits(full_text)
        match = re.search(r'20\d{2}[-./]\d{1,2}[-./]\d{1,2}', clean_text)
        if match:
             return match.group().replace('.', '-').replace('/', '-')
        return None

class VehicleExtractor:
    def __init__(self, label_detector, spatial_extractor, heuristic_finder):
        self.label_detector = label_detector
        self.spatial_extractor = spatial_extractor
        self.heuristic_finder = heuristic_finder
        
    def extract(self, word_boxes: List[WordBox]) -> Optional[str]:
        label_word = self.label_detector.find_label_in_wordboxes("vehicle", word_boxes)
        if label_word:
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "vehicle")
            if value: return value
        full_text = " ".join(w.text for w in word_boxes)
        val = self.heuristic_finder.find_vehicle_in_text(full_text)
        if val: return val
        
        # Fallback 3: Loose Regex (Legacy Style) with Normalization
        clean_text = normalize_ocr_digits(full_text)
        candidates = []
        for match in re.finditer(r'(?<![-/])\b\d{4}\b(?![-/])', clean_text):
            num = match.group()
            if not num.startswith('202'):
                candidates.append(num)
        if candidates: return candidates[0]
        
        return None

class CompanyExtractor:
    def __init__(self, label_detector, spatial_extractor):
        self.label_detector = label_detector
        self.spatial_extractor = spatial_extractor
        
    def extract(self, word_boxes: List[WordBox]) -> Optional[str]:
        label_word = self.label_detector.find_label_in_wordboxes("company", word_boxes, threshold=60)
        if label_word:
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "text", layout_threshold=300)
            if value: return value
        for i, word in enumerate(word_boxes):
            if "귀하" in word.text and i > 0:
                return word_boxes[i-1].text.strip()
                
        # Fallback: Full Text Pattern Search (Legacy Logic)
        full_text = " ".join(w.text for w in word_boxes)
        # 상호 : 청정그린 형태 대응 (다음 라벨이나 콜론 직전까지)
        labels = ["거래처", "상호"]
        for label in labels:
            pattern = rf'{label}\s*[:：\s-]*\s*([가-힣\(\)A-Z0-9]+)'
            match = re.search(pattern, full_text)
            if match:
                val = match.group(1).strip()
                # 품명 등 다른 라벨이 섞여 들어간 경우 잘라내기
                for stopper in ['품명', '구분', '날짜', '차량']:
                    if stopper in val:
                        val = val.split(stopper)[0].strip()
                
                if len(val) >= 2 and val not in ['입고', '출고', '품명', '차량', '계량']:
                    return val
        # Fallback 2: "귀하" 패턴 확장
        match = re.search(r'([가-힣\(\)A-Z0-9]+)\s*귀하', full_text)
        if match:
            return match.group(1).strip()
            
        # Fallback 3: Stronger Regex for Company (Noisy Label)
        # 거 래 처 : ...
        match = re.search(r'[거기]\s*[래례]\s*[처체]\s*[:;]\s*([가-힣]+)', full_text)
        if match:
            val = match.group(1).strip()
            if len(val) >= 2: return val
            
        return None

class IssuerExtractor:
    def __init__(self, label_detector):
        self.label_detector = label_detector
        
    def extract(self, word_boxes: List[WordBox]) -> Optional[str]:
        if not word_boxes: return None
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
                if word.x_min < 100: score -= 20
            elif cy <= top_threshold:
                if any(k in text for k in KEYWORDS['ISSUER_CORP']): score += 50
                if any(k in text for k in KEYWORDS['ISSUER_TYPE']): score += 40
                if any(k in text for k in KEYWORDS['ISSUER_HEADER_SKIP']): score = 0
                if "귀하" in text: score = 0
            if score >= 30:
                candidates.append((score, word))
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates:
            issuer = self._expand_issuer_name(candidates[0][1], word_boxes)
            return issuer
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

class PhoneExtractor:
    def __init__(self, label_detector, spatial_extractor):
        self.label_detector = label_detector
        self.spatial_extractor = spatial_extractor
        
    def extract(self, word_boxes: List[WordBox]) -> Optional[str]:
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
        full_text = " ".join(w.text for w in word_boxes)
        patterns = [r'0\d{1,2}-\d{3,4}-\d{4}', r'\(\d{2,3}\)\d{3,4}-\d{4}']
        for pattern in patterns:
            match = re.search(pattern, full_text)
            if match: return match.group()
        return None

class ProductExtractor:
    def __init__(self, label_detector, spatial_extractor):
        self.label_detector = label_detector
        self.spatial_extractor = spatial_extractor
        
    def extract(self, word_boxes: List[WordBox]) -> Optional[str]:
        label_word = self.label_detector.find_label_in_wordboxes("product", word_boxes, threshold=60)
        if label_word:
            value = self.spatial_extractor.extract_value_near_label(label_word, word_boxes, "text", layout_threshold=CONSTANTS['LABEL_MERGE_DIST_X'])
            if value and self._is_valid_product(value): return value
            
        # Fallback: Full Text Regex Search (Legacy Logic)
        full_text = " ".join(w.text for w in word_boxes)
        labels = ["품명", "품면", "제 품 명"]
        for label in labels:
            # 구분, 입고, 출고 등의 키워드 앞에서 멈춤
            # [Fix] 영문/숫자 허용 (플라스틱 PE 등)
            pattern = rf'{label.replace(" ", "\s*")}\s*[:：]?\s*([가-힣A-Za-z0-9 ]+?)(?=\s*(?:구분|입고|출고|날짜|차량|발행|총중량|실중량|공차중량|ID-NO)|[:：]|$)'
            match = re.search(pattern, full_text)
            if match:
                val = match.group(1).strip()
                if len(val) >= 1:
                    # [Fix] "총 중 량" 등이 잡히는 것 방지
                    if val.replace(" ", "") in ['총중량', '실중량', '공차중량', '차중량', '중량', '계량', '계량표', '증명서']:
                        return None
                    return val
        return None
        return None
        
    def _is_valid_product(self, text: str) -> bool:
        if re.search(r'\d{1,2}시', text) or re.search(r'\d{1,2}:\d{2}', text): return False
        if re.search(r'\d{4}-\d{2}-\d{2}', text) or re.search(r'\d{4}\.\d{2}\.\d{2}', text): return False
        clean = text.replace(",", "").replace(" ", "").lower()
        if re.match(r'^\d+(\.\d+)?(kg|ton|g|t)?$', clean): return False
        return True
