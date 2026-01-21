import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"
OUTPUT_FILE = Path(__file__).parent / "analysis_result.json"

def analyze_db():
    result = {"error": None, "tables": {}, "pages": []}
    
    if not DB_PATH.exists():
        result["error"] = f"Database not found at: {DB_PATH}"
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='raw_data'")
        schema = cursor.fetchone()
        result["tables"]["raw_data"] = schema['sql'] if schema else "Not Found"

        # 2. Page Keys
        cursor.execute("SELECT page_key, COUNT(*) as count, MAX(collected_at) as last_update FROM raw_data GROUP BY page_key")
        rows = cursor.fetchall()
        
        for row in rows:
            page_info = {
                "key": row["page_key"],
                "count": row["count"],
                "last_update": row["last_update"],
                "sample_keys": [],
                "sample_data": None
            }

            # 3. Sample
            cursor.execute("SELECT data_json FROM raw_data WHERE page_key = ? ORDER BY collected_at DESC LIMIT 1", (row["page_key"],))
            data_row = cursor.fetchone()
            if data_row and data_row["data_json"]:
                try:
                    data = json.loads(data_row["data_json"])
                    if isinstance(data, list) and len(data) > 0:
                        sample = data[0]
                        page_info["sample_keys"] = list(sample.keys())
                        # Store first 3 items for inspection
                        page_info["sample_data"] = {k: sample[k] for k in list(sample.keys())[:5]}
                except:
                    page_info["sample_error"] = "JSON Parse Error"
            
            result["pages"].append(page_info)

    except Exception as e:
        result["error"] = str(e)
    finally:
        conn.close()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Analysis saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    analyze_db()
