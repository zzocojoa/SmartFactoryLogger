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

    def test_under_range_cause_uses_non_config_diagnostic_evidence(self) -> None:
        cases = [
            (
                ("target_absent_verified",),
                "target_out_of_fov_candidate",
                0.6,
            ),
            (
                ("actuator_position_changed",),
                "alignment_change_candidate",
                0.55,
            ),
            (
                ("measurement_range_configured", "detector_below_measurement_range"),
                "below_measurement_range_candidate",
                0.65,
            ),
        ]
        for evidence_codes, expected_cause, expected_confidence in cases:
            with self.subTest(expected_cause=expected_cause):
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

                self.assertEqual(decision.temperature_under_range_cause_candidate, expected_cause)
                self.assertEqual(decision.temperature_cause_confidence, expected_confidence)
                self.assertIn("phase_setup_candidate", json.loads(decision.temperature_cause_evidence_codes))

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
                self.assertIn(evidence_code, json.loads(decision.temperature_cause_evidence_codes))

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
            )
        )

        self.assertEqual(decision.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertEqual(decision.temperature_cause_confidence, 0.85)
        self.assertEqual(
            json.loads(decision.temperature_cause_evidence_codes),
            ["alarm_low_signal", "phase_setup_candidate"],
        )

    def test_under_range_signalpc_threshold_config_promotes_low_signal_candidate(self) -> None:
        evidence_codes = derive_spot_diagnostic_evidence_codes(
            {
                "signalpc": "3.2",
                "low_signal_alarm_enabled": True,
                "low_signal_threshold_pc": "5.0",
                "low_signal_comparator": "lte",
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
            )
        )

        self.assertEqual(evidence_codes, ("signal_below_threshold",))
        self.assertEqual(decision.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertEqual(decision.temperature_cause_confidence, 0.65)
        self.assertEqual(
            json.loads(decision.temperature_cause_evidence_codes),
            ["phase_setup_candidate", "signal_below_threshold"],
        )

    def test_signalpc_6_threshold_2_alarm_disabled_is_not_low_signal(self) -> None:
        result = derive_low_signal_evidence(
            alarmstatus=0,
            signalpc=6.0,
            low_signal_alarm_enabled=False,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lt",
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
        )

        self.assertFalse(result["numeric_low_signal"])

    def test_signal_equal_threshold_lte_is_low(self) -> None:
        result = derive_low_signal_evidence(
            alarmstatus=0,
            signalpc=2.0,
            low_signal_alarm_enabled=True,
            low_signal_threshold_pc=2.0,
            low_signal_comparator="lte",
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


if __name__ == "__main__":
    unittest.main()
