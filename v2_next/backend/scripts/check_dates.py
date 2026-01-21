import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"
OUTPUT_FILE = Path(__file__).parent / "date_check.json"

def check_dates():
    if not DB_PATH.exists():
        print(f"Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    results = {}
    target_pages = ["proc_status", "proc_res_mct", "proc_res_cutting", "proc_res_heating"]

    try:
        for key in target_pages:
            results[key] = {}
            # Check LATEST snapshot only for now
            cursor.execute("SELECT data_json FROM raw_data WHERE page_key = ? ORDER BY collected_at DESC LIMIT 1", (key,))
            row = cursor.fetchone()
            if row and row['data_json']:
                try:
                    data = json.loads(row['data_json'])
                    dates = set()
                    date_field = None
                    
                    # Heuristic: Find first key containing "일자" or "date"
                    if data:
                        sample = data[0]
                        for k in sample.keys():
                            if "일자" in k or "Date" in k:
                                date_field = k
                                break
                    
                    if date_field:
                        results[key]["field"] = date_field
                        for item in data:
                            if date_field in item:
                                dates.add(item[date_field])
                        results[key]["dates"] = sorted(list(dates))
                    else:
                        results[key]["error"] = "No date field found"
                except:
                    pass

    except Exception as e:
        results["error"] = str(e)
    finally:
        conn.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Date check saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    check_dates()
