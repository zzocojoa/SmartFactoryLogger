from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


SPOT_TEMPERATURE_MIN_C = 0.0
SPOT_TEMPERATURE_MAX_C = 2000.0
SPOT_UNDER_RANGE_SENTINEL_VALUE = "6553.4"
SPOT_OVER_RANGE_SENTINEL_VALUE = "6553.5"
SPOT_INVALID_SENTINEL_VALUES = (
    SPOT_UNDER_RANGE_SENTINEL_VALUE,
    SPOT_OVER_RANGE_SENTINEL_VALUE,
)
SPOT_INVALID_SENTINEL_MEANINGS = {
    SPOT_UNDER_RANGE_SENTINEL_VALUE: "under_range",
    SPOT_OVER_RANGE_SENTINEL_VALUE: "over_range",
}


class SpotPollStatus(str, Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    CONFIG_MISSING = "config_missing"
    NOT_ATTEMPTED = "not_attempted"


class SpotRawValidity(str, Enum):
    VALID_TEMPERATURE = "valid_temperature"
    VERIFIED_NO_TARGET = "verified_no_target"
    EMPTY_BODY = "empty_body"
    PARSE_ERROR = "parse_error"
    INVALID_SENTINEL = "invalid_sentinel"
    OUT_OF_RANGE = "out_of_range"
    NOT_RECEIVED = "not_received"
    NOT_EVALUATED = "not_evaluated"


class SpotSourceFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class SpotTargetState(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class SpotTargetObservedSource(str, Enum):
    VERIFIED_DEVICE_CODE = "verified_device_code"
    VALID_TEMPERATURE = "valid_temperature"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpotRawClassification:
    poll_status: SpotPollStatus
    raw_validity: SpotRawValidity
    raw_value_text: Optional[str]
    parsed_temperature_c: Optional[float]
    cache_fallback_allowed: bool
    raw_payload_hash: Optional[str]
    response_content_length: Optional[int]
    http_status_code: Optional[int] = None
    error_code: Optional[str] = None


@dataclass(frozen=True)
class SpotTargetObservation:
    state: SpotTargetState
    source: SpotTargetObservedSource


def spot_raw_payload_hash(payload: Optional[bytes]) -> Optional[str]:
    if payload is None:
        return None
    return hashlib.sha256(payload).hexdigest()


def cache_fallback_allowed_for_poll_status(poll_status: SpotPollStatus | str) -> bool:
    status = _coerce_poll_status(poll_status)
    return status in {
        SpotPollStatus.TIMEOUT,
        SpotPollStatus.CONNECTION_ERROR,
        SpotPollStatus.HTTP_ERROR,
    }


def classify_spot_raw_response(
    *,
    poll_status: SpotPollStatus | str,
    body: Optional[bytes],
    http_status_code: Optional[int] = None,
    error_code: Optional[str] = None,
    verified_no_target_values: Iterable[str] = (),
    invalid_sentinel_values: Iterable[str] = SPOT_INVALID_SENTINEL_VALUES,
    min_c: float = SPOT_TEMPERATURE_MIN_C,
    max_c: float = SPOT_TEMPERATURE_MAX_C,
    encoding: str = "utf-8",
) -> SpotRawClassification:
    status = _coerce_poll_status(poll_status)
    content_length = len(body) if body is not None else None
    raw_hash = spot_raw_payload_hash(body)
    fallback_allowed = cache_fallback_allowed_for_poll_status(status)

    if status != SpotPollStatus.SUCCESS:
        if status == SpotPollStatus.HTTP_ERROR and body:
            raw_validity = SpotRawValidity.NOT_EVALUATED
            raw_text = _decode_body(body, encoding).strip()
        else:
            raw_validity = SpotRawValidity.NOT_RECEIVED
            raw_text = None
        return SpotRawClassification(
            poll_status=status,
            raw_validity=raw_validity,
            raw_value_text=raw_text,
            parsed_temperature_c=None,
            cache_fallback_allowed=fallback_allowed,
            raw_payload_hash=raw_hash,
            response_content_length=content_length,
            http_status_code=http_status_code,
            error_code=error_code,
        )

    raw_text = _decode_body(body or b"", encoding).strip()
    if raw_text == "":
        return SpotRawClassification(
            poll_status=status,
            raw_validity=SpotRawValidity.EMPTY_BODY,
            raw_value_text=raw_text,
            parsed_temperature_c=None,
            cache_fallback_allowed=False,
            raw_payload_hash=raw_hash,
            response_content_length=content_length,
            http_status_code=http_status_code,
            error_code=error_code,
        )

    if raw_text in set(verified_no_target_values):
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.VERIFIED_NO_TARGET,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    if raw_text in set(invalid_sentinel_values):
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.INVALID_SENTINEL,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    try:
        parsed = float(raw_text)
    except ValueError:
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.PARSE_ERROR,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    if not math.isfinite(parsed):
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.PARSE_ERROR,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    if parsed < min_c or parsed > max_c:
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.OUT_OF_RANGE,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    return SpotRawClassification(
        poll_status=status,
        raw_validity=SpotRawValidity.VALID_TEMPERATURE,
        raw_value_text=raw_text,
        parsed_temperature_c=parsed,
        cache_fallback_allowed=False,
        raw_payload_hash=raw_hash,
        response_content_length=content_length,
        http_status_code=http_status_code,
        error_code=error_code,
    )


def derive_spot_target_observed_shadow(
    raw_validity: SpotRawValidity | str,
    source_freshness: SpotSourceFreshness | str,
) -> SpotTargetObservation:
    freshness = _coerce_source_freshness(source_freshness)
    if freshness != SpotSourceFreshness.FRESH:
        return SpotTargetObservation(
            state=SpotTargetState.UNKNOWN,
            source=SpotTargetObservedSource.UNKNOWN,
        )

    validity = _coerce_raw_validity(raw_validity)
    if validity == SpotRawValidity.VERIFIED_NO_TARGET:
        return SpotTargetObservation(
            state=SpotTargetState.ABSENT,
            source=SpotTargetObservedSource.VERIFIED_DEVICE_CODE,
        )
    if validity == SpotRawValidity.VALID_TEMPERATURE:
        return SpotTargetObservation(
            state=SpotTargetState.PRESENT,
            source=SpotTargetObservedSource.VALID_TEMPERATURE,
        )
    return SpotTargetObservation(
        state=SpotTargetState.UNKNOWN,
        source=SpotTargetObservedSource.UNKNOWN,
    )


def _successful_non_temperature_classification(
    raw_text: str,
    raw_validity: SpotRawValidity,
    raw_hash: Optional[str],
    content_length: Optional[int],
    http_status_code: Optional[int],
    error_code: Optional[str],
) -> SpotRawClassification:
    return SpotRawClassification(
        poll_status=SpotPollStatus.SUCCESS,
        raw_validity=raw_validity,
        raw_value_text=raw_text,
        parsed_temperature_c=None,
        cache_fallback_allowed=False,
        raw_payload_hash=raw_hash,
        response_content_length=content_length,
        http_status_code=http_status_code,
        error_code=error_code,
    )


def _decode_body(body: bytes, encoding: str) -> str:
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _coerce_poll_status(value: SpotPollStatus | str) -> SpotPollStatus:
    if isinstance(value, SpotPollStatus):
        return value
    return SpotPollStatus(value)


def _coerce_raw_validity(value: SpotRawValidity | str) -> SpotRawValidity:
    if isinstance(value, SpotRawValidity):
        return value
    return SpotRawValidity(value)


def _coerce_source_freshness(value: SpotSourceFreshness | str) -> SpotSourceFreshness:
    if isinstance(value, SpotSourceFreshness):
        return value
    return SpotSourceFreshness(value)
