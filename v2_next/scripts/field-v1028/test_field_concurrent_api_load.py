"""Real loopback requests and owned Windows job cleanup, no production contact."""
import io
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
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
        self.image_delay = 0
        picture = io.BytesIO()
        Image.new('RGB', (2, 2), 'red').save(picture, format='JPEG')
        image = picture.getvalue()
        requests = self.requests
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, time.perf_counter_ns()))
                if self.path.endswith('.jpg'):
                    time.sleep(case.image_delay)
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
        self.assertIsNone(worker.receiver)
        self.assertIsNone(result['trigger'])

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

    def test_real_notice_is_available_before_drain_and_matches_retained_record(self):
        self.image_delay = .35
        worker = self.start(6)
        try:
            notice = None
            deadline = time.monotonic() + 6
            while notice is None and time.monotonic() < deadline:
                notice = worker.poll_trigger()
                time.sleep(.01)
            self.assertIsNotNone(notice)
            self.assertTrue(worker.process.is_alive())
            self.assertFalse((self.folder/'closeout.json').exists())
            self.assertEqual((notice['endpoint'], notice['reason']), ('image', 'request-period-overrun'))
            result = worker.finish(request_stop=True)
        finally:
            worker.finish(request_stop=True)
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'CAPTURE_COMPLETE')
        self.assertEqual(result['trigger'], notice)
        self.assertEqual(hashlib.sha256((self.folder/notice['record_file']).read_bytes()).hexdigest(), notice['record_sha256'])
        self.assertIsNone(worker.receiver)

    def test_notice_and_worker_result_disagreement_fails_after_cleanup(self):
        self.image_delay = .35
        worker = self.start(.6)
        try:
            worker.process.join(10)
            self.assertEqual(worker.process.exitcode, 0)
            path = self.folder/'worker-result.json'
            value = json.loads(path.read_bytes())
            self.assertIsNotNone(value['trigger'])
            value['trigger']['record_sha256'] = '0'*64
            path.write_text(json.dumps(value), encoding='utf-8')
            result = worker.finish()
        finally:
            worker.finish(request_stop=True)
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'FAIL')
        self.assertIn('companion-notice-result-mismatch', json.dumps(result['errors']))

    def test_broken_notice_delivery_fails_worker_and_closes_owned_job(self):
        self.image_delay = .35
        worker = self.start(6)
        try:
            worker.receiver.close()
            worker.receiver = None
            worker.process.join(10)
            self.assertEqual(worker.process.exitcode, 1)
            with self.assertRaisesRegex(ValueError, 'companion-exited-during-observation'):
                worker.poll_trigger()
            result = worker.finish()
        finally:
            worker.finish(request_stop=True)
        self.verify_closed(result)
        self.assertEqual(result['load_status'], 'FAIL')
        self.assertFalse(result['forced_termination'])

    def test_spawn_failure_closes_both_pipe_handles(self):
        context = load.multiprocessing.get_context('spawn')
        original = context.Pipe
        opened = []
        def pipe(*args, **kwargs):
            pair = original(*args, **kwargs)
            opened.extend(pair)
            return pair
        with patch.object(context, 'Pipe', side_effect=pipe), \
                patch.object(context.Process, 'start', side_effect=OSError('injected-spawn-failure')):
            with self.assertRaisesRegex(OSError, 'injected-spawn-failure'):
                self.start()
        self.assertEqual(len(opened), 2)
        self.assertTrue(all(handle.closed for handle in opened))
        self.assertEqual(self.requests, [])


class NoticeTests(unittest.TestCase):
    def test_period_and_failure_threshold_boundaries_preserve_existing_contract(self):
        data, image = load.ENDPOINTS
        row = dict(kind='request', request_success=True, scheduled_ns=1_000_000_000,
                   client_request_and_body_ms=500)
        self.assertIsNone(load._trigger_reason(data, row, 1_500_000_000))
        self.assertEqual(load._trigger_reason(data, {**row, 'client_request_and_body_ms': 500.01}, 1_500_010_000),
                         'request-threshold-exceeded')
        self.assertIsNone(load._trigger_reason(image, row, 1_249_999_999))
        self.assertEqual(load._trigger_reason(image, row, 1_250_000_000), 'request-period-overrun')
        self.assertEqual(load._trigger_reason(image, {**row, 'request_success': False}, 1_010_000_000), 'request-error')
        self.assertEqual(load._trigger_reason(image, dict(kind='missed_slot'), 1), 'missed-slot')
        self.assertIsNone(load._trigger_reason(image, dict(kind='cancelled_remaining'), 1))

    def test_concurrent_anomalies_send_only_one_bounded_hash_bound_notice(self):
        messages = []
        class Sender:
            def send_bytes(self, raw):
                messages.append(raw)
        observer = load._FirstAnomaly(Sender())
        origin = time.perf_counter_ns() - 1_000_000_000
        metadata = (json.dumps(dict(kind='missed_slot', sequence=0, scheduled_ns=origin,
                                   queued_ns=origin, reason='scheduler-missed-entire-slot'))+'\n').encode()
        barrier = threading.Barrier(3)
        def send():
            barrier.wait()
            observer(load.ENDPOINTS[1], metadata, time.perf_counter_ns())
        threads = [threading.Thread(target=send) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(messages), 1)
        self.assertLessEqual(len(messages[0]), load.NOTICE_LIMIT)
        notice = json.loads(messages[0])
        self.assertEqual(notice['record_sha256'], hashlib.sha256(metadata).hexdigest())
        self.assertEqual(load._validate_notice(notice, origin, 900), load.ENDPOINTS[1])
        for changed in ({'sequence': True}, {'record_file': '../other.json'}, {'period_ns': 1},
                        {'decision_ns': origin-1}, {'kind': 'cancelled_remaining'}, {'record_sha256': 'g'*64}):
            with self.assertRaises(ValueError):
                load._validate_notice({**notice, **changed}, origin, 900)

    def test_send_failure_is_not_a_successful_notice(self):
        class Sender:
            def send_bytes(self, raw):
                raise OSError('injected-send-failure')
        observer = load._FirstAnomaly(Sender())
        with self.assertRaisesRegex(OSError, 'injected-send-failure'):
            observer(load.ENDPOINTS[1], b'{"kind":"missed_slot","sequence":0,"scheduled_ns":1}', 2)
        self.assertIsNone(observer.notice)

    def test_duplicate_notice_is_rejected_and_hash_disagreement_is_not_completion(self):
        receiver, sender = load.multiprocessing.get_context('spawn').Pipe(duplex=False)
        worker = object.__new__(load.ConcurrentApiLoad)
        worker.origin_ns = time.perf_counter_ns() - 1_000_000_000
        worker.duration_seconds = 900
        worker.receiver, worker.trigger, worker.receipt = receiver, None, None
        worker.process = SimpleNamespace(exitcode=0)
        worker.output = Path('not-read-with-patched-reader')
        metadata = (json.dumps(dict(kind='missed_slot', sequence=0, scheduled_ns=worker.origin_ns,
                                   queued_ns=worker.origin_ns))+'\n').encode()
        observer = load._FirstAnomaly(sender)
        try:
            observer(load.ENDPOINTS[1], metadata, time.perf_counter_ns())
            notice = worker.poll_trigger()
            self.assertEqual(notice, observer.notice)
            sender.send_bytes(json.dumps(notice).encode())
            with self.assertRaisesRegex(ValueError, 'companion-duplicate-notice'):
                worker.poll_trigger()
            sender.close()
            with patch.object(load.observation, 'read_json', return_value=(json.loads(metadata), metadata+b' ')):
                with self.assertRaisesRegex(ValueError, 'companion-notice-record-hash'):
                    worker.verify_trigger({'trigger': notice})
            self.assertIsNone(worker.receiver)
        finally:
            receiver.close()
            sender.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
