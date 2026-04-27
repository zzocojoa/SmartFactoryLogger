import unittest

from backend.FacilityData.drivers.real_plc import MelsecResponseError, _parse_melsec_values


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


if __name__ == "__main__":
    unittest.main()
