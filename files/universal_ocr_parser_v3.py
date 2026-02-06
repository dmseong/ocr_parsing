"""
UniversalOCRParser v3 - 실제 데이터 패턴 기반 재설계

개선 사항:
1. 실제 샘플 데이터 패턴 분석 후 재설계
2. 라벨-값 매칭 로직 강화 (공백 분리된 라벨 처리)
3. 중량 추출 시 시간(HH:MM) 패턴 완전 제거
4. 적응형 임계값을 활용한 근접 단어 탐색
5. 중량 검증 로직 개선
"""

import json
import re
import statistics
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    from difflib import SequenceMatcher


@dataclass
class WordBox:
    """단어와 bounding box 정보"""
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    confidence: float = 0.0
    
    @property
    def centroid(self) -> Tuple[float, float]:
        return ((self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2)
    
    @property
    def width(self) -> float:
        return self.x_max - self.x_min
    
    @property
    def height(self) -> float:
        return self.y_max - self.y_min


@dataclass
class Line:
    """좌표 기반으로 그룹화된 라인"""
    words: List[WordBox]
    y_avg: float
    
    def get_text(self, sep: str = " ") -> str:
        return sep.join(w.text for w in self.words)


@dataclass
class DocumentLayout:
    """문서 레이아웃 특성"""
    avg_char_width: float
    avg_line_height: float
    avg_word_spacing: float
    page_width: float
    page_height: float
    
    @property
    def x_threshold(self) -> float:
        """X축 탐색 임계값 (같은 라인 내)"""
        return max(self.avg_char_width * 50, 300)
    
    @property
    def y_threshold_same_line(self) -> float:
        """같은 라인 판단 임계값"""
        return max(self.avg_line_height * 0.5, 30)
    
    @property
    def y_threshold_next_line(self) -> float:
        """다음 라인 탐색 임계값"""
        return max(self.avg_line_height * 2.5, 100)


class UniversalOCRParser:
    """
    개선된 범용 OCR 파서
    실제 계근지 데이터 패턴을 기반으로 최적화
    """
    
    def __init__(self):
        self._init_label_patterns()
    
    def _init_label_patterns(self):
        """라벨 패턴 정의"""
        self.label_patterns = {
            "total_weight": {
                "labels": ["총중량", "총 중량", "총 중 량", "총량"],
                "min_value": 1000,  # kg
            },
            "tare_weight": {
                "labels": ["공차중량", "공차 중량", "공 차 중 량", "차중량", "차 중량", "중량", "중 량"],
                "min_value": 1000,
            },
            "net_weight": {
                "labels": ["실중량", "실 중량", "실 중 량", "실량"],
                "min_value": 10,  # 실중량은 작을 수 있음
            },
            "date": {
                "labels": ["계량일자", "계량 일자", "날짜", "일자", "날 짜", "일 시"],
            },
            "vehicle": {
                "labels": ["차량번호", "차량 번호", "차 량 번 호", "차번호", "차 번호", "차량No", "차량 No"],
            },
            "company": {
                "labels": ["거래처", "거 래 처", "상호", "상 호", "회사명", "회 사 명"],
            },
            "product": {
                "labels": ["품명", "품 명", "제품명", "제 품 명", "품종명", "품 종 명"],
            },
            "type": {
                "labels": ["구분", "구 분"],
            },
            "ticket_id": {
                "labels": ["ID-NO", "ID - NO", "계량번호", "계량횟수", "계 량 횟 수"],
            },
        }
    
    def parse(self, json_data: dict) -> dict:
        """메인 파싱 메서드"""
        # 1. WordBox 추출
        word_boxes = self._extract_word_boxes(json_data)
        if not word_boxes:
            return self._empty_result()
        
        # 2. 레이아웃 분석
        layout = self._analyze_layout(word_boxes)
        
        # 3. 라인 클러스터링
        lines = self._cluster_lines(word_boxes, layout)
        
        # 4. 필드 추출
        result = self._empty_result()
        used_label_words = set()  # 이미 사용한 라벨 단어 추적
        
        # 중량 필드 (우선순위: 총중량 -> 실중량 -> 공차중량)
        # 총중량부터 추출해야 "중량" 라벨이 총중량에 우선 배정됨
        for field in ["total_weight", "net_weight", "tare_weight"]:
            value, label_word = self._extract_weight_field_with_label(field, word_boxes, layout, used_label_words)
            if value:
                result[field] = value
                if label_word:
                    used_label_words.add(id(label_word))
        
        # 날짜
        result["date"] = self._extract_date(word_boxes, lines, layout)
        
        # 차량번호
        result["vehicle_num"] = self._extract_vehicle(word_boxes, lines, layout)
        
        # 회사명
        result["company"] = self._extract_company(word_boxes, layout)
        
        # 품명
        result["product"] = self._extract_product(word_boxes, layout)
        
        # 구분 (입고/출고)
        result["type"] = self._extract_type(word_boxes, lines)
        
        # Ticket ID
        result["ticket_id"] = self._extract_ticket_id(word_boxes, lines, layout)
        
        # 5. 중량 검증 및 보정
        result = self._validate_weights(result, word_boxes, layout)
        
        # 6. 추가 필드
        full_text = "\n".join(line.get_text() for line in lines)
        result["gps"] = self._extract_gps(full_text)
        result["issuer"] = self._extract_issuer(full_text)
        
        # 7. company가 비어있고 issuer가 있으면 issuer를 company로 사용
        if not result["company"] and result["issuer"]:
            result["company"] = result["issuer"]
        
        return result
    
    def _empty_result(self) -> dict:
        """빈 결과"""
        return {
            "date": None,
            "vehicle_num": None,
            "total_weight": None,
            "tare_weight": None,
            "net_weight": None,
            "company": None,
            "product": None,
            "type": None,
            "ticket_id": None,
            "issuer": None,
            "gps": None
        }
    
    def _extract_word_boxes(self, json_data: dict) -> List[WordBox]:
        """WordBox 추출"""
        words = []
        
        if 'pages' not in json_data or not json_data['pages']:
            return words
        
        page = json_data['pages'][0]
        if 'words' not in page:
            return words
        
        for word_data in page['words']:
            text = word_data.get('text', '').strip()
            bbox = word_data.get('boundingBox', {})
            
            if not text or 'vertices' not in bbox:
                continue
            
            vertices = bbox['vertices']
            if len(vertices) < 4:
                continue
            
            x_coords = [v['x'] for v in vertices]
            y_coords = [v['y'] for v in vertices]
            
            words.append(WordBox(
                text=text,
                x_min=min(x_coords),
                y_min=min(y_coords),
                x_max=max(x_coords),
                y_max=max(y_coords),
                confidence=word_data.get('confidence', 0.0)
            ))
        
        return words
    
    def _analyze_layout(self, word_boxes: List[WordBox]) -> DocumentLayout:
        """레이아웃 분석"""
        if not word_boxes:
            return DocumentLayout(10, 20, 5, 1000, 1000)
        
        # 문자 너비
        char_widths = []
        for word in word_boxes:
            if len(word.text) > 0:
                char_widths.append(word.width / len(word.text))
        avg_char_width = statistics.median(char_widths) if char_widths else 10
        
        # 라인 높이
        line_heights = [w.height for w in word_boxes if w.height > 0]
        avg_line_height = statistics.median(line_heights) if line_heights else 20
        
        # 단어 간격
        word_spacings = []
        sorted_words = sorted(word_boxes, key=lambda w: (w.centroid[1], w.centroid[0]))
        for i in range(len(sorted_words) - 1):
            w1, w2 = sorted_words[i], sorted_words[i + 1]
            if abs(w1.centroid[1] - w2.centroid[1]) <= avg_line_height:
                spacing = w2.x_min - w1.x_max
                if spacing > 0:
                    word_spacings.append(spacing)
        avg_word_spacing = statistics.median(word_spacings) if word_spacings else 5
        
        page_width = max(w.x_max for w in word_boxes)
        page_height = max(w.y_max for w in word_boxes)
        
        return DocumentLayout(
            avg_char_width=avg_char_width,
            avg_line_height=avg_line_height,
            avg_word_spacing=avg_word_spacing,
            page_width=page_width,
            page_height=page_height
        )
    
    def _cluster_lines(self, word_boxes: List[WordBox], layout: DocumentLayout) -> List[Line]:
        """라인 클러스터링"""
        if not word_boxes:
            return []
        
        sorted_words = sorted(word_boxes, key=lambda w: w.centroid[1])
        
        lines = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0].centroid[1]
        
        for word in sorted_words[1:]:
            if abs(word.centroid[1] - current_y) <= layout.y_threshold_same_line:
                current_line.append(word)
            else:
                current_line.sort(key=lambda w: w.centroid[0])
                y_avg = sum(w.centroid[1] for w in current_line) / len(current_line)
                lines.append(Line(words=current_line, y_avg=y_avg))
                
                current_line = [word]
                current_y = word.centroid[1]
        
        if current_line:
            current_line.sort(key=lambda w: w.centroid[0])
            y_avg = sum(w.centroid[1] for w in current_line) / len(current_line)
            lines.append(Line(words=current_line, y_avg=y_avg))
        
        return lines
    
    def _fuzzy_match(self, text1: str, text2: str) -> float:
        """퍼지 매칭 점수 (0-100)"""
        if HAS_RAPIDFUZZ:
            return fuzz.ratio(text1, text2)
        else:
            return SequenceMatcher(None, text1, text2).ratio() * 100
    
    def _find_label(self, label_candidates: List[str], word_boxes: List[WordBox], 
                    threshold: float = 70) -> Optional[WordBox]:
        """
        라벨 단어 찾기
        - 단일 단어 매칭
        - 연속된 단어 조합 매칭 (공백으로 분리된 라벨 처리)
        """
        best_match = None
        best_score = 0
        
        # 1. 단일 단어 매칭
        for word in word_boxes:
            clean_text = word.text.replace(' ', '').replace(':', '').replace('.', '')
            
            for pattern in label_candidates:
                score = self._fuzzy_match(clean_text, pattern)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = word
        
        # 2. 연속된 단어 조합 매칭 (공백 분리 라벨 처리)
        # 예: "거" "래" "처:" -> "거래처"
        for i in range(len(word_boxes)):
            # 최대 5개 단어 조합
            for j in range(i + 1, min(i + 6, len(word_boxes) + 1)):
                combined = "".join(w.text.replace(':', '').replace('.', '') for w in word_boxes[i:j])
                
                for pattern in label_candidates:
                    score = self._fuzzy_match(combined, pattern)
                    if score > best_score and score >= threshold:
                        best_score = score
                        # 마지막 단어를 앵커로 사용
                        best_match = word_boxes[j - 1]
        
        return best_match
    
    def _find_right_words(self, anchor: WordBox, word_boxes: List[WordBox],
                         layout: DocumentLayout, max_words: int = 10) -> List[WordBox]:
        """오른쪽 단어들 찾기"""
        candidates = []
        
        for word in word_boxes:
            if word.x_min > anchor.x_max:
                y_diff = abs(word.centroid[1] - anchor.centroid[1])
                if y_diff <= layout.y_threshold_same_line:
                    x_dist = word.x_min - anchor.x_max
                    if x_dist <= layout.x_threshold:
                        candidates.append((x_dist, word))
        
        candidates.sort(key=lambda x: x[0])
        return [w for _, w in candidates[:max_words]]
    
    def _find_below_words(self, anchor: WordBox, word_boxes: List[WordBox],
                         layout: DocumentLayout, max_words: int = 5) -> List[WordBox]:
        """아래 단어들 찾기"""
        candidates = []
        
        for word in word_boxes:
            if word.y_min > anchor.y_max:
                y_dist = word.y_min - anchor.y_max
                if y_dist <= layout.y_threshold_next_line:
                    # X축 겹침 확인
                    overlap_start = max(anchor.x_min, word.x_min)
                    overlap_end = min(anchor.x_max, word.x_max)
                    
                    if overlap_start < overlap_end:
                        overlap = (overlap_end - overlap_start) / min(anchor.width, word.width)
                        if overlap >= 0.2:
                            candidates.append((y_dist, word))
        
        candidates.sort(key=lambda x: x[0])
        return [w for _, w in candidates[:max_words]]
    
    def _extract_weight_field_with_label(self, field_name: str, word_boxes: List[WordBox],
                                         layout: DocumentLayout, used_labels: set) -> Tuple[Optional[int], Optional[WordBox]]:
        """중량 필드 추출 (사용된 라벨 반환)"""
        config = self.label_patterns[field_name]
        label_word = self._find_label_excluding_used(config["labels"], word_boxes, used_labels)
        
        if not label_word:
            return None, None
        
        min_value = config["min_value"]
        
        # 오른쪽 탐색
        right_words = self._find_right_words(label_word, word_boxes, layout, max_words=15)
        if right_words:
            combined = " ".join(w.text for w in right_words)
            num = self._parse_weight(combined, min_value)
            if num:
                return num, label_word
        
        # 아래 탐색
        below_words = self._find_below_words(label_word, word_boxes, layout)
        if below_words:
            combined = " ".join(w.text for w in below_words)
            num = self._parse_weight(combined, min_value)
            if num:
                return num, label_word
        
        return None, None
    
    def _find_label_excluding_used(self, label_candidates: List[str], word_boxes: List[WordBox],
                                   used_labels: set, threshold: float = 70) -> Optional[WordBox]:
        """라벨 찾기 (이미 사용된 라벨 제외)"""
        best_match = None
        best_score = 0
        
        # 1. 단일 단어 매칭
        for word in word_boxes:
            if id(word) in used_labels:
                continue
            
            clean_text = word.text.replace(' ', '').replace(':', '').replace('.', '')
            
            for pattern in label_candidates:
                score = self._fuzzy_match(clean_text, pattern)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = word
        
        # 2. 연속된 단어 조합
        for i in range(len(word_boxes)):
            if id(word_boxes[i]) in used_labels:
                continue
            
            for j in range(i + 1, min(i + 6, len(word_boxes) + 1)):
                if any(id(word_boxes[k]) in used_labels for k in range(i, j)):
                    continue
                
                combined = "".join(w.text.replace(':', '').replace('.', '') for w in word_boxes[i:j])
                
                for pattern in label_candidates:
                    score = self._fuzzy_match(combined, pattern)
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = word_boxes[j - 1]
        
        return best_match
    
    def _parse_weight(self, text: str, min_value: int = 50) -> Optional[int]:
        """
        중량 파싱
        핵심: 시간 패턴(HH:MM)을 완전히 제거하고 숫자 추출
        """
        # 1. 시간 패턴 제거 (가장 먼저!)
        # "02:07 13 460 kg" -> " 13 460 kg"
        # "05:26:18 12,480 kg" -> " 12,480 kg"
        clean = re.sub(r'\d{1,2}\s*:\s*\d{2}(?:\s*:\s*\d{2})?', '', text)
        
        # 2. 날짜 패턴 제거
        clean = re.sub(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', '', clean)
        
        # 3. 쉼표 제거
        clean = clean.replace(',', '')
        
        # 4. 공백 정규화
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        # 5. kg 키워드 확인
        has_kg = 'kg' in text.lower()
        
        # 6. 숫자 패턴 매칭
        patterns = [
            r'\d+\s+\d{3}(?:\s+\d{3})*',  # "13 460", "1 320" 형태
            r'\d{4,}',                     # 4자리 이상
            r'\d+',                        # 일반 숫자
        ]
        
        candidates = []
        
        for pattern in patterns:
            for match in re.finditer(pattern, clean):
                num_str = match.group().replace(' ', '')
                
                if num_str.isdigit():
                    val = int(num_str)
                    
                    # 연도 필터링 (2000-2099)
                    if 2000 <= val <= 2099:
                        if not has_kg and min_value >= 1000:
                            continue
                    
                    # 작은 숫자 필터링 (차량번호 등)
                    if 100 <= val < 1000 and min_value >= 1000:
                        continue
                    
                    if val >= min_value:
                        candidates.append(val)
        
        # 가장 큰 숫자 반환 (일반적으로 중량값이 가장 큼)
        return max(candidates) if candidates else None
    
    def _extract_date(self, word_boxes: List[WordBox], lines: List[Line],
                     layout: DocumentLayout) -> Optional[str]:
        """날짜 추출"""
        # 1. 라벨 기반
        config = self.label_patterns["date"]
        label_word = self._find_label(config["labels"], word_boxes)
        
        if label_word:
            right_words = self._find_right_words(label_word, word_boxes, layout)
            if right_words:
                combined = " ".join(w.text for w in right_words[:5])
                date_str = self._parse_date(combined)
                if date_str:
                    return date_str
            
            below_words = self._find_below_words(label_word, word_boxes, layout)
            if below_words:
                combined = " ".join(w.text for w in below_words)
                date_str = self._parse_date(combined)
                if date_str:
                    return date_str
        
        # 2. 패턴 기반 (전체 텍스트)
        full_text = "\n".join(line.get_text() for line in lines)
        return self._parse_date(full_text)
    
    def _parse_date(self, text: str) -> Optional[str]:
        """날짜 파싱"""
        patterns = [
            r'20\d{2}[-./]\d{1,2}[-./]\d{1,2}',
            r'20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group().replace('.', '-').replace('/', '-')
                date_str = re.sub(r'\s+', '', date_str)
                return date_str
        
        return None
    
    def _extract_vehicle(self, word_boxes: List[WordBox], lines: List[Line],
                        layout: DocumentLayout) -> Optional[str]:
        """차량번호 추출"""
        # 1. 라벨 기반
        config = self.label_patterns["vehicle"]
        label_word = self._find_label(config["labels"], word_boxes)
        
        if label_word:
            right_words = self._find_right_words(label_word, word_boxes, layout)
            if right_words:
                combined = " ".join(w.text for w in right_words[:5])
                vehicle = self._parse_vehicle(combined)
                if vehicle:
                    return vehicle
            
            below_words = self._find_below_words(label_word, word_boxes, layout)
            if below_words:
                combined = " ".join(w.text for w in below_words)
                vehicle = self._parse_vehicle(combined)
                if vehicle:
                    return vehicle
        
        # 2. 패턴 기반
        full_text = "\n".join(line.get_text() for line in lines)
        return self._parse_vehicle(full_text)
    
    def _parse_vehicle(self, text: str) -> Optional[str]:
        """
        차량번호 파싱
        - 한글 포함 패턴 우선
        - 순수 숫자 4자리 (날짜/주소 제외)
        """
        # 1. 한글 포함 (12가3456, 80구8713)
        match = re.search(r'\d{2,3}[가-힣가-힣]+\d{4}', text)
        if match:
            return match.group()
        
        # 2. 숫자만 4자리
        # 날짜 제외, 주소의 번지수 제외 (하이픈 뒤에 오는 숫자)
        candidates = []
        for match in re.finditer(r'(?<![-/])\b\d{4}\b(?![-/])', text):
            num = match.group()
            # 연도 제외
            if not num.startswith('202') and not num.startswith('199'):
                # 주변 컨텍스트 확인 (주소가 아닌지)
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end]
                
                # 주소 키워드 제외
                if not any(kw in context for kw in ['번길', '로', '길', '면', '시', '동', '구']):
                    candidates.append(num)
        
        # 가장 먼저 나온 것 반환
        return candidates[0] if candidates else None
    
    def _extract_company(self, word_boxes: List[WordBox], layout: DocumentLayout) -> Optional[str]:
        """회사명 추출"""
        config = self.label_patterns["company"]
        label_word = self._find_label(config["labels"], word_boxes)
        
        if label_word:
            right_words = self._find_right_words(label_word, word_boxes, layout)
            if right_words:
                text = " ".join(w.text for w in right_words[:5])
                cleaned = self._clean_text_field(text)
                if cleaned:
                    return cleaned
            
            below_words = self._find_below_words(label_word, word_boxes, layout)
            if below_words:
                text = " ".join(w.text for w in below_words[:3])
                cleaned = self._clean_text_field(text)
                if cleaned:
                    return cleaned
        
        # Fallback 1: "귀하" 앞의 단어 (수신처 패턴)
        for i, word in enumerate(word_boxes):
            if word.text.strip() == '귀하':
                if i > 0:
                    company_text = word_boxes[i-1].text
                    # 괄호 제거 후 반환
                    company_text = re.sub(r'\([^)]*\)', '', company_text).strip()
                    if len(company_text) >= 2:
                        return company_text
        
        # Fallback 2: issuer에서 추출 (회사명 라벨이 있지만 값이 비어있는 경우)
        # 이 경우 나중에 issuer를 추출한 후 company가 비어있으면 issuer를 사용
        
        return None
    
    def _extract_product(self, word_boxes: List[WordBox], layout: DocumentLayout) -> Optional[str]:
        """품명 추출"""
        config = self.label_patterns["product"]
        label_word = self._find_label(config["labels"], word_boxes)
        
        if not label_word:
            return None
        
        right_words = self._find_right_words(label_word, word_boxes, layout)
        if right_words:
            text = " ".join(w.text for w in right_words[:5])
            return self._clean_text_field(text)
        
        below_words = self._find_below_words(label_word, word_boxes, layout)
        if below_words:
            text = " ".join(w.text for w in below_words[:3])
            return self._clean_text_field(text)
        
        return None
    
    def _clean_text_field(self, text: str) -> Optional[str]:
        """텍스트 필드 정제"""
        text = text.replace(':', '').strip()
        
        words = []
        for word in text.split():
            if len(word) >= 2 and any('\uac00' <= c <= '\ud7a3' for c in word):
                # 제외 키워드
                if word not in ['kg', 'ton', '입고', '출고', '호', '명', '량', '중', '품', '제']:
                    words.append(word)
        
        return " ".join(words[:3]) if words else None
    
    def _extract_type(self, word_boxes: List[WordBox], lines: List[Line]) -> Optional[str]:
        """구분 (입고/출고) 추출"""
        for word in word_boxes:
            text = word.text
            
            # "입고" 또는 "출고" 포함 여부 체크
            if '입고' in text:
                return '입고'
            elif '출고' in text:
                return '출고'
        
        # 전체 텍스트에서도 검색
        full_text = "\n".join(line.get_text() for line in lines)
        if '입고' in full_text:
            return '입고'
        elif '출고' in full_text:
            return '출고'
        
        # Fuzzy matching
        if HAS_RAPIDFUZZ:
            for word in word_boxes:
                if fuzz.partial_ratio(word.text, '입고') > 85:
                    return '입고'
                if fuzz.partial_ratio(word.text, '출고') > 85:
                    return '출고'
        
        return None
    
    def _extract_ticket_id(self, word_boxes: List[WordBox], lines: List[Line],
                          layout: DocumentLayout) -> Optional[str]:
        """Ticket ID 추출"""
        config = self.label_patterns["ticket_id"]
        label_word = self._find_label(config["labels"], word_boxes)
        
        if label_word:
            right_words = self._find_right_words(label_word, word_boxes, layout, max_words=5)
            if right_words:
                combined = " ".join(w.text for w in right_words)
                ticket_id = self._parse_ticket_id(combined)
                if ticket_id:
                    return ticket_id
        
        # Fallback: 4자리 숫자 찾기 (날짜 제외, 차량번호와 구분)
        # "0016", "010889", "0022" 등
        full_text = "\n".join(line.get_text() for line in lines)
        
        # 0으로 시작하는 4-6자리
        for match in re.finditer(r'\b(0\d{3,5})\b', full_text):
            ticket_id = match.group(1)
            # 길이 체크
            if 4 <= len(ticket_id) <= 6:
                return ticket_id
        
        return None
    
    def _parse_ticket_id(self, text: str) -> Optional[str]:
        """Ticket ID 파싱"""
        # 0으로 시작하는 4-6자리 우선
        match = re.search(r'\b(0\d{3,5})\b', text)
        if match:
            return match.group(1)
        
        # 일반 4-6자리 (날짜 제외)
        match = re.search(r'\b(\d{4,6})\b', text)
        if match:
            ticket_id = match.group(1)
            if not ticket_id.startswith('202'):
                return ticket_id
        
        return None
    
    def _validate_weights(self, result: dict, word_boxes: List[WordBox],
                         layout: DocumentLayout) -> dict:
        """중량 검증 및 보정"""
        total = result.get("total_weight")
        tare = result.get("tare_weight")
        net = result.get("net_weight")
        
        # 모두 있으면 검증
        if total and tare and net:
            expected_net = total - tare
            if abs(net - expected_net) <= 10:  # 허용 오차 10kg
                result["net_weight"] = expected_net
        
        # 하나 누락 시 계산
        elif total and tare and not net:
            result["net_weight"] = total - tare
        elif total and net and not tare:
            result["tare_weight"] = total - net
        elif tare and net and not total:
            result["total_weight"] = tare + net
        
        # 2개 이상 누락 시 전체 스캔
        elif sum(x is not None for x in [total, tare, net]) <= 1:
            all_weights = self._scan_all_weights(word_boxes)
            
            for a in all_weights:
                for b in all_weights:
                    if a > b:
                        c = a - b
                        if c in all_weights and c >= 10:  # 실중량 최소 10kg
                            if not result.get("total_weight"):
                                result["total_weight"] = a
                            if not result.get("tare_weight"):
                                result["tare_weight"] = b
                            if not result.get("net_weight"):
                                result["net_weight"] = c
                            break
                if result.get("total_weight"):
                    break
        
        return result
    
    def _scan_all_weights(self, word_boxes: List[WordBox]) -> List[int]:
        """모든 중량 후보 스캔"""
        weights = set()
        
        for i, word in enumerate(word_boxes):
            if 'kg' in word.text.lower():
                # 주변 10개 단어
                start = max(0, i - 5)
                end = min(len(word_boxes), i + 6)
                combined = " ".join(w.text for w in word_boxes[start:end])
                
                num = self._parse_weight(combined, min_value=50)
                if num:
                    weights.add(num)
        
        return sorted(list(weights), reverse=True)
    
    def _extract_gps(self, text: str) -> Optional[dict]:
        """GPS 좌표 추출"""
        pattern = r'(\d+\.\d+)[,\s]+.*?(\d+\.\d+)'
        match = re.search(pattern, text)
        if match:
            return {
                "latitude": float(match.group(1)),
                "longitude": float(match.group(2))
            }
        return None
    
    def _extract_issuer(self, text: str) -> Optional[str]:
        """발행자 추출 (회사명 부분만, 주소 제외)"""
        patterns = [
            # "정우리사이클링(주)", "정우리사이클링 (주)" - (주) 앞의 회사명
            r'([가-힣]+)\s*\(주\)',
            # "(주)하은펄프" - (주) 바로 뒤 공백 없이 회사명 (주소 전까지)
            r'\(주\)([가-힣]+)(?=\s|$)',
            # "장원C&S"
            r'([가-힣]{2,}C&S)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                issuer = match.group(1).strip()
                # 공백 제거
                issuer = re.sub(r'\s+', '', issuer)
                
                # "(주) 앞 패턴"인 경우 (주) 추가
                if pattern.endswith(r'\(주\)'):
                    issuer = issuer + '(주)'
                # "(주) 뒤 패턴"인 경우 (주) 추가
                elif pattern.startswith(r'\(주\)'):
                    issuer = '(주)' + issuer
                
                return issuer
        
        return None


# 하위 호환
WeightTicketParser = UniversalOCRParser


if __name__ == "__main__":
    import sys
    
    parser = UniversalOCRParser()
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        result = parser.parse(ocr_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
