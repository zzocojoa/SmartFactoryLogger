import unittest
from unittest.mock import patch

from backend.FacilityData.drivers.real_plc import MelsecResponseError, RealPLCDriver, _parse_melsec_values


class MelsecParseTests(unittest.TestCase):
    def test_parse_melsec_values_returns_hex_words(self) -> None:
        values = _parse_melsec_values("D0020", 2, b"01OK000A0014\r\n", "01OK000A0014")

        self.assertEqual(values, [10, 20])

    def test_parse_melsec_values_raises_with_context_for_invalid_hex(self) -> None:
        raw = b"01OK000G0014\r\n"

        with self.assertRaises(MelsecResponseError) as context:
            _parse_melsec_values("D0020", 2, raw, "01OK000G0014")

        message = str(context.exception)
        self.assertIn("addr=D0020", message)
        self.assertIn("count=2", message)
        self.assertIn("raw=b'01OK000G0014\\r\\n'", message)
        self.assertIn("chunk='000G'", message)
        self.assertIn("offset=0", message)

    def test_parse_melsec_values_raises_with_context_for_short_chunk(self) -> None:
        raw = b"01OK000A1\r\n"

        with self.assertRaises(MelsecResponseError) as context:
            _parse_melsec_values("D0020", 2, raw, "01OK000A1")

        message = str(context.exception)
        self.assertIn("addr=D0020", message)
        self.assertIn("count=2", message)
        self.assertIn("raw=b'01OK000A1\\r\\n'", message)
        self.assertIn("chunk='1'", message)
        self.assertIn("offset=4", message)


class SpotSnapshotTests(unittest.TestCase):
    def test_zero_cached_spot_temperature_replaces_previous_positive_snapshot(self) -> None:
        driver = RealPLCDriver()
        driver.last_spot = 45.5
        driver._update_spot_snapshot(45.5, 100.0)

        _, _, previous_spot = driver._read_cached_snapshot()
        self.assertEqual(previous_spot, 45.5)

        with patch("backend.FacilityData.drivers.real_plc.get_cached_spot_temp", return_value=0.0):
            spot_value = driver._read_spot()

        _, _, cached_spot = driver._read_cached_snapshot()

        self.assertEqual(spot_value, 0.0)
        self.assertEqual(driver.last_spot, 0.0)
        self.assertEqual(cached_spot, 0.0)


if __name__ == "__main__":
    unittest.main()
