"""Collection failure propagation with synthetic component boundaries."""
from contextlib import contextmanager, ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import field_health_collection as collection
from field_resource_sampling import ProcessIdentity


ROOT = Path(os.environ['SFL_HEALTH_COLLECTION_TEST_ROOT'])


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / str(len(list(ROOT.iterdir())))
        self.folder.mkdir()
        for name in ('ref.json', 'config.json'):
            (self.folder/name).write_text('{}', encoding='utf-8')
        self.spec = collection.HealthCollectionSpec(str(self.folder), str(self.folder/'ref.json'),
            ProcessIdentity(100, 1.0, os.path.normcase(str(self.folder/'smart-factory.exe'))),
            ProcessIdentity(101, 2.0, os.path.normcase(str(self.folder/'backend.exe'))), 8000,
            configuration_reference=str(self.folder/'config.json'),
            configuration_reference_sha256='a'*64, backend_created_filetime=1000)

    def run_collection(self, *, configuration=None, control=None, probes=None, native=None,
                       closeout_error=False, stop=None, duration=.01, trace=None):
        @contextmanager
        def reference(*args, **kwargs):
            yield {}
            if closeout_error:
                raise OSError('injected reference closeout failure')
        native = native or [dict(status='CAPTURED', pid=101, created_100ns=1000)] * 2
        probe = dict(status='REQUEST_AND_RUNTIME_BOUND', probe_id='a'*32,
                     health_record={'client_request_and_body_ms': 250}, health_body_hex='7b7d')
        events = []
        with ExitStack() as stack:
            payload = stack.enter_context(patch.object(collection.binding, 'InstalledPayload'))
            payload.return_value.__enter__.return_value = SimpleNamespace(recheck=lambda: {'files': 4})
            stack.enter_context(patch.object(collection.configuration, 'configuration_reference', reference))
            reader = stack.enter_context(patch.object(collection, 'WindowsProcessReader'))
            reader.return_value.read.side_effect = native
            stack.enter_context(patch.object(collection.binding, 'capture_runtime_binding',
                return_value={'binding_status': 'PASS', 'sessions': {'fixture': 'same'}}))
            stack.enter_context(patch.object(collection.generation, 'capture_generation',
                side_effect=control or [{'generation_status': 'PASS', 'identity': {'id': 1}}]*2))
            stack.enter_context(patch.object(collection.configuration, 'capture_configuration',
                side_effect=configuration or [{'configuration_status': 'PASS'}]*2))
            call = stack.enter_context(patch.object(collection.diagnostic, 'capture_health_probe',
                side_effect=probes or [probe]))
            result = collection.collect(self.spec, self.folder, duration, stop or threading.Event(), events.append, _trace=trace)
        self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])
        return result, events, call.call_count

    def test_slow_bound_response_is_preserved_without_performance_pass(self):
        result, events, count = self.run_collection()
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 1))
        self.assertEqual([e['phase'] for e in events], ['observing', 'finalizing'])
        raw = json.loads((self.folder/'evidence/probe-000.json').read_bytes())
        self.assertEqual(raw['health_record']['client_request_and_body_ms'], 250)
        self.assertEqual(result['etw_coverage'], 'NOT_EVALUATED')

    def test_initial_configuration_or_control_failure_prevents_probes(self):
        for kind, failed in (('configuration', {'configuration_status': 'FAIL'}),
                             ('control', {'generation_status': 'FAIL'})):
            self.setUp()
            result, events, count = self.run_collection(**{kind: [failed]})
            self.assertEqual((result['collection_status'], events, count), ('INCOMPLETE', [], 0))

    def test_final_generation_or_configuration_change_cannot_leave_success(self):
        for kind, rows in (('configuration', [{'configuration_status': 'PASS'}, {'configuration_status': 'FAIL'}]),
                           ('control', [{'generation_status': 'PASS', 'identity': {'id': 1}}, {'generation_status': 'FAIL'}])):
            self.setUp()
            result, _, count = self.run_collection(**{kind: rows})
            self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 1))
            self.assertTrue((self.folder/'evidence/probe-000.json').is_file())

    def test_reference_closeout_and_native_generation_fail_closed(self):
        result, _, _ = self.run_collection(closeout_error=True)
        self.assertEqual(result['collection_status'], 'INCOMPLETE')
        self.setUp()
        result, _, count = self.run_collection(native=[{'status': 'UNAVAILABLE'}])
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 0))

    def test_unbound_request_retains_failure_and_does_not_retry(self):
        result, _, count = self.run_collection(probes=[dict(status='NOT_BOUND', health_body_hex='7b7d')])
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 1))
        self.assertEqual(json.loads((self.folder/'evidence/probe-000.json').read_bytes())['status'], 'NOT_BOUND')

    def test_operator_stop_and_invalid_budget_prevent_collection(self):
        stop = threading.Event(); stop.set()
        result, _, count = self.run_collection(stop=stop)
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 0))
        for bad in (0, True, 31, float('nan')):
            with self.assertRaises(ValueError):
                collection.supervise(self.spec, self.folder/'never-created', duration_seconds=bad)
        self.assertFalse((self.folder/'never-created').exists())
        with self.assertRaises(ValueError):
            replace(self.spec, backend_created_filetime=True).validate()

    def test_overrun_is_durable_incomplete_and_has_no_catchup_request(self):
        def delayed(*args, **kwargs):
            time.sleep(2.05)
            return dict(status='REQUEST_AND_RUNTIME_BOUND', probe_id='a'*32)
        result, _, count = self.run_collection(probes=delayed, duration=2.1)
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 1))
        self.assertIn('diagnostic-slot-overrun', json.dumps(result))

    def test_final_manifest_tampering_is_not_silently_returned(self):
        original = collection.observation.verify_component_manifest
        def tampered(folder, budget):
            (folder/'probe-000.json').write_text('{}')
            return original(folder, budget)
        with patch.object(collection.observation, 'verify_component_manifest', tampered):
            with self.assertRaisesRegex(ValueError, 'component-file-hash'):
                self.run_collection()

    def test_trace_begin_and_finish_failures_are_durable_incomplete(self):
        for stage, count in (('begin', 0), ('finish', 1)):
            self.setUp()
            aborted = []
            def fail(*args):
                raise ValueError('injected-trace-'+stage)
            trace = SimpleNamespace(begin=fail if stage == 'begin' else lambda *args: {'bound': True},
                finish=fail if stage == 'finish' else lambda *args: {'stopped': True}, abort=aborted.append)
            result, _, actual = self.run_collection(trace=trace)
            self.assertEqual((result['collection_status'], actual, aborted), ('INCOMPLETE', count, ['ValueError']))
            self.assertIn('injected-trace-'+stage, json.dumps(result))

    def test_trace_stop_precedes_final_control_and_preserves_binding(self):
        phases = []
        def begin(files, stop):
            self.assertEqual(set(files), {'native-initial.json', 'runtime-initial.json', 'control-initial.json', 'configuration-initial.json'})
            phases.append('begin')
            return {'bound': True}
        def finish(files, stop):
            self.assertIn('probe-000.json', files)
            self.assertNotIn('control-final.json', files)
            phases.append('finish')
            return {'stopped': True}
        trace = SimpleNamespace(begin=begin, finish=finish, abort=phases.append)
        result, _, count = self.run_collection(trace=trace)
        self.assertEqual((result['collection_status'], count, phases), ('BOUND_WINDOW_CAPTURED', 1, ['begin', 'finish']))
        for name in ('trace-binding.json', 'trace-completion.json'):
            self.assertTrue((self.folder/'evidence'/name).is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
