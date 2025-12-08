# main.py
import time
import datetime
import queue
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
from gui import SmartFactoryApp

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
                ls.get('At_Temp', "") if ls.get('At_Temp') is not None else ""
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

            try: 
                log_queue.put((row, now), timeout=0.1)
                gui_queue.put(ui_data, timeout=0.1)
            except queue.Full:
                sys_logger.warning("Queue full!")
                pass

            sleep_time = next_tick - time.time()
            if sleep_time > 0: time.sleep(sleep_time)

    except Exception as e:
        print(f"\n❌ 데이터 수집 중 에러: {e}")
        sys_logger.critical(f"Data loop exception: {e}", exc_info=True)
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
    log_queue = queue.Queue(maxsize=1000) # [Memory Optimization] 5000 -> 1000
    gui_queue = queue.Queue(maxsize=1000)
    
    # 파일 쓰기 스레드
    writer_thread = threading.Thread(target=file_writer_thread, args=(log_queue,), daemon=True)
    writer_thread.start()

    # 데이터 수집 스레드
    data_thread = threading.Thread(target=data_collection_loop, args=(log_queue, gui_queue), daemon=True)
    data_thread.start()

    # GUI 실행 (메인 스레드)
    try:
        app = SmartFactoryApp(gui_queue)
        
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
        log_queue.put(None)
        writer_thread.join(timeout=2.0)
        data_thread.join(timeout=2.0)
        sys_logger.info("Application exit.")
        print("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    run_logger()
