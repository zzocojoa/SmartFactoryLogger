
import sqlite3
from pathlib import Path

# Path to the consolidated DB
DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def check_production_date(date_str):
    if not DB_PATH.exists():
        print(f"Error: DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        SUM(CAST(REPLACE(json_extract(value, '$.적합 중량'), ',', '') AS REAL)) as TotalWeight
    FROM raw_data, json_each(raw_data.data_json)
    WHERE page_key = 'rpt_press'
      AND json_extract(value, '$.일자') = ?
    """
    
    print(f"Querying Total Production for {date_str}...")
    try:
        cursor.execute(query, (date_str,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            print(f"Total Weight: {row[0]:,.1f} kg")
        else:
            print("No data found for this date.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_production_date("2026-01-16")
