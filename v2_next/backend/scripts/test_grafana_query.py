import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"

def test_query():
    if not DB_PATH.exists():
        print(f"Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=== Testing Grafana Query Logic for 'Process Production Status' ===")
    
    # Query: Get breakdown by Process from the LATEST snapshot of 'proc_status'
    # Note: SQLite JSON syntax (->>) might depend on version, so using json_extract for compatibility
    sql = """
    WITH latest_snap AS (
        SELECT data_json 
        FROM raw_data 
        WHERE page_key = 'proc_status' 
        ORDER BY collected_at DESC 
        LIMIT 1
    )
    SELECT 
        json_extract(value, '$.공정') as process,
        COUNT(*) as count,
        SUM(CAST(REPLACE(IFNULL(json_extract(value, '$.수량'), '0'), ',', '') AS INTEGER)) as total_qty,
        SUM(CAST(REPLACE(IFNULL(json_extract(value, '$.중량'), '0'), ',', '') AS REAL)) as total_weight
    FROM latest_snap, json_each(latest_snap.data_json)
    GROUP BY process
    ORDER BY total_weight DESC
    """
    
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        print(f"{'Process':<20} | {'Count':<5} | {'Qty':<10} | {'Weight (kg)':<15}")
        print("-" * 60)
        
        for row in rows:
            print(f"{row['process']:<20} | {row['count']:<5} | {row['total_qty']:<10} | {row['total_weight']:<15,.1f}")
            
    except Exception as e:
        print(f"Query Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_query()
