import json
import unittest

from backend.FacilityData.spot_observation_fact import derive_spot_diagnostic_evidence_codes
from backend.FacilityData.spot_low_signal import derive_low_signal_evidence
from backend.FacilityData.temperature_operational import (
    TemperatureOperationalInput,
    derive_temperature_operational_fields,
    derive_under_range_cause_candidate,
)


class TemperatureOperationalTests(unittest.TestCase):
    def eligible_diagnostics(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "diagnostics_current_poll_seq": 7,
            "diagnostics_current_service_instance_id": "svc-1",
            "diagnostics_snapshot_id": "svc-1:diag:3",
            "diagnostics_source_poll_seq": 7,
            "diagnostics_capture_status": "async_complete",
            "diagnostics_collection_mode": "async_same_poll",
            "diagnostics_binding_status": "same_poll",
            "diagnostics_age_ms": 25.0,
            "diagnostics_max_age_ms": 6000.0,
            "diagnostics_field_status": {
                "alarmstatus": "success",
                "signalpc": "success",
            },
        }
        values.update(overrides)
        return values

    def test_fresh_under_range_sentinel_maps_to_operational_under_range(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                process_phase_candidate="setup_candidate",
            )
        )

        self.assertEqual(decision.temperature_output_status, "under_range")
        self.assertEqual(decision.temperature_unavailable_reason, "under_range")
        self.assertEqual(decision.temperature_expectedness_candidate, "expected_candidate")
        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
        self.assertEqual(decision.temperature_cause_confidence, 0.0)
        self.assertEqual(json.loads(decision.temperature_cause_evidence_codes), ["phase_setup_candidate"])
        self.assertEqual(decision.spot_effective_freshness_at_row, "fresh")

    def test_under_range_setup_alignment_without_diagnostics_keeps_unknown_cause(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                process_phase_candidate="setup_alignment_candidate",
            )
        )

        self.assertEqual(decision.temperature_output_status, "under_range")
        self.assertEqual(decision.temperature_expectedness_candidate, "expected_candidate")
        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
        self.assertEqual(decision.temperature_cause_confidence, 0.0)
        self.assertEqual(json.loads(decision.temperature_cause_evidence_codes), ["phase_setup_candidate"])

    def test_trusted_phase_input_distinguishes_strong_pre_changeover_from_weak_stopped_hold(self) -> None:
        cases = [
            ("pre_changeover_hold_candidate", "expected_candidate"),
            ("stopped_after_production_candidate", "unknown"),
            ("possible_pre_changeover_hold", "unknown"),
        ]

        for phase, expectedness in cases:
            with self.subTest(phase=phase):
                decision = derive_temperature_operational_fields(
                    TemperatureOperationalInput(
                        poll_status="success",
                        raw_validity="invalid_sentinel",
                        source_freshness="fresh",
                        temperature_value_origin="none",
                        spot_device_status_code="temperature_under_range",
                        spot_effective_age_ms_at_row=100.0,
                        process_phase_candidate=phase,
                    )
                )

                self.assertEqual(decision.temperature_output_status, "under_range")
                self.assertEqual(decision.temperature_expectedness_candidate, expectedness)
                self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")

                evidence_codes = json.loads(decision.temperature_cause_evidence_codes)
                if phase == "pre_changeover_hold_candidate":
                    self.assertIn("phase_setup_candidate", evidence_codes)
                else:
                    self.assertNotIn("phase_setup_candidate", evidence_codes)

    def test_collectorless_evidence_is_preserved_but_cause_promotion_is_suppressed(self) -> None:
        cases = [
            (
                ("target_absent_verified",),
                ("target_absent_verified",),
            ),
            (
                ("actuator_position_changed",),
                ("actuator_position_changed",),
            ),
            (
                ("measurement_range_configured", "detector_below_measurement_range"),
                ("detector_below_measurement_range", "measurement_range_configured"),
            ),
        ]
        for evidence_codes, expected_suppressed in cases:
            with self.subTest(evidence_codes=evidence_codes):
                decision = derive_temperature_operational_fields(
                    TemperatureOperationalInput(
                        poll_status="success",
                        raw_validity="invalid_sentinel",
                        source_freshness="fresh",
                        temperature_value_origin="none",
                        spot_device_status_code="temperature_under_range",
                        spot_effective_age_ms_at_row=100.0,
                        process_phase_candidate="setup_candidate",
                        evidence_codes=evidence_codes,
                    )
                )

                self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
                self.assertEqual(decision.temperature_cause_confidence, 0.0)
                self.assertTrue(decision.unsupported_evidence_suppressed)
                self.assertEqual(
                    json.loads(decision.unsupported_evidence_suppressed_codes),
                    list(expected_suppressed),
                )
                output_evidence = json.loads(decision.temperature_cause_evidence_codes)
                self.assertIn("phase_setup_candidate", output_evidence)
                for evidence_code in evidence_codes:
                    self.assertIn(evidence_code, output_evidence)

    def test_stale_string_evidence_alone_does_not_promote_config_sensitive_causes(self) -> None:
        for evidence_code in (
            "alarm_low_signal",
            "signal_below_threshold",
            "peak_picker_off_mode_reset_configured",
        ):
            with self.subTest(evidence_code=evidence_code):
                decision = derive_temperature_operational_fields(
                    TemperatureOperationalInput(
                        poll_status="success",
                        raw_validity="invalid_sentinel",
                        source_freshness="fresh",
                        temperature_value_origin="none",
                        spot_device_status_code="temperature_under_range",
                        spot_effective_age_ms_at_row=100.0,
                        process_phase_candidate="setup_candidate",
                        evidence_codes=(evidence_code,),
                    )
                )

                self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
                self.assertEqual(decision.temperature_cause_confidence, 0.0)
                output_evidence = json.loads(decision.temperature_cause_evidence_codes)
                if evidence_code in {"alarm_low_signal", "signal_below_threshold"}:
                    self.assertNotIn(evidence_code, output_evidence)
                    self.assertIn("diagnostics_missing_or_stale", output_evidence)
                else:
                    self.assertIn(evidence_code, output_evidence)

    def test_under_range_alarmstatus_bit4_promotes_low_signal_candidate(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                process_phase_candidate="setup_candidate",
                alarmstatus=0x10,
                **self.eligible_diagnostics(),
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertEqual(decision.temperature_cause_confidence, 0.85)
        self.assertEqual(
            json.loads(decision.temperature_cause_evidence_codes),
            ["alarm_low_signal", "phase_setup_candidate"],
        )

    def test_same_response_diagnostics_are_causal_when_identity_and_age_are_valid(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                alarmstatus=0x10,
                **self.eligible_diagnostics(
                    diagnostics_capture_status="same_response",
                    diagnostics_collection_mode="atomic_output_json",
                    diagnostics_age_ms=0.0,
                ),
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertFalse(decision.diagnostics_cause_suppressed)

    def test_under_range_signalpc_threshold_config_promotes_low_signal_candidate(self) -> None:
        evidence_codes = derive_spot_diagnostic_evidence_codes(
            {
                "signalpc": "3.2",
                "low_signal_alarm_enabled": True,
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "lte",
                "low_signal_comparator_verified": True,
            }
        )

        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                process_phase_candidate="setup_candidate",
                evidence_codes=evidence_codes,
                alarmstatus=0,
                signalpc=3.2,
                low_signal_alarm_enabled=True,
                low_signal_threshold_pc=5.0,
                low_signal_comparator="lte",
                low_signal_comparator_verified=True,
                **self.eligible_diagnostics(),
            )
        )

        self.assertEqual(evidence_codes, ("signal_below_threshold",))
        self.assertEqual(decision.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertEqual(decision.temperature_cause_confidence, 0.65)
        self.assertEqual(
            json.loads(decision.temperature_cause_evidence_codes),
            ["phase_setup_candidate", "signal_below_threshold"],
        )

    def test_fact_only_diagnostics_are_preserved_but_not_causal(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                alarmstatus=0x10,
                **self.eligible_diagnostics(diagnostics_collection_mode="async_fact_only"),
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
        self.assertTrue(decision.diagnostics_cause_suppressed)
        self.assertEqual(decision.diagnostics_cause_suppressed_reason, "fact_only")
        self.assertEqual(
            json.loads(decision.temperature_cause_evidence_codes),
            ["diagnostics_missing_or_stale"],
        )

    def test_legacy_async_enriched_diagnostics_without_identity_are_not_causal(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                alarmstatus=0x10,
                diagnostics_capture_status="async_enriched",
                diagnostics_collection_mode="async_same_poll",
                diagnostics_binding_status="same_poll",
                diagnostics_age_ms=10.0,
                diagnostics_max_age_ms=6000.0,
                diagnostics_field_status={"alarmstatus": "success"},
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
        self.assertEqual(decision.diagnostics_cause_suppressed_reason, "capture_error")

    def test_partial_diagnostics_allow_successful_required_field(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                alarmstatus=0x10,
                **self.eligible_diagnostics(
                    diagnostics_capture_status="async_partial",
                    diagnostics_missing_fields=("d1temperature",),
                    diagnostics_field_status={
                        "alarmstatus": "success",
                        "signalpc": "success",
                        "d1temperature": "timeout",
                    },
                ),
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertFalse(decision.diagnostics_cause_suppressed)

    def test_partial_diagnostics_reject_failed_required_field(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=100.0,
                alarmstatus=0x10,
                **self.eligible_diagnostics(
                    diagnostics_capture_status="async_partial",
                    diagnostics_missing_fields=("alarmstatus",),
                    diagnostics_field_status={
                        "alarmstatus": "timeout",
                        "signalpc": "success",
                    },
                ),
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
        self.assertEqual(decision.diagnostics_cause_suppressed_reason, "required_field_failed")

    def test_previous_poll_and_stale_diagnostics_are_not_causal(self) -> None:
        cases = [
            (
                {
                    "diagnostics_source_poll_seq": 6,
                    "diagnostics_binding_status": "previous_poll",
                },
                "previous_poll",
            ),
            ({"diagnostics_age_ms": 7000.0}, "stale"),
            ({"diagnostics_age_ms": -1.0, "diagnostics_binding_status": "future_clock"}, "future_clock"),
            ({"diagnostics_snapshot_id": "other-svc:diag:3"}, "snapshot_identity_missing"),
        ]
        for overrides, expected_reason in cases:
            with self.subTest(expected_reason=expected_reason):
                decision = derive_temperature_operational_fields(
                    TemperatureOperationalInput(
                        poll_status="success",
                        raw_validity="invalid_sentinel",
                        source_freshness="fresh",
                        temperature_value_origin="none",
                        spot_device_status_code="temperature_under_range",
                        spot_effective_age_ms_at_row=100.0,
                        alarmstatus=0x10,
                        **self.eligible_diagnostics(**overrides),
                    )
                )

                self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
                self.assertEqual(decision.diagnostics_cause_suppressed_reason, expected_reason)

    def test_unverified_comparator_suppresses_numeric_low_signal_cause(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0,
            signalpc=1.5,
            low_signal_alarm_enabled=True,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=False,
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "unknown")
        self.assertEqual(result["temperature_cause_confidence"], 0.0)
        self.assertIn(
            "signalpc_present_comparator_unverified",
            result["temperature_cause_evidence_codes"],
        )
        self.assertNotIn("signal_below_threshold", result["temperature_cause_evidence_codes"])

    def test_alarmstatus_bit4_remains_authoritative_when_comparator_is_unverified(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0x10,
            signalpc=1.5,
            low_signal_alarm_enabled=True,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=False,
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "low_signal_candidate")
        self.assertEqual(result["temperature_cause_confidence"], 0.85)
        self.assertIn("alarm_low_signal", result["temperature_cause_evidence_codes"])

    def test_signalpc_6_threshold_2_alarm_disabled_is_not_low_signal(self) -> None:
        result = derive_low_signal_evidence(
            alarmstatus=0,
            signalpc=6.0,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=True,
        )

        self.assertFalse(result["low_signal_alarm_active"])
        self.assertFalse(result["numeric_low_signal"])
        self.assertNotIn("alarm_low_signal", result["evidence_codes"])
        self.assertIn("signal_at_or_above_configured_threshold", result["evidence_codes"])

    def test_alarmstatus_bit4_sets_low_signal_candidate(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0x10,
            signalpc=6.0,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=True,
            phase_evidence_codes=[],
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "low_signal_candidate")
        self.assertIn("alarm_low_signal", result["temperature_cause_evidence_codes"])
        self.assertGreaterEqual(result["temperature_cause_confidence"], 0.8)

    def test_signal_below_threshold_alarm_disabled_does_not_set_low_signal_cause(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0,
            signalpc=1.5,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=True,
            phase_evidence_codes=[],
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "unknown")
        self.assertEqual(result["temperature_cause_confidence"], 0.0)
        self.assertIn("signal_below_configured_threshold_alarm_disabled", result["temperature_cause_evidence_codes"])
        self.assertNotIn("signal_below_threshold", result["temperature_cause_evidence_codes"])

    def test_signal_below_threshold_alarm_enabled_sets_low_signal_cause(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0,
            signalpc=1.5,
            low_signal_alarm_enabled=True,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=True,
            phase_evidence_codes=[],
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "low_signal_candidate")
        self.assertIn("signal_below_threshold", result["temperature_cause_evidence_codes"])

    def test_signal_equal_threshold_lt_is_not_low(self) -> None:
        result = derive_low_signal_evidence(
            alarmstatus=0,
            signalpc=2.0,
            low_signal_alarm_enabled=True,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            low_signal_comparator_verified=True,
        )

        self.assertFalse(result["numeric_low_signal"])

    def test_signal_equal_threshold_lte_is_low(self) -> None:
        result = derive_low_signal_evidence(
            alarmstatus=0,
            signalpc=2.0,
            low_signal_alarm_enabled=True,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lte",
            low_signal_comparator_verified=True,
        )

        self.assertTrue(result["numeric_low_signal"])

    def test_phase_setup_alone_does_not_set_below_measurement_range(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0,
            signalpc=None,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            phase_evidence_codes=["phase_setup_candidate"],
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "unknown")
        self.assertEqual(result["temperature_cause_confidence"], 0.0)
        self.assertIn("phase_setup_candidate", result["temperature_cause_evidence_codes"])

    def test_peak_picker_disabled_never_sets_peak_picker_reset_candidate(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0,
            signalpc=None,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            peak_picker_enabled=False,
            peak_picker_off_mode="Reset",
            phase_evidence_codes=[],
        )

        self.assertNotEqual(result["temperature_under_range_cause_candidate"], "peak_picker_reset_candidate")

    def test_peak_picker_config_without_collector_is_suppressed(self) -> None:
        result = derive_under_range_cause_candidate(
            alarmstatus=0,
            signalpc=None,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
            peak_picker_enabled=True,
            peak_picker_off_mode="Reset",
            phase_evidence_codes=[],
        )

        self.assertEqual(result["temperature_under_range_cause_candidate"], "unknown")
        self.assertEqual(
            result["unsupported_evidence_suppressed_codes"],
            ["peak_picker_off_mode_reset_configured"],
        )

    def test_stale_precedence_preserves_raw_sentinel_but_outputs_stale(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="stale",
                temperature_value_origin="none",
                spot_device_status_code="temperature_under_range",
                spot_effective_age_ms_at_row=10_000.0,
                process_phase_candidate="production_stable",
            )
        )

        self.assertEqual(decision.temperature_output_status, "stale")
        self.assertEqual(decision.temperature_unavailable_reason, "stale_observation")
        self.assertEqual(decision.temperature_expectedness_candidate, "unknown")

    def test_over_range_is_unexpected_in_any_phase(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="invalid_sentinel",
                source_freshness="fresh",
                temperature_value_origin="none",
                spot_device_status_code="temperature_over_range",
                spot_effective_age_ms_at_row=10.0,
                process_phase_candidate="idle_candidate",
            )
        )

        self.assertEqual(decision.temperature_output_status, "over_range")
        self.assertEqual(decision.temperature_expectedness_candidate, "unexpected_candidate")

    def test_timeout_maps_to_source_error_reason(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="timeout",
                raw_validity="not_received",
                source_freshness="fresh",
                temperature_value_origin="none",
                cache_fallback_allowed=False,
                spot_effective_age_ms_at_row=10.0,
            )
        )

        self.assertEqual(decision.temperature_output_status, "source_error")
        self.assertEqual(decision.temperature_unavailable_reason, "timeout")

    def test_transport_failure_with_ttl_cache_is_valid_cached_observation(self) -> None:
        for poll_status in ("timeout", "connection_error", "http_error"):
            with self.subTest(poll_status=poll_status):
                decision = derive_temperature_operational_fields(
                    TemperatureOperationalInput(
                        poll_status=poll_status,
                        raw_validity="not_received",
                        source_freshness="fresh",
                        cache_fallback_allowed=True,
                        has_ttl_valid_cache=True,
                        has_previous_valid_value=True,
                        temperature_value_origin="cached_observation",
                        spot_effective_age_ms_at_row=10.0,
                    )
                )

                self.assertEqual(decision.temperature_output_status, "valid")
                self.assertEqual(decision.temperature_unavailable_reason, "")
                self.assertEqual(decision.temperature_value_origin, "cached_observation")
                self.assertTrue(decision.cached_fallback_accepted)
                self.assertEqual(decision.cached_fallback_rejected_reason, "")

    def test_transport_failure_with_suppressed_cache_is_rejected(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="timeout",
                raw_validity="not_received",
                source_freshness="fresh",
                cache_fallback_allowed=False,
                has_ttl_valid_cache=True,
                has_previous_valid_value=True,
                temperature_value_origin="none",
                spot_effective_age_ms_at_row=10.0,
            )
        )

        self.assertEqual(decision.temperature_output_status, "source_error")
        self.assertEqual(decision.temperature_value_origin, "none")
        self.assertFalse(decision.cached_fallback_accepted)
        self.assertEqual(decision.cached_fallback_rejected_reason, "fallback_disallowed")

    def test_cached_fallback_stays_stale_when_row_is_stale(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="timeout",
                raw_validity="not_received",
                source_freshness="stale",
                cache_fallback_allowed=True,
                has_ttl_valid_cache=True,
                has_previous_valid_value=True,
                temperature_value_origin="cached_observation",
                spot_effective_age_ms_at_row=10_000.0,
            )
        )

        self.assertEqual(decision.temperature_output_status, "stale")
        self.assertFalse(decision.cached_fallback_accepted)
        self.assertEqual(decision.cached_fallback_rejected_reason, "stale_observation")
        self.assertEqual(decision.temperature_value_origin, "none")

    def test_cached_fallback_clock_anomaly_fails_closed(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="timeout",
                raw_validity="not_received",
                source_freshness="fresh",
                cache_fallback_allowed=True,
                has_ttl_valid_cache=True,
                has_previous_valid_value=True,
                temperature_value_origin="cached_observation",
                spot_effective_age_ms_at_row=-1.0,
            )
        )

        self.assertEqual(decision.temperature_output_status, "unknown")
        self.assertFalse(decision.cached_fallback_accepted)
        self.assertEqual(decision.cached_fallback_rejected_reason, "clock_anomaly")

    def test_origin_mismatch_fails_closed(self) -> None:
        decision = derive_temperature_operational_fields(
            TemperatureOperationalInput(
                poll_status="success",
                raw_validity="valid_temperature",
                source_freshness="fresh",
                temperature_value_origin="cached_observation",
                spot_effective_age_ms_at_row=10.0,
            )
        )

        self.assertEqual(decision.temperature_output_status, "unknown")
        self.assertEqual(decision.temperature_value_origin, "none")
        self.assertTrue(decision.origin_decision_mismatch)


if __name__ == "__main__":
    unittest.main()
