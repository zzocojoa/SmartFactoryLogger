import sqlite3
from pathlib import Path
import os
import sys
import json

appdata = os.getenv("APPDATA")
db_path = Path(appdata) / "SmartFactoryLogger" / "logs" / "mes_data" / "mes_data.db"

print(f"Checking DB: {db_path}")

if not db_path.exists():
    print("DB not found.")
    sys.exit(1)

conn = sqlite3.connect(db_path)
try:
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM raw_data WHERE page_key='all_sign'")
    count = cursor.fetchone()[0]
    print(f"Record count for 'all_sign' (검토/승인 처리): {count}")
    
    if count > 0:
        cursor.execute("SELECT collected_at, record_count FROM raw_data WHERE page_key='all_sign' ORDER BY collected_at DESC LIMIT 1")
        row = cursor.fetchone()
        print(f"Latest record: Collected At {row[0]}, Record Count {row[1]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
