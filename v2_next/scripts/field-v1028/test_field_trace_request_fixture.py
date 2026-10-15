"""Local sampler/injection and binding rejection checks; does not start ETW."""
import argparse
import copy
import hashlib
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

import field_trace_request_fixture as fixture

OUTPUT = None


class FixtureTests(unittest.TestCase):
    def directory(self):
        path = OUTPUT / uuid4().hex[:12]
        path.mkdir()
        return path

    def test_real_sampler_three_conditions_and_cleanup(self):
        run_id = uuid4().hex
        original = fixture.sampling._LoopbackConnection
        result = fixture.run_workload(run_id, {'scope': 'SYNTHETIC_BINDING_TEST_ONLY'})
        self.assertIs(fixture.sampling._LoopbackConnection, original)
        self.assertEqual([r['case'] for r in result['client']], list(fixture.CASES))
        client_identities = [r['request']['native_timing']['begin']['identity'] for r in result['client']]
        self.assertTrue(all(item == client_identities[0] for item in client_identities))
        self.assertNotEqual(client_identities[0]['native_thread_id'], result['main_begin']['identity']['native_thread_id'])
        for row in result['client']:
            native = row['request']['native_timing']
            self.assertEqual(fixture.timing.interval(native['begin'], native['end'])['status'], 'CORRELATABLE_BOUNDARIES')
        for row in result['server']:
            self.assertNotEqual(row['begin']['identity']['native_thread_id'], client_identities[0]['native_thread_id'])
            if row['case'] == 'server_sleep':
                begin, end = row['begin']['boundary'], row['before_headers']['boundary']
                self.assertGreaterEqual((end['qpc_ticks']-begin['qpc_ticks'])/begin['qpc_frequency'], .075)
        for row in result['injections']:
            begin, end = row['begin']['boundary'], row['end']['boundary']
            self.assertGreaterEqual(end['thread_cpu_ns']-begin['thread_cpu_ns'], 80_000_000)
        self.assertFalse(any(run_id in thread.name for thread in threading.enumerate()))
        self.assertEqual(result['trace_quality'], 'NOT_EVALUATED')
        self.assertFalse(result['promotion_allowed'])
        fixture.publish(self.directory(), 'workload.json', result)

    def test_request_failure_closes_threads_restores_transport(self):
        run_id = uuid4().hex
        original = fixture.sampling._LoopbackConnection
        with patch.object(fixture.sampling, 'fetch_sample', side_effect=OSError('injected-read-failure')):
            with self.assertRaisesRegex(ValueError, 'fixture-worker-failed'):
                fixture.run_workload(run_id, {})
        self.assertIs(fixture.sampling._LoopbackConnection, original)
        self.assertFalse(any(run_id in thread.name for thread in threading.enumerate()))

    def test_publish_never_replaces_evidence(self):
        directory = self.directory()
        first = fixture.publish(directory, 'evidence.json', {'value': 1})
        with self.assertRaises(FileExistsError):
            fixture.publish(directory, 'evidence.json', {'value': 2})
        value, fact = fixture.read_fact(directory/'evidence.json')
        self.assertEqual(value, {'value': 1})
        self.assertEqual(first, fact)

    def binding(self):
        parent = self.directory()
        run = parent / ('T' + uuid4().hex[:12])
        run.mkdir()
        identity = {'pid': 1234, 'process_created_filetime': 134364938856872760}
        run_id = uuid4().hex
        instance = 'SFLTrace_' + uuid4().hex
        lease = dict(schema='sfl-local-trace-lease-v1', scope='LOCAL_CONTROLLER_VALIDATION_ONLY',
                     profile_sha256=fixture.PROFILE_SHA, guard_seconds=8, stop_timeout_seconds=60,
                     run_path=str(run), instance=instance, release_gate='HOLD', promotion_allowed=False)
        lease_fact = fixture.publish(run, 'lease.json', lease)
        ready_fact = fixture.publish(run, 'ready.json', dict(instance=instance, lease_sha256=lease_fact['sha256']))
        fixture.publish(run, 'guard-process.json', dict(pid=4567, created_filetime='134364938856872761'))
        binding = dict(schema='sfl-request-trace-binding-v1', run_id=run_id,
                       fixture_pid=identity['pid'], fixture_created_filetime=str(identity['process_created_filetime']),
                       trace_run_path=str(run), lease_sha256=lease_fact['sha256'], ready_sha256=ready_fact['sha256'],
                       instance=instance, guard_pid=4567, guard_created_filetime='134364938856872761',
                       release_gate='HOLD', promotion_allowed=False)
        return parent, run, run_id, identity, binding

    def test_binding_accepts_only_same_run_generation_and_pins(self):
        parent, run, run_id, identity, binding = self.binding()
        self.assertEqual(fixture.validate_binding(binding, run_id, identity, parent)['binding'], binding)
        for key, value in [('run_id', 'a'*32), ('fixture_pid', 1), ('fixture_created_filetime', '1'),
                           ('lease_sha256', '0'*64), ('ready_sha256', '0'*64), ('guard_pid', 1),
                           ('guard_created_filetime', '1'), ('instance', 'wrong'), ('promotion_allowed', True)]:
            changed = copy.deepcopy(binding)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixture.validate_binding(changed, run_id, identity, parent)
        fixture.publish(run, 'stop-request.json', {'lease_sha256': binding['lease_sha256']})
        with self.assertRaisesRegex(ValueError, 'trace-already-ending'):
            fixture.validate_binding(binding, run_id, identity, parent)

    def test_json_rejects_duplicate_nonfinite_and_oversize(self):
        directory = self.directory()
        for index, value in enumerate((b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b' '*65537)):
            path = directory / f'invalid-{index}.json'
            path.write_bytes(value)
            with self.assertRaises(ValueError): fixture.read_fact(path)

    def test_path_rejects_parent_and_remote(self):
        for value in ('relative/path', 'C:/temp/../outside', '//server/share/test', 'C:/test/file:stream'):
            with self.subTest(value=value), self.assertRaises(ValueError): fixture.local_path(value)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    OUTPUT = parser.parse_args().output.resolve()
    OUTPUT.mkdir()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureTests))
    files = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in
             ('field_trace_request_fixture.py', 'test_field_trace_request_fixture.py', 'field_http_sampling.py', 'field_native_timing.py')}
    fixture.publish(OUTPUT, 'summary.json', dict(status='PASS' if result.wasSuccessful() else 'FAIL',
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), sources=files,
        actual_etw_executed=False, field_gate='NOT_EVALUATED', release_gate='HOLD', promotion_allowed=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
