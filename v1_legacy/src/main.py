# main.py
import time
import datetime
import queue
import collections
import threading
import concurrent.futures
import sys
import signal
import atexit

from config import (
    DEVICE_NAME, INTERVAL_SEC, APP_DATA_DIR,
    IP_EXT, PORT_EXT, 
    IP_LS, PORT_LS, 
    CONSOLE_HEADER
)
from modules.extruder import ExtruderClient
from modules.ls_plc import LSPLCClient
from modules.spot import get_spot_temp
from modules.logger import file_writer_thread, sys_logger
from modules.logic_processor import LogicProcessor
from gui import SmartFactoryApp
import os
import traceback

# ---------------------------------------------------------------------------
# [Global Exception Handler] Crash Dump
# ---------------------------------------------------------------------------
def exception_hook(exctype, value, tb):
    if issubclass(exctype, KeyboardInterrupt):
        sys.__excepthook__(exctype, value, tb)
        return

    from config import LOG_PATH
    try:
        if not os.path.exists(LOG_PATH): os.makedirs(LOG_PATH)
        log_file = os.path.join(LOG_PATH, "crash.log")
        
        err_msg = "".join(traceback.format_exception(exctype, value, tb))
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*40}\n[{timestamp}] UNHANDLED EXCEPTION\n{'='*40}\n")
            f.write(err_msg)
            f.write("-" * 80 + "\n")
            
        print(f"\n[CRITICAL] Error logged to: {log_file}", file=sys.stderr)
        
        # GUI Alert (Optional, only if GUI is likely dead)
        try:
            import tkinter.messagebox
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            tkinter.messagebox.showerror("Fatal Error", f"A critical error occurred.\nProgram must terminate.\n\nLog: {log_file}")
            root.destroy()
        except: pass

    except Exception as e:
        print(f"Failed to log crash: {e}", file=sys.stderr)
    
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

def safe_fmt(val, fmt_str):
    if val is None: return " null"
    try: return f"{val:{fmt_str}}"
    except: return " null"

# 전역 플래그
running = True
app = None
_lock_fd = None

def _pid_is_alive(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True

def release_single_instance_lock():
    global _lock_fd
    lock_path = os.path.join(APP_DATA_DIR, "app.lock")
    try:
        if _lock_fd is not None:
            os.close(_lock_fd)
            _lock_fd = None
    except Exception:
        pass
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass

def acquire_single_instance_lock():
    global _lock_fd
    lock_path = os.path.join(APP_DATA_DIR, "app.lock")
    try:
        _lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_lock_fd, str(os.getpid()).encode("ascii", errors="ignore"))
        atexit.register(release_single_instance_lock)
        return True
    except FileExistsError:
        existing_pid = 0
        try:
            with open(lock_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if raw.isdigit():
                    existing_pid = int(raw)
        except Exception:
            existing_pid = 0

        if existing_pid and _pid_is_alive(existing_pid):
            sys_logger.error(f"Another instance is already running (pid={existing_pid}). Exiting.")
            return False

        # Stale lock detected; remove and retry once
        try:
            os.remove(lock_path)
        except Exception:
            sys_logger.error("Stale lock detected but could not remove. Exiting.")
            return False
        return acquire_single_instance_lock()
    except Exception as e:
        sys_logger.warning(f"Failed to acquire single instance lock: {e}")
        return True

def signal_handler(sig, frame):
    global running
    print("\n[System] 종료 시그널 감지. 안전하게 종료 중입니다...")
    sys_logger.info(f"Shutdown signal received: {sig}")
    running = False
    if app: app.quit()

def data_collection_loop(log_queue, gui_queue):
    global running
    
    print(f"=== [모듈화 버전] 스마트 팩토리 통합 로거 ===")
    print(f"장비명: {DEVICE_NAME}")
    print(f"압출기: {IP_EXT}:{PORT_EXT}")
    print(f"LS PLC: {IP_LS}:{PORT_LS}")
    print("-" * 180)
    print(CONSOLE_HEADER)
    print("-" * 180)

    sys_logger.info("Data collection thread started.")

    # 클라이언트 초기화
    extruder = ExtruderClient(IP_EXT, PORT_EXT)
    ls_plc = LSPLCClient(IP_LS, PORT_LS)
    
    # [New] Logic Processor 초기화
    logic_processor = LogicProcessor()
    
    # 스레드 풀
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    
    next_tick = time.time()
    last_q_log = 0
    last_gui_warn = 0

    try:
        while running:
            next_tick += INTERVAL_SEC
            now = datetime.datetime.now()
            date_s = now.strftime("%Y-%m-%d")
            time_s = now.strftime("%H:%M:%S.%f")[:-3]

            # 병렬 데이터 수집
            future_spot = executor.submit(get_spot_temp)
            future_ext  = executor.submit(extruder.get_data)
            future_ls   = executor.submit(ls_plc.get_data)
            
            spot = future_spot.result()
            ext  = future_ext.result()
            ls   = future_ls.result()

            mold1 = ls.get('Mold1')
            mold2 = ls.get('Mold2')
            mold3 = ls.get('Mold3')
            mold4 = ls.get('Mold4')
            mold5 = ls.get('Mold5')
            mold6 = ls.get('Mold6')
            billet_temp = ls.get('Billet_Temp')
            at_pre = ls.get('At_Pre')
            at_temp = ls.get('At_Temp')

            # 콘솔 출력 (선택 사항: GUI가 있으면 줄여도 됨)
            # print(f" {time_s} | ...") 

            # [New] Logic Processor Update
            # count, pressure, speed, timestamp
            die_id, billet_cycle_id = logic_processor.update(
                ext.get('Count'), 
                ext.get('Press'), 
                ext.get('Speed'), 
                now
            )

            # CSV 저장용 데이터
            row = [
                date_s, time_s, 
                spot if spot is not None else "",
                ext['Press'] if ext['Press'] is not None else "",
                ext['Billet'] if ext['Billet'] is not None else "",
                ext['Temp_F'] if ext['Temp_F'] is not None else "",
                ext['Temp_B'] if ext['Temp_B'] is not None else "",
                ext['Count'] if ext['Count'] is not None else "",
                ext['Speed'] if ext['Speed'] is not None else "",
                ext['EndPos'] if ext['EndPos'] is not None else "",
                mold1 if mold1 is not None else "",
                mold2 if mold2 is not None else "",
                mold3 if mold3 is not None else "",
                mold4 if mold4 is not None else "",
                mold5 if mold5 is not None else "",
                mold6 if mold6 is not None else "",
                billet_temp if billet_temp is not None else "",
                at_pre if at_pre is not None else "",
                at_temp if at_temp is not None else "",
                # [New] Columns
                die_id if die_id else "",
                billet_cycle_id if billet_cycle_id is not None else ""
            ]
            
            # GUI 업데이트용 데이터 딕셔너리
            ui_data = {
                'Time': now, # [수정] 타임스탬프 추가 (수집 시간 기준)
                'Speed': ext.get('Speed'), 'Press': ext.get('Press'), 'Count': ext.get('Count'), 'EndPos': ext.get('EndPos'),
                'Billet': ext.get('Billet'), # [수정] 빌렛 길이 추가
                'Spot': spot, 'Temp_F': ext.get('Temp_F'), 'Temp_B': ext.get('Temp_B'),
                'Billet_Temp': billet_temp, # PLC Billet Temp
                'Mold1': mold1, 'Mold2': mold2, 'Mold3': mold3,
                'Mold4': mold4, 'Mold5': mold5, 'Mold6': mold6,
                'At_Temp': at_temp, 'At_Pre': at_pre
            }

            # [Queue Logic] Deque Append (Ring Buffer)
            # Check for fullness before append to trigger warning
            log_full = len(log_queue) >= log_queue.maxlen
            gui_full = len(gui_queue) >= gui_queue.maxlen
            
            log_queue.append((row, now))
            gui_queue.append(ui_data)

            if log_full or gui_full:
                now_ts = time.time()
                if now_ts - last_q_log > 5.0:
                    sys_logger.warning(
                        f"Queue full! drop oldest data. log={len(log_queue)}/{log_queue.maxlen}, "
                        f"gui={len(gui_queue)}/{gui_queue.maxlen}"
                    )
                    last_q_log = now_ts
                if now_ts - last_gui_warn > 2.0:
                    gui_queue.append({'warning': 'Queue Full'})
                    last_gui_warn = now_ts

            sleep_time = next_tick - time.time()
            if sleep_time > 0: time.sleep(sleep_time)

    except Exception as e:
        err_msg = f"Data Loop Error: {e}"
        print(f"\n❌ {err_msg}")
        sys_logger.critical(err_msg, exc_info=True)
        # [Fix] Send error to GUI so user can see it
        try: gui_queue.append({'error': str(e)})
        except: pass
    finally:
        executor.shutdown(wait=False)
        try: extruder.close()
        except: pass
        try: ls_plc.close()
        except: pass
        sys_logger.info("Data collection thread stopped.")

def run_logger():
    global running, app
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not acquire_single_instance_lock():
        return

    # 큐 생성 (버퍼 최적화)
    # 큐 생성 (버퍼 최적화: Ring Buffer using Deque)
    log_queue = collections.deque(maxlen=5000) 
    gui_queue = collections.deque(maxlen=5000)
    
    # 파일 쓰기 스레드
    writer_thread = threading.Thread(target=file_writer_thread, args=(log_queue,), daemon=True)
    writer_thread.start()

    # 데이터 수집 스레드
    data_thread = threading.Thread(target=data_collection_loop, args=(log_queue, gui_queue), daemon=True)
    data_thread.start()

    # GUI 실행 (메인 스레드)
    try:
        app = SmartFactoryApp(gui_queue)
        
        # [Splash Screen] Close splash when UI is ready (only in frozen EXE)
        if getattr(sys, 'frozen', False):
            try:
                import pyi_splash
                # Wait a tiny bit (optional) or just close
                # You can also update text: pyi_splash.update_text('Starting UI...')
                pyi_splash.close()
            except: pass
        
        # 윈도우 닫기 버튼 처리
        def on_close():
            global running
            running = False
            app.destroy()
            
        app.protocol("WM_DELETE_WINDOW", on_close)
        app.mainloop()
        
    except Exception as e:
        print(f"GUI Error: {e}")
    finally:
        running = False
        print("종료 처리 중...")
        log_queue.append(None)
        writer_thread.join(timeout=2.0)
        data_thread.join(timeout=2.0)
        sys_logger.info("Application exit.")
        release_single_instance_lock()
        print("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    run_logger()
