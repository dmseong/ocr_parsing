import re
import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가하여 모듈 임포트 허용
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
os.chdir(str(root_dir))

from extractors.normalizer import AdvancedNoiseNormalizer
from extractors.utils import extract_address

text = """
정우리사이클링 (주)
경기도 화성시 팔탄면 노하길454번길 23
Tel) 031-354-7778
* 상기와 같이 계량하였음을 증명합니다. *
2026-02-01 11:55:35
"""

norm = AdvancedNoiseNormalizer()
norm_text = norm.normalize(text, context='label')

print(f"--- NORMALIZED TEXT ---\n{repr(norm_text)}\n")

addr = extract_address(norm_text)
print(f"--- EXTRACTED ADDRESS ---\n{repr(addr)}\n")

# Manual regex test
region = "경기도"
pattern = rf'({region}\s*[가-힣]+(?:시|군|구).*?)(?=\s*(?:Tel|Tel\)|FAX|Fax|\*|20\d{{2}}[-.]|$))'
match = re.search(pattern, norm_text, re.IGNORECASE)
if match:
    print(f"REGEX MATCH: '{match.group(1)}'")
    print(f"FOLLOWING TEXT: '{norm_text[match.end():][:20]}'")
else:
    print("NO REGEX MATCH")
