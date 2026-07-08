from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from backend.FacilityData.spot_low_signal import (
    LOW_SIGNAL_ALARM_BIT,
    LOW_SIGNAL_COMPARATORS,
    derive_low_signal_evidence,
)


SPOT_OBSERVATION_FACT_SCHEMA_VERSION = "1.2.1"
SPOT_OBSERVATION_FACT_FILENAME = "spot_observation_fact.csv"
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
SPOT_OBSERVATION_FACT_COLUMNS = [
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
SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS = {
    "alarmstatus": "alarmstatus_nonblank_count",
    "signalpc": "signalpc_nonblank_count",
    "d1temperature": "d1temperature_nonblank_count",
    "d2temperature": "d2temperature_nonblank_count",
    "e1out": "e1out_nonblank_count",
    "e2out": "e2out_nonblank_count",
}


@dataclass
class SpotObservationFactWriter:
    output_path: Path
    spool_path: Optional[Path] = None
    failure_count: int = 0
    _seen_keys: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._load_seen_keys_from_output()

    def write_fact(self, snapshot: Mapping[str, Any]) -> Optional[dict[str, str]]:
        fact = build_spot_observation_fact(snapshot)
        key = fact["spot_observation_key"]
        if not key or key in self._seen_keys:
            return None
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._flush_spool()
            self._append_fact(fact)
            self._seen_keys.add(key)
            return fact
        except Exception:
            self.failure_count += 1
            self._spool_fact(fact)
            return None

    def _append_fact(self, fact: Mapping[str, str]) -> None:
        write_header = self._prepare_output_file_for_append()
        with self.output_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(fact)

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
        archive_path = self._next_schema_mismatch_archive_path()
        self.output_path.rename(archive_path)

    def _next_schema_mismatch_archive_path(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        suffix = self.output_path.suffix or ".csv"
        archive_stem = f"{self.output_path.stem}.{timestamp}.schema-mismatch"
        candidate = self.output_path.with_name(f"{archive_stem}{suffix}")
        for index in range(1, 1000):
            if not candidate.exists():
                return candidate
            candidate = self.output_path.with_name(f"{archive_stem}.{index}{suffix}")
        raise FileExistsError(f"Could not allocate archive path for {self.output_path}")

    def _flush_spool(self) -> None:
        spool_path = self._effective_spool_path()
        if not spool_path.exists() or spool_path.stat().st_size == 0:
            return
        pending: list[dict[str, str]] = []
        with spool_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, dict):
                    pending.append({column: _text(raw.get(column)) for column in SPOT_OBSERVATION_FACT_COLUMNS})
        for fact in pending:
            key = fact["spot_observation_key"]
            if key and key not in self._seen_keys:
                self._append_fact(fact)
                self._seen_keys.add(key)
        spool_path.unlink(missing_ok=True)

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
        if not spool_path.exists() or spool_path.stat().st_size == 0:
            return 0
        try:
            with spool_path.open("r", encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        except OSError:
            return 0

    def _load_seen_keys_from_output(self) -> None:
        if not self.output_path.exists() or self.output_path.stat().st_size == 0:
            return
        try:
            with self.output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if list(reader.fieldnames or []) != SPOT_OBSERVATION_FACT_COLUMNS:
                    return
                for row in reader:
                    key = _text(row.get("spot_observation_key")).strip()
                    if key:
                        self._seen_keys.add(key)
        except (OSError, UnicodeError, csv.Error):
            return


def build_spot_observation_fact_manifest(
    *,
    fact_path: Path,
    enabled: bool,
    write_failure_count: int = 0,
    spool_pending_count: int | None = None,
    realtime_rows: Iterable[Mapping[str, Any]] | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    summary = summarize_spot_observation_fact(
        fact_path=fact_path,
        realtime_rows=realtime_rows,
    )
    return {
        "enabled": bool(enabled),
        "schema_version": SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
        "path": path or fact_path.name,
        "row_count": summary["row_count"],
        "distinct_observation_key_count": summary["distinct_observation_key_count"],
        "first_poll_seq": summary["first_poll_seq"],
        "last_poll_seq": summary["last_poll_seq"],
        "poll_seq_gap_count": summary["poll_seq_gap_count"],
        "sha256": summary["sha256"],
        "write_failure_count": int(write_failure_count),
        "spool_pending_count": (
            int(spool_pending_count)
            if spool_pending_count is not None
            else _spool_pending_count(fact_path.with_name(f"{fact_path.name}.failed.jsonl"))
        ),
        "required_columns": list(SPOT_OBSERVATION_FACT_COLUMNS),
        "link_coverage": summary["link_coverage"],
        "diagnostic_field_coverage": summary["diagnostic_field_coverage"],
    }


def summarize_spot_observation_fact(
    *,
    fact_path: Path,
    realtime_rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    header, rows = _read_fact_rows(fact_path)
    keys = [_text(row.get("spot_observation_key")).strip() for row in rows]
    distinct_keys = {key for key in keys if key}
    poll_sequences = sorted(
        {
            parsed
            for row in rows
            for parsed in (_positive_int_or_none(row.get("spot_poll_seq")),)
            if parsed is not None
        }
    )
    first_poll_seq = poll_sequences[0] if poll_sequences else None
    last_poll_seq = poll_sequences[-1] if poll_sequences else None
    poll_seq_gap_count = 0
    if first_poll_seq is not None and last_poll_seq is not None:
        poll_seq_gap_count = (last_poll_seq - first_poll_seq + 1) - len(set(poll_sequences))
    return {
        "header": header,
        "row_count": len(rows),
        "distinct_observation_key_count": len(distinct_keys),
        "first_poll_seq": first_poll_seq,
        "last_poll_seq": last_poll_seq,
        "poll_seq_gap_count": max(0, poll_seq_gap_count),
        "sha256": _file_sha256(fact_path),
        "link_coverage": _link_coverage(realtime_rows, distinct_keys),
        "diagnostic_field_coverage": {
            manifest_key: sum(1 for row in rows if _text(row.get(fact_column)).strip())
            for fact_column, manifest_key in SPOT_OBSERVATION_FACT_MANIFEST_DIAGNOSTIC_FIELDS.items()
        },
    }


def _read_fact_rows(fact_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not fact_path.exists() or fact_path.stat().st_size == 0:
        return ([], [])
    try:
        with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return (list(reader.fieldnames or []), list(reader))
    except (OSError, UnicodeError, csv.Error):
        return ([], [])


def _file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _spool_pending_count(spool_path: Path) -> int:
    if not spool_path.exists() or spool_path.stat().st_size == 0:
        return 0
    try:
        with spool_path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def _link_coverage(
    realtime_rows: Iterable[Mapping[str, Any]] | None,
    fact_keys: set[str],
) -> dict[str, Any]:
    if realtime_rows is None:
        return {
            "realtime_rows_with_observation_key": 0,
            "linked_rows": 0,
            "missing_fact_key_rows": 0,
            "coverage_pct": 0.0,
        }
    realtime_keys = [
        _text(row.get("spot_observation_key")).strip()
        for row in realtime_rows
        if _text(row.get("spot_observation_key")).strip()
    ]
    linked_rows = sum(1 for key in realtime_keys if key in fact_keys)
    missing_rows = len(realtime_keys) - linked_rows
    coverage_pct = (linked_rows / len(realtime_keys) * 100.0) if realtime_keys else 0.0
    return {
        "realtime_rows_with_observation_key": len(realtime_keys),
        "linked_rows": linked_rows,
        "missing_fact_key_rows": missing_rows,
        "coverage_pct": round(coverage_pct, 6),
    }


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


def build_spot_observation_fact(snapshot: Mapping[str, Any]) -> dict[str, str]:
    completed_at = _text(snapshot.get("spot_last_poll_completed_at"))
    diagnostics_present = _has_diagnostic_payload(snapshot)
    diagnostics_capture_status = _text(snapshot.get("diagnostics_capture_status"))
    if not diagnostics_capture_status:
        diagnostics_capture_status = "same_response" if diagnostics_present else "missing"
    diagnostics_captured_at = _text(snapshot.get("diagnostics_captured_at")) or completed_at
    diagnostics_age_ms = _text(snapshot.get("diagnostics_age_ms"))
    if diagnostics_present and not diagnostics_age_ms:
        diagnostics_age_ms = "0.0"
    evidence_codes = encode_spot_diagnostic_evidence_codes(snapshot)
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
        "spot_diagnostic_evidence_codes": evidence_codes,
        "alarmstatus": _text(snapshot.get("alarmstatus")),
        "signalpc": _text(snapshot.get("signalpc")),
        "d1temperature": _text(snapshot.get("d1temperature")),
        "d2temperature": _text(snapshot.get("d2temperature")),
        "e1out": _text(snapshot.get("e1out")),
        "e2out": _text(snapshot.get("e2out")),
        "itemperature": _text(snapshot.get("itemperature")),
        "appnumber": _text(snapshot.get("appnumber")),
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


def _normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).strip().lower()).strip("_")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
