
import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def check_deduplicated_sum(date_str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Calculating Deduplicated Sum for {date_str}...")
    
    # DISTINCT Logic on (Factory, Weight, LOT, Product)
    query = """
    SELECT SUM(WeightRaw) FROM (
      SELECT DISTINCT 
        json_extract(value, '$.공장') as FactoryRaw,
        CAST(REPLACE(json_extract(value, '$.적합 중량'), ',', '') AS REAL) as WeightRaw,
        json_extract(value, '$.LOT') as LotNo,
        json_extract(value, '$.제품') as Product
      FROM raw_data, json_each(raw_data.data_json)
      WHERE page_key = 'rpt_press'
        AND json_extract(value, '$.일자') = ?
    )
    """
    
    try:
        cursor.execute(query, (date_str,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            print(f"Final Count: {row[0]:,.1f} kg")
        else:
            print("No data found.")
    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    check_deduplicated_sum("2026-01-14")
