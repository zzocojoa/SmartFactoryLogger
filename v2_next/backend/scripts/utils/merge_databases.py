
import sqlite3
from pathlib import Path
import os
import sys

# Force output encoding/buffering fix
sys.stdout.reconfigure(encoding='utf-8')

# Paths
BASE_DIR = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data")
TARGET_DB = BASE_DIR / "merged_mes_data.db"

def find_db_in_folder(root_folder_name):
    """Find mes_data.db recursively in the given folder"""
    root_path = BASE_DIR / root_folder_name
    if not root_path.exists():
        print(f"[Warn] Root folder not found: {root_path}", flush=True)
        return None
    
    # Try expected paths first
    candidates = [
        root_path / "mes_data" / "mes_data.db",
        root_path / "mac_dist" / "mes_data" / "mes_data.db",
        root_path / "mes_data.db"
    ]
    
    for c in candidates:
        if c.exists():
            return c
            
    # Fallback: Recursive search
    print(f"Searching recursively in {root_path}...", flush=True)
    for p in root_path.rglob("mes_data.db"):
        return p
        
    return None

def init_target_db():
    if TARGET_DB.exists():
        print(f"Removing existing target DB: {TARGET_DB}", flush=True)
        try:
            os.remove(TARGET_DB)
        except PermissionError:
            print("Error: Target DB is open. Close it and try again.", flush=True)
            sys.exit(1)
    
    conn = sqlite3.connect(TARGET_DB)
    # Schema from db_manager.py
    conn.execute("""
        CREATE TABLE raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_key TEXT NOT NULL,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_json TEXT,
            record_count INTEGER,
            hash_val TEXT
        );
    """)
    conn.execute("CREATE INDEX idx_page_date ON raw_data(page_key, collected_at);")
    conn.execute("CREATE INDEX idx_hash ON raw_data(hash_val);")
    conn.commit()
    return conn

def merge_databases():
    print(f"Starting Merge... Target: {TARGET_DB}", flush=True)
    
    # Identify sources
    sources = []
    for folder in ["1번", "2번", "3번"]:
        db_path = find_db_in_folder(folder)
        if db_path:
            sources.append(db_path)
            print(f"Found Source [{folder}]: {db_path}", flush=True)
        else:
            print(f"[Error] Could not find 'mes_data.db' in {folder}", flush=True)

    if not sources:
        print("No databases found to merge!", flush=True)
        return

    conn = init_target_db()
    cursor = conn.cursor()
    
    total_merged = 0
    
    for i, db_path in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] Merging from: {db_path}...", flush=True)
        
        # Attach source DB
        alias = f"src{i}"
        try:
            cursor.execute(f"ATTACH DATABASE ? AS {alias}", (str(db_path),))
            
            # Insert data
            cursor.execute(f"""
                INSERT INTO main.raw_data (page_key, collected_at, data_json, record_count, hash_val)
                SELECT page_key, collected_at, data_json, record_count, hash_val
                FROM {alias}.raw_data
                ORDER BY collected_at ASC 
            """)
            
            count = cursor.rowcount
            print(f"   -> Merged {count} records.", flush=True)
            total_merged += count
            
            conn.commit()
            cursor.execute(f"DETACH DATABASE {alias}")
        except Exception as e:
            print(f"Error merging {db_path}: {e}", flush=True)
        
    print(f"\n[Success] Total records merged: {total_merged}", flush=True)
    print(f"Merged DB saved to: {TARGET_DB}", flush=True)
    conn.close()

if __name__ == "__main__":
    merge_databases()
