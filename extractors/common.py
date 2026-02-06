"""
공통 데이터 모델 및 유틸리티
"""
from dataclasses import dataclass, field
from typing import List, Tuple, Any, Optional, Dict

# spaCy import with fallback
try:
    import spacy
    from spacy.matcher import Matcher
    from spacy.tokens import Doc, Span
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    spacy = None
    Matcher = None

# rapidfuzz import with fallback
try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    from difflib import SequenceMatcher

@dataclass
class WordBox:
    """단어와 bounding box 정보"""
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float = 0.0
    
    @property
    def centroid(self) -> Tuple[float, float]:
        return ((self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2)
    
    @property
    def width(self) -> float:
        return self.x_max - self.x_min
    
    @property
    def height(self) -> float:
        return self.y_max - self.y_min

@dataclass
class ExtractedField:
    """추출된 필드 정보"""
    field_name: str
    value: Any
    confidence: float
    source_method: str
    source_words: List[WordBox] = field(default_factory=list)

@dataclass
class LabelMatch:
    """라벨 매칭 결과"""
    label_type: str  # e.g., "total_weight"
    matched_text: str
    match_score: float
    word_box: Optional[WordBox] = None

@dataclass
class Line:
    """좌표 기반으로 그룹화된 라인"""
    words: List[WordBox]
    y_avg: float
    
    def get_text(self, sep: str = " ") -> str:
        return sep.join(w.text for w in self.words)

@dataclass
class DocumentLayout:
    """문서 레이아웃 특성"""
    avg_char_width: float
    avg_line_height: float
    avg_word_spacing: float
    page_width: float = 0.0
    page_height: float = 0.0
    
    @property
    def x_threshold(self) -> float:
        """X축 탐색 임계값 (같은 라인 내)"""
        return max(self.avg_char_width * 50, 300)
    
    @property
    def y_threshold_same_line(self) -> float:
        """같은 라인 판단 임계값"""
        return max(self.avg_line_height * 0.5, 30)
    
    @property
    def y_threshold_next_line(self) -> float:
        """다음 라인 탐색 임계값"""
        return max(self.avg_line_height * 2.5, 100)

def get_empty_result() -> Dict[str, Any]:
    """빈 결과 템플릿"""
    return {
        "date": None,
        "vehicle_num": None,
        "total_weight": None,
        "tare_weight": None,
        "net_weight": None,
        "company": None,
        "product": None,
        "type": None,
        "ticket_id": None,
        "issuer": None,
        "gps": None,
        "phone": None,
        "address": None,
    }

def extract_word_boxes(json_data: dict) -> List[WordBox]:
    """WordBox 추출"""
    words = []
    if 'pages' not in json_data or not json_data['pages']: return words
    page = json_data['pages'][0]
    if 'words' not in page: return words
    for word_data in page['words']:
        text = word_data.get('text', '').strip()
        bbox = word_data.get('boundingBox', {})
        if not text or 'vertices' not in bbox: continue
        vertices = bbox['vertices']
        if len(vertices) < 4: continue
        x_coords = [v['x'] for v in vertices]
        y_coords = [v['y'] for v in vertices]
        words.append(WordBox(
            text=text, x_min=min(x_coords), y_min=min(y_coords),
            x_max=max(x_coords), y_max=max(y_coords),
            confidence=word_data.get('confidence', 0.0)
        ))
    return words

def analyze_layout(word_boxes: List[WordBox]) -> DocumentLayout:
    """레이아웃 분석"""
    import statistics
    if not word_boxes: return DocumentLayout(10, 20, 5, 1000, 1000)
    char_widths = []
    for word in word_boxes:
        if len(word.text) > 0: char_widths.append(word.width / len(word.text))
    avg_char_width = statistics.median(char_widths) if char_widths else 10
    line_heights = [w.height for w in word_boxes if w.height > 0]
    avg_line_height = statistics.median(line_heights) if line_heights else 20
    
    word_spacings = []
    sorted_words = sorted(word_boxes, key=lambda w: (w.centroid[1], w.centroid[0]))
    for i in range(len(sorted_words) - 1):
        w1, w2 = sorted_words[i], sorted_words[i + 1]
        if abs(w1.centroid[1] - w2.centroid[1]) <= avg_line_height:
            spacing = w2.x_min - w1.x_max
            if spacing > 0: word_spacings.append(spacing)
    avg_word_spacing = statistics.median(word_spacings) if word_spacings else 5
    page_width = max(w.x_max for w in word_boxes)
    page_height = max(w.y_max for w in word_boxes)
    return DocumentLayout(avg_char_width, avg_line_height, avg_word_spacing, page_width, page_height)

def cluster_lines(word_boxes: List[WordBox], layout: DocumentLayout) -> List[Line]:
    """라인 클러스터링"""
    if not word_boxes: return []
    sorted_words = sorted(word_boxes, key=lambda w: w.centroid[1])
    lines = []
    current_line = [sorted_words[0]]
    current_y = sorted_words[0].centroid[1]
    for word in sorted_words[1:]:
        if abs(word.centroid[1] - current_y) <= layout.y_threshold_same_line:
            current_line.append(word)
        else:
            current_line.sort(key=lambda w: w.centroid[0])
            y_avg = sum(w.centroid[1] for w in current_line) / len(current_line)
            lines.append(Line(words=current_line, y_avg=y_avg))
            current_line = [word]
            current_y = word.centroid[1]
    if current_line:
        current_line.sort(key=lambda w: w.centroid[0])
        y_avg = sum(w.centroid[1] for w in current_line) / len(current_line)
        lines.append(Line(words=current_line, y_avg=y_avg))
    return lines
