import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가하여 모듈 임포트 허용
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
os.chdir(str(root_dir))

from extractors.normalizer import AdvancedNoiseNormalizer
from extractors.utils import extract_gps

text = "37.105317, 127.375673"
norm = AdvancedNoiseNormalizer()
text_num = norm.normalize(text, context='number')

print(f"RAW: '{text}'")
print(f"NORM (number): '{text_num}'")

gps = extract_gps(text_num)
print(f"GPS: {gps}")

# Test with full text from sample_01
full_text = "계 량 증 명 서 \n계량일자: 2026-02-02 0016 \n차량번호: 8713 \n거 래 처: 곰욕환경폐기물 \n품종명랑 05:26:18 12,480 kg \n명: \n중 량: \n05:36:01 7,470 kg \n실 중 량: 5,010 kg \n* 위와 같이 계량하였음을 확인함. \n동우바이오(주) \n2026-02-02 05:37:55 \n37.105317, 127.375673"
full_text_num = norm.normalize(full_text, context='number')
gps_full = extract_gps(full_text_num)
print(f"GPS (Full): {gps_full}")
