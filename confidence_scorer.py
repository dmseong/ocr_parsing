"""
Confidence Scoring & Review System
===================================

추출된 데이터의 신뢰도를 평가하고, 사람이 검수해야 할 건을 분류합니다.

핵심 기능:
1. 필드별 신뢰도 점수 계산
2. 도메인 규칙 기반 검증
3. 자동 보정 로직
4. 검수 필요 플래그 생성
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from extractors.domain import DomainRules


class ReviewPriority(Enum):
    """검수 우선순위"""
    NONE = 0        # 검수 불필요
    LOW = 1         # 낮음 - 자동 보정됨
    MEDIUM = 2      # 중간 - 확인 권장
    HIGH = 3        # 높음 - 반드시 검수
    CRITICAL = 4    # 치명 - 파싱 실패


@dataclass
class FieldConfidence:
    """필드별 신뢰도 정보"""
    field_name: str
    value: Any
    confidence: float
    issues: List[str]
    is_auto_repaired: bool = False
    original_value: Any = None


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool
    confidence: float
    issues: List[str]
    repaired_values: Dict[str, Any]
    review_priority: ReviewPriority


# =============================================================================
# Domain Rules
# =============================================================================




# =============================================================================
# Field Validators
# =============================================================================

class WeightValidator:
    """중량 필드 검증기"""
    
    @staticmethod
    def validate_triplet(total: int, tare: int, net: int) -> Tuple[bool, List[str], Dict]:
        """
        중량 3중 검증
        
        Returns:
            (is_valid, issues, repaired_values)
        """
        issues = []
        repairs = {}
        
        # 1. 범위 검증
        if total and (total < DomainRules.WEIGHT_TOTAL_MIN or total > DomainRules.WEIGHT_TOTAL_MAX):
            issues.append(f"총중량 범위 초과: {total}kg")
        
        if tare and (tare < DomainRules.WEIGHT_TARE_MIN or tare > DomainRules.WEIGHT_TARE_MAX):
            issues.append(f"공차중량 범위 초과: {tare}kg")
        
        if net and (net < DomainRules.WEIGHT_NET_MIN or net > DomainRules.WEIGHT_NET_MAX):
            issues.append(f"실중량 범위 초과: {net}kg")
        
        # 2. 방정식 검증 (Total = Tare + Net)
        if total and tare and net:
            expected_net = total - tare
            error = abs(net - expected_net)
            
            if error > DomainRules.WEIGHT_EQUATION_TOLERANCE:
                issues.append(f"방정식 불만족: {total} ≠ {tare} + {net} (오차: {error}kg)")
                
                # 자동 보정 시도
                repairs['net_weight'] = expected_net
                repairs['_auto_repaired'] = True
        
        # 3. 비율 검증
        if total and net:
            ratio = net / total
            if not (DomainRules.NET_TOTAL_RATIO_MIN <= ratio <= DomainRules.NET_TOTAL_RATIO_MAX):
                issues.append(f"비율 이상: Net/Total = {ratio:.2%}")
        
        # 4. 논리적 관계
        if total and tare and tare >= total:
            issues.append("논리 오류: 공차중량 ≥ 총중량")
        
        if total and net and net >= total:
            issues.append("논리 오류: 실중량 ≥ 총중량")
        
        is_valid = len(issues) == 0
        return is_valid, issues, repairs
    
    @staticmethod
    def validate_single(field_name: str, value: int) -> Tuple[float, List[str]]:
        """
        단일 중량 필드 신뢰도 계산
        
        Returns:
            (confidence, issues)
        """
        confidence = 100.0
        issues = []
        
        if value is None:
            return 0.0, ["값 없음"]
        
        # 범위 검증
        if field_name == "total_weight":
            min_val, max_val = DomainRules.WEIGHT_TOTAL_MIN, DomainRules.WEIGHT_TOTAL_MAX
        elif field_name == "tare_weight":
            min_val, max_val = DomainRules.WEIGHT_TARE_MIN, DomainRules.WEIGHT_TARE_MAX
        else:
            min_val, max_val = DomainRules.WEIGHT_NET_MIN, DomainRules.WEIGHT_NET_MAX
        
        if value < min_val:
            confidence -= 30
            issues.append(f"최소값 미만: {value} < {min_val}")
        elif value > max_val:
            confidence -= 30
            issues.append(f"최대값 초과: {value} > {max_val}")
        
        # 비정상적인 값 패턴
        if value % 1000 == 0:
            # 딱 떨어지는 숫자는 약간 의심
            confidence -= 5
        
        return max(0, confidence), issues


class DateValidator:
    """날짜 필드 검증기"""
    
    @staticmethod
    def validate(date_str: str) -> Tuple[float, List[str]]:
        """
        날짜 검증
        
        Returns:
            (confidence, issues)
        """
        import re
        from datetime import datetime
        
        if not date_str:
            return 0.0, ["날짜 없음"]
        
        confidence = 100.0
        issues = []
        
        # 형식 검증
        match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
        if not match:
            return 50.0, ["비표준 형식"]
        
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            
            # 연도 범위
            if not (DomainRules.DATE_YEAR_MIN <= year <= DomainRules.DATE_YEAR_MAX):
                confidence -= 30
                issues.append(f"연도 범위 초과: {year}")
            
            # 월/일 범위
            if not (1 <= month <= 12):
                confidence -= 40
                issues.append(f"월 범위 오류: {month}")
            
            if not (1 <= day <= 31):
                confidence -= 40
                issues.append(f"일 범위 오류: {day}")
            
            # 실제 날짜 유효성
            try:
                datetime(year, month, day)
            except ValueError:
                confidence -= 30
                issues.append(f"유효하지 않은 날짜: {date_str}")
            
            # 미래 날짜 체크
            if datetime(year, month, day) > datetime.now():
                confidence -= 20
                issues.append("미래 날짜")
                
        except Exception as e:
            return 30.0, [f"파싱 오류: {str(e)}"]
        
        return max(0, confidence), issues


class VehicleValidator:
    """차량번호 검증기"""
    
    @staticmethod
    def validate(vehicle_num: str) -> Tuple[float, List[str]]:
        """
        차량번호 검증
        
        Returns:
            (confidence, issues)
        """
        import re
        
        if not vehicle_num:
            return 0.0, ["차량번호 없음"]
        
        confidence = 100.0
        issues = []
        
        # 표준 형식 체크 (12가3456, 경기12가3456 등)
        standard_pattern = r'^([가-힣]{2})?\d{1,3}[가-힣]\d{4}$'
        if re.match(standard_pattern, vehicle_num):
            # 완벽한 형식
            return 100.0, []
        
        # 4자리 숫자만
        if re.match(r'^\d{4}$', vehicle_num):
            confidence = 80.0
            issues.append("4자리 숫자만 (지역/문자 누락 가능성)")
            
            # 연도 패턴 제외
            if vehicle_num.startswith('202'):
                confidence -= 30
                issues.append("연도로 오인 가능")
        else:
            confidence = 60.0
            issues.append("비표준 형식")
        
        return max(0, confidence), issues


class CompanyValidator:
    """회사명 검증기"""
    
    # 제외할 패턴
    EXCLUDE_PATTERNS = [
        'kg', 'ton', '입고', '출고', '총', '중량', '계량',
    ]
    
    @staticmethod
    def validate(company_name: str) -> Tuple[float, List[str]]:
        """
        회사명 검증
        
        Returns:
            (confidence, issues)
        """
        if not company_name:
            return 0.0, ["회사명 없음"]
        
        confidence = 100.0
        issues = []
        
        # 최소 길이
        if len(company_name) < 2:
            confidence -= 40
            issues.append("너무 짧음")
        
        # 제외 패턴 체크
        for pattern in CompanyValidator.EXCLUDE_PATTERNS:
            if pattern in company_name.lower():
                confidence -= 30
                issues.append(f"잘못된 추출: '{pattern}' 포함")
                break
        
        # 한글 포함 여부
        import re
        if not re.search(r'[가-힣]', company_name):
            confidence -= 20
            issues.append("한글 없음")
        
        # 특수문자만 있는 경우
        if not re.search(r'[가-힣a-zA-Z]', company_name):
            confidence -= 50
            issues.append("문자 없음")
        
        return max(0, confidence), issues


# =============================================================================
# Confidence Scorer
# =============================================================================

class ConfidenceScorer:
    """
    종합 신뢰도 평가기
    
    필드별 신뢰도를 계산하고, 전체 문서의 검수 우선순위를 결정합니다.
    """
    
    # 필드별 가중치
    FIELD_WEIGHTS = {
        'date': 1.0,
        'vehicle_num': 1.0,
        'total_weight': 1.5,
        'tare_weight': 1.0,
        'net_weight': 1.5,
        'company': 0.4,
    }
    
    # 검수 기준
    REVIEW_THRESHOLDS = {
        ReviewPriority.NONE: 90,
        ReviewPriority.LOW: 75,
        ReviewPriority.MEDIUM: 50,
        ReviewPriority.HIGH: 25,
    }
    
    def score(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        전체 결과에 대한 신뢰도 계산
        
        Args:
            result: 파싱 결과 딕셔너리
            
        Returns:
            신뢰도 정보가 추가된 결과
        """
        field_scores = {}
        all_issues = []
        repairs = {}
        
        # 1. 중량 3중 검증
        total = result.get('total_weight')
        tare = result.get('tare_weight')
        net = result.get('net_weight')
        
        if total or tare or net:
            is_valid, weight_issues, weight_repairs = WeightValidator.validate_triplet(
                total, tare, net
            )
            all_issues.extend(weight_issues)
            repairs.update(weight_repairs)
        
        # 2. 개별 필드 검증
        # 날짜
        date_conf, date_issues = DateValidator.validate(result.get('date'))
        field_scores['date'] = date_conf
        all_issues.extend([f"날짜: {i}" for i in date_issues])
        
        # 차량번호
        vehicle_conf, vehicle_issues = VehicleValidator.validate(result.get('vehicle_num'))
        field_scores['vehicle_num'] = vehicle_conf
        all_issues.extend([f"차량번호: {i}" for i in vehicle_issues])
        
        # 중량
        if total:
            total_conf, total_issues = WeightValidator.validate_single('total_weight', total)
            field_scores['total_weight'] = total_conf
        
        if tare:
            tare_conf, tare_issues = WeightValidator.validate_single('tare_weight', tare)
            field_scores['tare_weight'] = tare_conf
        
        if net:
            net_conf, net_issues = WeightValidator.validate_single('net_weight', net)
            field_scores['net_weight'] = net_conf
        
        # 회사명
        company_conf, company_issues = CompanyValidator.validate(result.get('company'))
        field_scores['company'] = company_conf
        all_issues.extend([f"회사명: {i}" for i in company_issues])
        
        # 3. 가중 평균 계산
        weighted_sum = 0
        weight_total = 0
        
        for field, score in field_scores.items():
            weight = self.FIELD_WEIGHTS.get(field, 1.0)
            weighted_sum += score * weight
            weight_total += weight
        
        overall_confidence = weighted_sum / weight_total if weight_total > 0 else 0
        
        # 4. 검수 우선순위 결정
        review_priority = self._determine_priority(overall_confidence, all_issues)
        
        # 5. 결과 반환
        scored_result = result.copy()
        scored_result['_field_confidences'] = field_scores
        scored_result['_overall_confidence'] = round(overall_confidence, 2)
        scored_result['_issues'] = all_issues
        scored_result['_review_priority'] = review_priority.name
        scored_result['_needs_review'] = review_priority.value >= ReviewPriority.MEDIUM.value
        
        # 자동 보정 적용
        if repairs:
            for key, value in repairs.items():
                if key != '_auto_repaired':
                    scored_result[key] = value
                    scored_result['_repaired'] = True
        
        return scored_result
    
    def _determine_priority(self, confidence: float, issues: List[str]) -> ReviewPriority:
        """검수 우선순위 결정"""
        # 치명적 문제
        critical_keywords = ['논리 오류', '파싱 오류', '범위 초과']
        if any(any(kw in issue for kw in critical_keywords) for issue in issues):
            return ReviewPriority.HIGH
        
        # 신뢰도 기반
        for priority, threshold in sorted(self.REVIEW_THRESHOLDS.items(), 
                                          key=lambda x: x[1], reverse=True):
            if confidence >= threshold:
                return priority
        
        return ReviewPriority.CRITICAL
    
    def get_review_summary(self, results: List[Dict]) -> Dict:
        """
        다중 결과에 대한 검수 요약
        
        Args:
            results: 파싱 결과 리스트
            
        Returns:
            검수 요약 정보
        """
        summary = {
            'total': len(results),
            'by_priority': {p.name: 0 for p in ReviewPriority},
            'needs_review_count': 0,
            'auto_repaired_count': 0,
            'average_confidence': 0,
        }
        
        total_conf = 0
        
        for result in results:
            priority_name = result.get('_review_priority', 'CRITICAL')
            summary['by_priority'][priority_name] += 1
            
            if result.get('_needs_review'):
                summary['needs_review_count'] += 1
            
            if result.get('_repaired'):
                summary['auto_repaired_count'] += 1
            
            total_conf += result.get('_overall_confidence', 0)
        
        summary['average_confidence'] = round(total_conf / len(results), 2) if results else 0
        
        return summary


# =============================================================================
# Batch Processor
# =============================================================================

class ReviewBatchProcessor:
    """검수 대상 배치 처리기"""
    
    def __init__(self, scorer: ConfidenceScorer = None):
        self.scorer = scorer or ConfidenceScorer()
    
    def process_batch(self, results: List[Dict]) -> Dict:
        """
        배치 처리 및 분류
        
        Returns:
            {
                'passed': List[Dict],      # 검수 불필요
                'auto_fixed': List[Dict],  # 자동 보정됨
                'needs_review': List[Dict], # 검수 필요
                'failed': List[Dict],      # 파싱 실패
                'summary': Dict
            }
        """
        passed = []
        auto_fixed = []
        needs_review = []
        failed = []
        
        for result in results:
            scored = self.scorer.score(result)
            priority = ReviewPriority[scored.get('_review_priority', 'CRITICAL')]
            
            if priority == ReviewPriority.NONE:
                passed.append(scored)
            elif priority == ReviewPriority.LOW and scored.get('_repaired'):
                auto_fixed.append(scored)
            elif priority in [ReviewPriority.MEDIUM, ReviewPriority.HIGH]:
                needs_review.append(scored)
            else:
                failed.append(scored)
        
        return {
            'passed': passed,
            'auto_fixed': auto_fixed,
            'needs_review': needs_review,
            'failed': failed,
            'summary': self.scorer.get_review_summary(results)
        }


# =============================================================================
# CLI Test
# =============================================================================

if __name__ == "__main__":
    # 테스트
    scorer = ConfidenceScorer()
    
    test_result = {
        'date': '2026-02-02',
        'vehicle_num': '8713',
        'total_weight': 12480,
        'tare_weight': 7470,
        'net_weight': 5010,
        'company': '곰욕환경폐기물',
    }
    
    scored = scorer.score(test_result)
    
    import json
    print("=== Confidence Scoring Test ===")
    print(json.dumps(scored, ensure_ascii=False, indent=2, default=str))
