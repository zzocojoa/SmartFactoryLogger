import sqlite3
from pathlib import Path
import os
import sys

# Try to find the DB
appdata = os.getenv("APPDATA")
db_path = Path(appdata) / "SmartFactoryLogger" / "logs" / "mes_data" / "mes_data.db"

print(f"Checking DB: {db_path}")

if not db_path.exists():
    print("DB not found at default path. Checking local project...")
    # Try local project assumption
    # C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\backend\mes_bridge\constants.py says DATA_DIR = config.APP_DATA_DIR / "logs" / "mes_data"
    # So it should be there.
    sys.exit(1)

conn = sqlite3.connect(db_path)
try:
    rows = conn.execute("SELECT distinct page_key FROM raw_data").fetchall()
    print("Distinct Page Keys in DB:")
    for r in rows:
        print(f" - {r[0]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
