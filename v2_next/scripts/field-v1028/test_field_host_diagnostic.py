"""Bounded host evidence and synthetic observation integration, never field QA."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

import field_host_diagnostic as diagnostic
import field_observation as observation


class HostDiagnosticTests(unittest.TestCase):
    def test_durable_samples_and_intervals_are_hash_bound(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = Path(parent) / 'host'
            result = diagnostic.collect_host_window(folder, duration_seconds=.1,
                origin_ns=time.perf_counter_ns(), stop=threading.Event(), interval_seconds=.1)
            self.assertEqual(result['recording_status'], 'COMPLETE')
            self.assertEqual(result['captured_slots'], 2)
            self.assertEqual(result['missed_slots'], 0)
            manifest = json.loads((folder / 'manifest.json').read_bytes())
            self.assertEqual(set(manifest['files']), {p.name for p in folder.iterdir()} - {'manifest.json'})
            for name, fact in manifest['files'].items():
                raw = (folder / name).read_bytes()
                self.assertEqual(fact, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            before = json.loads((folder / 'host-00000.json').read_bytes())['snapshot']
            after = json.loads((folder / 'host-00001.json').read_bytes())['snapshot']
            intervals = json.loads((folder / 'intervals.json').read_bytes())
            self.assertEqual(intervals[0]['counters'], diagnostic.host.compare_host(before, after))
            self.assertEqual(result['release_gate'], 'HOLD')
            self.assertFalse(result['promotion_allowed'])

    def test_cancelled_collection_and_old_slots_are_not_filled(self):
        with tempfile.TemporaryDirectory() as parent:
            stop = threading.Event(); stop.set()
            cancelled = diagnostic.collect_host_window(Path(parent) / 'cancelled', duration_seconds=.1,
                origin_ns=time.perf_counter_ns(), stop=stop, interval_seconds=.1)
            self.assertEqual(cancelled['recording_status'], 'INCOMPLETE')
            self.assertEqual(cancelled['cancelled_slots'], 2)
            stale = diagnostic.collect_host_window(Path(parent) / 'stale', duration_seconds=.1,
                origin_ns=time.perf_counter_ns() - 1_000_000_000, stop=threading.Event(), interval_seconds=.1)
            self.assertEqual(stale['captured_slots'], 0)
            self.assertEqual(stale['missed_slots'], 2)
            self.assertEqual(stale['recording_status'], 'INCOMPLETE')

    @unittest.skipUnless(os.environ.get('SFL_HOST_DIAGNOSTIC_TEST_ROOT'), 'Explicit native fixture root required')
    def test_owned_synthetic_observation_includes_host_and_preserves_release_hold(self):
        from test_field_observation import fixture_app
        root = Path(os.environ['SFL_HOST_DIAGNOSTIC_TEST_ROOT'])
        root.mkdir()
        with fixture_app(root, disabled_low_signal=True) as spec:
            result = observation.supervise_observation(spec, root / 'diagnostic', duration_seconds=5,
                _worker_target=diagnostic.worker_entry)
            worker = json.loads((root / 'diagnostic/worker-result.json').read_bytes())
            self.assertEqual(result['errors'], [])
            self.assertFalse(result['termination_requested'])
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
            self.assertEqual(worker['host_diagnostic']['recording_status'], 'COMPLETE')
            self.assertEqual(worker['host_exit_code'], 0)
            self.assertEqual(worker['validation_scope'], diagnostic.host.SCOPE)
            self.assertEqual(worker['formal_qa_gate'], 'HOLD')
            self.assertEqual(worker['field_gate'], 'NOT_EVALUATED')
            self.assertFalse(worker['promotion_allowed'])
            self.assertEqual(set(worker['component_exits']), {'http', 'processes', 'resources'})

    @unittest.skipUnless(os.environ.get('SFL_HOST_DIAGNOSTIC_TEST_ROOT'), 'Explicit native fixture root required')
    def test_changed_application_generation_remains_failed_with_host_diagnostics(self):
        from test_field_observation import fixture_app
        root = Path(os.environ['SFL_HOST_DIAGNOSTIC_TEST_ROOT'] + '-changed')
        root.mkdir()
        with fixture_app(root, mode='changed-service', disabled_low_signal=True) as spec:
            result = observation.supervise_observation(spec, root / 'diagnostic', duration_seconds=5,
                _worker_target=diagnostic.worker_entry)
            worker = json.loads((root / 'diagnostic/worker-result.json').read_bytes())
            self.assertEqual(result['supervisor_status'], 'FAIL')
            self.assertEqual(worker['observation_status'], 'FAIL')
            self.assertEqual(result['worker_exit_code'], 1)
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
            self.assertFalse(worker['promotion_allowed'])


if __name__ == '__main__':
    unittest.main()
