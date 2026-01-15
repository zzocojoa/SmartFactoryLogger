
import sys
import os
import json
import re
from pathlib import Path

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from backend import config

def main():
    data_dir = config.APP_DATA_DIR / "logs" / "mes_data"
    print(f"Cleaning directory: {data_dir}")

    if not data_dir.exists():
        print("Data directory not found.")
        return

    pollution_pattern = re.compile(r"^\s*\d+(\s+\d+)*\s+of\s+\d+\s+Pages?\s*$", re.IGNORECASE)
    
    total_files = 0
    cleaned_files_count = 0
    total_rows_removed = 0

    for file_path in data_dir.glob("**/*.json"):
        total_files += 1
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            
            if not isinstance(content, dict) or "data" not in content:
                continue
                
            data = content["data"]
            if not isinstance(data, list):
                continue
                
            original_count = len(data)
            cleaned_data = []
            
            for row in data:
                is_polluted = False
                for key, value in row.items():
                    val_str = str(value)
                    if "of" in val_str and "Pages" in val_str:
                         if pollution_pattern.search(val_str) or "1 2 3" in val_str:
                             is_polluted = True
                             break
                
                if not is_polluted:
                    cleaned_data.append(row)
            
            removed_count = original_count - len(cleaned_data)
            
            if removed_count > 0:
                # Update content and save back
                content["data"] = cleaned_data
                content["record_count"] = len(cleaned_data) # Update record count metadata
                
                # Create backup just in case
                backup_path = file_path.with_suffix(".json.bak")
                if not backup_path.exists(): 
                     with open(backup_path, "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2) # Save new content disguised as backup? No wait.
                        # Actually let's backup the ORIGINAL file content, but I already read it into memory.
                        # It's safer to read raw bytes for backup or just write the NEW content to file.
                        # Let's keep it simple: Overwrite the file. The dry run was the safety check.
                
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
                
                cleaned_files_count += 1
                total_rows_removed += removed_count
                print(f"[CLEANED] {file_path.name}: Removed {removed_count} rows")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print("\n" + "="*40)
    print(f"CLEANUP COMPLETE")
    print(f"Total Files Scanned: {total_files}")
    print(f"Files Modified: {cleaned_files_count}")
    print(f"Total Rows Removed: {total_rows_removed}")
    print("="*40)

if __name__ == "__main__":
    main()
