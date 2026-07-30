from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
import threading
from datetime import datetime, timezone
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn, Optional

from backend.FacilityData.spot_low_signal import (
    LOW_SIGNAL_ALARM_BIT,
    LOW_SIGNAL_COMPARATORS,
    derive_low_signal_evidence,
)
from backend.FacilityData.spot_diagnostics import (
    SPOT_DIAGNOSTIC_OUTPUT_FIELDS,
    parse_diagnostics_field_status,
    parse_diagnostics_missing_fields,
)


SPOT_OBSERVATION_FACT_SCHEMA_VERSION = "1.3.0"
SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION = "1.2.1"
SPOT_OBSERVATION_FACT_FILENAME = "spot_observation_fact.csv"
_SPOT_OBSERVATION_FACT_FILE_LOCK = threading.Lock()
_MANIFEST_SQL_BATCH_SIZE = 4096
LOW_SIGNAL_ALARM_BIT_MASK = LOW_SIGNAL_ALARM_BIT
SPOT_DIAGNOSTIC_EVIDENCE_CODES = frozenset(
    {
        "actuator_position_changed",
        "actuator_scanning",
        "alarm_low_signal",
        "detector_below_measurement_range",
        "measurement_range_configured",
        "peak_picker_off_mode_reset_configured",
        "signal_at_or_above_configured_threshold",
        "signal_below_configured_threshold_alarm_disabled",
        "signal_below_threshold",
        "signalpc_present_comparator_unverified",
        "signalpc_present_threshold_unknown",
        "target_absent_verified",
        "target_out_of_fov_evidence",
    }
)
SPOT_DIAGNOSTIC_FACT_FIELDS = (
    "alarmstatus",
    "signalpc",
    "d1temperature",
    "d2temperature",
    "e1out",
    "e2out",
    "itemperature",
    "appnumber",
    "instrument_info",
    "peak_picker_enabled",
    "peak_picker_threshold",
    "peak_picker_off_delay_ms",
    "peak_picker_off_mode",
    "actuator_position",
    "actuator_scan_state",
    "actuator_peak_found",
)
SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS = [
    "spot_observation_fact_schema_version",
    "spot_observation_key",
    "spot_service_instance_id",
    "spot_poll_seq",
    "spot_observation_seq",
    "spot_poll_status",
    "spot_raw_validity",
    "spot_device_status_code",
    "spot_temperature_raw",
    "spot_raw_payload_hash",
    "spot_error_code",
    "spot_http_status_code",
    "spot_response_length_bytes",
    "spot_raw_payload_truncated",
    "spot_raw_payload_encoding",
    "spot_last_poll_started_at",
    "spot_last_poll_completed_at",
    "spot_poll_duration_ms",
    "diagnostics_captured_at",
    "diagnostics_capture_status",
    "diagnostics_age_ms",
    "spot_diagnostic_evidence_codes",
    "alarmstatus",
    "signalpc",
    "d1temperature",
    "d2temperature",
    "e1out",
    "e2out",
    "itemperature",
    "appnumber",
    "instrument_info",
    "peak_picker_enabled",
    "peak_picker_threshold",
    "peak_picker_off_delay_ms",
    "peak_picker_off_mode",
    "actuator_position",
    "actuator_scan_state",
    "actuator_peak_found",
    "low_signal_alarm_enabled",
    "low_signal_threshold_pc",
    "low_signal_comparator",
    "low_signal_comparator_verified",
    "spot_app_mode",
    "spot_range_min_c",
    "spot_range_max_c",
    "window_obscuration_pc",
    "focus_mm",
]
_SPOT_OBSERVATION_FACT_EVIDENCE_INDEX = SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS.index(
    "spot_diagnostic_evidence_codes"
)
SPOT_OBSERVATION_FACT_COLUMNS = [
    *SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS[:_SPOT_OBSERVATION_FACT_EVIDENCE_INDEX],
    "diagnostics_snapshot_id",
    "diagnostics_source_poll_seq",
    "diagnostics_binding_status",
    "diagnostics_missing_fields",
    "diagnostics_field_status_json",
    "diagnostics_source",
    SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS[_SPOT_OBSERVATION_FACT_EVIDENCE_INDEX],
    "evidence_provenance_json",
    *SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS[_SPOT_OBSERVATION_FACT_EVIDENCE_INDEX + 1 :],
]
SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS = {
    "alarmstatus": "alarmstatus_nonblank_count",
    "signalpc": "signalpc_nonblank_count",
    "d1temperature": "d1temperature_nonblank_count",
    "d2temperature": "d2temperature_nonblank_count",
    "e1out": "e1out_nonblank_count",
    "e2out": "e2out_nonblank_count",
}
SPOT_DIAGNOSTIC_EVIDENCE_FIELDS = {
    "alarm_low_signal": "alarmstatus",
    "signal_at_or_above_configured_threshold": "signalpc",
    "signal_below_configured_threshold_alarm_disabled": "signalpc",
    "signal_below_threshold": "signalpc",
    "signalpc_present_comparator_unverified": "signalpc",
    "signalpc_present_threshold_unknown": "signalpc",
    "peak_picker_off_mode_reset_configured": "peak_picker_off_mode",
    "actuator_position_changed": "actuator_position",
    "actuator_scanning": "actuator_scan_state",
    "target_absent_verified": "target_absent_verified",
    "target_out_of_fov_evidence": "target_out_of_fov_evidence",
    "measurement_range_configured": "spot_range_min_c",
    "detector_below_measurement_range": "spot_device_status_code",
}


@dataclass
class SpotObservationFactWriter:
    output_path: Path
    spool_path: Optional[Path] = None
    load_existing_keys: bool = True
    failure_count: int = 0
    _seen_keys: set[str] = field(default_factory=set)
    _seen_poll_sequences: set[int] = field(default_factory=set, init=False, repr=False)
    _manifest_digest: Any = field(default_factory=hashlib.sha256, init=False, repr=False)
    _manifest_state_ready: bool = field(default=True, init=False, repr=False)
    _manifest_tracked_size: int = field(default=0, init=False, repr=False)
    _manifest_row_count: int = field(default=0, init=False, repr=False)
    _capture_status_counts: Counter[str] = field(
        default_factory=Counter,
        init=False,
        repr=False,
    )
    _binding_status_counts: Counter[str] = field(
        default_factory=Counter,
        init=False,
        repr=False,
    )
    _missing_field_counts: Counter[str] = field(
        default_factory=Counter,
        init=False,
        repr=False,
    )
    _diagnostic_field_counts: Counter[str] = field(
        default_factory=Counter,
        init=False,
        repr=False,
    )
    _evidence_code_count: int = field(default=0, init=False, repr=False)
    _provenance_code_count: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.load_existing_keys:
            self._load_manifest_state_from_output()

    def ensure_initialized(self) -> bool:
        """Create a current-schema header even when no observation has been emitted yet."""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            with _SPOT_OBSERVATION_FACT_FILE_LOCK:
                if (
                    self._manifest_state_ready
                    and self._output_size() != self._manifest_tracked_size
                ):
                    self._manifest_state_ready = False
                write_header = self._prepare_output_file_for_append()
                if write_header:
                    previous_size = self._output_size()
                    with self.output_path.open("a", encoding="utf-8-sig", newline="") as handle:
                        csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS).writeheader()
                    self._extend_manifest_digest(previous_size)
                return (
                    self._manifest_state_ready
                    and self._output_size() == self._manifest_tracked_size
                )
        except Exception:
            self.failure_count += 1
            return False

    def write_fact(self, snapshot: Mapping[str, Any]) -> Optional[dict[str, str]]:
        fact = build_spot_observation_fact(snapshot)
        key = fact["spot_observation_key"]
        if not key or key in self._seen_keys:
            return None
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._flush_spool()
            self._append_fact(fact)
            return fact
        except Exception:
            self.failure_count += 1
            self._spool_fact(fact)
            return None

    def _append_fact(self, fact: Mapping[str, str]) -> None:
        with _SPOT_OBSERVATION_FACT_FILE_LOCK:
            write_header = self._prepare_output_file_for_append()
            previous_size = self._output_size()
            with self.output_path.open("a", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
                if write_header:
                    writer.writeheader()
                writer.writerow(fact)
            self._extend_manifest_digest(previous_size)
            self._record_manifest_row(fact)

    def _prepare_output_file_for_append(self) -> bool:
        if not self.output_path.exists() or self.output_path.stat().st_size == 0:
            return True
        if self._existing_header_matches_current_schema():
            return False
        self._archive_mismatched_output_file()
        return True

    def _existing_header_matches_current_schema(self) -> bool:
        try:
            with self.output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                existing_header = next(csv.reader(handle), [])
        except (OSError, UnicodeError, csv.Error):
            return False
        return existing_header == SPOT_OBSERVATION_FACT_COLUMNS

    def _archive_mismatched_output_file(self) -> None:
        archive_path = self._next_schema_mismatch_archive_path(self.output_path)
        self.output_path.rename(archive_path)
        self._reset_manifest_state()

    def _next_schema_mismatch_archive_path(self, source_path: Path) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        suffix = source_path.suffix or ".csv"
        archive_stem = f"{source_path.stem}.{timestamp}.schema-mismatch"
        candidate = source_path.with_name(f"{archive_stem}{suffix}")
        for index in range(1, 1000):
            if not candidate.exists():
                return candidate
            candidate = source_path.with_name(f"{archive_stem}.{index}{suffix}")
        raise FileExistsError(f"Could not allocate archive path for {source_path}")

    def _flush_spool(self) -> None:
        spool_path = self._effective_spool_path()
        if not spool_path.exists() or spool_path.stat().st_size == 0:
            return
        pending: list[dict[str, str]] = []
        with spool_path.open("r", encoding="utf-8") as handle:
            spool_lines = list(handle)
        for line in spool_lines:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                self._quarantine_invalid_spool(spool_path, "malformed-json", exc)
            if not isinstance(raw, dict):
                self._quarantine_invalid_spool(spool_path, "non-object-row")
            if raw.get("spot_observation_fact_schema_version") != SPOT_OBSERVATION_FACT_SCHEMA_VERSION or not set(
                SPOT_OBSERVATION_FACT_COLUMNS
            ).issubset(raw):
                self._quarantine_invalid_spool(spool_path, "schema-mismatch")
            pending.append({column: _text(raw.get(column)) for column in SPOT_OBSERVATION_FACT_COLUMNS})
        for fact in pending:
            key = fact["spot_observation_key"]
            if key and key not in self._seen_keys:
                self._append_fact(fact)
        spool_path.unlink(missing_ok=True)

    def _quarantine_invalid_spool(
        self,
        spool_path: Path,
        reason: str,
        cause: Exception | None = None,
    ) -> NoReturn:
        archive_path = self._next_schema_mismatch_archive_path(spool_path)
        spool_path.rename(archive_path)
        error = ValueError(
            f"Invalid SPOT observation fact spool quarantined: {reason}: {archive_path.name}"
        )
        if cause is not None:
            raise error from cause
        raise error

    def _spool_fact(self, fact: Mapping[str, str]) -> None:
        try:
            spool_path = self._effective_spool_path()
            spool_path.parent.mkdir(parents=True, exist_ok=True)
            with spool_path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(json.dumps(dict(fact), sort_keys=True, ensure_ascii=False))
                handle.write("\n")
        except Exception:
            return

    def _effective_spool_path(self) -> Path:
        if self.spool_path is not None:
            return self.spool_path
        return self.output_path.with_name(f"{self.output_path.name}.failed.jsonl")

    def spool_pending_count(self) -> int:
        spool_path = self._effective_spool_path()
        suffix = spool_path.suffix
        archive_pattern = f"{spool_path.stem}.*.schema-mismatch{suffix}"
        spool_paths = [spool_path, *sorted(spool_path.parent.glob(archive_pattern))]
        pending_count = 0
        for pending_path in spool_paths:
            if not pending_path.exists() or pending_path.stat().st_size == 0:
                continue
            with pending_path.open("r", encoding="utf-8") as handle:
                pending_count += sum(1 for line in handle if line.strip())
        return pending_count

    def manifest_summary(
        self,
        *,
        realtime_rows: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with _SPOT_OBSERVATION_FACT_FILE_LOCK:
            if (
                self._manifest_state_ready
                and self._output_size() != self._manifest_tracked_size
            ):
                self._manifest_state_ready = False
            if not self._manifest_state_ready:
                raise RuntimeError(
                    "SPOT observation fact runtime manifest state is unavailable"
                )
            realtime_row_count = 0
            linked_rows = 0
            for row in realtime_rows or ():
                key = _text(row.get("spot_observation_key")).strip()
                if not key:
                    continue
                realtime_row_count += 1
                if key in self._seen_keys:
                    linked_rows += 1
            first_poll_seq = (
                min(self._seen_poll_sequences)
                if self._seen_poll_sequences
                else None
            )
            last_poll_seq = (
                max(self._seen_poll_sequences)
                if self._seen_poll_sequences
                else None
            )
            poll_seq_gap_count = 0
            if first_poll_seq is not None and last_poll_seq is not None:
                poll_seq_gap_count = (
                    last_poll_seq
                    - first_poll_seq
                    + 1
                    - len(self._seen_poll_sequences)
                )
            missing_rows = realtime_row_count - linked_rows
            link_coverage_pct = (
                linked_rows / realtime_row_count * 100.0
                if realtime_row_count
                else 0.0
            )
            missing_provenance_count = max(
                0,
                self._evidence_code_count - self._provenance_code_count,
            )
            provenance_coverage_pct = (
                self._provenance_code_count
                / self._evidence_code_count
                * 100.0
                if self._evidence_code_count
                else 100.0
            )
            return {
                "header": list(SPOT_OBSERVATION_FACT_COLUMNS),
                "row_count": self._manifest_row_count,
                "distinct_observation_key_count": len(self._seen_keys),
                "first_poll_seq": first_poll_seq,
                "last_poll_seq": last_poll_seq,
                "poll_seq_gap_count": max(0, poll_seq_gap_count),
                "sha256": self._manifest_digest.copy().hexdigest(),
                "link_coverage": {
                    "realtime_rows_with_observation_key": realtime_row_count,
                    "linked_rows": linked_rows,
                    "missing_fact_key_rows": missing_rows,
                    "coverage_pct": round(link_coverage_pct, 6),
                },
                "diagnostic_field_coverage": {
                    manifest_key: self._diagnostic_field_counts[fact_column]
                    for fact_column, manifest_key in (
                        SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS.items()
                    )
                },
                "diagnostics_capture_status_counts": dict(
                    sorted(self._capture_status_counts.items())
                ),
                "diagnostics_binding_status_counts": dict(
                    sorted(self._binding_status_counts.items())
                ),
                "diagnostics_missing_field_counts": dict(
                    sorted(self._missing_field_counts.items())
                ),
                "evidence_provenance_coverage": {
                    "evidence_code_count": self._evidence_code_count,
                    "provenance_code_count": self._provenance_code_count,
                    "missing_provenance_count": missing_provenance_count,
                    "coverage_pct": round(provenance_coverage_pct, 6),
                },
            }

    def _load_manifest_state_from_output(self) -> None:
        if not self.output_path.exists() or self.output_path.stat().st_size == 0:
            return
        try:
            expected_size = self.output_path.stat().st_size
            self._manifest_digest = _file_sha256_digest(self.output_path)
            with self.output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if list(reader.fieldnames or []) != SPOT_OBSERVATION_FACT_COLUMNS:
                    self._manifest_state_ready = False
                    return
                for row in reader:
                    self._record_manifest_row(row)
            if self.output_path.stat().st_size != expected_size:
                self._manifest_state_ready = False
                return
            self._manifest_tracked_size = expected_size
        except (OSError, UnicodeError, csv.Error):
            self._manifest_state_ready = False

    def _record_manifest_row(self, row: Mapping[str, Any]) -> None:
        self._manifest_row_count += 1
        key = _text(row.get("spot_observation_key")).strip()
        if key:
            self._seen_keys.add(key)
        poll_sequence = _positive_int_or_none(row.get("spot_poll_seq"))
        if poll_sequence is not None:
            self._seen_poll_sequences.add(poll_sequence)
        self._capture_status_counts[
            _text(row.get("diagnostics_capture_status")).strip() or "missing"
        ] += 1
        self._binding_status_counts[
            _text(row.get("diagnostics_binding_status")).strip() or "missing"
        ] += 1
        self._missing_field_counts.update(
            parse_diagnostics_missing_fields(row.get("diagnostics_missing_fields"))
        )
        for fact_column in SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS:
            if _text(row.get(fact_column)).strip():
                self._diagnostic_field_counts[fact_column] += 1
        evidence_codes = set(
            parse_spot_diagnostic_evidence_codes(
                row.get("spot_diagnostic_evidence_codes")
            )
        )
        provenance = _json_object(row.get("evidence_provenance_json"))
        self._evidence_code_count += len(evidence_codes)
        self._provenance_code_count += len(
            evidence_codes.intersection(provenance)
        )

    def _output_size(self) -> int:
        try:
            return self.output_path.stat().st_size
        except FileNotFoundError:
            return 0

    def _extend_manifest_digest(self, previous_size: int) -> None:
        if not self._manifest_state_ready:
            return
        try:
            current_size = self._output_size()
            if previous_size != self._manifest_tracked_size or current_size < previous_size:
                self._manifest_state_ready = False
                return
            with self.output_path.open("rb") as handle:
                handle.seek(previous_size)
                remaining = current_size - previous_size
                while remaining > 0:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise OSError("SPOT observation fact digest read was truncated")
                    self._manifest_digest.update(chunk)
                    remaining -= len(chunk)
            if self._output_size() != current_size:
                self._manifest_state_ready = False
                return
        except OSError:
            # The CSV append already succeeded. Keep deduplication state current,
            # but fail manifest closeout closed instead of spooling a duplicate.
            self._manifest_state_ready = False
            return
        self._manifest_tracked_size = current_size

    def _reset_manifest_state(self) -> None:
        self._seen_keys.clear()
        self._seen_poll_sequences.clear()
        self._manifest_digest = hashlib.sha256()
        self._manifest_state_ready = True
        self._manifest_tracked_size = 0
        self._manifest_row_count = 0
        self._capture_status_counts.clear()
        self._binding_status_counts.clear()
        self._missing_field_counts.clear()
        self._diagnostic_field_counts.clear()
        self._evidence_code_count = 0
        self._provenance_code_count = 0


def build_spot_observation_fact_manifest(
    *,
    fact_path: Path,
    enabled: bool,
    write_failure_count: int = 0,
    spool_pending_count: int | None = None,
    realtime_rows: Iterable[Mapping[str, Any]] | None = None,
    path: str | None = None,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_summary = (
        dict(summary)
        if summary is not None
        else summarize_spot_observation_fact(
            fact_path=fact_path,
            realtime_rows=realtime_rows,
        )
    )
    return {
        "enabled": bool(enabled),
        "schema_version": SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
        "path": path or fact_path.name,
        "row_count": resolved_summary["row_count"],
        "distinct_observation_key_count": resolved_summary[
            "distinct_observation_key_count"
        ],
        "first_poll_seq": resolved_summary["first_poll_seq"],
        "last_poll_seq": resolved_summary["last_poll_seq"],
        "poll_seq_gap_count": resolved_summary["poll_seq_gap_count"],
        "sha256": resolved_summary["sha256"],
        "write_failure_count": int(write_failure_count),
        "spool_pending_count": (
            int(spool_pending_count)
            if spool_pending_count is not None
            else _spool_pending_count(fact_path.with_name(f"{fact_path.name}.failed.jsonl"))
        ),
        "required_columns": list(SPOT_OBSERVATION_FACT_COLUMNS),
        "link_coverage": resolved_summary["link_coverage"],
        "diagnostic_field_coverage": resolved_summary["diagnostic_field_coverage"],
        "diagnostics_capture_status_counts": resolved_summary[
            "diagnostics_capture_status_counts"
        ],
        "diagnostics_binding_status_counts": resolved_summary[
            "diagnostics_binding_status_counts"
        ],
        "diagnostics_missing_field_counts": resolved_summary[
            "diagnostics_missing_field_counts"
        ],
        "evidence_provenance_coverage": resolved_summary[
            "evidence_provenance_coverage"
        ],
    }


def summarize_spot_observation_fact(
    *,
    fact_path: Path,
    realtime_rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    realtime_row_count = 0
    linked_rows = 0
    header: list[str] = []
    row_count = 0
    distinct_observation_key_count = 0
    distinct_poll_sequence_count = 0
    first_poll_seq: int | None = None
    last_poll_seq: int | None = None
    capture_status_counts: Counter[str] = Counter()
    binding_status_counts: Counter[str] = Counter()
    missing_field_counts: Counter[str] = Counter()
    diagnostic_field_counts: Counter[str] = Counter()
    evidence_code_count = 0
    provenance_code_count = 0

    distinct_state: sqlite3.Connection | None = None
    try:
        distinct_state = sqlite3.connect("")
        distinct_state.execute("PRAGMA journal_mode=OFF")
        distinct_state.execute("PRAGMA synchronous=OFF")
        distinct_state.execute("PRAGMA temp_store=FILE")
        distinct_state.execute(
            "CREATE TABLE observation_keys (value TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        distinct_state.execute(
            "CREATE TABLE poll_sequences (value INTEGER PRIMARY KEY) WITHOUT ROWID"
        )
        distinct_state.execute(
            "CREATE TABLE realtime_keys "
            "(value TEXT PRIMARY KEY, occurrence_count INTEGER NOT NULL) WITHOUT ROWID"
        )
        observation_key_batch: list[tuple[str]] = []
        poll_sequence_batch: list[tuple[int]] = []
        realtime_key_batch: list[tuple[str, int]] = []

        def flush_distinct_state() -> None:
            if observation_key_batch:
                distinct_state.executemany(
                    "INSERT OR IGNORE INTO observation_keys(value) VALUES (?)",
                    observation_key_batch,
                )
                observation_key_batch.clear()
            if poll_sequence_batch:
                distinct_state.executemany(
                    "INSERT OR IGNORE INTO poll_sequences(value) VALUES (?)",
                    poll_sequence_batch,
                )
                poll_sequence_batch.clear()
            if realtime_key_batch:
                distinct_state.executemany(
                    "INSERT INTO realtime_keys(value, occurrence_count) VALUES (?, ?) "
                    "ON CONFLICT(value) DO UPDATE SET "
                    "occurrence_count = occurrence_count + excluded.occurrence_count",
                    realtime_key_batch,
                )
                realtime_key_batch.clear()

        for row in realtime_rows or ():
            key = _text(row.get("spot_observation_key")).strip()
            if not key:
                continue
            realtime_row_count += 1
            realtime_key_batch.append((key, 1))
            if len(realtime_key_batch) >= _MANIFEST_SQL_BATCH_SIZE:
                flush_distinct_state()
        flush_distinct_state()

        if fact_path.exists() and fact_path.stat().st_size > 0:
            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                header = list(reader.fieldnames or [])
                for row in reader:
                    row_count += 1
                    key = _text(row.get("spot_observation_key")).strip()
                    if key:
                        observation_key_batch.append((key,))
                    poll_sequence = _positive_int_or_none(row.get("spot_poll_seq"))
                    if poll_sequence is not None:
                        poll_sequence_batch.append((poll_sequence,))
                    if (
                        len(observation_key_batch) >= _MANIFEST_SQL_BATCH_SIZE
                        or len(poll_sequence_batch) >= _MANIFEST_SQL_BATCH_SIZE
                    ):
                        flush_distinct_state()
                    capture_status_counts[
                        _text(row.get("diagnostics_capture_status")).strip() or "missing"
                    ] += 1
                    binding_status_counts[
                        _text(row.get("diagnostics_binding_status")).strip() or "missing"
                    ] += 1
                    missing_field_counts.update(
                        parse_diagnostics_missing_fields(
                            row.get("diagnostics_missing_fields")
                        )
                    )
                    for fact_column in (
                        SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS
                    ):
                        if _text(row.get(fact_column)).strip():
                            diagnostic_field_counts[fact_column] += 1
                    evidence_codes = set(
                        parse_spot_diagnostic_evidence_codes(
                            row.get("spot_diagnostic_evidence_codes")
                        )
                    )
                    provenance = _json_object(row.get("evidence_provenance_json"))
                    evidence_code_count += len(evidence_codes)
                    provenance_code_count += len(
                        evidence_codes.intersection(provenance)
                    )

        flush_distinct_state()
        distinct_observation_key_count = int(
            distinct_state.execute(
                "SELECT COUNT(*) FROM observation_keys"
            ).fetchone()[0]
        )
        poll_sequence_summary = distinct_state.execute(
            "SELECT MIN(value), MAX(value), COUNT(*) FROM poll_sequences"
        ).fetchone()
        if poll_sequence_summary is not None:
            first_poll_seq = poll_sequence_summary[0]
            last_poll_seq = poll_sequence_summary[1]
            distinct_poll_sequence_count = int(poll_sequence_summary[2])
        linked_summary = distinct_state.execute(
            "SELECT COALESCE(SUM(realtime_keys.occurrence_count), 0) "
            "FROM realtime_keys "
            "INNER JOIN observation_keys "
            "ON observation_keys.value = realtime_keys.value"
        ).fetchone()
        if linked_summary is not None:
            linked_rows = int(linked_summary[0] or 0)
    finally:
        if distinct_state is not None:
            distinct_state.close()

    poll_seq_gap_count = 0
    if first_poll_seq is not None and last_poll_seq is not None:
        poll_seq_gap_count = (
            (last_poll_seq - first_poll_seq + 1) - distinct_poll_sequence_count
        )
    missing_provenance_count = max(0, evidence_code_count - provenance_code_count)
    provenance_coverage_pct = (
        provenance_code_count / evidence_code_count * 100.0 if evidence_code_count else 100.0
    )
    missing_rows = realtime_row_count - linked_rows
    link_coverage_pct = (
        linked_rows / realtime_row_count * 100.0 if realtime_row_count else 0.0
    )
    return {
        "header": header,
        "row_count": row_count,
        "distinct_observation_key_count": distinct_observation_key_count,
        "first_poll_seq": first_poll_seq,
        "last_poll_seq": last_poll_seq,
        "poll_seq_gap_count": max(0, poll_seq_gap_count),
        "sha256": _file_sha256(fact_path),
        "link_coverage": {
            "realtime_rows_with_observation_key": realtime_row_count,
            "linked_rows": linked_rows,
            "missing_fact_key_rows": missing_rows,
            "coverage_pct": round(link_coverage_pct, 6),
        },
        "diagnostic_field_coverage": {
            manifest_key: diagnostic_field_counts[fact_column]
            for fact_column, manifest_key in SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS.items()
        },
        "diagnostics_capture_status_counts": dict(sorted(capture_status_counts.items())),
        "diagnostics_binding_status_counts": dict(sorted(binding_status_counts.items())),
        "diagnostics_missing_field_counts": dict(sorted(missing_field_counts.items())),
        "evidence_provenance_coverage": {
            "evidence_code_count": evidence_code_count,
            "provenance_code_count": provenance_code_count,
            "missing_provenance_count": missing_provenance_count,
            "coverage_pct": round(provenance_coverage_pct, 6),
        },
    }


def _file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return _file_sha256_digest(path).hexdigest()


def _file_sha256_digest(path: Path) -> Any:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest


def _spool_pending_count(spool_path: Path) -> int:
    if not spool_path.exists() or spool_path.stat().st_size == 0:
        return 0
    try:
        with spool_path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _positive_int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def build_spot_observation_key(snapshot: Mapping[str, Any]) -> str:
    service_id = _text(snapshot.get("spot_service_instance_id"))
    poll_seq = _positive_poll_seq_text(snapshot.get("spot_poll_seq"))
    completed_at = _text(snapshot.get("spot_last_poll_completed_at"))
    if not service_id or not poll_seq or not completed_at or _is_startup_pending_snapshot(snapshot):
        return ""
    return f"{service_id}:{poll_seq}"


def _positive_poll_seq_text(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return ""
    if parsed <= 0:
        return ""
    return str(parsed)


def _is_startup_pending_snapshot(snapshot: Mapping[str, Any]) -> bool:
    return (
        _text(snapshot.get("spot_poll_status")) == "not_attempted"
        or _text(snapshot.get("temperature_output_status")) == "startup_pending"
        or _text(snapshot.get("temperature_status_shadow")) == "startup_pending"
    )


def _diagnostics_field_status_for_fact(snapshot: Mapping[str, Any]) -> dict[str, str]:
    parsed = parse_diagnostics_field_status(snapshot.get("diagnostics_field_status"))
    if parsed:
        return {
            field: parsed.get(field, "missing") for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS
        }
    return {
        field: "success" if _diagnostic_value_present(snapshot.get(field)) else "missing"
        for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS
    }


def _diagnostic_value_for_fact(snapshot: Mapping[str, Any], field: str) -> str:
    validated_value = _text(snapshot.get(field))
    if validated_value:
        return validated_value
    raw_values = snapshot.get("diagnostics_raw_values")
    if not isinstance(raw_values, Mapping):
        return ""
    return _text(raw_values.get(field))


def _build_evidence_provenance_json(
    snapshot: Mapping[str, Any],
    evidence_codes: Iterable[str],
    field_status: Mapping[str, str],
) -> str:
    captured_at = _text(snapshot.get("diagnostics_captured_at"))
    age_ms = _finite_non_negative_float_or_none(snapshot.get("diagnostics_age_ms"))
    max_age_ms = _finite_non_negative_float_or_none(snapshot.get("diagnostics_max_age_ms"))
    source = _text(snapshot.get("diagnostics_source")) or "unknown"
    collection_mode = _text(snapshot.get("diagnostics_collection_mode")) or "async_fact_only"
    snapshot_id = _text(snapshot.get("diagnostics_snapshot_id"))
    source_poll_seq = _positive_int_or_none(snapshot.get("diagnostics_source_poll_seq"))
    binding_status = _text(snapshot.get("diagnostics_binding_status")) or "missing"
    provenance: dict[str, dict[str, Any]] = {}
    for code in evidence_codes:
        field_name = SPOT_DIAGNOSTIC_EVIDENCE_FIELDS.get(code)
        if not field_name:
            continue
        provenance[code] = {
            "captured_at": captured_at,
            "age_ms": age_ms,
            "max_age_ms": max_age_ms,
            "source": source,
            "collection_mode": collection_mode,
            "field": field_name,
            "field_status": field_status.get(
                field_name,
                "success" if _diagnostic_value_present(snapshot.get(field_name)) else "missing",
            ),
            "snapshot_id": snapshot_id,
            "source_poll_seq": source_poll_seq,
            "binding_status": binding_status,
        }
    if not provenance:
        return ""
    return json.dumps(provenance, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def build_spot_observation_fact(snapshot: Mapping[str, Any]) -> dict[str, str]:
    completed_at = _text(snapshot.get("spot_last_poll_completed_at"))
    diagnostics_present = _has_diagnostic_payload(snapshot)
    diagnostics_capture_status = _text(snapshot.get("diagnostics_capture_status"))
    if not diagnostics_capture_status:
        diagnostics_capture_status = "async_partial" if diagnostics_present else "missing"
    diagnostics_captured_at = _text(snapshot.get("diagnostics_captured_at")) or completed_at
    diagnostics_age_ms = _text(snapshot.get("diagnostics_age_ms"))
    diagnostics_binding_status = _text(snapshot.get("diagnostics_binding_status"))
    if not diagnostics_binding_status:
        diagnostics_binding_status = "unbound" if diagnostics_present else "missing"
    diagnostics_collection_mode = (
        _text(snapshot.get("diagnostics_collection_mode")) or "async_fact_only"
    )
    diagnostics_field_status = _diagnostics_field_status_for_fact(snapshot)
    diagnostics_missing_fields = parse_diagnostics_missing_fields(
        snapshot.get("diagnostics_missing_fields")
    )
    if not diagnostics_missing_fields:
        diagnostics_missing_fields = tuple(
            field for field, status in diagnostics_field_status.items() if status != "success"
        )
    evidence_codes = encode_spot_diagnostic_evidence_codes(snapshot)
    parsed_evidence_codes = parse_spot_diagnostic_evidence_codes(evidence_codes)
    return {
        "spot_observation_fact_schema_version": SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
        "spot_observation_key": build_spot_observation_key(snapshot),
        "spot_service_instance_id": _text(snapshot.get("spot_service_instance_id")),
        "spot_poll_seq": _text(snapshot.get("spot_poll_seq")),
        "spot_observation_seq": _text(snapshot.get("spot_observation_seq")),
        "spot_poll_status": _text(snapshot.get("spot_poll_status")),
        "spot_raw_validity": _text(snapshot.get("spot_raw_validity")),
        "spot_device_status_code": _text(snapshot.get("spot_device_status_code")),
        "spot_temperature_raw": _text(snapshot.get("spot_raw_value_text")),
        "spot_raw_payload_hash": _text(snapshot.get("spot_raw_payload_hash")),
        "spot_error_code": _text(snapshot.get("spot_error_code")),
        "spot_http_status_code": _text(snapshot.get("spot_http_status_code")),
        "spot_response_length_bytes": _text(snapshot.get("spot_response_content_length")),
        "spot_raw_payload_truncated": "false",
        "spot_raw_payload_encoding": "utf-8-replace" if snapshot.get("spot_raw_value_text") is not None else "",
        "spot_last_poll_started_at": _text(snapshot.get("spot_last_poll_started_at")),
        "spot_last_poll_completed_at": completed_at,
        "spot_poll_duration_ms": _text(snapshot.get("spot_poll_duration_ms")),
        "diagnostics_captured_at": diagnostics_captured_at,
        "diagnostics_capture_status": diagnostics_capture_status,
        "diagnostics_age_ms": diagnostics_age_ms,
        "diagnostics_snapshot_id": _text(snapshot.get("diagnostics_snapshot_id")),
        "diagnostics_source_poll_seq": _text(snapshot.get("diagnostics_source_poll_seq")),
        "diagnostics_binding_status": diagnostics_binding_status,
        "diagnostics_missing_fields": json.dumps(
            list(diagnostics_missing_fields), ensure_ascii=False, separators=(",", ":")
        ),
        "diagnostics_field_status_json": json.dumps(
            diagnostics_field_status, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ),
        "diagnostics_source": diagnostics_collection_mode,
        "spot_diagnostic_evidence_codes": evidence_codes,
        "evidence_provenance_json": _build_evidence_provenance_json(
            snapshot,
            parsed_evidence_codes,
            diagnostics_field_status,
        ),
        "alarmstatus": _diagnostic_value_for_fact(snapshot, "alarmstatus"),
        "signalpc": _diagnostic_value_for_fact(snapshot, "signalpc"),
        "d1temperature": _diagnostic_value_for_fact(snapshot, "d1temperature"),
        "d2temperature": _diagnostic_value_for_fact(snapshot, "d2temperature"),
        "e1out": _diagnostic_value_for_fact(snapshot, "e1out"),
        "e2out": _diagnostic_value_for_fact(snapshot, "e2out"),
        "itemperature": _diagnostic_value_for_fact(snapshot, "itemperature"),
        "appnumber": _diagnostic_value_for_fact(snapshot, "appnumber"),
        "instrument_info": _text(snapshot.get("instrument_info")),
        "peak_picker_enabled": _text(snapshot.get("peak_picker_enabled")),
        "peak_picker_threshold": _text(snapshot.get("peak_picker_threshold")),
        "peak_picker_off_delay_ms": _text(snapshot.get("peak_picker_off_delay_ms")),
        "peak_picker_off_mode": _text(snapshot.get("peak_picker_off_mode")),
        "actuator_position": _text(snapshot.get("actuator_position")),
        "actuator_scan_state": _text(snapshot.get("actuator_scan_state")),
        "actuator_peak_found": _text(snapshot.get("actuator_peak_found")),
        "low_signal_alarm_enabled": _text(snapshot.get("low_signal_alarm_enabled")),
        "low_signal_threshold_pc": _text(snapshot.get("low_signal_threshold_pc")),
        "low_signal_comparator": _text(snapshot.get("low_signal_comparator")),
        "low_signal_comparator_verified": _text(snapshot.get("low_signal_comparator_verified")),
        "spot_app_mode": _text(snapshot.get("spot_app_mode")),
        "spot_range_min_c": _text(snapshot.get("spot_range_min_c")),
        "spot_range_max_c": _text(snapshot.get("spot_range_max_c")),
        "window_obscuration_pc": _text(snapshot.get("window_obscuration_pc")),
        "focus_mm": _text(snapshot.get("focus_mm")),
    }


def encode_spot_diagnostic_evidence_codes(snapshot: Mapping[str, Any]) -> str:
    codes = derive_spot_diagnostic_evidence_codes(snapshot)
    if not codes and not _has_diagnostic_payload(snapshot) and not snapshot.get("spot_diagnostic_evidence_codes"):
        return ""
    return json.dumps(list(codes), ensure_ascii=False, separators=(",", ":"))


def derive_spot_diagnostic_evidence_codes(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    evidence = set(parse_spot_diagnostic_evidence_codes(snapshot.get("spot_diagnostic_evidence_codes")))
    evidence.difference_update(
        {
            "signal_below_threshold",
            "signal_below_configured_threshold_alarm_disabled",
            "signal_at_or_above_configured_threshold",
            "signalpc_present_comparator_unverified",
        }
    )
    if _truthy(snapshot.get("target_absent_verified")):
        evidence.add("target_absent_verified")
    if _truthy(snapshot.get("target_out_of_fov_evidence")):
        evidence.add("target_out_of_fov_evidence")
    if _truthy(snapshot.get("actuator_position_changed")):
        evidence.add("actuator_position_changed")
    if _truthy(snapshot.get("measurement_range_configured")):
        evidence.add("measurement_range_configured")
    if _truthy(snapshot.get("detector_below_measurement_range")):
        evidence.add("detector_below_measurement_range")
    if not _truthy(snapshot.get("low_signal_alarm_enabled")):
        evidence.discard("signal_below_threshold")

    alarmstatus = _alarmstatus_byte_or_none(snapshot.get("alarmstatus"))
    low_signal = derive_low_signal_evidence(
        alarmstatus=alarmstatus,
        signalpc=_signal_percent_or_none(snapshot.get("signalpc")),
        low_signal_alarm_enabled=_truthy(snapshot.get("low_signal_alarm_enabled")),
        low_signal_threshold_pc=_signal_percent_or_none(snapshot.get("low_signal_threshold_pc")),
        low_signal_comparator=_low_signal_comparator_or_none(snapshot.get("low_signal_comparator")),
        low_signal_comparator_verified=_truthy(snapshot.get("low_signal_comparator_verified")),
    )
    evidence.update(str(code) for code in low_signal["evidence_codes"])

    if alarmstatus is None and _alarmstatus_low_signal_active(snapshot.get("alarmstatus")):
        evidence.add("alarm_low_signal")

    actuator_scan_state = _normalize_token(snapshot.get("actuator_scan_state"))
    if actuator_scan_state in {"active", "in_progress", "moving", "scan", "scanning"}:
        evidence.add("actuator_scanning")

    peak_picker_off_mode = _normalize_token(snapshot.get("peak_picker_off_mode"))
    if _truthy(snapshot.get("peak_picker_enabled")) and peak_picker_off_mode in {
        "reset",
        "reset_output",
        "resetting",
        "off_mode_reset",
    }:
        evidence.add("peak_picker_off_mode_reset_configured")

    return tuple(sorted(code for code in evidence if code in SPOT_DIAGNOSTIC_EVIDENCE_CODES))


def parse_spot_diagnostic_evidence_codes(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    raw_values: Iterable[Any]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = []
            raw_values = parsed if isinstance(parsed, list) else []
        else:
            raw_values = re.split(r"[,;|\s]+", stripped)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        raw_values = value
    else:
        raw_values = ()
    return tuple(sorted({str(code) for code in raw_values if str(code) in SPOT_DIAGNOSTIC_EVIDENCE_CODES}))


def _has_diagnostic_payload(snapshot: Mapping[str, Any]) -> bool:
    return any(_diagnostic_value_present(snapshot.get(field)) for field in SPOT_DIAGNOSTIC_FACT_FIELDS)


def _diagnostic_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return bool(_text(value).strip())


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


def _signalpc_below_configured_threshold(snapshot: Mapping[str, Any]) -> Optional[bool]:
    signalpc = _signal_percent_or_none(snapshot.get("signalpc"))
    threshold = _signal_percent_or_none(snapshot.get("low_signal_threshold_pc"))
    comparator = _low_signal_comparator_or_none(snapshot.get("low_signal_comparator"))
    if signalpc is None or threshold is None or comparator is None:
        return None
    if comparator == "lt":
        return signalpc < threshold
    return signalpc <= threshold


def _signal_percent_or_none(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (float, int)):
        parsed = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            parsed = float(text)
        except ValueError:
            return None
    if not math.isfinite(parsed) or parsed < 0.0 or parsed > 100.0:
        return None
    return parsed


def _low_signal_comparator_or_none(value: Any) -> Optional[str]:
    raw = _text(value).strip().lower()
    if raw in LOW_SIGNAL_COMPARATORS:
        return raw
    if raw == "<":
        return "lt"
    if raw in {"<=", "le"}:
        return "lte"
    return None


def _alarmstatus_low_signal_active(value: Any) -> bool:
    alarmstatus = _alarmstatus_byte_or_none(value)
    if alarmstatus is not None:
        return bool(alarmstatus & LOW_SIGNAL_ALARM_BIT_MASK)
    normalized = _normalize_token(value)
    return "low_signal" in normalized or "lowsignal" in normalized


def _alarmstatus_byte_or_none(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = int(text, 0)
        except ValueError:
            return None
    if parsed < 0 or parsed > 255:
        return None
    return parsed


def _finite_non_negative_float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def _json_object(value: Any) -> dict[str, Any]:
    raw: object = value
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): item for key, item in raw.items()}


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).strip().lower()).strip("_")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
