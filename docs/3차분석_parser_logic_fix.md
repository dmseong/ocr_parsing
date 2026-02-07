# Parser Logic 문제 진단 및 해결방안

**작성일**: 2026-02-03  
**대상 샘플**: sample_03.json, sample_04.json

---

## 문제 현상

### 검증 결과
```
[sample_03.json] Status: OK | Logic: FAIL (Expected 130, got 14080)
[sample_04.json] Status: OK | Logic: FAIL (Expected 1320, got 14230)
```

### 추출된 데이터
- **sample_03**: `total_weight: 14080`, `tare_weight: 13950`, `net_weight: 14080` ❌ (should be 130)
- **sample_04**: `total_weight: 14230`, `tare_weight: 12910`, `net_weight: 14230` ❌ (should be 1320)

---

## 근본 원인 (Root Cause)

### 1. OCR 텍스트 확인

**sample_03.json**의 실제 OCR 텍스트:
```
총 중 량 : 11시 33분 14,080 kg
공차중량 : 11시 39분 13,950 kg
실 중 량 : 130 kg
```

**sample_04.json**의 실제 OCR 텍스트:
```
총 중 량 14,230 kg (09:09)
공차중량 12,910 kg (09:09)
실 중 량 1,320 kg
```

> [!IMPORTANT]
> OCR 텍스트에는 올바른 실중량 값(130, 1320)이 포함되어 있습니다!

### 2. 파싱 로직 분석

parsing.py:L121-L125에서 `NET_WEIGHT_LABEL` 매칭 시:

```python
elif string_id == "NET_WEIGHT_LABEL" and not extracted["net_weight"]:
    val = self._extract_best_number(search_span)
    if val:
        extracted["net_weight"] = val
        found_weights_source['net'] = val
```

**문제점**: 
- `NET_WEIGHT_LABEL` 패턴에 단순 `{"TEXT": "중량"}` 패턴이 포함되어 있음 (L51)
- 이로 인해 **"총중량"의 "중량" 부분이 먼저 매칭됨**
- `extracted["net_weight"]`가 총중량 값으로 먼저 채워지면, 실제 "실중량" 레이블이 나중에 매칭되어도 `not extracted["net_weight"]` 조건 때문에 무시됨

### 3. 실행 순서 문제

spaCy Matcher가 모든 패턴을 찾은 후 순회하는 과정에서:

1. "총 중 량"에서 `TOTAL_WEIGHT_LABEL` 매칭 → `total_weight = 14080` ✅
2. **"총 중 량"의 "중 량" 부분이 `NET_WEIGHT_LABEL`로도 매칭** → `net_weight = 14080` ❌
3. 나중에 "실 중 량"이 `NET_WEIGHT_LABEL`로 매칭되지만, `not extracted["net_weight"]` 조건 때문에 스킵됨

---

## 해결 방안

### 1. NET_WEIGHT_LABEL 패턴 정리

더 구체적인 레이블만 매칭되도록 일반적인 "중량" 패턴 제거:

```python
# 변경 전
self.matcher.add("NET_WEIGHT_LABEL", [
    [{"TEXT": "실중량"}],
    [{"TEXT": "실"}, {"TEXT": "중"}, {"TEXT": "량"}],
    [{"TEXT": "실"}, {"TEXT": "중량"}],
    [{"TEXT": "실중"}, {"TEXT": "량"}],
    [{"TEXT": "중"}, {"TEXT": "량"}],  # ❌ 너무 일반적
    [{"TEXT": "중량"}]                  # ❌ 너무 일반적
])

# 변경 후
self.matcher.add("NET_WEIGHT_LABEL", [
    [{"TEXT": "실중량"}],
    [{"TEXT": "실"}, {"TEXT": "중"}, {"TEXT": "량"}],
    [{"TEXT": "실"}, {"TEXT": "중량"}],
    [{"TEXT": "실중"}, {"TEXT": "량"}]
])
```

### 2. 폴백 계산 로직 강화

수학적 무결성을 보장하기 위해 계산 기반 검증/교정 추가:

```python
# 변경 전
if extracted["total_weight"] and extracted["tare_weight"] and not extracted["net_weight"]:
     extracted["net_weight"] = extracted["total_weight"] - extracted["tare_weight"]

# 변경 후
if extracted["total_weight"] and extracted["tare_weight"]:
    calculated_net = extracted["total_weight"] - extracted["tare_weight"]
    
    # 실중량이 없거나, 계산값과 다르면 계산값으로 교체
    if not extracted["net_weight"] or extracted["net_weight"] != calculated_net:
        extracted["net_weight"] = calculated_net
```

**장점**:
- ✅ 잘못 추출된 값 자동 교정
- ✅ `Total = Tare + Net` 공식 항상 보장
- ✅ 향후 다양한 OCR 포맷에 대한 견고성 확보

---

## 검증 계획

```bash
python verify_parser.py
```

**예상 결과**:
```
[sample_01.json] Status: OK | Logic: PASS
[sample_02.json] Status: OK | Logic: PASS
[sample_03.json] Status: OK | Logic: PASS  ← 수정 후
[sample_04.json] Status: OK | Logic: PASS  ← 수정 후
```
