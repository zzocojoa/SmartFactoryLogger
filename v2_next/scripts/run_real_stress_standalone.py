import socket
import struct
import time
import threading
import queue
import csv
import configparser
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

# Try to import httpx for SPOT camera
try:
    import httpx
except ImportError:
    print("WARNING: 'httpx' library not found. SPOT camera features will be disabled.")
    httpx = None

# --- CONSTANTS & DEFAULTS ---
DEFAULT_INTERVAL_SEC = 0.01  # Target 100Hz for stress test
DEFAULT_SPOT_TIMEOUT = 0.5
DRIVER_RETRY_INTERVAL = 1.0
DRIVER_RETRY_MAX = 8.0
DRIVER_TIMEOUT = 0.5
DRIVER_MERGE_FAIL_THRESHOLD = 3
DRIVER_MERGE_RETRY_SUCCESSES = 300
DRIVER_MERGE_RETRY_GROWTH = 2
CYCLE_SPEED_THRESHOLD = 0.1

DEFAULT_LS_TARGETS = [
    ("%DW250", "Mold1"),
    ("%DW256", "Mold2"),
    ("%DW262", "Mold3"),
    ("%DW288", "Mold4"),
    ("%DW276", "Mold5"),
    ("%DW282", "Mold6"),
    ("%DW268", "Billet_Temp"),
    ("%DW40", "At_Temp"),
    ("%DW50", "At_Pre"),
]

# --- CONFIGURATION MANAGER ---
class SimpleConfig:
    def __init__(self):
        self.EXTRUDER_IP = "192.168.10.10"
        self.EXTRUDER_PORT = 12289
        self.LS_IP = "192.168.10.220"
        self.LS_PORT = 2004
        self.SPOT_IP = "10.1.10.50"
        self.SPOT_URL = f"http://{self.SPOT_IP}/output?p=temperature"
        self.LS_TARGETS = DEFAULT_LS_TARGETS
        self.LOG_PATH = "stress_test_logs"
        self._load_from_ini()

    def _load_from_ini(self):
        config_path = Path("config.ini")
        if not config_path.exists():
             # Try to find in parent dir (dev mode)
            config_path = Path("..") / "config.ini"
            
        if config_path.exists():
            print(f"[Config] Loading from {config_path.resolve()}")
            parser = configparser.ConfigParser()
            try:
                parser.read(config_path, encoding='utf-8-sig')
                
                # Extruder
                if parser.has_option("EXTRUDER", "ip"):
                    self.EXTRUDER_IP = parser.get("EXTRUDER", "ip")
                if parser.has_option("EXTRUDER", "port"):
                    self.EXTRUDER_PORT = parser.getint("EXTRUDER", "port")
                    
                # LS
                if parser.has_option("LS_PLC", "ip"):
                    self.LS_IP = parser.get("LS_PLC", "ip")
                if parser.has_option("LS_PLC", "port"):
                    self.LS_PORT = parser.getint("LS_PLC", "port")
                
                # SPOT
                if parser.has_option("SPOT", "ip"):
                    self.SPOT_IP = parser.get("SPOT", "ip")
                    self.SPOT_URL = f"http://{self.SPOT_IP}/output?p=temperature" # Update URL if IP changed
                if parser.has_option("SPOT", "url"): # Explicit URL override
                    self.SPOT_URL = parser.get("SPOT", "url")
                    
                # LS Targets
                if parser.has_section("LS_PLC_TARGETS"):
                    targets = []
                    for addr, key in parser.items("LS_PLC_TARGETS"):
                        addr_norm = addr.strip().upper()
                        if not addr_norm.startswith("%"): addr_norm = "%" + addr_norm
                        targets.append((addr_norm, key.strip()))
                    if targets:
                        self.LS_TARGETS = targets
                        
            except Exception as e:
                print(f"[Config] Error parsing config.ini: {e}")
        else:
            print("[Config] No config.ini found. Using defaults.")

CFG = SimpleConfig()

# --- DATA MODEL ---
class FactoryData:
    def __init__(self, **kwargs):
        self.Time = kwargs.get("Time", "")
        self.Speed = kwargs.get("Speed", 0.0)
        self.Press = kwargs.get("Press", 0.0)
        self.Spot = kwargs.get("Spot", 0.0)
        self.Temp_F = kwargs.get("Temp_F", 0.0)
        self.Temp_B = kwargs.get("Temp_B", 0.0)
        self.Billet_Temp = kwargs.get("Billet_Temp", 0.0)
        self.Billet_Length = kwargs.get("Billet_Length", 0.0)
        self.Count = kwargs.get("Count", 0.0)
        self.EndPos = kwargs.get("EndPos", 0.0)
        self.At_Temp = kwargs.get("At_Temp", 0.0)
        self.At_Pre = kwargs.get("At_Pre", 0.0)
        self.Mold1 = kwargs.get("Mold1", 0.0)
        self.Mold2 = kwargs.get("Mold2", 0.0)
        self.Mold3 = kwargs.get("Mold3", 0.0)
        self.Mold4 = kwargs.get("Mold4", 0.0)
        self.Mold5 = kwargs.get("Mold5", 0.0)
        self.Mold6 = kwargs.get("Mold6", 0.0)
        self.Die_ID = kwargs.get("Die_ID", "")
        self.Billet_Cycle_ID = kwargs.get("Billet_Cycle_ID", "")
        self.Status = kwargs.get("Status", "")

# --- LOGIC PROCESSOR (Cycle ID Generation) ---
class LogicProcessor:
    def __init__(self) -> None:
        self.die_id = None
        self.die_seq = 0
        self.billet_cycle_id = 0
        self.last_counter = -1
        self.last_update_time = 0.0

    def _generate_die_id(self, timestamp) -> str:
        date_str = timestamp.strftime("%Y%m%d")
        return f"{date_str}_{self.die_seq:02d}"

    def update(self, count, pressure, speed, timestamp):
        if count is None:
            return "", ""
        try:
            current_count = int(count)
        except:
            return "", ""

        try:
            current_speed = float(speed) if speed is not None else 0.0
        except:
            current_speed = 0.0

        self.last_update_time = timestamp.timestamp()

        if self.last_counter == -1:
            self.last_counter = current_count
            if not self.die_id:
                self.die_seq = 1
                self.die_id = self._generate_die_id(timestamp)
                self.billet_cycle_id = current_count - 1

        is_die_changed = current_count < self.last_counter
        if is_die_changed:
            current_date_str = timestamp.strftime("%Y%m%d")
            last_date_str = self.die_id.split("_")[0] if self.die_id else ""
            if current_date_str != last_date_str:
                self.die_seq = 0
            self.die_seq += 1
            self.die_id = self._generate_die_id(timestamp)
            self.billet_cycle_id = -1

        self.last_counter = current_count

        cycle_id_output = ""
        if current_speed > CYCLE_SPEED_THRESHOLD:
            if self.billet_cycle_id != current_count:
                self.billet_cycle_id = current_count
            cycle_id_output = str(self.billet_cycle_id)

        return self.die_id or "", cycle_id_output

# --- REAL DRIVER (Network Logic) ---
class RealPLCDriver:
    def __init__(self):
        # Extruder (Melsec)
        self.sock_ext = None
        self.ext_retry_interval = DRIVER_RETRY_INTERVAL
        self.ext_next_retry = 0.0
        self.ext_merge_blocks = True
        self.ext_merge_failures = 0
        self.ext_split_success_count = 0
        self.ext_skip_counter = 0
        
        # LS (Temp)
        self.sock_ls = None
        self.ls_retry_interval = DRIVER_RETRY_INTERVAL
        self.ls_next_retry = 0.0
        
        # SPOT
        self.last_spot = 0.0
        if httpx:
            self._spot_http_client = httpx.Client(
                timeout=httpx.Timeout(connect=0.5, read=DEFAULT_SPOT_TIMEOUT, write=0.5, pool=2.0)
            )
        else:
            self._spot_http_client = None

        self.logic = LogicProcessor()

    def connect(self):
        self._connect_extruder()
        self._connect_ls()
        return bool(self.sock_ext or self.sock_ls)

    def close(self):
        if self.sock_ext:
            try: self.sock_ext.close()
            except: pass
        if self.sock_ls:
            try: self.sock_ls.close()
            except: pass
        if self._spot_http_client:
            try: self._spot_http_client.close()
            except: pass

    # --- Extruder Logic ---
    def _connect_extruder(self):
        now = time.time()
        if now < self.ext_next_retry: return False
        try:
            if self.sock_ext:
                try: self.sock_ext.close()
                except: pass
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(DRIVER_TIMEOUT)
            s.connect((CFG.EXTRUDER_IP, CFG.EXTRUDER_PORT))
            self.sock_ext = s
            self.ext_retry_interval = DRIVER_RETRY_INTERVAL
            self.ext_next_retry = 0.0
            print(f"[Driver] Connected to Extruder ({CFG.EXTRUDER_IP})")
            return True
        except Exception as e:
            self.sock_ext = None
            self.ext_next_retry = time.time() + self.ext_retry_interval
            # print(f"[Driver] Extruder Connect Fail: {e}")
            return False

    def _melsec_read(self, addr, count):
        if not self.sock_ext: return []
        cmd = f"01WRD{addr} {count:02}\r\n".encode()
        try:
            self.sock_ext.sendall(cmd)
            data = bytearray()
            # simple recv loop
            try:
                while True:
                    chunk = self.sock_ext.recv(4096)
                    if not chunk: break
                    data.extend(chunk)
                    if b"\r\n" in data: break
            except socket.timeout:
                pass
                
            raw = bytes(data)
            if not raw: raise Exception("No data")
            
            resp_str = raw.decode("ascii", errors="replace").strip()
            if "OK" not in resp_str: return []
            
            parts = resp_str.split("OK", 1)
            if len(parts) < 2: return []
            
            hex_data = parts[1]
            values = []
            for i in range(0, len(hex_data), 4):
                chunk = hex_data[i : i + 4]
                if len(chunk) == 4:
                    try: values.append(int(chunk, 16))
                    except: values.append(0)
            return values
        except Exception as e:
            # print(f"[Driver] Extruder Read Fail: {e}")
            self.sock_ext = None
            return []

    def _read_extruder(self):
        if self.ext_skip_counter > 0:
            self.ext_skip_counter -= 1
            return {}
        if not self.sock_ext:
            if not self._connect_extruder(): return {}
            
        data = {}
        try:
            # Simple Read Strategy (Merged)
            # D0020(20), D0420(10), D1500(20), D1900(20), B1502(1)
            
            # Using individual reads for robustness in this simple script
            # (Merging adds complexity with failure handling)
            
            b1 = self._melsec_read("D0020", 20)
            if len(b1) > 14:
                data["Press"] = b1[3] / 10.0
                data["Temp_F"] = b1[11]
                data["Temp_B"] = b1[12]
            
            b_spd = self._melsec_read("B1502", 1)
            if b_spd:
                data["Speed"] = b_spd[0] / 10.0
                
            b3 = self._melsec_read("D1500", 20)
            if len(b3) > 10:
                data["Count"] = b3[10]
                
            b2 = self._melsec_read("D0420", 10)
            if len(b2) > 1:
                data["EndPos"] = b2[1] / 10.0
                
            b4 = self._melsec_read("D1900", 20)
            if len(b4) > 11:
                data["Billet_Length"] = b4[11]
                
        except Exception as e:
            # print(f"[Driver] Extruder Error: {e}")
            self.sock_ext = None
            self.ext_skip_counter = 5
            
        return data

    # --- LS Logic ---
    def _connect_ls(self):
        now = time.time()
        if now < self.ls_next_retry: return False
        try:
            if self.sock_ls:
                try: self.sock_ls.close()
                except: pass
                
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(DRIVER_TIMEOUT)
            s.connect((CFG.LS_IP, CFG.LS_PORT))
            self.sock_ls = s
            self.ls_retry_interval = DRIVER_RETRY_INTERVAL
            self.ls_next_retry = 0.0
            print(f"[Driver] Connected to LS PLC ({CFG.LS_IP})")
            return True
        except Exception as e:
            self.sock_ls = None
            self.ls_next_retry = time.time() + self.ls_retry_interval
            # print(f"[Driver] LS Connect Fail: {e}")
            return False

    def _ls_create_packet(self, var_names):
        body = bytearray()
        body += b"\x54\x00"  # Cmd
        body += b"\x02\x00"  # DataType
        body += b"\x00\x00"
        body += struct.pack("<H", len(var_names))
        for name in var_names:
            vb = name.encode("ascii")
            body += struct.pack("<H", len(vb)) + vb
            
        header = bytearray(b"LSIS-XGT")
        header += b"\x00\x00" * 2
        header += b"\xA0\x33\x00\x01"
        header += struct.pack("<H", len(body))
        header += b"\x00\x00"
        return header + body

    def _read_ls(self):
        if not self.sock_ls:
            if not self._connect_ls(): return {}
            
        data = {}
        try:
            targets = [t[0] for t in CFG.LS_TARGETS]
            req = self._ls_create_packet(targets)
            self.sock_ls.sendall(req)
            
            # Recv Header (20)
            header = b""
            while len(header) < 20:
                chunk = self.sock_ls.recv(20 - len(header))
                if not chunk: raise Exception("No Header")
                header += chunk
                
            body_len = struct.unpack("<H", header[16:18])[0]
            if body_len > 8192: raise ValueError("Too large")
            
            # Recv Body
            body = b""
            while len(body) < body_len:
                chunk = self.sock_ls.recv(body_len - len(body))
                if not chunk: raise Exception("No Body")
                body += chunk
                
            # Parse
            # ... (Simplified parse logic)
            offset = 10
            block_cnt = struct.unpack("<H", body[8:10])[0]
            values = []
            
            for _ in range(block_cnt):
                 if offset+2 > len(body): break
                 d_len = struct.unpack("<H", body[offset : offset+2])[0]
                 offset += 2
                 if offset + d_len > len(body): break
                 raw = body[offset : offset + d_len]
                 if len(raw) == 2:
                     values.append(struct.unpack("<H", raw)[0])
                 else:
                     values.append(None)
                 offset += d_len
                 
            if len(values) == len(CFG.LS_TARGETS):
                for i, (addr, key) in enumerate(CFG.LS_TARGETS):
                    val = values[i]
                    if val is not None:
                         if key in ["At_Temp", "At_Pre"]:
                             data[key] = val / 100.0
                         else:
                             data[key] = val
        except Exception as e:
            # print(f"[Driver] LS Read Fail: {e}")
            self.sock_ls = None
        return data

    def _read_spot(self):
        if not self._spot_http_client: return 0.0
        try:
            resp = self._spot_http_client.get(CFG.SPOT_URL)
            resp.raise_for_status()
            val = float(resp.text.strip())
            return val
        except:
            return 0.0

    def read_all(self) -> FactoryData:
        # Read from components
        ext = self._read_extruder()
        ls = self._read_ls()
        spot = self._read_spot()
        
        # Calculate Logic
        now = datetime.now()
        die_id, cycle_id = self.logic.update(
            ext.get("Count"), ext.get("Press"), ext.get("Speed"), now
        )
        
        # Helper for case-insensitive get
        def get_ignore_case(d, key):
            if key in d: return d[key]
            # fallback search
            k_lower = key.lower()
            for k, v in d.items():
                if k.lower() == k_lower:
                    return v
            return None

        # Create Data
        return FactoryData(
            Time=now.isoformat(),
            Status="Running",
            Speed=ext.get("Speed"),
            Press=ext.get("Press"),
            Count=ext.get("Count"),
            EndPos=ext.get("EndPos"),
            Billet_Length=ext.get("Billet_Length"),
            Temp_F=ext.get("Temp_F"),
            Temp_B=ext.get("Temp_B"),
            
            Mold1=get_ignore_case(ls, "Mold1"),
            Mold2=get_ignore_case(ls, "Mold2"),
            Mold3=get_ignore_case(ls, "Mold3"),
            Mold4=get_ignore_case(ls, "Mold4"),
            Mold5=get_ignore_case(ls, "Mold5"),
            Mold6=get_ignore_case(ls, "Mold6"),
            Billet_Temp=get_ignore_case(ls, "Billet_Temp"),
            At_Temp=get_ignore_case(ls, "At_Temp"),
            At_Pre=get_ignore_case(ls, "At_Pre"),
            
            Spot=spot,
            Die_ID=die_id,
            Billet_Cycle_ID=cycle_id
        )

# --- LOGGER ---
class StandaloneLogger:
    def __init__(self, log_dir):
        self.queue = queue.Queue(maxsize=5000)
        self.running = False
        self.thread = None
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.total_written = 0
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread: self.thread.join()
        
    def _loop(self):
        batch = []
        last_flush = time.time()
        
        # Header (Updated to Korean as requested)
        headers = [
            "Date","Time","Temperature","메인압력","빌렛길이",
            "콘테이너온도 앞쪽","콘테이너온도 뒷쪽","생산카운터","현재속도","압출종료 위치",
            "Mold1","Mold2","Mold3","Mold4","Mold5","Mold6",
            "Billet_Temp","At_Pre","At_Temp","DIE_ID","Billet_CycleID"
        ]
        
        # Open File
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fpath = self.log_dir / f"RealStress_{ts}.csv"
        f = open(fpath, "w", newline="", encoding="utf-8-sig")
        writer = csv.writer(f)
        writer.writerow(headers)
        
        while self.running or not self.queue.empty():
            try:
                item = self.queue.get(timeout=0.1)
                dt = datetime.fromisoformat(item.Time)
                row = [
                    dt.strftime("%Y-%m-%d"),
                    dt.strftime("%H:%M:%S.%f")[:-3],
                    str(item.Spot or ""), str(item.Press or ""), str(item.Billet_Length or ""),
                    str(item.Temp_F or ""), str(item.Temp_B or ""), str(item.Count or ""),
                    str(item.Speed or ""), str(item.EndPos or ""),
                    str(item.Mold1 or ""), str(item.Mold2 or ""), str(item.Mold3 or ""),
                    str(item.Mold4 or ""), str(item.Mold5 or ""), str(item.Mold6 or ""),
                    str(item.Billet_Temp or ""), str(item.At_Pre or ""), str(item.At_Temp or ""),
                    str(item.Die_ID), str(item.Billet_Cycle_ID)
                ]
                batch.append(row)
                self.total_written += 1
            except queue.Empty:
                pass
                
            if len(batch) >= 50 or (time.time() - last_flush > 1.0):
                if batch:
                    writer.writerows(batch)
                    f.flush()
                    batch.clear()
                last_flush = time.time()
                
        if batch:
            writer.writerows(batch)
        f.close()


# --- MAIN ---
def main():
    print("=== REAL HARDWARE STRESS TEST ===")
    print(f"Polling Interval: {DEFAULT_INTERVAL_SEC}s ({1/DEFAULT_INTERVAL_SEC} Hz)")
    print(f"Log Path: {CFG.LOG_PATH}")
    print("Connecting to:")
    print(f" - Extruder: {CFG.EXTRUDER_IP}:{CFG.EXTRUDER_PORT}")
    print(f" - LS PLC:   {CFG.LS_IP}:{CFG.LS_PORT}")
    print(f" - SPOT:     {CFG.SPOT_IP}")
    print("---------------------------------")
    
    driver = RealPLCDriver()
    logger = StandaloneLogger(CFG.LOG_PATH)
    
    print("Starting connections...")
    driver.connect()
    logger.start()
    
    start_time = time.time()
    try:
        duration = 60
        end_time = start_time + duration
        
        count = 0
        while time.time() < end_time:
            loop_start = time.time()
            
            # Sync Read (Stress)
            data = driver.read_all()
            
            # Enqueue
            try:
                logger.queue.put_nowait(data)
            except:
                pass # Drop if full (stress indication)
                
            count += 1
            
            # Sleep remainder
            elapsed = time.time() - loop_start
            sleep = DEFAULT_INTERVAL_SEC - elapsed
            if sleep > 0:
                time.sleep(sleep)
                
            if count % 100 == 0:
                print(f"Collected {count} samples... (Written: {logger.total_written})", end='\r')
                
    except KeyboardInterrupt:
        print("\nInterrupted!")
        
    print("\nStopping...")
    driver.close()
    logger.stop()
    
    print(f"\nTest Finished.")
    print(f"Total Collected: {count}")
    print(f"Total Written:   {logger.total_written}")
    print(f"Throughput:      {count/duration:.1f} Hz")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
