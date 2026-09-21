"""Shared source-clock validation; invalid ages must never become fresh."""
import math
import os
from uuid import uuid4

SPOT_CACHE_EXPIRY_THRESHOLD_SEC = 15.0  # Existing runtime default, not a replay setting.
_PROCESS_ID = os.getpid()
_PROCESS_NONCE = uuid4().hex


def clock_domain_id() -> str:
    # PID also prevents inherited tokens from authorizing a post-fork clock.
    return f"{_PROCESS_ID}:{os.getpid()}:{_PROCESS_NONCE}"


def finite_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def monotonic_age_ms(now: object, source: object) -> tuple[float | None, str]:
    current, started = finite_number(now), finite_number(source)
    if current is None or started is None:
        return None, "unknown"
    age = (current - started) * 1000.0
    if not math.isfinite(age) or age < 0 or started < 0 or current < 0:
        return None, "clock_anomaly"
    return age, "ok"


def cache_rejection_reason(age: object, clock: str, ttl_ms: object) -> str:
    if clock != "ok":
        return "value_clock_anomaly" if clock == "clock_anomaly" else "value_clock_unknown"
    value, ttl = finite_number(age), finite_number(ttl_ms)
    if value is None:
        return "value_age_unknown"
    if value < 0:
        return "value_clock_anomaly"
    if ttl is None or ttl <= 0:
        return "cache_ttl_invalid"
    return "cache_expired" if value > ttl else ""


def plc_required_input_status(*, count: object, speed: object, press: object) -> dict[str, str]:
    """Current collection's required phase inputs; zero is valid, bool/nonfinite is not."""
    status = {}
    for name, raw in (("Count", count), ("Speed", speed), ("Press", press)):
        value = finite_number(raw)
        status[name] = ("missing" if raw is None else "invalid" if value is None or
                        (name == "Count" and (value < 0 or not value.is_integer())) else "valid")
    return status


def plc_source_is_usable(usable: object, age_ms: object, threshold_ms: object, error: object,
                         *, count: object, speed: object, press: object) -> bool:
    age, threshold = finite_number(age_ms), finite_number(threshold_ms)
    return (usable is True and error is False and age is not None and threshold is not None
            and threshold > 0 and 0 <= age <= threshold
            and all(value == "valid" for value in
                    plc_required_input_status(count=count, speed=speed, press=press).values()))
