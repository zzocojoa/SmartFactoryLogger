
import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def check_dates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Latest 5 Dates in DB for rpt_press:")
    try:
        cursor.execute("SELECT DISTINCT json_extract(value, '$.일자') as d FROM raw_data, json_each(raw_data.data_json) WHERE page_key='rpt_press' ORDER BY d DESC LIMIT 5")
        for row in cursor.fetchall():
            print(f" - {row[0]}")
    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_dates()
