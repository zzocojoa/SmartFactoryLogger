from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


SPOT_DIAGNOSTIC_OUTPUT_FIELDS = (
    "alarmstatus",
    "signalpc",
    "d1temperature",
    "d2temperature",
    "e1out",
    "e2out",
    "itemperature",
    "appnumber",
)
DIAGNOSTICS_MAX_AGE_FLOOR_MS = 3000.0
DIAGNOSTICS_COLLECTION_MODES = frozenset(
    {"async_fact_only", "async_same_poll", "atomic_output_json"}
)
DIAGNOSTICS_CAUSAL_COLLECTION_MODES = frozenset({"async_same_poll", "atomic_output_json"})
DIAGNOSTICS_CAPTURE_STATUSES = frozenset(
    {"same_response", "async_complete", "async_partial", "missing", "error"}
)
DIAGNOSTICS_CAUSAL_CAPTURE_STATUSES = frozenset(
    {"same_response", "async_complete", "async_partial"}
)
DIAGNOSTICS_BINDING_STATUSES = frozenset(
    {"same_poll", "previous_poll", "future_clock", "unbound", "missing"}
)
DIAGNOSTICS_FIELD_STATUSES = frozenset(
    {"success", "missing", "http_error", "timeout", "parse_error", "not_requested"}
)
DIAGNOSTICS_SUPPRESSION_REASONS = frozenset(
    {
        "fact_only",
        "unsupported_collection_mode",
        "capture_missing",
        "capture_error",
        "snapshot_identity_missing",
        "binding_missing",
        "previous_poll",
        "future_clock",
        "unbound",
        "age_missing",
        "stale",
        "required_field_missing",
        "required_field_failed",
    }
)


@dataclass(frozen=True)
class SpotPollContext:
    service_instance_id: str
    poll_seq: int
    started_at_epoch: float
    started_monotonic: float


@dataclass(frozen=True)
class DiagnosticSnapshot:
    snapshot_id: str
    source_poll_seq: int | None
    captured_at: str
    captured_at_epoch: float
    captured_monotonic: float | None
    capture_status: str
    collection_mode: str
    source: str
    values: Mapping[str, object]
    field_status: Mapping[str, str]
    missing_fields: tuple[str, ...]

    def as_payload(self, *, diagnostics_max_age_ms: float) -> dict[str, Any]:
        return {
            "diagnostics_snapshot_id": self.snapshot_id,
            "diagnostics_source_poll_seq": self.source_poll_seq,
            "diagnostics_captured_at": self.captured_at,
            "_diagnostics_captured_at_epoch": self.captured_at_epoch,
            "_diagnostics_captured_monotonic": self.captured_monotonic,
            "diagnostics_capture_status": self.capture_status,
            "diagnostics_collection_mode": self.collection_mode,
            "diagnostics_source": self.source,
            "diagnostics_field_status": dict(self.field_status),
            "diagnostics_missing_fields": list(self.missing_fields),
            "diagnostics_max_age_ms": diagnostics_max_age_ms,
            **dict(self.values),
        }


@dataclass(frozen=True)
class DiagnosticsEligibilityDecision:
    eligible: bool
    reason: str = ""


def evaluate_diagnostics_eligibility(
    *,
    collection_mode: str,
    capture_status: str,
    binding_status: str,
    diagnostics_age_ms: float | None,
    diagnostics_max_age_ms: float | None,
    field_status: Mapping[str, str],
    values_present: Mapping[str, bool],
    required_fields: Sequence[str],
    snapshot_id: str | None,
    source_poll_seq: int | None,
    current_poll_seq: int | None = None,
    current_service_instance_id: str | None = None,
) -> DiagnosticsEligibilityDecision:
    if collection_mode == "async_fact_only":
        return DiagnosticsEligibilityDecision(False, "fact_only")
    if collection_mode not in DIAGNOSTICS_CAUSAL_COLLECTION_MODES:
        return DiagnosticsEligibilityDecision(False, "unsupported_collection_mode")
    if capture_status == "missing":
        return DiagnosticsEligibilityDecision(False, "capture_missing")
    if capture_status == "error" or capture_status not in DIAGNOSTICS_CAUSAL_CAPTURE_STATUSES:
        return DiagnosticsEligibilityDecision(False, "capture_error")
    if not _snapshot_identity_is_valid(snapshot_id, current_service_instance_id) or not _is_positive_int(
        source_poll_seq
    ):
        return DiagnosticsEligibilityDecision(False, "snapshot_identity_missing")
    if _is_positive_int(current_poll_seq) and source_poll_seq != current_poll_seq:
        reason = "previous_poll" if int(source_poll_seq) < int(current_poll_seq) else "future_clock"
        return DiagnosticsEligibilityDecision(False, reason)
    if binding_status == "previous_poll":
        return DiagnosticsEligibilityDecision(False, "previous_poll")
    if binding_status == "future_clock":
        return DiagnosticsEligibilityDecision(False, "future_clock")
    if binding_status == "unbound":
        return DiagnosticsEligibilityDecision(False, "unbound")
    if binding_status != "same_poll":
        return DiagnosticsEligibilityDecision(False, "binding_missing")
    if diagnostics_age_ms is None or diagnostics_max_age_ms is None:
        return DiagnosticsEligibilityDecision(False, "age_missing")
    if not math.isfinite(diagnostics_age_ms) or diagnostics_age_ms < 0:
        return DiagnosticsEligibilityDecision(False, "future_clock")
    if not math.isfinite(diagnostics_max_age_ms) or diagnostics_max_age_ms < 0:
        return DiagnosticsEligibilityDecision(False, "age_missing")
    if diagnostics_age_ms > diagnostics_max_age_ms:
        return DiagnosticsEligibilityDecision(False, "stale")
    for name in required_fields:
        if field_status.get(name) != "success":
            return DiagnosticsEligibilityDecision(False, "required_field_failed")
        if not values_present.get(name, False):
            return DiagnosticsEligibilityDecision(False, "required_field_missing")
    return DiagnosticsEligibilityDecision(True)


def configured_diagnostics_max_age_ms(refresh_interval: object) -> float:
    try:
        interval_sec = float(refresh_interval or 1.0)
    except (TypeError, ValueError):
        interval_sec = 1.0
    if not math.isfinite(interval_sec) or interval_sec <= 0:
        interval_sec = 1.0
    return max(DIAGNOSTICS_MAX_AGE_FLOOR_MS, interval_sec * 2.0 * 1000.0)


def parse_diagnostics_field_status(value: Any) -> dict[str, str]:
    raw: object = value
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, Mapping):
        return {}
    parsed: dict[str, str] = {}
    for key, status in raw.items():
        field_name = str(key).strip()
        normalized_status = str(status).strip().lower()
        if field_name in SPOT_DIAGNOSTIC_OUTPUT_FIELDS and normalized_status in DIAGNOSTICS_FIELD_STATUSES:
            parsed[field_name] = normalized_status
    return parsed


def parse_diagnostics_missing_fields(value: Any) -> tuple[str, ...]:
    raw: object = value
    if isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return ()
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(
        sorted(
            {
                str(item).strip()
                for item in raw
                if str(item).strip() in SPOT_DIAGNOSTIC_OUTPUT_FIELDS
            }
        )
    )


def _is_positive_int(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _snapshot_identity_is_valid(
    snapshot_id: str | None,
    current_service_instance_id: str | None,
) -> bool:
    text = str(snapshot_id or "").strip()
    service_id, separator, sequence = text.partition(":diag:")
    if not separator or not service_id or ":" in service_id or any(char.isspace() for char in service_id):
        return False
    if not _is_positive_int(sequence):
        return False
    expected_service_id = str(current_service_instance_id or "").strip()
    return not expected_service_id or service_id == expected_service_id
