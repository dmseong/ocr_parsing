from typing import List, Dict, Any
from .common import WordBox
from .weight_engine import UnifiedWeightEngine
from .label_detector import SmartLabelDetector
from .spatial_extractor import SpatialValueExtractor
from .heuristic_finder import HeuristicValueFinder
from .field_extractors import (
    WeightExtractor, DateExtractor, VehicleExtractor,
    CompanyExtractor, IssuerExtractor, PhoneExtractor, ProductExtractor
)

class SmartFieldExtractor:
    """
    spaCy 기반 통합 필드 추출기
    기존 Regex 기반 추출과 호환되는 인터페이스 제공
    """
    
    def __init__(self, normalizer=None):
        self.normalizer = normalizer
        
        # 모듈 초기화
        self.label_detector = SmartLabelDetector()
        self.spatial_extractor = SpatialValueExtractor(normalizer)
        self.heuristic_finder = HeuristicValueFinder(normalizer)
        
        # 전문 추출기
        self.unified_weight_engine = UnifiedWeightEngine(normalizer)
        self.weight_extractor = WeightExtractor(self.unified_weight_engine)
        self.date_extractor = DateExtractor(
            self.label_detector, self.spatial_extractor, self.heuristic_finder
        )
        self.vehicle_extractor = VehicleExtractor(
            self.label_detector, self.spatial_extractor, self.heuristic_finder
        )
        self.company_extractor = CompanyExtractor(
            self.label_detector, self.spatial_extractor
        )
        self.issuer_extractor = IssuerExtractor(self.label_detector)
        self.phone_extractor = PhoneExtractor(self.label_detector, self.spatial_extractor)
        self.product_extractor = ProductExtractor(self.label_detector, self.spatial_extractor)
    
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
            methods['weight'] = weights.get('_method', 'hybrid')
        
        # 2. 날짜
        result['date'] = self.date_extractor.extract(word_boxes)
        
        # 3. 차량번호
        result['vehicle_num'] = self.vehicle_extractor.extract(word_boxes)
        
        # 4. 회사명
        result['company'] = self.company_extractor.extract(word_boxes)
        
        # 5. 발행처 (Issuer)
        result['issuer'] = self.issuer_extractor.extract(word_boxes)
        if result['company'] and result['issuer']:
            if result['company'].replace(" ", "") == result['issuer'].replace(" ", ""):
                result['issuer'] = None
        
        # 6. 전화번호
        result['phone'] = self.phone_extractor.extract(word_boxes)
        
        # 7. 품명
        result['product'] = self.product_extractor.extract(word_boxes)

        # 8. 전표번호, GPS, 주소, 구분 (HeuristicValueFinder 사용)
        from .common import analyze_layout, cluster_lines
        layout_obj = analyze_layout(word_boxes)
        lines = cluster_lines(word_boxes, layout_obj)
        full_text_newline = "\n".join([line.get_text() for line in lines]) 
        
        result['ticket_id'] = self.heuristic_finder.find_ticket_id_in_text(full_text_newline, vehicle_num=result.get('vehicle_num'))
        result['type'] = self.heuristic_finder.extract_type(full_text_newline)
        result['gps'] = self.heuristic_finder.extract_gps(full_text_newline)
        result['address'] = self.heuristic_finder.extract_address(full_text_newline)
        
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
