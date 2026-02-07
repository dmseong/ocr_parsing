import sys
import os
from pathlib import Path
import io
import json
from typing import Dict, List

# 프로젝트 루트를 path에 추가하여 모듈 임포트 허용
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
os.chdir(str(root_dir)) # 작업 디렉토리를 루트로 변경하여 상대 경로(sample_data_ocr) 보장

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 테스트 대상 파서
from parser import UnifiedOCRParser
from confidence_scorer import ConfidenceScorer

def load_sample_data(sample_dir: str = "sample_data_ocr") -> List[Dict]:
    """샘플 데이터 로드"""
    samples = []
    sample_path = Path(sample_dir)
    
    if not sample_path.exists():
        print(f"❌ 샘플 디렉토리를 찾을 수 없습니다: {sample_dir}")
        return samples
    
    for json_file in sorted(sample_path.glob("sample_*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                samples.append({
                    'name': json_file.stem,
                    'data': data
                })
        except Exception as e:
            print(f"⚠️ {json_file.name} 로드 실패: {e}")
    
    return samples

def test_hybrid_parser(samples: List[Dict]) -> List[Dict]:
    """통합 파서 (UnifiedOCRParser) 테스트"""
    print("\n" + "="*60)
    print("🔀 통합 파서 (UnifiedOCRParser) 테스트")
    print("="*60)
    
    parser = UnifiedOCRParser()
    
    results = []
    
    for sample in samples:
        result = parser.parse(sample['data'])
        result['_sample'] = sample['name']
        results.append(result)
        
        # 검수 필요 여부
        needs_review = result.get('_needs_review', False)
        priority = result.get('_review_priority', 'N/A')
        
        print(f"\n[{sample['name']}]")
        print(f"  날짜: {result.get('date')}")
        print(f"  차량: {result.get('vehicle_num')}")
        print(f"  총중량: {result.get('total_weight')}")
        print(f"  공차중량: {result.get('tare_weight')}")
        print(f"  실중량: {result.get('net_weight')}")
        print(f"  회사: {result.get('company')}")
        print(f"  발행처: {result.get('issuer')}")
        print(f"  품명: {result.get('product')}")
        print(f"  구분: {result.get('type')}")
        print(f"  전표번호: {result.get('ticket_id')}")
        print(f"  전화번호: {result.get('phone')}")
        print(f"  주소: {result.get('address')}")
        print(f"  GPS: {result.get('gps')}")
        print(f"  신뢰도: {result.get('_overall_confidence', 'N/A')}%")
        print(f"  검수 필요: {'⚠️ 예' if needs_review else '✅ 아니오'} ({priority})")
        
        # [DEBUG] 실패 시 텍스트 확인 (Noisy Sample etc)
        if result.get('date') is None and 'noisy' in sample['name']:
             # 간단히 텍스트만 추출해서 출력
             if 'pages' in sample['data'] and sample['data']['pages']:
                 words = sample['data']['pages'][0].get('words', [])
                 ft = " ".join(w.get('text', '') for w in words)
                 print(f"  [DEBUG FULLTEXT]: {ft[:100]}...")
    
    return results

def compare_results(hybrid_results: List[Dict]):
    """통계 분석"""
    print("\n" + "="*60)
    print("📊 하이브리드 파서 통계")
    print("="*60)
    
    if not hybrid_results:
        print("결과 없음")
        return

    # 필드별 추출 성공률
    fields = ['date', 'vehicle_num', 'total_weight', 'tare_weight', 
              'net_weight', 'company', 'issuer', 'product', 'type', 
              'ticket_id', 'phone', 'address', 'gps']
    
    print("\n필드별 추출 성공률:")
    print("-" * 50)
    print(f"{'필드':<15} {'성공률':>10}")
    print("-" * 50)
    
    for field in fields:
        count = sum(1 for r in hybrid_results if r.get(field))
        pct = f"{count}/{len(hybrid_results)}"
        print(f"{field:<15} {pct:>10}")
    
    # 중량 검증
    print("\n중량 방정식 검증 (Total = Tare + Net):")
    print("-" * 50)
    
    valid_count = 0
    total_count = 0
    
    for r in hybrid_results:
        total = r.get('total_weight')
        tare = r.get('tare_weight')
        net = r.get('net_weight')
        
        if total and tare and net:
            total_count += 1
            if abs(total - (tare + net)) <= 50:
                valid_count += 1
    
    pct = (valid_count / total_count * 100) if total_count > 0 else 0
    print(f"  검증 성공: {valid_count}/{total_count} ({pct:.1f}%)")
    
    # 신뢰도 통계
    print("\n신뢰도 통계:")
    print("-" * 50)
    
    confidences = [r.get('_overall_confidence', 0) for r in hybrid_results]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    
    print(f"  평균 신뢰도: {avg_conf:.1f}%")
    print(f"  검수 필요: {sum(1 for r in hybrid_results if r.get('_needs_review'))}건")

def main():
    """메인 테스트 함수"""
    print("="*60)
    print("🔬 OCR 파서 비교 테스트")
    print("="*60)
    
    # 샘플 로드
    samples = load_sample_data()
    
    if not samples:
        print("❌ 샘플 데이터가 없습니다.")
        return
    
    print(f"📁 {len(samples)}개 샘플 로드됨")
    
    # 통합 파서 테스트
    hybrid_results = test_hybrid_parser(samples)
    
    # 비교 및 통계
    compare_results(hybrid_results)
    
    # 결과를 JSON 파일로 저장
    with open('test_results.json', 'w', encoding='utf-8') as f:
        json.dump(hybrid_results, f, ensure_ascii=False, indent=2, default=str)
    
    print("\n" + "="*60)
    print("✅ 테스트 완료 및 test_results.json 저장됨")
    print("compare_answer.py를 실행해주세요!")
    print("="*60)

if __name__ == "__main__":
    main()
