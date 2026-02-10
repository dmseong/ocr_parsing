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
    'ISSUER_TYPE': ["리사이클", "환경", "자원", "산업", "개발", "펄프", "제지", "장원"],
    'ISSUER_HEADER_SKIP': ["계량", "증명", "확인서", "전표", "발행"],
    'GLOBAL_NOISE': ["공육을", "unle"],
    'PHONE_LABELS': ["TEL", "Tel", "전화", "연락처", "H.P", "HP", "Fax", "FAX"],
}

NOISE_KEYWORDS = {
    # CompanyExtractor에서 식별되면 무시하거나 Truncate할 키워드
    'COMPANY_TRAILING': ["품명", "제품", "구분", "날짜", "시간", "중량", "차량", "전표", "계량", "발행", "품종", "명랑"],
    
    # ProductExtractor에서 식별되면 Truncate할 다음 필드 라벨
    'PRODUCT_NEXT_LABELS': ["구분", "입고", "출고", "수량", "중량", "비고", "차량", "전표", "단가", "금액", "확인"],
}

PATTERNS = {
    'DATE': [
        r'(\d{4})[-/\.\s]+([A-Za-z]{3})[-/\.\s]+(\d{1,2})',  # 2026-Feb-02
        r'(\d{2,4})[\.\-/]\s*(\d{1,2})[\.\-/]\s*(\d{1,2})',   # 2026-02-02, 26.02.02
        r'(\d{4})\s*[,.\-/]\s*(\d{1,2})\s*[,.\-/]\s*(\d{1,2})' # Noisy: 2026, 02. 01
    ],
    'VEHICLE': {
        'STANDARD': [
            r'[가-힣]{2}\s*\d{2}\s*[가-힣]\s*\d{4}',    # 경기12가3456
            r'[가-힣]{2}\s*\d{1,2}\s*[가-힣]\s*\d{4}',  # 서울1가1234
            r'\d{2,3}\s*[가-힣]\s*\d{4}',              # 12가3456
            r'0\d[-\s]*\d{4}',                         # 건설기계
            r'[가-힣]{2}\s*\d{3}-\d{3}',               # 외교
            r'임\s*시\s*\d{4,6}'                       # 임시
        ],
        'NOISE_REC': r'(\d{2,3})([가-힣ㄱ-ㅎㅏ-ㅣ])([A-Z0-9]{4})', # 56바7B9O -> 56바7890
        'PARSER_REGEX': r'([가-힣]{0,2})\d{2,3}[가-힣]\d{4}|[A-Z]{1,3}[-\s]?\d{3,4}|(?<!\d)\d{4}(?!\d)' # Spatial Extractor용
    },
    'TICKET_ID': {
        'LABEL': r'(N[O0]\.?|전\s*표(?:번\s*호)?|티\s*켓|계\s*량\s*(?:번\s*호|횟\s*수|회\s*수)|ID[-\s]*N[O0]|번\s*호:?|일\s*련\s*번\s*호)\s*[:：\.;,]?\s*([A-Z0-9-]{1,18})',
        'VALUE_NEXT_LINE': r'^[^\w]*([A-Z0-9-]{2,12})',
        'DATE_SUFFIX': r'20\d{2}[-.\s/]*\d{1,2}[-.\s/]*\d{1,2}(?:\s+\d{2}:\d{2}(?::\d{2})?)? +([A-Z0-9]{1,8})(?![\d:])'
    },
    'GPS': {
        'STANDARD': r'(\d{2}\.\d{4,})[^\d]{1,30}(\d{2,3}\.\d{4,})',
        'RELAXED': r'(3\d[\.,]\d{4,})[^\d]{1,50}(1[23]\d[\.,]\d{4,})',
        'CANDIDATE': r'(\d{2,3}\.\d{4,})'
    },
    'PHONE': r'(0\d{1,2})\s*[-.)]\s*(\d{3,4})\s*[-.]\s*(\d{4})',
    'COMPANY': {
        'LABEL': r'(상\s*호|샹\s*호|성\s*명|거\s*래\s*처|공\s*급\s*자|공\s*급\s*받\s*는\s*자|업\s*체\s*명)\s*[:;：]?\s*([가-힣\(\)A-Z0-9 ]+)',
        'HONORIFIC': r'([가-힣\(\)A-Z0-9 ]+)\s*귀하',
        'CORP_SUFFIX': r'([가-힣A-Za-z0-9 ]+)\s*\(주\)',
        'CORP_PREFIX': r'\(주\)\s*([가-힣A-Za-z0-9 ]+)',
        'ONLY_DIGIT_DASH': r'^[\d\s-]+$'
    },
    'ISSUER': {
        'CORP_ANY': r'(\(주\)\s*[가-힣A-Za-z0-9 ]+)|([가-힣A-Za-z0-9 ]+\s*\(주\))'
    },
    'ADDRESS': {
        'REGION_PREFIX': r'({region}\s*[가-힣]+(?:시|군|구).*?)(?=\s*(?:Tel|Tel\)|FAX|Fax|\*|20\d{{2}}[-.]|$))'
    },
    'PRODUCT': r'(품\s*명|품\s*면|제\s*품\s*명|제\s*품|품\s*목|품\s*\.+\s*목)\s*[:;：]?\s*([가-힣A-Za-z0-9 ]+?)(?=\s*(?:\(|구분|입고|출고|날짜|차량|발행|총중량|실중량|공차중량|ID-NO)|[:：\n]|$)',
    'TYPE': {
        'LABEL': r'(구\s*분|구\s*문)\s*[:;：]?\s*([가-힣 ]+)',
        'IN': r'입\s*고',
        'OUT': r'출\s*고'
    },
    'ENTITY': {
        'ORGANIZATION': ['ORG', 'OG', 'PS'],  # 조직, 기관, 인물(개인사업자)
        'LOCATION': ['GPE', 'LOC', 'LC'],     # 지명, 장소
        'DATE': ['DATE', 'DT', 'TI']           # 날짜, 시간
    }
}

THRESHOLDS = {
    'WEIGHT': {
        'EQUATION_TOLERANCE': 50,
        'MIN': 100,
        'MAX': 100000,
        'RATIO_MIN': 0.01,
        'RATIO_MAX': 0.9,
        'SPATIAL_MAX_DIST': 600,
        'SPATIAL_NEAR_DIST': 300,
        'SPATIAL_ALIGN_X': 100,
        'SPATIAL_ALIGN_Y': 50
    },
    'GPS': {
        'LAT_MIN': 33, 'LAT_MAX': 43,
        'LON_MIN': 124, 'LON_MAX': 132
    },
    'SPATIAL': {
        'MARGIN_RIGHT': 20,
        'MARGIN_NEXT_LINE_START': 50,
        'SAME_LINE_Y_DIFF': 15,
        'SAME_LINE_MAX_Y_DIFF': 30, # Text Candidate
        'NEXT_LINE_Y_MIN': 15,
        'WEIGHT_SAME_LINE': 0.5,
        'WEIGHT_VERTICAL_PENALTY_MULTIPLIER': 3
    }
}

# Expand KEYWORDS
KEYWORDS.update({
    'REGIONS': ['경기도', '강원도', '충청북도', '충청남도', '전라북도', '전라남도',
                '경상북도', '경상남도', '제주도', '서울', '부산', '대구', '인천',
                '광주', '대전', '울산', '세종'],
    'MONTH_MAP': {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                  'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'},
    'TICKET_LABELS': ['ID-NO', '계량번', '계량횟', '계량회', '전표', 'TICKET', 'SLIP', 'ID', '번호', '일련번호'],
    'COMPANY_STOPPERS': ['품면', '품명', '품 명', '구분', '입고', '출고', '총중량', '실중량', '공차', '차량', '날짜', '보관용', '전화', 'TEL', 'FAX'],
    'COMPANY_BLACKLIST': ['경기도', '서울', 'Tel', 'TEL', '보관용', '차량', '계량', '전화', 'FAX'],
    'UNIT_NOISE': ['k9', 'kg', 'ton', 'pe', 'm3'],
    'ISSUER_STOPPERS': ['경기도', '서울', '인천', '충남', '충북', '전남', '전북', '경남', '경북', '강원', 
                        '제주', '세종', '광주', '대전', '대구', '부산', '울산',
                        'TEL', 'FAX', 'HP', '전화', '주소', '포승', '팔탄', '품목', '품명'],
    'VEHICLE_CONTEXT': ['차량', '차', '차번', 'VEHICLE', 'TRUCK', 'CAR'],
    'LABEL_NOISE': ['NO', 'ID', 'TEL', 'FAX', 'DATE', 'N0'],
})
