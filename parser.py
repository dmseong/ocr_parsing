import json
import re
import statistics
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

# 외부 모듈 import
from extractors.normalizer import AdvancedNoiseNormalizer
from extractors.common import (
    WordBox, Line, DocumentLayout,
    get_empty_result, extract_word_boxes, analyze_layout
)

# [New] Preprocessing Layer
from extractors.preprocessor import OCRPreprocessor

# 새 모듈 import
try:
    from extractors import (
        SmartFieldExtractor,
        SmartLabelDetector,
        SpatialValueExtractor,
        HeuristicValueFinder,
        LABEL_CONFIG,
    )
    HAS_SMART_EXTRACTORS = True
except ImportError:
    HAS_SMART_EXTRACTORS = False
    SmartFieldExtractor = None

try:
    from confidence_scorer import (
        ConfidenceScorer,
        ReviewPriority,
    )
    HAS_CONFIDENCE_SCORER = True
except ImportError:
    HAS_CONFIDENCE_SCORER = False
    ConfidenceScorer = None


# =============================================================================
# Hybrid Parser
# =============================================================================

class UnifiedOCRParser:
    """
    통합 OCR 파서 (UnifiedOCRParser)
    
    SmartFieldExtractor를 중심으로 모든 추출 로직을 통합한
    고성능 단일 파이프라인 파서입니다.
    """
    
    def __init__(self, use_smart_extractor: bool = True,
                 use_confidence_scorer: bool = True):
        """
        Args:
            use_smart_extractor: SmartFieldExtractor 사용 여부
            use_confidence_scorer: ConfidenceScorer 사용 여부
        """
        # 공통 컴포넌트
        self.normalizer = AdvancedNoiseNormalizer()
        self.preprocessor = OCRPreprocessor()  # [New] 전처리 레이어
        
        # 스마트 추출기 (선택적)
        self.use_smart = use_smart_extractor and HAS_SMART_EXTRACTORS
        if self.use_smart:
            self.smart_extractor = SmartFieldExtractor(self.normalizer)
        else:
            self.smart_extractor = None
        
        # 설정 기반 라벨 패턴 초기화 상단으로 이동
        self._init_label_patterns()
        
        # 레거시 전략 제거됨
        self.regex_extractor = None
        
        # 신뢰도 점수기 (선택적)
        self.use_scorer = use_confidence_scorer and HAS_CONFIDENCE_SCORER
        if self.use_scorer:
            self.scorer = ConfidenceScorer()
        else:
            self.scorer = None
    
    def _init_label_patterns(self) -> None:
        """라벨 패턴 초기화 및 기본값 설정"""
        if HAS_SMART_EXTRACTORS and LABEL_CONFIG:
            # 설정 복사
            import copy
            self.label_patterns = copy.deepcopy(LABEL_CONFIG)
            
            # 레거시 추출을 위해 누락된 한국어 특정 키워드 보강
            if "company" in self.label_patterns:
                canon = self.label_patterns["company"].get("canonical", [])
                for k in ["상호", "샹호", "샹 호"]:
                    if k not in canon: canon.append(k)
        else:
            # 기본 패턴 (Fallback): 정규화된 값과 매칭되도록 구성
            self.label_patterns = {
                "total_weight": {"canonical": ["총중량", "총 중량", "충중량", "충 중 량"]},
                "tare_weight": {"canonical": ["공차중량", "공차 중량"]},
                "net_weight": {"canonical": ["실중량", "실 중량", "실 충 량", "실충량"]},
                "date": {"canonical": ["계량일자", "날짜", "낱짜", "날좌", "낱 짜"]},
                "vehicle": {"canonical": ["차량번호", "차 량", "차 번 호"]},
                "company": {"canonical": ["거래처", "상호", "샹호", "샹 호"]},
                "product": {"canonical": ["품명", "제품명", "품면", "품 명"]},
                "ticket_id": {"canonical": ["전표번호", "ID-NO", "ID-N0", "IDNO"]},
            }
    
    # =========================================================================
    # Main Parse Method
    # =========================================================================
    
    def parse(self, json_data: dict) -> dict:
        """
        OCR JSON 데이터를 파싱하여 구조화된 딕셔너리를 반환합니다.
        
        Args:
            json_data: OCR 엔진에서 반환한 원본 JSON 데이터
            
        Returns:
            파싱된 결과 딕셔너리 (신뢰도 및 검수 정보 포함)
        """
        # 1. BoundingBox 유무 확인
        if not self._has_bounding_boxes(json_data):
            # BB가 없으면 텍스트 기반 Fallback
            result = self._parse_text_based(json_data)
        else:
            # 2. 전처리 및 레이아웃 분석
            word_boxes = extract_word_boxes(json_data)
            
            # [New] Preprocessing Layer (Layer 0)
            if self.preprocessor:
                word_boxes = self.preprocessor.run(word_boxes)
                
            if not word_boxes:
                result = self._empty_result()
            else:
                layout = analyze_layout(word_boxes)
                
                # 3. 전략 실행 (Single Pipeline)
                # SmartFieldExtractor가 모든 것을 담당
                if self.use_smart and self.smart_extractor:
                    try:
                        result = self.smart_extractor.extract_all(word_boxes, layout)
                    except Exception as e:
                        print(f"Extraction Error: {e}")
                        result = self._empty_result()
                        result['_error'] = str(e)
                else:
                    # Smart Extractor가 없는 경우 (거의 없음)
                    result = self._empty_result()
                    
                # 4. 결과 보정 (항상 ConfidenceScorer에서 수행됨)
                pass
        
        # 5. 신뢰도 측정 및 메타데이터 (항상 수행)
        if self.use_scorer and self.scorer:
            result = self.scorer.score(result)
        
        result['_parser_version'] = 'integrated_v6'
        return result

    def _parse_text_based(self, json_data: dict) -> dict:
        """텍스트 데이터만 있을 때의 Fallback 파싱"""
        raw_text = json_data.get('pages', [{}])[0].get('text', '')
        if not raw_text:
            return self._empty_result()
        
        # 텍스트 기반 파싱 (SmartExtractor 내부 기능 사용)
        result = self._empty_result()
        if self.use_smart and self.smart_extractor:
             # 임시 WordBox 생성 (좌표 0)
             # 하지만 SmartFieldExtractor는 WordBox 리스트를 요구함.
             # 텍스트만으로는 한계가 있으므로, 최소한의 정규식 추출만 수행하거나 Heuristic 사용
             # 여기서는 UnifiedWeightEngine의 텍스트 모드 사용
             text_weights = self.smart_extractor.unified_weight_engine.extract_weights_from_text(raw_text)
             if text_weights:
                 result.update(text_weights)
                 
             # [FIX] HeuristicValueFinder를 사용하여 나머지 필드 추출 (날짜, 차량, 전표 등)
             # SmartExtractor 내부에 heuristic_finder가 없으므로 새로 생성하거나 import 필요
             # 여기서는 직접 생성하여 사용
             try:
                 heuristic = HeuristicValueFinder(self.normalizer)
                 
                 # 1. 날짜
                 if not result.get('date'):
                     result['date'] = heuristic.find_date_in_text(raw_text)
                     
                 # 2. 차량번호
                 if not result.get('vehicle_num'):
                     result['vehicle_num'] = heuristic.find_vehicle_in_text(raw_text)
                     
                 # 3. 전표번호
                 if not result.get('ticket_id'):
                     result['ticket_id'] = heuristic.find_ticket_id_in_text(raw_text, result.get('vehicle_num'))
                     
                 # 4. GPS
                 if not result.get('gps'):
                     result['gps'] = heuristic.extract_gps(raw_text)
                     
                 # 5. 전화번호 (회사명 추론용 힌트)
                 if not result.get('phone'):
                     result['phone'] = heuristic.extract_phone(raw_text)
                     
                 # 6. 회사명 (HeuristicValueFinder 활용)
                 if not result.get('company'):
                     result['company'] = heuristic.extract_company(raw_text)

                 # 7. 발행처 (Issuer) - Company와 다를 경우
                 if not result.get('issuer'):
                     result['issuer'] = heuristic.extract_issuer(text=raw_text, company=result.get('company'))

                 # 8. 품명 및 구분
                 if not result.get('product'):
                     result['product'] = heuristic.extract_product(raw_text)
                 if not result.get('type'):
                     result['type'] = heuristic.extract_type(raw_text)

                 # 9. 주소
                 if not result.get('address'):
                     result['address'] = heuristic.extract_address(raw_text)

             except Exception as e:
                 print(f"Heuristic fallback error: {e}")
                 pass

        result['_parser_method'] = 'text_fallback_heuristic'
        return result

    
    def _has_bounding_boxes(self, json_data: dict) -> bool:
        """boundingBox 존재 여부"""
        if 'pages' not in json_data or not json_data['pages']:
            return False
        
        page = json_data['pages'][0]
        if 'words' not in page:
            return False
        
        for word_data in page['words']:
            bbox = word_data.get('boundingBox', {})
            if 'vertices' in bbox:
                return True
        
        return False
    
    # _ensemble_results 제거됨 (Single Pipeline)
    
    # _ensemble_weights 제거됨 (단일 소스)
    
    
    # =========================================================================
    # Text Parsers
    # =========================================================================
    
    def _empty_result(self) -> dict:
        """빈 결과 템플릿"""
        return get_empty_result()


# =============================================================================
# CLI Test
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=== Unified OCR Parser v6 ===")
    print(f"Smart Extractors: {HAS_SMART_EXTRACTORS}")
    print(f"Confidence Scorer: {HAS_CONFIDENCE_SCORER}")
    
    parser = UnifiedOCRParser()
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        result = parser.parse(ocr_data)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
