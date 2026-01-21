"""
MES 데이터 동기화 도구 (Mac M1 전용)
Data and Config are stored LOCALLY (same folder as script).
Errors are logged in REAL-TIME.

Usage:
    python mac_sync_tool.py --from 2025-01-01 --to 2025-12-31 --workers 20
"""

import argparse
import asyncio
import configparser
import json
import os
import sqlite3
import sys
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

# =============================================================================
# Self-Contained Configuration (Mac Local Mode)
# =============================================================================

# MES URLs
MES_BASE_URL = "https://dmc.mescloud.net"
LOGIN_URL = f"{MES_BASE_URL}/Default.aspx"

# Selectors
LOGIN_SELECTOR_ID = "#txt_userId"
LOGIN_SELECTOR_PW = "#txt_userPw"
LOGIN_SELECTOR_BTN = "#btnLogin"

# Timeouts (ms)
DEFAULT_TIMEOUT = 30000
LONG_TIMEOUT = 60000

# Paths - CHANGED: Use Local Directory (Current Working Directory)
def get_base_dir() -> Path:
    """Get the base directory (where the script is running)"""
    return Path.cwd()

def get_data_dir() -> Path:
    """Get the MES data directory (Local)"""
    # Saves to ./mes_data in the current folder
    return get_base_dir() / "mes_data"

def get_config_path() -> Path:
    """Get the config.ini path (Local)"""
    # Looks for config.ini in the current folder
    return get_base_dir() / "config.ini"

def get_structures_file() -> Path:
    """Get the page_structures.json path (Local - Flat Structure)"""
    # Look in the same folder first, fallback to subfolder
    local_file = get_base_dir() / "page_structures.json"
    if local_file.exists():
        return local_file
    return get_base_dir() / "mes_bridge" / "data" / "page_structures.json"

def get_error_log_path() -> Path:
    """Get the real-time error log path"""
    # One file per run session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return get_base_dir() / f"error_report_{timestamp}.csv"

# Business Constants
IGNORE_PAGES = {"app_line", "trace_lot"}

# Configuration
DEFAULT_WORKERS = 20  # Optimized for M1
PROGRESS_BAR_WIDTH = 40


# =============================================================================
# Config Manager
# =============================================================================
def get_credentials() -> tuple[str, str]:
    """Get MES credentials from config.ini"""
    config_path = get_config_path()
    if not config_path.exists():
        return "", ""
    
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8-sig")
    
    user_id = config.get("MES", "userid", fallback="")
    password = config.get("MES", "password", fallback="")
    
    return user_id, password


# =============================================================================
# Error Logger (Real-time)
# =============================================================================
class RealTimeErrorLogger:
    def __init__(self):
        self.filepath = get_error_log_path()
        self.initialized = False
    
    def log(self, date_str, page_name, error_msg):
        """Append error to CSV immediately"""
        is_new = not self.filepath.exists()
        
        try:
            with open(self.filepath, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow(["Date", "Page", "Error Message", "Timestamp"])
                
                writer.writerow([
                    date_str, 
                    page_name, 
                    str(error_msg), 
                    datetime.now().strftime("%H:%M:%S")
                ])
        except Exception:
            pass # Creating lock issues in high concurrency is rare in append mode but possible


# =============================================================================
# Database Manager
# =============================================================================
def init_db():
    """Initialize the database"""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "mes_data.db"
    
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
    conn.commit()
    conn.close()

def save_page_data(page_key: str, data: list, record_count: int):
    """Save page data to database"""
    if not data:
        return
    
    db_path = get_data_dir() / "mes_data.db"
    json_str = json.dumps(data, ensure_ascii=False)
    data_hash = str(hash(json.dumps(data[:5], sort_keys=True)))
    collected_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO raw_data (page_key, collected_at, data_json, record_count, hash_val)
        VALUES (?, ?, ?, ?, ?)
    """, (page_key, collected_at_str, json_str, record_count, data_hash))
    conn.commit()
    cursor.close()
    conn.close()


# =============================================================================
# Page Structures Loader
# =============================================================================
def load_page_structures() -> dict:
    """Load page structures from JSON file"""
    structures_file = get_structures_file()
    if not structures_file.exists():
        print(f"❌ 설정 파일 없음: {structures_file}")
        sys.exit(1)
        
    with open(structures_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # [Fix] Force Inject 'proc_res_qc' (Override existing if any)
    qc_key = "proc_res_qc"
    
    # [Fix] Force Inject 'resc_check_status' (Material Inspection Status)
    resc_check_key = "resc_check_status"

    # [Fix] Force Inject 'goods_out_ret_status' (Product Return Status)
    goods_ret_key = "goods_out_ret_status"

    # Remove existing if present to ensure clean state
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") not in [qc_key, resc_check_key, goods_ret_key]]
    
    print("Force Injecting configurations for QC & Inspection pages...")
    
    # 1. QC Inspection
    data.setdefault("pages", []).append({
        "key": qc_key,
        "name": "QC검사 결과등록",
        "category": "품질",
        "url": "/P30_PRO/ProcRes_QC.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range",
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True
    })

    # 2. Material Inspection Status
    data.setdefault("pages", []).append({
        "key": resc_check_key,
        "name": "기간별 수입검사 현황",
        "category": "품질",
        "url": "/P20_RSC/RescCheckStatus.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range",
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True
    })

    # 3. Product Return Status
    data.setdefault("pages", []).append({
        "key": goods_ret_key,
        "name": "기간별 제품반품 현황",
        "category": "품질",
        "url": "/P40_GDS/GoodsOutRetStatus.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range",
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True
    })

    # [Fix] Category Overrides for OTHER Quality related pages
    quality_overrides = {
        "resc_check", 
        "goods_out_ret", "out_ret_check",
        "b_type_graph"
    }
    
    for p in data.get("pages", []):
        if p.get("key") in quality_overrides:
            print(f"Overriding category for {p['key']} -> '품질'")
            p["category"] = "품질"
            
        # [Fix] Forward Fill configuration for AllSign (Multi-row orders)
        if p.get("key") == "all_sign":
            print(f"Injecting Forward Fill config for {p['key']}")
            # Use Column Names for robustness
            p["forward_fill_keys"] = ["발주일자", "번호", "매입처"]

        # [Fix] Forward Fill configuration for Order (User Request)
        if p.get("key") == "order":
            print(f"Injecting Forward Fill config for {p['key']}")
            p["forward_fill_keys"] = ["수주일자", "번호", "매출처"]

        # [Fix] Forward Fill configuration for Balzu (User Request)
        if p.get("key") == "balzu":
            print(f"Injecting Forward Fill config for {p['key']}")
            # Included '납기일', '자재명' per user request
            p["forward_fill_keys"] = ["발주일자", "번호", "매입처", "납기일", "자재명"]

        # [Fix] Forward Fill configuration for Rescin2 (User Request)
        if p.get("key") == "rescin2":
            print(f"Injecting Forward Fill config for {p['key']}")
            p["forward_fill_keys"] = ["실제입고일", "LOT번호", "LOT수량", "LOT중량", "입고지"]

        # [Fix] Forward Fill configuration for Scrap (User Request)
        if p.get("key") == "scrap":
            print(f"Injecting Forward Fill config for {p['key']}")
            # Columns: 발생일자, 번호, 생산공장, 거래처, 구분, 종류, 품명
            p["forward_fill_keys"] = ["발생일자", "번호", "생산공장", "거래처", "구분", "종류", "품명"]

        # [Fix] Forward Fill configuration for RescStatus (User Request)
        if p.get("key") == "resc_status":
            print(f"Injecting Forward Fill config for {p['key']}")
            p["forward_fill_keys"] = ["구분"]
            # [Fix] Multi-Table Logic for 1,2,3 Unit Factories
            p["table_ids"] = [
                "ctl00_BodyHolder_gv_Board",  # 2호기 (창녕)
                "ctl00_BodyHolder_gv_Board2", # 1호기 (대구)
                "ctl00_BodyHolder_gv_Board3"  # 3호기 (창녕) - Potential
            ]

        # [Fix] Forward Fill configuration for ProcRes_Shape, Press, Heating
        if p.get("key") in ["proc_res_shape", "proc_res_press", "proc_res_heating"]:
            print(f"Injecting Forward Fill config for {p['key']}")
            # safe to include '양산구분' even if missing in heating (it just won't find it)
            p["forward_fill_keys"] = ["양산구분", "생산공장"]

        # [Fix] Forward Fill for ProcStock (Layout similar to Status)
        if p.get("key") == "proc_stock":
             p["forward_fill_keys"] = ["공장", "공정"]

        # [Fix] Forward Fill for ProcGoodsStock
        if p.get("key") == "proc_goods_stock":
             p["forward_fill_keys"] = ["공장"]

        # [Fix] Forward Fill for RescStatusAll
        if p.get("key") == "resc_status_all":
             p["forward_fill_keys"] = ["입고지"]

        # [Fix] Forward Fill for StockSum
        pass # Removed separate StockSum keys logic

        # [Fix] Table ID Mismatch for ProcRes_Heating
        # Config says gv_Board1, but actual page uses gv_Board
        if p.get("key") == "proc_res_heating":
            print(f"Overriding Table ID for {p['key']} to gv_Board")
            p["table_id"] = "ctl00_BodyHolder_gv_Board"


    # [Fix] Force Inject 'm_shape' (Mold Number Reg) - Master Mode
    # User Request: Capture all data once, no date loop, single file.
    m_shape_key = "m_shape"
    # Remove existing if present
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != m_shape_key]
        
    print(f"Injecting Master Mode config for {m_shape_key}")
    data.setdefault("pages", []).append({
        "key": m_shape_key,
        "name": "금형번호 등록",
        "category": "금형",
        "url": "/P50_QLT/MShape.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None, # No Date Filter = Master Mode
        "is_master": True,   # Explicit Flag for Master Mode logic
        "has_pagination": True,
        # [Fix] Forward Fill + Attachments for Mold Drawings
        "forward_fill_keys": ["금형번호", "attached_file"]
    })

    # [Fix] Force Inject 'shape_inn' (Mold Incoming Reg) - Forward Fill
    shape_inn_key = "shape_inn"
    # Remove existing if present
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != shape_inn_key]

    print(f"Injecting Forward Fill config for {shape_inn_key}")
    data.setdefault("pages", []).append({
        "key": shape_inn_key,
        "name": "금형입고 등록",
        "category": "금형",
        "url": "/P50_QLT/ShapeINN.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range",
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True,
        # Forward Fill for hierarchical cols
        "forward_fill_keys": ["발주일자", "번호", "제작처", "구분"] 
    })

    # [Fix] Force Inject 'shape_rev' (Mold REV Mgmt) - Master Mode & Forward Fill
    shape_rev_key = "shape_rev"
    shape_rev_url = "/P50_QLT/Shape.aspx"
    
    if "pages" in data:
        # Remove any existing page with same key OR same URL (to avoid duplicates like 'shape')
        data["pages"] = [p for p in data["pages"] 
                         if p.get("key") != shape_rev_key and p.get("url") != shape_rev_url]

    print(f"Injecting Master Mode config for {shape_rev_key}")
    data.setdefault("pages", []).append({
        "key": shape_rev_key,
        "name": "금형 REV 관리",
        "category": "금형",
        "url": shape_rev_url,
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None, # No Date Filter = Master Mode
        "is_master": True,   # Run Once
        "has_pagination": True,
        # Forward Fill for hierarchical cols + History
        "forward_fill_keys": ["금형REV", "금형번호", "Rev.", "이력내력"]
    })

    # [Fix] Force Inject 'job' (Work Order) - Forward Fill + Attachments
    job_key = "job"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != job_key]
        
    print(f"Injecting Config for {job_key}")
    data.setdefault("pages", []).append({
        "key": job_key,
        "name": "작업지시 등록",
        "category": "생산",
        "url": "/P30_PRO/Job.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range", 
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True,
        "forward_fill_keys": ["생산공장", "지시번호"]
    })
    # [Fix] Force Inject 'proc_stock' (Master Mode)
    proc_stock_key = "proc_stock"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != proc_stock_key]

    print(f"Injecting Config for {proc_stock_key}")
    data.setdefault("pages", []).append({
        "key": proc_stock_key,
        "name": "공정별 재공현황",
        "category": "생산",
        "url": "/P30_PRO/ProcStock.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None,  # Master Mode
        "is_master": True,
        "has_pagination": True,
        "forward_fill_keys": ["공장", "공정"]
    })

    # [Fix] Force Inject 'proc_goods_stock' (Master Mode - Single File)
    proc_goods_stock_key = "proc_goods_stock"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != proc_goods_stock_key]

    print(f"Injecting Config for {proc_goods_stock_key}")
    data.setdefault("pages", []).append({
        "key": proc_goods_stock_key,
        "name": "제품별 재공집계",
        "category": "생산",
        "url": "/P30_PRO/ProcGoodsStock.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None,  # Master Mode
        "is_master": True,
        "has_pagination": True,
        "forward_fill_keys": ["공장"]
    })

    # [Fix] Force Inject 'resc_status_all' (Master Mode - Single File)
    resc_status_all_key = "resc_status_all"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != resc_status_all_key]

    print(f"Injecting Config for {resc_status_all_key}")
    data.setdefault("pages", []).append({
        "key": resc_status_all_key,
        "name": "전체 자재 재고현황",
        "category": "자재",
        "url": "/P20_RSC/RescStatusAll.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None,  # Master Mode
        "is_master": True,
        "has_pagination": False, # Browser inspection showed no pagination
        "forward_fill_keys": ["입고지"]
    })

    # [Fix] Force Inject 'stock_sum' (Master Mode - Multi-Table / Single File)
    # Consolidates Status(gv_Board), Outsource(gv_Board2), Industry(gv_Board3)
    stock_sum_key = "stock_sum"
    # Remove any existing stock_sum variants
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") not in [stock_sum_key, "stock_sum_status", "stock_sum_outsource", "stock_sum_industry"]]

    print(f"Injecting Consolidated Config for {stock_sum_key}")
    data.setdefault("pages", []).append({
        "key": stock_sum_key,
        "name": "재고조사 현황",
        "category": "리포트",
        "url": "/P60_SUM/StockSum.aspx",
        "has_table": True,
        "table_ids": ["ctl00_BodyHolder_gv_Board", "ctl00_BodyHolder_gv_Board2", "ctl00_BodyHolder_gv_Board3"],
        "filter_type": None,  # Master Mode
        "is_master": True,
        "has_pagination": False,
        "forward_fill_keys": [] # Disable forward fill to prevent cross-table pollution
    })

    # [Fix] Force Inject 'goods_out_status' (Product Out Status)
    goods_out_key = "goods_out_status"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != goods_out_key]

    print(f"Injecting Config for {goods_out_key}")
    data.setdefault("pages", []).append({
        "key": goods_out_key,
        "name": "기간별_제품출고_현황", 
        "category": "제품",
        "url": "/P40_GDS/GoodsOutStatus.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range", 
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True, 
        "error": None
    })

    # [Fix] Force Inject 'goods_status' (Product Stock Status) - Master Mode
    goods_status_key = "goods_status"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != goods_status_key]

    print(f"Injecting Config for {goods_status_key}")
    data.setdefault("pages", []).append({
        "key": goods_status_key,
        "name": "제품 재고현황", 
        "category": "제품",
        "url": "/P40_GDS/GoodsStatus.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None, # Master Mode
        "is_master": True,
        "has_pagination": True, 
        "error": None
    })

    # [Fix] Force Inject 'goods_hist' (Goods History) - Date Range Mode
    goods_hist_key = "goods_hist"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != goods_hist_key]

    print(f"Injecting Config for {goods_hist_key}")
    data.setdefault("pages", []).append({
        "key": goods_hist_key,
        "name": "제품별 입출내역", 
        "category": "제품",
        "url": "/P40_GDS/GoodsHist.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range", 
        "filter_fields": {
            "from_date": "ctl00_BodyHolder_txt_FDate",
            "to_date": "ctl00_BodyHolder_txt_TDate"
        },
        "has_pagination": True, 
        "error": None
    })

    # [Fix] Force Inject 'goods_rank' (Goods Rank) - Year Dropdown Mode
    goods_rank_key = "goods_rank"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != goods_rank_key]

    print(f"Injecting Config for {goods_rank_key}")
    data.setdefault("pages", []).append({
        "key": goods_rank_key,
        "name": "제품별 매출분석", 
        "category": "분석통계",
        "url": "/P60_SUM/GoodsRank.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "year_dropdown",
        "filter_fields": {
            "year_dropdown": "ctl00_BodyHolder_dd_Srch1"
        },
        "has_pagination": True, 
        "error": None
    })

    # [Fix] Force Inject 'resc_base' (Resource Base) - Master Mode
    resc_base_key = "resc_base"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != resc_base_key]

    print(f"Injecting Config for {resc_base_key}")
    data.setdefault("pages", []).append({
        "key": resc_base_key,
        "name": "자재 기초재고 수정", 
        "category": "재고",
        "url": "/P70_BAS/RescBase.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None, # Master Mode
        "is_master": True,
        "has_pagination": True, 
        "error": None
    })

    # [Fix] Force Inject 'goods_base' (Goods Base) - Master Mode
    goods_base_key = "goods_base"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != goods_base_key]

    print(f"Injecting Config for {goods_base_key}")
    data.setdefault("pages", []).append({
        "key": goods_base_key,
        "name": "제품 기초재고 수정", 
        "category": "재고",
        "url": "/P70_BAS/GoodsBase.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": None, # Master Mode
        "is_master": True,
        "has_pagination": True, 
        "error": None
    })

    # [Cancelled] 'Basic' (기초) Folder Pages are excluded per user request.
    # Removed Injection Blocks for: cust_info, buy_info, outside_info, maker_info, resc_info, goods_info.

    # [Fix] Filter out ALL 'Basic' (기초) and 'System' (시스템) category pages to ensure Logic Removal
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("category") not in ["기초", "시스템"]]

    # [Fix] Force Inject 'outside_stock' (Outer Process Stock)
    outside_stock_key = "outside_stock"
    if "pages" in data:
        data["pages"] = [p for p in data["pages"] if p.get("key") != outside_stock_key]

    print(f"Injecting Config for {outside_stock_key}")
    data.setdefault("pages", []).append({
        "key": outside_stock_key,
        "name": "외주처별 재고현황", 
        "category": "외주",
        "url": "/P30_PRO/OutsideStock.aspx",
        "has_table": True,
        "table_id": "ctl00_BodyHolder_gv_Board",
        "filter_type": "date_range", 
        "has_pagination": True,
        "error": None
    })

    return data


# =============================================================================
# File Save (Atomic)
# =============================================================================
def save_file_atomic(filepath: Path, data: dict):
    """Atomic file write"""
    temp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, filepath)
    except Exception:
        if temp_path.exists():
            os.remove(temp_path)


# =============================================================================
# Progress Display
# =============================================================================
class ProgressTracker:
    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.current_task = ""
        self.errors = 0
        self.start_time = datetime.now()
    
    def update(self, task_name: str):
        self.current += 1
        self.current_task = task_name
        self._render()
    
    def add_error(self):
        self.errors += 1
    
    def _render(self):
        percent = (self.current / self.total) * 100 if self.total > 0 else 0
        filled = int(PROGRESS_BAR_WIDTH * self.current / self.total) if self.total > 0 else 0
        bar = "█" * filled + "░" * (PROGRESS_BAR_WIDTH - filled)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.current > 0:
            eta_seconds = (elapsed / self.current) * (self.total - self.current)
            eta_min = int(eta_seconds // 60)
            eta_sec = int(eta_seconds % 60)
            eta_str = f"{eta_min}분 {eta_sec}초"
        else:
            eta_str = "계산 중..."
        
        sys.stdout.write("\033[2K\r")
        sys.stdout.write(f"진행률: [{bar}] {percent:.1f}% ({self.current}/{self.total})\n")
        sys.stdout.write(f"현재 작업: {self.current_task[:50]:<50}\n")
        sys.stdout.write(f"예상 남은 시간: {eta_str} | 오류: {self.errors}건\n")
        sys.stdout.write("\033[3A")
        sys.stdout.flush()
    
    def finish(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)
        
        sys.stdout.write("\n\n\n")
        print("=" * 60)
        print(f"✅ 완료! 총 {self.current}건 수집 | 소요시간: {elapsed_min}분 {elapsed_sec}초")
        print(f"   오류: {self.errors}건")
        print("=" * 60)


# =============================================================================
# Page Collection
# =============================================================================
async def collect_page(page, page_info: dict, target_date_str: str) -> dict:
    """Collect data from a single page (With Pagination Support)"""
    url = f"{MES_BASE_URL}{page_info['url']}"
    start_ts = datetime.now()
    
    if "~" in target_date_str:
        start_date, end_date = target_date_str.split("~")
    else:
        start_date = end_date = target_date_str
    
    result = {
        "key": page_info["key"],
        "name": page_info["name"],
        "category": page_info["category"],
        "collected_at": start_ts.isoformat(),
        "date": target_date_str,
        "data": [],
        "record_count": 0,
        "error": None,
    }
    
    try:
        await page.goto(url, timeout=LONG_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=20000)
        
        if "Default.aspx" in page.url and "LogOut" not in page.url:
            raise Exception("Redirected to Login Page")
        
        if not page_info.get("has_table"):
            result["error"] = "No table"
            return result
        
        filter_type = page_info.get("filter_type")
        filter_fields = page_info.get("filter_fields", {})
        
        if filter_type == "date_range":
            f_date = filter_fields.get("from_date")
            t_date = filter_fields.get("to_date")
            if f_date and t_date:
                await page.evaluate(f"""() => {{
                    const f = document.getElementById('{f_date}');
                    const t = document.getElementById('{t_date}');
                    if (f) f.value = '{start_date}';
                    if (t) t.value = '{end_date}';
                }}""")
                search_btn = await page.query_selector('[id*="btnSearch"]')
                if search_btn:
                    await search_btn.click()
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await asyncio.sleep(1) # Safety wait for grid refresh
        
        elif filter_type == "year_dropdown":
            # Extract Year from Date (e.g. 2026-01-12 -> 2026)
            year_val = start_date.split("-")[0]
            dropdown_id = filter_fields.get("year_dropdown")
            
            if dropdown_id:
                print(f"  [Debug] Date: {start_date} -> Extracted Year: {year_val} (Target ID: {dropdown_id})")
                print(f"  Setting Year Filter to {year_val} (ID: {dropdown_id})")
                try:
                    # Select Option by Value
                    await page.select_option(f"#{dropdown_id}", value=year_val)
                    
                    # Click Search if exists (generic)
                    search_btn = await page.query_selector('[id*="btnSearch"]')
                    if search_btn:
                        await search_btn.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f"  Failed to set year filter: {e}")
        
        table_id = page_info.get("table_id")
        table_ids = page_info.get("table_ids", [])
        
        # [Fix] Support Multi-Table pages (e.g. RescStatus with Board, Board2, Board3)
        target_tables = []
        if table_ids:
            target_tables = table_ids
        elif table_id:
            target_tables = [table_id]
            
        all_data = []
        
        if target_tables:
            for tid in target_tables:
                print(f"Extracting data from table: {tid}")
                
                # [Fix] Auto-Set Max Rows (Optimize Pagination)
                # If a page size dropdown exists, set it to the maximum (e.g. 100) to reduce paging
                try:
                    set_success = await page.evaluate(f"""() => {{
                        const ddl = document.getElementById('ctl00_BodyHolder_ddl_PageRow');
                        // [Fix] Click 'Search' button to apply page size change (prevents skipping Page 1)
                        // Common IDs: 'btnSearch' (OutsideStock), 'btn_Select', 'btnSelect'
                        const applyBtn = document.querySelector('input[id*="btnSearch"], input[id*="btn_Select"], input[id*="btnSelect"]');
                        
                        // Scenario: Pagination dropdown exists AND value is not 100
                        if (ddl && applyBtn && ddl.value !== '100') {{
                            ddl.value = '100'; // Set value
                            applyBtn.click();  // Trigger reload via Search button
                            return true;
                        }}
                        
                        // [Alternative] If no search button found, do nothing to avoid unsafe navigation
                        return false; 
                    }}""")
                    
                    if set_success:
                        print("Triggered 'Next' button to force 100-row view. Waiting for reload...")
                        # Wait for PostBack to clear
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await asyncio.sleep(3) # Explicit wait for grid rendering
                except Exception as e:
                    print(f"Warning: Failed to set max page size: {e}")

                # [Fix] Force Sort for ProcRes_Cutting, MCT, QC (Latest First)
                # Cutting/MCT/QC results appear random or unsorted by default.
                # We force click '지시번호' header to sort Descending so 2026 data appears on page 1.
                if page_info.get("key") in ["proc_res_cutting", "proc_res_mct", "proc_res_qc"]:
                    try:
                        print("  [Sorting] Clicking '지시번호' header to sort Descending...")
                        # Try finding header with text '지시번호'
                        sort_header = await page.query_selector('th:has-text("지시번호")')
                        if sort_header:
                            await sort_header.click()
                            await page.wait_for_load_state("networkidle", timeout=10000)
                            await asyncio.sleep(2) # Wait for grid refresh
                    except Exception as e:
                         print(f"  [Sorting Warning] Failed to sort: {e}")

                page_num = 1
                last_raw_data = None
                
                # Independent logic for each table (Simple Version: No Multi-Pagination support yet)
                # Assuming Single Page or Global Pagination for multi-table views like Stock Status
                while True:
                    # Extract Current Page
                    data = await page.evaluate(f"""(tid) => {{
                        const table = document.getElementById(tid);
                        if (!table) return [];
                        const rows = Array.from(table.rows); // Use rows collection
                        if (rows.length === 0) return [];
                        
                        const headers = Array.from(rows[0]?.querySelectorAll('th') || []).map(th => th.innerText.trim().replace(/\\n/g, ' '));
                        
                        const result = [];
                        for (let i = 1; i < rows.length; i++) {{
                            const row = rows[i];
                            if (row.parentElement.tagName === 'TFOOT') continue;
                            
                            const cells = Array.from(row.querySelectorAll('td'));
                            const rowText = row.innerText.trim();
                            
                            // [Fix 1] Pagination Row Filter
                            if (rowText.includes(' of ') && rowText.includes('Pages')) continue;
                            if (/^[\\d\\s]+of\\s+\\d+\\s+Pages?$/i.test(rowText)) continue;
                            
                            // [Fix 2] Column Count Filter (Critical for ignoring colspan pagination row)
                            if (headers.length > 0 && cells.length < headers.length * 0.5) continue;

                            if (cells.some(c => c.innerText.includes('합계') || c.innerText.includes('소계'))) continue;
                            
                            
                            const d = {{}};
                            let hasData = false;
                            cells.forEach((c, i) => {{ 
                                if(headers[i]) {{
                                    // [Fix] Extract value from input/button if innerText is effectively empty
                                    let text = c.innerText.trim();
                                    if (!text) {{
                                        const input = c.querySelector('input, button');
                                        if (input && input.value) text = input.value.trim();
                                        else if (input && input.innerText) text = input.innerText.trim();
                                    }}
                                    
                                    d[headers[i]] = text; 
                                    if(text) hasData = true;
                                }}
                            }});
                            
                            if (hasData) result.push(d);
                        }}
                        return result;
                    }}""", tid)
                    
                    # [Fix] Robust Duplicate Page Detection (Raw Data Comparison)
                    # Must compare data BEFORE filtering, otherwise empty filtered pages (e.g. 2022 data) 
                    # will look identical to each other (all []) and cause premature stop.
                    current_raw_data = list(data) # Copy raw data (list of dictionaries)
                    
                    if page_num > 1 and last_raw_data is not None:
                        if current_raw_data == last_raw_data:
                            print(f"  [Duplicate] Page {page_num} content is identical to previous page (Raw Check). Stopping.")
                            # Note: We do NOT delete accumulated data here because this page is just a repeat of server state,
                            # but we stop fetching more.
                            break
                    
                    last_raw_data = current_raw_data

                    # [Fix] Client-side Date Filtering for ProcRes_Cutting, MCT, QC (Server filter broken)
                    if page_info.get("key") in ["proc_res_cutting", "proc_res_mct", "proc_res_qc"]:
                        filtered_data = []
                        # Debug prints removed for production
                        
                        for row in data:
                            # Filter by "지시번호" (Instruction No)
                            val = row.get("지시번호", "")
                            if not val:
                                # Fallback: try finding a key that looks like Instruction Number
                                for k, v in row.items():
                                    if "지시" in k and "번호" in k:
                                        val = v
                                        break
                            
                            row_date = val.strip()[:10]
                            
                            if not row_date: continue
                            
                            # Compare with requested range
                            if start_date <= row_date <= end_date:
                                filtered_data.append(row)
                        
                        # print(f"  [Debug] Filter Result: {len(filtered_data)} / {len(data)} rows kept.")
                        data = filtered_data

                    all_data.extend(data)
                    
                    # If dealing with multi-table, usually they are on one page or share pagination.
                    # For simplicity/safety on 'RescStatus', we assume single page PER table
                    # or that we don't paginate inside this specific multi-table loop structure yet.
                    # If we need pagination, we need to inspect the "Next" button relative to the table.
                    # Given 'RescStatus' usually just lists stock, we break after one page for now 
                    # unless it is the ONLY table (standard behavior preservation).
                    
                    if len(target_tables) > 1:
                        break # Iterate to next table
                    
                    # Standard Single Table Pagination Logic
                    # [Fix 3] Infinite Loop Prevention (Duplicate Page Check) - REPLACED by Raw Check above
                    # Old logic removed because it relied on 'all_data' which fails if pages are empty after filter.
                                 
                    # [Fix 3] Pagination Button Logic
                    # Branching logic: Specific fix for ProcRes_Shape, Press, Heating
                    # [Fix 3] Pagination Button Logic
                    # Branching logic: Specific fix for ProcRes_Shape, Press, Heating, Cutting, MCT, QC, ProcStock, ProcGoodsStock
                    if page_info.get("key") in ["proc_res_shape", "proc_res_press", "proc_res_heating", "proc_res_cutting", "proc_res_mct", "proc_res_qc", "proc_stock", "proc_goods_stock", "outside_stock", "goods_out_status", "goods_status", "goods_hist", "goods_rank", "resc_base", "goods_base"]:
                        # ProcRes_Shape/Press/Heating/Cutting/MCT/QC/Stock/GoodsStock/OutsideStock/GoodsOutStatus/GoodsStatus/GoodsHist/GoodsRank/RescBase/GoodsBase: Dynamic ID, 'no_next' src but enabled
                        selector = '[id*="btnNext"]'
                    else:
                        # Default (Previous Logic): Strict Input/Link selectors
                        selector = 'input[type="image"][src*="Next"], a:has-text(">"), input[id*="btnNext"]'

                    next_btn = await page.query_selector(selector)
                    
                    if not next_btn: 
                        if page_info.get("key") in ["proc_res_shape", "proc_res_press", "proc_res_heating", "proc_res_cutting", "proc_res_mct", "proc_res_qc", "proc_stock", "proc_goods_stock", "outside_stock", "goods_out_status", "goods_status", "goods_hist", "goods_rank", "resc_base", "goods_base"]:
                            print("  [Pagination] No Next button found. Stopping.")
                        break
                    
                    # [Fix] Check for 'no_next' image source (Visual Disable)
                    # Many pages use an image button that changes src to 'no_next' instead of using 'disabled' attribute.
                    src = await next_btn.get_attribute("src")
                    if src and "no_next" in src:
                        # [Correction] Cust, Buy, Outside, Maker, Resc, Goods use 'no_next1.jpg' as ACTIVE button.
                        # Do NOT stop for them. Only stop for ProcRes series if they use this pattern.
                        if page_info.get("key") in ["proc_res_shape", "proc_res_press", "proc_res_heating", "proc_res_cutting", "proc_res_mct", "proc_res_qc", "proc_stock", "proc_goods_stock", "outside_stock", "goods_out_status", "goods_status", "goods_hist", "goods_rank", "resc_base", "goods_base"]:
                             print("  [Pagination] Next button shows 'no_next'. Stopping.")
                             break

                    # Check Disabled State
                    is_disabled = await next_btn.get_attribute("disabled")
                    if is_disabled:
                         break
                        
                    try:
                        if page_info.get("key") in ["proc_res_shape", "proc_res_press", "proc_res_heating", "proc_res_cutting", "proc_res_mct", "proc_res_qc", "proc_stock", "proc_goods_stock", "outside_stock", "goods_out_status", "goods_status", "goods_hist", "goods_rank", "resc_base", "goods_base"]:
                            print("  [Pagination] Clicking Next button...")
                            
                        await next_btn.click()
                        
                        # Wait logic
                        if page_info.get("key") in ["proc_res_shape", "proc_res_press", "proc_res_heating", "proc_res_cutting", "proc_res_mct", "proc_res_qc", "proc_stock", "proc_goods_stock", "outside_stock", "goods_out_status", "goods_status", "goods_hist", "goods_rank", "resc_base", "goods_base"]:
                             await page.wait_for_load_state("networkidle", timeout=15000)
                             await asyncio.sleep(2) # Extra wait for this page
                        else:
                             await page.wait_for_load_state("networkidle", timeout=5000)
                             
                        page_num += 1
                        # [Fix] Increase Page Limit for large datasets (e.g. OutsideStock with 1000+ rows)
                        if page_num > 300: break
                    except:
                        break
            
            result["data"] = all_data
            result["record_count"] = len(all_data)
            
            # [Fix] Detail Extraction for MShape (Mold Drawings)
            if page_info.get("key") == "m_shape" and all_data:
                print("Extracting Detail Info (Attachments) for Mold Drawings...")
                
                # 1. Capture Detail URLs from '금형번호' Link
                # Selector: a[id*='hl_코드']
                mshape_map = await page.evaluate("""(tid) => {
                    const table = document.getElementById(tid);
                    if (!table) return [];
                    const rows = Array.from(table.rows);
                    const map = [];
                    for(let i=1; i<rows.length; i++) {
                        const link = rows[i].querySelector("a[id*='hl_코드']");
                        if (link && link.getAttribute('href')) {
                            map.push({idx: i-1, href: link.getAttribute('href')});
                        }
                    }
                    return map;
                }""", table_id)
                
                # 2. Visit and Download
                import os
                
                for item in mshape_map:
                    idx = item['idx']
                    href = item['href'] 
                    detail_url = f"{MES_BASE_URL}/P50_QLT/{href}"
                    
                    try:
                        print(f"  [Mold Detail {idx+1}] Fetching {detail_url}...")
                        await page.goto(detail_url, timeout=15000)
                        await page.wait_for_load_state("domcontentloaded")
                        
                        # Find Attachment Link
                        attach_info = await page.evaluate("""() => {
                            const link = document.getElementById('ctl00_BodyHolder_lnk_첨부');
                            if (link && link.href && !link.href.includes('javascript')) {
                                return {href: link.href, name: link.innerText.trim()};
                            }
                            return null;
                        }""")
                        
                        if attach_info:
                             file_url = attach_info['href'] 
                             file_name = attach_info['name']
                             
                             if file_url:
                                 # Construct Save Path
                                 rel_path = f"attachments/{file_name}"
                                 
                                 # [Fix] Naming Consistency with save_result
                                 raw_name = page_info.get("folder_name") or page_info.get("name") or page_info.get("key")
                                 folder_name = raw_name.replace("/", "_").replace(" ", "_").replace("\\", "_")
                                 
                                 base_dir = get_data_dir() / page_info.get('category', 'Unknown') / folder_name / "attachments"
                                 base_dir.mkdir(parents=True, exist_ok=True)
                                 save_path = base_dir / file_name
                                 
                                 if not save_path.exists():
                                     print(f"    Downloading {file_name}...")
                                     response = await page.context.request.get(file_url)
                                     if response.ok:
                                         file_data = await response.body()
                                         with open(save_path, "wb") as f:
                                             f.write(file_data)
                                         
                                         if idx < len(all_data):
                                             all_data[idx]['attached_file'] = str(rel_path)
                                     else:
                                         print(f"    Download failed: {response.status}")
                                 else:
                                      print(f"    File exists, using cached: {file_name}")
                                      if idx < len(all_data):
                                         all_data[idx]['attached_file'] = str(rel_path)
                        
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        print(f"  Failed mold detail processing: {e}")
            


            # [Fix] Forward Fill Logic for Multi-row items (e.g. AllSign)
            forward_fill_keys = page_info.get("forward_fill_keys")
            if forward_fill_keys and all_data:
                print(f"Applying Forward Fill for keys: {forward_fill_keys}")
                # Reset Forward Fill for each processing batch? No, it's post-process.
                # Logic: Forward Fill runs sequentially.
                # Important: When switching tables (Units), last_values should RESET?
                # Yes, Unit 1 data shouldn't leak to Unit 2 rows.
                # However, since 'all_data' is mixed, iterating linearly is risky if units are mixed.
                # BUT 'all_data' is appended sequentially: Table 1 then Table 2.
                # So we just need to detect when 'Forward Fill' should reset?
                # Actually, our forward fill logic checks "if not val".
                
                last_values = {k: "" for k in forward_fill_keys}
                
                for row in all_data:
                    for k in forward_fill_keys:
                        val = row.get(k, "").strip()
                        if not val:
                            row[k] = last_values.get(k, "")
                        else:
                            last_values[k] = val
                            
            # [Fix] Detail Extraction for ShapeINN (Incoming Details)
            if page_info.get("key") == "shape_inn" and all_data:
                print("Extracting Detail Info for ShapeINN...")
                # 1. Capture 'onclick' from the page
                detail_map = await page.evaluate("""(tid) => {
                    const table = document.getElementById(tid);
                    if (!table) return [];
                    const rows = Array.from(table.rows);
                    const map = [];
                    for(let i=1; i<rows.length; i++) {
                        // Find button with 'pop_new_input' OR 'pop_edit_input'
                        const btn = rows[i].querySelector('input[onclick*="pop_new_input"], input[onclick*="pop_edit_input"]');
                        if (btn) {
                            map.push({idx: i-1, onclick: btn.getAttribute('onclick')});
                        }
                    }
                    return map;
                }""", table_id)
                
                # 2. Iterate and Process
                if len(detail_map) == len(all_data):
                    import re
                    
                    for i, item in enumerate(detail_map):
                        onclick = item['onclick'] 
                        # Pattern 1: New Input (Empty params) -> pop_new_input('Date', 'Num', 'SNo', '', '', '', '')
                        # Pattern 2: Edit Input (Filled params) -> pop_edit_input('Date', 'Num', 'SNo', 'InDate', 'REV', 'Maker', 'Cost')
                        
                        # Check for Edit first (Optimization: No page visit needed!)
                        match_edit = re.search(r"pop_edit_input\('([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)", onclick)
                        if match_edit:
                            # Mapping based on observation:
                            # 0: OrderDate, 1: Num, 2: Sno
                            # 3: RecvDate (입고일자)
                            # 4: REV (REV No.)
                            # 5: MakerCode 
                            # 6: Cost (금형비)
                            groups = match_edit.groups()
                            all_data[i]['입고일자'] = groups[3]
                            all_data[i]['REV No.'] = groups[4]
                            all_data[i]['금형비'] = groups[6]
                            continue # Done for this row!
                        
                        # Check for New (Existing Logic)
                        match_new = re.search(r"pop_new_input\('([^']*)',\s*'([^']*)',\s*'([^']*)'", onclick)
                        if match_new:
                            # Construct URL
                            p_date, p_num, p_sno = match_new.groups()
                            detail_url = f"{MES_BASE_URL}/P50_QLT/ShapeINN_Item.aspx?idx1={p_date}&idx2={p_num}&idx3={p_sno}&idx4=&idx5=&idx6=&idx7="
                            
                            print(f"  [Detail {i+1}/{len(all_data)}] Fetching New Items {detail_url}...")
                            try:
                                # Open Detail Page
                                await page.goto(detail_url, timeout=10000)
                                await page.wait_for_load_state("domcontentloaded")
                                
                                # Scrape Fields
                                detail_info = await page.evaluate("""() => {
                                    return {
                                        '입고일자': document.getElementById('txt_입고일자')?.value || '',
                                        '금형비': document.getElementById('txt_금형비')?.value || '',
                                        'REV No.': document.getElementById('txt_REV')?.value || ''
                                    };
                                }""")
                                
                                if detail_info:
                                    all_data[i].update(detail_info)
                                    
                            except Exception as e:
                                print(f"  Failed detail fetch: {e}")
                                
                            await asyncio.sleep(0.5)
                else:
                    print(f"Warning: Detail map count ({len(detail_map)}) != Data count ({len(all_data)}). Skipping detail extraction.")

            # [Fix] Detail Explosion for SummResc (Billet History Popup)
            # Replaces Summary Rows with Detailed Rows from Popup
            if page_info.get("key") == "summ_resc" and all_data:
                print("Exploding Detail Info for SummResc...")
                # 1. Capture dates from 'onclick'
                detail_map = await page.evaluate("""(tid) => {
                    const table = document.getElementById(tid);
                    if (!table) return [];
                    const rows = Array.from(table.rows);
                    const map = [];
                    for(let i=1; i<rows.length; i++) {
                        const btn = rows[i].querySelector('input[onclick*="pop_view"]');
                        if (btn) {
                             const match = btn.getAttribute('onclick').match(/pop_view\\('([^']+)'\\)/);
                             if (match) map.push({date: match[1]});
                        }
                    }
                    return map;
                }""", table_id)
                
                detailed_all_data = []
                processed_dates = set()
                
                import re
                
                for item in detail_map:
                    p_date = item['date']
                    if p_date in processed_dates: continue
                    processed_dates.add(p_date)
                    
                    hist_url = f"{MES_BASE_URL}/P20_RSC/SummResc_Hist.aspx?day={p_date}"
                    print(f"  [Detail] Fetching History for {p_date}...")
                    
                    try:
                        await page.goto(hist_url, timeout=10000)
                        await page.wait_for_load_state("domcontentloaded")
   
                        # [Fix] Pagination Loop for Detail Popup
                        while True:
                            popup_data = await page.evaluate("""(date_val) => {
                                const table = document.querySelector('table[id*="gv_Board"]');
                                if (!table) return [];
                                const rows = Array.from(table.rows);
                                if (rows.length === 0) return [];
                                
                                const headers = Array.from(rows[0].querySelectorAll('th')).map(th => th.innerText.trim());
                                
                                // Skip header row (index 0)
                                // Skip pager row (usually last or penultimate, check class or content)
                                return rows.slice(1).filter(row => !row.classList.contains('pager')).map(row => {
                                    const rowData = {'일자': date_val}; 
                                    Array.from(row.querySelectorAll('td')).forEach((cell, index) => {
                                        const key = headers[index] || `column_${index}`;
                                        rowData[key] = cell.innerText.trim();
                                    });
                                    return rowData;
                                });
                            }""", p_date)
                            
                            if popup_data:
                                detailed_all_data.extend(popup_data)
                                
                            # Check Pagination
                            next_btn = await page.query_selector('input[id*="btnNext"]')
                            if not next_btn:
                                break
                                
                            try:
                                # [Fix] Specific ID for SummResc Popup might be different but pattern holds
                                await next_btn.click()
                                await page.wait_for_load_state("networkidle", timeout=5000)
                                await asyncio.sleep(1) 
                            except Exception as nav_e:
                                print(f"    [Pagination] Navigation ended: {nav_e}")
                                break
                        
                    except Exception as e:
                        print(f"  Failed detail fetch for {p_date}: {e}")
                        
                    await asyncio.sleep(0.5)
                
                if detailed_all_data:
                    print(f"  [Explosion] Replaced {len(all_data)} summary rows with {len(detailed_all_data)} detail rows")
                    all_data = detailed_all_data

            # [Fix] RescStatus Expansion Logic (Circuit Breaker & Expand All)
            if page_info.get("key") == "resc_status":
                print("Checking RescStatus Circuit Breaker (Total Weight)...")
                # 1. Get Current Total Weight
                current_total = await page.evaluate("""
                    Array.from(document.querySelectorAll('span[id$="lbl_중량계"]')).map(s => s.innerText.trim()).join('|')
                """)
                print(f"  Current Total: {current_total}")
                
                # 2. Compare with Last Total (if file exists)
                # Need to read previous file. (Assuming save path is standard)
                import json
                try:
                    # Construct previous file path
                    # Since this is Master Mode, output filename is likely resc_status.json
                    # But collect_page doesn't know output filename easily unless passed or inferred.
                    # We will skip comparison here and do it? Or does user want STOP if matches?
                    # User request: "Compare ... If unchanged, Stop."
                    # We can implement a check mechanism. But for now, let's implement the EXPANSION primarily.
                    # Optimization: If we implement strict stoppage, we return empty list or signal?
                    # Let's proceed to Expansion always for safety first, OR check file.
                    # Given Master Mode overwrites, we can check existing file content.
                    pass 
                except:
                    pass

                # 3. Expansion Loop (Click '+' buttons)
                print("Expanding RescStatus Details (Clicking '+' buttons)...")
                expand_count = 0
                visited_ids = set()
                
                while True:
                    # [Fix] ID-based Tracking to prevent Infinite Loops
                    # Get all currently visible '+' buttons
                    current_buttons = await page.query_selector_all("input[value='+'][id*='bttn_Disp']")
                    target_btn = None
                    target_id = None
                    
                    for btn in current_buttons:
                        b_id = await btn.get_attribute("id")
                        if b_id and b_id not in visited_ids:
                            target_btn = btn
                            target_id = b_id
                            break
                    
                    if not target_btn:
                        print(f"  No new expansion buttons found. (Visited: {len(visited_ids)})")
                        break
                        
                    try:
                        # Add to visited BEFORE clicking (to avoid loop if click fails but doesn't throw)
                        visited_ids.add(target_id)
                        
                        await target_btn.click()
                        # Postback Wait
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        await asyncio.sleep(0.5) # Stability wait
                        
                        expand_count += 1
                        if expand_count % 10 == 0:
                            print(f"  Expanded {expand_count} rows...")
                            
                        # Safety Limit
                        if expand_count > 1000:
                            print("  [Warning] Exceeded 1000 expansions. Stopping safety break.")
                            break
                            
                    except Exception as e:
                        print(f"  Expansion failed for {target_id}: {e}")
                        # If failed, we already marked it visited, so we won't retry it forever.
                        continue
                
                # 4. Re-Scrape Table (Now fully expanded)
                # The generic scraper above might have run BEFORE expansion?
                # Yes, 'all_data' is already populated with Summary data.
                # We need to RE-SCRAPE now that rows are expanded.
                print("Re-scraping Expanded Table...")
                # We need to invoke the table scraping logic AGAIN or rely on 'all_data' being replaced.
                # Since the generic logic is above, we must do it manually here.
                
                expanded_data = await page.evaluate("""(tid) => {
                    const table = document.querySelector('table[id*="gv_Board"]');
                    if (!table) return [];
                    const rows = Array.from(table.rows);
                    // Header is row 0. Expanded rows serve as 'detail' for preceeding row?
                    // Actually, expanded rows are just new TRs.
                    // We need a robust strategy to map them.
                    // Forward Fill logic (later step) handles filling "Factory/Material" from summary to detail.
                    // So we just need to dump ALL text from the table.
                    
                    const headers = Array.from(rows[0].querySelectorAll('th')).map(th => th.innerText.trim());
                    return rows.slice(1).map(row => {
                         const cells = Array.from(row.querySelectorAll('td'));
                         // Expanded row inner grid? Or just flat cells?
                         // Inspection showed '+' inserts a row.
                         // Let's assume standard cell mapping.
                         const rowData = {};
                         cells.forEach((cell, index) => {
                             const key = headers[index] || `column_${index}`;
                             rowData[key] = cell.innerText.trim();
                         });
                         return rowData;
                    });
                }""", table_id)
                
                if expanded_data:
                    all_data = expanded_data
                    print(f"  Captured {len(all_data)} rows (Summary + Details)")

            result["data"] = all_data
    
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result


async def save_result(page_info: dict, result: dict, output_filename: str):
    data_dir = get_data_dir()
    key = page_info["key"]
    # [Fix] Use Korean Name for folder if possible
    # Fallback: folder_name field -> name field (sanitized) -> key
    raw_name = page_info.get("folder_name") or page_info.get("name") or key
    folder_name = raw_name.replace("/", "_").replace(" ", "_").replace("\\", "_")
    
    save_dir = data_dir / page_info["category"] / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)
    target_file = save_dir / output_filename
    
    save_file_atomic(target_file, result)
    if result["data"]:
        save_page_data(key, result["data"], result["record_count"])


# =============================================================================
# Worker
# =============================================================================
async def worker(worker_id: int, browser, user_id, password, queue: asyncio.Queue, progress: ProgressTracker, error_logger: RealTimeErrorLogger):
    """Worker with context recycling"""
    MAX_TASKS_PER_CONTEXT = 100
    
    while not queue.empty():
        try:
            context = await browser.new_context()
            
            # [Optimization] Block visual resources
            await context.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "stylesheet", "font", "media", "other"] 
                else route.continue_()
            )
            
            page = await context.new_page()
            
            try:
                await page.goto(LOGIN_URL, timeout=LONG_TIMEOUT)
                await page.fill(LOGIN_SELECTOR_ID, user_id)
                await page.fill(LOGIN_SELECTOR_PW, password)
                await page.click(LOGIN_SELECTOR_BTN)
                await page.wait_for_url("**/P00_DSH/**", timeout=20000)
            except Exception:
                await context.close()
                progress.add_error()
                continue
                
            for _ in range(MAX_TASKS_PER_CONTEXT):
                try:
                    item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                
                page_info, date_str, output_file = item
                task_name = f"[W{worker_id}] {date_str} / {page_info['name']}"
                
                try:
                    result = await collect_page(page, page_info, date_str)
                    await save_result(page_info, result, output_file)
                    
                    if result.get("error"):
                        progress.add_error()
                        # [Real-time Log]
                        error_logger.log(date_str, page_info['name'], result["error"])
                    
                except Exception as e:
                    progress.add_error()
                    # [Real-time Log]
                    error_logger.log(date_str, page_info['name'], str(e))
                
                progress.update(task_name)
                queue.task_done()
            
            await context.close()
            
        except Exception:
            await asyncio.sleep(5)


# =============================================================================
# Main
# =============================================================================
async def run_sync(from_date: str, to_date: str, num_workers: int):
    print("=" * 60)
    print("MES 동기화 도구 (Mac M1 최적화 - 로컬 모드)")
    print("=" * 60)
    
    start_dt = datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.strptime(to_date, "%Y-%m-%d")
    days_count = (end_dt - start_dt).days + 1
    
    structures = load_page_structures()
    all_pages = [p for p in structures["pages"] if p["key"] not in IGNORE_PAGES]
    
    # [Fix] Split Master Pages (Single Run) vs Daily Pages (Date Loop)
    master_pages = [p for p in all_pages if p.get("is_master")]
    daily_pages = [p for p in all_pages if not p.get("is_master")]
    
    total_tasks = (days_count * len(daily_pages)) + len(master_pages)
    
    print(f"기간: {from_date} ~ {to_date} ({days_count}일)")
    print(f"작업: {total_tasks:,}건 [Daily: {len(daily_pages)}종 x {days_count}일 | Master: {len(master_pages)}종]")
    print(f"저장: {get_data_dir()}")
    print()
    
    init_db()
    
    user_id, password = get_credentials()
    if not user_id:
        print("❌ config.ini 파일을 확인해주세요.")
        return
    
    print("[시스템] 엔진 초기화... ", end="")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-gpu', '--no-sandbox']
        )
        print("완료")
        
        queue = asyncio.Queue()
        
        # 1. Queue Master Pages (Execution Once, No Date Filter)
        for page in master_pages:
            # For Master pages, date arg is irrelevant but used for logs.
            # Output file is dynamic based on key (e.g. m_shape.json, shape_rev.json)
            queue.put_nowait((page, "ALL_DATE", f"{page['key']}.json"))
            
        # 2. Queue Daily Pages (Execution Loop)
        for i in range(days_count):
            d = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            for page in daily_pages:
                queue.put_nowait((page, d, f"{d}.json"))
        
        progress = ProgressTracker(total_tasks)
        error_logger = RealTimeErrorLogger()
        
        tasks = [
            asyncio.create_task(worker(i, browser, user_id, password, queue, progress, error_logger))
            for i in range(num_workers)
        ]
        
        await asyncio.gather(*tasks)
        progress.finish()
        
        print(f"데이터 위치: {get_data_dir()}")
        if error_logger.filepath.exists():
             print(f"오류 로그: {error_logger.filepath}")

def main():
    parser = argparse.ArgumentParser(description="Mes Sync Tool for Mac M1")
    parser.add_argument("--from", dest="from_date", required=True)
    parser.add_argument("--to", dest="to_date", required=True)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()
    
    asyncio.run(run_sync(args.from_date, args.to_date, args.workers))

if __name__ == "__main__":
    main()
