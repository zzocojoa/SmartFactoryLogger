
import json
from pathlib import Path

FILE_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\리포트\압출_일보\2026.json")

def validate_fix():
    if not FILE_PATH.exists():
        print(f"Error: {FILE_PATH} not found.")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = json.load(f)
        
    data = content.get('data', [])
    print(f"Total Records in 2026.json: {len(data)}")
    
    # 1. Search for Error String
    error_count = 0
    for row in data:
        for v in row.values():
            if isinstance(v, str) and "of" in v and "Pages" in v:
                error_count += 1
                
    if error_count > 0:
        print(f"FAIL: Found {error_count} records with pagination error string!")
    else:
        print("PASS: No pagination error strings found.")

    # 2. Sum for Jan 14
    target_date = "2026-01-14"
    jan14_rows = [r for r in data if r.get("일자") == target_date]
    print(f"Records for {target_date}: {len(jan14_rows)}")
    
    total_weight = 0.0
    for r in jan14_rows:
        try:
            w = float(r.get("적합 중량", "0").replace(",", ""))
            total_weight += w
        except:
            pass
            
    print(f"Total Weight for {target_date}: {total_weight:,.1f} kg")
    
    # Show factories to confirm multi-page
    factories = set(r.get("공장") for r in jan14_rows)
    print(f"Factories found: {factories}")

if __name__ == "__main__":
    validate_fix()
