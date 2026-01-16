"""
JSON to SQLite Migration Script for MES Data

Usage:
    python migrate_json_to_db.py [--data-dir PATH] [--dry-run]

This script scans for all *.json files in the MES data directory
and imports them into the mes_data.db SQLite database.
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def get_default_data_dir() -> Path:
    """Get the default MES data directory based on OS."""
    if os.name == "nt":  # Windows
        base = os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "SmartFactoryLogger" / "logs" / "mes_data"
    else:
        return Path.home() / ".config" / "SmartFactoryLogger" / "logs" / "mes_data"


def init_db(db_path: Path):
    """Initialize the database if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_key TEXT NOT NULL,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_json TEXT,
            record_count INTEGER,
            hash_val TEXT
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_page_date ON raw_data(page_key, collected_at);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON raw_data(hash_val);")
    conn.commit()
    conn.close()


def migrate_json_files(data_dir: Path, db_path: Path, dry_run: bool = False):
    """
    Scan all JSON files in data_dir and import them into the SQLite database.
    """
    json_files = list(data_dir.rglob("*.json"))
    
    # Exclude page_structures.json (config file)
    json_files = [f for f in json_files if f.name != "page_structures.json"]
    
    print(f"Found {len(json_files)} JSON files to migrate.")
    
    if not json_files:
        print("No JSON files found. Nothing to migrate.")
        return
    
    if dry_run:
        print("[DRY RUN] Would import the following files:")
        for f in json_files[:10]:
            print(f"  - {f}")
        if len(json_files) > 10:
            print(f"  ... and {len(json_files) - 10} more")
        return
    
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    imported = 0
    skipped = 0
    errors = 0
    
    for json_file in json_files:
        try:
            # Try multiple encodings
            content = None
            for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
                try:
                    content = json_file.read_text(encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                print(f"[ERROR] Could not decode: {json_file}")
                errors += 1
                continue
            
            data = json.loads(content)
            
            # Extract fields from JSON structure
            page_key = data.get("key")
            collected_at_str = data.get("collected_at")
            records = data.get("data", [])
            record_count = data.get("record_count", len(records))
            
            if not page_key:
                print(f"[SKIP] No page_key in: {json_file}")
                skipped += 1
                continue
            
            if not records:
                print(f"[SKIP] No data in: {json_file}")
                skipped += 1
                continue
            
            # Parse collected_at
            try:
                collected_at = datetime.fromisoformat(collected_at_str) if collected_at_str else datetime.now()
            except:
                collected_at = datetime.now()
            
            # Create data JSON string
            json_str = json.dumps(records, ensure_ascii=False)
            data_hash = str(hash(json.dumps(records[:5], sort_keys=True, ensure_ascii=False)))
            
            # Check for duplicates (same page_key and collected_at)
            cursor.execute(
                "SELECT id FROM raw_data WHERE page_key = ? AND collected_at = ?",
                (page_key, collected_at)
            )
            if cursor.fetchone():
                skipped += 1
                continue
            
            # Insert
            cursor.execute("""
                INSERT INTO raw_data (page_key, collected_at, data_json, record_count, hash_val)
                VALUES (?, ?, ?, ?, ?)
            """, (page_key, collected_at, json_str, record_count, data_hash))
            
            imported += 1
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON: {json_file} - {e}")
            errors += 1
        except Exception as e:
            print(f"[ERROR] {json_file} - {e}")
            errors += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n=== Migration Complete ===")
    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")
    print(f"  Database: {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Migrate MES JSON files to SQLite database")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to MES data directory (default: %%APPDATA%%\\SmartFactoryLogger\\logs\\mes_data)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without actually importing"
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir) if args.data_dir else get_default_data_dir()
    db_path = data_dir / "mes_data.db"
    
    print(f"Data Directory: {data_dir}")
    print(f"Database Path:  {db_path}")
    print()
    
    if not data_dir.exists():
        print(f"[ERROR] Data directory does not exist: {data_dir}")
        return 1
    
    migrate_json_files(data_dir, db_path, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    exit(main())
