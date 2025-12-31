from typing import Optional, Dict, Any
import threading
import time
from ..models.data_model import FactoryData
from .base_driver import BasePLCDriver
from .mock_driver import MockPLCDriver
from .real_driver import RealPLCDriver
from .. import config

class PLCService:
    def __init__(self, use_mock: bool = True):
        # Select Driver based on flag
        if use_mock:
            print("[PLCService] Mode: MOCK (Simulation)")
            self.driver: BasePLCDriver = MockPLCDriver()
            self.mode = "MOCK"
        else:
            print("[PLCService] Mode: REAL (Hardware Connection)")
            self.driver: BasePLCDriver = RealPLCDriver()
            self.mode = "REAL"

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.last_update: Optional[float] = None
        
        # Global State (Thread Safe?)
        self.current_data: FactoryData = FactoryData(
            Time="", Speed=0, Press=0, Count=0, EndPos=0, Billet_Length=0,
            Spot=0, Temp_F=0, Temp_B=0, Billet_Temp=0,
            Mold1=0, Mold2=0, Mold3=0, Mold4=0, Mold5=0, Mold6=0,
            At_Temp=0, At_Pre=0, Status="Initializing"
        )

    def start(self):
        if self.running: return
        
        self.driver.connect()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print("[PLCService] Background Thread Started.")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.driver.close()
        
    def _loop(self):
        while self.running:
            try:
                # 1. Read from Driver
                new_data = self.driver.read_data()
                
                # 2. Update State
                with self.lock:
                    self.current_data = new_data
                    self.last_update = time.time()
                    
                # 3. Rate Limit (fixed at 0.2s)
                time.sleep(config.INTERVAL_SEC)
                
            except Exception as e:
                print(f"[PLCService] Error: {e}")
                time.sleep(1.0) # Backoff
                
    def get_latest_data(self) -> FactoryData:
        with self.lock:
            return self.current_data

    def get_health(self) -> Dict[str, Any]:
        with self.lock:
            last_update = self.last_update
        return {
            "running": self.running,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "last_update": last_update,
            "driver_connected": getattr(self.driver, "connected", False),
            "mode": self.mode,
        }

# Singleton Instance (Initialized by main.py)
import os
# Default to MOCK for safety, set V2_MODE=REAL to use Hardware
mode = os.getenv("V2_MODE", "MOCK").upper()
plc_service = PLCService(use_mock=(mode != 'REAL'))
