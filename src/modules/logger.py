# modules/logger.py
import os
import csv
import datetime
import queue
import logging
from config import CSV_HEADER, LOG_PATH, AUTO_SAVE, APP_DATA_DIR, ROTATION_MODE, CYCLE_IDLE_TIME, CYCLE_THRESHOLD_PRESS
from logging.handlers import RotatingFileHandler

def setup_system_logger():
    """ 시스템 로그 설정 (system.log, 10MB x 5 Backups) """
    logger = logging.getLogger("SystemLogger")
    logger.setLevel(logging.INFO)
    
    # [Fix] Use APPDATA path strictly
    logs_dir = os.path.join(APP_DATA_DIR, "logs")
    if not os.path.exists(logs_dir):
        try: os.makedirs(logs_dir)
        except: pass
        
    sys_log_path = os.path.join(logs_dir, "system.log")
    
    # [Stability] Rotating Log Handler with Fallback for Overlap Update
    try:
        file_handler = RotatingFileHandler(
            sys_log_path, 
            maxBytes=10*1024*1024, # 10 MB
            backupCount=5,         # Keep 5 Backups
            encoding="utf-8"
        )
    except PermissionError:
        # Fallback: Add PID to filename if locked (Overlap running)
        # This allows running New Version while Old Version is still active
        pid = os.getpid()
        sys_log_path = os.path.join(logs_dir, f"system_{pid}.log")
        file_handler = RotatingFileHandler(
            sys_log_path, 
            maxBytes=10*1024*1024, 
            backupCount=5, 
            encoding="utf-8"
        )
        
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

def open_log_file(timestamp_str, prefix="Factory_Integrated_Log"):
    if not AUTO_SAVE:
        return None, None
        
    filename = f"{prefix}_{timestamp_str}.csv"
    full_path = os.path.join(LOG_PATH, filename)
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
    
    # [Cycle Logic]
    # Default prefix is Factory_Integrated_Log
    # Even in BILLET mode, user requested consistent naming
    file_prefix = "Factory_Integrated_Log"
    # if ROTATION_MODE == "BILLET":
    #    file_prefix = "Billet"
        
    f, writer = open_log_file(current_timestamp, prefix=file_prefix)
    
    buffer = []
    BATCH_SIZE = 20
    FLUSH_INTERVAL = 1.0 # seconds
    last_flush_time = time.time()
    
    # [Cycle Logic State]
    cycle_idle_start = 0
    is_cycle_armed = False
    
    while True:
        try:
            # 0.1 sec connection to avoid busy loop but fast enough
            try:
                item = None
                if hasattr(data_queue, 'get'):
                    item = data_queue.get(timeout=0.2)
                else:
                    # Deque Support
                    if len(data_queue) > 0:
                        item = data_queue.popleft()
                    else:
                        time.sleep(0.1)
                        continue
                        
                if item is None: break # Stop signal
                buffer.append(item)
                
                # [Cycle Logic] Check Pressure for Splitting
                if ROTATION_MODE == "BILLET" and item:
                    row, _ = item
                    # CSV Index 3 = Main Press (Check modules/logger.py or config.py CSV_HEADER)
                    # "Date,Time,Temperature,메인압력..." -> Index 3 is '메인압력'
                    try: 
                        current_press = float(row[3])
                        
                        # 1. Idle Detection (Press < 10 for N sec)
                        # We use 10 bar (safe low) hardcoded or maybe 50% of Threshold
                        idle_threshold = 10.0 
                        
                        if current_press < idle_threshold:
                            if cycle_idle_start == 0:
                                cycle_idle_start = time.time()
                            elif (time.time() - cycle_idle_start) > CYCLE_IDLE_TIME:
                                if not is_cycle_armed:
                                    sys_logger.info(f"Cycle Armed (Idle > {CYCLE_IDLE_TIME}s)")
                                is_cycle_armed = True
                        else:
                            # Reset idle timer if pressure rises (but keep ARMED if valid)
                            cycle_idle_start = 0
                            
                            # 2. Trigger Detection (Armed & Press > Threshold)
                            if is_cycle_armed and current_press >= CYCLE_THRESHOLD_PRESS:
                                sys_logger.info(f"New Cycle Triggered! (Press: {current_press})")
                                
                                # Split File
                                if f: f.close()
                                
                                # New Timestamp & Reset State
                                new_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                f, writer = open_log_file(new_ts, prefix="Factory_Integrated_Log")
                                
                                is_cycle_armed = False # Reset Arm
                    except (ValueError, IndexError):
                        pass

                if hasattr(data_queue, 'task_done'):
                    data_queue.task_done()
            except queue.Empty:
                pass
            
            # Flush Logic
            current_time = time.time()
            if buffer and (len(buffer) >= BATCH_SIZE or (current_time - last_flush_time) > FLUSH_INTERVAL):
                if not f: # Re-open if closed (redundancy)
                     f, writer = open_log_file(datetime.datetime.now().strftime("%Y%m%d_%H%M%S"), prefix=file_prefix)
                
                # Check date rotation first based on first item in buffer (Only for DAILY mode)
                if ROTATION_MODE == "DAILY":
                    first_item_timestamp = buffer[0][1]
                    today_str = first_item_timestamp.strftime("%Y%m%d")
                    
                    if today_str != current_date_str:
                        if f: f.close()
                        sys_logger.info("Log Rotation Triggered.")
                        current_date_str = today_str
                        new_timestamp = first_item_timestamp.strftime("%Y%m%d_%H%M%S")
                        f, writer = open_log_file(new_timestamp, prefix=file_prefix)
                
                if writer and AUTO_SAVE:
                    writer.writerows([row for row, _ in buffer])
                    f.flush()
                # If not AUTO_SAVE, just clear buffer (data is lost intentionally)
                    
                buffer.clear()
                last_flush_time = current_time
                
        except Exception as e:
            sys_logger.error(f"Error in file_writer_thread: {e}")
            # [Fix] Reset file handle to force re-open on next attempt
            if f:
                try: f.close()
                except: pass
            f, writer = None, None
            
            if buffer: buffer.clear() # Prevent sticking error loop
            
    # Final Flush on exit
    if f and buffer:
        try:
            writer.writerows([row for row, _ in buffer])
            f.flush()
        except: pass
        
    if f: f.close()
    sys_logger.info("File writer thread stopped.")
