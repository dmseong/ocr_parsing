from typing import List, Optional, Any, Dict
from abc import ABC, abstractmethod
from .common import WordBox
from .label_detector import SmartLabelDetector
from .spatial_extractor import SpatialValueExtractor
from .normalizer import AdvancedNoiseNormalizer

class BaseExtractor(ABC):
    """모든 추출기의 기본 클래스"""
    
    def __init__(self, 
                 label_detector: SmartLabelDetector, 
                 spatial_extractor: SpatialValueExtractor,
                 heuristic_finder: 'HeuristicValueFinder',
                 normalizer: AdvancedNoiseNormalizer = None):
        self.label_detector = label_detector
        self.spatial_extractor = spatial_extractor
        self.heuristic_finder = heuristic_finder
        self.normalizer = normalizer or AdvancedNoiseNormalizer()

    def extract(self, word_boxes: List[WordBox], **kwargs) -> Any:
        """필드 추출 로직의 표준 흐름 제어"""
        extractor_name = self.__class__.__name__
        try:
            # print(f"[INFO] {extractor_name} started...")
            result = self._do_extract(word_boxes, **kwargs)
            if result:
                # print(f"[INFO] {extractor_name} success: {result}")
                pass
            return result
        except Exception as e:
            print(f"[ERROR] {extractor_name} failed: {e}")
            return None

    @abstractmethod
    def _do_extract(self, word_boxes: List[WordBox], **kwargs) -> Any:
        """실제 추출 로직 (하위 클래스에서 구현)"""
        pass

    def get_full_text(self, word_boxes: List[WordBox]) -> str:
        """WordBox 리스트를 하나의 텍스트로 합침"""
        return " ".join(w.text for w in word_boxes)

    def normalize_numbers(self, text: str) -> str:
        """숫자 오인식 보정 (중량, 날짜 등)"""
        return self.normalizer.normalize(text, context='number')
