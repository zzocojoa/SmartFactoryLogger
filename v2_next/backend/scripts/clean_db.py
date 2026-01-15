
import sys
import os
import json
import sqlite3
import re
from pathlib import Path

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from backend import config

def main():
    db_path = config.APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"
    print(f"Connecting to DB: {db_path}")

    if not db_path.exists():
        print("Database not found.")
        return

    pollution_pattern = re.compile(r"^\s*\d+(\s+\d+)*\s+of\s+\d+\s+Pages?\s*$", re.IGNORECASE)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, page_key, data_json FROM raw_data")
        rows = cursor.fetchall()
        
        total_rows = len(rows)
        updated_count = 0
        total_records_removed = 0
        
        print(f"Scanning {total_rows} DB entries...")
        
        for row in rows:
            row_id = row["id"]
            try:
                data = json.loads(row["data_json"])
            except:
                continue
                
            if not isinstance(data, list):
                continue
                
            original_len = len(data)
            cleaned_data = []
            is_polluted = False
            
            for record in data:
                record_is_polluted = False
                for key, value in record.items():
                    val_str = str(value)
                    if "of" in val_str and "Pages" in val_str:
                         if pollution_pattern.search(val_str) or "1 2 3" in val_str:
                             record_is_polluted = True
                             break
                
                if not record_is_polluted:
                    cleaned_data.append(record)
                else:
                    is_polluted = True
            
            if is_polluted:
                new_len = len(cleaned_data)
                removed = original_len - new_len
                
                # Update DB
                new_json = json.dumps(cleaned_data, ensure_ascii=False)
                cursor.execute(
                    "UPDATE raw_data SET data_json = ?, record_count = ? WHERE id = ?",
                    (new_json, new_len, row_id)
                )
                updated_count += 1
                total_records_removed += removed
                
                # print(f"[UPDATE] ID {row_id} ({row['page_key']}): Removed {removed} records")
                
        conn.commit()
        
        if updated_count > 0:
            print("Vacuuming database...")
            conn.execute("VACUUM")
            
        print("\n" + "="*40)
        print("DB CLEANUP COMPLETE")
        print(f"Entries Scanned: {total_rows}")
        print(f"Entries Updated: {updated_count}")
        print(f"Total Pollution Records Removed: {total_records_removed}")
        print("="*40)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
