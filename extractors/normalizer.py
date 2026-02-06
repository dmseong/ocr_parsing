import re
import unicodedata
from typing import Dict

class AdvancedNoiseNormalizer:
    """다층 노이즈 정규화 엔진"""
    
    def __init__(self):
        # Pass 1: 명확한 단일 변환 (순서 중요!)
        self.char_map = {
            'O': '0', 'o': '0', 'D': '0',
            'l': '1', 'I': '1', '|': '1',
            'B': '8',
            'S': '5', 's': '5',
            'Z': '2',
            'g': '9', 'q': '9'
        }
        
        # Pass 2: 복합 패턴
        self.pattern_map = {
            'k9': 'kg', 'K9': 'kg', 'kG': 'kg',
            'kg9': 'kg', 'KG9': 'KG',
            'Te1': 'Tel', 'TeI': 'Tel', 'Te l': 'Tel',
        }
        
        # Pass 3: 한글 OCR 오류 (도메인 지식 기반)
        self.korean_fixes = {
            '거래쳐': '거래처',
            '거ㄹh쳐': '거래처',
            'フㅓㄹh처': '거래처',
            '차랑': '차량',
            '차 랑': '차량',
            '차 번 호': '차량번호',
            '차번호': '차량번호',
            '충중량': '총중량',
            '충 중 량': '총중량',
            '총 중 량': '총중량',
            '공차중량': '공차중량',
            '공차 중량': '공차중량',
            '실중량': '실중량',
            '실 중 량': '실중량',
            '실 충 량': '실중량',
            '실충량': '실중량',
            '낱짜': '날짜',
            '날좌': '날짜',
            '낱 짜': '날짜',
            '날 짜': '날짜',
            '계량일자': '날짜',
            '샹호': '상호',
            '샹 호': '상호',
            '상 호': '상호',
            '샹  호': '상호',
            '샹   호': '상호',
            '상  호': '상호',
            '상   호': '상호',
            '품면': '품명',
            '품 면': '품명',
            '품 명': '품명',
            '제품명': '품명',
            '게근표': '계근표',
            '입 고': '입고',
            '출 고': '출고',
        }
    
    def normalize(self, text: str, context: str = 'general') -> str:
        """
        주어진 텍스트를 문맥(context)에 따라 정규화합니다.
        
        Args:
            text: 정규화할 원본 텍스트
            context: 'number' (숫자), 'label' (라벨), 'general' (일반)
        
        Returns:
            정규화된 텍스트
        """
        if not text:
            return text
        
        result = text
        
        # Unicode 정규화 (NFD → NFC)
        result = unicodedata.normalize('NFC', result)
        
        # Context별 전략
        if context == 'number':
            result = self._normalize_number_context(result)
        elif context == 'label':
            # 라벨 매칭을 위해 여러 개의 공백을 하나로 축소
            result = re.sub(r'\s+', ' ', result)
            result = self._normalize_label_context(result)
        
        # 일반 변환 적용
        result = self._apply_char_map(result)
        result = self._apply_pattern_map(result)
        
        return result
    
    def _normalize_number_context(self, text: str) -> str:
        """숫자 문맥 강화 보정"""
        result = text
        
        # 최대 10회 반복 (연쇄 변환 처리)
        for _ in range(10):
            prev = result
            
            # Lookback/Lookahead 패턴
            patterns = [
                (r'(\d)O(\d)', r'\g<1>0\g<2>'),      # 1O5 → 105
                (r'(\d)O([,.])', r'\g<1>0\g<2>'),    # 1O,234 → 10,234
                (r'([,.])OOO', r'\g<1>000'),         # ,OOO → ,000
                (r'(\d)l(\d)', r'\g<1>1\g<2>'),      # 1l5 → 115
                (r'(\d)I(\d)', r'\g<1>1\g<2>'),      # 1I5 → 115
                (r'(\d)B(\d)', r'\g<1>8\g<2>'),      # 1B5 → 185
                (r',BB', ',88'),                      # ,BB → ,88
                (r'(\d)o(\d)', r'\g<1>0\g<2>'),      # 소문자 o
                (r'2O2', '202'),                      # 2O26 -> 2026
                (r'(\d)B', r'\g<1>8'),                # B in middle/end
                (r'B(\d)', r'8\g<1>'),                # B in start/middle
                (r'(\d)S', r'\g<1>5'),
                (r'S(\d)', r'5\g<1>'),
            ]
            
            for pattern, repl in patterns:
                result = re.sub(pattern, repl, result)
            
            # 변화 없으면 중단
            if prev == result:
                break
        
        return result
    
    def _normalize_label_context(self, text: str) -> str:
        """
        라벨 문맥에서 한글 오인식 및 띄어쓰기를 보정합니다.
        
        Args:
            text: 원본 텍스트
            
        Returns:
            보정된 텍스트
        """
        result = text
        
        # 1. 특정 키워드 노이즈 제거 (강력한 정규식 기반)
        # 상호/거래처 관련
        result = re.sub(r'[샹상]\s*[후호]', '상호', result)
        result = re.sub(r'거\s*[래래레]\s*[처쳐]', '거래처', result)
        
        # 품명/제품명 관련
        result = re.sub(r'품\s*[면명]', '품명', result)
        result = re.sub(r'품\s*종\s*명\s*[랑랑]?\s*', '품명', result) # 품종명랑 대응
        result = re.sub(r'제\s*품\s*[면명]', '제품명', result)
        
        # 중량 관련
        result = re.sub(r'[충총]\s*중\s*량', '총중량', result)
        result = re.sub(r'공\s*차\s*중\s*량', '공차중량', result)
        result = re.sub(r'실\s*[충중]\s*량', '실중량', result)
        
        # 날짜/차량 관련
        result = re.sub(r'[낱날]\s*[짜좌]', '날짜', result)
        result = re.sub(r'계\s*량\s*일\s*자', '날짜', result)
        result = re.sub(r'차\s*번\s*호', '차량번호', result)
        
        # 기타
        result = re.sub(r'구\s*분', '구분', result)
        result = re.sub(r'경\s*위\s*도', 'GPS', result)
        
        # 2. 사전 정의된 오인식 교환 (개별 매핑)
        for wrong, correct in self.korean_fixes.items():
            result = result.replace(wrong, correct)
        
        return result
    
    def _apply_char_map(self, text: str) -> str:
        """문자 단위 변환"""
        result = []
        for char in text:
            result.append(self.char_map.get(char, char))
        return ''.join(result)
    
    def _apply_pattern_map(self, text: str) -> str:
        """패턴 단위 변환"""
        result = text
        for wrong, correct in self.pattern_map.items():
            result = result.replace(wrong, correct)
        return result
