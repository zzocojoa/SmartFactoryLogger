from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from backend import config
from backend.MESSync import repository as mes_db
from backend.FacilityData.repository import logger_service

router = APIRouter()
logger = logging.getLogger("SmartFactoryLoggerV2.MES")

# --- Models ---
class AuthRequest(BaseModel):
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class DataResponse(BaseModel):
    page_key: str
    collected_at: str
    record_count: int
    data: List[Dict[str, Any]]

# --- API Endpoints ---

@router.post("/auth/verify", response_model=AuthResponse)
async def verify_password(payload: AuthRequest):
    """
    Verify MES Dashboard Password.
    Compares against config.MES_PASSWORD.
    """
    import configparser
    from pathlib import Path
    from backend.Configuration.service import get_config_snapshot

    # 1. Check if password check is skipped based on current config snapshot
    snapshot = get_config_snapshot()
    # Note: 'password_set' logic in snapshot might be helpful, but let's read file for absolute truth like app.py
    
    config_path_str = snapshot.get("config_path", "")
    config_path = Path(config_path_str) if config_path_str else None

    # If no config file, we can't verify, so assume open (or fail safe? app.py allows it)
    if not config_path or not config_path.exists():
        logger.warning("Config file not found during MES auth. Allowing access.")
        return {"success": True, "message": "No config file"}

    try:
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(str(config_path), encoding="utf-8-sig")
        
        stored_password = ""
        if parser.has_option("SETTINGS", "password"):
            stored_password = parser.get("SETTINGS", "password").strip()
            
        # If no password set in file -> OPEN ACCESS
        if not stored_password:
             return {"success": True, "message": "No password set"}
             
        # Verify
        if payload.password == stored_password:
            return {"success": True, "message": "Authenticated"}
        else:
            return {"success": False, "message": "Invalid Password"}
            
    except Exception as e:
        logger.error(f"Error reading config during MES auth: {e}")
        return {"success": False, "message": "Auth Error"}

from backend.MESSync.MESSync_Structure import MES_PAGES

class PageItem(BaseModel):
    key: str
    name: str     # Korean Name
    category: str # Korean Category

@router.get("/pages", response_model=List[PageItem])
async def get_pages():
    """
    Get list of available MES pages (that have data) with metadata.
    """
    try:
        # 1. Get available keys from DB
        db_keys = mes_db.get_available_pages()
        
        # 2. Map to metadata
        result = []
        for key in db_keys:
            info = MES_PAGES.get(key)
            if info:
                result.append({
                    "key": key,
                    "name": info["name"],
                    "category": info["category"]
                })
            else:
                # Fallback for keys not in registry
                result.append({
                    "key": key,
                    "name": key,
                    "category": "기타"
                })
        
        # Sort by Category then Name for consistent display
        result.sort(key=lambda x: (x["category"], x["name"]))
        
        return result
    except Exception as e:
        logger.error(f"Failed to fetch pages: {e}")
        raise HTTPException(status_code=500, detail="Database Error")

@router.get(
    "/data/{page_key}", 
    response_model=DataResponse, 
    response_model_exclude_none=True,
    summary="Get Paginated MES Data",
    description="Fetch historical data for a specific MES page by its key, supporting chunked payload streaming via offset-based pagination to prevent memory issues. Highly unrecommended to request more than 5000 records at once."
)
async def get_page_data(page_key: str, limit: int = 500, offset: int = 0):
    """
    Retrieves the most recent data for a specific MES page, merged from past collections.
    Supports limit and offset parameters to control payload size.
    """
    try:
        # Vercel Guidelines: Use async for DB/IO operations if possible
        import asyncio
        result = await asyncio.to_thread(mes_db.get_latest_data, page_key, limit, offset)
        
        if not result:
            raise HTTPException(status_code=404, detail="No data found for this page")
        
        return {
            "page_key": page_key,
            "collected_at": result.get("collected_at", "Unknown"), # Placeholder until fix
            "record_count": result.get("record_count", 0),
            "data": result.get("data", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch data for {page_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
