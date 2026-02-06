"""
Domain constants and validation rules shared across the system.
"""

class DomainRules:
    """도메인 지식 기반 규칙 및 상수"""
    
    # 중량 범위 (kg)
    WEIGHT_TOTAL_MIN = 1000
    WEIGHT_TOTAL_MAX = 100000
    WEIGHT_TARE_MIN = 500
    WEIGHT_TARE_MAX = 50000
    WEIGHT_NET_MIN = 10
    WEIGHT_NET_MAX = 99000
    
    # 허용 오차
    WEIGHT_EQUATION_TOLERANCE = 50  # kg
    
    # 비율 범위
    NET_TOTAL_RATIO_MIN = 0.001
    NET_TOTAL_RATIO_MAX = 0.95
    TARE_TOTAL_RATIO_MIN = 0.05
    TARE_TOTAL_RATIO_MAX = 0.99
    
    # 날짜 범위
    DATE_YEAR_MIN = 2020
    DATE_YEAR_MAX = 2030
    
    # 차량번호 패턴 (Regex)
    VEHICLE_PATTERNS = [
        r'\d{2,3}[가-힣]+\d{4}',  # 표준 형식 (예: 12가3456)
        r'\d{4}',                   # 4자리 숫자 (부분 인식/구형)
    ]

def is_valid_weight_logic(total: int, tare: int, net: int) -> bool:
    """
    도메인 상식 검증 통합 로직
    """
    if total <= 0 or tare < DomainRules.WEIGHT_TARE_MIN or net < DomainRules.WEIGHT_NET_MIN:
        return False
    
    if tare >= total or net >= total:
        return False
    
    ratio = net / total
    if not (DomainRules.NET_TOTAL_RATIO_MIN <= ratio <= DomainRules.NET_TOTAL_RATIO_MAX):
        return False
    
    return True
