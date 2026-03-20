
import os
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data")
TARGET_DIR = BASE_DIR / "merged_all"

# Define source roots in order (1 -> 2 -> 3)
SOURCES = [
    BASE_DIR / "1번" / "mes_data",
    BASE_DIR / "2번" / "mac_dist" / "mes_data",
    BASE_DIR / "3번" / "mac_dist" / "mes_data"
]

def merge_json_files():
    print(f"Starting JSON Merge...", flush=True)
    print(f"Target Directory: {TARGET_DIR}", flush=True)
    
    if TARGET_DIR.exists():
        print(f"Note: Target directory already exists. Merging into it.", flush=True)
    else:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        
    total_files = 0
    total_copied = 0
    
    for i, src_root in enumerate(SOURCES, 1):
        if not src_root.exists():
            print(f"[Warn] Source {i} not found: {src_root}", flush=True)
            continue
            
        print(f"[{i}/3] Scanning Source: {src_root}...", flush=True)
        
        # Walk through source directory
        for root, dirs, files in os.walk(src_root):
            # Calculate relative path to maintain structure
            rel_path = Path(root).relative_to(src_root)
            
            # Skip if it's the DB file or non-relevant folders
            if rel_path.name.startswith("."):
                continue
                
            target_subdir = TARGET_DIR / rel_path
            
            # Create target subdirectory
            if not target_subdir.exists():
                target_subdir.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                if not file.lower().endswith(".json"):
                    continue
                    
                src_file = Path(root) / file
                dst_file = target_subdir / file
                
                # Copy file
                try:
                    shutil.copy2(src_file, dst_file)
                    total_copied += 1
                except Exception as e:
                    print(f"[Error] Failed to copy {src_file}: {e}", flush=True)
                    
        print(f"   -> Finished processing Source {i}", flush=True)

    print(f"\n[Success] JSON Merge Complete!", flush=True)
    print(f"Total JSON files copied: {total_copied}", flush=True)
    print(f"Merged Data Location: {TARGET_DIR}", flush=True)

if __name__ == "__main__":
    merge_json_files()
