from collections import deque
import json
import logging
from pathlib import Path
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
from backend.Observability.memory_service import estimate_size_bytes
from backend.Observability.service import observability_service

OPERATOR_METADATA_RUNTIME_STATE_VERSION = "1.0.0"
OPERATOR_METADATA_RUNTIME_STATE_WRITE_INTERVAL_SEC = 60.0


class PLCService:
    HISTORY_MAX_AGE_MS = 60 * 60 * 1000
    HISTORY_MAX_SAMPLES = 36_000

    def __init__(self, use_mock: bool = True, operator_metadata_runtime_state_path: Optional[Path] = None):
        self._logger = logging.getLogger("SmartFactoryLoggerV2")
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
        self.operator_metadata_runtime_state_path = (
            operator_metadata_runtime_state_path
            or (config.APP_DATA_DIR / "operator_metadata_runtime_state.json")
        )
        self.operator_metadata_state_lock = threading.Lock()
        self.operator_metadata_previous_count: Optional[int] = None
        self.operator_metadata_last_normal_sample_at = self._load_operator_metadata_last_sample_at()
        self.operator_metadata_last_state_write_at = self.operator_metadata_last_normal_sample_at
        self._process_operator_context: Optional[tuple[str, str]] = None

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

    def stop(self) -> bool:
        self.running = False
        if self.driver_thread:
            self.driver_thread.join(timeout=1.0)
        if self.thread:
            self.thread.join(timeout=1.0)
        self.driver.close()
        return not (
            (self.driver_thread is not None and self.driver_thread.is_alive())
            or (self.thread is not None and self.thread.is_alive())
        )

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

    def _operator_metadata_downtime_reset_hours(self) -> int:
        fallback = getattr(config, "DEFAULT_OPERATOR_METADATA_DOWNTIME_RESET_HOURS", 8)
        minimum = getattr(config, "MIN_OPERATOR_METADATA_DOWNTIME_RESET_HOURS", 1)
        maximum = getattr(config, "MAX_OPERATOR_METADATA_DOWNTIME_RESET_HOURS", 72)
        try:
            value = int(getattr(config, "OPERATOR_METADATA_DOWNTIME_RESET_HOURS", fallback))
        except Exception:
            value = fallback
        return max(minimum, min(maximum, value))

    def _load_operator_metadata_last_sample_at(self) -> Optional[float]:
        try:
            if not self.operator_metadata_runtime_state_path.exists():
                return None
            payload = json.loads(self.operator_metadata_runtime_state_path.read_text(encoding="utf-8"))
            last_sample_at = payload.get("last_normal_sample_at")
            if isinstance(last_sample_at, (int, float)) and last_sample_at >= 0:
                return float(last_sample_at)
        except Exception as exc:
            self._logger.warning("Operator metadata runtime state load failed: %s", exc)
        return None

    def _persist_operator_metadata_runtime_state(
        self,
        *,
        sample_at_sec: float,
        count: int,
        force: bool = False,
    ) -> None:
        with self.operator_metadata_state_lock:
            previous_write_at = self.operator_metadata_last_state_write_at
            if (
                not force
                and previous_write_at is not None
                and sample_at_sec - previous_write_at < OPERATOR_METADATA_RUNTIME_STATE_WRITE_INTERVAL_SEC
            ):
                return

            payload = {
                "operator_metadata_runtime_state_version": OPERATOR_METADATA_RUNTIME_STATE_VERSION,
                "last_normal_sample_at": sample_at_sec,
                "last_count": count,
            }
            temp_path = self.operator_metadata_runtime_state_path.with_name(
                f"{self.operator_metadata_runtime_state_path.name}.tmp"
            )
            try:
                self.operator_metadata_runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                temp_path.replace(self.operator_metadata_runtime_state_path)
                self.operator_metadata_last_state_write_at = sample_at_sec
            except Exception as exc:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                self._logger.warning("Operator metadata runtime state persist failed: %s", exc)

    def _apply_operator_metadata_auto_reset(self, raw_data: FactoryData, captured_at_sec: float) -> None:
        count = raw_data.Count
        if count is None:
            return

        reset_reason: Optional[str] = None
        previous_count = self.operator_metadata_previous_count
        if previous_count is not None and previous_count > 0 and count == 0:
            reset_reason = "count_transition_to_zero"
        else:
            last_sample_at = self.operator_metadata_last_normal_sample_at
            threshold_sec = self._operator_metadata_downtime_reset_hours() * 60 * 60
            if last_sample_at is not None and captured_at_sec - last_sample_at >= threshold_sec:
                reset_reason = "downtime_threshold"

        if reset_reason:
            _, did_reset = operator_metadata_store.reset_if_valid(source=f"auto_{reset_reason}")
            if did_reset:
                self._logger.info(
                    "Operator metadata auto reset applied: reason=%s count=%s",
                    reset_reason,
                    count,
                )

        self.operator_metadata_previous_count = count
        self.operator_metadata_last_normal_sample_at = captured_at_sec
        self._persist_operator_metadata_runtime_state(
            sample_at_sec=captured_at_sec,
            count=count,
            force=reset_reason is not None,
        )

    def _derive_metadata_process_state_candidate(
        self,
        current_state: Optional[str],
        operator_metadata: Any,
    ) -> str:
        state = current_state or "unknown"
        context = (operator_metadata.product_no or "", operator_metadata.operator_mold_no or "")
        previous_context = self._process_operator_context
        self._process_operator_context = context
        if previous_context is None or previous_context == context:
            return state
        if state not in {"stopped", "idle_candidate"}:
            return state
        if not operator_metadata.valid or not context[0] or not context[1]:
            return state
        return "changeover_candidate"

    def _compose_data(self, raw_data: FactoryData, captured_at_sec: Optional[float] = None) -> FactoryData:
        sample_at_sec = captured_at_sec if captured_at_sec is not None else time.time()
        self._apply_operator_metadata_auto_reset(raw_data, sample_at_sec)
        operator_metadata = operator_metadata_store.get()
        extruder_process_state_online = self._derive_metadata_process_state_candidate(
            raw_data.extruder_process_state_online,
            operator_metadata,
        )
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
            "extruder_process_state_online": extruder_process_state_online,
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

    def get_history_memory_summary(self, sample_size: int = 128) -> dict[str, Any]:
        bounded_sample_size = max(1, int(sample_size))
        with self.history_lock:
            count = len(self.history)
            max_samples = self.HISTORY_MAX_SAMPLES
            oldest_timestamp_ms = self.history[0].timestamp_ms if self.history else None
            newest_timestamp_ms = self.history[-1].timestamp_ms if self.history else None
            if count <= bounded_sample_size:
                sample_items = list(self.history)
            else:
                step = max(1, count // bounded_sample_size)
                sample_items = [
                    item
                    for idx, item in enumerate(self.history)
                    if idx % step == 0
                ][:bounded_sample_size]

        sample_count = len(sample_items)
        sampled_bytes = estimate_size_bytes(sample_items) if sample_count else 0
        avg_bytes_per_sample = sampled_bytes / max(sample_count, 1)
        estimated_bytes = int(avg_bytes_per_sample * count)

        return {
            "count": count,
            "max_samples": max_samples,
            "oldest_timestamp_ms": oldest_timestamp_ms,
            "newest_timestamp_ms": newest_timestamp_ms,
            "sample_size": sample_count,
            "sampled_bytes": sampled_bytes,
            "estimated_bytes": estimated_bytes,
            "avg_bytes_per_sample": avg_bytes_per_sample,
            "fill_ratio": count / max(max_samples, 1),
        }

    def clear_data_history(self) -> None:
        with self.history_lock:
            self.history.clear()
            self.history_instance_id = uuid.uuid4().hex

    def _loop(self):
        while self.running:
            try:
                raw_data, driver_data_at = self._get_driver_snapshot()
                if raw_data is not None and driver_data_at is not None and driver_data_at != self.last_processed_driver_data_at:
                    next_data = self._compose_data(raw_data, driver_data_at)
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


    def _spot_temperature_health(self) -> Dict[str, Any]:
        try:
            from backend.FacilityData.drivers import spot_api as spot_control

            diagnostics = spot_control.get_spot_diagnostics()
            fact_health = spot_control.get_spot_observation_fact_health()
        except Exception as exc:
            v2_4_operational = logger_service.get_v2_4_operational_summary()
            v2_4_operational.update(
                {
                    "observation_fact_enabled": bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)),
                    "observation_fact_write_failure_count": None,
                    "config_drift_detected_count": None,
                }
            )
            return {
                "diagnostics_available": False,
                "diagnostics_error": exc.__class__.__name__,
                "validation_state": "shadow",
                "operational_truth": False,
                "v2_4_operational": v2_4_operational,
            }

        exposed_fields = (
            "build_git_commit",
            "spot_service_instance_id",
            "spot_poll_seq",
            "spot_observation_seq",
            "spot_poll_status",
            "spot_raw_validity",
            "spot_source_freshness",
            "spot_device_status_code",
            "temperature_status_shadow",
            "spot_cache_status",
            "temperature_value_origin",
            "cache_fallback_allowed",
            "spot_snapshot_age_ms",
            "spot_value_age_ms",
            "spot_poll_freshness_threshold_sec",
            "spot_cache_expiry_threshold_sec",
            "temperature_cache_status",
            "temperature_last_success_at",
            "temperature_last_error_at",
            "temperature_last_error_code",
        )
        payload = {field: diagnostics.get(field) for field in exposed_fields}
        v2_4_operational = logger_service.get_v2_4_operational_summary()
        v2_4_operational.update(
            {
                "observation_fact_enabled": bool(fact_health.get("enabled")),
                "observation_fact_write_failure_count": fact_health.get("write_failure_count"),
                "config_drift_detected_count": fact_health.get("config_drift_detected_count"),
            }
        )
        payload.update(
            {
                "diagnostics_available": True,
                "validation_state": "shadow",
                "operational_truth": False,
                "v2_4_operational": v2_4_operational,
            }
        )
        return payload

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
        spot_temperature = self._spot_temperature_health()
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
            "spot_temperature": spot_temperature,
        }

# Singleton Instance (Initialized by main.py)
# Default to config.MODE (REAL if frozen, MOCK if dev)
mode = config.MODE
plc_service = PLCService(use_mock=(mode != 'REAL'))
