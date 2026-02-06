import sys
import json
import re

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_answer_md(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    samples = {}
    # Split by separator ---
    sections = re.split(r'\n---', content)
    
    for section in sections:
        name_match = re.search(r'## (sample_\d+(?:_\w+)?)\.json', section)
        if not name_match:
            continue
        
        sample_name = name_match.group(1)
        data = {}
        
        # Parse table rows more robustly
        lines = section.split('\n')
        for line in lines:
            if '|' not in line: continue
            parts = [p.strip() for p in line.split('|')]
            # Remove empty strings from split at start/end
            if parts[0] == '': parts = parts[1:]
            if parts and parts[-1] == '': parts = parts[:-1]
            
            if len(parts) < 2: continue
            
            field = parts[0]
            if field == '필드' or all(c in '- :' for c in field):
                continue
            
            value = parts[-1]
            if value == '-': value = None
            
            # Numeric fields
            if field in ['total_weight', 'tare_weight', 'net_weight']:
                try:
                    # Remove commas and convert to int
                    clean_val = str(value).replace(',', '')
                    value = int(clean_val)
                except:
                    pass
            
            data[field] = value
        
        samples[sample_name] = data
    return samples

def compare():
    try:
        with open('test_results.json', 'r', encoding='utf-8') as f:
            results = json.load(f)
    except FileNotFoundError:
        print("test_results.json not found.")
        return

    answers = parse_answer_md('sample_data_ocr/answer.md')
    
    report = []
    report.append(f"{'Sample':<25} | {'Field':<15} | {'Result':<20} | {'Answer':<20} | {'Status'}")
    report.append("-" * 95)
    
    total_fields = 0
    matches = 0
    
    for res in results:
        sample_name = res['_sample']
        if sample_name not in answers:
            continue
            
        answer = answers[sample_name]
        target_fields = ['date', 'vehicle_num', 'total_weight', 'tare_weight', 'net_weight', 'company', 'product', 'type', 'ticket_id', 'issuer']
        
        for field in target_fields:
            if field not in answer: continue
            
            res_val = res.get(field)
            ans_val = answer.get(field)
            
            def normalize(v):
                if v is None: return "None"
                # Remove spaces, parentheses, commas, colons, and periods, and convert to lower
                res = str(v).replace(" ", "").replace("(", "").replace(")", "").replace(",", "").replace(":", "").replace(".", "").lower()
                if res.startswith("supplier"): res = res[len("supplier"):]
                if res == "-" or not res: return "None"
                return res

            s_res = normalize(res_val)
            s_ans = normalize(ans_val)
            
            status = "✅" if s_res == s_ans else "❌"
            if status == "✅":
                matches += 1
            total_fields += 1
            
            report.append(f"{sample_name:<25} | {field:<15} | {str(res_val):<20} | {str(ans_val):<20} | {status}")

    report.append("-" * 95)
    rate = (matches / total_fields) * 100 if total_fields > 0 else 0
    report.append(f"Total Match Rate: {matches}/{total_fields} ({rate:.2f}%)")
    
    with open('comparison_report.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(report))
    print("Report saved to comparison_report.txt")
    print(f"Match Rate: {rate:.2f}%")

if __name__ == "__main__":
    compare()
