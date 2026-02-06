"""
OCR 파서 테스트 및 비교 스크립트
- 기존 파서 vs 개선된 파서 성능 비교
- 샘플 데이터에 대한 정확도 측정
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum

# 파서 임포트
try:
    from universal_ocr_parser_v3 import UniversalOCRParser as ParserV3
    HAS_V3 = True
except Exception as e:
    print(f"Warning: Could not import v3 parser: {e}")
    HAS_V3 = False

try:
    from universal_ocr_parser_v2 import UniversalOCRParser as ParserV2
    HAS_V2 = True
except Exception as e:
    print(f"Warning: Could not import v2 parser: {e}")
    HAS_V2 = False


@dataclass
class TestCase:
    """테스트 케이스"""
    file_path: str
    expected: Dict[str, Any]
    description: str = ""


class FieldStatus(Enum):
    """필드 추출 상태"""
    CORRECT = "✓ 정확"
    INCORRECT = "✗ 오류"
    MISSING = "- 누락"
    EXTRA = "+ 추가"


@dataclass
class FieldResult:
    """필드별 결과"""
    field_name: str
    expected: Any
    actual: Any
    status: FieldStatus
    
    def __str__(self):
        if self.status == FieldStatus.CORRECT:
            return f"{self.status.value}: {self.field_name} = {self.actual}"
        elif self.status == FieldStatus.INCORRECT:
            return f"{self.status.value}: {self.field_name} (기대: {self.expected}, 실제: {self.actual})"
        elif self.status == FieldStatus.MISSING:
            return f"{self.status.value}: {self.field_name} (기대: {self.expected})"
        else:
            return f"{self.status.value}: {self.field_name} = {self.actual}"


@dataclass
class TestResult:
    """테스트 결과"""
    test_case: TestCase
    field_results: List[FieldResult]
    accuracy: float
    
    @property
    def passed(self) -> bool:
        return self.accuracy >= 0.8  # 80% 이상 정확도
    
    def summary(self) -> str:
        correct = sum(1 for r in self.field_results if r.status == FieldStatus.CORRECT)
        total = len([r for r in self.field_results if r.status != FieldStatus.EXTRA])
        
        return f"정확도: {self.accuracy*100:.1f}% ({correct}/{total})"


class ParserTester:
    """파서 테스트 도구"""
    
    def __init__(self):
        self.test_cases = self._define_test_cases()
    
    def _define_test_cases(self) -> List[TestCase]:
        """테스트 케이스 정의 - 실제 샘플 데이터 기준"""
        return [
            TestCase(
                file_path="/mnt/user-data/uploads/sample_01.json",
                expected={
                    "date": "2026-02-02",
                    "vehicle_num": "8713",  # 차량번호는 단순 숫자
                    "total_weight": 12480,  # 05:26:18 12,480 kg
                    "tare_weight": 7470,    # 05:36:01 7,470 kg
                    "net_weight": 5010,     # 5,010 kg
                    "company": "곰욕환경폐기물",  # 거래처
                    "product": None,
                    "type": None,  # 입고/출고 없음
                    "ticket_id": "0016",
                },
                description="Sample 01 - 동우바이오 양식"
            ),
            TestCase(
                file_path="/mnt/user-data/uploads/sample_02.json",
                expected={
                    "date": "2026-02-02",
                    "vehicle_num": "80구8713",  # 한글 포함
                    "total_weight": 13460,   # 02:07 13 460 kg (공백 분리)
                    "tare_weight": 7560,     # 차중량: 02 : 13 7 560 kg
                    "net_weight": 5900,      # 5 900 kg
                    "company": "고요환경",
                    "product": "식물",
                    "type": "입고",
                    "ticket_id": "010889",
                },
                description="Sample 02 - 장원C&S 양식"
            ),
            TestCase(
                file_path="/mnt/user-data/uploads/sample_03.json",
                expected={
                    "date": "2026-02-01",
                    "vehicle_num": "5405",
                    "total_weight": 14080,   # 11시 33분 14,080 kg
                    "tare_weight": 13950,    # 공차중량 : 11시 39분 13,950 kg
                    "net_weight": 130,       # 130 kg
                    "company": None,  # 회사명이 명확하지 않음
                    "product": None,
                    "type": "입고",
                    "ticket_id": None,
                },
                description="Sample 03 - 정우리사이클링 양식"
            ),
            TestCase(
                file_path="/mnt/user-data/uploads/sample_04.json",
                expected={
                    "date": "2025-12-01",
                    "vehicle_num": "0580",
                    "total_weight": 14230,   # 14,230 kg (09:09)
                    "tare_weight": 12910,    # 공차중량 12,910 kg (09:0...)
                    "net_weight": 1320,      # 계산값 (14230 - 12910)
                    "company": "신성",  # 귀하 앞의 회사명
                    "product": "국판",
                    "type": "입고",  # 출 자체가 아니라 입고로 보임
                    "ticket_id": "0022",
                },
                description="Sample 04 - 하은펄프 양식"
            ),
        ]
    
    def run_test(self, parser, test_case: TestCase) -> TestResult:
        """단일 테스트 실행"""
        # JSON 로드
        with open(test_case.file_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        # 파싱
        result = parser.parse(ocr_data)
        
        # 결과 비교
        field_results = []
        
        for field_name, expected_value in test_case.expected.items():
            actual_value = result.get(field_name)
            
            # 상태 판단
            if expected_value is None and actual_value is None:
                status = FieldStatus.CORRECT
            elif expected_value is None and actual_value is not None:
                status = FieldStatus.EXTRA
            elif expected_value is not None and actual_value is None:
                status = FieldStatus.MISSING
            elif self._values_match(expected_value, actual_value):
                status = FieldStatus.CORRECT
            else:
                status = FieldStatus.INCORRECT
            
            field_results.append(FieldResult(
                field_name=field_name,
                expected=expected_value,
                actual=actual_value,
                status=status
            ))
        
        # 정확도 계산
        correct = sum(1 for r in field_results if r.status == FieldStatus.CORRECT)
        total = len([r for r in field_results if r.expected is not None])
        accuracy = correct / total if total > 0 else 0.0
        
        return TestResult(
            test_case=test_case,
            field_results=field_results,
            accuracy=accuracy
        )
    
    def _values_match(self, expected: Any, actual: Any) -> bool:
        """값 비교 (타입 변환 고려)"""
        if expected == actual:
            return True
        
        # 문자열 비교 (공백 무시)
        if isinstance(expected, str) and isinstance(actual, str):
            return expected.strip() == actual.strip()
        
        # 숫자 비교
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return abs(expected - actual) <= 5  # 5 이내 허용
        
        return False
    
    def run_all_tests(self, parser) -> List[TestResult]:
        """모든 테스트 실행"""
        results = []
        
        for test_case in self.test_cases:
            if not os.path.exists(test_case.file_path):
                print(f"Warning: File not found: {test_case.file_path}")
                continue
            
            try:
                result = self.run_test(parser, test_case)
                results.append(result)
            except Exception as e:
                print(f"Error testing {test_case.file_path}: {e}")
                import traceback
                traceback.print_exc()
        
        return results
    
    def print_report(self, results: List[TestResult], title: str = "테스트 결과"):
        """결과 리포트 출력"""
        print("\n" + "="*80)
        print(f" {title}")
        print("="*80)
        
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] {result.test_case.description}")
            print(f"    파일: {os.path.basename(result.test_case.file_path)}")
            print(f"    {result.summary()}")
            print(f"    {'PASS ✓' if result.passed else 'FAIL ✗'}")
            
            # 필드별 상세
            for field_result in result.field_results:
                if field_result.status != FieldStatus.CORRECT:
                    print(f"      {field_result}")
        
        # 전체 통계
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        avg_accuracy = sum(r.accuracy for r in results) / total_tests if total_tests > 0 else 0
        
        print("\n" + "-"*80)
        print(f"전체 통과율: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)" if total_tests > 0 else "")
        print(f"평균 정확도: {avg_accuracy*100:.1f}%")
        print("="*80 + "\n")


def inspect_sample_files():
    """샘플 파일 내용 간단 출력 (테스트 케이스 작성용)"""
    print("\n" + "="*80)
    print(" 샘플 파일 내용 미리보기")
    print("="*80)
    
    sample_dir = Path("/mnt/user-data/uploads")
    
    for i in range(1, 5):
        file_path = sample_dir / f"sample_0{i}.json"
        
        if not file_path.exists():
            continue
        
        print(f"\n[sample_0{i}.json]")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 전체 텍스트 추출
            if 'pages' in data and data['pages']:
                page = data['pages'][0]
                if 'words' in page:
                    all_text = " ".join(w.get('text', '') for w in page['words'])
                    print(f"전체 텍스트: {all_text[:200]}...")
                    
                    # 주요 키워드 검색
                    keywords = ['총중량', '공차', '실중량', '입고', '출고', 'kg', '차량']
                    found = [kw for kw in keywords if kw in all_text]
                    print(f"발견된 키워드: {', '.join(found)}")
        
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n" + "="*80 + "\n")


def main():
    """메인 실행"""
    print("OCR 파서 테스트 시작\n")
    
    # 1. 샘플 파일 미리보기
    inspect_sample_files()
    
    # 2. 파서 v3 테스트 (최신 버전)
    if HAS_V3:
        print("\n개선된 파서 (v3) 테스트 중...")
        parser_v3 = ParserV3()
        tester = ParserTester()
        
        results_v3 = tester.run_all_tests(parser_v3)
        tester.print_report(results_v3, "개선된 파서 (v3) 테스트 결과")
    else:
        print("v3 파서를 임포트할 수 없습니다.")
    
    # 3. 파서 v2 테스트 (비교용)
    if HAS_V2:
        print("\n개선된 파서 (v2) 테스트 중...")
        parser_v2 = ParserV2()
        tester = ParserTester()
        
        results_v2 = tester.run_all_tests(parser_v2)
        tester.print_report(results_v2, "개선된 파서 (v2) 테스트 결과")
    
    print("\n테스트 완료!\n")


if __name__ == "__main__":
    main()
