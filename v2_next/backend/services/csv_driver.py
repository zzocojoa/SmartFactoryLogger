import csv
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from ..models.data_model import FactoryData
from .base_driver import BasePLCDriver

class CsvReplayDriver(BasePLCDriver):
    def __init__(self, csv_path: str):
        super().__init__()
        self.csv_path = Path(csv_path)
        self.rows: List[Dict[str, str]] = []
        self.current_index = 0
        self.last_step_time = 0.0
        self._load_csv()

    def _safe_float(self, value: Optional[str]) -> float:
        if not value:
            return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0
        
    def _load_csv(self):
        if not self.csv_path.exists():
            print(f"[CsvDriver] Error: File not found {self.csv_path}")
            return
            
        print(f"[CsvDriver] Loading {self.csv_path}...")
        
        # Helper to read with specific encoding
        def read_with_encoding(enc, errors='strict'):
            with self.csv_path.open("r", encoding=enc, errors=errors) as f:
                reader = csv.DictReader(f)
                return [{k.strip(): v for k, v in row.items() if k} for row in reader]

        try:
            # File has UTF-8 BOM, so we must use utf-8-sig. 
            # We use errors='replace' to avoid crashing on random bad bytes in data rows.
            print(f"[CsvDriver] Attempting UTF-8-SIG with replacement...")
            self.rows = read_with_encoding("utf-8-sig", errors='replace')
            
            # If that yielded no rows or keys look wrong (e.g. garbled), we could try CP949, 
            # but BOM confirms UTF-8.
            print(f"[CsvDriver] Loaded {len(self.rows)} rows.")
            if self.rows:
                keys = list(self.rows[0].keys())
                print(f"[CsvDriver] Keys: {keys}")
                # DEBUG: Write keys to file to verify
                try:
                    with open("debug_csv_driver.log", "w", encoding="utf-8") as f:
                        f.write(f"Keys: {keys}\n")
                        f.write(f"First Row: {self.rows[0]}\n")
                        f.write(f"Current Speed Val: {self.rows[0].get('현재속도')}\n")
                        f.write(f"Main Press Val: {self.rows[0].get('메인압력')}\n")
                        f.write(f"Spot Temp Val: {self.rows[0].get('Temperature')}\n")
                except Exception as e:
                    print(f"Failed to write debug log: {e}")
            # Skip initial idle rows (where Speed is 0 or empty)
            # This prevents the user from staring at 0.0 values on startup
            start_index = 0
            for i, row in enumerate(self.rows):
                try:
                    speed_val = self._safe_float(row.get("현재속도") or row.get("Speed"))
                    if speed_val > 0.5: # Threshold for "Active"
                        start_index = i
                        print(f"[CsvDriver] Fast-forwarding to index {i} (Speed={speed_val})")
                        break
                except:
                    continue
            
            self.current_index = start_index
            print(f"[CsvDriver] Ready to replay from index {self.current_index}.")
        except Exception as e:
            print(f"[CsvDriver] Failed to load CSV: {e}")
            self.rows = []
        except Exception as e:
            print(f"[CsvDriver] Failed to load CSV: {e}")
            self.rows = []

    def connect(self) -> bool:
        if not self.rows:
            return False
        self.connected = True
        print("[CsvDriver] Ready to replay.")
        return True

    def read_data(self) -> FactoryData:
        if not self.rows:
            return self._empty_data()
            
        # Replay logic: cyclical access
        row = self.rows[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.rows)
        
        # Inject current time to make it look live
        now = datetime.now()
        
        try:
            data = FactoryData(
                Time=now.isoformat(),
                Status="Running",
                # Map Korean headers to internal English keys
                Speed=self._safe_float(row.get("현재속도") or row.get("Speed")),
                Press=self._safe_float(row.get("메인압력") or row.get("MainPress")),
                Count=int(self._safe_float(row.get("생산카운터") or row.get("Count"))),
                EndPos=self._safe_float(row.get("압출종료 위치") or row.get("EndPos")),
                Billet_Length=self._safe_float(row.get("빌렛길이") or row.get("BilletLength")),
                
                # IDs
                Die_ID=row.get("DIE_ID", ""),
                Billet_Cycle_ID=row.get("Billet_CycleID", ""),
                
                # Temperatures
                Spot=self._safe_float(row.get("Temperature")), 
                Temp_F=self._safe_float(row.get("콘테이너온도 앞쪽") or row.get("Temp_F")),
                # Note: CSV header has a typo '콘테이 너온도 뒷쪽'
                Temp_B=self._safe_float(row.get("콘테이 너온도 뒷쪽") or row.get("콘테이너온도 뒷쪽") or row.get("Temp_B")),
                
                Billet_Temp=self._safe_float(row.get("Billet_Temp")),
                
                # Molds
                Mold1=self._safe_float(row.get("Mold1")),
                Mold2=self._safe_float(row.get("Mold2")),
                Mold3=self._safe_float(row.get("Mold3")),
                Mold4=self._safe_float(row.get("Mold4")),
                Mold5=self._safe_float(row.get("Mold5")),
                Mold6=self._safe_float(row.get("Mold6")),
                
                # Environment
                At_Temp=self._safe_float(row.get("At_Temp")),
                At_Pre=self._safe_float(row.get("At_Pre"))
            )
            return data
        except Exception as e:
            print(f"[CsvDriver] Parse error at row {self.current_index}: {e}")
            return self._empty_data()

    def _empty_data(self) -> FactoryData:
        return FactoryData(
            Time=datetime.now().isoformat(),
            Status="Error",
            Speed=0, Press=0, Spot=0, Temp_F=0, Temp_B=0
        )

    def close(self):
        self.connected = False
