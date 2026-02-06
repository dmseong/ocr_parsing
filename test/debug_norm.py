import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가하여 모듈 임포트 허용
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
os.chdir(str(root_dir))

import json
from extractors.normalizer import AdvancedNoiseNormalizer

with open('sample_data_ocr/sample_06_noisy.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

raw_text = data['pages'][0]['text']
norm = AdvancedNoiseNormalizer()
label_text = norm.normalize(raw_text, context='label')

print("--- RAW TEXT ---")
print(repr(raw_text))
print("\n--- NORMALIZED LABEL TEXT ---")
print(repr(label_text))

# Test regex
import re
labels = ["거래처", "상호"]
for label in labels:
    pattern = rf'{label}\s*[:：\s-]*\s*([가-힣\(\)A-Z0-9]+)'
    match = re.search(pattern, label_text)
    if match:
        print(f"\nMATCH FOUND for {label}: '{match.group(1)}'")
    else:
        print(f"\nNO MATCH for {label}")
