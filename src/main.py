# main.py
import time
import datetime
import queue
import collections
import threading
import concurrent.futures
import sys
import signal

from config import (
    DEVICE_NAME, INTERVAL_SEC, 
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
                ls['Mold1'] if ls['Mold1'] is not None else "",
                ls['Mold2'] if ls['Mold2'] is not None else "",
                ls['Mold3'] if ls['Mold3'] is not None else "",
                ls['Mold4'] if ls['Mold4'] is not None else "",
                ls.get('Mold5', "") if ls.get('Mold5') is not None else "",
                ls.get('Mold6', "") if ls.get('Mold6') is not None else "",
                ls.get('Billet_Temp', "") if ls.get('Billet_Temp') is not None else "",
                ls.get('At_Pre', "") if ls.get('At_Pre') is not None else "",
                ls.get('At_Temp', "") if ls.get('At_Temp') is not None else "",
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
                'Billet_Temp': ls.get('Billet_Temp'), # PLC Billet Temp
                'Mold1': ls.get('Mold1'), 'Mold2': ls.get('Mold2'), 'Mold3': ls.get('Mold3'),
                'Mold4': ls.get('Mold4'), 'Mold5': ls.get('Mold5'), 'Mold6': ls.get('Mold6'),
                'At_Temp': ls.get('At_Temp'), 'At_Pre': ls.get('At_Pre')
            }

            # [Queue Logic] Deque Append (Ring Buffer)
            # Check for fullness before append to trigger warning
            is_queue_full = False
            if len(log_queue) >= log_queue.maxlen or len(gui_queue) >= gui_queue.maxlen:
                is_queue_full = True
            
            log_queue.append((row, now))
            gui_queue.append(ui_data)

            if is_queue_full:
                sys_logger.warning("Queue full! Ring Buffer dropped oldest data.")
                # Throttle GUI Warning (Once every 2 seconds)
                if 'last_q_warn' not in locals(): last_q_warn = 0
                if time.time() - last_q_warn > 2.0:
                    gui_queue.append({'warning': 'Queue Full'})
                    last_q_warn = time.time()

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

    # 큐 생성 (버퍼 최적화)
    # 큐 생성 (버퍼 최적화: Ring Buffer using Deque)
    log_queue = collections.deque(maxlen=1000) 
    gui_queue = collections.deque(maxlen=1000)
    
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
        print("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    run_logger()
