
import json

def sum_json_file():
    path = r"c:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data\리포트\압출 일보\2026-01-14.json"
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    total = 0.0
    print("Items in JSON:")
    for item in data['data']:
        try:
            w_str = item.get("적합 중량", "0").replace(",", "")
            w = float(w_str)
            print(f" + {w}")
            total += w
        except:
            print(f" [Skip] {item}")
            
    print(f"Total: {total:,.1f}")

if __name__ == "__main__":
    sum_json_file()
