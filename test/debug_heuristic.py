

import sys
import os
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors.heuristic_finder import HeuristicValueFinder

def test_heuristic_debug():
    finder = HeuristicValueFinder()
    
    # Sample 05 Noisy Text (Directly from JSON)
    original_text = "** 게 량 중 멍 셔 **\n게량일자 : 2O26-O2-O3\n차 량 번 호 : 12가345B\n거 래 처 : 대한리싸이클\n"
    
    print(f"Original: {original_text}")
    
    # 1. Date
    date = finder.find_date_in_text(original_text)
    print(f"Date Result: {date}")
    
    # 2. Vehicle
    veh = finder.find_vehicle_in_text(original_text)
    print(f"Vehicle Result: {veh}")
    
    # Clean check
    clean = finder._normalize_ocr_digits(original_text)
    print(f"Normalized: {clean}")

if __name__ == "__main__":
    test_heuristic_debug()
