import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"
OUTPUT_FILE = Path(__file__).parent / "factory_values.json"

def check_values():
    if not DB_PATH.exists():
        print(f"Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        sql = """
        WITH latest_snap AS (
            SELECT data_json 
            FROM raw_data 
            WHERE page_key = 'proc_res_press' 
            ORDER BY collected_at DESC 
            LIMIT 1
        )
        SELECT DISTINCT json_extract(value, '$.생산공장') as factory
        FROM latest_snap, json_each(latest_snap.data_json)
        ORDER BY factory
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        factories = [row['factory'] for row in rows]
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(factories, f, ensure_ascii=False, indent=2)
            
        print(f"Saved {len(factories)} factory names to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_values()
