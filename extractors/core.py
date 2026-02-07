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
        
        # [Fix] 특정 노이즈 패턴에 의한 필드 오검출 보정
        if result['company'] and 'Supplier' in result['company']:
             val = result['company']
             # "Supplier : Global..." -> "Global..."
             for prefix in ['Supplier:', 'Supplier :', 'Supplier']:
                  if val.startswith(prefix):
                      val = val[len(prefix):].strip()
             result['issuer'] = val
             result['company'] = None


        
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
        
        return result
