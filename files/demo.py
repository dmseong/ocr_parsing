"""
배치 처리 데모 스크립트
여러 OCR JSON 파일을 한 번에 처리하여 CSV로 출력
"""

import json
import csv
import glob
from pathlib import Path
from typing import List, Dict
from universal_ocr_parser_v3 import UniversalOCRParser


def process_batch(input_dir: str, output_csv: str):
    """
    디렉토리의 모든 JSON 파일을 처리하여 CSV로 저장
    
    Args:
        input_dir: JSON 파일들이 있는 디렉토리
        output_csv: 출력 CSV 파일 경로
    """
    parser = UniversalOCRParser()
    
    # JSON 파일 찾기
    json_files = glob.glob(f"{input_dir}/*.json")
    
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return
    
    print(f"Found {len(json_files)} files")
    
    # 결과 저장
    results = []
    
    for i, file_path in enumerate(json_files, 1):
        print(f"[{i}/{len(json_files)}] Processing {Path(file_path).name}...", end=" ")
        
        try:
            # JSON 로드
            with open(file_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            
            # 파싱
            result = parser.parse(ocr_data)
            
            # 파일명 추가
            result['filename'] = Path(file_path).name
            
            results.append(result)
            print("✓ OK")
            
        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append({
                'filename': Path(file_path).name,
                'error': str(e)
            })
    
    # CSV로 저장
    if results:
        # 모든 필드명 수집
        all_fields = set()
        for result in results:
            all_fields.update(result.keys())
        
        # GPS는 별도 컬럼으로
        if 'gps' in all_fields:
            all_fields.remove('gps')
            all_fields.add('latitude')
            all_fields.add('longitude')
        
        fieldnames = ['filename'] + sorted([f for f in all_fields if f != 'filename'])
        
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # GPS 분리
                row = result.copy()
                if 'gps' in row and row['gps']:
                    row['latitude'] = row['gps'].get('latitude')
                    row['longitude'] = row['gps'].get('longitude')
                    del row['gps']
                elif 'gps' in row:
                    del row['gps']
                
                writer.writerow(row)
        
        print(f"\n✓ Saved to {output_csv}")
        print(f"  Total: {len(results)} records")
        print(f"  Success: {sum(1 for r in results if 'error' not in r)}")
        print(f"  Errors: {sum(1 for r in results if 'error' in r)}")


def process_single(json_path: str, output_json: str = None, pretty: bool = True):
    """
    단일 JSON 파일 처리
    
    Args:
        json_path: 입력 JSON 파일
        output_json: 출력 JSON 파일 (None이면 stdout)
        pretty: 보기 좋게 포맷팅
    """
    parser = UniversalOCRParser()
    
    # JSON 로드
    with open(json_path, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)
    
    # 파싱
    result = parser.parse(ocr_data)
    
    # 출력
    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2 if pretty else None)
        print(f"✓ Saved to {output_json}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2 if pretty else None))


def show_statistics(csv_path: str):
    """
    CSV 파일 통계 출력
    
    Args:
        csv_path: CSV 파일 경로
    """
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if not rows:
        print("No data")
        return
    
    total = len(rows)
    
    print(f"\n📊 Statistics ({total} records)")
    print("="*60)
    
    # 필드별 누락률
    for field in rows[0].keys():
        if field in ['filename', 'error']:
            continue
        
        missing = sum(1 for row in rows if not row.get(field))
        rate = (total - missing) / total * 100
        
        status = "✓" if rate >= 90 else "⚠" if rate >= 70 else "✗"
        print(f"{status} {field:20s}: {rate:5.1f}% ({total-missing}/{total})")
    
    # 중량 데이터 통계
    print("\n📦 Weight Statistics")
    print("-"*60)
    
    weights = {
        'total_weight': [],
        'tare_weight': [],
        'net_weight': []
    }
    
    for row in rows:
        for field in weights:
            if row.get(field):
                try:
                    weights[field].append(int(row[field]))
                except ValueError:
                    pass
    
    for field, values in weights.items():
        if values:
            print(f"{field:20s}: avg={sum(values)/len(values):,.0f}kg, "
                  f"min={min(values):,}kg, max={max(values):,}kg")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
Usage:
  # 배치 처리
  python demo.py batch <input_dir> <output.csv>
  
  # 단일 파일 처리
  python demo.py single <input.json> [output.json]
  
  # 통계 보기
  python demo.py stats <input.csv>

Examples:
  python demo.py batch /mnt/user-data/uploads results.csv
  python demo.py single sample_01.json result_01.json
  python demo.py stats results.csv
""")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "batch":
        if len(sys.argv) < 4:
            print("Usage: python demo.py batch <input_dir> <output.csv>")
            sys.exit(1)
        
        process_batch(sys.argv[2], sys.argv[3])
    
    elif command == "single":
        if len(sys.argv) < 3:
            print("Usage: python demo.py single <input.json> [output.json]")
            sys.exit(1)
        
        output = sys.argv[3] if len(sys.argv) > 3 else None
        process_single(sys.argv[2], output)
    
    elif command == "stats":
        if len(sys.argv) < 3:
            print("Usage: python demo.py stats <input.csv>")
            sys.exit(1)
        
        show_statistics(sys.argv[2])
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
