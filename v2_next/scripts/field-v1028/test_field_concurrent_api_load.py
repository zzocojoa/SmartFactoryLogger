"""Real loopback requests and owned Windows job cleanup, no production contact."""
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from PIL import Image
import field_concurrent_api_load as load


ROOT = Path(os.environ['SFL_CONCURRENT_API_TEST_ROOT'])


class CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT/str(len(list(ROOT.iterdir())))
        self.requests = []
        picture = io.BytesIO()
        Image.new('RGB', (2, 2), 'red').save(picture, format='JPEG')
        image = picture.getvalue()
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, time.perf_counter_ns()))
                body = image if self.path.endswith('.jpg') else b'{"fixture":true}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Content-Type', 'image/jpeg' if self.path.endswith('.jpg') else 'application/json')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def start(self, duration=.6):
        origin = time.perf_counter_ns() + 3_000_000_000
        return load.ConcurrentApiLoad(self.server.server_port, self.folder,
            duration_seconds=duration, origin_ns=origin)

    def verify_closed(self, result):
        self.assertFalse(result['worker_still_alive'])
        self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
        self.assertFalse(result['promotion_allowed'])

    def test_complete_window_has_only_data_and_image_at_existing_periods(self):
        worker = self.start(6.2)
        result = worker.finish()
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'CAPTURE_COMPLETE')
        self.assertFalse(result['forced_termination'])
        self.assertEqual(result['worker_exit_code'], 0)
        self.assertEqual({path for path, _ in self.requests}, {'/api/data', '/api/spot/live_image.jpg'})
        self.assertTrue(all(when >= worker.origin_ns for _, when in self.requests))
        origin = json.loads((self.folder/'requests/origin.json').read_bytes())
        self.assertEqual(origin['period_ns'], {'data': 6_000_000_000, 'image': 250_000_000})
        self.assertEqual(origin['expected_slots'], {'data': 2, 'image': 25})
        summary = json.loads((self.folder/'requests/summary.json').read_bytes())
        self.assertGreaterEqual(summary['finished_ns'], origin['origin_ns'] + origin['duration_ns'])
        for path in (self.folder/'requests').glob('*.json'):
            record = json.loads(path.read_bytes())
            if record.get('kind') == 'request':
                self.assertGreaterEqual(record['started_ns'], record['scheduled_ns'], path.name)
                self.assertGreaterEqual(record['start_lateness_ms'], 0, path.name)
        self.assertIs(worker.finish(), result)

    def exercise_worker_wait(self, *, collector_fails):
        class EarlyEvent:
            def __init__(self):
                self.flag = threading.Event()

            def is_set(self):
                return self.flag.is_set()

            def set(self):
                self.flag.set()

            def wait(self, seconds):
                # Model a timeout return before its requested deadline.
                return self.flag.is_set()

        gate, ready, external = threading.Event(), threading.Event(), EarlyEvent()
        gate.set()
        self.folder.mkdir()
        observed, bridges = [], []
        original_stop = load.observation.ObservationStop

        def make_stop(event):
            bridge = original_stop(event)
            bridges.append(bridge)
            return bridge

        def collect(_port, _output, **kwargs):
            local = kwargs['stop_event']
            before = time.perf_counter_ns()
            self.assertFalse(local.wait(.03))
            observed.append(time.perf_counter_ns() - before)
            if collector_fails:
                raise OSError('injected-collector-failure')
            return dict(persistence={name: 0 for name in ('pending_bytes', 'pending_records',
                        'discarded_records', 'submitted_records', 'persisted_records')},
                        worker_errors=[], persistence_errors=[])

        stdout, stderr = sys.stdout, sys.stderr
        try:
            with patch.object(load.observation, 'ObservationStop', side_effect=make_stop), \
                    patch.object(load.http, 'collect_http_window', side_effect=collect), \
                    patch.object(load.observation, 'verify_component_manifest', return_value={}):
                with self.assertRaises(SystemExit) as ended:
                    load._worker(gate, ready, external, self.server.server_port,
                                 self.folder, .1, time.perf_counter_ns()+1_000_000_000)
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        self.assertEqual(ended.exception.code, 1 if collector_fails else 0)
        self.assertEqual(len(observed), 1)
        self.assertGreaterEqual(observed[0], 30_000_000)
        self.assertEqual(len(bridges), 1)
        self.assertFalse(bridges[0].bridge.is_alive())
        if collector_fails:
            result = json.loads((self.folder/'worker-result.json').read_bytes())
            self.assertIn('injected-collector-failure', json.dumps(result['errors']))

    def test_early_wait_return_cannot_advance_worker_request_deadline(self):
        self.exercise_worker_wait(collector_fails=False)

    def test_collector_failure_closes_cancellation_bridge(self):
        self.exercise_worker_wait(collector_fails=True)

    def test_early_stop_preserves_cancelled_slots_without_a_performance_pass(self):
        worker = self.start(6)
        time.sleep(max(0, (worker.origin_ns - time.perf_counter_ns())/1e9) + .3)
        worker.request_stop()
        result = worker.finish()
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'CAPTURE_COMPLETE')
        self.assertEqual(result['http_component_status'], 'FAIL')
        self.assertGreater(result['channels']['image']['cancelled_slots'], 0)
        self.assertFalse(result['forced_termination'])
        self.assertEqual(result['worker_exit_code'], 0)

    def test_deadline_terminates_only_owned_job_and_preserves_failure(self):
        worker = self.start(6)
        result = worker.finish(_join_seconds=.02)
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'FAIL')
        self.assertTrue(result['forced_termination'])
        self.assertNotEqual(result['worker_exit_code'], 0)
        self.assertEqual(self.requests, [])

    def test_assignment_failure_never_opens_request_gate(self):
        with patch.object(load.CollectorJob, 'assign_owned_process', side_effect=OSError('injected-assignment-failure')):
            with self.assertRaisesRegex(OSError, 'injected-assignment-failure'):
                self.start()
        result = json.loads((self.folder/'closeout.json').read_bytes())
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'FAIL')
        self.assertEqual(self.requests, [])

    def test_completed_child_with_changed_body_cannot_claim_capture_complete(self):
        worker = self.start()
        worker.process.join(10)
        self.assertEqual(worker.process.exitcode, 0)
        bodies = sorted((self.folder/'requests').glob('*.body'))
        self.assertTrue(bodies)
        with bodies[0].open('ab') as stream:
            stream.write(b'fixture-tampering')
        result = worker.finish()
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'FAIL')
        self.assertIn('component-file-hash', json.dumps(result['errors']))
        self.assertFalse(result['forced_termination'])

    def test_unrequested_stop_cannot_claim_capture_complete(self):
        worker = self.start(6)
        worker.stop.set()
        result = worker.finish()
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'FAIL')
        self.assertIn('companion-unrequested-stop', json.dumps(result['errors']))
        self.assertFalse(result['forced_termination'])
        self.assertEqual(self.requests, [])

    def test_invalid_port_duration_and_origin_prevent_output_creation(self):
        for port, duration, origin in [(True, 1, time.perf_counter_ns()+1_000_000_000),
                (8000, 901, time.perf_counter_ns()+1_000_000_000),
                (8000, float('nan'), time.perf_counter_ns()+1_000_000_000), (8000, 1, 1)]:
            with self.assertRaises(ValueError):
                load.ConcurrentApiLoad(port, self.folder, duration_seconds=duration, origin_ns=origin)
            self.assertFalse(self.folder.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
