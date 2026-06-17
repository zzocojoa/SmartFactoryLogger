from collections import deque
from typing import Optional, Dict, Any
import threading
import time
import uuid
from backend.FacilityData.schemas import FactoryData, FactoryDataHistoryResponse, FactoryDataHistorySample
from .drivers.base import BasePLCDriver
from .drivers.mock_plc import MockPLCDriver
from .drivers.real_plc import RealPLCDriver
from .. import config
from backend.FacilityData.operator_metadata import operator_metadata_store
from backend.FacilityData.repository import logger_service
from backend.Configuration.Configuration_DB_Manager import config_manager
from backend.Observability.Observability_Logic_Status import StatusEvaluator
from backend.Observability.service import observability_service

class PLCService:
    HISTORY_MAX_AGE_MS = 60 * 60 * 1000
    HISTORY_MAX_SAMPLES = 36_000

    def __init__(self, use_mock: bool = True):
        if use_mock:
            import os
            mode_env = os.getenv("V2_MODE", "MOCK").upper()
            if mode_env == "CSV":
                print("[PLCService] Mode: CSV (Replay)")
                from .drivers.csv_replay import CsvReplayDriver
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
        self.driver_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.driver_state_lock = threading.Lock()
        self.interval_lock = threading.Lock()
        self.history_lock = threading.Lock()
        self.history: deque[FactoryDataHistorySample] = deque(maxlen=self.HISTORY_MAX_SAMPLES)
        self.history_instance_id = uuid.uuid4().hex
        self.last_update: Optional[float] = None
        self.interval_sec = float(config.INTERVAL_SEC)
        self.status_evaluator = StatusEvaluator()
        self.driver_last_data: Optional[FactoryData] = None
        self.driver_last_data_at: Optional[float] = None
        self.driver_last_error: Optional[str] = None
        self.driver_last_error_at: Optional[float] = None
        self.last_processed_driver_data_at: Optional[float] = None

        self.current_data: FactoryData = FactoryData(
            Time="", Speed=0, Press=0, Count=0, EndPos=0, Billet_Length=0,
            Spot=0, Temp_F=0, Temp_B=0, Billet_Temp=0,
            Mold1=0, Mold2=0, Mold3=0, Mold4=0, Mold5=0, Mold6=0,
            At_Temp=0, At_Pre=0, Status="Initializing"
        )

    def start(self):
        if self.running:
            return

        self.driver.connect()
        self.running = True
        self.driver_thread = threading.Thread(target=self._driver_loop, daemon=True)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.driver_thread.start()
        self.thread.start()
        print("[PLCService] Background Thread Started.")

    def stop(self):
        self.running = False
        if self.driver_thread:
            self.driver_thread.join(timeout=1.0)
        if self.thread:
            self.thread.join(timeout=1.0)
        self.driver.close()

    def apply_interval(self, interval_sec: float) -> float:
        clamped = max(config.MIN_INTERVAL_SEC, min(config.MAX_INTERVAL_SEC, interval_sec))
        with self.interval_lock:
            self.interval_sec = clamped
        return clamped

    def apply_connection_config(self) -> bool:
        try:
            if hasattr(self.driver, "apply_connection_config"):
                self.driver.apply_connection_config()
            return True
        except Exception:
            return False

    def _current_interval(self) -> float:
        with self.interval_lock:
            return self.interval_sec

    def _driver_loop(self) -> None:
        while self.running:
            started_at = time.time()
            try:
                next_data = self.driver.read_data()
                captured_at = time.time()
                with self.driver_state_lock:
                    self.driver_last_data = next_data
                    self.driver_last_data_at = captured_at
                    self.driver_last_error = None
                    self.driver_last_error_at = None
            except Exception as exc:
                with self.driver_state_lock:
                    self.driver_last_error = str(exc)
                    self.driver_last_error_at = time.time()
                try:
                    observability_service.record_error("plc_driver", str(exc))
                except Exception:
                    pass
                time.sleep(1.0)
                continue

            sleep_sec = max(0.0, self._current_interval() - (time.time() - started_at))
            time.sleep(sleep_sec)

    def _get_driver_snapshot(self) -> tuple[Optional[FactoryData], Optional[float]]:
        with self.driver_state_lock:
            return self.driver_last_data, self.driver_last_data_at

    def _compose_data(self, raw_data: FactoryData) -> FactoryData:
        operator_metadata = operator_metadata_store.get()
        snapshot = config_manager.get_snapshot()
        values = snapshot.get("values", {})
        thresholds_cfg = values.get("thresholds", {})
        status_cfg = values.get("status", {})
        jam_press_threshold = status_cfg.get("jam_press_threshold", config.JAM_PRESS_THRESHOLD)
        computed = self.status_evaluator.evaluate(
            raw_data,
            thresholds_cfg,
            float(jam_press_threshold),
        )
        return raw_data.model_copy(update={
            "Computed": computed,
            "Product_No_operator": operator_metadata.product_no,
            "Mold_No_operator": operator_metadata.operator_mold_no,
            "operator_metadata_valid": operator_metadata.valid,
            "operator_metadata_missing_fields": operator_metadata.missing_fields,
            "operator_metadata_updated_at": operator_metadata.updated_at,
        })

    def _with_timestamp_ms(self, data: FactoryData, timestamp_ms: int) -> FactoryData:
        return data.model_copy(update={"timestamp_ms": timestamp_ms})

    def _prune_history_locked(self, now_ms: int) -> None:
        cutoff_ms = now_ms - self.HISTORY_MAX_AGE_MS
        while self.history and self.history[0].timestamp_ms < cutoff_ms:
            self.history.popleft()

    def _record_history_sample(self, data: FactoryData, captured_at_sec: float) -> None:
        timestamp_ms = int(captured_at_sec * 1000)
        data_with_timestamp = self._with_timestamp_ms(data, timestamp_ms)
        sample = FactoryDataHistorySample(
            timestamp_ms=timestamp_ms,
            data=data_with_timestamp.model_copy(deep=True),
        )
        with self.history_lock:
            self._prune_history_locked(timestamp_ms)
            if self.history and self.history[-1].timestamp_ms == timestamp_ms:
                self.history[-1] = sample
                return
            self.history.append(sample)

    def get_data_history(self, since_ms: int, limit: int) -> FactoryDataHistoryResponse:
        now_ms = int(time.time() * 1000)
        cutoff_ms = max(since_ms, now_ms - self.HISTORY_MAX_AGE_MS)
        with self.history_lock:
            self._prune_history_locked(now_ms)
            oldest_timestamp_ms = self.history[0].timestamp_ms if self.history else None
            newest_timestamp_ms = self.history[-1].timestamp_ms if self.history else None
            truncated = since_ms > 0 if oldest_timestamp_ms is None else since_ms < oldest_timestamp_ms
            samples = [sample for sample in self.history if sample.timestamp_ms > cutoff_ms]
            return FactoryDataHistoryResponse(
                samples=samples[-limit:],
                oldest_timestamp_ms=oldest_timestamp_ms,
                newest_timestamp_ms=newest_timestamp_ms,
                history_instance_id=self.history_instance_id,
                truncated=truncated,
            )

    def clear_data_history(self) -> None:
        with self.history_lock:
            self.history.clear()
            self.history_instance_id = uuid.uuid4().hex

    def _loop(self):
        while self.running:
            try:
                raw_data, driver_data_at = self._get_driver_snapshot()
                if raw_data is not None and driver_data_at is not None and driver_data_at != self.last_processed_driver_data_at:
                    next_data = self._compose_data(raw_data)
                    timestamp_ms = int(driver_data_at * 1000)
                    current_data = self._with_timestamp_ms(next_data, timestamp_ms)
                    with self.lock:
                        self.current_data = current_data
                        self.last_update = driver_data_at
                    self._record_history_sample(current_data, driver_data_at)
                    logger_service.enqueue(next_data)
                    self.last_processed_driver_data_at = driver_data_at
                time.sleep(self._current_interval())
            except Exception as e:
                try:
                    observability_service.record_error("plc_loop", str(e))
                except Exception:
                    pass
                time.sleep(1.0)

    def get_latest_data(self) -> FactoryData:
        with self.lock:
            return self.current_data

    def get_health(self) -> Dict[str, Any]:
        with self.lock:
            last_update = self.last_update
        with self.driver_state_lock:
            driver_last_data_at = self.driver_last_data_at
            driver_last_error = self.driver_last_error
        comm_metrics: Dict[str, Any] = {}
        try:
            comm_metrics = self.driver.get_comm_metrics()
        except Exception:
            comm_metrics = {}
        driver_snapshot_age_sec: Optional[float] = None
        if driver_last_data_at is not None:
            driver_snapshot_age_sec = max(0.0, time.time() - driver_last_data_at)
        return {
            "running": self.running,
            "thread_alive": self.thread.is_alive() if self.thread else False,
            "driver_thread_alive": self.driver_thread.is_alive() if self.driver_thread else False,
            "last_update": last_update,
            "driver_connected": getattr(self.driver, "connected", False),
            "mode": self.mode,
            "driver_snapshot_at": driver_last_data_at,
            "driver_snapshot_age_sec": driver_snapshot_age_sec,
            "driver_last_error": driver_last_error,
            "comm": comm_metrics,
        }

# Singleton Instance (Initialized by main.py)
# Default to config.MODE (REAL if frozen, MOCK if dev)
mode = config.MODE
plc_service = PLCService(use_mock=(mode != 'REAL'))
