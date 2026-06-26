import json
import unittest

from backend.FacilityData.temperature_operational import (
    TemperatureOperationalInput,
    derive_temperature_operational_fields,
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

    def test_under_range_cause_requires_direct_diagnostic_evidence(self) -> None:
        cases = [
            (
                ("peak_picker_off_mode_reset_configured",),
                "peak_picker_reset_candidate",
                0.75,
            ),
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
                ("signal_below_threshold",),
                "low_signal_candidate",
                0.6,
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
