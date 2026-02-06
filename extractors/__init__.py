from .common import WordBox, LabelMatch, ExtractedField
from .config import LABEL_CONFIG, CONSTANTS
from .label_detector import SmartLabelDetector
from .spatial_extractor import SpatialValueExtractor
from .heuristic_finder import HeuristicValueFinder
from .core import SmartFieldExtractor

__all__ = [
    'WordBox', 'LabelMatch', 'ExtractedField',
    'LABEL_CONFIG', 'CONSTANTS',
    'SmartLabelDetector',
    'SpatialValueExtractor',
    'HeuristicValueFinder',
    'SmartFieldExtractor',
    'check_dependencies'
]

# 의존성 체크 함수 (app.py 등에서 사용)
def check_dependencies():
    from .common import HAS_SPACY, spacy, HAS_RAPIDFUZZ
    status = {
        'spacy': HAS_SPACY,
        'rapidfuzz': HAS_RAPIDFUZZ,
    }
    if HAS_SPACY and spacy:
        try:
            spacy.load('ko_core_news_sm')
            status['ko_model'] = True
        except OSError:
            status['ko_model'] = False
    else:
        status['ko_model'] = False
    return status
