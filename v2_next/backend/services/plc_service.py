from typing import Optional, Dict, Any
import threading
import time
from ..models.data_model import FactoryData
from .base_driver import BasePLCDriver
from .mock_driver import MockPLCDriver
from .real_driver import RealPLCDriver
from .. import config
from .logger_service import logger_service
from .config_manager import config_manager
from .status_service import StatusEvaluator
from .observability_service import observability_service

class PLCService:
    def __init__(self, use_mock: bool = True):
        # Select Driver based on flag
        # Select Driver based on flag
        if use_mock:
            # Check environment for CSV Mode
            import os
            mode_env = os.getenv("V2_MODE", "MOCK").upper()
            if mode_env == "CSV":
                print("[PLCService] Mode: CSV (Replay)")
                from .csv_driver import CsvReplayDriver
                csv_path = os.getenv("V2_CSV_PATH", "data.csv")
                self.driver: BasePLCDriver = CsvReplayDriver(csv_path)
                self.mode = "CSV"
            else:
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
        self.interval_lock = threading.Lock()
        self.last_update: Optional[float] = None
        self.interval_sec = float(config.INTERVAL_SEC)
        self.status_evaluator = StatusEvaluator()
        
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

    def apply_interval(self, interval_sec: float) -> float:
        # Policy: interval is fixed at config.INTERVAL_SEC (0.2s).
        fixed = float(config.INTERVAL_SEC)
        with self.interval_lock:
            self.interval_sec = fixed
        return fixed

    def apply_connection_config(self) -> bool:
        try:
            if hasattr(self.driver, "apply_connection_config"):
                self.driver.apply_connection_config()
            return True
        except Exception:
            return False
        
    def _loop(self):
        while self.running:
            try:
                # 1. Read from Driver
                new_data = self.driver.read_data()
                
                snapshot = config_manager.get_snapshot()
                values = snapshot.get("values", {})
                thresholds_cfg = values.get("thresholds", {})
                logging_cfg = values.get("logging", {})
                press_threshold = logging_cfg.get(
                    "cycle_threshold_press", config.DEFAULT_CYCLE_THRESHOLD_PRESS
                )
                computed = self.status_evaluator.evaluate(new_data, thresholds_cfg, float(press_threshold))
                new_data = new_data.model_copy(update={"Computed": computed})
                
                # 2. Update State
                with self.lock:
                    self.current_data = new_data
                    self.last_update = time.time()

                logger_service.enqueue(new_data)
                    
                # 3. Rate Limit (fixed at 0.2s)
                with self.interval_lock:
                    interval = self.interval_sec
                time.sleep(interval)
                
            except Exception as e:
                print(f"[PLCService] Error: {e}")
                try:
                    observability_service.record_error("plc_loop", str(e))
                except Exception:
                    pass
                time.sleep(1.0) # Backoff
                
    def get_latest_data(self) -> FactoryData:
        with self.lock:
            return self.current_data

    def get_health(self) -> Dict[str, Any]:
        with self.lock:
            last_update = self.last_update
        comm_metrics: Dict[str, Any] = {}
        try:
            comm_metrics = self.driver.get_comm_metrics()
        except Exception:
            comm_metrics = {}
        return {
            "running": self.running,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "last_update": last_update,
            "driver_connected": getattr(self.driver, "connected", False),
            "mode": self.mode,
            "comm": comm_metrics,
        }

# Singleton Instance (Initialized by main.py)
import os
# Default to MOCK for safety, set V2_MODE=REAL to use Hardware
mode = os.getenv("V2_MODE", "MOCK").upper()
plc_service = PLCService(use_mock=(mode != 'REAL'))
