import sqlite3
from pathlib import Path
import os
import sys
import json

# Setup DB Path
appdata = os.getenv("APPDATA")
db_path = Path(appdata) / "SmartFactoryLogger" / "logs" / "mes_data" / "mes_data.db"

print(f"Checking DB Content: {db_path}")

if not db_path.exists():
    print("DB not found.")
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
try:
    cursor = conn.cursor()
    # Get latest data for all_sign
    cursor.execute("""
        SELECT data_json, record_count
        FROM raw_data 
        WHERE page_key = 'all_sign'
        ORDER BY collected_at DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if row:
        raw_json = row["data_json"]
        data = json.loads(raw_json)
        print(f"Record Count in DB: {row['record_count']}")
        print(f"Data Length: {len(data)}")
        if len(data) > 0:
            print("First Record Keys:", list(data[0].keys()))
            print("First Record Sample:", data[0])
        else:
            print("Data is empty list []")
    else:
        print("No data found for 'all_sign'")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
