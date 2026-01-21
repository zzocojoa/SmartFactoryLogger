"""
MES 데이터 동기화 도구 (독립 실행형)
Standalone CLI tool for fast MES data synchronization.

Usage:
    python sync_tool.py --from 2025-01-01 --to 2025-12-31
    python sync_tool.py --from 2025-01-01 --to 2025-01-31 --workers 3
    
    MES_Sync_Tool.exe --from 2025-01-01 --to 2015-12-31
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
# Self-Contained Configuration (No relative imports)
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

# Paths - Self-contained logic
def get_app_data_dir() -> Path:
    """Get the application data directory"""
    if os.name == "nt":  # Windows
        base = os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "SmartFactoryLogger"
    else:
        return Path.home() / ".config" / "SmartFactoryLogger"

def get_data_dir() -> Path:
    """Get the MES data directory"""
    return get_app_data_dir() / "logs" / "mes_data"

def get_config_path() -> Path:
    """Get the config.ini path"""
    return get_app_data_dir() / "config.ini"

def get_structures_file() -> Path:
    """Get the page_structures.json path"""
    if getattr(sys, "frozen", False):
        # PyInstaller EXE
        base = Path(sys._MEIPASS)
        return base / "mes_bridge" / "data" / "page_structures.json"
    else:
        # Development
        return Path(__file__).parent / "mes_bridge" / "data" / "page_structures.json"

# Business Constants
IGNORE_PAGES = {"app_line", "trace_lot"}

# Configuration
DEFAULT_WORKERS = 5
PROGRESS_BAR_WIDTH = 40


# =============================================================================
# Config Manager (Self-contained)
# =============================================================================
def get_credentials() -> tuple[str, str]:
    """Get MES credentials from config.ini"""
    config_path = get_config_path()
    if not config_path.exists():
        return "", ""
    
    config = configparser.ConfigParser()
    # Use utf-8-sig to handle BOM (Byte Order Mark)
    config.read(config_path, encoding="utf-8-sig")
    
    # Note: config.ini uses 'userid' not 'user_id'
    user_id = config.get("MES", "userid", fallback="")
    password = config.get("MES", "password", fallback="")
    
    return user_id, password


# =============================================================================
# Database Manager (Self-contained)
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON raw_data(hash_val);")
    conn.commit()
    conn.close()

def save_page_data(page_key: str, data: list, record_count: int):
    """Save page data to database"""
    if not data:
        return
    
    db_path = get_data_dir() / "mes_data.db"
    json_str = json.dumps(data, ensure_ascii=False)
    data_hash = str(hash(json.dumps(data[:5], sort_keys=True)))
    
    # [Fix] Explicitly convert datetime to string to avoid DeprecationWarning
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
    with open(structures_file, "r", encoding="utf-8") as f:
        return json.load(f)


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
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        raise e


# =============================================================================
# Page Collection
# =============================================================================
async def collect_page(page, page_info: dict, target_date_str: str) -> dict:
    """Collect data from a single page"""
    url = f"{MES_BASE_URL}{page_info['url']}"
    start_ts = datetime.now()
    
    # Parse date range
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
        
        # Check for login redirect
        if "Default.aspx" in page.url and "LogOut" not in page.url:
            raise Exception("Redirected to Login Page")
        
        if not page_info.get("has_table"):
            result["error"] = "No table"
            return result
        
        # Set date filter
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
                    await page.wait_for_load_state("networkidle", timeout=20000)
        
        # Extract table data
        table_id = page_info.get("table_id")
        if table_id:
            data = await page.evaluate(f"""(tid) => {{
                const table = document.getElementById(tid);
                if (!table) return [];
                const rows = Array.from(table.querySelectorAll('tr'));
                const headers = Array.from(rows[0]?.querySelectorAll('th') || []).map(th => th.innerText.trim().replace(/\\n/g, ' '));
                return rows.slice(1).map(row => {{
                    const cells = Array.from(row.querySelectorAll('td'));
                    if (cells.some(c => c.innerText.includes('합계') || c.innerText.includes('소계'))) return null;
                    const d = {{}};
                    cells.forEach((c, i) => {{ if(headers[i]) d[headers[i]] = c.innerText.trim(); }});
                    return d;
                }}).filter(x => x !== null && Object.keys(x).length > 0);
            }}""", table_id)
            result["data"] = data
            result["record_count"] = len(data)
    
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result


async def save_result(page_info: dict, result: dict, output_filename: str):
    """Save collection result to file and database"""
    data_dir = get_data_dir()
    key = page_info["key"]
    
    # Determine folder name
    folder_name = page_info.get("folder_name", key.replace("_", "_"))
    save_dir = data_dir / page_info["category"] / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)
    target_file = save_dir / output_filename
    
    # Save to JSON file
    try:
        save_file_atomic(target_file, result)
    except Exception:
        pass
    
    # Save to DB
    try:
        if result["data"]:
            save_page_data(key, result["data"], result["record_count"])
    except Exception:
        pass


# =============================================================================
# Progress Display (Moved BEFORE Worker)
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
# Worker
# =============================================================================
async def worker(worker_id: int, browser, user_id, password, queue: asyncio.Queue, progress: ProgressTracker, results: list):
    """Worker with context recycling for memory management"""
    MAX_TASKS_PER_CONTEXT = 100  # Restart context every 100 tasks
    
    while not queue.empty():
        # Create fresh context
        try:
            context = await browser.new_context()
            
            # [Optimization] Block unnecessary resources to speed up loading
            await context.route("**/*", lambda route: route.abort() 
                if route.request.resource_type in ["image", "stylesheet", "font", "media", "other"] 
                else route.continue_()
            )
            
            page = await context.new_page()
            
            # Login
            try:
                await page.goto(LOGIN_URL, timeout=LONG_TIMEOUT)
                await page.fill(LOGIN_SELECTOR_ID, user_id)
                await page.fill(LOGIN_SELECTOR_PW, password)
                await page.click(LOGIN_SELECTOR_BTN)
                await page.wait_for_url("**/P00_DSH/**", timeout=20000)
            except Exception as e:
                # Login failed, skip this batch (or retry?)
                # For now, mark current items as error or just retry logic could be added
                await context.close()
                progress.add_error()
                continue
                
            # Process batch
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
                    
                    results.append(result)
                except Exception as e:
                    progress.add_error()
                    results.append({"error": str(e), "page": page_info["key"], "date": date_str})
                
                progress.update(task_name)
                queue.task_done()
            
            await context.close()
            
        except Exception as e:
            # Context creation failure
            await asyncio.sleep(5) # Wait a bit before retry


# =============================================================================
# Main Sync Logic
# =============================================================================
async def run_sync(from_date: str, to_date: str, num_workers: int):
    """Run the synchronization process"""
    
    print("=" * 60)
    print("MES 데이터 동기화 도구 v1.2 (최적화 버전)")
    print("=" * 60)
    
    # Parse dates
    start_dt = datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.strptime(to_date, "%Y-%m-%d")
    days_count = (end_dt - start_dt).days + 1
    
    # Load page structures
    structures = load_page_structures()
    pages = [p for p in structures["pages"] if p["key"] not in IGNORE_PAGES]
    
    total_tasks = days_count * len(pages)
    
    print(f"날짜 범위: {from_date} ~ {to_date} ({days_count}일)")
    print(f"수집 대상: {len(pages)}개 페이지 × {days_count}일 = {total_tasks:,}건")
    print(f"병렬 처리: {num_workers}개 워커")
    print(f"저장 경로: {get_data_dir()}")
    print()
    
    # Initialize DB
    try:
        init_db()
        print("[DB] 데이터베이스 초기화 완료")
    except Exception as e:
        print(f"[경고] DB 초기화 실패: {e}")
    
    # Get credentials
    user_id, password = get_credentials()
    if not user_id or not password:
        print("❌ [오류] MES 계정 정보가 설정되지 않았습니다.")
        print(f"   설정 파일 경로: {get_config_path()}")
        print("   SmartFactory 앱에서 설정 > MES 계정 정보를 입력해주세요.")
        return
    
    print("[시스템] 브라우저 엔진 준비 중...", end=" ")
    
    # Set browser path for EXE environment
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        browsers_path = exe_dir / "browsers"
        if browsers_path.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-extensions',
                ]
            )
            print("✔ 완료")
        except Exception as e:
            print(f"❌ 실패")
            print(f"[오류] 브라우저 실행 실패: {e}")
            return
            
        # Build task queue
        queue = asyncio.Queue()
        for i in range(days_count):
            current_dt = start_dt + timedelta(days=i)
            date_str = current_dt.strftime("%Y-%m-%d")
            
            for page_info in pages:
                output_file = f"{date_str}.json"
                queue.put_nowait((page_info, date_str, output_file))
        
        print()
        print("-" * 60)
        
        # Create progress tracker
        progress = ProgressTracker(total_tasks)
        results = []
        
        # Start workers (Independent Contexts)
        tasks = [
            asyncio.create_task(worker(i, browser, user_id, password, queue, progress, results))
            for i in range(num_workers)
        ]
        
        await asyncio.gather(*tasks)
        
        progress.finish()
        
        # Summary & Error Report
        success_count = sum(1 for r in results if not r.get("error"))
        errors = [r for r in results if r.get("error")]
        error_count = len(errors)
        total_records = sum(r.get("record_count", 0) for r in results if not r.get("error"))
        
        print(f"\n📊 결과 요약:")
        print(f"   - 성공: {success_count:,}건")
        print(f"   - 실패: {error_count:,}건")
        print(f"   - 총 레코드: {total_records:,}건")
        
        if error_count > 0:
            error_file = f"error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(error_file, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Page", "Error Message"])
                for err in errors:
                    writer.writerow([err.get("date"), err.get("page"), err.get("error")])
            print(f"   - ⚠️ 오류 리포트 생성됨: {error_file}")
        
        await browser.close()


# =============================================================================
# Entry Point
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="MES 데이터 동기화 도구 (독립 실행형)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python sync_tool.py --from 2025-01-01 --to 2025-12-31
  python sync_tool.py --from 2025-01-01 --to 2025-01-31 --workers 3
  
  MES_Sync_Tool.exe --from 2025-01-01 --to 2025-12-31
        """
    )
    parser.add_argument(
        "--from", dest="from_date", required=True,
        help="시작 날짜 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--to", dest="to_date", required=True,
        help="종료 날짜 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_WORKERS,
        help=f"동시 처리 워커 수 (기본값: {DEFAULT_WORKERS})"
    )
    
    args = parser.parse_args()
    
    # Validate dates
    try:
        datetime.strptime(args.from_date, "%Y-%m-%d")
        datetime.strptime(args.to_date, "%Y-%m-%d")
    except ValueError:
        print("❌ 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.")
        sys.exit(1)
    
    if args.from_date > args.to_date:
        print("❌ 시작 날짜가 종료 날짜보다 늦을 수 없습니다.")
        sys.exit(1)
    
    # Run sync
    asyncio.run(run_sync(args.from_date, args.to_date, args.workers))
    
    # Pause before exit (so user can see results)
    input("\n종료하려면 Enter를 누르세요...")


if __name__ == "__main__":
    main()
