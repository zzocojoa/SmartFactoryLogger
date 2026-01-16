"""
MES Database Manager (SQLite)
- Handles raw data storage in SQLite
- Uses WAL (Write-Ahead Logging) mode for concurrency
- Schema: raw_data (id, page_key, collected_at, data_json, record_count)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from .constants import DATA_DIR
from .logger_config import get_logger

logger = get_logger("db_manager")

DB_PATH = DATA_DIR / "mes_data.db"

def init_db():
    """Initialize Database and Create Tables"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;") # Balance between safety and speed
        
        # Create Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_key TEXT NOT NULL,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_json TEXT,
                record_count INTEGER,
                hash_val TEXT  -- For deduplication/change detection
            );
        """)
        
        # Create Index
        conn.execute("CREATE INDEX IF NOT EXISTS idx_page_date ON raw_data(page_key, collected_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON raw_data(hash_val);")
        
        conn.commit()
        logger.info("Database initialized successfully", extra={"db_path": str(DB_PATH)})
    except Exception as e:
        logger.error("Failed to initialize database", exc_info=e)
        raise e
    finally:
        conn.close()

def get_connection():
    """Get SQLite Connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_page_data(page_key: str, data: list, record_count: int):
    """Save collected page data to DB"""
    if not data:
        return # Do not save empty data unless needed

    json_str = json.dumps(data, ensure_ascii=False)
    # Calculate hash to detect changes (deduplication logic can be added here)
    data_hash = str(hash(json.dumps(data[:5], sort_keys=True))) # Simple hash of first 5 records

    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Insert data
        cursor.execute("""
            INSERT INTO raw_data (page_key, collected_at, data_json, record_count, hash_val)
            VALUES (?, ?, ?, ?, ?)
        """, (page_key, datetime.now(), json_str, record_count, data_hash))
        
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to insert data for {page_key}", exc_info=e)
        raise e
    finally:
        cursor.close()
        conn.close()

def get_latest_data(page_key: str):
    """Get all historical data for a specific page (aggregated from all entries)"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Get all unique data entries for this page, ordered by collected_at DESC
        # We'll merge all data arrays together
        cursor.execute("""
            SELECT data_json, record_count, hash_val, collected_at
            FROM raw_data 
            WHERE page_key = ? 
            ORDER BY collected_at DESC
        """, (page_key,))
        rows = cursor.fetchall()
        
        if not rows:
            return None
        
        # Aggregate all data from all entries (deduplicated by content hash)
        all_data = []
        seen_hashes = set()
        latest_collected_at = None
        
        for row in rows:
            if latest_collected_at is None:
                latest_collected_at = row["collected_at"]
            
            try:
                data = json.loads(row["data_json"])
                # Add each record if not already seen (simple dedup by string repr)
                for record in data:
                    # Filter out effectively empty records (treat '.' as empty too)
                    if not any(str(v).strip() not in ['', '.'] for v in record.values() if v is not None):
                        continue

                    # Filter out pagination rows (e.g. "1 2 3 ... of 13 Pages") which were wrongly scraped
                    # Check if any value in the record looks like a pagination string
                    record_values = [str(v) for v in record.values() if v is not None]
                    if any("of" in v and "Pages" in v and any(c.isdigit() for c in v) for v in record_values):
                        continue

                    record_hash = hash(json.dumps(record, sort_keys=True, ensure_ascii=False))
                    if record_hash not in seen_hashes:
                        seen_hashes.add(record_hash)
                        all_data.append(record)
            except:
                pass
        
        return {
            "data": all_data,
            "record_count": len(all_data),
            "hash_val": str(hash(str(len(all_data)))),
            "collected_at": latest_collected_at
        }
    finally:
        cursor.close()
        conn.close()


def get_available_pages() -> list[str]:
    """Get list of all page keys that have data"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT page_key FROM raw_data ORDER BY page_key")
        rows = cursor.fetchall()
        return [row["page_key"] for row in rows]
    except Exception:
        return []
    finally:
        cursor.close()
        conn.close()
