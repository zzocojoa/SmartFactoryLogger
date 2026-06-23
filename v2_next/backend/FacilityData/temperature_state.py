from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.FacilityData.spot_observation import (
    SpotPollStatus,
    SpotRawValidity,
    SpotSourceFreshness,
    cache_fallback_allowed_for_poll_status,
)


class SpotCacheStatus(str, Enum):
    FRESH = "fresh"
    REUSED = "reused"
    EXPIRED = "expired"
    EMPTY = "empty"
    INVALIDATED = "invalidated"
    AVAILABLE_NOT_USED = "available_not_used"


class TemperatureValueOrigin(str, Enum):
    CURRENT_OBSERVATION = "current_observation"
    CACHED_OBSERVATION = "cached_observation"
    NONE = "none"


class TemperatureStatusShadow(str, Enum):
    OK = "ok"
    NO_TARGET = "no_target"
    STARTUP_PENDING = "startup_pending"
    SOURCE_ERROR = "source_error"
    INVALID_VALUE = "invalid_value"
    STALE = "stale"
    UNKNOWN_MISSING = "unknown_missing"


@dataclass(frozen=True)
class TemperatureStateDecision:
    temperature_status_shadow: TemperatureStatusShadow
    spot_cache_status: SpotCacheStatus
    temperature_value_origin: TemperatureValueOrigin


@dataclass(frozen=True)
class TemperatureStateInput:
    poll_status: SpotPollStatus
    raw_validity: SpotRawValidity
    source_freshness: SpotSourceFreshness
    cache_fallback_allowed: bool
    has_ttl_valid_cache: bool = False
    has_previous_valid_value: bool = False
    first_poll_completed: bool = True


def derive_temperature_state(input_state: TemperatureStateInput) -> TemperatureStateDecision:
    if not input_state.first_poll_completed:
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.STARTUP_PENDING,
            spot_cache_status=SpotCacheStatus.EMPTY,
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    if input_state.source_freshness == SpotSourceFreshness.UNKNOWN:
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.UNKNOWN_MISSING,
            spot_cache_status=SpotCacheStatus.EMPTY,
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    if input_state.source_freshness == SpotSourceFreshness.STALE:
        return _derive_for_stale_source(input_state)

    if input_state.raw_validity == SpotRawValidity.VERIFIED_NO_TARGET:
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.NO_TARGET,
            spot_cache_status=SpotCacheStatus.INVALIDATED,
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    if input_state.raw_validity == SpotRawValidity.VALID_TEMPERATURE:
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.OK,
            spot_cache_status=SpotCacheStatus.FRESH,
            temperature_value_origin=TemperatureValueOrigin.CURRENT_OBSERVATION,
        )

    if _is_transport_failure_with_allowed_fallback(input_state):
        if input_state.has_ttl_valid_cache:
            return TemperatureStateDecision(
                temperature_status_shadow=TemperatureStatusShadow.OK,
                spot_cache_status=SpotCacheStatus.REUSED,
                temperature_value_origin=TemperatureValueOrigin.CACHED_OBSERVATION,
            )
        if input_state.has_previous_valid_value:
            return TemperatureStateDecision(
                temperature_status_shadow=TemperatureStatusShadow.STALE,
                spot_cache_status=SpotCacheStatus.EXPIRED,
                temperature_value_origin=TemperatureValueOrigin.NONE,
            )
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.SOURCE_ERROR,
            spot_cache_status=SpotCacheStatus.EMPTY,
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    if input_state.raw_validity in {
        SpotRawValidity.EMPTY_BODY,
        SpotRawValidity.PARSE_ERROR,
        SpotRawValidity.INVALID_SENTINEL,
        SpotRawValidity.OUT_OF_RANGE,
        SpotRawValidity.NOT_EVALUATED,
    }:
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.INVALID_VALUE,
            spot_cache_status=(
                SpotCacheStatus.AVAILABLE_NOT_USED
                if input_state.has_ttl_valid_cache
                else SpotCacheStatus.EMPTY
            ),
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    return TemperatureStateDecision(
        temperature_status_shadow=TemperatureStatusShadow.UNKNOWN_MISSING,
        spot_cache_status=SpotCacheStatus.EMPTY,
        temperature_value_origin=TemperatureValueOrigin.NONE,
    )


def _derive_for_stale_source(input_state: TemperatureStateInput) -> TemperatureStateDecision:
    if _is_transport_failure_with_allowed_fallback(input_state):
        if input_state.has_ttl_valid_cache:
            return TemperatureStateDecision(
                temperature_status_shadow=TemperatureStatusShadow.OK,
                spot_cache_status=SpotCacheStatus.REUSED,
                temperature_value_origin=TemperatureValueOrigin.CACHED_OBSERVATION,
            )
        if input_state.has_previous_valid_value:
            return TemperatureStateDecision(
                temperature_status_shadow=TemperatureStatusShadow.STALE,
                spot_cache_status=SpotCacheStatus.EXPIRED,
                temperature_value_origin=TemperatureValueOrigin.NONE,
            )
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.SOURCE_ERROR,
            spot_cache_status=SpotCacheStatus.EMPTY,
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    if input_state.has_previous_valid_value and not input_state.has_ttl_valid_cache:
        return TemperatureStateDecision(
            temperature_status_shadow=TemperatureStatusShadow.STALE,
            spot_cache_status=SpotCacheStatus.EXPIRED,
            temperature_value_origin=TemperatureValueOrigin.NONE,
        )

    return TemperatureStateDecision(
        temperature_status_shadow=TemperatureStatusShadow.UNKNOWN_MISSING,
        spot_cache_status=(
            SpotCacheStatus.AVAILABLE_NOT_USED
            if input_state.has_ttl_valid_cache
            else SpotCacheStatus.EMPTY
        ),
        temperature_value_origin=TemperatureValueOrigin.NONE,
    )


def _is_transport_failure_with_allowed_fallback(input_state: TemperatureStateInput) -> bool:
    return input_state.cache_fallback_allowed and cache_fallback_allowed_for_poll_status(
        input_state.poll_status
    )