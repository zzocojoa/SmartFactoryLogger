
import csv
import json
import sys
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# Setup paths to import backend modules as a package
BACKEND_DIR = Path(__file__).parent
V2_NEXT_DIR = BACKEND_DIR.parent
sys.path.append(str(V2_NEXT_DIR))

# Import backend modules
try:
    from backend.MESSync.MESSync_Logic_Collector import (
        login, 
        extract_table_data, 
        set_date_range, 
        get_all_pages_data,
        MES_BASE_URL
    )
    from backend.MESSync.MESSync_DB import save_page_data
    from backend.MESSync.MESSync_Config import get_credentials
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Valid Paths
CSV_PATH = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data\merged_error_report.csv")
TARGET_DB_PATH = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data\mes_data.db")
JSON_BASE_DIR = Path(r"C:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data\merged_all")
PAGE_STRUCTURE_PATH = BACKEND_DIR.parent / "MESSync" / "data" / "page_structures.json"

# Monkey-patch DB path
try:
    import backend.MESSync.MESSync_DB as db_manager
    db_manager.DB_PATH = TARGET_DB_PATH
except ImportError:
    pass

# CONSTANTS
EXTENDED_TIMEOUT = 90000  # 90 seconds
MAX_RETRIES = 3

def check_already_collected(page_key, target_date_str):
    """
    Check if data for this page and date was successfully collected RECENTLY.
    Strategy: Check DB for records collected in the last 24 hours that contain the date string.
    """
    try:
        conn = sqlite3.connect(TARGET_DB_PATH)
        cursor = conn.cursor()
        
        # Check records collected since yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            SELECT data_json 
            FROM raw_data 
            WHERE page_key = ? AND collected_at > ?
        """, (page_key, yesterday))
        
        rows = cursor.fetchall()
        
        for (json_str,) in rows:
            # Simple substring check: does the target date appear in the JSON?
            # e.g. "2024-05-15"
            # This is heuristic but highly effective for this specific task.
            if target_date_str in json_str:
                return True
                
        return False
    except Exception as e:
        # If DB check fails, assume not done
        return False
    finally:
        if 'conn' in locals():
            conn.close()

async def extract_specific_date(page, page_info, target_date_str):
    """Extract data for a specific date (Single Day)"""
    url = f"{MES_BASE_URL}{page_info['url']}"
    
    try:
        print(f" -> Navigating to {page_info['name']}...", end="", flush=True)
        await page.goto(url, timeout=EXTENDED_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=EXTENDED_TIMEOUT)
        
        # Check table existence logic
        if not page_info.get("has_table", True):
             pass

        # Filter Setup
        filter_type = page_info.get("filter_type")
        filter_fields = page_info.get("filter_fields", {})
        
        if filter_type == "date_range":
            await set_date_range(page, target_date_str, target_date_str, filter_fields)
            
        elif filter_type == "year":
            year = target_date_str.split("-")[0]
            year_id = filter_fields.get("year_select", "")
            if year_id:
                await page.select_option(f"#{year_id}", year)
                await page.wait_for_load_state("networkidle", timeout=30000)
        
        # Extract
        table_id = page_info.get("table_id")
        if not table_id:
            print(" [Skip: No Table ID]", flush=True)
            return []
            
        data = await get_all_pages_data(page, table_id)
        print(f" [OK: {len(data)} records]", flush=True)
        return data

    except Exception as e:
        print(f" [Error: {e}]", flush=True)
        return None

def save_to_json_file(page_info, date_str, data):
    """Save data to JSON in merged_all structure"""
    if not data:
        return
        
    year = date_str.split("-")[0]
    category = page_info.get("category", "Uncategorized")
    page_name = page_info.get("name")
    
    target_dir = JSON_BASE_DIR / category / page_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{year}.json"
    
    existing_data = []
    if target_file.exists():
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if isinstance(content, list):
                    existing_data = content
        except:
            pass

    existing_data.extend(data)
    
    with open(target_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

async def retry_failed_collections():
    print(f"Starting Smart Retry Process (Skipping Successes)...", flush=True)
    print(f"Target DB: {TARGET_DB_PATH}", flush=True)
    
    # 1. Load Mappings
    with open(PAGE_STRUCTURE_PATH, 'r', encoding='utf-8') as f:
        structure = json.load(f)
    name_to_info = { p['name']: p for p in structure['pages'] }
    
    # 2. Load CSV Errors
    tasks = []
    if not CSV_PATH.exists():
        return

    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get('Date')
            page_name = row.get('Page')
            if date_str and page_name:
                page_info = name_to_info.get(page_name)
                if page_info:
                    tasks.append((date_str, page_info))

    print(f"Found {len(tasks)} total tasks in error log.", flush=True)
    
    # FILTER DONE TASKS
    pending_tasks = []
    for date_str, page_info in tasks:
        if check_already_collected(page_info['key'], date_str):
            # Already done recently
            continue
        pending_tasks.append((date_str, page_info))
        
    print(f"Filtered: {len(tasks) - len(pending_tasks)} succeeded previously.", flush=True)
    print(f"Pending: {len(pending_tasks)} tasks to retry.", flush=True)
    
    if not pending_tasks:
        print("All tasks verified as complete! Nothing to do.")
        return

    # 3. Browser Setup
    user_id, password = get_credentials()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        if not await login(page, user_id, password):
            return
            
        # 4. Process Pending Tasks
        success_count = 0
        pending_tasks.sort(key=lambda x: (x[1]['key'], x[0]))
        
        for i, (date_str, page_info) in enumerate(pending_tasks, 1):
            print(f"[{i}/{len(pending_tasks)}] Processing {page_info['name']} ({date_str})...", end="", flush=True)
            
            # Retry Loop
            data = None
            for attempt in range(1, MAX_RETRIES + 1):
                if attempt > 1:
                    print(f" [Retry {attempt}]...", end="", flush=True)
                
                data = await extract_specific_date(page, page_info, date_str)
                
                if data is not None: 
                    break
                await asyncio.sleep(2)

            if data:
                save_page_data(page_info['key'], data, len(data))
                save_to_json_file(page_info, date_str, data)
                success_count += 1
            else:
                print(f" [Failed after {MAX_RETRIES} attempts]", flush=True)
            
            await asyncio.sleep(0.5)
            
        print(f"\n[Success] Finished. Fixed {success_count}/{len(pending_tasks)} pending items.", flush=True)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(retry_failed_collections())
