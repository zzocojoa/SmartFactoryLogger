"""Independent synthetic malformed-evidence checks; no field performance claim."""
import copy
from fractions import Fraction
import hashlib
import json
import unittest

import field_health_timing as health


PROBE = 'a' * 32
CREATED = 134364960000000000
BODY = b'{"running":true}'


def anchor(pid, tid, before, after, ticks, created=CREATED):
    return dict(status='OBSERVED', pid=pid, tid=tid, process_created_filetime=created,
                thread_created_filetime=created + tid, perf_before_ns=before, perf_after_ns=after,
                qpc_ticks=ticks, qpc_frequency=10_000_000)


def collector(before, after, ticks, cpu):
    return dict(schema='sfl-self-thread-clock-v1', status='OBSERVED', error=None,
                identity=dict(pid=200, native_thread_id=201, process_created_filetime=CREATED - 100,
                              thread_created_filetime=CREATED - 90),
                boundary=dict(perf_before_ns=before, perf_after_ns=after, qpc_ticks=ticks,
                              qpc_frequency=10_000_000, thread_cpu_ns=cpu))


def write_header(record, value):
    record['headers'] = [('X-SFL-Health-Timing', json.dumps(value, separators=(',', ':')))]
    rehash_headers(record)


def rehash_headers(record):
    raw = json.dumps(record['headers'], ensure_ascii=True).encode()
    record.update(headers_bytes=len(raw), headers_sha256=hashlib.sha256(raw).hexdigest())


def fixture():
    timing = dict(v=2, probe_id=PROBE, pid=100, loop_tid=101, worker_tid=102, clock='perf_counter_ns',
        checkpoints=dict(zip(health.POINTS, (1000, 1200, 2000, 3000, 4000, 5000, 6000, 7000))),
        native=dict(loop_begin=anchor(100, 101, 1010, 1190, 11), worker_begin=anchor(100, 102, 2010, 2200, 21),
                    worker_end=anchor(100, 102, 6010, 6200, 61), loop_end=anchor(100, 101, 7010, 7200, 71)))
    record = dict(endpoint='health', path='/health', health_probe_id=PROBE, request_success=True, status=200,
        body_complete=True, decode_complete=True, error_type=None, timeout=False,
        body_bytes=len(BODY), body_sha256=hashlib.sha256(BODY).hexdigest(), headers_truncated=False,
        started_ns=700, response_finished_ns=8000, finished_ns=8300,
        native_timing=dict(begin=collector(800, 900, 8, 100), end=collector(8100, 8200, 81, 150)))
    write_header(record, timing)
    return record, timing


class ValidationTests(unittest.TestCase):
    def validate(self, record, raw=BODY, **kwargs):
        args = dict(probe_id=PROBE, backend_pid=100, backend_created_filetime=CREATED)
        args.update(kwargs)
        return health.validate_health_sample(record, raw, **args)

    def assert_rejected(self, result):
        self.assertEqual(result['status'], 'NOT_CORRELATABLE', result)
        self.assertIsNone(result['stages_ns'])
        self.assertIsNone(result['checkpoint_qpc_bounds'])
        self.assertFalse(result['promotion_allowed'])
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertTrue(result['reason'])

    def test_integer_qpc_bounds_and_stage_partition(self):
        record, timing = fixture()
        before = copy.deepcopy(record)
        result = self.validate(record)
        self.assertEqual(result['status'], 'REQUEST_AND_NATIVE_CLOCK_BOUND', result)
        self.assertEqual(sum(result['stages_ns'].values()), 6000)
        for name, point in timing['checkpoints'].items():
            exact = Fraction(point * 10_000_000, 1_000_000_000)
            low, high = result['checkpoint_qpc_bounds'][name]
            self.assertLessEqual(low, exact)
            self.assertGreaterEqual(high, exact)
        self.assertEqual(record, before)
        self.assertEqual(result['etw_coverage'], 'NOT_EVALUATED')
        self.assertEqual(result['latency_cause'], 'UNDETERMINED')

    def test_body_header_hash_and_incomplete_requests(self):
        for key, value in [('path', '/other'), ('health_probe_id', 'b' * 32), ('request_success', 1),
                ('status', True), ('status', 503), ('body_complete', False), ('decode_complete', False),
                ('error_type', 'Timeout'), ('timeout', True), ('body_bytes', 0), ('body_sha256', 'f' * 64),
                ('headers_bytes', True), ('headers_sha256', '0' * 64), ('headers_truncated', True),
                ('started_ns', True), ('response_finished_ns', 6999), ('finished_ns', 7999)]:
            with self.subTest(key=key, value=value):
                record, _ = fixture()
                record[key] = value
                self.assert_rejected(self.validate(record))
        record, _ = fixture()
        self.assert_rejected(self.validate(record, b'{"running":false}'))
        for raw in (b'null', b'{"x":1,"x":2}', b'{"x":NaN}', b'{' * 5000):
            record, _ = fixture()
            record.update(body_bytes=len(raw), body_sha256=hashlib.sha256(raw).hexdigest())
            self.assert_rejected(self.validate(record, raw))

    def test_missing_duplicate_oversized_and_malformed_headers(self):
        for mode in ('missing', 'duplicate', 'combined', 'huge', 'unicode', 'duplicate-json', 'nested', 'list'):
            with self.subTest(mode=mode):
                record, _ = fixture()
                value = record['headers'][0][1]
                replacement = {'missing': [], 'duplicate': record['headers'] * 2,
                    'combined': [('x-sfl-health-timing', value + ',' + value)],
                    'huge': [('x-sfl-health-timing', ' ' * 4097)],
                    'unicode': [('x-sfl-health-timing', '한글')],
                    'duplicate-json': [('x-sfl-health-timing', '{"v":2,"v":2}')],
                    'nested': [('x-sfl-health-timing', '[' * 1500 + ']' * 1500)],
                    'list': [('x-sfl-health-timing', '[]')]}[mode]
                record['headers'] = replacement
                rehash_headers(record)
                self.assert_rejected(self.validate(record))

    def test_version_identity_and_checkpoint_mismatches(self):
        for key, value in [('v', 1), ('v', True), ('clock', 'UTC'), ('probe_id', 'b' * 32),
                           ('pid', 999), ('loop_tid', True), ('worker_tid', 101), ('extra', 1)]:
            record, timing = fixture()
            timing[key] = value
            write_header(record, timing)
            self.assert_rejected(self.validate(record))
        for name, value in [('worker_enter', 1100), ('route_resume', 8001), ('plc_done', 1.5),
                            ('frontend_done', True), ('route_enter', -1), ('route_enter', 2**63)]:
            record, timing = fixture()
            timing['checkpoints'][name] = value
            write_header(record, timing)
            self.assert_rejected(self.validate(record))
        for name in health.POINTS:
            record, timing = fixture()
            del timing['checkpoints'][name]
            write_header(record, timing)
            self.assert_rejected(self.validate(record))

    def test_native_generation_clock_and_stage_mismatches(self):
        changes = [('pid', 200), ('tid', 101), ('process_created_filetime', CREATED + 1),
                   ('thread_created_filetime', CREATED + 1), ('qpc_frequency', True), ('qpc_frequency', 1),
                   ('qpc_ticks', -1), ('qpc_ticks', 100000), ('perf_before_ns', 0),
                   ('perf_after_ns', 2999), ('perf_after_ns', 999999), ('status', 'UNAVAILABLE')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                record, timing = fixture()
                timing['native']['worker_end'][key] = value
                write_header(record, timing)
                self.assert_rejected(self.validate(record))
        record, timing = fixture()
        timing['native']['loop_begin'] = {'status': 'UNAVAILABLE', 'error_type': 'OSError'}
        write_header(record, timing)
        self.assert_rejected(self.validate(record))
        record, timing = fixture()
        for name in ('worker_begin', 'worker_end'):
            timing['native'][name]['thread_created_filetime'] = CREATED - 1
        write_header(record, timing)
        self.assert_rejected(self.validate(record))

    def test_collector_claims_do_not_override_native_evidence(self):
        for section, key, value in [('identity', 'pid', 999), ('identity', 'thread_created_filetime', 1),
                ('boundary', 'qpc_frequency', 1), ('boundary', 'perf_before_ns', 7900),
                ('boundary', 'qpc_ticks', 999999), ('boundary', 'thread_cpu_ns', 1)]:
            record, _ = fixture()
            record['native_timing']['status'] = 'CORRELATABLE_BOUNDARIES'
            record['native_timing']['end'][section][key] = value
            self.assert_rejected(self.validate(record))
        for bad in (None, {}, {'status': 'CORRELATABLE_BOUNDARIES'}):
            record, _ = fixture()
            record['native_timing'] = bad
            self.assert_rejected(self.validate(record))

    def test_expected_generation_and_malformed_records_fail_closed(self):
        record, _ = fixture()
        for kwargs in ({'probe_id': True}, {'backend_pid': True}, {'backend_pid': 101},
                       {'backend_created_filetime': CREATED + 1}):
            self.assert_rejected(self.validate(record, **kwargs))
        for bad in (None, {}, [], {'endpoint': 'health'}):
            self.assert_rejected(self.validate(bad))


if __name__ == '__main__':
    unittest.main(verbosity=2)
