"""
설정 파일: 라벨 패턴, 상수, 키워드 관리
"""

LABEL_CONFIG = {
    "total_weight": {
        "canonical": ["총중량", "총 중량", "Gross Weight"],
        "variants": ["총량", "합계중량", "합계 중량", "전체중량", "전체 중량", "Gross"],
        "keywords": ["총", "합계", "전체", "계", "Gross"],
        "suffix_keywords": ["중량", "무게", "Weight"],
        "min_value": 1000,
        "max_value": 100000,
    },
    "tare_weight": {
        "canonical": ["공차중량", "공차 중량", "차중량", "차 중량", "Tare Weight"],
        "variants": ["빈차중량", "빈 차 중량", "공 차 중 량", "Tare"],
        "keywords": ["공", "차", "빈", "공차", "Tare"],
        "suffix_keywords": ["중량", "무게", "Weight"],
        "min_value": 500,
        "max_value": 50000,
    },
    "net_weight": {
        "canonical": ["실중량", "실 중량", "Net Weight"],
        "variants": ["순중량", "순 중량", "정미중량", "적재중량", "실 중 량", "Net"],
        "keywords": ["실", "순", "정미", "적재", "적", "Net"],
        "suffix_keywords": ["중량", "무게", "Weight"],
        "min_value": 10,
        "max_value": 99000,
    },
    "date": {
        "canonical": ["계량일자", "측정일자", "날짜", "Date"],
        "variants": ["계량 일자", "측정 일자", "일자", "일시", "일 시", "계량일"],
        "keywords": ["계량", "측정", "날짜", "일자", "일시", "Date"],
        "suffix_keywords": ["일자", "날짜", "일시", "Date"],
    },
    "vehicle": {
        "canonical": ["차량번호", "차량 번호", "Truck No", "Lorry No"],
        "variants": ["차번호", "차 번호", "차량No", "차량 No", "차 량 번 호", "번호", "Truck", "Vehicle"],
        "keywords": ["차량", "차", "번호", "Truck", "No"],
        "suffix_keywords": ["번호", "No", "NO"],
    },
    "company": {
        "canonical": ["거래처", "Customer"],
        "variants": ["거 래 처", "상호", "상 호", "회사명", "고객명", "업체명", "거ㄹh처"],
        "keywords": ["거래", "상호", "회사", "업체", "고객"],
        "suffix_keywords": ["처", "명"],
    },
    "product": {
        "canonical": ["품명", "Product", "Item"],
        "variants": ["품 명", "품목", "품종", "품종명", "제품명", "제품"],
        "keywords": ["품명", "품목", "품종", "제품", "Product"],
        "suffix_keywords": ["명"],
    },
    "ticket_id": {
        "canonical": ["ID-NO", "계량번호", "Ticket No", "Slip No"],
        "variants": ["ID - NO", "IDNO", "계량 번호", "계량횟수", "순번", "No.", "Ticket"],
        "keywords": ["ID", "계량", "번호", "순번", "Ticket", "No"],
        "suffix_keywords": ["NO", "번호", "No"],
    },
}

CONSTANTS = {
    # Label Detector
    'LABEL_MATCH_THRESHOLD': 70,
    'LABEL_MERGE_DIST_X': 200,
    'LABEL_MERGE_DIST_Y': 20,
    'MERGE_SCORE_THRESHOLD': 90,

    # Spatial Extractor
    'SPATIAL_DEFAULT_LAYOUT': 150,
    'SPATIAL_EXTENDED_LAYOUT': 300,
    'SPATIAL_Y_MIN': -30,
    'SPATIAL_Y_MAX': 150,
    'OVERLAP_RATIO': 0.5,

    # Issuer
    'ISSUER_BOTTOM_RATIO': 0.6,
    'ISSUER_TOP_RATIO': 0.4,
    'ISSUER_MERGE_DIST': 100,
}

KEYWORDS = {
    'ISSUER_CORP': ["(주)", "주식회사", "Co.", "Inc.", "Corp.", "ENG"],
    'ISSUER_TYPE': ["리사이클", "환경", "자원", "산업", "개발", "펄프", "제지"],
    'ISSUER_HEADER_SKIP': ["계량", "증명", "확인서", "전표", "발행"],
    'PHONE_LABELS': ["TEL", "Tel", "전화", "연락처", "H.P", "HP", "Fax", "FAX"],
}
