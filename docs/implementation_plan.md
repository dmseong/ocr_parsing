# HybridOCRParser Implementation Plan

Build a sophisticated OCR post-processing parser for weight tickets (계근지) that can handle various layouts and OCR noise patterns using coordinate-based extraction and fuzzy matching.

## User Review Required

> [!IMPORTANT]
> **Architectural Decision**: This implementation creates `HybridOCRParser`, which integrates Regex-based and spaCy-based extraction.


> [!WARNING]
> **Dependency Change**: The new parser will use `rapidfuzz` for fuzzy matching but will minimize spaCy usage (only for text tokenization if needed). Core logic relies on coordinate geometry using standard library (`math`, `difflib`).

## Proposed Changes

### Core Parser Module

#### [NEW] [universal_ocr_parser.py](file:///c:/Users/2with/OneDrive/Desktop/assign/other/reco/universal_ocr_parser.py)

**Purpose**: Complete implementation of coordinate-based OCR parser

**Key Components**:

1. **Line Clustering Algorithm**
   - Extract bounding box centroids (Y-coordinate)
   - Group words into lines using Y-coordinate clustering (tolerance ~20px)
   - Sort words within each line by X-coordinate (left-to-right)
   - Reconstruct text based on spatial layout, not OCR sequence

2. **Relative Position Extraction**
   - Define spatial relationship functions:
     - `find_right_of(label_box, threshold=50)`: Find boxes to the right
     - `find_below(label_box, threshold=50)`: Find boxes below
   - When label is found, search for values using coordinate proximity
   - Handle both horizontal layouts (label: value) and vertical layouts

3. **Noise Cleaning**
   ```python
   # Number reconstruction
   "12 480" → "12480"
   "7 560" → "7560"
   
   # Fuzzy label matching (using rapidfuzz)
   "품종명랑" → "품명" (score: 85%)
   "차 중 량" → "차량중량" (score: 90%)
   "* 계 그 표 *" → "계근표" (score: 75%)
   ```

4. **Weight Validation & Correction**
   - Extract all three weights: 총중량, 공차중량, 실중량
   - Validate: `총중량 - 공차중량 == 실중량`
   - If one is missing/wrong, calculate from other two:
     ```python
     if 총중량 and 공차중량 and not 실중량:
         실중량 = 총중량 - 공차중량
     # Similar logic for other combinations
     ```

**Class Structure**:
```python
class UniversalOCRParser:
    def __init__(self):
        self.label_patterns = {...}  # Fuzzy match patterns
        
    def parse(self, json_data) -> dict:
        """Main entry point"""
        
    def _extract_words_with_boxes(self, json_data) -> List[WordBox]:
        """Extract words and bounding boxes"""
        
    def _cluster_into_lines(self, word_boxes) -> List[Line]:
        """Coordinate-based line clustering"""
        
    def _find_label_fuzzy(self, text, candidates) -> Optional[Match]:
        """Fuzzy label matching"""
        
    def _find_right_of(self, anchor_box, word_boxes) -> List[WordBox]:
        """Find boxes to the right"""
        
    def _find_below(self, anchor_box, word_boxes) -> List[WordBox]:
        """Find boxes below"""
        
    def _clean_number(self, text) -> Optional[int]:
        """Clean and extract numbers (handle spaces)"""
        
    def _validate_weights(self, extracted) -> dict:
        """Validate and correct weights"""
```

---

### Testing & Verification

#### [MODIFY] [verify_parser.py](file:///c:/Users/2with/OneDrive/Desktop/assign/other/reco/verify_parser.py)

Add option to test the new `UniversalOCRParser`:
- Import both parsers
- Add command-line flag to select parser
- Compare results side-by-side

---

## Verification Plan

### Automated Tests

1. **Unit Tests** (New file: `test_universal_parser.py`)
   ```bash
   python -m pytest test_universal_parser.py -v
   ```
   
   Test cases:
   - Line clustering with various Y-coordinate distributions
   - Number cleaning: `"12 480"` → `12480`
   - Fuzzy matching: `"품종명랑"` → `"품명"`
   - Weight validation logic
   - Position-based extraction (right/below)

2. **Integration Test with Sample Data**
   ```bash
   python verify_parser.py --parser universal
   ```
   
   Expected results:
   - **sample_01.json**: 
     - Extract despite typos: '품종명랑' → '품명', '곰욕환경폐기물' → company
     - Weights: 총중량=12,480kg, 공차중량=7,470kg, 실중량=5,010kg
     - Validation: 12,480 - 7,470 = 5,010 ✓
   
   - **sample_02.json**:
     - Handle spaced numbers: '13 460' → 13,460
     - Handle label noise: '* 계 그 표 *' → recognize as title
     - Weights: 총중량=13,460kg, 차중량=7,560kg, 실중량=5,900kg
     - Validation: 13,460 - 7,560 = 5,900 ✓
   
   - **sample_03.json** & **sample_04.json**: Parse successfully

### Manual Verification

1. **Visual Inspection**
   - Print extracted lines with Y-coordinates to verify clustering
   - Display matched labels with fuzzy scores
   - Show weight calculation steps

2. **Edge Case Testing**
   - Create a test JSON with intentionally corrupted data
   - Verify parser handles missing fields gracefully
   - Test with completely unrelated JSON (should fail gracefully)

### Success Criteria

- ✅ All 4 sample files parse successfully
- ✅ Weight validation passes for all samples
- ✅ Fuzzy matching handles known typos (score > 75%)
- ✅ Coordinate-based extraction works for both horizontal and vertical layouts
- ✅ Number reconstruction handles spaced digits correctly
