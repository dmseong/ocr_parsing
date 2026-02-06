---
description: 프로젝트 코딩 규칙, 저장 위치 및 스킬 활용 가이드
---

# 1. 파일 저장 위치 & 구조
- **메인 소스**: `c:\Users\2with\OneDrive\Desktop\assign\other\reco\`
- **문서**: `docs/` (예: `architecture.md`, `README.md`)
- **테스트**: `test_*.py`, `debug_*.py` 파일들은 루트에 위치하거나 `test/` 폴더 사용
- **데이터**: `sample_data_ocr/` (OCR JSON 샘플)
- **임시 파일**: `tmp/` (필요 시에만 사용)

# 2. 코딩 스타일 가이드
- **언어**: Python 3.12 
- **인코딩**: **UTF-8 필수** (Windows 환경에서 한글 깨짐 방지 위해 입출력 시 `encoding='utf-8'` 명시)
- **타입 힌트**: `typing` 모듈을 사용하여 명시적 타입 정의 (`List[str]`, `Optional[int]`, `Dict[str, Any]` 등)
- **Docstring**: 함수/클래스에 대한 명확한 한글 설명 포함
- **모듈화**: 기능별로 파일을 분리 (`parsing.py`, `smart_extractors.py` 등)하여 유지보수성 확보

# 3. 테스트 및 검증 규칙
- **회귀 테스트**: 기능 수정 후 반드시 `sample_01` ~ `sample_07` 전체에 대해 `test_hybrid.py` 실행
- **신뢰도 검증**: 데이터 추출 시 도메인 규칙(방정식 검증, 비율 검사 등)을 통과해야 함
- **예외 처리**: OCR 데이터의 노이즈, 누락, 포맷 변경에 대해 Graceful Degradation(우아한 실패/대체 로직) 구현

# 4. 스킬 및 리소스 활용
사용자가 지정한 스킬 리소스를 적극 활용하여 코드 품질과 UI를 개선한다.

## 참고 리소스
- **Everything Claude Code**: https://github.com/affaan-m/everything-claude-code
- **Skills.sh**: https://skills.sh
- **Antigravity Awesome Skills**: https://github.com/sickn33/antigravity-awesome-skills
- **Anthropic Skills**: https://github.com/anthropics/skills/tree/main/skills

## 스킬 적용 원칙
- 코드 구조 개선 시 `python-expert` 또는 `clean-code` 관련 스킬 적용

# 5. 코드 품질 및 유지보수
- **하드코딩 지양**: 매직 넘버, 키워드 리스트, 정규식 패턴 등은 코드 내에 직접 작성하지 말고 `CONSTANTS`나 설정 파일로 분리하여 관리.
- **범용성 확보**: 특정 데이터 샘플에만 과적합(Overfitting)되지 않도록 일반화된 로직 구현.
- **리팩토링 용이성**: 함수는 단일 책임(Single Responsibility)을 갖도록 작게 분리하고, 의존성을 명확히 하여 추후 수정이 쉽도록 설계.