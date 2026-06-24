from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
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
SPOT_UNDER_RANGE_DEVICE_STATUS_CODE = "temperature_under_range"
SPOT_OVER_RANGE_DEVICE_STATUS_CODE = "temperature_over_range"
SPOT_INVALID_SENTINEL_DEVICE_STATUS_CODES = {
    SPOT_UNDER_RANGE_SENTINEL_VALUE: SPOT_UNDER_RANGE_DEVICE_STATUS_CODE,
    SPOT_OVER_RANGE_SENTINEL_VALUE: SPOT_OVER_RANGE_DEVICE_STATUS_CODE,
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
    device_status_code: Optional[str] = None
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
            raw_text = _decode_body(body, encoding)
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

    raw_text = _decode_body(body or b"", encoding)
    classification_text = raw_text.strip()
    if classification_text == "":
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

    verified_no_target_set = {str(value).strip() for value in verified_no_target_values}
    if classification_text in verified_no_target_set:
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.VERIFIED_NO_TARGET,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    sentinel_matched, device_status_code = _match_invalid_sentinel(
        classification_text,
        invalid_sentinel_values,
    )
    if sentinel_matched:
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.INVALID_SENTINEL,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
            device_status_code=device_status_code,
        )

    parsed_decimal = _parse_decimal(classification_text)
    if parsed_decimal is None or not parsed_decimal.is_finite():
        return _successful_non_temperature_classification(
            raw_text,
            SpotRawValidity.PARSE_ERROR,
            raw_hash,
            content_length,
            http_status_code,
            error_code,
        )

    if parsed_decimal < Decimal(str(min_c)) or parsed_decimal > Decimal(str(max_c)):
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
        parsed_temperature_c=float(parsed_decimal),
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
    *,
    device_status_code: Optional[str] = None,
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
        device_status_code=device_status_code,
        error_code=error_code,
    )


def _match_invalid_sentinel(
    classification_text: str,
    invalid_sentinel_values: Iterable[str],
) -> tuple[bool, Optional[str]]:
    sentinel_texts = {str(value).strip() for value in invalid_sentinel_values}
    if classification_text in sentinel_texts:
        parsed = _parse_decimal(classification_text)
        return True, _device_status_code_for_invalid_sentinel_decimal(parsed)

    parsed = _parse_decimal(classification_text)
    if parsed is None or not parsed.is_finite():
        return False, None

    for sentinel_text in sentinel_texts:
        sentinel_decimal = _parse_decimal(sentinel_text)
        if sentinel_decimal is None or not sentinel_decimal.is_finite():
            continue
        if parsed == sentinel_decimal:
            return True, _device_status_code_for_invalid_sentinel_decimal(sentinel_decimal)
    return False, None


def _device_status_code_for_invalid_sentinel_decimal(value: Optional[Decimal]) -> Optional[str]:
    if value is None or not value.is_finite():
        return None
    if value == Decimal(SPOT_UNDER_RANGE_SENTINEL_VALUE):
        return SPOT_UNDER_RANGE_DEVICE_STATUS_CODE
    if value == Decimal(SPOT_OVER_RANGE_SENTINEL_VALUE):
        return SPOT_OVER_RANGE_DEVICE_STATUS_CODE
    return None


def _parse_decimal(text: str) -> Optional[Decimal]:
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


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
