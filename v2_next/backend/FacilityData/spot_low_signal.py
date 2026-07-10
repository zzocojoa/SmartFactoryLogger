from __future__ import annotations

from typing import Optional, TypedDict


LOW_SIGNAL_ALARM_BIT = 1 << 4
LOW_SIGNAL_COMPARATORS = frozenset({"lt", "lte"})


class LowSignalEvidence(TypedDict):
    low_signal_alarm_active: bool
    numeric_low_signal: Optional[bool]
    evidence_codes: list[str]


def derive_low_signal_evidence(
    *,
    alarmstatus: int | None,
    signalpc: float | None,
    low_signal_alarm_enabled: bool,
    low_signal_threshold_pc: float | None,
    low_signal_comparator: str | None,
    low_signal_comparator_verified: bool = False,
) -> LowSignalEvidence:
    evidence_codes: list[str] = []

    low_signal_alarm_active = alarmstatus is not None and (alarmstatus & LOW_SIGNAL_ALARM_BIT) != 0
    if low_signal_alarm_active:
        evidence_codes.append("alarm_low_signal")

    numeric_low_signal: Optional[bool] = None
    if (
        signalpc is not None
        and low_signal_threshold_pc is not None
        and low_signal_comparator in LOW_SIGNAL_COMPARATORS
    ):
        if not low_signal_comparator_verified:
            evidence_codes.append("signalpc_present_comparator_unverified")
        elif low_signal_comparator == "lt":
            numeric_low_signal = signalpc < low_signal_threshold_pc
        else:
            numeric_low_signal = signalpc <= low_signal_threshold_pc

        if low_signal_comparator_verified:
            if numeric_low_signal and low_signal_alarm_enabled:
                evidence_codes.append("signal_below_threshold")
            elif numeric_low_signal and not low_signal_alarm_enabled:
                evidence_codes.append("signal_below_configured_threshold_alarm_disabled")
            else:
                evidence_codes.append("signal_at_or_above_configured_threshold")
    elif signalpc is not None:
        evidence_codes.append("signalpc_present_threshold_unknown")

    return {
        "low_signal_alarm_active": low_signal_alarm_active,
        "numeric_low_signal": numeric_low_signal,
        "evidence_codes": evidence_codes,
    }
