import csv
import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Iterable, Tuple

from .. import config
from .. import constants
from backend.FacilityData.schemas import FactoryData


CSV_SCHEMA_VERSION = "2.1.0"
DERIVATION_VERSION = "cycle-heuristic-v1"

V1_CSV_COLUMNS = [
    "Date",
    "Time",
    "Temperature",
    "MainPress",
    "BilletLength",
    "Temp_F",
    "Temp_B",
    "Count",
    "Speed",
    "EndPos",
    "Mold1",
    "Mold2",
    "Mold3",
    "Mold4",
    "Mold5",
    "Mold6",
    "Billet_Temp",
    "At_Pre",
    "At_Temp",
    "DIE_ID",
    "Billet_CycleID",
]

V1_CSV_HEADER_ALIASES = {
    "Date": frozenset({"Date", "날짜"}),
    "Time": frozenset({"Time", "시간"}),
    "Temperature": frozenset({"Temperature", "Spot", "SPOT", "스팟온도"}),
    "MainPress": frozenset({"MainPress", "Press", "메인압력"}),
    "BilletLength": frozenset({"BilletLength", "Billet_Length", "빌렛길이"}),
    "Temp_F": frozenset({"Temp_F", "콘테이너온도 앞쪽"}),
    "Temp_B": frozenset({"Temp_B", "콘테이너온도 뒷쪽"}),
    "Count": frozenset({"Count", "생산카운터"}),
    "Speed": frozenset({"Speed", "현재속도"}),
    "EndPos": frozenset({"EndPos", "압출종료 위치", "압출 종료 위치"}),
    "Mold1": frozenset({"Mold1"}),
    "Mold2": frozenset({"Mold2"}),
    "Mold3": frozenset({"Mold3"}),
    "Mold4": frozenset({"Mold4"}),
    "Mold5": frozenset({"Mold5"}),
    "Mold6": frozenset({"Mold6"}),
    "Billet_Temp": frozenset({"Billet_Temp", "빌렛온도"}),
    "At_Pre": frozenset({"At_Pre", "대기압"}),
    "At_Temp": frozenset({"At_Temp", "대기온도"}),
    "DIE_ID": frozenset({"DIE_ID"}),
    "Billet_CycleID": frozenset({"Billet_CycleID"}),
}

V2_CSV_COLUMNS = [
    "schema_version",
    "sample_seq",
    "timestamp_local",
    "timestamp_utc",
    "ingest_timestamp",
    "captured_at_extruder",
    "captured_at_ls",
    "captured_at_spot",
    *V1_CSV_COLUMNS,
    "MainRamPosition_D0010",
    "ContainerPosition_D0012",
    "MainPress_quality",
    "MainPress_missing_reason",
    "MainPress_unit",
    "Temperature_quality",
    "Temperature_missing_reason",
    "Temperature_unit",
    "Speed_quality",
    "Speed_missing_reason",
    "Speed_unit",
    "BilletLength_quality",
    "BilletLength_missing_reason",
    "BilletLength_unit",
    "DIE_ID_derived",
    "Billet_CycleID_derived",
    "derivation_version",
    "cycle_confidence",
    "cycle_state",
]

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")


class CSVLoggerService:
    def __init__(self) -> None:
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.queue: queue.Queue[Optional[FactoryData]] = queue.Queue(maxsize=5000)
        self.logger = logging.getLogger("SmartFactoryLoggerV2")
        self._config_lock = threading.Lock()
        self._config_version = 0
        # CSV data logs path (User configured)
        self.active_log_dir = Path(config.LOG_PATH)
        self.fallback_log_dir = config.APP_DATA_DIR / "logs" / "data"
        self.auto_save = bool(config.AUTO_SAVE)
        self.csv_v2_enabled = bool(getattr(config, "CSV_V2_ENABLED", False))
        self.csv_v2_sidecar_enabled = bool(getattr(config, "CSV_V2_SIDECAR_ENABLED", True))
        self.csv_header = self._parse_header(config.CSV_HEADER)
        self._logpath_warned = False
        self._buffer_size = 0
        self._last_batch_size = 0
        self._sample_seq = 0
        self._sidecar_paths_written: set[str] = set()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="CSVLogger", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass
        if self.thread:
            self.thread.join(timeout=2.0)

    def enqueue(self, data: FactoryData) -> None:
        if not self.running:
            return
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            self.logger.warning("CSV log queue full. Dropping data.")

    def apply_config(
        self,
        *,
        log_path: Optional[Path] = None,
        auto_save: Optional[bool] = None,
        csv_header: Optional[str] = None,
        csv_v2_enabled: Optional[bool] = None,
        csv_v2_sidecar_enabled: Optional[bool] = None,
    ) -> bool:
        changed = False
        with self._config_lock:
            if log_path is not None:
                self.active_log_dir = Path(log_path)
                changed = True
            if auto_save is not None:
                self.auto_save = bool(auto_save)
                changed = True
            if csv_header is not None:
                self.csv_header = self._parse_header(csv_header)
                changed = True
            if csv_v2_enabled is not None:
                self.csv_v2_enabled = bool(csv_v2_enabled)
                changed = True
            if csv_v2_sidecar_enabled is not None:
                self.csv_v2_sidecar_enabled = bool(csv_v2_sidecar_enabled)
                changed = True
            if changed:
                self._config_version += 1
        return changed

    def _parse_header(self, header: str) -> list[str]:
        if not header:
            return list(V1_CSV_COLUMNS)
        parsed = [item.strip() for item in header.split(",") if item.strip()]
        if len(parsed) != len(V1_CSV_COLUMNS):
            self.logger.warning(
                "CSV header ignored because column count does not match v1 contract. expected=%s actual=%s",
                len(V1_CSV_COLUMNS),
                len(parsed),
            )
            return list(V1_CSV_COLUMNS)
        if not self._is_valid_v1_header_contract(parsed):
            return list(V1_CSV_COLUMNS)
        return parsed

    def _is_valid_v1_header_contract(self, parsed: list[str]) -> bool:
        for index, (canonical, label) in enumerate(zip(V1_CSV_COLUMNS, parsed), start=1):
            allowed = V1_CSV_HEADER_ALIASES.get(canonical, frozenset({canonical}))
            if label not in allowed:
                self.logger.warning(
                    (
                        "CSV header ignored because label does not match v1 position contract. "
                        "index=%s canonical=%s label=%s allowed=%s"
                    ),
                    index,
                    canonical,
                    label,
                    sorted(allowed),
                )
                return False
        return True

    def _ensure_dir(self, path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    def _get_log_dir(self) -> Path:
        with self._config_lock:
            active_dir = self.active_log_dir
            fallback_dir = self.fallback_log_dir
            warned = self._logpath_warned
        if self._ensure_dir(active_dir):
            return active_dir
        if active_dir != fallback_dir:
            if not warned:
                self.logger.warning(
                    "LOG_PATH not usable: %s. Using fallback: %s",
                    active_dir,
                    fallback_dir,
                )
                warned = True
            active_dir = fallback_dir
            self._ensure_dir(active_dir)
            with self._config_lock:
                self.active_log_dir = active_dir
                self._logpath_warned = warned
        return active_dir

    def _open_log_file(self, timestamp_str: str, prefix: str) -> Tuple[Optional[object], Optional[csv.writer]]:
        if not self.auto_save:
            return None, None
        filename = f"{prefix}_{timestamp_str}.csv"
        log_dir = self._get_log_dir()
        full_path = log_dir / filename
        try:
            handle = full_path.open("a", newline="", encoding="utf-8-sig")
            writer = csv.writer(handle)
            if handle.tell() == 0 and self.csv_header:
                writer.writerow(self.csv_header)
                handle.flush()
            self.logger.info("CSV log file opened: %s", full_path)
            return handle, writer
        except Exception as exc:
            self.logger.error("Failed to open CSV log file: %s", exc)
            if log_dir != self.fallback_log_dir:
                fallback_path = self.fallback_log_dir / filename
                try:
                    self._ensure_dir(self.fallback_log_dir)
                    handle = fallback_path.open("a", newline="", encoding="utf-8-sig")
                    writer = csv.writer(handle)
                    if handle.tell() == 0 and self.csv_header:
                        writer.writerow(self.csv_header)
                        handle.flush()
                    self.logger.warning("CSV log fallback path used: %s", fallback_path)
                    self.active_log_dir = self.fallback_log_dir
                    return handle, writer
                except Exception as exc2:
                    self.logger.error("Failed to open CSV log file (fallback): %s", exc2)
        return None, None

    def _open_v2_log_file(self, timestamp_str: str, prefix: str) -> Tuple[Optional[object], Optional[csv.writer]]:
        if not self.auto_save or not self.csv_v2_enabled:
            return None, None
        filename = f"{prefix}_{timestamp_str}.csv"
        log_dir = self._get_log_dir()
        full_path = log_dir / filename
        try:
            handle = full_path.open("a", newline="", encoding="utf-8-sig")
            writer = csv.writer(handle)
            if handle.tell() == 0:
                writer.writerow(V2_CSV_COLUMNS)
                handle.flush()
                self._write_v2_sidecar(full_path)
            self.logger.info("CSV v2 log file opened: %s", full_path)
            return handle, writer
        except Exception as exc:
            self.logger.warning("Failed to open CSV v2 log file: %s", exc)
            return None, None

    def _write_v2_sidecar(self, csv_path: Path) -> None:
        if not self.csv_v2_sidecar_enabled:
            return
        sidecar_path = csv_path.with_suffix(".metadata.json")
        sidecar_key = str(sidecar_path)
        if sidecar_key in self._sidecar_paths_written or sidecar_path.exists():
            self._sidecar_paths_written.add(sidecar_key)
            return
        payload = {
            "schema_metadata": {
                "schema_version": CSV_SCHEMA_VERSION,
                "v1_compatibility": True,
                "v1_columns": V1_CSV_COLUMNS,
                "v2_columns": V2_CSV_COLUMNS,
                "header_policy": (
                    "HEADERS.csv may rename v1 columns only when the column count and each "
                    "position-specific label match the v1 contract aliases."
                ),
                "position_read_feature_flag": "EXTRUDER.position_read_enabled or POSITION_READ_ENABLED",
                "v1_header_aliases": {
                    column: sorted(aliases) for column, aliases in V1_CSV_HEADER_ALIASES.items()
                },
                "writer": "CSVLoggerService",
                "created_at": datetime.now().astimezone().isoformat(),
            },
            "sensor_metadata": [
                {
                    "column_name": "MainPress",
                    "field_name": "Press",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "plc_address": "D0023 via D0020[3]",
                    "unit": "bar",
                    "mapping_status": "verified_by_code_and_device_doc",
                },
                {
                    "column_name": "Temperature",
                    "field_name": "Spot",
                    "source_system": "SPOT",
                    "device_id": "spot",
                    "plc_address": "",
                    "unit": "degC",
                    "mapping_status": "runtime_source",
                },
                {
                    "column_name": "Speed",
                    "field_name": "Speed",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "plc_address": "B1502",
                    "unit": "mm/s",
                    "mapping_status": "verified_by_code_and_device_doc",
                },
                {
                    "column_name": "BilletLength",
                    "field_name": "BilletLength",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "source_address": "D1911",
                    "plc_address": "D1911 via D1900[11]",
                    "unit": "mm",
                    "mapping_status": "hmi_confirmed",
                    "note": (
                        "HMI field observation confirmed D1911 is BilletLength in mm. "
                        "It records 0 during billet preheat/idle phases, then 600-690 mm while "
                        "the billet is loaded, and returns to 0 after loading completes. "
                        "B1880 Float32 LH matches the separate HMI Butt Length value, not this v1 column."
                    ),
                },
                {
                    "field_name": "ButtLength_HMI_B1880",
                    "physical_meaning": "HMI 버트 길이",
                    "type": "float",
                    "unit": "mm",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "source_address": "B1880",
                    "data_type": "Float32",
                    "word_order": "LH",
                    "mapping_status": "hmi_confirmed_separate_field",
                    "semantic_group": "butt_length",
                    "not_replacement_for": "BilletLength",
                    "related_v1_field": "BilletLength",
                    "quality_rule": {
                        "none": "missing",
                        "plc_read_failure": "source_error",
                        "empty_value": "source_missing",
                        "less_than_or_equal_zero": "invalid_candidate",
                        "range_10_to_200": "ok",
                        "outside_range": "invalid_candidate",
                    },
                    "missing_rule": {
                        "None": "missing",
                        "PLC read failure": "source_error",
                        "No value": "source_missing",
                    },
                    "notes": (
                        "B1880 Float32 LH is HMI butt length and must not be treated as "
                        "v1 BilletLength replacement."
                    ),
                },
                {
                    "column_name": "EndPos",
                    "field_name": "EndPos",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "plc_address": "D0421 via D0420[1]",
                    "unit": "mm",
                    "mapping_status": "hmi_confirmed_setting_value",
                    "note": (
                        "HMI field observation confirmed D0421 / 10.0 is the extrusion end "
                        "position setting value, not the moving actual position. D0010 / 10.0 "
                        "is the real-time main ram position, and D0012 / 10.0 is the real-time "
                        "container position."
                    ),
                },
                {
                    "column_name": "MainRamPosition_D0010",
                    "field_name": "MainRamPosition_D0010",
                    "physical_meaning": "Main ram actual position",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "source_address": "D0010",
                    "plc_address": "D0010 / 10.0",
                    "unit": "mm",
                    "mapping_status": "hmi_confirmed_actual_position",
                    "semantic_group": "position",
                    "read_feature_flag": "POSITION_READ_ENABLED",
                    "note": "HMI field observation confirmed this is the real-time main ram position.",
                },
                {
                    "column_name": "ContainerPosition_D0012",
                    "field_name": "ContainerPosition_D0012",
                    "physical_meaning": "Container actual position",
                    "source_system": "Extruder PLC",
                    "device_id": "extruder",
                    "source_address": "D0012",
                    "plc_address": "D0012 / 10.0",
                    "unit": "mm",
                    "mapping_status": "hmi_confirmed_actual_position",
                    "semantic_group": "position",
                    "read_feature_flag": "POSITION_READ_ENABLED",
                    "note": (
                        "HMI field observation confirmed this is the real-time container position. "
                        "It changes with billet loading and production motion."
                    ),
                },
            ],
            "derivation_metadata": {
                "DIE_ID": {
                    "derived": True,
                    "derivation_version": DERIVATION_VERSION,
                    "inputs": ["Count", "Speed", "Time", "state.json"],
                    "logic_summary": "Local heuristic increments DIE_ID when Count decreases.",
                },
                "Billet_CycleID": {
                    "derived": True,
                    "derivation_version": DERIVATION_VERSION,
                    "inputs": ["Count", "Speed", "state.json"],
                    "logic_summary": "Local heuristic emits Count when Speed is above CYCLE_SPEED_THRESHOLD.",
                },
            },
            "quality_rule_metadata": {
                "quality_values": ["unknown", "ok", "idle", "missing", "stale", "invalid", "mapping_unverified"],
                "mapping_status_values": [
                    "runtime_source",
                    "verified_by_code_and_device_doc",
                    "hmi_confirmed",
                    "hmi_confirmed_setting_value",
                    "hmi_confirmed_actual_position",
                    "hmi_confirmed_separate_field",
                    "mapping_unverified",
                ],
                "missing_reason_values": [
                    "not_missing",
                    "source_missing",
                    "source_error",
                    "stale_snapshot",
                    "mapping_unverified",
                    "invalid_value",
                ],
            },
        }
        try:
            sidecar_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._sidecar_paths_written.add(sidecar_key)
        except Exception as exc:
            self.logger.warning("Failed to write CSV v2 sidecar metadata: %s", exc)

    def _build_row(self, data: FactoryData, timestamp: datetime) -> list:
        date_s = timestamp.strftime("%Y-%m-%d")
        time_s = timestamp.strftime("%H:%M:%S.%f")[:-3]
        press_value = self._to_float(data.Press)
        row = [
            date_s,
            time_s,
            self._fmt(data.Spot),
            self._fmt(press_value),
            self._fmt(data.Billet_Length),
            self._fmt(data.Temp_F),
            self._fmt(data.Temp_B),
            self._fmt(data.Count),
            self._fmt(data.Speed),
            self._fmt(data.EndPos),
            self._fmt(data.Mold1),
            self._fmt(data.Mold2),
            self._fmt(data.Mold3),
            self._fmt(data.Mold4),
            self._fmt(data.Mold5),
            self._fmt(data.Mold6),
            self._fmt(data.Billet_Temp),
            self._fmt(data.At_Pre),
            self._fmt(data.At_Temp),
            self._escape_csv_text(data.Die_ID or ""),
            self._escape_csv_text(data.Billet_Cycle_ID or ""),
        ]
        return row

    def _build_v2_row(
        self,
        data: FactoryData,
        timestamp: datetime,
        ingest_timestamp: datetime,
        sample_seq: int,
        v1_row: list,
    ) -> list:
        local_timestamp = self._to_local_timestamp(timestamp)
        utc_timestamp = local_timestamp.astimezone(timezone.utc)
        mainpress_quality, mainpress_reason = self._quality_for_mainpress(data)
        temperature_quality, temperature_reason = self._quality_for_temperature(data)
        speed_quality, speed_reason = self._quality_for_speed(data)
        billet_quality, billet_reason = self._quality_for_billet_length(data)
        cycle_state = self._cycle_state(data)
        cycle_confidence = self._cycle_confidence(data, cycle_state)
        return [
            CSV_SCHEMA_VERSION,
            sample_seq,
            local_timestamp.isoformat(),
            utc_timestamp.isoformat().replace("+00:00", "Z"),
            ingest_timestamp.isoformat(),
            self._epoch_to_iso(data.captured_at_extruder),
            self._epoch_to_iso(data.captured_at_ls),
            self._epoch_to_iso(data.captured_at_spot),
            *v1_row,
            self._fmt(data.MainRamPosition_D0010),
            self._fmt(data.ContainerPosition_D0012),
            mainpress_quality,
            mainpress_reason,
            "bar",
            temperature_quality,
            temperature_reason,
            "degC",
            speed_quality,
            speed_reason,
            "mm/s",
            billet_quality,
            billet_reason,
            "mm",
            self._fmt_bool(data.Die_ID_derived if data.Die_ID_derived is not None else bool(data.Die_ID)),
            self._fmt_bool(
                data.Billet_Cycle_ID_derived
                if data.Billet_Cycle_ID_derived is not None
                else bool(data.Billet_Cycle_ID)
            ),
            self._escape_csv_text(data.derivation_version or DERIVATION_VERSION),
            self._fmt(cycle_confidence),
            cycle_state,
        ]

    def _parse_timestamp(self, data: FactoryData) -> datetime:
        timestamp_text = data.Time or ""
        try:
            if timestamp_text:
                return datetime.fromisoformat(timestamp_text)
            self.logger.warning(
                "CSV timestamp missing. Falling back to current time.",
                extra={"csv_time_value": timestamp_text},
            )
        except Exception as exc:
            self.logger.warning(
                "CSV timestamp invalid. Falling back to current time.",
                extra={"csv_time_value": timestamp_text, "csv_time_error": str(exc)},
            )
        return datetime.now()

    def _fmt(self, value: Optional[float]) -> str:
        if value is None:
            return ""
        try:
            if isinstance(value, (int, float)):
                if not isinstance(value, bool):
                    return str(value)
        except Exception:
            return ""
        return ""

    def _fmt_bool(self, value: bool) -> str:
        return "true" if value else "false"

    def _escape_csv_text(self, value: str) -> str:
        if value and value[0] in CSV_INJECTION_PREFIXES:
            return "'" + value
        return value

    def _to_local_timestamp(self, timestamp: datetime) -> datetime:
        if timestamp.tzinfo is not None:
            return timestamp.astimezone()
        return timestamp.replace(tzinfo=datetime.now().astimezone().tzinfo)

    def _epoch_to_iso(self, value: Optional[float]) -> str:
        if value is None:
            return ""
        try:
            return datetime.fromtimestamp(float(value)).astimezone().isoformat()
        except Exception:
            return ""

    def _quality_for_mainpress(self, data: FactoryData) -> tuple[str, str]:
        if data.Press is None:
            reason = "source_error" if data.extruder_snapshot_error else "source_missing"
            return "missing", reason
        if data.captured_at_extruder is None:
            return "stale", "stale_snapshot"
        if data.Press <= constants.PRESS_IDLE_MAX:
            return "idle", "not_missing"
        return "ok", "not_missing"

    def _quality_for_temperature(self, data: FactoryData) -> tuple[str, str]:
        if data.Spot is None:
            reason = "source_error" if data.spot_snapshot_error else "source_missing"
            return "missing", reason
        if data.captured_at_spot is None:
            return "stale", "stale_snapshot"
        if data.Spot <= 0:
            return "missing", "source_missing"
        return "ok", "not_missing"

    def _quality_for_speed(self, data: FactoryData) -> tuple[str, str]:
        if data.Speed is None:
            reason = "source_error" if data.extruder_snapshot_error else "source_missing"
            return "missing", reason
        if data.captured_at_extruder is None:
            return "stale", "stale_snapshot"
        if data.Speed <= constants.SPEED_IDLE_MAX:
            return "idle", "not_missing"
        return "ok", "not_missing"

    def _quality_for_billet_length(self, data: FactoryData) -> tuple[str, str]:
        if data.Billet_Length is None:
            reason = "source_error" if data.extruder_snapshot_error else "source_missing"
            return "missing", reason
        if data.Billet_Length <= 0:
            return "idle", "not_missing"
        return "ok", "not_missing"

    def _cycle_state(self, data: FactoryData) -> str:
        if data.cycle_state:
            return self._escape_csv_text(data.cycle_state)
        if data.Speed is None:
            return "unknown"
        if data.Speed > constants.CYCLE_SPEED_THRESHOLD:
            return "active"
        return "idle"

    def _cycle_confidence(self, data: FactoryData, cycle_state: str) -> Optional[float]:
        if data.cycle_confidence is not None:
            return data.cycle_confidence
        if cycle_state == "active" and data.Billet_Cycle_ID:
            return 0.5
        return None

    def _to_float(self, value: Optional[float]) -> float:
        try:
            return float(value) if value is not None else 0.0
        except Exception:
            return 0.0

    def _flush_buffer(
        self,
        writer: Optional[csv.writer],
        handle: Optional[object],
        buffer: Iterable[Tuple[list, datetime]],
    ) -> bool:
        rows = list(buffer)
        self._last_batch_size = len(rows)
        if not rows:
            return True
        if writer is None or handle is None:
            return False
        writer.writerows([row for row, _ in rows])
        handle.flush()
        return True

    def _flush_v2_buffer(
        self,
        writer: Optional[csv.writer],
        handle: Optional[object],
        buffer: Iterable[Tuple[list, datetime]],
    ) -> bool:
        rows = list(buffer)
        if not rows:
            return True
        if writer is None or handle is None:
            return False
        writer.writerows([row for row, _ in rows])
        handle.flush()
        return True

    def _close_file(self, handle: Optional[object]) -> None:
        if handle is None:
            return
        try:
            handle.close()
        except Exception:
            pass

    def get_runtime_state(self) -> dict[str, int | bool | str]:
        with self._config_lock:
            auto_save = self.auto_save
            log_path = str(self.active_log_dir)
            csv_v2_enabled = self.csv_v2_enabled
        return {
            "queue_size": self.queue.qsize(),
            "buffer_size": self._buffer_size,
            "last_batch_size": self._last_batch_size,
            "running": self.running,
            "auto_save": auto_save,
            "csv_v2_enabled": csv_v2_enabled,
            "log_path": log_path,
        }

    def _loop(self) -> None:
        buffer: list[Tuple[list, datetime]] = []
        v2_buffer: list[Tuple[list, datetime]] = []
        batch_size = 20
        flush_interval = 1.0
        last_flush_time = time.time()
        file_prefix = "Factory_Integrated_Log"
        v2_file_prefix = "Factory_Integrated_Log_v2"

        f_handle = None
        writer = None
        v2_handle = None
        v2_writer = None
        current_config_version = -1

        while True:
            try:
                with self._config_lock:
                    auto_save = self.auto_save
                    csv_v2_enabled = self.csv_v2_enabled
                    config_version = self._config_version

                if config_version != current_config_version:
                    current_config_version = config_version
                    if buffer:
                        if auto_save and (f_handle is None or writer is None):
                            f_handle, writer = self._open_log_file(
                                buffer[0][1].strftime("%Y%m%d_%H%M%S"),
                                prefix=file_prefix,
                            )
                        if self._flush_buffer(writer, f_handle, buffer):
                            buffer.clear()
                            self._buffer_size = 0
                        elif not auto_save:
                            buffer.clear()
                            self._buffer_size = 0
                    if v2_buffer:
                        if auto_save and csv_v2_enabled and (v2_handle is None or v2_writer is None):
                            v2_handle, v2_writer = self._open_v2_log_file(
                                v2_buffer[0][1].strftime("%Y%m%d_%H%M%S"),
                                prefix=v2_file_prefix,
                            )
                        if csv_v2_enabled and self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                            v2_buffer.clear()
                        else:
                            if csv_v2_enabled:
                                self.logger.warning("CSV v2 buffer dropped during config change.")
                            v2_buffer.clear()
                    self._close_file(f_handle)
                    self._close_file(v2_handle)
                    f_handle = None
                    writer = None
                    v2_handle = None
                    v2_writer = None

                item = None
                try:
                    item = self.queue.get(timeout=0.2)
                except queue.Empty:
                    item = None

                if item is None:
                    if not self.running:
                        break
                else:
                    timestamp = self._parse_timestamp(item)
                    row = self._build_row(item, timestamp)
                    v2_row = None
                    if csv_v2_enabled:
                        self._sample_seq += 1
                        v2_row = self._build_v2_row(
                            item,
                            timestamp,
                            datetime.now().astimezone(),
                            self._sample_seq,
                            row,
                        )

                    if not auto_save:
                        continue

                    if f_handle is None or writer is None:
                        f_handle, writer = self._open_log_file(
                            timestamp.strftime("%Y%m%d_%H%M%S"),
                            prefix=file_prefix,
                        )
                    if csv_v2_enabled and (v2_handle is None or v2_writer is None):
                        v2_handle, v2_writer = self._open_v2_log_file(
                            timestamp.strftime("%Y%m%d_%H%M%S"),
                            prefix=v2_file_prefix,
                        )

                    buffer.append((row, timestamp))
                    if v2_row is not None:
                        v2_buffer.append((v2_row, timestamp))
                    self._buffer_size = len(buffer)

                now = time.time()
                if buffer and (len(buffer) >= batch_size or (now - last_flush_time) > flush_interval):
                    if auto_save and (not f_handle or not writer):
                        ts = buffer[0][1].strftime("%Y%m%d_%H%M%S")
                        f_handle, writer = self._open_log_file(ts, prefix=file_prefix)

                    if auto_save and self._flush_buffer(writer, f_handle, buffer):
                        buffer.clear()
                        self._buffer_size = 0
                    elif not auto_save:
                        buffer.clear()
                        self._buffer_size = 0
                    if v2_buffer:
                        if auto_save and csv_v2_enabled and (not v2_handle or not v2_writer):
                            ts = v2_buffer[0][1].strftime("%Y%m%d_%H%M%S")
                            v2_handle, v2_writer = self._open_v2_log_file(ts, prefix=v2_file_prefix)
                        if auto_save and csv_v2_enabled and self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                            v2_buffer.clear()
                        else:
                            self.logger.warning("CSV v2 buffer dropped because v2 writer is unavailable.")
                            v2_buffer.clear()
                    last_flush_time = now
            except Exception as exc:
                self.logger.error("Error in CSV logger loop: %s", exc)
                self._close_file(f_handle)
                self._close_file(v2_handle)
                f_handle, writer = None, None
                v2_handle, v2_writer = None, None
                self._buffer_size = len(buffer)
                time.sleep(0.5)

        if buffer:
            try:
                if self.auto_save and (f_handle is None or writer is None):
                    f_handle, writer = self._open_log_file(
                        buffer[0][1].strftime("%Y%m%d_%H%M%S"),
                        prefix=file_prefix,
                    )
                if self._flush_buffer(writer, f_handle, buffer):
                    buffer.clear()
            except Exception:
                pass
        if v2_buffer:
            try:
                if self.csv_v2_enabled and (v2_handle is None or v2_writer is None):
                    v2_handle, v2_writer = self._open_v2_log_file(
                        v2_buffer[0][1].strftime("%Y%m%d_%H%M%S"),
                        prefix=v2_file_prefix,
                    )
                if self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                    v2_buffer.clear()
            except Exception as exc:
                self.logger.warning("CSV v2 final flush failed: %s", exc)
        self._buffer_size = 0
        self._close_file(f_handle)
        self._close_file(v2_handle)
        self.logger.info("CSV logger thread stopped.")


logger_service = CSVLoggerService()
