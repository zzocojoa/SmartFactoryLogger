"""
MES 실시간 데이터 수집 스케줄러 (Robust Version)
- 세션 유지 & 멀티탭 병렬 수집
- Micro-Batch (1분 실시간 + 3일 보정)
- 안정성 강화: Self-Healing, Login Check, Atomic Write
"""

import asyncio
import json
import os
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright
import traceback
import gc
from typing import Optional

from .constants import (
    MES_BASE_URL, 
    LOGIN_URL, 
    LOGIN_SELECTOR_ID, 
    LOGIN_SELECTOR_PW, 
    LOGIN_SELECTOR_BTN,
    DEFAULT_TIMEOUT,
    DATA_DIR,
    STRUCTURES_FILE,
    LONG_TIMEOUT,
    IGNORE_PAGES
)
from .config_manager import get_credentials
from .pages_registry import MES_PAGES
from .logger_config import get_logger

import random

class CircuitBreaker:
    """네트워크 안전장치 (회로 차단기)"""
    def __init__(self, failure_threshold=5, recovery_timeout=1800):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout # 30분
        self.last_failure_time = None
        self.state = "CLOSED" # CLOSED(정상), OPEN(차단), HALF_OPEN(간보기)

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.critical("Circuit Breaker OPENED due to consecutive failures", extra={
                "failure_count": self.failure_count
            })

    def record_success(self):
        if self.state != "CLOSED":
            logger.info("Circuit Breaker CLOSED (Recovered)")
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    def can_proceed(self):
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit Breaker HALF_OPEN (Probing...)")
                return True # 한번 시도 허용
            return False
            
        return True # HALF_OPEN 상태에서도 시도 허용

# 로거 설정
logger = get_logger("scheduler")

# 설정 (메모리 최적화)
NUM_WORKERS = 3         # 동시 탭 수 (5 -> 3으로 감소)
INTERVAL_SECONDS = 300  # 수집 주기 (5분, 메모리 최적화)
BROWSER_RESTART_CYCLES = 6   # 브라우저 재시작 주기 (6 * 5분 = 30분, 메모리 누수 방지)

# 안전장치 인스턴스
circuit_breaker = CircuitBreaker()


# 운영 시간 체크 함수들
def get_operating_hours() -> tuple[int, int]:
    """config 모듈에서 현재 운영 시간 로드 (동적 반영)"""
    from backend import config
    return config.MES_START_HOUR, config.MES_END_HOUR


def is_within_operating_hours() -> bool:
    """현재 시간이 운영 시간 내인지 확인"""
    start_hour, end_hour = get_operating_hours()
    now = datetime.now()
    return start_hour <= now.hour < end_hour


def seconds_until_start() -> float:
    """다음 운영 시작 시간까지 남은 초 계산"""
    start_hour, end_hour = get_operating_hours()
    now = datetime.now()
    
    if now.hour >= end_hour:
        # 오늘 종료 후 → 내일 시작 시간까지
        next_start = (now + timedelta(days=1)).replace(
            hour=start_hour, minute=0, second=0, microsecond=0
        )
    elif now.hour < start_hour:
        # 오늘 시작 전
        next_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    else:
        return 0
    
    return (next_start - now).total_seconds()

def load_page_structures():
    """페이지 구조 정보 로드"""
    with open(STRUCTURES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_changes(old_data: list, new_data: list) -> dict:
    """데이터 변경 감지"""
    old_count = len(old_data) if old_data else 0
    new_count = len(new_data) if new_data else 0
    
    old_hash = hash(json.dumps(old_data[:5], sort_keys=True, ensure_ascii=False)) if old_data else 0
    new_hash = hash(json.dumps(new_data[:5], sort_keys=True, ensure_ascii=False)) if new_data else 0
    
    return {
        "changed": (old_count != new_count) or (old_hash != new_hash),
        "old_count": old_count,
        "new_count": new_count,
        "diff": new_count - old_count
    }


def save_file_atomic(filepath: Path, data: dict):
    """원자적 파일 쓰기 (Atomic Write)"""
    temp_path = filepath.with_suffix(filepath.suffix + ".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno()) # 디스크 동기화
        os.replace(temp_path, filepath) # 원자적 이름 변경
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        raise e


def write_changelog(save_dir: Path, page_key: str, change_info: dict):
    """변경 이력 기록"""
    changelog_file = save_dir / "changelog.jsonl"
    log_entry = {
        "ts": datetime.now().isoformat(),
        "page": page_key,
        "action": "add" if change_info["diff"] > 0 else ("remove" if change_info["diff"] < 0 else "update"),
        "old_count": change_info["old_count"],
        "new_count": change_info["new_count"],
        "diff": change_info["diff"]
    }
    with open(changelog_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


async def collect_page(page, page_info, target_date_str, output_filename="today.json"):
    """단일 페이지 수집"""
    url = f"{MES_BASE_URL}{page_info['url']}"
    start_ts = datetime.now()
    
    # 날짜 범위 파싱
    if "~" in target_date_str:
        start_date, end_date = target_date_str.split("~")
        date_label = target_date_str
    else:
        start_date = end_date = target_date_str
        date_label = target_date_str

    result = {
        "key": page_info["key"],
        "name": page_info["name"],
        "category": page_info["category"],
        "collected_at": start_ts.isoformat(),
        "date": date_label,
        "data": [],
        "record_count": 0,
        "error": None,
    }
    
    try:
        await page.goto(url, timeout=LONG_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=20000)
        
        # 로그인 페이지로 튕겼는지 체크
        if "Default.aspx" in page.url and "LogOut" not in page.url:
             raise Exception("Redirected to Login Page")

        if not page_info.get("has_table"):
            result["error"] = "테이블 없음"
            return result
        
        # 날짜 필터 설정
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
        
        # 테이블 데이터 추출
        table_id = page_info.get("table_id")
        if table_id:
            # 1. 스키마 변경 감지 (Schema Drift)
            current_headers = await page.evaluate(f"""(tid) => {{
                const table = document.getElementById(tid);
                if (!table) return [];
                const rows = Array.from(table.querySelectorAll('tr'));
                return Array.from(rows[0]?.querySelectorAll('th') || []).map(th => th.innerText.trim().replace(/\\n/g, ' '));
            }}""", table_id)
            
            expected_headers = page_info.get("columns", [])
            # 순서나 개수가 다르면 경고
            if expected_headers and current_headers != expected_headers:
                logger.warning("Schema Drift Detected", extra={
                    "page": page_info["key"],
                    "expected": expected_headers,
                    "current": current_headers
                })

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

        # 2. Data Lag & Payload Size
        payload_size = len(json.dumps(result["data"]))
        data_lag_sec = None
        
        # 데이터에 '일시', '시간' 등의 필드가 있으면 Lag 계산 시도
        if result["data"]:
            first_row = result["data"][0]
            time_str = first_row.get("일시") or first_row.get("생산일시") or first_row.get("작업일자")
            if time_str:
                try:
                    # 포맷이 다양할 수 있으므로 간단한 파싱 시도 (예: 2023-10-01 12:00:00)
                    # 실제 환경에 맞춰 포맷 추가 필요
                    data_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    data_lag_sec = (start_ts - data_time).total_seconds()
                except:
                    pass # 파싱 실패 시 무시

    except Exception as e:
        result["error"] = str(e)[:200]
        # ... (기존 스냅샷 로직) ...

    finally:
        # Latency Logging + New Metrics
        elapsed_ms = (datetime.now() - start_ts).total_seconds() * 1000
        logger.info(f"Page collection finished", extra={
            "page": page_info["key"],
            "duration_ms": elapsed_ms,
            "record_count": result["record_count"],
            "payload_bytes": payload_size if 'payload_size' in locals() else 0,
            "data_lag_sec": data_lag_sec if 'data_lag_sec' in locals() else None,
            "status": "error" if result["error"] else "success"
        })

    return result


from .db_manager import init_db, save_page_data

async def save_result(page_info, result, output_filename="today.json"):
    """결과 저장 (Hybrid: JSON File + SQLite DB)"""
    # Use folder_name from registry for directory, fallback to key
    key = page_info["key"]
    folder_name = MES_PAGES.get(key, {}).get("folder_name", key)
    
    save_dir = DATA_DIR / page_info["category"] / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)
    target_file = save_dir / output_filename
    
    old_data = []
    if target_file.exists():
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                old_result = json.load(f)
                old_data = old_result.get("data", [])
        except:
            pass
    
    change_info = detect_changes(old_data, result["data"])
    
    # 1. JSON File Write (Atomic)
    try:
        save_file_atomic(target_file, result)
    except Exception as e:
        logger.error(f"File Save failed for {key}", exc_info=e)
        return "⚠️ 파일저장실패"

    # 2. SQLite DB Write (New)
    try:
        if result["data"]:
            save_page_data(key, result["data"], result["record_count"])
    except Exception as e:
        logger.error(f"DB Save failed for {key}", exc_info=e)
        # DB 실패는 치명적이지 않으므로(파일이 있으니까) 로그만 남기고 진행
    
    if change_info["changed"] and not result["error"]:
        write_changelog(save_dir, page_info["key"], change_info)
        # 중요: 데이터 변경 감지 로그 (Audit)
        logger.info("Data changed", extra={
            "page": key,
            "diff": change_info["diff"],
            "old_count": change_info["old_count"],
            "new_count": change_info["new_count"]
        })
        return f"🔄 ({change_info['old_count']}→{change_info['new_count']})"
    elif result["error"]:
        return "❌"
    else:
        return f"✅ ({result['record_count']}건)"


async def worker(worker_id, page, pages_queue, results):
    """워커"""
    while True:
        try:
            item = pages_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        
        page_info, date_str, output_file = item
        result = await collect_page(page, page_info, date_str, output_file)
        status = await save_result(page_info, result, output_file)
        
        prefix = "[보정]" if "~" in date_str else "[실시간]"
        error_msg = f" - {result['error']}" if result["error"] else ""
        
        # 콘솔 출력은 유지하되, 상세 내용은 로거로
        print(f"[W{worker_id}]{prefix} {page_info['name']} {status}{error_msg}")
        results.append(result)


async def check_login_session(page, user_id, password):
    """로그인 세션 확인 및 복구 (Positive Check)"""
    try:
        current_url = page.url
        is_valid_session = "/P" in current_url and "Default.aspx" not in current_url
        
        if not is_valid_session:
            logger.warning("Invalid session detected, attempting relogin", extra={"url": current_url, "retry_attempt": 1})
            print(f"[세션복구] 유효하지 않은 세션 감지 (URL: {current_url[-20:]})... 재로그인 시도")
            
            await page.goto(LOGIN_URL)
            await page.wait_for_load_state("networkidle")
            
            if await page.query_selector(LOGIN_SELECTOR_ID):
                await page.fill(LOGIN_SELECTOR_ID, user_id)
                await page.fill(LOGIN_SELECTOR_PW, password)
                await page.click(LOGIN_SELECTOR_BTN)
                await page.wait_for_url("**/P00_DSH/**", timeout=20000)
                logger.info("Session recovery successful", extra={"retry_count": 1})
                print("[세션복구] 성공 ✅")
            else:
                 logger.error("Session recovery failed: Login page not loaded properly", extra={"retry_count": 1})
                 print("[세션복구] 로그인 페이지 로드 실패 (이미 로그인 상태일 수 있음)")
            
            return True
        return True
    except Exception as e:
        logger.error("Session check error", exc_info=e)
        print(f"[세션체크] 오류: {e}")
        return False


async def run_collection_cycle(pages, browser_pages, correction_index):
    """Micro-Batch 사이클 실행"""
    # 0. Circuit Breaker Check
    if not circuit_breaker.can_proceed():
        logger.warning(f"Circuit OPEN. Skipping cycle. (Data saved to DB: {circuit_breaker.last_failure_time})")
        print(f"⛔ [차단] 네트워크 불안정으로 30분간 휴식 중...")
        return 0, correction_index # 시간 소요 0으로 리턴하여 즉시 대기모드 진입

    start_time = datetime.now()
    today_str = start_time.strftime("%Y-%m-%d")
    
    from datetime import timedelta
    three_days_ago = (start_time - timedelta(days=2)).strftime("%Y-%m-%d")
    correction_range = f"{three_days_ago}~{today_str}"
    
    logger.info("Collection cycle started", extra={
        "correction_index": correction_index,
        "worker_count": len(browser_pages),
        "circuit_state": circuit_breaker.state
    })
    
    print(f"\n{'='*60}")
    print(f"[{start_time.strftime('%H:%M:%S')}] 수집 사이클 시작 (보정: {correction_index})")
    print(f"{'='*60}")
    
    pages_queue = asyncio.Queue()
    valid_pages = [p for p in pages if p["key"] not in IGNORE_PAGES]
    
    # ... (큐 채우기 로직은 동일) ...
    # 1. [실시간] 오늘 데이터
    for p in valid_pages:
        pages_queue.put_nowait((p, today_str, "today.json"))
        
    # 2. [보정] 최근 3일 데이터 (5개씩)
    batch_size = 5
    start_idx = correction_index % len(valid_pages)
    
    doubled_pages = valid_pages * 2 
    correction_targets = doubled_pages[start_idx : start_idx + batch_size]

    for p in correction_targets:
        pages_queue.put_nowait((p, correction_range, "recent.json"))

    results = []
    tasks = [
        asyncio.create_task(worker(i, browser_pages[i], pages_queue, results))
        for i in range(len(browser_pages))
    ]
    await asyncio.gather(*tasks)
    
    total_records = sum(r["record_count"] for r in results if not r.get("error"))
    errors = sum(1 for r in results if r.get("error"))
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Circuit Breaker Logic Update
    error_rate = errors / len(results) if results else 0
    if error_rate > 0.8: # 80% 이상 실패 시 네트워크 장애로 간주
        circuit_breaker.record_failure()
        logger.warning(f"High error rate detected: {error_rate:.1%}", extra={"failures": circuit_breaker.failure_count})
    else:
        circuit_breaker.record_success()

    logger.info("Collection cycle finished", extra={
        "elapsed_sec": elapsed,
        "total_records": total_records,
        "error_count": errors
    })
    
    print(f"\n[완료] {len(results)}건 처리 | {total_records} 레코드 | {errors} 오류 | {elapsed:.1f}초")
    
    return elapsed, (start_idx + batch_size) % len(valid_pages)


async def run_browser_session(cycle_limit, user_id, password, pages, start_correction_index):
    """브라우저 세션 실행 (Self-Healing 단위)"""
    logger.info("Browser session starting", extra={"cycle_limit": cycle_limit})
    print(f"\n🚀 [브라우저 시작] {cycle_limit} 사이클 후 재시작 예정")
    
    correction_index = start_correction_index

    current_loop = asyncio.get_running_loop()
    if _should_use_threaded_loop(current_loop):
        logger.error(
            "SelectorEventLoop detected on Windows. "
            "Playwright requires ProactorEventLoop for subprocess spawning."
        )
        return correction_index
    
    
    # EXE 환경에서 시스템에 설치된 브라우저를 찾도록 강제 설정
    if getattr(sys, 'frozen', False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            standard_path = os.path.join(local_app_data, "ms-playwright")
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = standard_path
            logger.info(f"EXE mode: Force PLAYWRIGHT_BROWSERS_PATH to {standard_path}")

    async with async_playwright() as p:
        try:
            # 메모리 최적화 플래그
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--mute-audio',
                    '--no-first-run',
                    '--safebrowsing-disable-auto-update',
                    '--js-flags=--max-old-space-size=256',
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                java_script_enabled=True,
            )
        except Exception as e:
            logger.error("Failed to launch browser", exc_info=e)
            print(f"❌ [에러] 브라우저 실행 실패: {e}")
            print("💡 해결방법: 'playwright install chromium' 명령어로 브라우저를 설치했는지 확인해주세요.")
            return start_correction_index
        
        # 최초 로그인
        login_page = await context.new_page()
        await login_page.goto(LOGIN_URL)
        await login_page.fill(LOGIN_SELECTOR_ID, user_id)
        await login_page.fill(LOGIN_SELECTOR_PW, password)
        await login_page.click(LOGIN_SELECTOR_BTN)
        
        try:
            await login_page.wait_for_url("**/P00_DSH/**", timeout=20000)
            logger.info("Initial login successful")
            print("[초기화] 로그인 성공")
        except:
            logger.error("Initial login failed")
            print("[초기화] 로그인 실패 - 재시도 대기")
            await browser.close()
            return correction_index
            
        browser_pages = [login_page]
        for _ in range(NUM_WORKERS - 1):
            browser_pages.append(await context.new_page())
            
        for i in range(cycle_limit):
            try:
                # 사이클 시작 전 세션 점검 (첫번째 탭 이용)
                if not await check_login_session(browser_pages[0], user_id, password):
                    logger.warning("Session check failed. Restarting browser session.")
                    print("⚠️ [세션오류] 세션 점검 실패. 브라우저를 재시작합니다.")
                    break
                
                elapsed, next_idx = await run_collection_cycle(pages, browser_pages, correction_index)
                correction_index = next_idx
                
                wait_time = max(0, INTERVAL_SECONDS - elapsed)
                
                # 메모리 최적화: 사이클 종료 후 GC 강제 호출
                collected = gc.collect()
                if collected > 0:
                    logger.debug(f"GC collected {collected} objects after cycle {i+1}")
                
                print(f"[대기] {wait_time:.0f}초 (사이클 {i+1}/{cycle_limit})")
                await asyncio.sleep(wait_time)
                
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except Exception as e:
                logger.error(f"Cycle error in cycle {i}", exc_info=e)
                print(f"[사이클오류] {e}")
                # Jitter Backoff: 10초 ~ 30초 사이 랜덤 대기 (서버 충돌 방지)
                backoff_time = random.uniform(10, 30)
                print(f"⚠️ 안정화를 위해 {backoff_time:.1f}초 대기 후 재시도...")
                await asyncio.sleep(backoff_time)
        
        logger.info("Browser session ending for restart")
        print("🧹 [브라우저 종료] Self-Healing 재시작")
        await browser.close()
        
        # 메모리 최적화: 브라우저 종료 후 강제 GC
        gc_count = gc.collect()
        logger.info(f"Post-browser GC collected {gc_count} objects")
        
    return correction_index


_scheduler_task: Optional[asyncio.Task] = None
_scheduler_loop: Optional[asyncio.AbstractEventLoop] = None
_scheduler_thread: Optional[threading.Thread] = None


def _has_reload_flag(argv: list[str]) -> bool:
    return any(arg == "--reload" or arg.startswith("--reload=") for arg in argv)


def _is_uvicorn_reload_mode() -> bool:
    env_reload = os.getenv("UVICORN_RELOAD", "").strip().lower()
    if env_reload in {"1", "true", "yes", "on"}:
        return True
    return _has_reload_flag(sys.argv)


def _reload_guard_disabled() -> bool:
    # Escape hatch for local debugging.
    allow_reload = os.getenv("MES_SCHEDULER_ALLOW_RELOAD", "").strip().lower()
    return allow_reload in {"1", "true", "yes", "on"}


def _should_skip_scheduler_for_reload() -> bool:
    return sys.platform == "win32" and _is_uvicorn_reload_mode() and not _reload_guard_disabled()


def _should_use_threaded_loop(loop: asyncio.AbstractEventLoop) -> bool:
    # On Windows + uvicorn --reload, SelectorEventLoop has no subprocess support.
    return sys.platform == "win32" and isinstance(loop, asyncio.SelectorEventLoop)


def _create_scheduler_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


def _scheduler_thread_main():
    global _scheduler_task
    global _scheduler_loop
    global _scheduler_thread

    loop = _create_scheduler_loop()
    _scheduler_loop = loop
    asyncio.set_event_loop(loop)
    _scheduler_task = loop.create_task(main_loop())

    try:
        loop.run_until_complete(_scheduler_task)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.critical("Scheduler thread crashed", exc_info=e)
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        _scheduler_task = None
        _scheduler_loop = None
        _scheduler_thread = None

async def main_loop():
    logger.info("MES Scheduler starting")
    print("=" * 60)
    print(f"MES Scheduler Robust v1.0 (Managed)")
    print(f"- Workers: {NUM_WORKERS}")
    print(f"- Restart: Every {BROWSER_RESTART_CYCLES} cycles")
    print("=" * 60)
    
    # Initialize DB (Hybrid Storage)
    try:
        init_db()
    except Exception as e:
        logger.critical("DB Initialization failed", exc_info=e)
        print("❌ [경고] DB 초기화 실패 (파일 저장만 수행됩니다)")

    correction_index = 0
    structures = load_page_structures()
    pages = structures["pages"]
    
    while True:
        try:
            # 운영 시간 체크 (매 루프마다 동적으로 확인)
            if not is_within_operating_hours():
                start_hour, end_hour = get_operating_hours()
                wait_sec = seconds_until_start()
                next_start = datetime.now() + timedelta(seconds=wait_sec)
                
                logger.info(f"Outside operating hours ({start_hour}:00~{end_hour}:00). "
                           f"Sleeping until {next_start.strftime('%H:%M')}")
                print(f"💤 [휴식] 운영 시간 외 ({start_hour}:00~{end_hour}:00)")
                print(f"    다음 시작: {next_start.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 최대 5분마다 재확인 (설정 변경 반영을 위해)
                await asyncio.sleep(min(wait_sec, 300))
                continue
            
            # 매 세션 시작 시 최신 계정 정보 로드
            current_user, current_pw = get_credentials()
            
            if not current_user or not current_pw:
                logger.warning("MES credentials missing. Waiting 60s...")
                print("⚠️ [대기] MES 계정 정보가 설정되지 않았습니다.")
                await asyncio.sleep(60)
                continue

            correction_index = await run_browser_session(
                BROWSER_RESTART_CYCLES, 
                current_user, 
                current_pw, 
                pages, 
                correction_index
            )
            await asyncio.sleep(5)
            
        except asyncio.CancelledError:
            logger.info("Scheduler task cancelled")
            break
        except Exception as e:
            logger.critical("Fatal error in scheduler loop", exc_info=e)
            print(f"[치명적 오류] {e}")
            await asyncio.sleep(30)

async def start():
    """스케줄러 시작 (이미 실행 중이면 무시)"""
    global _scheduler_task
    global _scheduler_loop
    global _scheduler_thread

    if is_running():
        logger.info("Scheduler already running")
        return

    if _should_skip_scheduler_for_reload():
        logger.warning(
            "Scheduler start skipped in Windows uvicorn --reload mode. "
            "Set MES_SCHEDULER_ALLOW_RELOAD=1 to force enable."
        )
        print(
            "[MES Scheduler] Skipped in --reload mode on Windows. "
            "Set MES_SCHEDULER_ALLOW_RELOAD=1 to enable."
        )
        return
    
    loop = asyncio.get_running_loop()
    if _should_use_threaded_loop(loop):
        _scheduler_thread = threading.Thread(
            target=_scheduler_thread_main,
            name="mes-scheduler-loop",
            daemon=True,
        )
        _scheduler_thread.start()
        logger.info("Scheduler task started in dedicated loop thread")
        return

    _scheduler_loop = loop
    _scheduler_task = loop.create_task(main_loop())
    logger.info("Scheduler task started on current loop")

async def stop():
    """스케줄러 정지"""
    global _scheduler_task
    global _scheduler_loop
    global _scheduler_thread

    if _scheduler_thread and _scheduler_thread.is_alive():
        loop = _scheduler_loop
        task = _scheduler_task
        if loop and task and not task.done():
            loop.call_soon_threadsafe(task.cancel)
        await asyncio.to_thread(_scheduler_thread.join, 10)
        if _scheduler_thread and _scheduler_thread.is_alive():
            logger.warning("Scheduler thread did not stop within timeout")
        else:
            logger.info("Scheduler task stopped")
        return

    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        finally:
            _scheduler_task = None
            _scheduler_loop = None
        logger.info("Scheduler task stopped")

def is_running():
    """실행 상태 확인"""
    if _scheduler_thread and _scheduler_thread.is_alive():
        return True
    return _scheduler_task is not None and not _scheduler_task.done()

async def restart():
    """스케줄러 재시작 (설정 변경 시 호출)"""
    if _should_skip_scheduler_for_reload():
        logger.info("Scheduler restart skipped in Windows uvicorn --reload mode")
        return

    await stop()
    await asyncio.sleep(1)  # 약간의 지연 후 시작 (취소 완료 보장)
    await start()



if __name__ == "__main__":
    asyncio.run(main())
