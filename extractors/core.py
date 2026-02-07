import re
from typing import List, Dict, Any
from .common import WordBox
from .weight_engine import UnifiedWeightEngine
from .label_detector import SmartLabelDetector
from .spatial_extractor import SpatialValueExtractor
from .heuristic_finder import HeuristicValueFinder
from .field_extractors import (
    WeightExtractor, DateExtractor, VehicleExtractor,
    CompanyExtractor, IssuerExtractor, PhoneExtractor, ProductExtractor,
    TicketIdExtractor, TypeExtractor, GpsExtractor, AddressExtractor
)

class SmartFieldExtractor:
    """
    spaCy 기반 통합 필드 추출기
    기존 Regex 기반 추출과 호환되는 인터페이스 제공
    """
    
    def __init__(self, normalizer=None):
        from .normalizer import AdvancedNoiseNormalizer
        self.normalizer = normalizer or AdvancedNoiseNormalizer()
        
        # 공통 모듈 초기화
        self.label_detector = SmartLabelDetector()
        self.spatial_extractor = SpatialValueExtractor(self.normalizer)
        self.heuristic_finder = HeuristicValueFinder(self.normalizer)
        
        # 추출기 공통 인자
        common_args = {
            'label_detector': self.label_detector,
            'spatial_extractor': self.spatial_extractor,
            'heuristic_finder': self.heuristic_finder,
            'normalizer': self.normalizer
        }
        
        # 전문 추출기 초기화
        self.unified_weight_engine = UnifiedWeightEngine(self.normalizer)
        self.weight_extractor = WeightExtractor(self.unified_weight_engine, **common_args)
        self.date_extractor = DateExtractor(**common_args)
        self.vehicle_extractor = VehicleExtractor(**common_args)
        self.company_extractor = CompanyExtractor(**common_args)
        self.issuer_extractor = IssuerExtractor(**common_args)
        self.phone_extractor = PhoneExtractor(**common_args)
        self.product_extractor = ProductExtractor(**common_args)
        
        # 신규 보조 추출기들
        self.ticket_id_extractor = TicketIdExtractor(**common_args)
        self.type_extractor = TypeExtractor(**common_args)
        self.gps_extractor = GpsExtractor(**common_args)
        self.address_extractor = AddressExtractor(**common_args)
    
    def extract_all(self, word_boxes: List[WordBox], layout: Any = None) -> Dict[str, Any]:
        """모든 필드 추출"""
        result = {}
        methods = {}
        
        # 1. 중량
        weights = self.weight_extractor.extract(word_boxes)
        if weights:
            result['total_weight'] = weights.get('total_weight')
            result['tare_weight'] = weights.get('tare_weight')
            result['net_weight'] = weights.get('net_weight')
        
        # 2. 고정 필드 및 비즈니스 엔티티
        result['date'] = self.date_extractor.extract(word_boxes)
        result['vehicle_num'] = self.vehicle_extractor.extract(word_boxes)
        result['company'] = self.company_extractor.extract(word_boxes)
        
        # 발행처 (Issuer) - 상호와 중복 체크 포함
        self.issuer_extractor.set_company_for_validation(result['company'])
        result['issuer'] = self.issuer_extractor.extract(word_boxes)
        
        # [Fix] Supplier가 Company에 잡힌 경우 Issuer로 이동 (Sample 08 대응)
        if result['company'] and 'Supplier' in result['company']:
             val = result['company']
             # "Supplier : Global..." -> "Global..."
             for prefix in ['Supplier:', 'Supplier :', 'Supplier']:
                  if val.startswith(prefix):
                      val = val[len(prefix):].strip()
             result['issuer'] = val
             result['company'] = None

        # [Fix] Company 추출 실패 시 Issuer를 Company로 대체 (Sample 10, 04 대응)
        if not result['company'] and result['issuer']:
             result['company'] = result['issuer']
        
        # 중복 체크 (Company == Issuer)
        if result['company'] and result['issuer']:
            def clean(s):
                # [Fix] 콜론(:), 세미콜론(;) 등 특수문자도 제거하여 비교
                return re.sub(r'[\s\.\(\)주업체명상호품목:;-]', '', s)
            
            c_clean = clean(result['company'])
            i_clean = clean(result['issuer'])
            
            if c_clean == i_clean:
                result['issuer'] = None
        
        # 3. 부가 정보
        result['phone'] = self.phone_extractor.extract(word_boxes)
        result['product'] = self.product_extractor.extract(word_boxes)

        # 4. 보조 정보 (신규 추출기 위임)
        result['ticket_id'] = self.ticket_id_extractor.extract(word_boxes, vehicle_num=result.get('vehicle_num'))
        result['type'] = self.type_extractor.extract(word_boxes)
        result['gps'] = self.gps_extractor.extract(word_boxes)
        result['address'] = self.address_extractor.extract(word_boxes)
        
        # 신뢰도 계산
        result['_confidence'] = self._calculate_confidence(result)
        result['_methods'] = methods
        
        return result
    
    def _calculate_confidence(self, result: Dict) -> float:
        """신뢰도 계산"""
        score = 100.0
        required = ['date', 'vehicle_num', 'total_weight']
        for field in required:
            if not result.get(field): score -= 20
        if not result.get('company') and not result.get('issuer'): score -= 10
        
        total = result.get('total_weight')
        tare = result.get('tare_weight')
        net = result.get('net_weight')
        if total and tare and net:
            error = abs(total - (tare + net))
            if error > 100: score -= 30
            elif error > 50: score -= 15
        
        return max(0, score)
