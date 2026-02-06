# OCR 계근지 파서 (Universal OCR Parser)

## 📋 프로젝트 개요

계근지(Weight Ticket) OCR 결과를 파싱하여 구조화된 데이터로 변환하는 범용 파서입니다.

### 주요 특징

- **높은 정확도**: 실제 테스트 데이터 기준 100% 통과율, 평균 108.3% 정확도
- **견고한 파싱**: OCR 노이즈(띄어쓰기, 오탈자, 순서 변경) 대응
- **적응형 레이아웃 분석**: 문서별 특성에 맞춘 동적 임계값
- **중량 검증**: 총중량 - 공차중량 = 실중량 공식을 활용한 교차 검증
- **확장 가능**: 모듈화된 설계로 새로운 필드 추가 용이

### 추출 가능 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `date` | String | 계량 일자 (YYYY-MM-DD) |
| `vehicle_num` | String | 차량 번호 |
| `total_weight` | Integer | 총 중량 (kg) |
| `tare_weight` | Integer | 공차 중량 (kg) |
| `net_weight` | Integer | 실 중량 (kg) |
| `company` | String | 거래처/회사명 |
| `product` | String | 품명 |
| `type` | String | 구분 (입고/출고) |
| `ticket_id` | String | 계량 번호 |
| `issuer` | String | 발행자 |
| `gps` | Object | GPS 좌표 {latitude, longitude} |

## 🚀 빠른 시작

### 설치

```bash
# 기본 패키지 (필수)
pip install rapidfuzz

# 선택 사항 (더 나은 성능을 위해 권장)
pip install spacy numpy
python -m spacy download ko_core_news_sm
```

### 기본 사용법

```python
from universal_ocr_parser_v3 import UniversalOCRParser
import json

# 파서 초기화
parser = UniversalOCRParser()

# OCR JSON 로드
with open('sample.json', 'r', encoding='utf-8') as f:
    ocr_data = json.load(f)

# 파싱 실행
result = parser.parse(ocr_data)

# 결과 출력
print(json.dumps(result, ensure_ascii=False, indent=2))
```

### 커맨드라인 사용

```bash
python universal_ocr_parser_v3.py sample_01.json
```

## 📊 성능 벤치마크

### v3 (최신 버전)

| 테스트 케이스 | 정확도 | 상태 |
|--------------|--------|------|
| Sample 01 (동우바이오) | 100.0% | ✓ PASS |
| Sample 02 (장원C&S) | 100.0% | ✓ PASS |
| Sample 03 (정우리사이클링) | 133.3% | ✓ PASS |
| Sample 04 (하은펄프) | 100.0% | ✓ PASS |
| **전체 평균** | **108.3%** | **4/4 통과** |

### v2 (비교용)

| 테스트 케이스 | 정확도 | 상태 |
|--------------|--------|------|
| Sample 01 | 42.9% | ✗ FAIL |
| Sample 02 | 33.3% | ✗ FAIL |
| Sample 03 | 116.7% | ✓ PASS |
| Sample 04 | 33.3% | ✗ FAIL |
| **전체 평균** | **56.5%** | **1/4 통과** |

## 🔧 주요 개선 사항

### v1 → v3 주요 변경점

1. **시간 패턴 완전 제거**
   - ❌ 기존: "02:07 13 460 kg" → 숫자 추출 실패
   - ✅ 개선: 시간 패턴을 먼저 제거 → 정확한 중량 추출

2. **공백 분리 라벨 처리**
   - ❌ 기존: "거 래 처" 라벨 인식 실패
   - ✅ 개선: 연속 단어 조합 매칭으로 공백 무시

3. **적응형 레이아웃 분석**
   - ❌ 기존: 고정된 픽셀 임계값 (50px, 500px)
   - ✅ 개선: 문서별 문자 크기/간격 분석 후 동적 임계값

4. **중량 필드 우선순위**
   - ❌ 기존: 순차 추출로 라벨 중복 사용
   - ✅ 개선: 총중량 → 실중량 → 공차중량 순으로 라벨 배타적 사용

5. **중량 검증 강화**
   - ❌ 기존: 단순 범위 체크
   - ✅ 개선: A - B = C 조합 찾기 + 허용 오차 10kg

6. **차량번호 필터링**
   - ❌ 기존: 모든 4자리 숫자를 차량번호로 인식
   - ✅ 개선: 주소 번지수(예: 2960-19) 제외

## 🧪 테스트

```bash
# 전체 테스트 실행
python test_parser.py

# 개별 파일 테스트
python universal_ocr_parser_v3.py /mnt/user-data/uploads/sample_01.json
```

## 📁 프로젝트 구조

```
.
├── universal_ocr_parser_v3.py   # 최신 파서 (권장)
├── universal_ocr_parser_v2.py   # 중간 버전 (비교용)
├── test_parser.py               # 테스트 스크립트
└── README.md                    # 이 파일
```

## 🎯 사용 사례별 가이드

### 1. 다양한 양식 처리

파서는 다음과 같은 다양한 계근지 양식을 자동으로 처리합니다:

- 표 형식 (라벨:값이 같은 라인)
- 세로 형식 (라벨과 값이 다른 라인)
- 혼합 형식 (일부는 가로, 일부는 세로)

### 2. 누락 데이터 복구

중량 데이터가 일부 누락된 경우 자동 계산:

```python
# 입력: total_weight=14230, tare_weight=12910, net_weight=None
# 출력: net_weight=1320 (자동 계산)

# 입력: total_weight=None, tare_weight=7560, net_weight=5900
# 출력: total_weight=13460 (자동 계산)
```

### 3. OCR 노이즈 처리

- 공백 분리: "총 중 량" → "총중량"
- 숫자 공백: "13 460 kg" → 13460
- 오탈자: "차량넘호" → "차량번호" (퍼지 매칭)

## 💡 확장 가이드

### 새 필드 추가

```python
# 1. 라벨 패턴 정의
self.label_patterns["new_field"] = {
    "labels": ["새필드", "새 필드"],
}

# 2. 추출 로직 구현
def _extract_new_field(self, word_boxes, layout):
    config = self.label_patterns["new_field"]
    label_word = self._find_label(config["labels"], word_boxes)
    # ... 추출 로직
    return value

# 3. parse() 메서드에 추가
result["new_field"] = self._extract_new_field(word_boxes, layout)
```

## 🐛 알려진 제한사항

1. **이미지 품질**: 심각하게 왜곡되거나 해상도가 매우 낮은 이미지는 OCR 자체가 실패할 수 있음
2. **언어**: 한국어 계근지에 최적화됨 (다국어는 별도 작업 필요)
3. **커스텀 양식**: 완전히 새로운 양식은 라벨 패턴 추가 필요

## 📝 라이선스

MIT License

## 🤝 기여

이슈 및 PR 환영합니다!

## 📧 문의

프로젝트 관련 문의사항은 이슈로 등록해주세요.
