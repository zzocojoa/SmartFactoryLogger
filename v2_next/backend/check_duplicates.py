
import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def check_duplicate_rows():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Checking for multiple DB rows containing 2026-01-14 data:")
    query = """
    SELECT id, collected_at, length(data_json)
    FROM raw_data
    WHERE page_key = 'rpt_press'
      AND data_json LIKE '%2026-01-14%'
    """
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        for r in rows:
            print(f"ID: {r[0]}, Collected: {r[1]}, Bytes: {r[2]}")
    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_duplicate_rows()
