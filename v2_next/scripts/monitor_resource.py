import psutil
import time
import csv
import os
import sys
from datetime import datetime

# Configuration
TARGET_PROCESS_NAME = "SmartFactory_v1.0.0.exe"
BROWSER_PROCESS_NAMES = ["msedge.exe", "chrome.exe"] # Monitor both
LOG_INTERVAL_SEC = 60  # Log every 1 minute
OUTPUT_FILE = "resource_usage.csv"

def get_process_usage(names):
    """Aggregate usage of all processes matching names."""
    total_cpu = 0.0
    total_mem_mb = 0.0
    proc_count = 0
    threads = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'num_threads']):
        try:
            name = proc.info['name'].lower()
            if any(target.lower() in name for target in names):
                try:
                    # CPU aggregation (interval=0.1 for actual measurement)
                    total_cpu += proc.cpu_percent(interval=0.1)
                    
                    # Memory aggregation
                    mem_info = proc.memory_info()
                    total_mem_mb += mem_info.rss / (1024 * 1024)
                    
                    # Thread aggregation
                    threads += proc.num_threads()
                    
                    proc_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    return total_cpu, total_mem_mb, proc_count, threads

def main():
    print(f"=== Resource Monitor ===")
    print(f"Target:  {TARGET_PROCESS_NAME}")
    print(f"Browsers: {', '.join(BROWSER_PROCESS_NAMES)}")
    print("Waiting for target process to start...")
    
    # Simple wait for at least one instance
    while True:
        _, _, count, _ = get_process_usage([TARGET_PROCESS_NAME])
        if count > 0:
            print(f"Found {count} instance(s) of {TARGET_PROCESS_NAME}")
            break
        time.sleep(2)
            
    print(f"Logging to: {os.path.abspath(OUTPUT_FILE)}")
    
    # Initialize CSV
    file_exists = os.path.isfile(OUTPUT_FILE)
    try:
        with open(OUTPUT_FILE, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Date", "Time", 
                    "App_CPU", "App_Mem_MB", "App_Threads", "App_Procs",
                    "Browser_CPU", "Browser_Mem_MB", "Browser_Procs"
                ])
                
            while True:
                try:
                    # 1. App Metrics (Aggregate)
                    app_cpu, app_mem_mb, app_count, app_threads = get_process_usage([TARGET_PROCESS_NAME])
                    
                    if app_count == 0:
                         print("\nTarget process lost.")
                         break
                    
                    # 2. Browser Metrics (Aggregate)
                    br_cpu, br_mem_mb, br_count, _ = get_process_usage(BROWSER_PROCESS_NAMES)
                    
                    now = datetime.now()
                    row = [
                        now.strftime("%Y-%m-%d"),
                        now.strftime("%H:%M:%S"),
                        f"{app_cpu:.1f}",
                        f"{app_mem_mb:.1f}",
                        app_threads,
                        app_count,
                        f"{br_cpu:.1f}",
                        f"{br_mem_mb:.1f}",
                        br_count
                    ]
                    
                    writer.writerow(row)
                    f.flush()
                    
                    print(f"App: {app_mem_mb:.1f}MB ({app_count}p) | Browser: {br_mem_mb:.1f}MB ({br_count}p)", end='\r')
                    
                    time.sleep(LOG_INTERVAL_SEC)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"\nError: {e}")
                    break
                    
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
