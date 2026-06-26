from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from backend.FacilityData.spot_observation import (
    SPOT_OVER_RANGE_DEVICE_STATUS_CODE,
    SPOT_UNDER_RANGE_DEVICE_STATUS_CODE,
    SpotPollStatus,
    SpotRawValidity,
    SpotSourceFreshness,
)
from backend.FacilityData.spot_low_signal import derive_low_signal_evidence
from backend.FacilityData.temperature_state import (
    TemperatureStateDecision,
    TemperatureStateInput,
    TemperatureValueOrigin,
    derive_temperature_state,
)


TEMPERATURE_OPERATIONAL_RULE_VERSION = "temperature-operational-v1"
SPOT_ROW_FRESHNESS_RULE_VERSION = "spot-row-freshness-v1"


class TemperatureOutputStatus(str, Enum):
    VALID = "valid"
    UNDER_RANGE = "under_range"
    OVER_RANGE = "over_range"
    STALE = "stale"
    SOURCE_ERROR = "source_error"
    STARTUP_PENDING = "startup_pending"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TemperatureOperationalInput:
    poll_status: str = "not_attempted"
    raw_validity: str = "not_received"
    source_freshness: str = "unknown"
    cache_fallback_allowed: bool = False
    has_ttl_valid_cache: bool = False
    has_previous_valid_value: bool = False
    first_poll_completed: bool = True
    temperature_value_origin: str = "none"
    spot_device_status_code: Optional[str] = None
    spot_error_code: Optional[str] = None
    spot_effective_age_ms_at_row: Optional[float] = None
    spot_effective_value_age_ms_at_row: Optional[float] = None
    process_phase_candidate: str = "unknown"
    evidence_codes: Iterable[str] = ()
    state_decision: Optional[TemperatureStateDecision] = None


@dataclass(frozen=True)
class TemperatureOperationalDecision:
    temperature_output_status: str
    temperature_unavailable_reason: str
    temperature_expectedness_candidate: str
    temperature_under_range_cause_candidate: str
    temperature_cause_confidence: Optional[float]
    temperature_cause_evidence_codes: str
    spot_effective_age_ms_at_row: Optional[float]
    spot_effective_freshness_at_row: str
    spot_effective_value_age_ms_at_row: Optional[float]
    spot_row_age_clock_status: str


def derive_temperature_operational_fields(
    input_state: TemperatureOperationalInput,
) -> TemperatureOperationalDecision:
    row_freshness, clock_status = derive_spot_row_freshness(input_state.spot_effective_age_ms_at_row)
    state_decision = input_state.state_decision or derive_temperature_state(
        TemperatureStateInput(
            poll_status=_coerce_poll_status(input_state.poll_status),
            raw_validity=_coerce_raw_validity(input_state.raw_validity),
            source_freshness=_coerce_source_freshness(input_state.source_freshness),
            cache_fallback_allowed=input_state.cache_fallback_allowed,
            has_ttl_valid_cache=input_state.has_ttl_valid_cache,
            has_previous_valid_value=input_state.has_previous_valid_value,
            first_poll_completed=input_state.first_poll_completed,
        )
    )

    status, reason = _derive_status_and_reason(input_state, state_decision, row_freshness, clock_status)
    expectedness = _derive_expectedness(status, input_state.process_phase_candidate)
    cause, confidence, evidence_json = _derive_under_range_cause(
        status,
        input_state.process_phase_candidate,
        input_state.evidence_codes,
    )
    return TemperatureOperationalDecision(
        temperature_output_status=status,
        temperature_unavailable_reason=reason,
        temperature_expectedness_candidate=expectedness,
        temperature_under_range_cause_candidate=cause,
        temperature_cause_confidence=confidence,
        temperature_cause_evidence_codes=evidence_json,
        spot_effective_age_ms_at_row=input_state.spot_effective_age_ms_at_row,
        spot_effective_freshness_at_row=row_freshness,
        spot_effective_value_age_ms_at_row=input_state.spot_effective_value_age_ms_at_row,
        spot_row_age_clock_status=clock_status,
    )


def derive_spot_row_freshness(age_ms: Optional[float], *, threshold_ms: float = 9000.0) -> tuple[str, str]:
    if age_ms is None:
        return "unknown", "unknown"
    try:
        age = float(age_ms)
    except (TypeError, ValueError):
        return "unknown", "unknown"
    if age < 0:
        return "unknown", "clock_anomaly"
    if age > threshold_ms:
        return "stale", "ok"
    return "fresh", "ok"


def _derive_status_and_reason(
    input_state: TemperatureOperationalInput,
    state_decision: TemperatureStateDecision,
    row_freshness: str,
    clock_status: str,
) -> tuple[str, str]:
    poll_status = _coerce_poll_status(input_state.poll_status)
    raw_validity = _coerce_raw_validity(input_state.raw_validity)
    origin = input_state.temperature_value_origin or state_decision.temperature_value_origin.value
    if not input_state.first_poll_completed or poll_status == SpotPollStatus.NOT_ATTEMPTED:
        return TemperatureOutputStatus.STARTUP_PENDING.value, "startup_pending"
    if clock_status == "clock_anomaly":
        return TemperatureOutputStatus.UNKNOWN.value, "unknown_freshness"
    if row_freshness == "stale" or input_state.source_freshness == SpotSourceFreshness.STALE.value:
        return TemperatureOutputStatus.STALE.value, "stale_observation"
    if input_state.spot_device_status_code == SPOT_UNDER_RANGE_DEVICE_STATUS_CODE:
        return TemperatureOutputStatus.UNDER_RANGE.value, "under_range"
    if input_state.spot_device_status_code == SPOT_OVER_RANGE_DEVICE_STATUS_CODE:
        return TemperatureOutputStatus.OVER_RANGE.value, "over_range"
    if poll_status == SpotPollStatus.TIMEOUT:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "timeout"
    if poll_status == SpotPollStatus.CONNECTION_ERROR:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "connection_error"
    if poll_status == SpotPollStatus.HTTP_ERROR:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "http_error"
    if poll_status == SpotPollStatus.CONFIG_MISSING:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "config_missing"
    if raw_validity == SpotRawValidity.PARSE_ERROR:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "parse_error"
    if raw_validity == SpotRawValidity.EMPTY_BODY:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "empty_body"
    if raw_validity == SpotRawValidity.OUT_OF_RANGE:
        return TemperatureOutputStatus.SOURCE_ERROR.value, "numeric_out_of_range"
    if origin in {
        TemperatureValueOrigin.CURRENT_OBSERVATION.value,
        TemperatureValueOrigin.CACHED_OBSERVATION.value,
    }:
        return TemperatureOutputStatus.VALID.value, ""
    if raw_validity == SpotRawValidity.NOT_RECEIVED:
        return TemperatureOutputStatus.UNKNOWN.value, "not_attempted"
    if row_freshness == "unknown":
        return TemperatureOutputStatus.UNKNOWN.value, "unknown_freshness"
    return TemperatureOutputStatus.UNKNOWN.value, "unknown"


def _derive_expectedness(status: str, phase: str) -> str:
    if status == TemperatureOutputStatus.VALID.value:
        return ""
    if status in {
        TemperatureOutputStatus.STALE.value,
        TemperatureOutputStatus.SOURCE_ERROR.value,
        TemperatureOutputStatus.STARTUP_PENDING.value,
        TemperatureOutputStatus.UNKNOWN.value,
    }:
        return "unknown"
    if status == TemperatureOutputStatus.OVER_RANGE.value:
        return "unexpected_candidate"
    if status == TemperatureOutputStatus.UNDER_RANGE.value:
        if phase in {
            "setup_candidate",
            "setup_alignment_candidate",
            "pre_changeover_hold_candidate",
            "die_change_candidate",
            "changeover_candidate",
        }:
            return "expected_candidate"
        if phase == "production_stable":
            return "unexpected_candidate"
    return "unknown"


def derive_under_range_cause_candidate(
    *,
    alarmstatus: int | None,
    signalpc: float | None,
    low_signal_alarm_enabled: bool,
    low_signal_threshold_pc: float | None,
    low_signal_comparator: str | None,
    phase_evidence_codes: Iterable[str] = (),
    peak_picker_enabled: bool = False,
    peak_picker_off_mode: Optional[str] = None,
) -> dict[str, object]:
    low_signal = derive_low_signal_evidence(
        alarmstatus=alarmstatus,
        signalpc=signalpc,
        low_signal_alarm_enabled=low_signal_alarm_enabled,
        low_signal_threshold_pc=low_signal_threshold_pc,
        low_signal_comparator=low_signal_comparator,
    )
    evidence = [str(code) for code in low_signal["evidence_codes"]]
    evidence.extend(str(code) for code in phase_evidence_codes if str(code))

    if "alarm_low_signal" in evidence:
        return {
            "temperature_under_range_cause_candidate": "low_signal_candidate",
            "temperature_cause_confidence": 0.85,
            "temperature_cause_evidence_codes": sorted(set(evidence)),
        }
    if low_signal["numeric_low_signal"] is True and low_signal_alarm_enabled is True:
        return {
            "temperature_under_range_cause_candidate": "low_signal_candidate",
            "temperature_cause_confidence": 0.65,
            "temperature_cause_evidence_codes": sorted(set(evidence)),
        }
    if peak_picker_enabled and _is_peak_picker_reset_mode(peak_picker_off_mode):
        evidence.append("peak_picker_off_mode_reset_configured")
        return {
            "temperature_under_range_cause_candidate": "peak_picker_reset_candidate",
            "temperature_cause_confidence": 0.75,
            "temperature_cause_evidence_codes": sorted(set(evidence)),
        }
    return {
        "temperature_under_range_cause_candidate": "unknown",
        "temperature_cause_confidence": 0.0,
        "temperature_cause_evidence_codes": sorted(set(evidence)),
    }


def _derive_under_range_cause(
    status: str,
    phase: str,
    evidence_codes: Iterable[str],
) -> tuple[str, Optional[float], str]:
    if status != TemperatureOutputStatus.UNDER_RANGE.value:
        return "", None, ""
    evidence = set(str(code) for code in evidence_codes if str(code))
    if phase in {
        "setup_candidate",
        "setup_alignment_candidate",
        "pre_changeover_hold_candidate",
        "die_change_candidate",
        "changeover_candidate",
    }:
        evidence.add("phase_setup_candidate")
    sorted_evidence = sorted(evidence)
    if "alarm_low_signal" in evidence:
        return "low_signal_candidate", 0.85, _json_list(sorted_evidence)
    if "signal_below_threshold" in evidence:
        return "low_signal_candidate", 0.65, _json_list(sorted_evidence)
    if "peak_picker_off_mode_reset_configured" in evidence:
        return "peak_picker_reset_candidate", 0.75, _json_list(sorted_evidence)
    if "target_absent_verified" in evidence or "target_out_of_fov_evidence" in evidence:
        return "target_out_of_fov_candidate", 0.6, _json_list(sorted_evidence)
    if "actuator_scanning" in evidence or "actuator_position_changed" in evidence:
        return "alignment_change_candidate", 0.55, _json_list(sorted_evidence)
    if {
        "measurement_range_configured",
        "detector_below_measurement_range",
    }.issubset(evidence):
        return "below_measurement_range_candidate", 0.65, _json_list(sorted_evidence)
    return "unknown", 0.0, _json_list(sorted_evidence)


def _is_peak_picker_reset_mode(value: Optional[str]) -> bool:
    normalized = "" if value is None else str(value).strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {"reset", "reset_output", "resetting", "off_mode_reset"}


def _json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _coerce_poll_status(value: str) -> SpotPollStatus:
    try:
        return SpotPollStatus(value)
    except ValueError:
        return SpotPollStatus.NOT_ATTEMPTED


def _coerce_raw_validity(value: str) -> SpotRawValidity:
    try:
        return SpotRawValidity(value)
    except ValueError:
        return SpotRawValidity.NOT_EVALUATED


def _coerce_source_freshness(value: str) -> SpotSourceFreshness:
    try:
        return SpotSourceFreshness(value)
    except ValueError:
        return SpotSourceFreshness.UNKNOWN
