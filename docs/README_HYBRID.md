# spaCy 기반 하이브리드 OCR 파싱 시스템 (v5)

## 📋 개요

이 시스템은 계근표(Weight Ticket) OCR 데이터의 노이즈를 처리하고 정형화된 데이터를 추출합니다.

### 핵심 특징
- **하이브리드 파싱**: Regex 기반 + spaCy 토큰 레벨 패턴 매칭
- **설정 기반 확장**: 라벨 패턴을 LABEL_CONFIG로 중앙 관리
- **신뢰도 평가**: 도메인 규칙 기반 검증 및 검수 필요 플래그
- **Graceful Degradation**: spaCy 없이도 동작

## 📁 파일 구조

```
reco/
├── parsing.py              # 기존 파서 (참고용 유지)
├── extractors/             # spaCy 기반 스마트 추출기 패키지 (리팩토링됨)
├── confidence_scorer.py    # 신뢰도 평가 시스템 (신규)
├── hybrid_parser.py        # 통합 하이브리드 파서 (신규)
├── test_hybrid.py          # 비교 테스트 스크립트 (신규)
└── docs/
    └── architecture_hybrid.md  # 시스템 아키텍처 문서
```

## 🚀 빠른 시작

### 1. 의존성 설치 (선택적)

```bash
# spaCy 설치 (선택적 - 없어도 동작)
pip install spacy
python -m spacy download ko_core_news_sm
```

### 2. 기본 사용법

```python
from hybrid_parser import HybridOCRParser
import json

# 파서 생성
parser = HybridOCRParser()

# OCR JSON 파싱
with open('ocr_result.json', 'r', encoding='utf-8') as f:
    ocr_data = json.load(f)

result = parser.parse(ocr_data)

# 결과 확인
print(f"날짜: {result['date']}")
print(f"차량번호: {result['vehicle_num']}")
print(f"총중량: {result['total_weight']} kg")
print(f"신뢰도: {result['_overall_confidence']}%")
print(f"검수 필요: {result['_needs_review']}")
```

### 3. 배치 처리

```python
from confidence_scorer import ReviewBatchProcessor

# 여러 결과를 분류
processor = ReviewBatchProcessor()
batch = processor.process_batch(results_list)

print(f"검수 불필요: {len(batch['passed'])}건")
print(f"자동 보정됨: {len(batch['auto_fixed'])}건")
print(f"검수 필요: {len(batch['needs_review'])}건")
print(f"파싱 실패: {len(batch['failed'])}건")
```

## 📊 성능 비교 (7개 샘플 기준)

| 지표 | Legacy | Hybrid |
|------|--------|--------|
| 날짜 추출 | 7/7 | 7/7 |
| 차량번호 | 7/7 | 7/7 |
| 중량 추출 | 4/7 | 4/7 |
| 회사명 | 3/7 | 3/7 |
| 평균 신뢰도 | N/A | 86.9% |

## 🔧 핵심 모듈

### SmartLabelDetector
spaCy Matcher를 활용한 라벨 탐지

```python
# 토큰 레벨 패턴 매칭
# "총 중 량" → "총중량" 인식
# "フㅓㄹh처" → "거래처" Fuzzy 매칭
```

### SpatialValueExtractor
라벨 근처에서 공간 거리 기반 Value 추출

### HeuristicValueFinder
라벨 없을 때 방정식 역추론 (Total = Tare + Net)

### ConfidenceScorer
필드별 신뢰도 계산 및 검수 우선순위 분류

## 📌 검수 우선순위

| 우선순위 | 신뢰도 | 설명 |
|----------|--------|------|
| NONE | ≥90% | 검수 불필요 |
| LOW | ≥75% | 자동 보정됨 |
| MEDIUM | ≥50% | 확인 권장 |
| HIGH | ≥25% | 반드시 검수 |
| CRITICAL | <25% | 파싱 실패 |

## 🔮 향후 개선

1. **학습 데이터 구축**: 현재 규칙 기반 → ML 기반 전환 준비
2. **라벨 임베딩**: Fuzzy Matching → 의미적 유사도 기반
3. **Layout 학습**: 공간 관계 → 학습 기반 추론
