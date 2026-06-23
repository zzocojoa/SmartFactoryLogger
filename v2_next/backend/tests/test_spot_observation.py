import unittest

from backend.FacilityData.spot_observation import (
    SpotPollStatus,
    SpotRawValidity,
    SpotSourceFreshness,
    SpotTargetObservedSource,
    SpotTargetState,
    classify_spot_raw_response,
    derive_spot_target_observed_shadow,
)
from backend.FacilityData.temperature_state import (
    SpotCacheStatus,
    TemperatureStateInput,
    TemperatureStatusShadow,
    TemperatureValueOrigin,
    derive_temperature_state,
)


class SpotObservationTests(unittest.TestCase):
    def test_successful_numeric_body_is_current_valid_temperature(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.SUCCESS,
            body=b"448.5",
            http_status_code=200,
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.VALID_TEMPERATURE)
        self.assertEqual(classification.parsed_temperature_c, 448.5)
        self.assertFalse(classification.cache_fallback_allowed)
        self.assertEqual(classification.response_content_length, 5)

        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=classification.poll_status,
                raw_validity=classification.raw_validity,
                source_freshness=SpotSourceFreshness.FRESH,
                cache_fallback_allowed=classification.cache_fallback_allowed,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.OK)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.FRESH)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.CURRENT_OBSERVATION)

    def test_http_error_with_body_is_not_evaluated_and_allows_transport_fallback(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.HTTP_ERROR,
            body=b"upstream detail",
            http_status_code=503,
            error_code="temperature-upstream-http-error",
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.NOT_EVALUATED)
        self.assertTrue(classification.cache_fallback_allowed)
        self.assertEqual(classification.raw_value_text, "upstream detail")

    def test_timeout_without_body_is_not_received_and_allows_transport_fallback(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.TIMEOUT,
            body=None,
            error_code="temperature-upstream-timeout",
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.NOT_RECEIVED)
        self.assertTrue(classification.cache_fallback_allowed)
        self.assertIsNone(classification.raw_value_text)

    def test_empty_success_body_is_not_no_target_without_vendor_evidence(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.SUCCESS,
            body=b"",
            http_status_code=200,
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.EMPTY_BODY)
        self.assertFalse(classification.cache_fallback_allowed)

        target = derive_spot_target_observed_shadow(
            classification.raw_validity,
            SpotSourceFreshness.FRESH,
        )

        self.assertEqual(target.state, SpotTargetState.UNKNOWN)
        self.assertEqual(target.source, SpotTargetObservedSource.UNKNOWN)

    def test_verified_no_target_is_absent_only_for_fresh_snapshot(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.SUCCESS,
            body=b"NO_TARGET",
            http_status_code=200,
            verified_no_target_values=("NO_TARGET",),
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.VERIFIED_NO_TARGET)

        fresh_target = derive_spot_target_observed_shadow(
            classification.raw_validity,
            SpotSourceFreshness.FRESH,
        )
        stale_target = derive_spot_target_observed_shadow(
            classification.raw_validity,
            SpotSourceFreshness.STALE,
        )

        self.assertEqual(fresh_target.state, SpotTargetState.ABSENT)
        self.assertEqual(fresh_target.source, SpotTargetObservedSource.VERIFIED_DEVICE_CODE)
        self.assertEqual(stale_target.state, SpotTargetState.UNKNOWN)

        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=classification.poll_status,
                raw_validity=classification.raw_validity,
                source_freshness=SpotSourceFreshness.FRESH,
                cache_fallback_allowed=classification.cache_fallback_allowed,
                has_ttl_valid_cache=True,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.NO_TARGET)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.INVALIDATED)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_invalid_current_response_suppresses_ttl_valid_cache(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.SUCCESS,
            body=b"not-a-number",
            http_status_code=200,
        )

        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=classification.poll_status,
                raw_validity=classification.raw_validity,
                source_freshness=SpotSourceFreshness.FRESH,
                cache_fallback_allowed=classification.cache_fallback_allowed,
                has_ttl_valid_cache=True,
            )
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.PARSE_ERROR)
        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.INVALID_VALUE)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.AVAILABLE_NOT_USED)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_stale_success_snapshot_suppresses_ttl_cache(self) -> None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.SUCCESS,
                raw_validity=SpotRawValidity.VALID_TEMPERATURE,
                source_freshness=SpotSourceFreshness.STALE,
                cache_fallback_allowed=False,
                has_ttl_valid_cache=True,
                has_previous_valid_value=True,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.UNKNOWN_MISSING)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.AVAILABLE_NOT_USED)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_stale_transport_failure_reuses_ttl_cache_when_fallback_allowed(self) -> None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.TIMEOUT,
                raw_validity=SpotRawValidity.NOT_RECEIVED,
                source_freshness=SpotSourceFreshness.STALE,
                cache_fallback_allowed=True,
                has_ttl_valid_cache=True,
                has_previous_valid_value=True,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.OK)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.REUSED)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.CACHED_OBSERVATION)

    def test_stale_transport_failure_without_previous_value_is_source_error(self) -> None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.TIMEOUT,
                raw_validity=SpotRawValidity.NOT_RECEIVED,
                source_freshness=SpotSourceFreshness.STALE,
                cache_fallback_allowed=True,
                has_ttl_valid_cache=False,
                has_previous_valid_value=False,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.SOURCE_ERROR)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.EMPTY)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_stale_snapshot_with_expired_previous_value_is_stale(self) -> None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.SUCCESS,
                raw_validity=SpotRawValidity.VALID_TEMPERATURE,
                source_freshness=SpotSourceFreshness.STALE,
                cache_fallback_allowed=False,
                has_ttl_valid_cache=False,
                has_previous_valid_value=True,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.STALE)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.EXPIRED)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_transport_failure_without_cache_is_source_error_when_fresh(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.TIMEOUT,
            body=None,
            error_code="temperature-upstream-timeout",
        )

        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=classification.poll_status,
                raw_validity=classification.raw_validity,
                source_freshness=SpotSourceFreshness.FRESH,
                cache_fallback_allowed=classification.cache_fallback_allowed,
                has_ttl_valid_cache=False,
                has_previous_valid_value=False,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.SOURCE_ERROR)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.EMPTY)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_unknown_source_after_first_poll_is_unknown_missing(self) -> None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.NOT_ATTEMPTED,
                raw_validity=SpotRawValidity.NOT_RECEIVED,
                source_freshness=SpotSourceFreshness.UNKNOWN,
                cache_fallback_allowed=False,
                first_poll_completed=True,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.UNKNOWN_MISSING)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.EMPTY)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_first_poll_before_snapshot_is_startup_pending(self) -> None:
        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=SpotPollStatus.NOT_ATTEMPTED,
                raw_validity=SpotRawValidity.NOT_RECEIVED,
                source_freshness=SpotSourceFreshness.UNKNOWN,
                cache_fallback_allowed=False,
                first_poll_completed=False,
            )
        )

        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.STARTUP_PENDING)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.EMPTY)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_ametek_under_range_sentinel_is_invalid_not_no_target(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.SUCCESS,
            body=b"6553.4\r\n",
            http_status_code=200,
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.INVALID_SENTINEL)
        self.assertEqual(classification.raw_value_text, "6553.4")
        self.assertIsNone(classification.parsed_temperature_c)
        self.assertFalse(classification.cache_fallback_allowed)

        target = derive_spot_target_observed_shadow(
            classification.raw_validity,
            SpotSourceFreshness.FRESH,
        )
        self.assertEqual(target.state, SpotTargetState.UNKNOWN)
        self.assertEqual(target.source, SpotTargetObservedSource.UNKNOWN)

        decision = derive_temperature_state(
            TemperatureStateInput(
                poll_status=classification.poll_status,
                raw_validity=classification.raw_validity,
                source_freshness=SpotSourceFreshness.FRESH,
                cache_fallback_allowed=classification.cache_fallback_allowed,
                has_ttl_valid_cache=True,
            )
        )
        self.assertEqual(decision.temperature_status_shadow, TemperatureStatusShadow.INVALID_VALUE)
        self.assertEqual(decision.spot_cache_status, SpotCacheStatus.AVAILABLE_NOT_USED)
        self.assertEqual(decision.temperature_value_origin, TemperatureValueOrigin.NONE)

    def test_ametek_over_range_sentinel_is_invalid_not_temperature(self) -> None:
        classification = classify_spot_raw_response(
            poll_status=SpotPollStatus.SUCCESS,
            body=b"6553.5",
            http_status_code=200,
        )

        self.assertEqual(classification.raw_validity, SpotRawValidity.INVALID_SENTINEL)
        self.assertEqual(classification.raw_value_text, "6553.5")
        self.assertIsNone(classification.parsed_temperature_c)
        self.assertFalse(classification.cache_fallback_allowed)

if __name__ == "__main__":
    unittest.main()
