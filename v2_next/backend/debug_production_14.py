
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def debug_Jan14():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("DEBUG: Raw Data for 2026-01-14 (rpt_press)")
    print(f"{'Factory':<15} | {'Weight (String)':<15} | {'Weight (Float)':<15}")
    print("-" * 50)
    
    query = """
    SELECT 
        json_extract(value, '$.공장'),
        json_extract(value, '$.적합 중량')
    FROM raw_data, json_each(raw_data.data_json)
    WHERE page_key = 'rpt_press'
      AND json_extract(value, '$.일자') = '2026-01-14'
    """
    
    total_val = 0.0
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        for factory, weight_str in rows:
            # Clean comma
            try:
                weight_val = float(weight_str.replace(',', ''))
            except (ValueError, AttributeError):
                weight_val = 0.0
                
            print(f"{factory:<15} | {weight_str:<15} | {weight_val:,.1f}")
            total_val += weight_val
            
        print("-" * 50)
        print(f"Total Sum: {total_val:,.1f}")
            
    except Exception as e:
        print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    debug_Jan14()
