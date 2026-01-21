import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"

def search_db(search_term):
    if not DB_PATH.exists():
        print(f"Database not found at: {DB_PATH}")
        return

    print(f"Searching for '{search_term}' in database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get all page keys
        cursor.execute("SELECT DISTINCT page_key FROM raw_data")
        page_keys = [row['page_key'] for row in cursor.fetchall()]
        
        found_counts = {}

        for key in page_keys:
            # We search in the latest snapshot first
            cursor.execute("SELECT data_json FROM raw_data WHERE page_key = ? ORDER BY collected_at DESC LIMIT 1", (key,))
            row = cursor.fetchone()
            if row and row['data_json']:
                try:
                    data = json.loads(row['data_json'])
                    count = 0
                    examples = []
                    
                    # Search recursively or just string dump
                    json_str = json.dumps(data, ensure_ascii=False)
                    if search_term in json_str:
                        # If found, try to find specific records
                        for item in data:
                            if search_term in str(item):
                                count += 1
                                if len(examples) < 3:
                                    examples.append(item)
                                    
                        if count > 0:
                            found_counts[key] = {"count": count, "examples": examples}
                except:
                    pass

        # Report
        if found_counts:
            print(f"\nTerm '{search_term}' found in:")
            for key, info in found_counts.items():
                print(f"Page: {key} ({info['count']} matches in latest snapshot)")
                for ex in info['examples']:
                    print(f"  - {str(ex)[:200]}...") # truncate
        else:
            print(f"Term '{search_term}' not found in any page.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    search_db("포장")
