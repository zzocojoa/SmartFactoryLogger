"""Keep full-byte/JSON verification while bounding each small-file read request."""
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import field_installation_binding as binding
import field_observation as observation


ROOT = Path(os.environ['SFL_READ_TEST_ROOT'])


class RecordingReader(io.BytesIO):
    def __init__(self, raw, *, short_read=None, fail_on=None):
        super().__init__(raw)
        self.requests = []
        self.returned_bytes = 0
        self.short_read = short_read
        self.fail_on = fail_on

    def read(self, size=-1):
        self.requests.append(size)
        if len(self.requests) == self.fail_on:
            raise OSError('injected-read-failure')
        raw = super().read(min(size, self.short_read) if self.short_read else size)
        self.returned_bytes += len(raw)
        return raw


class ZeroStream:
    """Exercise the real512MiB limit without allocating a512MiB fixture."""
    def __init__(self, size):
        self.size = size
        self.position = 0
        self.max_request = 0

    def seek(self, offset):
        if offset != 0:
            raise ValueError('fixture-only-rewinds')
        self.position = 0

    def read(self, size):
        self.max_request = max(self.max_request, size)
        count = min(size, self.size - self.position)
        self.position += count
        return b'\0' * count


class BoundedReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()

    def json_input(self, raw, *, limit=16 * 1024**2, **reader_options):
        path = self.folder / 'input.json'
        path.write_bytes(raw)
        reader = RecordingReader(raw, **reader_options)
        with patch.object(Path, 'open', return_value=reader):
            value = observation.read_json(path, limit)
        return value, reader

    def test_small_fact_read_has_bounded_request_and_exact_hash(self):
        raw = b'field-evidence' * 170
        stream = RecordingReader(raw)
        stream.seek(31)
        self.assertEqual(binding.stream_fact(stream),
                         dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        self.assertLessEqual(max(stream.requests), 64 * 1024)
        self.assertEqual(stream.returned_bytes, len(raw))
        self.assertFalse(stream.closed)

    def test_empty_and_short_reads_hash_all_bytes_from_start(self):
        for raw in (b'', bytes(range(256)) * 513):
            with self.subTest(size=len(raw)):
                stream = RecordingReader(raw, short_read=17)
                self.assertEqual(binding.stream_fact(stream),
                                 dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
                self.assertEqual(stream.returned_bytes, len(raw))

    def test_stream_byte_budget_at_and_around_actual_limit(self):
        maximum = 512 * 1024**2
        expected = {
            maximum - 1: 'bf7f45d9df691bd277948d7f124b87a9f76e16ddb5d8fb25a49df939798f0a01',
            maximum: '9acca8e8c22201155389f65abbf6bc9723edc7384ead80503839f49dcc56d767',
        }
        for size, sha in expected.items():
            with self.subTest(size=size):
                stream = ZeroStream(size)
                self.assertEqual(binding.stream_fact(stream), dict(bytes=size, sha256=sha))
        stream = ZeroStream(maximum + 1)
        with self.assertRaisesRegex(ValueError, 'file-byte-budget'):
            binding.stream_fact(stream)
        self.assertEqual(stream.position, maximum + 1)

    def test_stream_read_failure_is_not_a_partial_fact(self):
        with self.assertRaisesRegex(OSError, 'injected-read-failure'):
            binding.stream_fact(RecordingReader(b'abcdef', short_read=2, fail_on=2))

    def test_small_json_does_not_request_the_entire_size_budget(self):
        raw = b'{"verified":true}\n'
        (parsed, returned), reader = self.json_input(raw)
        self.assertEqual(parsed, {'verified': True})
        self.assertEqual(returned, raw)
        self.assertLessEqual(max(reader.requests), 64 * 1024)
        self.assertEqual(reader.returned_bytes, len(raw))

    def test_json_multibyte_text_crosses_read_boundary_unchanged(self):
        prefix = b'{"text":"'
        raw = prefix + b'x' * (65535 - len(prefix)) + '가'.encode() + b'"}'
        (parsed, returned), reader = self.json_input(raw)
        self.assertEqual(parsed, json.loads(raw))
        self.assertEqual(returned, raw)
        self.assertLessEqual(max(reader.requests), 64 * 1024)

    def test_json_short_reads_continue_until_eof(self):
        raw = b'{"verified":true,"sequence":123}\n'
        (parsed, returned), reader = self.json_input(raw, short_read=3)
        self.assertEqual(parsed, json.loads(raw))
        self.assertEqual(returned, raw)
        self.assertEqual(reader.returned_bytes, len(raw))

    def test_json_budget_at_and_around_actual_limit(self):
        maximum = 16 * 1024**2
        for size in (maximum - 1, maximum, maximum + 1):
            with self.subTest(size=size):
                raw = b'{}' + b' ' * (size - 2)
                if size <= maximum:
                    (parsed, returned), _ = self.json_input(raw)
                    self.assertEqual(parsed, {})
                    self.assertEqual(returned, raw)
                else:
                    with self.assertRaisesRegex(ValueError, 'json-read-budget'):
                        self.json_input(raw)

    def test_custom_json_budget_reads_at_most_one_over_limit(self):
        path = self.folder / 'oversized.json'
        path.write_bytes(b'{}' + b' ' * 1000)
        reader = RecordingReader(path.read_bytes(), short_read=7)
        with patch.object(Path, 'open', return_value=reader):
            with self.assertRaisesRegex(ValueError, 'json-read-budget'):
                observation.read_json(path, limit=31)
        self.assertEqual(reader.returned_bytes, 32)

    def test_json_read_failure_is_not_partial_success(self):
        with self.assertRaisesRegex(OSError, 'injected-read-failure'):
            self.json_input(b'{"verified":true}', short_read=3, fail_on=2)

    def test_json_validation_remains_strict(self):
        for raw in (b'', b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'{}trailing', b'{"a":"\xff"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.json_input(raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
