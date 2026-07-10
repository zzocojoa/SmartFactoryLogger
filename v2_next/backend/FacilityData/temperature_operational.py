from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, cast

from backend.FacilityData.spot_observation import (
    SPOT_OVER_RANGE_DEVICE_STATUS_CODE,
    SPOT_UNDER_RANGE_DEVICE_STATUS_CODE,
    SpotPollStatus,
    SpotRawValidity,
    SpotSourceFreshness,
)
from backend.FacilityData.spot_low_signal import derive_low_signal_evidence
from backend.FacilityData.spot_diagnostics import evaluate_diagnostics_eligibility
from backend.FacilityData.temperature_state import (
    SpotCacheStatus,
    TemperatureStateDecision,
    TemperatureStateInput,
    TemperatureStatusShadow,
    TemperatureValueOrigin,
    derive_temperature_state,
)


TEMPERATURE_OPERATIONAL_RULE_VERSION = "temperature-operational-v3"
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
    temperature_value_origin: str = ""
    spot_device_status_code: Optional[str] = None
    spot_error_code: Optional[str] = None
    spot_effective_age_ms_at_row: Optional[float] = None
    spot_effective_value_age_ms_at_row: Optional[float] = None
    spot_row_freshness_threshold_ms: Optional[float] = None
    # Trusted phase input. Realtime callers must normalize externally supplied
    # pre_changeover_hold_candidate to stopped_after_production_candidate before calling.
    process_phase_candidate: str = "unknown"
    evidence_codes: Iterable[str] = ()
    state_decision: Optional[TemperatureStateDecision] = None
    alarmstatus: int | None = None
    signalpc: float | None = None
    low_signal_alarm_enabled: bool = False
    low_signal_threshold_pc: float | None = None
    low_signal_comparator: str | None = None
    low_signal_comparator_verified: bool = False
    diagnostics_current_poll_seq: int | None = None
    diagnostics_current_service_instance_id: str | None = None
    diagnostics_snapshot_id: str | None = None
    diagnostics_source_poll_seq: int | None = None
    diagnostics_capture_status: str = "missing"
    diagnostics_collection_mode: str = "async_fact_only"
    diagnostics_binding_status: str = "missing"
    diagnostics_age_ms: float | None = None
    diagnostics_max_age_ms: float | None = None
    diagnostics_missing_fields: tuple[str, ...] = ()
    diagnostics_field_status: Mapping[str, str] = field(default_factory=dict)
    peak_picker_enabled: bool = False
    peak_picker_off_mode: Optional[str] = None


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
    temperature_value_origin: str
    origin_decision_mismatch: bool
    cached_fallback_accepted: bool
    cached_fallback_rejected_reason: str
    diagnostics_cause_suppressed: bool
    diagnostics_cause_suppressed_reason: str


def derive_temperature_operational_fields(
    input_state: TemperatureOperationalInput,
) -> TemperatureOperationalDecision:
    row_freshness, clock_status = derive_spot_row_freshness(
        input_state.spot_effective_age_ms_at_row,
        threshold_ms=input_state.spot_row_freshness_threshold_ms or 9000.0,
    )
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

    effective_origin, origin_decision_mismatch = _effective_temperature_origin(input_state, state_decision)
    cached_fallback_accepted = _is_accepted_cached_fallback(
        input_state,
        state_decision,
        row_freshness,
        origin_decision_mismatch,
    )
    status, reason = _derive_status_and_reason(
        input_state,
        row_freshness,
        clock_status,
        effective_origin,
        cached_fallback_accepted,
    )
    output_origin = (
        effective_origin
        if status == TemperatureOutputStatus.VALID.value
        else TemperatureValueOrigin.NONE.value
    )
    cached_fallback_rejected_reason = _cached_fallback_rejected_reason(
        input_state,
        state_decision,
        row_freshness,
        clock_status,
        cached_fallback_accepted,
        origin_decision_mismatch,
    )
    expectedness = _derive_expectedness(status, input_state.process_phase_candidate)
    cause, confidence, evidence_json, diagnostics_suppressed, diagnostics_suppressed_reason = (
        _derive_under_range_cause(status, input_state)
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
        temperature_value_origin=output_origin,
        origin_decision_mismatch=origin_decision_mismatch,
        cached_fallback_accepted=cached_fallback_accepted,
        cached_fallback_rejected_reason=cached_fallback_rejected_reason,
        diagnostics_cause_suppressed=diagnostics_suppressed,
        diagnostics_cause_suppressed_reason=diagnostics_suppressed_reason,
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
    row_freshness: str,
    clock_status: str,
    effective_origin: str,
    cached_fallback_accepted: bool,
) -> tuple[str, str]:
    poll_status = _coerce_poll_status(input_state.poll_status)
    raw_validity = _coerce_raw_validity(input_state.raw_validity)
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
    if cached_fallback_accepted:
        return TemperatureOutputStatus.VALID.value, ""
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
    if effective_origin == TemperatureValueOrigin.CURRENT_OBSERVATION.value:
        return TemperatureOutputStatus.VALID.value, ""
    if raw_validity == SpotRawValidity.NOT_RECEIVED:
        return TemperatureOutputStatus.UNKNOWN.value, "not_attempted"
    if row_freshness == "unknown":
        return TemperatureOutputStatus.UNKNOWN.value, "unknown_freshness"
    return TemperatureOutputStatus.UNKNOWN.value, "unknown"


def _effective_temperature_origin(
    input_state: TemperatureOperationalInput,
    state_decision: TemperatureStateDecision,
) -> tuple[str, bool]:
    state_origin = state_decision.temperature_value_origin.value
    input_origin = str(input_state.temperature_value_origin or "").strip()
    mismatch = bool(input_origin and input_origin != state_origin)
    if mismatch:
        return TemperatureValueOrigin.NONE.value, True
    return state_origin, False


def _is_accepted_cached_fallback(
    input_state: TemperatureOperationalInput,
    state_decision: TemperatureStateDecision,
    row_freshness: str,
    origin_decision_mismatch: bool,
) -> bool:
    poll_status = _coerce_poll_status(input_state.poll_status)
    return (
        not origin_decision_mismatch
        and poll_status in {
            SpotPollStatus.TIMEOUT,
            SpotPollStatus.CONNECTION_ERROR,
            SpotPollStatus.HTTP_ERROR,
        }
        and input_state.source_freshness == SpotSourceFreshness.FRESH.value
        and state_decision.temperature_status_shadow == TemperatureStatusShadow.OK
        and state_decision.spot_cache_status == SpotCacheStatus.REUSED
        and state_decision.temperature_value_origin == TemperatureValueOrigin.CACHED_OBSERVATION
        and input_state.cache_fallback_allowed is True
        and input_state.has_ttl_valid_cache is True
        and row_freshness == "fresh"
    )


def _cached_fallback_rejected_reason(
    input_state: TemperatureOperationalInput,
    state_decision: TemperatureStateDecision,
    row_freshness: str,
    clock_status: str,
    accepted: bool,
    origin_decision_mismatch: bool,
) -> str:
    if accepted:
        return ""
    poll_status = _coerce_poll_status(input_state.poll_status)
    is_transport_failure = poll_status in {
        SpotPollStatus.TIMEOUT,
        SpotPollStatus.CONNECTION_ERROR,
        SpotPollStatus.HTTP_ERROR,
    }
    if state_decision.spot_cache_status == SpotCacheStatus.REUSED and origin_decision_mismatch:
        return "origin_decision_mismatch"
    if state_decision.spot_cache_status == SpotCacheStatus.REUSED and clock_status == "clock_anomaly":
        return "clock_anomaly"
    if state_decision.spot_cache_status == SpotCacheStatus.REUSED and (
        row_freshness == "stale" or input_state.source_freshness == SpotSourceFreshness.STALE.value
    ):
        return "stale_observation"
    if is_transport_failure and state_decision.spot_cache_status == SpotCacheStatus.AVAILABLE_NOT_USED:
        return "fallback_disallowed"
    if is_transport_failure and state_decision.spot_cache_status == SpotCacheStatus.EXPIRED:
        return "cache_expired"
    if state_decision.spot_cache_status == SpotCacheStatus.REUSED:
        return "state_contract_mismatch"
    return ""


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
            "production_stabilizing",
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
    low_signal_comparator_verified: bool = False,
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
        low_signal_comparator_verified=low_signal_comparator_verified,
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


_LOW_SIGNAL_DIAGNOSTIC_EVIDENCE_CODES = frozenset(
    {
        "alarm_low_signal",
        "signal_below_threshold",
        "signal_below_configured_threshold_alarm_disabled",
        "signal_at_or_above_configured_threshold",
        "signalpc_present_comparator_unverified",
        "signalpc_present_threshold_unknown",
    }
)


def _eligible_low_signal_inputs(
    input_state: TemperatureOperationalInput,
    raw_evidence: set[str],
) -> tuple[int | None, float | None, bool, str]:
    values_present = {
        "alarmstatus": input_state.alarmstatus is not None,
        "signalpc": input_state.signalpc is not None,
    }
    alarm_decision = evaluate_diagnostics_eligibility(
        collection_mode=input_state.diagnostics_collection_mode,
        capture_status=input_state.diagnostics_capture_status,
        binding_status=input_state.diagnostics_binding_status,
        diagnostics_age_ms=input_state.diagnostics_age_ms,
        diagnostics_max_age_ms=input_state.diagnostics_max_age_ms,
        field_status=input_state.diagnostics_field_status,
        values_present=values_present,
        required_fields=("alarmstatus",),
        snapshot_id=input_state.diagnostics_snapshot_id,
        source_poll_seq=input_state.diagnostics_source_poll_seq,
        current_poll_seq=input_state.diagnostics_current_poll_seq,
        current_service_instance_id=input_state.diagnostics_current_service_instance_id,
    )
    signal_decision = evaluate_diagnostics_eligibility(
        collection_mode=input_state.diagnostics_collection_mode,
        capture_status=input_state.diagnostics_capture_status,
        binding_status=input_state.diagnostics_binding_status,
        diagnostics_age_ms=input_state.diagnostics_age_ms,
        diagnostics_max_age_ms=input_state.diagnostics_max_age_ms,
        field_status=input_state.diagnostics_field_status,
        values_present=values_present,
        required_fields=("signalpc",),
        snapshot_id=input_state.diagnostics_snapshot_id,
        source_poll_seq=input_state.diagnostics_source_poll_seq,
        current_poll_seq=input_state.diagnostics_current_poll_seq,
        current_service_instance_id=input_state.diagnostics_current_service_instance_id,
    )
    alarm_material = input_state.alarmstatus is not None or "alarm_low_signal" in raw_evidence
    signal_material = input_state.signalpc is not None or bool(
        raw_evidence.intersection(_LOW_SIGNAL_DIAGNOSTIC_EVIDENCE_CODES - {"alarm_low_signal"})
    )
    suppression_reasons: list[str] = []
    if alarm_material and not alarm_decision.eligible:
        suppression_reasons.append(alarm_decision.reason)
    if signal_material and not signal_decision.eligible:
        suppression_reasons.append(signal_decision.reason)
    suppressed = bool(suppression_reasons)
    return (
        input_state.alarmstatus if alarm_decision.eligible else None,
        input_state.signalpc if signal_decision.eligible else None,
        suppressed,
        suppression_reasons[0] if suppression_reasons else "",
    )


def _derive_under_range_cause(
    status: str,
    input_state: TemperatureOperationalInput,
) -> tuple[str, Optional[float], str, bool, str]:
    if status != TemperatureOutputStatus.UNDER_RANGE.value:
        return "", None, "", False, ""
    evidence = set(str(code) for code in input_state.evidence_codes if str(code))
    eligible_alarmstatus, eligible_signalpc, diagnostics_suppressed, diagnostics_reason = (
        _eligible_low_signal_inputs(input_state, evidence)
    )
    evidence.difference_update(_LOW_SIGNAL_DIAGNOSTIC_EVIDENCE_CODES)
    if diagnostics_suppressed:
        evidence.add("diagnostics_missing_or_stale")
    phase_evidence: list[str] = []
    if input_state.process_phase_candidate in {
        "setup_candidate",
        "setup_alignment_candidate",
        "pre_changeover_hold_candidate",
        "die_change_candidate",
        "changeover_candidate",
    }:
        phase_evidence.append("phase_setup_candidate")
        evidence.add("phase_setup_candidate")

    config_aware = derive_under_range_cause_candidate(
        alarmstatus=eligible_alarmstatus,
        signalpc=eligible_signalpc,
        low_signal_alarm_enabled=input_state.low_signal_alarm_enabled,
        low_signal_threshold_pc=input_state.low_signal_threshold_pc,
        low_signal_comparator=input_state.low_signal_comparator,
        low_signal_comparator_verified=input_state.low_signal_comparator_verified,
        phase_evidence_codes=phase_evidence,
        peak_picker_enabled=input_state.peak_picker_enabled,
        peak_picker_off_mode=input_state.peak_picker_off_mode,
    )
    config_aware_evidence = cast(Iterable[object], config_aware["temperature_cause_evidence_codes"])
    evidence.update(str(code) for code in config_aware_evidence)
    config_aware_cause = str(config_aware["temperature_under_range_cause_candidate"])
    config_aware_confidence = cast(float, config_aware["temperature_cause_confidence"])
    if config_aware_cause != "unknown":
        return (
            config_aware_cause,
            config_aware_confidence,
            _json_list(sorted(evidence)),
            diagnostics_suppressed,
            diagnostics_reason,
        )

    sorted_evidence = sorted(evidence)
    if "target_absent_verified" in evidence or "target_out_of_fov_evidence" in evidence:
        return (
            "target_out_of_fov_candidate",
            0.6,
            _json_list(sorted_evidence),
            diagnostics_suppressed,
            diagnostics_reason,
        )
    if "actuator_scanning" in evidence or "actuator_position_changed" in evidence:
        return (
            "alignment_change_candidate",
            0.55,
            _json_list(sorted_evidence),
            diagnostics_suppressed,
            diagnostics_reason,
        )
    if {
        "measurement_range_configured",
        "detector_below_measurement_range",
    }.issubset(evidence):
        return (
            "below_measurement_range_candidate",
            0.65,
            _json_list(sorted_evidence),
            diagnostics_suppressed,
            diagnostics_reason,
        )
    return (
        "unknown",
        0.0,
        _json_list(sorted_evidence),
        diagnostics_suppressed,
        diagnostics_reason,
    )


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
