import time
import threading
import queue
import csv
import logging
from datetime import datetime
from pathlib import Path
import sys
import os

# --- MOCK MODELS & SERVICE ---

class FactoryData:
    def __init__(self, Time, Spot, Press, Temp_F, Temp_B, Count, **kwargs):
        self.Time = Time
        self.Spot = Spot
        self.Press = Press
        self.Temp_F = Temp_F
        self.Temp_B = Temp_B
        self.Count = Count
        
        # Populate optional fields
        self.Billet_Length = kwargs.get('Billet_Length')
        self.Speed = kwargs.get('Speed')
        self.EndPos = kwargs.get('EndPos')
        self.Mold1 = kwargs.get('Mold1')
        self.Mold2 = kwargs.get('Mold2')
        self.Mold3 = kwargs.get('Mold3')
        self.Mold4 = kwargs.get('Mold4')
        self.Mold5 = kwargs.get('Mold5')
        self.Mold6 = kwargs.get('Mold6')
        self.Billet_Temp = kwargs.get('Billet_Temp')
        self.At_Pre = kwargs.get('At_Pre')
        self.At_Temp = kwargs.get('At_Temp')
        self.Die_ID = kwargs.get('Die_ID')
        self.Billet_Cycle_ID = kwargs.get('Billet_Cycle_ID')

class StandaloneCSVLogger:
    def __init__(self):
        self.running = False
        self.thread = None
        self.queue = queue.Queue(maxsize=5000)
        self.active_log_dir = Path("perf_test_logs")
        
        # Standard Header
        self.csv_header = [
            "Date", "Time", "Spot_Temp", "Press_Value", "Billet_Len", 
            "Temp_F", "Temp_B", "Count", "Speed", "EndPos", 
            "Mold1", "Mold2", "Mold3", "Mold4", "Mold5", "Mold6",
            "Billet_Temp", "At_Pre", "At_Temp", "Die_ID", "Billet_Cycle_ID"
        ]
        
    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
    def _open_file(self, prefix="PerfTest"):
        self.active_log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{ts}.csv"
        path = self.active_log_dir / filename
        f = open(path, "a", newline="", encoding="utf-8-sig")
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(self.csv_header)
        return f, writer

    def _loop(self):
        buffer = []
        batch_size = 20
        flush_interval = 1.0
        last_flush = time.time()
        
        f, writer = self._open_file()
        
        while self.running or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
                # Parse timestamp
                try:
                    dt = datetime.fromisoformat(item.Time)
                except:
                    dt = datetime.now()
                
                # Build Row (Full Data)
                row = [
                    dt.strftime("%Y-%m-%d"),
                    dt.strftime("%H:%M:%S.%f")[:-3],
                    str(item.Spot), str(item.Press), str(item.Billet_Length or ""),
                    str(item.Temp_F), str(item.Temp_B), str(item.Count),
                    str(item.Speed or ""), str(item.EndPos or ""),
                    str(item.Mold1 or ""), str(item.Mold2 or ""), str(item.Mold3 or ""),
                    str(item.Mold4 or ""), str(item.Mold5 or ""), str(item.Mold6 or ""),
                    str(item.Billet_Temp or ""), str(item.At_Pre or ""), str(item.At_Temp or ""),
                    str(item.Die_ID or ""), str(item.Billet_Cycle_ID or "")
                ]
                buffer.append(row)
                
            except queue.Empty:
                pass
            
            # Flush Check
            now = time.time()
            if buffer and (len(buffer) >= batch_size or (now - last_flush) > flush_interval):
                writer.writerows(buffer)
                f.flush()
                buffer.clear()
                last_flush = now
                
        # Final Flush
        if buffer:
            writer.writerows(buffer)
            f.flush()
        f.close()

# --- REPLAY LOGIC ---

def load_sample_data(filename="sample_data.csv"):
    if not os.path.exists(filename):
        return None
    
    print(f"Loading sample data from {filename}...")
    rows = []
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # Map standard CSV columns to FactoryData properties if names differ
            # Assuming standard names match or are close.
            # We map known columns.
            for line in reader:
                # Basic cleaning
                clean_row = {}
                for k, v in line.items():
                    k_clean = k.strip()
                    if v and v.strip():
                        clean_row[k_clean] = v
                rows.append(clean_row)
    except Exception as e:
        print(f"Failed to load sample data: {e}")
        return None
        
    print(f"Loaded {len(rows)} sample rows.")
    return rows

# --- MAIN TEST LOGIC ---

def run_performance_test(duration_sec=10, rate_hz=100, sample_rows=None):
    mode = "REPLAY" if sample_rows else "DUMMY"
    print(f"\n>>> Starting Test ({mode}): Duration={duration_sec}s, Rate={rate_hz}Hz")
    
    logger = StandaloneCSVLogger()
    # Cleanup prev logs
    import shutil
    if logger.active_log_dir.exists():
        try:
            shutil.rmtree(logger.active_log_dir)
        except:
            pass
            
    logger.start()
    
    start_time = time.time()
    sent_count = 0
    full_events = 0
    
    try:
        end_time = start_time + duration_sec
        interval = 1.0 / rate_hz
        
        while time.time() < end_time:
            loop_start = time.time()
            
            # Create Data
            if sample_rows:
                # Replay
                idx = sent_count % len(sample_rows)
                raw_item = sample_rows[idx]
                
                # Careful helper to get float
                def get_float(k, default=0.0):
                    try:
                        return float(raw_item.get(k, default))
                    except:
                        return default
                        
                data = FactoryData(
                    Time=datetime.now().isoformat(),
                    Spot=get_float('Spot_Temp', 0.0), # Adapting legacy names if needed
                    Press=get_float('Press_Value', 0.0),
                    Temp_F=get_float('Temp_F', 0.0),
                    Temp_B=get_float('Temp_B', 0.0),
                    Count=get_float('Count', sent_count),
                    # Pass everything else
                    **{k: v for k, v in raw_item.items() if k not in ['Date', 'Time']}
                )
            else:
                # Dummy (Full Fields)
                data = FactoryData(
                    Time=datetime.now().isoformat(),
                    Spot=123.45 + (sent_count % 10),
                    Press=1000.0,
                    Temp_F=50.0,
                    Temp_B=60.0,
                    Count=sent_count,
                    Billet_Length=500,
                    Speed=12.5,
                    EndPos=1000,
                    Mold1=25.1, Mold2=25.2, Mold3=25.3, Mold4=25.4, Mold5=25.5, Mold6=25.6,
                    Billet_Temp=450.0,
                    At_Pre=1,
                    At_Temp=2,
                    Die_ID="TEST_DIE_01",
                    Billet_Cycle_ID=f"CYCLE_{sent_count}"
                )
            
            try:
                logger.queue.put_nowait(data)
                sent_count += 1
            except queue.Full:
                full_events += 1
            
            elapsed = time.time() - loop_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        print("Interrupted!")
    finally:
        print("Stopping Logger...")
        logger.stop()
        
    total_time = time.time() - start_time
    effective_rate = sent_count / total_time if total_time > 0 else 0
    
    print(f"Test Completed in {total_time:.2f}s")
    print(f"Total Sent: {sent_count}")
    print(f"Queue Full: {full_events}")
    print(f"Throughput: {effective_rate:.1f} rows/sec")
    
    # Verify
    total_written = 0
    for f in logger.active_log_dir.glob("*.csv"):
        with open(f, 'r', encoding='utf-8') as fs:
            total_written += sum(1 for _ in fs) - 1
            
    print(f"Total Written: {total_written}")
    if abs(sent_count - total_written) < 5:
        print("SUCCESS: Data Integrity Verified")
    else:
        print(f"WARNING: Data Loss Detected! ({sent_count - total_written} rows lost)")

if __name__ == "__main__":
    print("=== CSV Performance Evaluator ===")
    
    samples = load_sample_data("sample_data.csv")
    if samples:
        print(f"INFO: 'sample_data.csv' found. Running in REPLAY mode.")
    else:
        print(f"INFO: 'sample_data.csv' not found. Running in DUMMY mode with generated data.")
        
    run_performance_test(duration_sec=5, rate_hz=10, sample_rows=samples)
    print("-" * 30)
    run_performance_test(duration_sec=5, rate_hz=1000, sample_rows=samples)
    
    input("\nPress Enter to exit...")
