import json
import os

def reconstruct_layout_from_data(json_data: dict) -> str:
    """
    JSON dict를 받아 좌표(boundingBox)를 기반으로 
    원본 문서의 레이아웃을 복원하여 문자열로 반환합니다.
    
    Args:
        json_data: OCR JSON 데이터 (dict)
    
    Returns:
        복원된 레이아웃 문자열
    """
    
    # 단어 데이터 추출
    try:
        words = json_data['pages'][0]['words']
    except (KeyError, IndexError):
        return "JSON 데이터 형식이 올바르지 않습니다 ('pages' 또는 'words' 누락)."

    # 데이터 전처리: 중심 좌표(cy) 및 높이 계산
    processed_words = []
    for w in words:
        box = w['boundingBox']['vertices']
        cy = (box[0]['y'] + box[2]['y']) / 2
        height = box[2]['y'] - box[0]['y']
        
        processed_words.append({
            'text': w['text'],
            'cy': cy,
            'x': box[0]['x'],
            'x_end': box[1]['x'],
            'height': height
        })

    processed_words.sort(key=lambda k: k['cy'])

    if not processed_words:
        return "추출된 텍스트가 없습니다."

    # 줄 단위 그룹화
    lines = []
    current_line = [processed_words[0]]
    
    for word in processed_words[1:]:
        last_word = current_line[-1]
        threshold = last_word['height'] * 0.3
        
        if abs(word['cy'] - last_word['cy']) < threshold:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
    
    lines.append(current_line)

    # 결과 문자열 생성
    SPACE_WIDTH_PIXEL = 12 
    result_lines = []

    for line in lines:
        line.sort(key=lambda k: k['x'])
        
        line_text = ""
        last_x_end = 0 

        if line:
            indent = int(line[0]['x'] // SPACE_WIDTH_PIXEL)
            line_text += " " * indent
            last_x_end = line[0]['x']

        for word in line:
            gap = word['x'] - last_x_end
            
            if gap > SPACE_WIDTH_PIXEL:
                num_spaces = int(gap // SPACE_WIDTH_PIXEL)
                line_text += " " * num_spaces
            
            line_text += word['text']
            last_x_end = word['x_end']
        
        result_lines.append(line_text)
    
    return "\n".join(result_lines)


def reconstruct_layout_from_file(file_path):
    """
    지정된 JSON 파일을 읽어 좌표(boundingBox)를 기반으로 
    원본 문서의 레이아웃을 복원하여 출력합니다.
    """
    
    if not os.path.exists(file_path):
        print(f"오류: 파일을 찾을 수 없습니다 -> {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"파일 읽기 오류: {e}")
        return

    result = reconstruct_layout_from_data(json_data)
    
    print("=" * 60)
    print(f"📄 파일 분석 결과: {file_path}")
    print("=" * 60)
    print(result)
    print("=" * 60)

# --- 실행 ---
if __name__ == "__main__":
    # 모든 샘플 파일 분석
    sample_files = [
        "sample_data_ocr/sample_01.json",
        "sample_data_ocr/sample_02.json",
        "sample_data_ocr/sample_03.json",
        "sample_data_ocr/sample_04.json"
    ]

    for target_file in sample_files:
        if os.path.exists(target_file):
            reconstruct_layout_from_file(target_file)
            print("\n")
        else:
            print(f"파일을 찾을 수 없음: {target_file}\n")