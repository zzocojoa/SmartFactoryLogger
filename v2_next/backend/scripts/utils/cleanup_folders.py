
import json
import shutil
import os
from pathlib import Path

# Paths
BACKEND_DIR = Path(__file__).parent
DATA_DIR = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data\merged_all")
PAGE_STRUCTURE_PATH = BACKEND_DIR / "mes_bridge" / "data" / "page_structures.json"

def cleanup_merged_folders():
    print("Starting Folder Cleanup...", flush=True)
    print(f"Base Directory: {DATA_DIR}", flush=True)

    # 1. Load Canonical Names
    with open(PAGE_STRUCTURE_PATH, 'r', encoding='utf-8') as f:
        structure = json.load(f)
        
    # Map: English Key -> Canonical Korean Name
    # Map: Normalized Name (no space) -> Canonical Name
    key_to_name = {}
    norm_name_to_name = {}
    
    for p in structure['pages']:
        key = p['key']
        name = p['name'] # Canonical Name (e.g., "절단가공 결과등록")
        category = p['category']
        
        key_to_name[key] = (category, name)
        
        # Also map "절단가공_결과등록" -> "절단가공 결과등록"
        norm_name = name.replace(" ", "_")
        if norm_name != name:
            norm_name_to_name[norm_name] = name

    # 2. Scan Departments (Categories)
    for category_dir in DATA_DIR.iterdir():
        if not category_dir.is_dir():
            continue
            
        print(f"\nScanning Category: {category_dir.name}", flush=True)
        
        # Scan Subdirectories (Page Folders)
        for page_folder in list(category_dir.iterdir()):
            if not page_folder.is_dir():
                continue
                
            folder_name = page_folder.name
            target_name = None
            
            # Case 1: English Key -> Move to Korean Name
            # We must scan all keys because folder might be "rpt_press"
            # But we don't have a direct reverse map from folder if it's unknown.
            # We check if folder_name is a known KEY.
            if folder_name in key_to_name:
                _, target_name = key_to_name[folder_name]
                
            # Case 2: Korean with Underscore -> Move to Canonical (Space)
            elif folder_name in norm_name_to_name:
                target_name = norm_name_to_name[folder_name]
                
            if target_name and target_name != folder_name:
                # Sanitize target name (remove invalid chars like /)
                safe_target_name = target_name.replace("/", "_").replace("\\", "_")
                target_folder = category_dir / safe_target_name
                
                print(f" [Move] '{folder_name}' -> '{safe_target_name}'", flush=True)
                
                # Create target if missing
                target_folder.mkdir(exist_ok=True)
                
                # Move contents
                files_moved = 0
                for item in page_folder.iterdir():
                    dst = target_folder / item.name
                    if dst.exists():
                        # If duplicate, replace or skip? User said "English folder should be empty".
                        # We overwrite to be safe (assuming merge logic).
                        try:
                            shutil.copy2(item, dst)
                            os.remove(item) # Remove source after copy
                        except Exception as e:
                            print(f"   Error moving {item.name}: {e}", flush=True)
                    else:
                        shutil.move(str(item), str(dst))
                    files_moved += 1
                
                print(f"   Moved {files_moved} files.", flush=True)
                
                # Remove empty source folder
                try:
                    page_folder.rmdir()
                    print(f"   Removed empty folder: {folder_name}", flush=True)
                except OSError:
                    print(f"   [Warn] Could not remove {folder_name} (not empty?)", flush=True)

    print("\n[Success] Cleanup Complete.", flush=True)

if __name__ == "__main__":
    cleanup_merged_folders()
