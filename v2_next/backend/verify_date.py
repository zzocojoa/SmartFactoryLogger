
import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\Users\user\AppData\Roaming\SmartFactoryLogger\logs\mes_data\mes_data.db")

def check_sqlite_date():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Checking SQLite Date Functions:")
    try:
        cursor.execute("SELECT date('now'), date('now', 'localtime')")
        row = cursor.fetchone()
        print(f"UTC Date: {row[0]}")
        print(f"Local Date: {row[1]}")
    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_sqlite_date()
