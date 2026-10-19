"""Partial capture must retain a failed review and explain process-slot misses."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import field_observation as observation


class PartialReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['SFL_PARTIAL_TEST_ROOT'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec = SimpleNamespace(backend=SimpleNamespace(pid=42, created=1.0, exe='backend'))
        self.origin = 10_000_000_000
        self.duration = 12
        self.sessions = {'session': 'fixture'}
        self.boundaries = [dict(binding_status='PASS', sessions=self.sessions,
            health_record=dict(client_request_and_body_ms=1.0, request_success=True)) for _ in range(2)]

    def fixture(self, *, health_cancel=True, resource_cancel=True):
        summaries = {
            'http': dict(origin_ns=self.origin, http_component_status='FAIL'),
            'resources': dict(origin_ns=self.origin, recording_status='INCOMPLETE',
                              unmeasured_intervals=1, resource_coverage_status='NOT_MEASURED'),
            'processes': dict(origin_ns=self.origin, status='FAIL'),
        }
        for component, summary in summaries.items():
            folder = self.root / component
            folder.mkdir()
            files = {'summary.json': observation.write_json(folder / 'summary.json', summary)}
            if component == 'http' and health_cancel:
                files['health-00000.json'] = observation.write_json(folder / 'health-00000.json',
                    dict(kind='cancelled_remaining', sequence=0, remaining_slots=6,
                         scheduled_ns=self.origin))
            elif component == 'resources' and resource_cancel:
                files['resource-00000.json'] = observation.write_json(folder / 'resource-00000.json',
                    dict(kind='cancelled_remaining', sequence=0, remaining_slots=3,
                         scheduled_ns=self.origin))
            observation.write_json(folder / 'manifest.json', dict(files=files))

    def review(self):
        return observation.review_window(self.spec, self.root, self.origin, self.duration,
                                         self.sessions, self.boundaries)

    def test_cancelled_spans_produce_failed_review_without_missing_file_error(self):
        self.fixture()
        result = self.review()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('health-0-cancelled-remaining:6', result['issues'])
        self.assertIn('resource-0-cancelled-remaining:3', result['issues'])
        self.assertIn('all-health-including-boundaries-failed', result['issues'])
        self.assertEqual(result['health_requests_including_boundaries'], 2)
        self.assertEqual(result['resource_rows_checked_for_backend'], 0)

    def test_missing_health_without_marker_is_still_rejected(self):
        self.fixture(health_cancel=False)
        with self.assertRaises(FileNotFoundError):
            self.review()

    def test_missing_resource_without_marker_is_still_rejected(self):
        self.fixture(resource_cancel=False)
        with self.assertRaises(FileNotFoundError):
            self.review()

    def test_corrupt_manifest_member_is_still_rejected(self):
        self.fixture()
        (self.root / 'http/health-00000.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'component-file-hash'):
            self.review()

    def test_invalid_cancelled_span_is_rejected(self):
        self.fixture()
        path = self.root / 'http/health-00000.json'
        value = json.loads(path.read_bytes())
        value['remaining_slots'] = True
        path.unlink()
        fact = observation.write_json(path, value)
        manifest = self.root / 'http/manifest.json'
        data = json.loads(manifest.read_bytes())
        data['files'][path.name] = fact
        manifest.unlink()
        observation.write_json(manifest, data)
        with self.assertRaisesRegex(ValueError, 'health-cancelled-span'):
            self.review()

    def test_process_miss_keeps_prior_persistence_interval_and_still_cancels(self):
        clock = [self.origin]
        stopped = [False]
        class Stop:
            def wait(self, seconds):
                if not stopped[0]:
                    clock[0] += round(seconds * 1e9)
                return stopped[0]
            def is_set(self):
                return stopped[0]
            def set(self):
                stopped[0] = True
        original = observation.write_json
        def write(path, value):
            result = original(path, value)
            if Path(path).name == 'process-00000.json':
                clock[0] += 6_000_000_000
            return result
        spec = SimpleNamespace(main=None, backend=None, port=8000)
        with patch.object(observation.time, 'perf_counter_ns', side_effect=lambda: clock[0]), \
                patch.object(observation.binding, 'read_process_binding', return_value={'fixture': True}), \
                patch.object(observation, 'write_json', side_effect=write):
            result = observation.collect_process_window(spec, self.root / 'processes', 12,
                                                         self.origin, Stop())
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(stopped[0])
        row = json.loads((self.root / 'processes/process-00001.json').read_bytes())
        self.assertEqual(row['status'], 'MISSED')
        self.assertEqual(row['observed_ns'], self.origin + 6_000_000_000)
        previous = row['previous_turn']
        self.assertEqual(previous['sample_finished_ns'], self.origin)
        self.assertEqual(previous['persistence_started_ns'], self.origin)
        self.assertEqual(previous['persistence_finished_ns'], self.origin + 6_000_000_000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
