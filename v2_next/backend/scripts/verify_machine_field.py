import sqlite3
import json
import os
from pathlib import Path

APP_DATA_DIR = Path(os.getenv("APPDATA")) / "SmartFactoryLogger"
DB_PATH = APP_DATA_DIR / "logs" / "mes_data" / "mes_data.db"

def verify_factory_fields():
    if not DB_PATH.exists():
        print(f"Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    target_tables = [
        "proc_res_press",  # Extrusion (confirmed)
        "proc_res_cutting",
        "proc_res_heating",
        "proc_res_mct"
    ]

    print("=== Verification of Factory Field (생산공장) for Machine Breakdown ===")

    try:
        for key in target_tables:
            cursor.execute("SELECT data_json FROM raw_data WHERE page_key = ? ORDER BY collected_at DESC LIMIT 1", (key,))
            row = cursor.fetchone()
            if row and row['data_json']:
                try:
                    data = json.loads(row['data_json'])
                    if data:
                        sample = data[0]
                        # Check for "생산공장" or "공장"
                        factory_val = sample.get("생산공장") or sample.get("공장")
                        print(f"[{key}] Field found: {'Yes' if factory_val else 'No'}")
                        if factory_val:
                            print(f"  Sample Value: {factory_val}")
                        else:
                            print(f"  Keys available: {list(sample.keys())}")
                    else:
                        print(f"[{key}] No data rows")
                except:
                    print(f"[{key}] JSON Error")
            else:
                print(f"[{key}] Page not found")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_factory_fields()
