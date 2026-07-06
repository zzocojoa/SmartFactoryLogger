from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend import constants


PROCESS_PHASE_RULE_VERSION = "process-phase-candidate-v3"

PROCESS_PHASE_CANDIDATES = {
    "production_stable",
    "setup_candidate",
    "pre_changeover_hold_candidate",
    "stopped_after_production_candidate",
    "possible_pre_changeover_hold",
    "die_change_candidate",
    "setup_alignment_candidate",
    "changeover_candidate",
    "production_stabilizing",
    "idle_candidate",
    "unknown",
}

_LOW_COUNT_MAX = 2
_STABILIZING_COUNT_MAX = 3
_COUNT_HELD_FOR_CHANGEOVER_SEC = 30.0


@dataclass(frozen=True)
class ProcessPhaseInput:
    speed: Optional[float] = None
    press: Optional[float] = None
    count: Optional[int] = None
    extruder_process_state_online: Optional[str] = None
    product_no: Optional[str] = None
    mold_no: Optional[str] = None
    previous_product_no: Optional[str] = None
    previous_mold_no: Optional[str] = None
    count_held_sec: Optional[float] = None
    recent_production_motion: bool = False
    operator_die_change_marker: bool = False
    actuator_scanning: bool = False


@dataclass(frozen=True)
class ProcessPhaseDecision:
    process_phase_candidate: str
    process_phase_rule_version: str = PROCESS_PHASE_RULE_VERSION
    phase_confirmation_state: str = "realtime_candidate"
    process_segment_id: str = ""
    changeover_candidate_id: str = ""


def derive_process_phase_candidate(input_state: ProcessPhaseInput) -> ProcessPhaseDecision:
    """Derive realtime process phase without SPOT temperature or future context."""

    speed = _to_float(input_state.speed)
    press = _to_float(input_state.press)
    count = _to_int(input_state.count)
    online_state = (input_state.extruder_process_state_online or "unknown").strip() or "unknown"
    low_speed = speed is not None and speed <= constants.SPEED_IDLE_MAX
    low_press = press is not None and press <= constants.PRESS_IDLE_MAX
    low_count_startup = count is not None and 0 <= count <= _LOW_COUNT_MAX
    stabilizing_count = count is not None and _LOW_COUNT_MAX < count <= _STABILIZING_COUNT_MAX
    production_motion = online_state == "extruding" or (
        speed is not None and speed > constants.CYCLE_SPEED_THRESHOLD
    )

    phase = "unknown"
    if low_count_startup and low_speed and low_press:
        phase = "setup_candidate"
    elif low_count_startup and production_motion:
        phase = "setup_alignment_candidate"
    elif stabilizing_count and production_motion:
        phase = "production_stabilizing"
    elif production_motion:
        phase = "production_stable"
    elif input_state.actuator_scanning and low_speed:
        phase = "setup_alignment_candidate"
    elif input_state.operator_die_change_marker or _operator_context_changed(input_state):
        if low_speed or online_state in {"stopped", "idle_candidate", "changeover_candidate"}:
            phase = "die_change_candidate"
    elif online_state == "changeover_candidate":
        phase = "changeover_candidate"
    elif (
        count is not None
        and count > _STABILIZING_COUNT_MAX
        and input_state.recent_production_motion
        and low_speed
        and low_press
        and (input_state.count_held_sec or 0.0) >= _COUNT_HELD_FOR_CHANGEOVER_SEC
    ):
        phase = "stopped_after_production_candidate"
    elif online_state == "idle_candidate" or (low_speed and low_press):
        phase = "idle_candidate"

    return ProcessPhaseDecision(
        process_phase_candidate=phase,
    )


def _operator_context_changed(input_state: ProcessPhaseInput) -> bool:
    current = ((input_state.product_no or "").strip(), (input_state.mold_no or "").strip())
    previous = (
        (input_state.previous_product_no or "").strip(),
        (input_state.previous_mold_no or "").strip(),
    )
    return bool(current[0] and current[1] and previous[0] and previous[1] and current != previous)



def _to_float(value: Optional[float]) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Optional[int]) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
