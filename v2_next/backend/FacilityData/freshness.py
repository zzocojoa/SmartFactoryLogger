"""Shared source-clock validation; invalid ages must never become fresh."""
import math
import os
from uuid import uuid4

SPOT_CACHE_EXPIRY_THRESHOLD_SEC = 15.0  # Existing runtime default, not a replay setting.
_PROCESS_ID = os.getpid()
_PROCESS_NONCE = uuid4().hex
SPOT_POLL_DURATION_RULE_VERSION = "spot-poll-duration-monotonic-v1"
SPOT_POLL_DURATION_STATUSES = frozenset({"ok", "missing_start", "missing_end", "invalid_endpoint",
                                       "negative_elapsed", "domain_unknown", "not_attempted", "unknown"})


def spot_poll_duration(start: object, end: object, domain: object) -> tuple[float | None, str]:
    """Original poll boundaries only; UTC and publisher residence are not elapsed time."""
    if start is None:
        return None, "missing_start"
    if end is None:
        return None, "missing_end"
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return None, "invalid_endpoint"
    if any(isinstance(value, bool) or not math.isfinite(value) or value < 0 for value in (start, end)):
        return None, "invalid_endpoint"
    if domain != clock_domain_id():
        return None, "domain_unknown"
    elapsed = (end - start) * 1000.0
    if not math.isfinite(elapsed):
        return None, "invalid_endpoint"
    return (None, "negative_elapsed") if elapsed < 0 else (elapsed, "ok")


def spot_poll_duration_output(value: object, status: object) -> tuple[float | None, str]:
    """Never promote a legacy duration without its measurement status to the new contract."""
    if not isinstance(status, str) or status not in SPOT_POLL_DURATION_STATUSES:
        return None, "unknown"
    if status != "ok":
        return None, str(status)
    duration = finite_number(value)
    return (duration, "ok") if duration is not None and duration >= 0 else (None, "invalid_endpoint")


def spot_poll_duration_metadata() -> dict:
    return {"rule_version": SPOT_POLL_DURATION_RULE_VERSION, "clock": "same_process_monotonic",
            "interval": "original_poll_context_start_to_completion_before_publish",
            "invalid_policy": "blank_with_status; no_epoch_fallback; temperature_independent",
            "statuses": sorted(SPOT_POLL_DURATION_STATUSES),
            "historical_policy": "older_schema_duration_remains_epoch_based; never_reinterpreted"}


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


def plc_source_age_at_sample(source: object, sample: object, domain: object) -> tuple[float | None, str]:
    """Frozen acquisition proof, never an epoch or consumer-time fallback."""
    if not isinstance(domain, str) or domain != clock_domain_id():
        return None, "domain_unknown"
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (source, sample)):
        return None, "unknown"
    return monotonic_age_ms(sample, source)


def plc_source_is_usable(usable: object, age_ms: object, threshold_ms: object, error: object,
                         *, count: object, speed: object, press: object,
                         source_completed_monotonic: object = None, sample_monotonic: object = None,
                         source_clock_domain: object = None) -> bool:
    age, threshold = finite_number(age_ms), finite_number(threshold_ms)
    clock_age, clock_status = plc_source_age_at_sample(source_completed_monotonic, sample_monotonic, source_clock_domain)
    return (usable is True and error is False and age is not None and threshold is not None
            and clock_status == "ok" and age == clock_age
            and threshold > 0 and 0 <= age <= threshold
            and all(value == "valid" for value in
                    plc_required_input_status(count=count, speed=speed, press=press).values()))
