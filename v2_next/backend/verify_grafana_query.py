
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def verify_factory_group():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n[Testing Factory Aggregation]")
    # 1. Distinct Factory Names
    print("Distinct Factory Names:")
    try:
        cursor.execute("SELECT DISTINCT json_extract(value, '$.공장') FROM raw_data, json_each(raw_data.data_json) WHERE page_key='rpt_press' LIMIT 10")
        for row in cursor.fetchall():
            print(f" - {row[0]}")
    except Exception as e:
        print(f"Distinct Check Failed: {e}")

    # 2. Group by Factory + Total
    # Using simple UNION logic for verification
    query = """
    SELECT
      json_extract(value, '$.공장') as Factory,
      SUM(CAST(REPLACE(json_extract(value, '$.적합 중량'), ',', '') AS REAL)) as Weight
    FROM raw_data, json_each(raw_data.data_json)
    WHERE page_key = 'rpt_press'
    GROUP BY Factory
    UNION ALL
    SELECT
      'Total Production' as Factory,
      SUM(CAST(REPLACE(json_extract(value, '$.적합 중량'), ',', '') AS REAL)) as Weight
    FROM raw_data, json_each(raw_data.data_json)
    WHERE page_key = 'rpt_press'
    ORDER BY Weight DESC;
    """
    
    print("\nAggregation Results:")
    try:
        cursor.execute(query)
        for row in cursor.fetchall():
            print(f"{row[0]:<20} | {row[1]:<15}")
    except Exception as e:
        print(f"Query Failed: {e}")
        
    conn.close()

if __name__ == "__main__":
    verify_factory_group()
