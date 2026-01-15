import json
from pathlib import Path
import os
import sys

# Setup backend path
current_dir = Path(os.getcwd())
sys.path.append(str(current_dir))

from backend.mes_bridge.db_manager import save_page_data, init_db
from backend.mes_bridge.constants import DATA_DIR as APPDATA_DIR

# Use PROJECT mes_data directory (where historical data lives)
PROJECT_ROOT = Path(__file__).parent
PROJECT_MES_DATA = PROJECT_ROOT / "mes_data"

# Fallback to AppData if project dir doesn't exist
DATA_DIR = PROJECT_MES_DATA if PROJECT_MES_DATA.exists() else APPDATA_DIR

def sync_all():
    print(f"Syncing JSON data from {DATA_DIR} to DB...")
    if not DATA_DIR.exists():
        print("Data directory not found.")
        return

    # Walk through all json files
    count = 0
    for file_path in DATA_DIR.rglob("*.json"):
        if file_path.name == "changelog.jsonl":
            continue
            
        try:
            # Determine page key from folder name or file?
            # Folder structure: DATA_DIR / Category / FolderName / year.json
            # We need PAGE_KEY.
            # pages_registry has mapping.
            # But here we can't easily reverse map folder to key unless we load registry.
            # Let's load registry.
            pass
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Easier way: iterate registry
    from backend.mes_bridge.pages_registry import MES_PAGES
    
    for key, info in MES_PAGES.items():
        folder_name = info.get("folder_name", key)
        category = info.get("category", "기타")
        
        # Check current.json (Master) and year.json (History)
        target_dir = DATA_DIR / category / folder_name
        if not target_dir.exists():
            continue
            
        for json_file in target_dir.glob("*.json"):
            if json_file.name == "changelog.jsonl": continue
            
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    
                    # collector returns {key, name, data, ...} 
                    # If content has "data" list.
                    data = content.get("data", [])
                    record_count = content.get("record_count", len(data))
                    
                    if data:
                        # Save to DB
                        save_page_data(key, data, record_count)
                        print(f"Synced {key} ({json_file.name}): {record_count} records")
                        count += 1
            except Exception as e:
                print(f"Failed to sync {json_file}: {e}")

    print(f"Sync completed. Updated {count} files.")

if __name__ == "__main__":
    sync_all()
