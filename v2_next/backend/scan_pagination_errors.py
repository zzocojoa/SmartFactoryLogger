
import json
import os
from pathlib import Path

DATA_DIR = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data")


def scan_pagination_errors():
    print(f"Scanning {DATA_DIR} for pagination artifacts...")
    
    error_files = []
    scanned_count = 0
    
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            if not file.endswith(".json"):
                continue
                
            scanned_count += 1
            path = Path(root) / file
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for known pagination footprint strings
                # "of 3 Pages", "of 2 Pages", etc.
                # Or just the pattern specific to the error
                if "of " in content and "Pages" in content and "공장" in content:
                    # Parse to be sure
                    try:
                        data = json.loads(content)
                        if isinstance(data, dict) and 'data' in data:
                            last_item = data['data'][-1]
                            # Check strict condition
                            for key, val in last_item.items():
                                if isinstance(val, str) and "Pages" in val and "of" in val:
                                    error_files.append(str(path))
                                    break
                    except:
                        pass
                        
            except Exception as e:
                print(f"Could not read {path}: {e}")

    print(f"\nScan Complete. Scanned {scanned_count} files.")
    print(f"Found {len(error_files)} files with incomplete pagination errors.")
    
    if error_files:
        print("\nAffected Files:")
        for f in error_files[:20]:
            print(f" - {f}")
        if len(error_files) > 20:
            print(f"... and {len(error_files) - 20} more.")

if __name__ == "__main__":
    scan_pagination_errors()
