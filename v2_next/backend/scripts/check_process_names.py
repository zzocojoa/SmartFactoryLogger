import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"
OUTPUT_FILE = Path(__file__).parent / "process_names.json"

def check_names():
    if not DB_PATH.exists():
        print(f"Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get distinct process names from the latest snapshot of 'proc_status'
        sql = """
        WITH latest_snap AS (
            SELECT data_json 
            FROM raw_data 
            WHERE page_key = 'proc_status' 
            ORDER BY collected_at DESC 
            LIMIT 1
        )
        SELECT DISTINCT json_extract(value, '$.공정') as process
        FROM latest_snap, json_each(latest_snap.data_json)
        ORDER BY process
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        processes = [row['process'] for row in rows]
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(processes, f, ensure_ascii=False, indent=2)
            
        print(f"Saved {len(processes)} process names to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_names()
