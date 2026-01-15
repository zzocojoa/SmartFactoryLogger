
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
    # DATA_DIR from mes_bridge constants logic
    data_dir = config.APP_DATA_DIR / "logs" / "mes_data"
    print(f"Scanning directory: {data_dir}")

    if not data_dir.exists():
        print("Data directory not found.")
        return

    pollution_pattern = re.compile(r"^\s*\d+(\s+\d+)*\s+of\s+\d+\s+Pages?\s*$", re.IGNORECASE)
    
    total_files = 0
    affected_files = 0
    total_rows = 0
    polluted_rows = 0

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
                
            local_polluted_count = 0
            
            for row in data:
                total_rows += 1
                # Check all values in the row for the pattern
                is_polluted = False
                
                # Check if the row looks like a pagination row
                # Often these end up with keys like "발주일자" having the value "1 2 3 ... of 36 Pages"
                # or sometimes the key itself might be weird if the header was messed up (less likely)
                
                for key, value in row.items():
                    val_str = str(value)
                    if "of" in val_str and "Pages" in val_str:
                         if pollution_pattern.search(val_str) or "1 2 3" in val_str:
                             is_polluted = True
                             break
                
                # Also check for empty rows (optional, but requested in collector update)
                if not is_polluted:
                    if all(not str(v).strip() or str(v).strip() == '-' for v in row.values()):
                        # We won't count empty rows as "polluted" for this specific report, 
                        # but we can optionally note them. Let's focus on pagination text first.
                        pass

                if is_polluted:
                    local_polluted_count += 1
            
            if local_polluted_count > 0:
                affected_files += 1
                polluted_rows += local_polluted_count
                print(f"[DETECTED] {file_path.name}: {local_polluted_count} polluted rows")
                # Print sample
                # print(f"  Sample: {data[-1]}") 

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print("\n" + "="*40)
    print(f"SCAN COMPLETE")
    print(f"Total Files Scanned: {total_files}")
    print(f"Affected Files: {affected_files}")
    print(f"Total Rows Checked: {total_rows}")
    print(f"Polluted Rows Found: {polluted_rows}")
    print("="*40)

if __name__ == "__main__":
    main()
