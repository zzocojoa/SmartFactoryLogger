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
        conn.close()

def get_latest_data(page_key: str):
    """Get the latest data for a specific page"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data_json, record_count, hash_val 
            FROM raw_data 
            WHERE page_key = ? 
            ORDER BY collected_at DESC 
            LIMIT 1
        """, (page_key,))
        row = cursor.fetchone()
        
        if row:
            return {
                "data": json.loads(row["data_json"]),
                "record_count": row["record_count"],
                "hash_val": row["hash_val"]
            }
        return None
    finally:
        conn.close()
