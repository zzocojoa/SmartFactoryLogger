import math
import unittest

from pydantic import ValidationError

from backend.FacilityData.schemas import FactoryData


class FactoryDataSchemaTests(unittest.TestCase):
    def test_spot_rejects_negative_nonfinite_and_bool_values(self) -> None:
        invalid_values = [-1, float("nan"), float("inf"), float("-inf"), True, False]

        for value in invalid_values:
            with self.subTest(value=value):
                data = FactoryData(Time="2026-06-23T00:00:00", Spot=value)
                self.assertIsNone(data.Spot)

    def test_spot_rejects_nan_string_even_though_float_accepts_it(self) -> None:
        self.assertTrue(math.isnan(float("NaN")))

        data = FactoryData(Time="2026-06-23T00:00:00", Spot="NaN")

        self.assertIsNone(data.Spot)

    def test_shadow_enum_fields_reject_unknown_values(self) -> None:
        invalid_cases = {
            "extruder_process_state_online": "idle",
            "spot_target_state_observed_shadow": "present_candidate",
            "spot_poll_status": "parse_error",
            "spot_raw_validity": "http_error",
            "spot_cache_status": "fresh_cache",
            "spot_source_freshness": "old",
            "temperature_value_origin": "cache",
            "temperature_status_shadow": "missing",
        }

        for field, value in invalid_cases.items():
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    FactoryData(Time="2026-06-23T00:00:00", **{field: value})

    def test_shadow_enum_fields_accept_contract_values(self) -> None:
        data = FactoryData(
            Time="2026-06-23T00:00:00",
            extruder_process_state_online="changeover_candidate",
            spot_target_state_observed_shadow="unknown",
            spot_target_state_observed_source="unknown",
            label_validation_state="shadow",
            temperature_status_shadow="unknown_missing",
            spot_poll_status="http_error",
            spot_raw_validity="not_evaluated",
            spot_cache_status="available_not_used",
            spot_source_freshness="stale",
            temperature_value_origin="none",
        )

        self.assertEqual(data.extruder_process_state_online, "changeover_candidate")
        self.assertEqual(data.temperature_status_shadow, "unknown_missing")
        self.assertEqual(data.spot_raw_validity, "not_evaluated")

    def test_spot_sequence_ids_are_non_negative_and_ordered(self) -> None:
        data = FactoryData(
            Time="2026-06-23T00:00:00",
            spot_poll_seq="5",
            spot_observation_seq="5",
            spot_http_status_code="200",
            spot_response_content_length="12",
        )

        self.assertEqual(data.spot_poll_seq, 5)
        self.assertEqual(data.spot_observation_seq, 5)
        self.assertEqual(data.spot_http_status_code, 200)
        self.assertEqual(data.spot_response_content_length, 12)

        with self.assertRaises(ValidationError):
            FactoryData(Time="2026-06-23T00:00:00", spot_poll_seq=4, spot_observation_seq=5)

        negative = FactoryData(
            Time="2026-06-23T00:00:00",
            spot_poll_seq=-1,
            spot_observation_seq=-1,
            spot_http_status_code=-1,
            spot_response_content_length=-1,
        )
        self.assertIsNone(negative.spot_poll_seq)
        self.assertIsNone(negative.spot_observation_seq)
        self.assertIsNone(negative.spot_http_status_code)
        self.assertIsNone(negative.spot_response_content_length)


if __name__ == "__main__":
    unittest.main()