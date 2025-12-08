# modules/logger.py
import os
import csv
import datetime
import queue
import logging
from config import CSV_HEADER, LOG_PATH

def setup_system_logger():
    """ 시스템 로그 설정 (system.log) """
    logger = logging.getLogger("SystemLogger")
    logger.setLevel(logging.INFO)
    
    # 파일 핸들러 (시스템 로그도 LOG_PATH에 저장하려면 경로 수정 필요, 일단 유지)
    file_handler = logging.FileHandler("system.log", encoding="utf-8")
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러 (선택 사항: 콘솔에도 에러 출력)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 전역 로거 인스턴스
sys_logger = setup_system_logger()

def open_log_file(timestamp_str):
    filename = f"Factory_Integrated_Log_{timestamp_str}.csv"
    full_path = os.path.join(LOG_PATH, filename) # [수정] 설정된 경로 사용
    try:
        f = open(full_path, "a", newline="", encoding="utf-8-sig")
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(CSV_HEADER)
            f.flush()
        sys_logger.info(f"CSV Log file opened: {full_path}")
        return f, writer
    except Exception as e:
        sys_logger.error(f"Failed to open CSV log file: {e}")
        return None, None

import time

def file_writer_thread(data_queue):
    current_date_str = datetime.datetime.now().strftime("%Y%m%d")
    current_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    f, writer = open_log_file(current_timestamp)
    
    buffer = []
    BATCH_SIZE = 20
    FLUSH_INTERVAL = 1.0 # seconds
    last_flush_time = time.time()
    
    while True:
        try:
            # 0.1 sec connection to avoid busy loop but fast enough
            try:
                item = data_queue.get(timeout=0.2)
                if item is None: break # Stop signal
                buffer.append(item)
                data_queue.task_done()
            except queue.Empty:
                pass
            
            # Flush Logic
            current_time = time.time()
            if buffer and (len(buffer) >= BATCH_SIZE or (current_time - last_flush_time) > FLUSH_INTERVAL):
                if not f: # Re-open if closed (redundancy)
                     f, writer = open_log_file(datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
                
                # Check date rotation first based on first item in buffer
                first_item_timestamp = buffer[0][1]
                today_str = first_item_timestamp.strftime("%Y%m%d")
                
                if today_str != current_date_str:
                    if f: f.close()
                    sys_logger.info("Log Rotation Triggered.")
                    current_date_str = today_str
                    new_timestamp = first_item_timestamp.strftime("%Y%m%d_%H%M%S")
                    f, writer = open_log_file(new_timestamp)
                
                if writer:
                    writer.writerows([row for row, _ in buffer])
                    f.flush()
                    
                buffer.clear()
                last_flush_time = current_time
                
        except Exception as e:
            sys_logger.error(f"Error in file_writer_thread: {e}")
            if buffer: buffer.clear() # Prevent sticking error loop
            
    # Final Flush on exit
    if f and buffer:
        try:
            writer.writerows([row for row, _ in buffer])
            f.flush()
        except: pass
        
    if f: f.close()
    sys_logger.info("File writer thread stopped.")
