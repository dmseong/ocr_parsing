# 📘 상세 분석 보고서 (Detailed Documentation)

본 문서는 `UnifiedOCRParser` 시스템의 핵심 기술 요소인 **Extractors**, **Confidence Score**, **BoundingBox**의 동작 원리와 구현 디테일을 다룹니다.

---

## 1. 🧶 Extractors (추출기 모듈)

### 기본 구조
- **`base.py` (BaseExtractor)**: 모든 추출기의 부모 클래스로, 공통 기능(라벨 탐지, 공간 분석 등)을 제공합니다.
- **`core.py` (SmartFieldExtractor)**: 파이프라인의 컨트롤 타워입니다. 개별 추출기들을 순차적으로 실행하고, 필드 간의 상호 의존성(예: Company vs Issuer)을 조율합니다.

### 핵심 알고리즘
#### 1. UnifiedWeightEngine (중량 추출)
중량 데이터는 가장 중요하면서도 오인식이 잦은 필드입니다. 이를 위해 **3중 앙상블(Ensemble)** 전략을 사용합니다.
1. **Equation (방정식)**: `총중량 = 공차 + 실중량` 공식이 성립하는 숫자 조합을 우선적으로 찾습니다. (오차범위 ±50kg)
2. **Spatial (공간 순서)**: 위에서부터 `Total -> Tare -> Net` 순으로 배치되는 문서의 일반적 특성을 활용합니다.
3. **Proximity (키워드 근접)**: "총", "실" 등의 키워드 주변에 있는 숫자를 탐색합니다.

> **💡 노이즈 보정**: `k9` → `kg`, `O` → `0`, `B` → `8` 등 OCR 오인식 패턴을 정규식으로 강력하게 보정합니다.

#### 2. SpatialValueExtractor (공간 분석)
텍스트의 의미가 아닌, **좌표(Coordinate)**를 기반으로 데이터를 찾습니다.
- **원리**: 라벨(Key)의 좌표 `(x_max, y_min)` 등을 기준으로 **우측** 또는 **하단**에 위치한 단어들을 검색합니다.
- **가중치**: 같은 라인(Y축 차이 15px 이내)에 있는 단어에 높은 점수를 부여하여 줄바꿈된 텍스트보다 우선순위를 높입니다.

#### 3. LabelDetector (Fuzzy Matching)
- **Levenshtein Distance**: OCR이 "중량"을 "즁량"으로, "날짜"를 "날짜l"로 잘못 인식하더라도, 문자열 간의 편집 거리를 계산하여 유사도가 높으면(70점 이상) 해당 라벨로 인정합니다.

### 4. 개별 추출기 파일 설명 (File Structure)

`extractors/` 폴더 내의 각 파일이 담당하는 역할과 구현 전략입니다.

| 파일명 | 클래스 (Class) | 주요 역할 및 특징 |
|---|---|---|
| `base.py` | `BaseExtractor` | 모든 추출기의 공통 부모 클래스. 라벨 탐지기, 공간 분석기 초기화 및 에러 핸들링을 담당합니다. |
| `core.py` | `SmartFieldExtractor` | 전체 추출 프로세스를 총괄하는 **Control Tower**. 개별 추출기를 호출하고, 상호 의존성(Company-Issuer)을 조율하며, 최종 신뢰도를 계산합니다. |
| `weight_engine.py` | `UnifiedWeightEngine` | **중량(Total/Tare/Net)** 전문 추출 엔진. 3중 앙상블(Equation, Spatial, Proximity) 전략과 단위(ton/kg) 자동 보정 로직을 포함합니다. |
| `field_extractors.py` | `DateExtractor` 등 | 중량을 제외한 나머지 필드(날짜, 차량번호, 상호, 전표번호 등)의 개별 추출 로직이 모여 있습니다. |
| `spatial_extractor.py` | `SpatialValueExtractor` | 텍스트의 의미가 아닌 **좌표(Coordinate)**를 기반으로 값을 찾는 핵심 모듈. 라벨의 우측/하단 영역을 분석합니다. |
| `normalizer.py` | `AdvancedNoiseNormalizer` | OCR 오인식(오타, 노이즈, 특수문자)을 문맥에 맞게 교정합니다. (예: `O`->`0`, `즁량`->`중량`) |
| `label_detector.py` | `SmartLabelDetector` | Fuzzy Matching(Levenshtein Distance)을 사용하여 오타가 포함된 라벨 키워드를 찾아냅니다. |

---

## 2. � Confidence Score (신뢰도 점수 산출)

추출된 데이터가 얼마나 믿을만한지 0~100점 사이의 점수로 수치화합니다. `confidence_scorer.py`에서 계산됩니다.

### 점수 산출 로직
**기본 점수**: 100점에서 시작하여, 결함이 발견될 때마다 감점하는 방식(Deduction System)입니다.

| 검사 항목 | 감점 루틴 | 설명 |
|---|---|---|
| **필수 필드 누락** | -20점/개 | 날짜, 차량번호, 총중량 등 핵심 데이터가 없으면 크게 감점됩니다. |
| **중량 방정식 오차** | -15~30점 | `Total - (Tare + Net)` 값이 0이 아니면 감점됩니다. (오차 크기에 비례) |
| **범위(Range) 위반** | -30점 | 예: 날짜의 '월'이 13월이라거나, 중량이 터무니없이 작거나 큰 경우. |
| **포맷(Format) 위반** | -20~40점 | 예: 차량번호가 "1234"(숫자만)로 추출된 경우 (정상: "12가3456"). |

### 검수 우선순위 (Review Priority)
산출된 점수에 따라 데이터의 처리 방식을 결정합니다.
- **PASS (90점▲)**: 자동 승인.
- **LOW (75점▲)**: 경미한 이슈(예: 단순 오타 보정됨). 자동 처리 가능.
- **MEDIUM (50점▲)**: 확인 권장. 주요 데이터는 있으나 일부 포맷이 이상함.
- **HIGH / CRITICAL (50점▼)**: **필수 검수**. 데이터가 누락되었거나 논리적으로 말이 안 됨.

---

## 3. 📦 BoundingBox (좌표계 데이터 모델)

OCR 엔진이 반환하는 원본 데이터를 다루기 쉬운 객체로 변환하여 사용합니다. `common.py`에 정의되어 있습니다.

### WordBox 객체 구조
```python
@dataclass
class WordBox:
    text: str       # 인식된 텍스트
    x_min: float    # 좌측 좌표
    y_min: float    # 상단 좌표
    x_max: float    # 우측 좌표
    y_max: float    # 하단 좌표
    confidence: float # OCR 엔진 자체 신뢰도
```

### 공간 분석 활용
이 좌표 정보를 이용하여 다음과 같은 고차원적인 분석을 수행합니다:
1. **Centroid (중심점) 계산**: `(x_min + x_max) / 2` 를 통해 단어의 중심 위치를 파악합니다.
2. **Line Clustering (라인 그룹화)**: Y축 중심점 차이가 적은(예: 10px 이내) 단어들을 하나의 '줄(Line)'로 묶습니다.
3. **Relative Position (상대 위치)**: "A 단어의 `x_max`보다 B 단어의 `x_min`이 큰가?"를 통해 단어 간의 좌우 배치를 판단합니다.

---

## 4. � 결론 및 활용 가이드

이 시스템은 단순한 텍스트 매칭이 아닌, **공간(위치)**과 **문맥(Context)**, 그리고 **도메인 지식(중량 공식 등)**을 결합하여 작동합니다.

- **데이터가 잘 안 뽑힌다면?**
    - `extractors/` 내의 해당 필드 추출기 로직을 확인하세요.
    - 특히 `SpatialValueExtractor`의 거리 임계값(Threshold) 조절이 필요할 수 있습니다.
- **점수가 너무 낮게 나온다면?**
    - `confidence_scorer.py`의 감점 규칙(Rule)이 너무 엄격한지 확인해 보세요.
    - 입력 이미지의 품질(기울어짐, 흐릿함)이 원인일 수도 있습니다.
