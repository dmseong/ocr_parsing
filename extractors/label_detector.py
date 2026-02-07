import re
from typing import List, Dict, Optional
from difflib import SequenceMatcher

from .common import LabelMatch, WordBox, HAS_SPACY, spacy, Matcher, HAS_RAPIDFUZZ, fuzz, process
from .config import LABEL_CONFIG, CONSTANTS

class SmartLabelDetector:
    """
    spaCy Matcher를 활용한 지능형 라벨 탐지기
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or LABEL_CONFIG
        
        if HAS_SPACY:
            self._init_spacy()
        else:
            self.nlp = None
            self.matcher = None
    
    def _init_spacy(self):
        """spaCy 모델 및 Matcher 초기화"""
        try:
            self.nlp = spacy.load('ko_core_news_sm')
        except OSError:
            # 한국어 모델 없으면 blank 모델 사용
            self.nlp = spacy.blank('ko')
        
        self.matcher = Matcher(self.nlp.vocab)
        self._add_patterns()
    
    def _add_patterns(self):
        """설정 기반 spaCy 패턴 등록"""
        for field_name, cfg in self.config.items():
            patterns = []
            
            # 패턴 1: 키워드 + 접미사
            for kw in cfg.get("keywords", []):
                for suffix in cfg.get("suffix_keywords", []):
                    # [{"LOWER": "총"}, {"LOWER": "중량"}]
                    patterns.append([
                        {"LOWER": {"IN": [kw.lower()]}},
                        {"LOWER": {"IN": [suffix.lower()]}}
                    ])
            
            # 패턴 2: 단일 키워드 (canonical)
            for canonical in cfg.get("canonical", []):
                # 공백 제거 버전
                clean = canonical.replace(" ", "")
                if len(clean) >= 2:
                    patterns.append([{"LOWER": clean.lower()}])
            
            if patterns and self.matcher:
                self.matcher.add(field_name.upper(), patterns)
    
    def detect_labels(self, text: str) -> List[LabelMatch]:
        """텍스트에서 라벨 탐지"""
        results = []
        
        if HAS_SPACY and self.nlp and self.matcher:
            results.extend(self._detect_with_spacy(text))
        
        # Fuzzy fallback
        results.extend(self._detect_with_fuzzy(text))
        
        # 중복 제거 (같은 타입에서 최고 점수만)
        best_by_type = {}
        for match in results:
            key = match.label_type
            if key not in best_by_type or match.match_score > best_by_type[key].match_score:
                best_by_type[key] = match
        
        return list(best_by_type.values())
    
    def _detect_with_spacy(self, text: str) -> List[LabelMatch]:
        """spaCy Matcher로 탐지"""
        results = []
        
        doc = self.nlp(text)
        matches = self.matcher(doc)
        
        for match_id, start, end in matches:
            label_type = self.nlp.vocab.strings[match_id].lower()
            matched_span = doc[start:end]
            
            results.append(LabelMatch(
                label_type=label_type,
                matched_text=matched_span.text,
                match_score=90.0,  # spaCy 패턴 매치는 높은 신뢰도
                word_box=None
            ))
        
        return results
    
    def _detect_with_fuzzy(self, text: str) -> List[LabelMatch]:
        """Fuzzy Matching으로 탐지 (Fallback)"""
        results = []
        
        # 텍스트를 청크로 분할
        chunks = re.split(r'[\s:,\n]+', text)
        
        for field_name, cfg in self.config.items():
            all_labels = cfg.get("canonical", []) + cfg.get("variants", [])
            
            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                
                for label in all_labels:
                    score = self._fuzzy_score(chunk, label)
                    if score >= 70:
                        results.append(LabelMatch(
                            label_type=field_name,
                            matched_text=chunk,
                            match_score=score,
                            word_box=None
                        ))
        
        return results
    
    def _fuzzy_score(self, text1: str, text2: str) -> float:
        """레벤슈타인 거리 기반 두 문자열 유사도 계산"""
        # 전처리: 공백 및 특수문자 제거, 소문자화
        t1 = re.sub(r'[^가-힣a-zA-Z0-9]', '', text1).lower()
        t2 = re.sub(r'[^가-힣a-zA-Z0-9]', '', text2).lower()
        
        # 완전 일치 시 가산점
        if t1 == t2: return 100.0
        
        if HAS_RAPIDFUZZ:
            return fuzz.ratio(t1, t2)
        else:
            return SequenceMatcher(None, t1, t2).ratio() * 100
    
    def find_label_in_wordboxes(self, label_type: str, 
                                  word_boxes: List[WordBox],
                                  threshold: float = None) -> Optional[WordBox]:
        """
        WordBox 리스트에서 특정 라벨 타입 찾기
        (N-gram 병합 로직 포함: 최대 6단어)
        """
        if threshold is None:
            # 라벨별 동적 임계값 적용
            if label_type in ["total_weight", "net_weight", "tare_weight"]:
                threshold = 60  # 중량은 뭉개지는 빈도가 높음
            elif label_type == "date":
                threshold = 65
            else:
                threshold = CONSTANTS['LABEL_MATCH_THRESHOLD']
            
        cfg = self.config.get(label_type, {})
        all_labels = cfg.get("canonical", []) + cfg.get("variants", [])
        
        best_match = None
        best_score = 0
        
        # 최대 6단어까지 병합 시도
        MAX_MERGE = 6
        n_boxes = len(word_boxes)
        
        for i in range(n_boxes):
            current_group = []
            
            for j in range(MAX_MERGE):
                if i + j >= n_boxes:
                    break
                
                word = word_boxes[i + j]
                
                # 병합 유효성 검사 (첫 단어 이후부터 체크)
                if j > 0:
                    prev_word = current_group[-1]
                    # x축 거리 체크
                    if word.x_min - prev_word.x_max > CONSTANTS['LABEL_MERGE_DIST_X']: 
                        break
                    # y축 라인 체크
                    if abs(word.centroid[1] - prev_word.centroid[1]) > CONSTANTS['LABEL_MERGE_DIST_Y']:
                        break
                
                current_group.append(word)
                
                # 현재 그룹 텍스트 병합 (공백, 기호 제거 후 비교)
                merged_text = "".join(w.text for w in current_group).replace(" ", "").replace(":", "").replace(".", "")
                
                # 라벨 매칭 시도
                for label in all_labels:
                    # 라벨은 한글인데 매칭 대상에 한글이 너무 적으면 스킵 (노이즈 방지)
                    if any('가' <= c <= '힣' for c in label):
                        hangul_len = len(re.findall(r'[가-힣]', merged_text))
                        if hangul_len < len(label) * 0.5: continue

                    score = self._fuzzy_score(merged_text, label)
                    
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = self._create_merged_box(current_group, merged_text)
                    
                    elif score == best_score and score >= threshold:
                        best_match = self._create_merged_box(current_group, merged_text)

        return best_match

    def _create_merged_box(self, group: List[WordBox], text: str) -> WordBox:
        """병합된 WordBox 생성 헬퍼"""
        return WordBox(
            text=text,
            x_min=group[0].x_min,
            y_min=min(w.y_min for w in group),
            x_max=group[-1].x_max,
            y_max=max(w.y_max for w in group),
            confidence=sum(w.confidence for w in group) / len(group)
        )
