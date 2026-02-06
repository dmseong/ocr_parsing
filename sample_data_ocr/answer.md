# OCR 샘플 데이터 정답지

이 문서는 각 샘플 OCR JSON 파일의 **정답 파싱 결과**를 정리합니다.

---

## sample_01.json

| 필드 | 정답값 |
|------|--------|
| date | 2026-02-02 |
| vehicle_num | 8713 |
| total_weight | 12480 |
| tare_weight | 7470 |
| net_weight | 5010 |
| company | 곰욕환경폐기물 |
| product | - |
| type | - |
| ticket_id | 0016 |
| issuer | 동우바이오(주) |
| gps | 37.105317, 127.375673 |

---

## sample_02.json

| 필드 | 정답값 |
|------|--------|
| date | 2026-02-02 |
| vehicle_num | 80구8713 |
| total_weight | 13460 |
| tare_weight | 7560 |
| net_weight | 5900 |
| company | 고요환경 |
| product | 식물 |
| type | 입고 |
| ticket_id | 010889 |
| issuer | 장원C&S |
| gps | 37.718114, 126.844940 |

---

## sample_03.json

| 필드 | 정답값 |
|------|--------|
| date | 2026-02-01 |
| vehicle_num | 5405 |
| total_weight | 14080 |
| tare_weight | 13950 |
| net_weight | 130 |
| company | - |
| product | - |
| type | 입고 |
| ticket_id | 5 |
| issuer | 정우리사이클링(주) |
| gps | - |

---

## sample_04.json

| 필드 | 정답값 |
|------|--------|
| date | 2025-12-01 |
| vehicle_num | 0580 |
| total_weight | 14230 |
| tare_weight | 12910 |
| net_weight | 1320 |
| company | 신성(푸디스트) |
| product | 국판 |
| type | 입고 |
| ticket_id | 0022 |
| issuer | (주)하은펄프 |
| gps | - |

---

## sample_05_noisy.json (노이즈 심함)

**OCR 노이즈**: O↔0, B↔8, k9→kg

| 필드 | OCR 원본 | 정답값 |
|------|----------|--------|
| date | 2O26-O2-O3 | 2026-02-03 |
| vehicle_num | 12가345B | 12가3458 |
| total_weight | 23,4BO | 23480 |
| tare_weight | 1B,25O | 18250 |
| net_weight | 5,23O | 5230 |
| company | 대한리싸이클 | 대한리싸이클 |
| product | 고 철 | 고철 |
| type | 출 고 | 출고 |
| ticket_id | - | - |
| issuer | (주)한국자원 | (주)한국자원 |
| gps | 37.2345B7, 127.1234B7 | 37.234587, 127.123487 |

---

## sample_06_noisy.json (노이즈 매우 심함)

**OCR 노이즈**: l↔1, 한글 심하게 오인식 (게→계, 충→총, 샹→상)

| 필드 | OCR 원본 | 정답값 |
|------|----------|--------|
| date | 2O26-O1-15-OOO32 | 2026-01-15 |
| vehicle_num | 9l구1234 | 91구1234 |
| total_weight | 31,BBO | 31880 |
| tare_weight | 22,44O | 22440 |
| net_weight | 9,44O | 9440 |
| company | 청정그린 | 청정그린 |
| product | 폐 지 | 폐지 |
| type | 입 고 | 입고 |
| ticket_id | O234B7 | 023487 |
| issuer | 그린환경(주) | 그린환경(주) |
| gps | 36.B7654, l26.54321O | 36.87654, 126.543210 |

---

## sample_07_noisy.json (다양한 노이즈)

**OCR 노이즈**: 공차→공동 오인식, l↔1, k9→kg

| 필드 | OCR 원본 | 정답값 |
|------|----------|--------|
| date | 2O26-O2-O5 | 2026-02-05 |
| vehicle_num | 56바7B9O | 56바7890 |
| total_weight | 45,67O | 45670 |
| tare_weight | 32,lBO | 32180 |
| net_weight | l3,49O | 13490 |
| company | (주)에코월드 | (주)에코월드 |
| product | 플라스틱 PE | 플라스틱 PE |
| type | - | - |
| ticket_id | - | - |
| issuer | (주)클린테크 | (주)클린테크 |
| gps | 35.54B2l3, l29.3l4567 | 35.548213, 129.314567 |

---

## sample_08_english.json (영문 라벨)

| 필드 | 정답값 |
|------|--------|
| date | 2025-10-20 |
| vehicle_num | AB-1234 |
| total_weight | 25400 |
| tare_weight | 12200 |
| net_weight | 13200 |
| company | - |
| product | - |
| type | - |
| ticket_id | - |
| issuer | Global Resources Inc. |
| phone | - |

---

## sample_09_unit_confusion.json (단위 혼동 & 소수점)

**이슈**: 단위가 `ton`/`t`으로 표기됨 (x1000 필요), 값이 소수점(`24.50`).

| 필드 | 정답값 |
|------|--------|
| date | 2025-12-25 |
| vehicle_num | 경기99바1234 |
| total_weight | 24500 |
| tare_weight | 10200 |
| net_weight | 14300 |
| company | - |
| product | - |
| type | - |
| ticket_id | - |
| issuer | - |
| phone | - |

---

## sample_10_extreme_noise.json (극한 노이즈 & 필드 혼동)

**이슈**: 라벨과 값의 Y축 정렬 불일치, Ticket ID와 차량번호가 동일(8713), 날짜 없음.

| 필드 | 정답값 |
|------|--------|
| date | - |
| vehicle_num | 8713 |
| total_weight | 12480 |
| tare_weight | 7470 |
| net_weight | 5010 |
| company | (주)태양자원 |
| product | - |
| type | - |
| ticket_id | 8713 |
| issuer | - |
| phone | 031-1234-5678 |

---

## 노이즈 패턴 정리

| 패턴 | 설명 | 예시 |
|------|------|------|
| O → 0 | 대문자 O가 숫자 0으로 오인식 | 2O26 → 2026 |
| l → 1 | 소문자 l이 숫자 1로 오인식 | l3,490 → 13,490 |
| B → 8 | 대문자 B가 숫자 8로 오인식 | 1B,250 → 18,250 |
| k9 → kg | 숫자 9가 g로 오인식 | k9 → kg |
| 한글 오인식 | 비슷한 한글로 오인식 | 계→게, 총→충, 상→샹 |