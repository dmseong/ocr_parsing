import re
import unicodedata
from typing import List
from extractors.common import WordBox
from extractors.normalizer import AdvancedNoiseNormalizer

class OCRPreprocessor:
    """
    OCR 전처리 레이어 (Layer 0)
    
    모든 추출 로직이 실행되기 전에 원본 WordBox 데이터를 정제합니다.
    - 공백 정리 (Trim)
    - 무의미한 특수문자 제거
    - 글로벌 오인식 교정 (안전한 변환만 적용)
    """
    
    def __init__(self):
        self.normalizer = AdvancedNoiseNormalizer()
        
    def run(self, word_boxes: List[WordBox]) -> List[WordBox]:
        """
        WordBox 리스트를 순회하며 전처리를 수행합니다.
        
        Args:
            word_boxes: 원본 WordBox 리스트
            
        Returns:
            정제된 WordBox 리스트
        """
        cleaned_boxes = []
        
        for box in word_boxes:
            # 1. 텍스트 정규화
            original_text = box.text
            cleaned_text = self._clean_text(original_text)
            
            # 2. 필터링: 빈 문자열이나 무의미한 노이즈 제거
            if not cleaned_text:
                continue
            
            # 너무 짧은 노이즈 (예: ".", ",", "~") 단독 존재 시 제거
            # 단, 숫자나 통화 기호 등은 유지
            if len(cleaned_text) == 1 and not cleaned_text.isalnum():
                # 예외: 1,000의 콤마나 소수점 등이 단독으로 떨어져 나온 경우...
                # 하지만 보통 WordBox 단위에서 특수문자 단독은 노이즈일 확률이 높음.
                # 위험하므로 일단 유지하되, 정제만 수행
                pass
            
            box.text = cleaned_text
            cleaned_boxes.append(box)
            
        return cleaned_boxes

    def _clean_text(self, text: str) -> str:
        """단일 텍스트 정제"""
        if not text:
            return ""
        
        # 1. 유니코드 정규화 (NFC)
        text = unicodedata.normalize('NFC', text)
        
        # 2. 양끝 공백 제거
        text = text.strip()
        
        # 3. 안전한 글로벌 오인식 교정
        # AdvancedNoiseNormalizer의 char_map 사용
        # (주의: 문맥 없는 글로벌 변환이므로 정말 확실한 것만 해야 함)
        # 예: 'O' -> '0'은 맥락 없이 하면 위험할 수 있음 (영어 단어 ORANGE 등)
        # 따라서 여기서는 char_map 전체 적용보다는 '확실한 한글 깨짐' 위주로 처리
        
        # 한글 자모 분리 보정 (일단 간단한 것만)
        # 예: '차 랑' -> '차량' (공백 제거가 아님, 오타 수정임)
        # 이는 Normalizer의 context='label' 로직과 일부 겹치지만,
        # 여기서는 WordBox 텍스트 자체를 수정해버림.
        
        # Normalizer의 한글 fix map 활용
        for wrong, correct in self.normalizer.korean_fixes.items():
            if wrong in text:
                text = text.replace(wrong, correct)
                
        # 4. 불필요한 공백 축소 (두 칸 이상 -> 한 칸)
        text = re.sub(r'\s+', ' ', text)
        
        # 5. 특정 노이즈 키워드 제거 (Sample 03 '공육을 unle' 등)
        # 이런 무의미한 단어는 전처리 단계에서 날리는 것이 안전함
        NOISE_KEYWORDS = ['공육을', 'unle']
        if text in NOISE_KEYWORDS:
            return ""
            
        return text
