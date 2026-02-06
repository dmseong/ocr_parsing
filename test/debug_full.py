
import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors import WordBox, SmartLabelDetector, SpatialValueExtractor, HeuristicValueFinder
from extractors.field_extractors import DateExtractor, VehicleExtractor

def test_full_debug():
    # Mock WordBoxes from sample_05
    # "게량일자 : 2O26-O2-O3"
    w1 = WordBox(text="게량일자", x_min=10, y_min=10, x_max=50, y_max=20, confidence=0.45)
    w2 = WordBox(text=":", x_min=55, y_min=10, x_max=60, y_max=20, confidence=0.95)
    w3 = WordBox(text="2O26-O2-O3", x_min=65, y_min=10, x_max=150, y_max=20, confidence=0.62)
    
    # "차 량 번 호 : 12가345B"
    w4 = WordBox(text="차", x_min=10, y_min=50, x_max=20, y_max=60, confidence=0.9)
    w5 = WordBox(text="량", x_min=25, y_min=50, x_max=35, y_max=60, confidence=0.9)
    w6 = WordBox(text="12가345B", x_min=100, y_min=50, x_max=200, y_max=60, confidence=0.58)

    word_boxes = [w1, w2, w3, w4, w5, w6]

    # Dependencies
    ld = SmartLabelDetector()
    se = SpatialValueExtractor()
    hf = HeuristicValueFinder() # normalizer=None for simplicity
    
    # 1. Date
    de = DateExtractor(ld, se, hf)
    print(f"Date Extracted: {de.extract(word_boxes)}")
    
    # 2. Vehicle
    ve = VehicleExtractor(ld, se, hf)
    print(f"Vehicle Extracted: {ve.extract(word_boxes)}")

if __name__ == "__main__":
    test_full_debug()
