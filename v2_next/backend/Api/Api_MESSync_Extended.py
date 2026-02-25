from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
from backend.FacilityData.FacilityData_DB_Logger import logger_service
from backend.MESSync.MESSync_Logic_Collector import load_page_structures, get_credentials, login
from backend.MESSync.MESSync_Logic_Scheduler import save_result, collect_page
from backend.MESSync.MESSync_Structure import MES_PAGES
from playwright.async_api import async_playwright
import logging

# Logger setup
logger = logging.getLogger("mes_sync")

router = APIRouter()

# Global Sync State
sync_state = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_date": None,
    "current_step": "idle", # idle, login, collecting, saving, done
    "status": "idle", # idle, running, completed, error
    "message": None,
    "start_time": None,
    "result": None  # {total_collected, elapsed_time, errors[]}
}

class ManualSyncRequest(BaseModel):
    from_date: str # YYYY-MM-DD
    to_date: str   # YYYY-MM-DD

async def run_sync_task(from_date: str, to_date: str):
    global sync_state
    sync_state["is_running"] = True
    sync_state["status"] = "running"
    sync_state["start_time"] = datetime.now().isoformat()
    sync_state["message"] = "Initializing..."
    
    try:
        start_dt = datetime.strptime(from_date, "%Y-%m-%d")
        end_dt = datetime.strptime(to_date, "%Y-%m-%d")
        delta = end_dt - start_dt
        days_count = delta.days + 1
        
        # Load Pages
        structures = load_page_structures()
        pages = structures["pages"]
        # Only extract daily data pages, ignore master data pages if possible or include all?
        # For now, include all enabled pages.
        
        sync_state["total"] = days_count * len(pages)
        sync_state["progress"] = 0
        sync_state["result"] = None
        errors_list = []
        
        user_id, password = get_credentials()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Login
            sync_state["current_step"] = "login"
            sync_state["message"] = "Logging in to MES..."
            if not await login(page, user_id, password):
                raise Exception("Login failed")
            
            sync_state["current_step"] = "collecting"
            
            for i in range(days_count):
                current_dt = start_dt + timedelta(days=i)
                date_str = current_dt.strftime("%Y-%m-%d")
                sync_state["current_date"] = date_str
                
                for page_info in pages:
                    sync_state["message"] = f"Collecting {page_info['name']} ({date_str})"
                    
                    try:
                        # Collect
                        # Note: collect_page takes (page, page_info, date_str, output_filename)
                        # We use date_str as filename base e.g. "2024-01-01.json"? 
                        # Or keep structure? Scheduler uses "today.json" or "recent.json".
                        # Here we should probably use "YYYY-MM-DD.json" to avoid overwriting today?
                        # But collector.py extract_historical_data uses year folder + year.json.
                        # Wait, collector logic is:
                        # Date Range Pages -> saved by YEAR (one big file per year) or daily?
                        # collector.py extract_historical_data saves "2024.json".
                        # But scheduler saves "today.json".
                        
                        # If we want to allow DAILY granularity sync, we should probably stick to
                        # the pattern: Data is stored in DB. JSON files are secondary/backup.
                        # DB storage handles daily records.
                        # So filename matters less for DB, but matters for file backup.
                        # Let's use "YYYY-MM-DD.json" for manual sync dumps.
                        
                        output_file = f"{date_str}.json"
                        result = await collect_page(page, page_info, date_str, output_file)
                        await save_result(page_info, result, output_file)
                        
                    except Exception as e:
                        error_msg = f"{page_info['key']} ({date_str}): {str(e)}"
                        errors_list.append(error_msg)
                        logger.error(f"Error collecting {page_info['key']} for {date_str}: {e}")
                    
                    sync_state["progress"] += 1
                    
            await browser.close()
            
        # Calculate elapsed time
        start_time = datetime.fromisoformat(sync_state["start_time"])
        elapsed = datetime.now() - start_time
        elapsed_str = str(elapsed).split('.')[0]  # HH:MM:SS format
        
        sync_state["current_step"] = "done"
        sync_state["status"] = "completed"
        sync_state["message"] = "Synchronization finished successfully."
        sync_state["result"] = {
            "total_collected": sync_state["progress"],
            "elapsed_time": elapsed_str,
            "errors": errors_list
        }
        
    except Exception as e:
        sync_state["status"] = "error"
        sync_state["message"] = str(e)
        logger.error(f"Sync task failed: {e}")
    finally:
        sync_state["is_running"] = False

@router.post("/manual")
async def start_manual_sync(request: ManualSyncRequest, background_tasks: BackgroundTasks):
    if sync_state["is_running"]:
        raise HTTPException(status_code=400, detail="Sync already in progress")
    
    background_tasks.add_task(run_sync_task, request.from_date, request.to_date)
    return {"status": "started", "message": "Manual sync started in background"}

@router.get("/status")
async def get_sync_status():
    return sync_state
