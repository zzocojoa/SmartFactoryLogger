import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"

def show_extrusion():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get Extrusion data from proc_status
        sql = """
        WITH latest_snap AS (
            SELECT data_json 
            FROM raw_data 
            WHERE page_key = 'proc_status' 
            ORDER BY collected_at DESC 
            LIMIT 1
        )
        SELECT value
        FROM latest_snap, json_each(latest_snap.data_json)
        WHERE json_extract(value, '$.공정') LIKE '%압출%'
        LIMIT 2
        """
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        print("=== Extrusion Data Sample (from proc_status) ===")
        for row in rows:
            data = json.loads(row['value'])
            # Print key fields
            print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    show_extrusion()
