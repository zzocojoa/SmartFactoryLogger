from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


SPOT_OBSERVATION_FACT_SCHEMA_VERSION = "1.0.0"
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
    "alarmstatus",
    "signalpc",
    "d1temperature",
    "d2temperature",
    "e1out",
    "e2out",
    "appnumber",
    "instrument_info",
    "peak_picker_enabled",
    "peak_picker_threshold",
    "peak_picker_off_delay_ms",
    "peak_picker_off_mode",
    "actuator_position",
    "actuator_scan_state",
    "actuator_peak_found",
]


@dataclass
class SpotObservationFactWriter:
    output_path: Path
    spool_path: Optional[Path] = None
    failure_count: int = 0
    _seen_keys: set[str] = field(default_factory=set)

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
        write_header = not self.output_path.exists() or self.output_path.stat().st_size == 0
        with self.output_path.open("a", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(fact)

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


def build_spot_observation_key(snapshot: Mapping[str, Any]) -> str:
    service_id = _text(snapshot.get("spot_service_instance_id"))
    poll_seq = _text(snapshot.get("spot_poll_seq"))
    if not service_id or not poll_seq:
        return ""
    return f"{service_id}:{poll_seq}"


def build_spot_observation_fact(snapshot: Mapping[str, Any]) -> dict[str, str]:
    completed_at = _text(snapshot.get("spot_last_poll_completed_at"))
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
        "diagnostics_captured_at": completed_at,
        "diagnostics_capture_status": "missing",
        "diagnostics_age_ms": "",
        "alarmstatus": "",
        "signalpc": "",
        "d1temperature": "",
        "d2temperature": "",
        "e1out": "",
        "e2out": "",
        "appnumber": "",
        "instrument_info": "",
        "peak_picker_enabled": "",
        "peak_picker_threshold": "",
        "peak_picker_off_delay_ms": "",
        "peak_picker_off_mode": "",
        "actuator_position": "",
        "actuator_scan_state": "",
        "actuator_peak_found": "",
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
