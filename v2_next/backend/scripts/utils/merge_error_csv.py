
import csv
import glob
from pathlib import Path
import os

# Paths
BASE_DIR = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data")
TARGET_FILE = BASE_DIR / "merged_error_report.csv"

# Source folders to inspect
SOURCES = [
    ("2번", BASE_DIR / "2번" / "mac_dist"),
    ("3번", BASE_DIR / "3번" / "mac_dist")
]

def merge_csv_files():
    print(f"Starting Error Log Merge...", flush=True)
    
    all_rows = []
    headers = ["Source_Folder", "Date", "Page", "Error Message", "Timestamp"]
    
    total_files = 0
    total_rows = 0
    
    for label, folder in SOURCES:
        if not folder.exists():
            print(f"[Warn] Folder not found: {folder}", flush=True)
            continue
            
        # Find all error_report_*.csv files using glob
        csv_files = list(folder.glob("error_report_*.csv"))
        print(f"[{label}] Found {len(csv_files)} error report files in {folder.name}", flush=True)
        
        for csv_path in csv_files:
            total_files += 1
            try:
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    
                    # Verify headers match expectation somewhat
                    # Expected: Date,Page,Error Message,Timestamp
                    
                    for row in reader:
                        # Add Source identifier
                        merged_row = {
                            "Source_Folder": label,
                            "Date": row.get("Date", ""),
                            "Page": row.get("Page", ""),
                            "Error Message": row.get("Error Message", ""),
                            "Timestamp": row.get("Timestamp", "")
                        }
                        all_rows.append(merged_row)
                        total_rows += 1
                        
            except Exception as e:
                print(f"[Error] Failed to read {csv_path.name}: {e}", flush=True)

    # Write merged CSV
    try:
        with open(TARGET_FILE, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_rows)
            
        print(f"\n[Success] Merged {total_files} files with {total_rows} rows.", flush=True)
        print(f"Output: {TARGET_FILE}", flush=True)
        
    except Exception as e:
        print(f"[Error] Failed to write target file: {e}", flush=True)

if __name__ == "__main__":
    merge_csv_files()
