import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가하여 모듈 임포트 허용
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
os.chdir(str(root_dir))

from extractors.normalizer import AdvancedNoiseNormalizer
from extractors.utils import fuzzy_match

normalizer = AdvancedNoiseNormalizer()

test_cases = [
    ("낱짜:", "날짜", "label"),
    ("샹호:", "상호", "label"),
    ("품면:", "품명", "label"),
    ("충중량:", "총중량", "label"),
    ("2O26-O1-15-OOO32", "2026-01-15", "number"),
    ("9l구1234", "91구1234", "number"),
    ("O234B7", "023487", "number"),
]

print(f"{'Original':<20} | {'Normalized':<20} | {'Target':<15} | {'Match'}")
print("-" * 75)

for original, target, context in test_cases:
    clean_original = original.replace(' ', '').replace(':', '')
    normalized = normalizer.normalize(clean_original, context=context)
    score = fuzzy_match(normalized, target)
    print(f"{original:<20} | {normalized:<20} | {target:<15} | {score:>5.1f}%")

# Test parse_date with normalized text
from extractors.utils import parse_date
date_text = "2O26-O1-15-OOO32"
norm_date = normalizer.normalize(date_text, context="number")
parsed = parse_date(norm_date)
print(f"\nDate Parsing: '{date_text}' -> '{norm_date}' -> '{parsed}'")
