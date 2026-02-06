# 📄 Hybrid OCR Parsing Engine

본 프로젝트는 계근지/영수증 OCR 데이터를 분석하여 정형화된 데이터로 추출하는 **하이브리드 파싱 엔진**입니다. 단순 텍스트 매칭을 넘어 공간 분석, 산술 검증, 그리고 자연어 처리를 결합하여 높은 정확도를 제공합니다.

---

## 🚀 실행 방법 (Local Reproduction)

### 1. 환경 구축
Python 3.12의 환경에서 다음 명령어를 실행하여 필수 라이브러리를 설치합니다.

```bash
# 의존성 패키지 설치
pip install -r requirements.txt

# spaCy 한국어 모델 설치 (필수)
python -m spacy download ko_core_news_sm
```

### 2. 대시보드 실행
Streamlit 기반의 시각화 도구를 통해 OCR JSON 파일을 업로드하고 파싱 결과를 실시간으로 확인할 수 있습니다.

```bash
streamlit run app.py
```

### 3. 테스트 및 성능 검증
전체 샘플 데이터(`sample_data_ocr/`)에 대한 추출 정확도를 테스트하고 리포트를 생성합니다.

```bash
# 전체 파싱 테스트 실행
python test/test_hybrid.py

# 정답지(answer.md)와 비교 및 정확도 리포트 생성
python test/compare_answer.py
```
*결과는 `comparison_report.txt`에 저장됩니다.

---

## 🛠️ 의존성 및 환경

- **Core**: Python 3.12.5
- **UI & Visualization**: `streamlit` (대시보드 운영)
- **Data Processing**: `pandas` (결합 및 통계)
- **NLP & Fuzzy Matching**: 
    - `spacy` (개체명 인식을 통한 발행처/회사명 추출)
    - `rapidfuzz` (OCR 오타 보정 및 라벨 매칭)
- **Custom Engines**:
    - `AdvancedNoiseNormalizer`: OCR 특화 오인식 교정 엔진 (O->0, B->8 등 및 문맥 보정)
    - `UnifiedWeightEngine`: 산술 검증 기반 중량 추출 엔진

---

## 🏗️ 설계 및 주요 가정

### 1. 하이브리드 추출 전략 (3-Layer)
- **Layer 1: Spatial Analysis**: 라벨과 숫자 간의 기하학적 거리와 정렬 상태를 분석합니다.
- **Layer 2: Heuristic Regex**: 전표번호, GPS 좌표, 날짜 등 정형화된 패턴을 정규식으로 정밀 타격합니다.
- **Layer 3: NLP NER**: 라벨이 없거나 모호한 발행처/업체명은 spaCy의 개체명 인식(NER)을 사용하여 문맥을 파악합니다.

### 2. 중량 추출의 앙상블 시스템
중량 데이터는 `총중량 = 공차중량 + 실중량`이라는 도메인 지식을 바탕으로 3가지 전략(방정식 기반, Y축 순서 기반, 키워드 근접성)을 투표(Ensemble Voting)시켜 최종 값을 결정합니다.

### 3. 주요 가정
- 모든 계량표에는 최소한 하나 이상의 일관된 중량 흐름이 존재한다고 가정합니다.
- OCR 데이터는 `WordBox` 단위의 좌표 정보(boundingBox)를 포함하고 있다고 가정하며, 없을 경우 텍스트 기반 휴리스틱 엔진으로 자동 전환됩니다.

---

## ⚠️ 한계 및 개선 아이디어

### 현재 한계
- **극심한 기울기(Tilt)**: OCR 엔진 자체가 기울어진 텍스트를 제대로 읽지 못했을 경우, 공간 분석 엔진의 성능이 저하될 수 있습니다.
- **다양한 규격**: 표준화되지 않은 매우 특이한 양식의 영수증에서는 정규식 패턴이 어긋날 가능성이 있습니다.

### 개선 아이디어
- **사용자 피드백 루프**: 대시보드에서 사용자가 수정한 데이터를 학습 데이터로 활용하여 파서의 가중치를 자동 갱신하는 기능.
- **LLM 하이브리드**: 현재의 규칙 기반 엔진이 "낮은 신뢰도"를 뱉었을 때만 선택적으로 LLM API(예: Gemini)를 호출하여 비용 효율적인 고정밀 파싱 구현.
- **Multi-page 지원**: 여러 장의 사진이 하나의 JSON으로 들어오는 경우를 위한 페이지 분할 및 통합 로직 강화.
