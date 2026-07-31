import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import logging
import math
import queue
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional, Iterable, Tuple
from uuid import uuid4

from .. import config
from .. import constants
from backend.FacilityData.changeover_candidate_resolution_fact import (
    CHANGEOVER_CANDIDATE_RESOLUTION_FACT_FILENAME,
    PROCESS_PHASE_EVENT_FACT_FILENAME,
    build_changeover_candidate_resolution_fact_manifest,
    build_process_phase_event_fact_manifest,
)
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.spot_observation import (
    SPOT_INVALID_SENTINEL_MEANINGS,
    SPOT_INVALID_SENTINEL_VALUES,
    SPOT_TEMPERATURE_MAX_C,
    SPOT_TEMPERATURE_MIN_C,
)
from backend.FacilityData.spot_diagnostics import (
    DIAGNOSTICS_BINDING_STATUSES,
    DIAGNOSTICS_CAPTURE_STATUSES,
    DIAGNOSTICS_SUPPRESSION_REASONS,
    configured_diagnostics_max_age_ms,
    parse_diagnostics_field_status,
    parse_diagnostics_missing_fields,
)
from backend.version import get_runtime_info, resolve_runtime_git_commit, validate_git_commit
from backend.FacilityData.process_phase import (
    PROCESS_PHASE_RULE_VERSION,
    ProcessPhaseDecision,
    ProcessPhaseInput,
    derive_process_phase_candidate,
)
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_FILENAME,
    build_spot_observation_fact_manifest,
    build_spot_observation_key,
    parse_spot_diagnostic_evidence_codes,
)
from backend.FacilityData.spot_config_provenance import build_spot_configuration_snapshot
from backend.FacilityData.spot_image_fact import (
    SPOT_IMAGE_FACT_FILENAME,
    SPOT_IMAGE_FACT_FINAL_MANIFEST_FILENAME,
    build_spot_image_fact_manifest,
)
from backend.FacilityData.temperature_operational import (
    SPOT_ROW_FRESHNESS_RULE_VERSION,
    TEMPERATURE_OPERATIONAL_RULE_VERSION,
    TemperatureOperationalDecision,
    TemperatureOperationalInput,
    derive_temperature_operational_fields,
)


CSV_SCHEMA_VERSION_V2_3 = "2.3.0"
CSV_SCHEMA_VERSION_V2_4 = "2.4.0"
CSV_SCHEMA_VERSION_V2_5 = "2.5.0"
DERIVATION_VERSION = "cycle-heuristic-v1"
PROCESS_STATE_ONLINE_RULE_VERSION = "process-state-online-v1"
OPERATOR_METADATA_VERSION = "1.0.0"
TEMPERATURE_STATUS_RULE_VERSION = "temperature-status-shadow-v1"
SPOT_FRESHNESS_RULE_VERSION = "spot-freshness-shadow-v1"
SPOT_SENTINEL_MAP_VERSION = "spot-sentinel-ametek-rest-v1"
SPOT_VERIFIED_NO_TARGET_VALUES: tuple[str, ...] = ()
SPOT_CACHE_EXPIRY_THRESHOLD_SEC = 15.0
SPOT_TEMPERATURE_RAW_MAX_LENGTH = 256
TEMPERATURE_QUALITY_MAPPING_VERSION = "temperature-quality-operational-v1"

SPOT_TEMPERATURE_SHADOW_COLUMNS = [
    "logger_service_instance_id",
    "logger_service_started_at",
    "extruder_process_state_online",
    "process_state_online_rule_version",
    "spot_target_state_observed_shadow",
    "spot_target_state_observed_source",
    "label_validation_state",
    "temperature_status_shadow",
    "temperature_status_rule_version",
    "spot_poll_status",
    "spot_raw_validity",
    "spot_cache_status",
    "spot_source_freshness",
    "temperature_value_origin",
    "cache_fallback_allowed",
    "spot_service_instance_id",
    "spot_service_started_at",
    "spot_poll_seq",
    "spot_observation_seq",
    "spot_temperature_observed_c",
    "spot_temperature_raw",
    "spot_temperature_raw_truncated",
    "spot_raw_payload_hash",
    "spot_raw_payload_encoding",
    "spot_http_status_code",
    "spot_device_status_code",
    "spot_error_code",
    "spot_poll_duration_ms",
    "spot_response_content_length",
    "spot_last_poll_started_at",
    "spot_last_poll_completed_at",
    "spot_last_response_at",
    "spot_last_valid_value_at",
    "spot_snapshot_age_ms",
    "spot_value_age_ms",
]

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

V2_3_CSV_COLUMNS = [
    "schema_version",
    "sample_seq",
    "timestamp_local",
    "timestamp_utc",
    "ingest_timestamp",
    "captured_at_extruder",
    "captured_at_ls",
    "captured_at_spot",
    "Product_No_operator",
    "Mold_No_operator",
    "operator_metadata_valid",
    "operator_metadata_missing_fields",
    "operator_metadata_updated_at",
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
    *SPOT_TEMPERATURE_SHADOW_COLUMNS,
]

V2_4_OPERATIONAL_COLUMNS = [
    "temperature_output_status",
    "temperature_unavailable_reason",
    "temperature_expectedness_candidate",
    "temperature_under_range_cause_candidate",
    "temperature_cause_confidence",
    "temperature_cause_evidence_codes",
    "spot_effective_age_ms_at_row",
    "spot_effective_freshness_at_row",
    "spot_effective_value_age_ms_at_row",
    "spot_row_age_clock_status",
    "process_phase_candidate",
    "process_phase_rule_version",
    "phase_confirmation_state",
    "process_segment_id",
    "changeover_candidate_id",
    "spot_observation_key",
    "spot_image_capture_id_nearest",
    "spot_image_path_nearest",
    "spot_image_link_status_nearest",
    "spot_image_link_age_ms_nearest",
]

V2_4_CSV_COLUMNS = [
    *V2_3_CSV_COLUMNS,
    *V2_4_OPERATIONAL_COLUMNS,
]

V2_5_OPERATIONAL_HARDENING_COLUMNS = [
    "spot_value_age_clock_status",
]

V2_5_CSV_COLUMNS = [
    *V2_4_CSV_COLUMNS,
    *V2_5_OPERATIONAL_HARDENING_COLUMNS,
]

V2_CSV_COLUMNS = V2_3_CSV_COLUMNS

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")


_CHANGEOVER_LIFECYCLE_PHASES = {
    "setup_candidate",
    "pre_changeover_hold_candidate",
    "die_change_candidate",
    "setup_alignment_candidate",
    "changeover_candidate",
}
_CHANGEOVER_TERMINAL_EVIDENCE_PHASES = {
    "setup_candidate",
    "die_change_candidate",
    "setup_alignment_candidate",
    "changeover_candidate",
}
_PROCESS_SEGMENT_PHASES = {
    "production_stable",
    "production_stabilizing",
    "stopped_after_production_candidate",
    "possible_pre_changeover_hold",
    "idle_candidate",
    "unknown",
}

# Caller-supplied realtime hold candidates are weak until post-hoc evidence confirms them.
_EXTERNALLY_SUPPLIED_WEAK_PHASES = {
    "pre_changeover_hold_candidate": "stopped_after_production_candidate",
    "possible_pre_changeover_hold": "stopped_after_production_candidate",
}


@dataclass(frozen=True)
class V2CsvContract:
    schema_version: str
    columns: tuple[str, ...]
    operational_fields_enabled: bool
    temperature_hardening_enabled: bool
    column_hash: str


@dataclass
class _ProcessPhaseRuntimeState:
    committed_product_no: Optional[str] = None
    committed_mold_no: Optional[str] = None
    count_value: Optional[int] = None
    count_first_observed_at: Optional[datetime] = None
    count_recent_production_motion: bool = False
    active_changeover_candidate_id: Optional[str] = None
    active_changeover_start_sample_seq: Optional[int] = None
    active_changeover_terminal_eligible: bool = False
    process_segment_id: Optional[str] = None
    process_segment_phase: Optional[str] = None
    process_segment_start_sample_seq: Optional[int] = None


def _v2_column_hash(columns: Iterable[str]) -> str:
    return hashlib.sha256(
        json.dumps(list(columns), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class CSVLoggerService:
    def __init__(self, *, require_runtime_manifest_state: bool = False) -> None:
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
        self.csv_v1_enabled = bool(getattr(config, "CSV_V1_ENABLED", True))
        self.csv_v2_enabled = bool(getattr(config, "CSV_V2_ENABLED", False))
        self.csv_v2_sidecar_enabled = bool(getattr(config, "CSV_V2_SIDECAR_ENABLED", True))
        self.csv_v2_operational_fields_enabled = bool(
            getattr(config, "CSV_V2_OPERATIONAL_FIELDS_ENABLED", False)
        )
        self.csv_v2_temperature_hardening_enabled = bool(
            getattr(config, "CSV_V2_TEMPERATURE_HARDENING_ENABLED", False)
        )
        self._validate_temperature_hardening_contract(
            operational_fields_enabled=self.csv_v2_operational_fields_enabled,
            temperature_hardening_enabled=self.csv_v2_temperature_hardening_enabled,
        )
        self._active_v2_contract: Optional[V2CsvContract] = None
        self._ensure_csv_writer_enabled()
        self.csv_header = self._parse_header(config.CSV_HEADER)
        self._logpath_warned = False
        self._buffer_size = 0
        self._last_batch_size = 0
        self._drop_count = 0
        self._last_drop_at: Optional[float] = None
        self._last_enqueue_at: Optional[float] = None
        self._last_write_at: Optional[float] = None
        self._payload_bytes_ema: Optional[float] = None
        self._runtime_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._sample_seq = 0
        self.logger_service_instance_id = str(uuid4())
        self.logger_service_started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._sidecar_paths_written: set[str] = set()
        self._process_phase_runtime_state = _ProcessPhaseRuntimeState()
        self._v2_4_operational_lock = threading.Lock()
        self._v2_4_operational_rows_total = 0
        self._v2_4_temperature_output_status_counts: Counter[str] = Counter()
        self._v2_4_temperature_unavailable_reason_counts: Counter[str] = Counter()
        self._v2_4_sentinel_device_status_counts: Counter[str] = Counter()
        self._v2_4_process_phase_candidate_counts: Counter[str] = Counter()
        self._v2_4_stale_threshold_breach_count = 0
        self._v2_4_observation_fact_link_failure_count = 0
        self._v2_4_cached_fallback_accepted_count = 0
        self._v2_4_cached_fallback_rejected_count = 0
        self._v2_4_cached_fallback_rejected_reason_counts: Counter[str] = Counter()
        self._v2_4_origin_decision_mismatch_count = 0
        self._v2_4_comparator_unverified_count = 0
        self._v2_4_diagnostics_capture_status_counts: Counter[str] = Counter()
        self._v2_4_diagnostics_binding_status_counts: Counter[str] = Counter()
        self._v2_4_diagnostics_cause_suppressed_count = 0
        self._v2_4_diagnostics_cause_suppressed_reason_counts: Counter[str] = Counter()
        self._v2_4_unsupported_evidence_suppressed_count = 0
        self._v2_4_value_age_clock_anomaly_count = 0
        self._v2_4_last_sample_seq: Optional[int] = None
        self._v2_4_last_updated_at: Optional[str] = None
        self._current_v2_csv_path: Optional[Path] = None
        self._v2_persisted_sample_seq_by_path: dict[str, int] = {}
        self._v2_persisted_at_by_path: dict[str, str] = {}
        self._shutdown_flush_succeeded: Optional[bool] = None
        self._runtime_write_failure_observed = False
        self._finalize_spot_image_manifest_on_stop = True
        self._finalize_spot_observation_manifest_on_stop = True
        self._require_runtime_manifest_state = bool(require_runtime_manifest_state)

    def start(self) -> None:
        with self._lifecycle_lock:
            existing_thread = self.thread
            if self.running:
                if existing_thread is None or not existing_thread.is_alive():
                    raise RuntimeError(
                        "CSV logger is marked running without a live worker thread."
                    )
                return
            if existing_thread is not None:
                raise RuntimeError(
                    "CSV logger cannot start until the previous worker generation "
                    "has completed stop()."
                )
            self.thread = None
            self._shutdown_flush_succeeded = False
            self._runtime_write_failure_observed = False
            self._finalize_spot_image_manifest_on_stop = True
            self._finalize_spot_observation_manifest_on_stop = True
            self.running = True
            self.thread = threading.Thread(target=self._loop, name="CSVLogger", daemon=True)
            self.thread.start()

    def stop(
        self,
        *,
        timeout_sec: Optional[float] = 2.0,
        finalize_spot_image_manifest: bool = True,
        finalize_spot_observation_manifest: bool = True,
    ) -> bool:
        with self._lifecycle_lock:
            retiring_thread = self.thread
            if (
                retiring_thread is not None
                and retiring_thread.is_alive()
                and not finalize_spot_image_manifest
            ):
                # Once closeout is unsafe for a logger generation, a repeated
                # stop must not re-enable its final manifest.
                self._finalize_spot_image_manifest_on_stop = False
            if (
                retiring_thread is not None
                and retiring_thread.is_alive()
                and not finalize_spot_observation_manifest
            ):
                self._finalize_spot_observation_manifest_on_stop = False
            if self.running:
                self.running = False
                try:
                    self.queue.put_nowait(None)
                except queue.Full:
                    pass
        if retiring_thread:
            retiring_thread.join(timeout=timeout_sec)
            stopped = not retiring_thread.is_alive()
            if not stopped:
                self.logger.warning("CSV logger thread did not stop within %.1f seconds.", timeout_sec)
            elif self._shutdown_flush_succeeded is not True:
                self.logger.warning("CSV logger stopped without a durable final flush.")
            if stopped:
                with self._lifecycle_lock:
                    flush_succeeded = self._shutdown_flush_succeeded is True
                    if self.thread is retiring_thread:
                        self.thread = None
            else:
                flush_succeeded = False
            return stopped and flush_succeeded
        with self._lifecycle_lock:
            if self._shutdown_flush_succeeded is None:
                return True
            return self._shutdown_flush_succeeded is True

    def enqueue(self, data: FactoryData) -> None:
        payload_bytes = self._estimate_factory_data_bytes(data)
        now = time.time()
        with self._lifecycle_lock:
            if not self.running:
                return
            try:
                self.queue.put_nowait(data)
            except queue.Full:
                with self._runtime_lock:
                    self._drop_count += 1
                    self._last_drop_at = time.time()
                self.logger.warning("CSV log queue full. Dropping data.")
                return
            with self._runtime_lock:
                self._last_enqueue_at = now
                if self._payload_bytes_ema is None:
                    self._payload_bytes_ema = float(payload_bytes)
                else:
                    self._payload_bytes_ema = (self._payload_bytes_ema * 0.8) + (float(payload_bytes) * 0.2)

    def _estimate_factory_data_bytes(self, data: FactoryData) -> int:
        try:
            return max(0, len(data.model_dump_json()) * 2)
        except Exception:
            return 1024

    def apply_config(
        self,
        *,
        log_path: Optional[Path] = None,
        auto_save: Optional[bool] = None,
        csv_header: Optional[str] = None,
        csv_v1_enabled: Optional[bool] = None,
        csv_v2_enabled: Optional[bool] = None,
        csv_v2_sidecar_enabled: Optional[bool] = None,
        csv_v2_operational_fields_enabled: Optional[bool] = None,
        csv_v2_temperature_hardening_enabled: Optional[bool] = None,
    ) -> bool:
        changed = False
        with self._config_lock:
            next_operational_enabled = (
                self.csv_v2_operational_fields_enabled
                if csv_v2_operational_fields_enabled is None
                else bool(csv_v2_operational_fields_enabled)
            )
            next_hardening_enabled = (
                self.csv_v2_temperature_hardening_enabled
                if csv_v2_temperature_hardening_enabled is None
                else bool(csv_v2_temperature_hardening_enabled)
            )
            self._validate_temperature_hardening_contract(
                operational_fields_enabled=next_operational_enabled,
                temperature_hardening_enabled=next_hardening_enabled,
            )
            if log_path is not None:
                self.active_log_dir = Path(log_path)
                changed = True
            if auto_save is not None:
                self.auto_save = bool(auto_save)
                changed = True
            if csv_header is not None:
                self.csv_header = self._parse_header(csv_header)
                changed = True
            if csv_v1_enabled is not None:
                self.csv_v1_enabled = bool(csv_v1_enabled)
                changed = True
            if csv_v2_enabled is not None:
                self.csv_v2_enabled = bool(csv_v2_enabled)
                changed = True
            if (
                next_operational_enabled != self.csv_v2_operational_fields_enabled
                or next_hardening_enabled != self.csv_v2_temperature_hardening_enabled
            ):
                self.csv_v2_operational_fields_enabled = next_operational_enabled
                self.csv_v2_temperature_hardening_enabled = next_hardening_enabled
                self._active_v2_contract = None
                changed = True
            if csv_v2_sidecar_enabled is not None:
                self.csv_v2_sidecar_enabled = bool(csv_v2_sidecar_enabled)
                changed = True
            if changed:
                self._ensure_csv_writer_enabled()
            if changed:
                self._config_version += 1
        return changed

    @staticmethod
    def _validate_temperature_hardening_contract(
        *,
        operational_fields_enabled: bool,
        temperature_hardening_enabled: bool,
    ) -> None:
        if temperature_hardening_enabled and not operational_fields_enabled:
            raise ValueError(
                "csv_v2_temperature_hardening_enabled requires "
                "csv_v2_operational_fields_enabled=true"
            )

    def _ensure_csv_writer_enabled(self) -> None:
        if not self.auto_save:
            return
        if self.csv_v1_enabled or self.csv_v2_enabled:
            return
        self.csv_v1_enabled = True
        self.logger.warning(
            "CSV logging cannot disable both v1 and v2 writers while auto_save is enabled. "
            "Forcing csv_v1_enabled=True."
        )

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
        if not self.auto_save or not self.csv_v1_enabled:
            return None, None
        return self._open_v1_log_file_unchecked(timestamp_str, prefix)

    def _open_v1_log_file_for_drain(
        self,
        timestamp_str: str,
        prefix: str,
    ) -> Tuple[Optional[object], Optional[csv.writer]]:
        if not self.auto_save:
            return None, None
        return self._open_v1_log_file_unchecked(timestamp_str, prefix)

    def _open_v1_log_file_unchecked(
        self,
        timestamp_str: str,
        prefix: str,
    ) -> Tuple[Optional[object], Optional[csv.writer]]:
        filename = f"{prefix}_{timestamp_str}.csv"
        log_dir = self._get_log_dir()
        full_path = log_dir / filename
        handle = None
        try:
            handle = full_path.open("a", newline="", encoding="utf-8-sig")
            writer = csv.writer(handle)
            if handle.tell() == 0 and self.csv_header:
                writer.writerow(self.csv_header)
                handle.flush()
            self.logger.info("CSV log file opened: %s", full_path)
            return handle, writer
        except Exception as exc:
            self._close_file(handle)
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

    def _resolve_v2_contract(self) -> V2CsvContract:
        operational_enabled = bool(self.csv_v2_operational_fields_enabled)
        hardening_enabled = bool(self.csv_v2_temperature_hardening_enabled)
        if hardening_enabled:
            columns = tuple(V2_5_CSV_COLUMNS)
            schema_version = CSV_SCHEMA_VERSION_V2_5
        elif operational_enabled:
            columns = tuple(V2_4_CSV_COLUMNS)
            schema_version = CSV_SCHEMA_VERSION_V2_4
        else:
            columns = tuple(V2_3_CSV_COLUMNS)
            schema_version = CSV_SCHEMA_VERSION_V2_3
        return V2CsvContract(
            schema_version=schema_version,
            columns=columns,
            operational_fields_enabled=operational_enabled,
            temperature_hardening_enabled=hardening_enabled,
            column_hash=_v2_column_hash(columns),
        )

    def _get_active_v2_contract(self) -> V2CsvContract:
        if self._active_v2_contract is None:
            self._active_v2_contract = self._resolve_v2_contract()
        return self._active_v2_contract

    def _v2_rollover_path_for_contract(self, csv_path: Path, contract: V2CsvContract) -> Path:
        schema_suffix = contract.schema_version.replace(".", "_")
        candidate = csv_path.with_name(f"{csv_path.stem}_{schema_suffix}{csv_path.suffix}")
        if candidate == csv_path:
            return csv_path
        return candidate

    def _open_v2_log_file(self, timestamp_str: str, prefix: str) -> Tuple[Optional[object], Optional[csv.writer]]:
        if not self.auto_save or not self.csv_v2_enabled:
            return None, None
        contract = self._get_active_v2_contract()
        filename = f"{prefix}_{timestamp_str}.csv"
        log_dir = self._get_log_dir()
        full_path = log_dir / filename
        handle = None
        try:
            if full_path.exists() and full_path.stat().st_size > 0:
                if not self._v2_header_matches_current_schema(full_path, contract):
                    if not self._v2_header_matches_known_schema(full_path):
                        self.logger.error(
                            "CSV v2 schema mismatch. Refusing append to existing file: %s",
                            full_path,
                        )
                        return None, None
                    rollover_path = self._v2_rollover_path_for_contract(full_path, contract)
                    self.logger.info(
                        "CSV v2 schema rollover selected: previous=%s next=%s schema=%s",
                        full_path,
                        rollover_path,
                        contract.schema_version,
                    )
                    full_path = rollover_path
                    if full_path.exists() and full_path.stat().st_size > 0:
                        if not self._v2_header_matches_current_schema(full_path, contract):
                            self.logger.error(
                                "CSV v2 rollover target schema mismatch. Refusing append: %s",
                                full_path,
                            )
                            return None, None

            handle = full_path.open("a", newline="", encoding="utf-8-sig")
            writer = csv.writer(handle)
            if handle.tell() == 0:
                writer.writerow(list(contract.columns))
                handle.flush()
            self._write_v2_sidecar(full_path, contract)
            self._current_v2_csv_path = full_path
            self.logger.info("CSV v2 log file opened: %s", full_path)
            return handle, writer
        except Exception as exc:
            self._close_file(handle)
            self.logger.warning("Failed to open CSV v2 log file: %s", exc)
            return None, None

    def _v2_header_matches_known_schema(self, csv_path: Path) -> bool:
        try:
            with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
        except Exception as exc:
            self.logger.warning("Failed to read CSV v2 header for schema rollover check: %s", exc)
            return False
        if header in (V2_3_CSV_COLUMNS, V2_4_CSV_COLUMNS, V2_5_CSV_COLUMNS):
            return True
        if not header:
            return False
        return header[: len(V2_3_CSV_COLUMNS)] == V2_3_CSV_COLUMNS


    def _v2_header_matches_current_schema(
        self,
        csv_path: Path,
        contract: Optional[V2CsvContract] = None,
    ) -> bool:
        active_contract = contract or self._get_active_v2_contract()
        try:
            with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
        except Exception as exc:
            self.logger.warning("Failed to read CSV v2 header for compatibility check: %s", exc)
            return False
        expected_columns = list(active_contract.columns)
        if header != expected_columns:
            expected_count = len(expected_columns)
            actual_count = len(header or [])
            self.logger.error(
                "CSV v2 header mismatch: expected_columns=%s actual_columns=%s path=%s",
                expected_count,
                actual_count,
                csv_path,
            )
            return False
        return True

    def _spot_temperature_shadow_metadata(self, contract: Optional[V2CsvContract] = None) -> dict:
        sentinel_payload = {
            "version": SPOT_SENTINEL_MAP_VERSION,
            "verified_no_target_values": list(SPOT_VERIFIED_NO_TARGET_VALUES),
            "invalid_sentinel_values": list(SPOT_INVALID_SENTINEL_VALUES),
            "invalid_sentinel_meanings": dict(SPOT_INVALID_SENTINEL_MEANINGS),
            "documented_temperature_sentinels": {
                "under_range": "6553.4",
                "over_range": "6553.5",
            },
            "documentation_reference": "docs/reference/ametek_land_spot.pdf",
            "document_title": "SPOT+ Family REST API User Guide",
            "document_issue": "2",
            "repository_relative_path": "docs/reference/ametek_land_spot.pdf",
            "document_sha256": "c8d315fafd796075545558afcca894e0f1855fc3ba6ebc2f875e95ca1d39bf22",
            "page_numbers": [7],
            "verified_at": "2026-06-24",
            "verification_method": "local_pdf_text_extraction_pypdf",
            "pdf_verified": True,
            "verified_no_target_server_pc_verified": False,
            "server_pc_verified": False,
        }
        sentinel_hash = hashlib.sha256(
            json.dumps(sentinel_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        active_contract = contract or self._get_active_v2_contract()
        return {
            "schema_version": active_contract.schema_version,
            "shadow_columns": SPOT_TEMPERATURE_SHADOW_COLUMNS,
            "temperature_status_rule_version": TEMPERATURE_STATUS_RULE_VERSION,
            "process_state_online_rule_version": PROCESS_STATE_ONLINE_RULE_VERSION,
            "spot_freshness_rule_version": SPOT_FRESHNESS_RULE_VERSION,
            "spot_temperature_min_c": SPOT_TEMPERATURE_MIN_C,
            "spot_temperature_max_c": SPOT_TEMPERATURE_MAX_C,
            "cache_expiry_threshold_sec": SPOT_CACHE_EXPIRY_THRESHOLD_SEC,
            "poll_freshness_threshold_sec": float(getattr(config, "SPOT_REFRESH_INTERVAL", 3.0)) * 3.0,
            "poll_freshness_threshold_status": "candidate_unverified_server_pc",
            "raw_payload_realtime_csv_policy": "temporary validation-period repetition; long-term storage belongs in spot_observation_fact",
            "spot_temperature_raw_max_length": SPOT_TEMPERATURE_RAW_MAX_LENGTH,
            "sentinel_map": sentinel_payload,
            "sentinel_map_sha256": sentinel_hash,
            "v2_3_policy": "instrumentation_shadow_only; operational truth requires v2.4.0+ operational fields",
        }

    def _spot_configuration_snapshot(self, runtime_git_commit: str | None) -> dict[str, Any]:
        return build_spot_configuration_snapshot(
            config,
            runtime_git_commit=runtime_git_commit,
            device_readback_status="not_supported",
        )

    def _spot_image_fact_manifest(self, log_path: Path) -> dict[str, Any]:
        raw_capture_path = str(getattr(config, "SPOT_IMAGE_CAPTURE_PATH", "spot_images") or "spot_images").strip()
        capture_root = Path(raw_capture_path or "spot_images")
        if not capture_root.is_absolute():
            capture_root = log_path / capture_root
        try:
            from backend.FacilityData.drivers import spot_api

            health = spot_api.get_spot_image_capture_health()
            runtime_stats = spot_api.get_spot_image_capture_manifest_stats(
                fact_path=log_path / SPOT_IMAGE_FACT_FILENAME,
            )
        except Exception as exc:
            if self._require_runtime_manifest_state:
                raise RuntimeError(
                    "SPOT image fact runtime manifest state is unavailable"
                ) from exc
            health = {}
            runtime_stats = None
        if runtime_stats is None and self._require_runtime_manifest_state:
            raise RuntimeError(
                "SPOT image fact runtime manifest path does not match closeout path"
            )
        mode = str(health.get("mode") or getattr(config, "SPOT_IMAGE_CAPTURE_MODE", "off") or "off")
        enabled = bool(health.get("enabled", getattr(config, "SPOT_IMAGE_CAPTURE_ENABLED", False)))
        return build_spot_image_fact_manifest(
            log_path=log_path,
            capture_root=capture_root,
            enabled=enabled,
            mode=mode,
            health=health,
            runtime_stats=runtime_stats,
        )

    def write_spot_image_fact_final_manifest(self, log_path: Optional[Path] = None) -> Path:
        target_dir = Path(log_path) if log_path is not None else self._get_log_dir()
        self._ensure_dir(target_dir)
        manifest = self._spot_image_fact_manifest(target_dir)
        final_path = target_dir / SPOT_IMAGE_FACT_FINAL_MANIFEST_FILENAME
        temp_path = final_path.with_name(f"{final_path.name}.tmp")
        temp_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(final_path)
        return final_path

    def _write_spot_image_fact_final_manifest_safely(
        self,
        log_path: Optional[Path] = None,
    ) -> bool:
        try:
            self.write_spot_image_fact_final_manifest(log_path)
        except Exception as exc:
            self.logger.warning("Failed to write SPOT image fact final manifest: %s", exc)
            return False
        return True

    def _changeover_candidate_resolution_fact_manifest(self, log_path: Path) -> dict[str, Any]:
        return build_changeover_candidate_resolution_fact_manifest(
            fact_path=log_path / CHANGEOVER_CANDIDATE_RESOLUTION_FACT_FILENAME,
        )

    def _process_phase_event_fact_manifest(self, log_path: Path) -> dict[str, Any]:
        return build_process_phase_event_fact_manifest(
            fact_path=log_path / PROCESS_PHASE_EVENT_FACT_FILENAME,
        )

    def _spot_observation_fact_manifest(self, log_path: Path) -> dict[str, Any]:
        spot_api_module: Any | None = None
        try:
            from backend.FacilityData.drivers import spot_api as imported_spot_api

            spot_api_module = imported_spot_api
            health = spot_api_module.get_spot_observation_fact_health()
        except Exception:
            health = {}
        enabled = bool(health.get("enabled", getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)))
        fact_path = log_path / SPOT_OBSERVATION_FACT_FILENAME
        initialization_failure_count = self._ensure_spot_observation_fact_file(
            fact_path,
            enabled=enabled,
        )
        runtime_summary = (
            spot_api_module.get_spot_observation_fact_manifest_summary(
                fact_path=fact_path,
                allow_offline_rebuild=not self._require_runtime_manifest_state,
            )
            if spot_api_module is not None
            else None
        )
        if runtime_summary is None and self._require_runtime_manifest_state:
            raise RuntimeError(
                "SPOT observation fact runtime manifest state is unavailable"
            )
        return build_spot_observation_fact_manifest(
            fact_path=fact_path,
            enabled=enabled,
            write_failure_count=(
                int(health.get("write_failure_count", 0) or 0) + initialization_failure_count
            ),
            spool_pending_count=int(health.get("spool_pending_count", 0) or 0),
            path=SPOT_OBSERVATION_FACT_FILENAME,
            summary=runtime_summary,
        )

    def _ensure_spot_observation_fact_file(self, fact_path: Path, *, enabled: bool) -> int:
        if not enabled:
            return 0
        try:
            from backend.FacilityData.drivers import spot_api

            initialized = spot_api.ensure_spot_observation_fact_initialized(
                fact_path=fact_path,
                allow_offline_rebuild=not self._require_runtime_manifest_state,
            )
            if initialized:
                return 0
        except Exception as exc:
            self.logger.warning(
                "Failed to initialize enabled SPOT observation fact: %s",
                exc,
            )
            return 1
        self.logger.warning("Failed to initialize enabled SPOT observation fact: %s", fact_path.name)
        return 1

    def refresh_spot_observation_fact_manifest_for_csv(
        self,
        csv_path: Path,
        *,
        closeout_reason: str = "runtime-close",
    ) -> Optional[Path]:
        metadata_path = csv_path.with_suffix(".metadata.json")
        if not metadata_path.exists():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("Failed to read CSV v2 sidecar for observation fact refresh: %s", exc)
            return None
        spot_api_module: Any | None = None
        try:
            from backend.FacilityData.drivers import spot_api as imported_spot_api

            spot_api_module = imported_spot_api
            health = spot_api_module.get_spot_observation_fact_health()
        except Exception:
            health = {}
        enabled = bool(health.get("enabled", getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)))
        fact_path = csv_path.parent / SPOT_OBSERVATION_FACT_FILENAME
        initialization_failure_count = self._ensure_spot_observation_fact_file(
            fact_path,
            enabled=enabled,
        )
        try:
            if spot_api_module is None:
                raise RuntimeError(
                    "SPOT observation fact runtime summary is unavailable"
                )
            with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                runtime_summary = (
                    spot_api_module.get_spot_observation_fact_manifest_summary(
                        fact_path=fact_path,
                        realtime_rows=csv.DictReader(handle),
                        allow_offline_rebuild=not self._require_runtime_manifest_state,
                    )
                )
                observation_fact_manifest = build_spot_observation_fact_manifest(
                    fact_path=fact_path,
                    enabled=enabled,
                    write_failure_count=(
                        int(health.get("write_failure_count", 0) or 0)
                        + initialization_failure_count
                    ),
                    spool_pending_count=int(
                        health.get("spool_pending_count", 0) or 0
                    ),
                    path=SPOT_OBSERVATION_FACT_FILENAME,
                    summary=runtime_summary,
                )
        except Exception as exc:
            self.logger.warning(
                "Failed to build refreshed CSV v2 observation fact manifest: %s",
                exc,
            )
            return None
        csv_path_key = str(csv_path)
        with self._runtime_lock:
            final_persisted_sample_seq = self._v2_persisted_sample_seq_by_path.get(
                csv_path_key
            )
            persisted_at = self._v2_persisted_at_by_path.get(csv_path_key)
        if (
            (final_persisted_sample_seq is None or persisted_at is None)
            and not self._require_runtime_manifest_state
        ):
            try:
                with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                    final_row: Optional[dict[str, str]] = None
                    for final_row in csv.DictReader(handle):
                        pass
                if final_row is not None:
                    final_persisted_sample_seq = int(final_row["sample_seq"])
                    persisted_at = datetime.fromtimestamp(
                        csv_path.stat().st_mtime,
                        timezone.utc,
                    ).isoformat().replace("+00:00", "Z")
            except (KeyError, OSError, TypeError, ValueError):
                final_persisted_sample_seq = None
                persisted_at = None
        if final_persisted_sample_seq is None or persisted_at is None:
            self.logger.warning(
                "Refusing CSV v2 closeout without a file-specific persisted sample: %s",
                csv_path.name,
            )
            return None
        payload.pop("spot_observation_fact_closeout", None)
        payload["spot_observation_fact_manifest"] = observation_fact_manifest
        payload["csv_closeout"] = {
            "finalized": True,
            "closeout_reason": closeout_reason,
            "csv_file_name": csv_path.name,
            "logger_service_instance_id": self.logger_service_instance_id,
            "final_persisted_sample_seq": final_persisted_sample_seq,
            "persisted_at": persisted_at,
        }
        temp_path = metadata_path.with_name(f"{metadata_path.name}.tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp_path.replace(metadata_path)
        except OSError as exc:
            self.logger.warning("Failed to write refreshed CSV v2 observation fact manifest: %s", exc)
            return None
        return metadata_path

    def _suppress_spot_observation_fact_manifest_for_csv(
        self,
        csv_path: Path,
        *,
        writes_drained: bool = False,
        reason: str = "shutdown-write-drain-timeout",
    ) -> Optional[Path]:
        metadata_path = csv_path.with_suffix(".metadata.json")
        if not metadata_path.exists():
            return None
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning(
                "Failed to read CSV v2 sidecar for observation fact suppression: %s",
                exc,
            )
            return None
        payload.pop("spot_observation_fact_manifest", None)
        payload.pop("csv_closeout", None)
        payload["spot_observation_fact_closeout"] = {
            "finalized": False,
            "writes_drained": writes_drained,
            "reason": reason,
        }
        temp_path = metadata_path.with_name(f"{metadata_path.name}.tmp")
        try:
            temp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp_path.replace(metadata_path)
        except OSError as exc:
            self.logger.warning(
                "Failed to suppress unsafe CSV v2 observation fact manifest: %s",
                exc,
            )
            return None
        return metadata_path


    def _resolve_clean_git_commit(self) -> Optional[str]:
        return resolve_runtime_git_commit()

    def _write_v2_sidecar(self, csv_path: Path, contract: Optional[V2CsvContract] = None) -> None:
        if not self.csv_v2_sidecar_enabled:
            return
        active_contract = contract or self._get_active_v2_contract()
        sidecar_path = csv_path.with_suffix(".metadata.json")
        sidecar_key = str(sidecar_path)
        if sidecar_key in self._sidecar_paths_written or sidecar_path.exists():
            self._sidecar_paths_written.add(sidecar_key)
            return
        runtime_git_commit = self._resolve_clean_git_commit()
        payload = {
            "schema_metadata": {
                "schema_version": active_contract.schema_version,
                "active_schema_version": active_contract.schema_version,
                "active_column_hash": active_contract.column_hash,
                "csv_v2_operational_fields_enabled": active_contract.operational_fields_enabled,
                "csv_v2_temperature_hardening_enabled": active_contract.temperature_hardening_enabled,
                "temperature_operational_rule_version": TEMPERATURE_OPERATIONAL_RULE_VERSION,
                "temperature_quality_mapping_version": TEMPERATURE_QUALITY_MAPPING_VERSION,
                "spot_row_freshness_rule_version": SPOT_ROW_FRESHNESS_RULE_VERSION,
                "process_phase_rule_version": PROCESS_PHASE_RULE_VERSION,
                "posthoc_fact_manifests": [
                    "changeover_candidate_resolution_fact_manifest",
                    "process_phase_event_fact_manifest",
                ],
                "authoritative_fact_manifests": [
                    "spot_observation_fact_manifest",
                ],
                "promotion_bundle_required_flags": {
                    "CSV_V2_OPERATIONAL_FIELDS_ENABLED": True,
                    "SPOT_OBSERVATION_FACT_ENABLED": True,
                    "PROCESS_PHASE_EVENT_FACT_ENABLED": True,
                },
                "operator_metadata_version": OPERATOR_METADATA_VERSION,
                "logger_service_instance_id": self.logger_service_instance_id,
                "logger_service_started_at": self.logger_service_started_at,
                "git_commit": validate_git_commit(runtime_git_commit),
                "runtime_info": get_runtime_info(),
                "v1_compatibility": True,
                "v1_csv_enabled": self.csv_v1_enabled,
                "v1_columns": V1_CSV_COLUMNS,
                "v2_columns": list(active_contract.columns),
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
                "row_unique_key": ["logger_service_instance_id", "sample_seq"],
                "spot_observation_key_scope": (
                    "spot_service_instance_id and spot_poll_seq/spot_observation_seq are unique "
                    "only in spot_observation_fact, not realtime CSV rows."
                ),
                "spot_image_linkage_policy": {
                    "realtime_columns": [
                        "spot_image_capture_id_nearest",
                        "spot_image_path_nearest",
                        "spot_image_link_status_nearest",
                        "spot_image_link_age_ms_nearest",
                    ],
                    "realtime_semantics": "spot_image_*_nearest columns are best-effort live hints.",
                    "authoritative_linkage": (
                        "Authoritative linkage is post-hoc join via spot_image_fact.csv "
                        "and spot_observation_key."
                    ),
                    "authoritative_fact_file": "spot_image_fact.csv",
                    "authoritative_join_key": "spot_observation_key",
                    "realtime_csv_completeness": "best_effort_not_guaranteed",
                },
                "compatibility_statement": (
                    "Append-compatible for tolerant column-name consumers; strict backward "
                    "compatibility is not guaranteed for exact-column-count consumers."
                ),
            },
            "spot_temperature_shadow_metadata": self._spot_temperature_shadow_metadata(active_contract),
            "spot_configuration_snapshot": self._spot_configuration_snapshot(runtime_git_commit),
            "changeover_candidate_resolution_fact_manifest": (
                self._changeover_candidate_resolution_fact_manifest(sidecar_path.parent)
            ),
            "process_phase_event_fact_manifest": self._process_phase_event_fact_manifest(sidecar_path.parent),
            "sensor_metadata": [
                {
                    "column_name": "Product_No_operator",
                    "field_name": "product_no",
                    "physical_meaning": "Operator-entered numeric product number",
                    "source_system": "Operator input",
                    "device_id": "operator_console",
                    "plc_address": "",
                    "unit": "",
                    "mapping_status": "operator_entered_required",
                    "semantic_group": "operator_metadata",
                    "required": True,
                    "validation_rule": "1-40 digits only",
                    "not_replacement_for": "%DW PLC address",
                },
                {
                    "column_name": "Mold_No_operator",
                    "field_name": "operator_mold_no",
                    "physical_meaning": "Operator-entered mold number",
                    "source_system": "Operator input",
                    "device_id": "operator_console",
                    "plc_address": "",
                    "unit": "",
                    "mapping_status": "operator_entered_required",
                    "semantic_group": "operator_metadata",
                    "required": True,
                    "validation_rule": "1-32 digits only",
                    "not_replacement_for": "DIE_ID",
                    "note": "DIE_ID remains the derived cycle identifier from Count/Speed/state.",
                },
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
                    "operator_entered_required",
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
            "operator_metadata": {
                "version": OPERATOR_METADATA_VERSION,
                "source": "operator_input_api",
                "required_fields": ["product_no", "operator_mold_no"],
                "csv_columns": [
                    "Product_No_operator",
                    "Mold_No_operator",
                    "operator_metadata_valid",
                    "operator_metadata_missing_fields",
                    "operator_metadata_updated_at",
                ],
                "missing_policy": (
                    "The backend records invalid operator metadata state in v2 rows instead of "
                    "dropping PLC telemetry. UI should gate work start until required fields are valid."
                ),
            },
        }
        runtime_manifests = (
            (
                "spot_observation_fact_manifest",
                "spot_observation_fact_closeout",
                lambda: self._spot_observation_fact_manifest(sidecar_path.parent),
            ),
            (
                "spot_image_fact_manifest",
                "spot_image_fact_closeout",
                lambda: self._spot_image_fact_manifest(sidecar_path.parent),
            ),
        )
        for manifest_key, closeout_key, build_manifest in runtime_manifests:
            try:
                payload[manifest_key] = build_manifest()
            except Exception as exc:
                # A runtime fact writer can remain bound to the previous configured
                # directory while the CSV logger has already selected its durable
                # fallback or a newly configured LogPath. Preserve the realtime CSV
                # in that situation, but make the incomplete fact closeout explicit
                # and reject a clean shutdown until the manifests can be reconciled.
                self._runtime_write_failure_observed = True
                payload[closeout_key] = {
                    "finalized": False,
                    "writes_drained": False,
                    "reason": "runtime-manifest-unavailable-at-open",
                    "error_type": exc.__class__.__name__,
                }
                self.logger.warning(
                    "CSV v2 logging will continue without %s: %s",
                    manifest_key,
                    exc,
                )
        try:
            sidecar_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._sidecar_paths_written.add(sidecar_key)
        except Exception as exc:
            self.logger.warning("Failed to write CSV v2 sidecar metadata: %s", exc)

    def _build_row(self, data: FactoryData, timestamp: datetime) -> list:
        local_timestamp = self._to_local_timestamp(timestamp)
        date_s = local_timestamp.strftime("%Y-%m-%d")
        time_s = local_timestamp.strftime("%H:%M:%S.%f")[:-3]
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

    def _derive_process_phase_decision(
        self,
        data: FactoryData,
        timestamp: datetime,
        sample_seq: int,
    ) -> ProcessPhaseDecision:
        phase_input = self._process_phase_input_for_row(data, timestamp)
        if data.process_phase_candidate:
            process_phase_candidate = self._normalize_external_process_phase_candidate(
                data.process_phase_candidate,
            )
            decision = ProcessPhaseDecision(
                process_phase_candidate=process_phase_candidate,
                process_phase_rule_version=data.process_phase_rule_version or PROCESS_PHASE_RULE_VERSION,
                phase_confirmation_state=data.phase_confirmation_state or "realtime_candidate",
            )
        else:
            decision = derive_process_phase_candidate(phase_input)
        decision = self._assign_process_phase_ids(decision, sample_seq)
        self._commit_process_phase_operator_context(data, decision)
        return decision

    @staticmethod
    def _normalize_external_process_phase_candidate(process_phase_candidate: str) -> str:
        return _EXTERNALLY_SUPPLIED_WEAK_PHASES.get(process_phase_candidate, process_phase_candidate)

    def _process_phase_input_for_row(self, data: FactoryData, timestamp: datetime) -> ProcessPhaseInput:
        state = self._process_phase_runtime_state
        previous_product_no = state.committed_product_no
        previous_mold_no = state.committed_mold_no
        production_motion = self._has_process_phase_production_motion(data)
        count_held_sec, recent_production_motion = self._observe_process_phase_count(
            data,
            timestamp,
            production_motion,
        )
        return ProcessPhaseInput(
            speed=data.Speed,
            press=data.Press,
            count=data.Count,
            extruder_process_state_online=data.extruder_process_state_online,
            product_no=data.Product_No_operator,
            mold_no=data.Mold_No_operator,
            previous_product_no=previous_product_no,
            previous_mold_no=previous_mold_no,
            count_held_sec=count_held_sec,
            recent_production_motion=recent_production_motion,
        )

    def _observe_process_phase_count(
        self,
        data: FactoryData,
        timestamp: datetime,
        production_motion: bool,
    ) -> tuple[Optional[float], bool]:
        state = self._process_phase_runtime_state
        count = self._optional_int(data.Count)
        if count is None:
            state.count_value = None
            state.count_first_observed_at = None
            state.count_recent_production_motion = False
            return None, production_motion

        if state.count_value != count:
            state.count_value = count
            state.count_first_observed_at = timestamp
            state.count_recent_production_motion = production_motion
        else:
            if state.count_first_observed_at is None:
                state.count_first_observed_at = timestamp
            if production_motion:
                state.count_recent_production_motion = True

        return (
            self._elapsed_seconds(state.count_first_observed_at, timestamp),
            state.count_recent_production_motion,
        )

    def _commit_process_phase_operator_context(
        self,
        data: FactoryData,
        decision: ProcessPhaseDecision,
    ) -> None:
        if (
            decision.process_phase_candidate != "production_stable"
            and not self._has_process_phase_production_motion(data)
        ):
            return
        if data.operator_metadata_valid is False:
            return
        product_no = self._normalized_operator_text(data.Product_No_operator)
        mold_no = self._normalized_operator_text(data.Mold_No_operator)
        if not product_no or not mold_no:
            return
        self._process_phase_runtime_state.committed_product_no = product_no
        self._process_phase_runtime_state.committed_mold_no = mold_no

    def _assign_process_phase_ids(
        self,
        decision: ProcessPhaseDecision,
        sample_seq: int,
    ) -> ProcessPhaseDecision:
        phase = decision.process_phase_candidate or "unknown"
        process_segment_id = ""
        changeover_candidate_id = ""
        close_changeover_after_row = False
        state = self._process_phase_runtime_state

        if phase == "production_stabilizing" and state.active_changeover_candidate_id:
            changeover_candidate_id = state.active_changeover_candidate_id
            close_changeover_after_row = True
        elif phase == "production_stable" and state.active_changeover_candidate_id:
            if state.active_changeover_terminal_eligible:
                phase = "production_stabilizing"
                changeover_candidate_id = state.active_changeover_candidate_id
                close_changeover_after_row = True
            else:
                self._clear_active_changeover_candidate()
                process_segment_id = self._process_segment_id_for_phase(phase, sample_seq)
        elif phase in _CHANGEOVER_LIFECYCLE_PHASES:
            self._clear_active_process_segment()
            changeover_candidate_id = self._changeover_candidate_id_for_row(sample_seq)
            if phase in _CHANGEOVER_TERMINAL_EVIDENCE_PHASES:
                state.active_changeover_terminal_eligible = True
        else:
            process_segment_id = self._process_segment_id_for_phase(phase, sample_seq)

        assigned = ProcessPhaseDecision(
            process_phase_candidate=phase,
            process_phase_rule_version=decision.process_phase_rule_version,
            phase_confirmation_state=decision.phase_confirmation_state,
            process_segment_id=process_segment_id,
            changeover_candidate_id=changeover_candidate_id,
        )
        if close_changeover_after_row:
            self._clear_active_changeover_candidate()
        return assigned

    def _changeover_candidate_id_for_row(self, sample_seq: int) -> str:
        state = self._process_phase_runtime_state
        if not state.active_changeover_candidate_id:
            state.active_changeover_start_sample_seq = sample_seq
            state.active_changeover_terminal_eligible = False
            state.active_changeover_candidate_id = self._row_scoped_id(
                "chg",
                str(self.logger_service_instance_id),
                str(sample_seq),
            )
        return state.active_changeover_candidate_id

    def _clear_active_process_segment(self) -> None:
        state = self._process_phase_runtime_state
        state.process_segment_id = None
        state.process_segment_phase = None
        state.process_segment_start_sample_seq = None

    def _clear_active_changeover_candidate(self) -> None:
        state = self._process_phase_runtime_state
        state.active_changeover_candidate_id = None
        state.active_changeover_start_sample_seq = None
        state.active_changeover_terminal_eligible = False

    def _process_segment_id_for_phase(self, phase: str, sample_seq: int) -> str:
        segment_phase = phase if phase in _PROCESS_SEGMENT_PHASES else "unknown"
        state = self._process_phase_runtime_state
        if state.process_segment_id and state.process_segment_phase == segment_phase:
            return state.process_segment_id
        state.process_segment_phase = segment_phase
        state.process_segment_start_sample_seq = sample_seq
        state.process_segment_id = self._row_scoped_id(
            "seg",
            str(self.logger_service_instance_id),
            segment_phase,
            str(sample_seq),
        )
        return state.process_segment_id

    def _row_scoped_id(self, prefix: str, *parts: str) -> str:
        return prefix + "_" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]

    def _has_process_phase_production_motion(self, data: FactoryData) -> bool:
        online_state = (data.extruder_process_state_online or "").strip()
        speed = self._optional_float(data.Speed)
        return online_state == "extruding" or (
            speed is not None and speed > constants.CYCLE_SPEED_THRESHOLD
        )

    def _elapsed_seconds(self, start: Optional[datetime], end: datetime) -> Optional[float]:
        if start is None:
            return None
        try:
            return max(0.0, (end - start).total_seconds())
        except TypeError:
            start_naive = start.replace(tzinfo=None)
            end_naive = end.replace(tzinfo=None)
            return max(0.0, (end_naive - start_naive).total_seconds())

    def _normalized_operator_text(self, value: Optional[str]) -> str:
        return str(value or "").strip()

    def _optional_float(self, value: Optional[float]) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _optional_int(self, value: Optional[int]) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_alarmstatus(self, value: Optional[str]) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(str(value).strip(), 0)
        except (TypeError, ValueError):
            return None

    def _optional_bool(self, value: Optional[bool], default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}

    def _spot_row_freshness_threshold_ms(self) -> float:
        return float(getattr(config, "SPOT_REFRESH_INTERVAL", 3.0) or 3.0) * 3.0 * 1000.0

    def _timestamp_age_ms_at_row(self, row_timestamp: datetime, source_timestamp: Optional[str]) -> Optional[float]:
        source_dt = self._parse_utc_timestamp_text(source_timestamp)
        if source_dt is None:
            return None
        row_dt = row_timestamp
        if row_dt.tzinfo is None:
            row_dt = row_dt.replace(tzinfo=timezone.utc)
        age_ms = (row_dt.astimezone(timezone.utc) - source_dt.astimezone(timezone.utc)).total_seconds() * 1000.0
        return age_ms

    def _monotonic_age_ms_at_row(
        self,
        *,
        row_created_monotonic: Optional[float],
        source_completed_monotonic: Optional[float],
    ) -> Optional[float]:
        if row_created_monotonic is None or source_completed_monotonic is None:
            return None
        if isinstance(row_created_monotonic, bool) or isinstance(source_completed_monotonic, bool):
            return None
        try:
            row_clock = float(row_created_monotonic)
            source_clock = float(source_completed_monotonic)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(row_clock) or not math.isfinite(source_clock) or source_clock <= 0:
            return None
        return (row_clock - source_clock) * 1000.0

    def _parse_utc_timestamp_text(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _effective_age_ms_at_row(
        self,
        *,
        row_timestamp: datetime,
        row_created_monotonic: Optional[float],
        explicit_age_ms: Optional[float],
        source_completed_monotonic: Optional[float],
        source_timestamp: Optional[str],
        fallback_age_ms: Optional[float],
        row_freshness_threshold_ms: Optional[float] = None,
    ) -> Optional[float]:
        monotonic_age = self._monotonic_age_ms_at_row(
            row_created_monotonic=row_created_monotonic,
            source_completed_monotonic=source_completed_monotonic,
        )
        timestamp_age = self._timestamp_age_ms_at_row(row_timestamp, source_timestamp)
        if timestamp_age is not None and row_freshness_threshold_ms is not None:
            if timestamp_age < 0 or timestamp_age > row_freshness_threshold_ms:
                return timestamp_age
        if monotonic_age is not None:
            return monotonic_age
        if explicit_age_ms is not None:
            return explicit_age_ms
        if timestamp_age is not None:
            return timestamp_age
        return fallback_age_ms

    def _effective_value_age_ms_at_row(
        self,
        *,
        row_timestamp: datetime,
        row_created_monotonic: Optional[float],
        source_completed_monotonic: Optional[float],
        source_timestamp: Optional[str],
    ) -> tuple[Optional[float], str]:
        if source_completed_monotonic is not None:
            if (
                row_created_monotonic is None
                or isinstance(row_created_monotonic, bool)
                or isinstance(source_completed_monotonic, bool)
            ):
                return None, "clock_anomaly"
            try:
                row_clock = float(row_created_monotonic)
                source_clock = float(source_completed_monotonic)
            except (TypeError, ValueError):
                return None, "clock_anomaly"
            if not math.isfinite(row_clock) or not math.isfinite(source_clock):
                return None, "clock_anomaly"
            age_ms = (row_clock - source_clock) * 1000.0
            if not math.isfinite(age_ms) or age_ms < 0:
                return None, "clock_anomaly"
            return age_ms, "ok"

        timestamp_age = self._timestamp_age_ms_at_row(row_timestamp, source_timestamp)
        if timestamp_age is None:
            return None, "unknown"
        if not math.isfinite(timestamp_age) or timestamp_age < 0:
            return None, "clock_anomaly"
        return timestamp_age, "ok"

    def _derive_temperature_operational_decision(
        self,
        data: FactoryData,
        process_phase_candidate: str,
        row_timestamp: datetime,
        row_created_monotonic: Optional[float],
        temperature_hardening_enabled: bool,
    ):
        row_freshness_threshold_ms = self._spot_row_freshness_threshold_ms()
        if temperature_hardening_enabled:
            effective_value_age_ms, value_age_clock_status = self._effective_value_age_ms_at_row(
                row_timestamp=row_timestamp,
                row_created_monotonic=row_created_monotonic,
                source_completed_monotonic=data.spot_last_valid_value_monotonic,
                source_timestamp=data.spot_last_valid_value_at,
            )
        else:
            effective_value_age_ms = self._effective_age_ms_at_row(
                row_timestamp=row_timestamp,
                row_created_monotonic=None,
                explicit_age_ms=data.spot_effective_value_age_ms_at_row,
                source_completed_monotonic=None,
                source_timestamp=data.spot_last_valid_value_at,
                fallback_age_ms=data.spot_value_age_ms,
            )
            value_age_clock_status = "unknown"
        return derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status=data.spot_poll_status or "not_attempted",
                raw_validity=data.spot_raw_validity or "not_received",
                source_freshness=data.spot_source_freshness or "unknown",
                cache_fallback_allowed=bool(data.cache_fallback_allowed),
                has_ttl_valid_cache=data.spot_cache_status in {"fresh", "reused", "available_not_used"},
                has_previous_valid_value=bool(data.spot_last_valid_value_at),
                first_poll_completed=bool(data.spot_poll_status and data.spot_poll_status != "not_attempted"),
                temperature_value_origin=data.temperature_value_origin or "none",
                spot_device_status_code=data.spot_device_status_code,
                spot_error_code=data.spot_error_code,
                # Recompute row freshness at CSV write time. Snapshot-provided
                # row age can be stale by the time this row is emitted.
                spot_effective_age_ms_at_row=self._effective_age_ms_at_row(
                    row_timestamp=row_timestamp,
                    row_created_monotonic=row_created_monotonic,
                    explicit_age_ms=None,
                    source_completed_monotonic=data.spot_last_poll_completed_monotonic,
                    source_timestamp=data.spot_last_poll_completed_at,
                    fallback_age_ms=data.spot_snapshot_age_ms,
                    row_freshness_threshold_ms=row_freshness_threshold_ms,
                ),
                spot_effective_value_age_ms_at_row=effective_value_age_ms,
                spot_value_age_clock_status=value_age_clock_status,
                spot_row_freshness_threshold_ms=row_freshness_threshold_ms,
                process_phase_candidate=process_phase_candidate,
                evidence_codes=parse_spot_diagnostic_evidence_codes(data.spot_diagnostic_evidence_codes),
                alarmstatus=self._optional_alarmstatus(data.alarmstatus),
                signalpc=self._optional_float(data.signalpc),
                low_signal_alarm_enabled=self._optional_bool(
                    data.low_signal_alarm_enabled,
                    bool(getattr(config, "SPOT_LOW_SIGNAL_ALARM_ENABLED", False)),
                ),
                low_signal_threshold_pc=self._optional_float(data.low_signal_threshold_pc)
                if data.low_signal_threshold_pc is not None
                else self._optional_float(getattr(config, "SPOT_LOW_SIGNAL_THRESHOLD_PC", None)),
                low_signal_comparator=str(
                    data.low_signal_comparator
                    if data.low_signal_comparator is not None
                    else getattr(config, "SPOT_LOW_SIGNAL_COMPARATOR", "")
                ),
                low_signal_comparator_verified=self._optional_bool(
                    data.low_signal_comparator_verified,
                    False,
                ),
                diagnostics_current_poll_seq=self._optional_int(data.spot_poll_seq),
                diagnostics_current_service_instance_id=data.spot_service_instance_id,
                diagnostics_snapshot_id=data.diagnostics_snapshot_id,
                diagnostics_source_poll_seq=self._optional_int(data.diagnostics_source_poll_seq),
                diagnostics_capture_status=data.diagnostics_capture_status or "missing",
                diagnostics_collection_mode=data.diagnostics_collection_mode or "async_fact_only",
                diagnostics_binding_status=data.diagnostics_binding_status or "missing",
                diagnostics_age_ms=self._optional_float(data.diagnostics_age_ms),
                diagnostics_max_age_ms=configured_diagnostics_max_age_ms(
                    getattr(config, "SPOT_REFRESH_INTERVAL", 1.0)
                ),
                diagnostics_missing_fields=parse_diagnostics_missing_fields(data.diagnostics_missing_fields),
                diagnostics_field_status=parse_diagnostics_field_status(data.diagnostics_field_status),
                peak_picker_enabled=self._optional_bool(
                    data.peak_picker_enabled,
                    bool(getattr(config, "SPOT_PEAK_PICKER_ENABLED", False)),
                ),
                peak_picker_off_mode=data.peak_picker_off_mode,
            )
        )

    def _spot_observation_key_for_data(self, data: FactoryData) -> str:
        built_key = build_spot_observation_key(
            {
                "spot_service_instance_id": data.spot_service_instance_id,
                "spot_poll_seq": data.spot_poll_seq,
                "spot_last_poll_completed_at": data.spot_last_poll_completed_at,
                "spot_poll_status": data.spot_poll_status,
                "temperature_output_status": data.temperature_output_status,
                "temperature_status_shadow": data.temperature_status_shadow,
            }
        )
        if not built_key:
            return ""
        return built_key

    def _spot_image_link_for_row(self, data: FactoryData, spot_observation_key: str) -> dict[str, str]:
        explicit = {
            "spot_image_capture_id_nearest": self._escape_csv_text(data.spot_image_capture_id_nearest or ""),
            "spot_image_path_nearest": self._escape_csv_text(data.spot_image_path_nearest or ""),
            "spot_image_link_status_nearest": self._escape_csv_text(data.spot_image_link_status_nearest or ""),
            "spot_image_link_age_ms_nearest": self._fmt(data.spot_image_link_age_ms_nearest),
        }
        if any(explicit.values()):
            return explicit
        if not spot_observation_key:
            return {
                "spot_image_capture_id_nearest": "",
                "spot_image_path_nearest": "",
                "spot_image_link_status_nearest": "",
                "spot_image_link_age_ms_nearest": "",
            }
        try:
            from backend.FacilityData.drivers import spot_api

            fact = spot_api.get_latest_spot_image_capture_fact()
        except Exception:
            fact = {}
        if fact.get("spot_image_linked_observation_key") != spot_observation_key:
            return {
                "spot_image_capture_id_nearest": "",
                "spot_image_path_nearest": "",
                "spot_image_link_status_nearest": "",
                "spot_image_link_age_ms_nearest": "",
            }
        return {
            "spot_image_capture_id_nearest": self._escape_csv_text(fact.get("spot_image_capture_id", "")),
            "spot_image_path_nearest": self._escape_csv_text(fact.get("spot_image_path", "")),
            "spot_image_link_status_nearest": self._escape_csv_text(fact.get("spot_image_link_status", "")),
            "spot_image_link_age_ms_nearest": self._escape_csv_text(fact.get("spot_image_link_age_ms", "")),
        }

    def _record_v2_4_operational_counters(
        self,
        *,
        operational_decision: TemperatureOperationalDecision,
        process_phase_decision: ProcessPhaseDecision,
        data: FactoryData,
        sample_seq: int,
        spot_observation_key: str,
    ) -> None:
        output_status = str(operational_decision.temperature_output_status or "unknown")
        unavailable_reason = str(operational_decision.temperature_unavailable_reason or "").strip()
        device_status = str(data.spot_device_status_code or "").strip()
        process_phase = str(process_phase_decision.process_phase_candidate or "unknown")
        row_freshness = str(operational_decision.spot_effective_freshness_at_row or "unknown")
        fact_link_expected = bool(getattr(config, "SPOT_OBSERVATION_FACT_ENABLED", False)) and bool(
            build_spot_observation_key(
                {
                    "spot_service_instance_id": data.spot_service_instance_id or "__missing_service_id__",
                    "spot_poll_seq": data.spot_poll_seq,
                    "spot_last_poll_completed_at": data.spot_last_poll_completed_at,
                    "spot_poll_status": data.spot_poll_status,
                    "temperature_output_status": data.temperature_output_status,
                    "temperature_status_shadow": data.temperature_status_shadow,
                }
            )
        )
        updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with self._v2_4_operational_lock:
            self._v2_4_operational_rows_total += 1
            self._v2_4_temperature_output_status_counts[output_status] += 1
            if unavailable_reason:
                self._v2_4_temperature_unavailable_reason_counts[unavailable_reason] += 1
            if device_status:
                self._v2_4_sentinel_device_status_counts[device_status] += 1
            self._v2_4_process_phase_candidate_counts[process_phase] += 1
            if output_status == "stale" or row_freshness == "stale":
                self._v2_4_stale_threshold_breach_count += 1
            if fact_link_expected and not spot_observation_key:
                self._v2_4_observation_fact_link_failure_count += 1
            if operational_decision.cached_fallback_accepted:
                self._v2_4_cached_fallback_accepted_count += 1
            if operational_decision.cached_fallback_rejected_reason:
                self._v2_4_cached_fallback_rejected_count += 1
                self._v2_4_cached_fallback_rejected_reason_counts[
                    operational_decision.cached_fallback_rejected_reason
                ] += 1
            if operational_decision.origin_decision_mismatch:
                self._v2_4_origin_decision_mismatch_count += 1
            if "signalpc_present_comparator_unverified" in parse_spot_diagnostic_evidence_codes(
                operational_decision.temperature_cause_evidence_codes
            ):
                self._v2_4_comparator_unverified_count += 1
            capture_status = str(data.diagnostics_capture_status or "missing")
            if capture_status not in DIAGNOSTICS_CAPTURE_STATUSES:
                capture_status = "error"
            binding_status = str(data.diagnostics_binding_status or "missing")
            if binding_status not in DIAGNOSTICS_BINDING_STATUSES:
                binding_status = "unbound"
            self._v2_4_diagnostics_capture_status_counts[capture_status] += 1
            self._v2_4_diagnostics_binding_status_counts[binding_status] += 1
            if operational_decision.diagnostics_cause_suppressed:
                self._v2_4_diagnostics_cause_suppressed_count += 1
                suppression_reason = operational_decision.diagnostics_cause_suppressed_reason
                if suppression_reason in DIAGNOSTICS_SUPPRESSION_REASONS:
                    self._v2_4_diagnostics_cause_suppressed_reason_counts[suppression_reason] += 1
            if operational_decision.unsupported_evidence_suppressed:
                self._v2_4_unsupported_evidence_suppressed_count += 1
            if operational_decision.spot_value_age_clock_status == "clock_anomaly":
                self._v2_4_value_age_clock_anomaly_count += 1
            self._v2_4_last_sample_seq = sample_seq
            self._v2_4_last_updated_at = updated_at

    def get_v2_4_operational_summary(self) -> dict[str, Any]:
        with self._config_lock:
            operational_fields_enabled = self.csv_v2_operational_fields_enabled
            temperature_hardening_enabled = self.csv_v2_temperature_hardening_enabled
            csv_v2_enabled = self.csv_v2_enabled
        with self._v2_4_operational_lock:
            return {
                "enabled": bool(csv_v2_enabled and operational_fields_enabled),
                "schema_version": (
                    CSV_SCHEMA_VERSION_V2_5
                    if temperature_hardening_enabled
                    else CSV_SCHEMA_VERSION_V2_4
                ),
                "logger_service_instance_id": self.logger_service_instance_id,
                "logger_service_started_at": self.logger_service_started_at,
                "current_v2_csv_file_name": (
                    self._current_v2_csv_path.name
                    if self._current_v2_csv_path is not None
                    else None
                ),
                "temperature_hardening_enabled": temperature_hardening_enabled,
                "rows_total": self._v2_4_operational_rows_total,
                "rows_by_temperature_output_status": dict(self._v2_4_temperature_output_status_counts),
                "rows_by_temperature_unavailable_reason": dict(
                    self._v2_4_temperature_unavailable_reason_counts
                ),
                "sentinel_counts_by_spot_device_status_code": dict(
                    self._v2_4_sentinel_device_status_counts
                ),
                "stale_threshold_breach_count": self._v2_4_stale_threshold_breach_count,
                "observation_fact_link_failure_count": self._v2_4_observation_fact_link_failure_count,
                "cached_fallback_accepted_count": self._v2_4_cached_fallback_accepted_count,
                "cached_fallback_rejected_count": self._v2_4_cached_fallback_rejected_count,
                "cached_fallback_rejected_reason_counts": dict(
                    self._v2_4_cached_fallback_rejected_reason_counts
                ),
                "origin_decision_mismatch_count": self._v2_4_origin_decision_mismatch_count,
                "comparator_unverified_count": self._v2_4_comparator_unverified_count,
                "diagnostics_capture_status_counts": dict(
                    self._v2_4_diagnostics_capture_status_counts
                ),
                "diagnostics_binding_status_counts": dict(
                    self._v2_4_diagnostics_binding_status_counts
                ),
                "diagnostics_cause_suppressed_count": self._v2_4_diagnostics_cause_suppressed_count,
                "diagnostics_cause_suppressed_reason_counts": dict(
                    self._v2_4_diagnostics_cause_suppressed_reason_counts
                ),
                "unsupported_evidence_suppressed_count": (
                    self._v2_4_unsupported_evidence_suppressed_count
                ),
                "value_age_clock_anomaly_count": self._v2_4_value_age_clock_anomaly_count,
                "process_phase_candidate_counts": dict(self._v2_4_process_phase_candidate_counts),
                "last_sample_seq": self._v2_4_last_sample_seq,
                "last_updated_at": self._v2_4_last_updated_at,
            }

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
        contract = self._get_active_v2_contract()
        mainpress_quality, mainpress_reason = self._quality_for_mainpress(data)
        temperature_quality, temperature_reason = self._quality_for_temperature(data)
        speed_quality, speed_reason = self._quality_for_speed(data)
        billet_quality, billet_reason = self._quality_for_billet_length(data)
        cycle_state = self._cycle_state(data)
        cycle_confidence = self._cycle_confidence(data, cycle_state)
        spot_temperature_raw, spot_temperature_raw_truncated = self._bounded_csv_text(
            data.spot_temperature_raw,
            SPOT_TEMPERATURE_RAW_MAX_LENGTH,
        )
        process_phase_decision = self._derive_process_phase_decision(data, timestamp, sample_seq)
        row_created_monotonic = time.monotonic()
        operational_decision = self._derive_temperature_operational_decision(
            data,
            process_phase_decision.process_phase_candidate,
            utc_timestamp,
            row_created_monotonic,
            contract.temperature_hardening_enabled,
        )
        if contract.temperature_hardening_enabled:
            temperature_quality, temperature_reason = self._quality_for_temperature_operational_status(
                operational_decision.temperature_output_status
            )
        v1_values = list(v1_row)
        temperature_value_origin = data.temperature_value_origin or ""
        if contract.operational_fields_enabled:
            temperature_value_origin = operational_decision.temperature_value_origin
            if operational_decision.temperature_output_status != "valid":
                v1_values[V1_CSV_COLUMNS.index("Temperature")] = ""
        base_row = [
            contract.schema_version,
            sample_seq,
            local_timestamp.isoformat(),
            utc_timestamp.isoformat().replace("+00:00", "Z"),
            ingest_timestamp.isoformat(),
            self._epoch_to_iso(data.captured_at_extruder),
            self._epoch_to_iso(data.captured_at_ls),
            self._epoch_to_iso(data.captured_at_spot),
            self._escape_csv_text(data.Product_No_operator or ""),
            self._escape_csv_text(data.Mold_No_operator or ""),
            self._fmt_bool(bool(data.operator_metadata_valid)),
            self._escape_csv_text(",".join(data.operator_metadata_missing_fields or [])),
            self._escape_csv_text(data.operator_metadata_updated_at or ""),
            *v1_values,
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
            self._escape_csv_text(self.logger_service_instance_id),
            self._escape_csv_text(self.logger_service_started_at),
            self._escape_csv_text(data.extruder_process_state_online or "unknown"),
            self._escape_csv_text(data.process_state_online_rule_version or PROCESS_STATE_ONLINE_RULE_VERSION),
            self._escape_csv_text(data.spot_target_state_observed_shadow or ""),
            self._escape_csv_text(data.spot_target_state_observed_source or ""),
            self._escape_csv_text(data.label_validation_state or "shadow"),
            self._escape_csv_text(data.temperature_status_shadow or ""),
            self._escape_csv_text(data.temperature_status_rule_version or TEMPERATURE_STATUS_RULE_VERSION),
            self._escape_csv_text(data.spot_poll_status or ""),
            self._escape_csv_text(data.spot_raw_validity or ""),
            self._escape_csv_text(data.spot_cache_status or ""),
            self._escape_csv_text(data.spot_source_freshness or ""),
            self._escape_csv_text(temperature_value_origin),
            self._fmt_optional_bool(data.cache_fallback_allowed, default=False),
            self._escape_csv_text(data.spot_service_instance_id or ""),
            self._escape_csv_text(data.spot_service_started_at or ""),
            self._fmt_int(data.spot_poll_seq),
            self._fmt_int(data.spot_observation_seq),
            self._fmt(data.spot_temperature_observed_c),
            spot_temperature_raw,
            self._fmt_bool(bool(data.spot_temperature_raw_truncated or spot_temperature_raw_truncated)),
            self._escape_csv_text(data.spot_raw_payload_hash or ""),
            self._escape_csv_text(data.spot_raw_payload_encoding or ""),
            self._fmt_int(data.spot_http_status_code),
            self._escape_csv_text(data.spot_device_status_code or ""),
            self._escape_csv_text(data.spot_error_code or ""),
            self._fmt(data.spot_poll_duration_ms),
            self._fmt_int(data.spot_response_content_length),
            self._escape_csv_text(data.spot_last_poll_started_at or ""),
            self._escape_csv_text(data.spot_last_poll_completed_at or ""),
            self._escape_csv_text(data.spot_last_response_at or ""),
            self._escape_csv_text(data.spot_last_valid_value_at or ""),
            self._fmt(data.spot_snapshot_age_ms),
            self._fmt(data.spot_value_age_ms),
        ]
        if not contract.operational_fields_enabled:
            return base_row
        spot_observation_key = self._spot_observation_key_for_data(data)
        spot_image_link = self._spot_image_link_for_row(data, spot_observation_key)
        self._record_v2_4_operational_counters(
            operational_decision=operational_decision,
            process_phase_decision=process_phase_decision,
            data=data,
            sample_seq=sample_seq,
            spot_observation_key=spot_observation_key,
        )
        operational_row = [
            *base_row,
            self._escape_csv_text(operational_decision.temperature_output_status),
            self._escape_csv_text(operational_decision.temperature_unavailable_reason),
            self._escape_csv_text(operational_decision.temperature_expectedness_candidate),
            self._escape_csv_text(operational_decision.temperature_under_range_cause_candidate),
            self._fmt(operational_decision.temperature_cause_confidence),
            self._escape_csv_text(operational_decision.temperature_cause_evidence_codes),
            self._fmt(operational_decision.spot_effective_age_ms_at_row),
            self._escape_csv_text(operational_decision.spot_effective_freshness_at_row),
            self._fmt(operational_decision.spot_effective_value_age_ms_at_row),
            self._escape_csv_text(operational_decision.spot_row_age_clock_status),
            self._escape_csv_text(process_phase_decision.process_phase_candidate),
            self._escape_csv_text(process_phase_decision.process_phase_rule_version),
            self._escape_csv_text(process_phase_decision.phase_confirmation_state),
            self._escape_csv_text(process_phase_decision.process_segment_id),
            self._escape_csv_text(process_phase_decision.changeover_candidate_id),
            self._escape_csv_text(spot_observation_key),
            spot_image_link["spot_image_capture_id_nearest"],
            spot_image_link["spot_image_path_nearest"],
            spot_image_link["spot_image_link_status_nearest"],
            spot_image_link["spot_image_link_age_ms_nearest"],
        ]
        if contract.temperature_hardening_enabled:
            operational_row.append(
                self._escape_csv_text(operational_decision.spot_value_age_clock_status)
            )
        return operational_row

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

    def _fmt_optional_bool(self, value: Optional[bool], *, default: Optional[bool] = None) -> str:
        if value is None:
            if default is None:
                return ""
            return self._fmt_bool(default)
        return self._fmt_bool(bool(value))

    def _fmt_int(self, value: Optional[int]) -> str:
        if value is None or isinstance(value, bool):
            return ""
        try:
            return str(int(value))
        except Exception:
            return ""

    def _bounded_csv_text(self, value: Optional[str], max_length: int) -> tuple[str, bool]:
        if value is None:
            return "", False
        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        truncated = len(text) > max_length
        if truncated:
            text = text[:max_length]
        return self._escape_csv_text(text), truncated

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

    def _quality_for_temperature_operational_status(self, output_status: str) -> tuple[str, str]:
        return {
            "valid": ("ok", "not_missing"),
            "under_range": ("invalid", "invalid_value"),
            "over_range": ("invalid", "invalid_value"),
            "stale": ("stale", "stale_snapshot"),
            "source_error": ("missing", "source_error"),
            "startup_pending": ("missing", "source_missing"),
            "unknown": ("unknown", "source_missing"),
        }.get(str(output_status or "unknown"), ("unknown", "source_missing"))

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

    def _log_file_date(self, timestamp: datetime) -> date:
        return self._to_local_timestamp(timestamp).date()

    def _filename_timestamp(self, timestamp: datetime) -> str:
        return self._to_local_timestamp(timestamp).strftime("%Y%m%d_%H%M%S")

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
        self._mark_write_completed()
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
        persistence = self._prepare_v2_rows_persisted(rows)
        writer.writerows([row for row, _ in rows])
        handle.flush()
        self._commit_v2_rows_persisted(persistence)
        self._mark_write_completed()
        return True

    def _prepare_v2_rows_persisted(
        self,
        rows: list[Tuple[list, datetime]],
    ) -> tuple[str, int, str]:
        csv_path = self._current_v2_csv_path
        if csv_path is None:
            raise RuntimeError("CSV v2 persisted rows have no active file identity.")
        sample_seq_index = self._get_active_v2_contract().columns.index("sample_seq")
        try:
            persisted_sample_seqs = [
                int(row[sample_seq_index])
                for row, _ in rows
            ]
        except (IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("CSV v2 persisted rows have an invalid sample_seq.") from exc
        if any(
            current <= previous
            for previous, current in zip(
                persisted_sample_seqs,
                persisted_sample_seqs[1:],
            )
        ):
            raise RuntimeError(
                "CSV v2 persisted sample_seq is not strictly increasing."
            )
        persisted_sample_seq = persisted_sample_seqs[-1]
        csv_path_key = str(csv_path)
        persisted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._runtime_lock:
            previous_sample_seq = self._v2_persisted_sample_seq_by_path.get(csv_path_key)
            if (
                previous_sample_seq is not None
                and persisted_sample_seqs[0] <= previous_sample_seq
            ):
                raise RuntimeError(
                    "CSV v2 persisted sample_seq did not advance for the active file."
                )
        return csv_path_key, persisted_sample_seq, persisted_at

    def _commit_v2_rows_persisted(
        self,
        persistence: tuple[str, int, str],
    ) -> None:
        csv_path_key, persisted_sample_seq, persisted_at = persistence
        with self._runtime_lock:
            self._v2_persisted_sample_seq_by_path[csv_path_key] = (
                persisted_sample_seq
            )
            self._v2_persisted_at_by_path[csv_path_key] = persisted_at

    def _mark_write_completed(self) -> None:
        with self._runtime_lock:
            self._last_write_at = time.time()

    def _close_file(self, handle: Optional[object]) -> None:
        if handle is None:
            return
        try:
            handle.close()
        except Exception as exc:
            self.logger.warning("Failed to close CSV log file handle: %s", exc)

    def _close_v2_file(
        self,
        handle: Optional[object],
        *,
        closeout_reason: str = "runtime-close",
        finalize_closeout: bool = True,
    ) -> bool:
        csv_path = self._current_v2_csv_path
        closeout_succeeded = True
        if handle is not None:
            try:
                handle.flush()
            except Exception as exc:
                closeout_succeeded = False
                self.logger.warning("Failed to flush CSV v2 log file before close: %s", exc)
        if csv_path is not None and self.csv_v2_sidecar_enabled:
            if (
                closeout_succeeded
                and finalize_closeout
                and self._finalize_spot_observation_manifest_on_stop
            ):
                refreshed_path = self.refresh_spot_observation_fact_manifest_for_csv(
                    csv_path,
                    closeout_reason=closeout_reason,
                )
                if refreshed_path is None:
                    closeout_succeeded = False
                    suppressed_path = self._suppress_spot_observation_fact_manifest_for_csv(
                        csv_path,
                        writes_drained=True,
                        reason="manifest-refresh-failed",
                    )
                    if suppressed_path is None:
                        self.logger.warning(
                            "Failed to invalidate stale SPOT observation fact manifest."
                        )
                    else:
                        self.logger.warning(
                            "Invalidated stale SPOT observation fact manifest after refresh failure."
                        )
            else:
                suppression_reason = (
                    "close-flush-failed"
                    if not closeout_succeeded
                    else (
                        "closeout-not-finalized"
                        if not finalize_closeout
                        else "shutdown-write-drain-timeout"
                    )
                )
                suppressed_path = self._suppress_spot_observation_fact_manifest_for_csv(
                    csv_path,
                    writes_drained=closeout_succeeded,
                    reason=suppression_reason,
                )
                if suppressed_path is None:
                    closeout_succeeded = False
                self.logger.warning(
                    "Skipped SPOT observation fact manifest because writes did not drain."
                )
        self._close_file(handle)
        if csv_path is not None:
            csv_path_key = str(csv_path)
            with self._runtime_lock:
                self._v2_persisted_sample_seq_by_path.pop(csv_path_key, None)
                self._v2_persisted_at_by_path.pop(csv_path_key, None)
        self._current_v2_csv_path = None
        if not closeout_succeeded:
            self._runtime_write_failure_observed = True
        return closeout_succeeded

    def get_runtime_state(self) -> dict[str, Any]:
        with self._config_lock:
            auto_save = self.auto_save
            csv_v1_enabled = self.csv_v1_enabled
            log_path = str(self.active_log_dir)
            csv_v2_enabled = self.csv_v2_enabled
            csv_v2_operational_fields_enabled = self.csv_v2_operational_fields_enabled
            csv_v2_temperature_hardening_enabled = self.csv_v2_temperature_hardening_enabled
        queue_size = self.queue.qsize()
        queue_maxsize = self.queue.maxsize
        with self._runtime_lock:
            drop_count = self._drop_count
            last_drop_at = self._last_drop_at
            last_enqueue_at = self._last_enqueue_at
            last_write_at = self._last_write_at
            payload_bytes_ema = self._payload_bytes_ema
        now = time.time()
        queue_ratio = queue_size / queue_maxsize if queue_maxsize > 0 else 0.0
        writer_lag_sec = (now - last_write_at) if last_write_at is not None else None
        estimated_queue_bytes = int(queue_size * payload_bytes_ema) if payload_bytes_ema is not None else 0
        return {
            "queue_size": queue_size,
            "queue_maxsize": queue_maxsize,
            "queue_ratio": queue_ratio,
            "drop_count": drop_count,
            "last_drop_at": last_drop_at,
            "last_enqueue_at": last_enqueue_at,
            "last_write_at": last_write_at,
            "writer_lag_sec": writer_lag_sec,
            "payload_bytes_ema": payload_bytes_ema,
            "estimated_queue_bytes": estimated_queue_bytes,
            "buffer_size": self._buffer_size,
            "last_batch_size": self._last_batch_size,
            "running": self.running,
            "auto_save": auto_save,
            "csv_v1_enabled": csv_v1_enabled,
            "csv_v2_enabled": csv_v2_enabled,
            "csv_v2_operational_fields_enabled": csv_v2_operational_fields_enabled,
            "csv_v2_temperature_hardening_enabled": csv_v2_temperature_hardening_enabled,
            "log_path": log_path,
            "v2_4_operational": self.get_v2_4_operational_summary(),
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
        current_file_date: Optional[date] = None
        deferred_item: Optional[FactoryData] = None

        while True:
            try:
                item: Optional[FactoryData] = None
                with self._config_lock:
                    auto_save = self.auto_save
                    csv_v1_enabled = self.csv_v1_enabled
                    csv_v2_enabled = self.csv_v2_enabled
                    config_version = self._config_version

                if config_version != current_config_version:
                    current_config_version = config_version
                    if buffer:
                        if auto_save and (f_handle is None or writer is None):
                            f_handle, writer = self._open_v1_log_file_for_drain(
                                self._filename_timestamp(buffer[0][1]),
                                prefix=file_prefix,
                            )
                        if auto_save and self._flush_buffer(writer, f_handle, buffer):
                            buffer.clear()
                            self._buffer_size = 0
                        elif not auto_save:
                            buffer.clear()
                            self._buffer_size = 0
                        else:
                            self.logger.warning("CSV v1 buffer retained during config change.")
                    if v2_buffer:
                        if auto_save and csv_v2_enabled and (v2_handle is None or v2_writer is None):
                            v2_handle, v2_writer = self._open_v2_log_file(
                                self._filename_timestamp(v2_buffer[0][1]),
                                prefix=v2_file_prefix,
                            )
                        if csv_v2_enabled and self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                            v2_buffer.clear()
                        else:
                            self._runtime_write_failure_observed = True
                            self.logger.warning(
                                "CSV v2 buffer dropped during config change; clean shutdown will be rejected."
                            )
                            v2_buffer.clear()
                    self._close_file(f_handle)
                    self._close_v2_file(
                        v2_handle,
                        closeout_reason="config-change",
                    )
                    f_handle = None
                    writer = None
                    v2_handle = None
                    v2_writer = None
                    current_file_date = None

                if deferred_item is not None:
                    item = deferred_item
                    deferred_item = None
                else:
                    try:
                        item = self.queue.get(timeout=0.2)
                    except queue.Empty:
                        item = None

                if item is None:
                    if not self.running:
                        break
                else:
                    timestamp = self._parse_timestamp(item)
                    if not auto_save:
                        continue

                    item_file_date = self._log_file_date(timestamp)
                    if current_file_date is not None and item_file_date != current_file_date:
                        rollover_ready = True
                        if buffer:
                            if f_handle is None or writer is None:
                                f_handle, writer = self._open_v1_log_file_for_drain(
                                    self._filename_timestamp(buffer[0][1]),
                                    prefix=file_prefix,
                                )
                            if self._flush_buffer(writer, f_handle, buffer):
                                buffer.clear()
                                self._buffer_size = 0
                            else:
                                rollover_ready = False
                                self.logger.warning(
                                    "CSV v1 daily rollover delayed because pending rows could not be flushed."
                                )
                        if v2_buffer:
                            if csv_v2_enabled and (v2_handle is None or v2_writer is None):
                                v2_handle, v2_writer = self._open_v2_log_file(
                                    self._filename_timestamp(v2_buffer[0][1]),
                                    prefix=v2_file_prefix,
                                )
                            if csv_v2_enabled and self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                                v2_buffer.clear()
                            else:
                                rollover_ready = False
                                self.logger.warning(
                                    "CSV v2 daily rollover delayed because pending rows could not be flushed."
                                )
                        if rollover_ready:
                            self._close_file(f_handle)
                            self._close_v2_file(
                                v2_handle,
                                closeout_reason="daily-rollover",
                            )
                            f_handle = None
                            writer = None
                            v2_handle = None
                            v2_writer = None
                            self.logger.info(
                                "CSV daily rollover completed: %s -> %s",
                                current_file_date.isoformat(),
                                item_file_date.isoformat(),
                            )
                            current_file_date = None
                        else:
                            if not self.running:
                                deferred_item = item
                                self._buffer_size = len(buffer)
                                break
                            deferred_item = item
                            self._buffer_size = len(buffer)
                            time.sleep(0.2)
                            continue

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

                    if csv_v1_enabled and (f_handle is None or writer is None):
                        f_handle, writer = self._open_log_file(
                            self._filename_timestamp(timestamp),
                            prefix=file_prefix,
                        )
                    if csv_v2_enabled and (v2_handle is None or v2_writer is None):
                        v2_handle, v2_writer = self._open_v2_log_file(
                            self._filename_timestamp(timestamp),
                            prefix=v2_file_prefix,
                        )
                    if current_file_date is None:
                        current_file_date = item_file_date

                    if csv_v1_enabled:
                        buffer.append((row, timestamp))
                    if v2_row is not None:
                        v2_buffer.append((v2_row, timestamp))
                    self._buffer_size = len(buffer)

                now = time.time()
                pending_rows = len(buffer) + len(v2_buffer)
                if pending_rows and (pending_rows >= batch_size or (now - last_flush_time) > flush_interval):
                    if buffer and auto_save and (not f_handle or not writer):
                        ts = self._filename_timestamp(buffer[0][1])
                        f_handle, writer = self._open_v1_log_file_for_drain(ts, prefix=file_prefix)

                    if buffer and auto_save and self._flush_buffer(writer, f_handle, buffer):
                        buffer.clear()
                        self._buffer_size = 0
                    elif not auto_save:
                        buffer.clear()
                        self._buffer_size = 0
                    elif buffer:
                        self.logger.warning("CSV v1 buffer retained because v1 writer is unavailable.")
                    if v2_buffer:
                        if auto_save and csv_v2_enabled and (not v2_handle or not v2_writer):
                            ts = self._filename_timestamp(v2_buffer[0][1])
                            v2_handle, v2_writer = self._open_v2_log_file(ts, prefix=v2_file_prefix)
                        if auto_save and csv_v2_enabled and self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                            v2_buffer.clear()
                        elif auto_save and csv_v2_enabled:
                            self.logger.warning("CSV v2 buffer retained because v2 writer is unavailable.")
                        else:
                            self._runtime_write_failure_observed = True
                            self.logger.warning(
                                "CSV v2 buffer dropped after persistence was disabled; clean shutdown will be rejected."
                            )
                            v2_buffer.clear()
                    last_flush_time = now
            except Exception as exc:
                self.logger.error("Error in CSV logger loop: %s", exc)
                if item is not None and current_file_date is not None:
                    try:
                        item_file_date = self._log_file_date(self._parse_timestamp(item))
                    except Exception:
                        item_file_date = current_file_date
                    if item_file_date != current_file_date and deferred_item is None:
                        deferred_item = item
                        self.logger.warning(
                            "CSV daily rollover delayed because flush raised an exception. "
                            "Current row deferred to preserve daily file boundary."
                        )
                self._close_file(f_handle)
                self._close_v2_file(
                    v2_handle,
                    closeout_reason="runtime-error",
                )
                f_handle, writer = None, None
                v2_handle, v2_writer = None, None
                self._buffer_size = len(buffer)
                if buffer:
                    current_file_date = self._log_file_date(buffer[0][1])
                elif v2_buffer:
                    current_file_date = self._log_file_date(v2_buffer[0][1])
                else:
                    current_file_date = None
                time.sleep(0.5)

        shutdown_flush_succeeded = not self._runtime_write_failure_observed
        if buffer:
            try:
                if self.auto_save and (f_handle is None or writer is None):
                    f_handle, writer = self._open_v1_log_file_for_drain(
                        self._filename_timestamp(buffer[0][1]),
                        prefix=file_prefix,
                    )
                if self._flush_buffer(writer, f_handle, buffer):
                    buffer.clear()
                else:
                    shutdown_flush_succeeded = False
                    self.logger.warning("CSV v1 final flush failed because writer is unavailable.")
            except Exception as exc:
                shutdown_flush_succeeded = False
                self.logger.warning("CSV v1 final flush failed: %s", exc)
        if v2_buffer:
            try:
                if self.csv_v2_enabled and (v2_handle is None or v2_writer is None):
                    v2_handle, v2_writer = self._open_v2_log_file(
                        self._filename_timestamp(v2_buffer[0][1]),
                        prefix=v2_file_prefix,
                    )
                if self._flush_v2_buffer(v2_writer, v2_handle, v2_buffer):
                    v2_buffer.clear()
                else:
                    shutdown_flush_succeeded = False
                    self.logger.warning("CSV v2 final flush failed because writer is unavailable.")
            except Exception as exc:
                shutdown_flush_succeeded = False
                self.logger.warning("CSV v2 final flush failed: %s", exc)
        if deferred_item is not None:
            if buffer or v2_buffer:
                shutdown_flush_succeeded = False
                self.logger.warning(
                    "CSV deferred shutdown row was not written because previous-day final flush failed."
                )
            elif self.auto_save:
                self._close_file(f_handle)
                if not self._close_v2_file(
                    v2_handle,
                    closeout_reason="daily-rollover",
                    finalize_closeout=shutdown_flush_succeeded,
                ):
                    shutdown_flush_succeeded = False
                f_handle, writer = None, None
                v2_handle, v2_writer = None, None
                try:
                    timestamp = self._parse_timestamp(deferred_item)
                    row = self._build_row(deferred_item, timestamp)
                    if self.csv_v1_enabled:
                        f_handle, writer = self._open_log_file(
                            self._filename_timestamp(timestamp),
                            prefix=file_prefix,
                        )
                        if self._flush_buffer(writer, f_handle, [(row, timestamp)]):
                            self.logger.info("CSV deferred shutdown v1 row written after final rollover flush.")
                        else:
                            shutdown_flush_succeeded = False
                            self.logger.warning("CSV deferred shutdown v1 row was not written.")
                    if self.csv_v2_enabled:
                        self._sample_seq += 1
                        v2_row = self._build_v2_row(
                            deferred_item,
                            timestamp,
                            datetime.now().astimezone(),
                            self._sample_seq,
                            row,
                        )
                        v2_handle, v2_writer = self._open_v2_log_file(
                            self._filename_timestamp(timestamp),
                            prefix=v2_file_prefix,
                        )
                        if self._flush_v2_buffer(v2_writer, v2_handle, [(v2_row, timestamp)]):
                            self.logger.info("CSV deferred shutdown v2 row written after final rollover flush.")
                        else:
                            shutdown_flush_succeeded = False
                            self.logger.warning("CSV deferred shutdown v2 row was not written.")
                except Exception as exc:
                    shutdown_flush_succeeded = False
                    self.logger.warning("CSV deferred shutdown row write failed: %s", exc)
        self._buffer_size = 0
        self._close_file(f_handle)
        if not self._close_v2_file(
            v2_handle,
            closeout_reason="shutdown",
            finalize_closeout=shutdown_flush_succeeded,
        ):
            shutdown_flush_succeeded = False
        if (
            self.csv_v2_enabled
            and self.csv_v2_sidecar_enabled
            and self._finalize_spot_image_manifest_on_stop
        ):
            if not self._write_spot_image_fact_final_manifest_safely():
                shutdown_flush_succeeded = False
        elif self.csv_v2_enabled and self.csv_v2_sidecar_enabled:
            self.logger.warning(
                "Skipped SPOT image fact final manifest because image capture did not drain."
            )
        self._shutdown_flush_succeeded = shutdown_flush_succeeded
        self.logger.info("CSV logger thread stopped.")


logger_service = CSVLoggerService(require_runtime_manifest_state=True)
