"""Collection failure propagation with synthetic component boundaries."""
from contextlib import contextmanager, ExitStack
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
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
                       closeout_error=False, stop=None, duration=.01, trace=None, outlier=False, concurrent=False,
                       event_query=None, ready_stacks=False, python_frames=None):
        @contextmanager
        def reference(*args, **kwargs):
            self.assertEqual(kwargs['candidate'], self.spec.candidate)
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
            stack.enter_context(patch.object(collection.system_events, 'capture',
                side_effect=event_query or (lambda *args: dict(query_status='COMPLETE',
                    events=[], matched_record_count=0, errors=[]))))
            result = collection.collect(self.spec, self.folder, duration, stop or threading.Event(), events.append,
                                        _trace=trace, _outlier=outlier, _concurrent_api=concurrent,
                                        _ready_stacks=ready_stacks, _python_frames=python_frames)
            if payload.called:
                self.assertEqual(payload.call_args.kwargs['candidate'], self.spec.candidate)
        self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
        self.assertEqual(result['release_gate'], 'HOLD')
        self.assertFalse(result['promotion_allowed'])
        return result, events, call.call_count

    def test_event_query_runs_after_trace_and_final_binding_and_is_manifest_bound(self):
        phases = []
        trace = SimpleNamespace(begin=lambda *args: {},
            finish=lambda *args: phases.append('trace-finished') or {}, abort=phases.append)
        def capture(start, end, stop):
            self.assertEqual(phases, ['trace-finished'])
            self.assertTrue((self.folder/'evidence/payload-closeout.json').exists())
            self.assertGreaterEqual((end-start).total_seconds(), 120)
            phases.append('events')
            return dict(query_status='COMPLETE', events=[], matched_record_count=0, errors=[])
        result, _, _ = self.run_collection(trace=trace, event_query=capture)
        self.assertEqual(result['collection_status'], 'BOUND_WINDOW_CAPTURED')
        self.assertEqual(result['system_event_query_status'], 'COMPLETE')
        self.assertEqual(phases, ['trace-finished', 'events'])
        manifest = json.loads((self.folder/'evidence/manifest.json').read_bytes())
        self.assertIn('system-events.json', manifest['files'])
        (self.folder/'evidence/system-events.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'component-file-hash'):
            collection.observation.verify_component_manifest(self.folder/'evidence', 32)

    def test_incomplete_query_is_saved_and_prevents_collection_completion(self):
        partial = dict(query_status='INCOMPLETE', events=[{'record_id': 5}],
                       matched_record_count=None, errors=[{'stage': 'next', 'winerror': 5}])
        result, _, count = self.run_collection(event_query=lambda *args: partial)
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 1))
        self.assertEqual(result['system_event_query_status'], 'INCOMPLETE')
        self.assertIn('system-event-query-incomplete', json.dumps(result))
        self.assertEqual(json.loads((self.folder/'evidence/system-events.json').read_bytes()), partial)

    def test_failed_binding_never_claims_an_event_query(self):
        def forbidden(*args):
            self.fail('event query after failed binding')
        result, _, _ = self.run_collection(native=[{'status': 'UNAVAILABLE'}], event_query=forbidden)
        self.assertEqual(result['system_event_query_status'], 'NOT_ATTEMPTED')

    def test_slow_bound_response_is_preserved_without_performance_pass(self):
        result, events, count = self.run_collection()
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 1))
        self.assertEqual([e['phase'] for e in events], ['observing', 'finalizing'])
        raw = json.loads((self.folder/'evidence/probe-000.json').read_bytes())
        self.assertEqual(raw['health_record']['client_request_and_body_ms'], 250)
        self.assertEqual(result['etw_coverage'], 'NOT_EVALUATED')

    def test_diagnostic_default_is_1029_and_mixed_candidate_prevents_collection(self):
        self.assertEqual(self.spec.candidate, collection.binding.CANDIDATE_1029)
        self.spec = replace(self.spec, candidate_commit=collection.binding.BUILD)
        with self.assertRaisesRegex(ValueError, 'diagnostic-candidate-required'):
            self.run_collection()

    def test_1030_is_bound_to_both_payload_and_configuration_references(self):
        self.spec = replace(self.spec, candidate_commit=collection.binding.CANDIDATE_1030.commit)
        result, _, count = self.run_collection()
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 1))

    def test_1030_generation_change_retains_raw_probe_and_fails_collection(self):
        self.spec = replace(self.spec, candidate_commit=collection.binding.CANDIDATE_1030.commit)
        result, _, count = self.run_collection(native=[
            dict(status='CAPTURED', pid=101, created_100ns=1000),
            dict(status='CAPTURED', pid=101, created_100ns=1001)])
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 1))
        self.assertTrue((self.folder/'evidence/probe-000.json').is_file())

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

    def test_python_stream_is_inside_trace_and_cleanup_precedes_trace_abort(self):
        self.spec = replace(self.spec, candidate_commit=collection.binding.CANDIDATE_1030.commit)
        for failure in (None, 'start', 'finish'):
            if failure is not None: self.setUp(); self.spec = replace(self.spec, candidate_commit=collection.binding.CANDIDATE_1030.commit)
            phases = []
            def step(name, value):
                phases.append(name)
                if failure == name: raise ValueError('injected-python-'+name)
                return value
            companion = SimpleNamespace(start=lambda: step('start', {}),
                finish=lambda probes, origin_ns: step('finish', dict(status='CAPTURED', count=len(probes), origin_ns=origin_ns)),
                abort=lambda: step('python-abort', dict(background_closed=True)))
            trace = SimpleNamespace(begin=lambda *args: step('trace-begin', {}),
                finish=lambda *args: step('trace-finish', {}), abort=lambda *args: step('trace-abort', {}))
            fake_time = {'ns': 1_000_000_000}
            def wait(seconds): fake_time['ns'] += round(seconds*1e9); return False
            stop = SimpleNamespace(is_set=lambda: False, wait=wait, set=lambda: None)
            probe = dict(status='REQUEST_AND_RUNTIME_BOUND', health_record={}, probe_id='a'*32)
            with patch.object(collection.time, 'perf_counter_ns', side_effect=lambda: fake_time['ns']):
                result, _, count = self.run_collection(duration=6, stop=stop, probes=[probe]*3,
                                                       trace=trace, python_frames=companion)
            if failure is None:
                self.assertEqual(phases, ['trace-begin', 'start', 'finish', 'trace-finish'])
                self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 3))
                completion = json.loads((self.folder/'evidence/python-completion.json').read_bytes())
                self.assertEqual(completion['count'], 3)
            else:
                self.assertEqual(result['collection_status'], 'INCOMPLETE')
                self.assertEqual(phases[-2:], ['python-abort', 'trace-abort'])
                self.assertNotIn('trace-finish', phases)
                self.assertTrue((self.folder/'evidence/python-abort.json').is_file())

    def run_outlier(self, latencies, *, bound=True, concurrent=False, fail_at=None,
                    notice_at=None, late_notice=False, ready_stacks=False):
        clock = {'ns': 1_000_000_000, 'stop': False}
        def wait(seconds):
            clock['ns'] += round(seconds * 1e9)
            return clock['stop']
        stop = SimpleNamespace(wait=wait, is_set=lambda: clock['stop'], set=lambda: clock.update(stop=True))
        values = iter(latencies)
        def probe(*args, **kwargs):
            elapsed = next(values)
            clock['ns'] += round(elapsed * 1e6)
            return dict(status='REQUEST_AND_RUNTIME_BOUND' if bound else 'NOT_BOUND', probe_id=kwargs['probe_id'],
                        health_record=dict(client_request_and_body_ms=elapsed, response_finished_ns=clock['ns']))
        phases = []
        def trace_phase(name):
            if concurrent or name != 'begin':
                phases.append(name)
            if fail_at == 'trace-'+name:
                raise ValueError('injected-trace-'+name)
            return {}
        trace = SimpleNamespace(begin=lambda *args: trace_phase('begin'),
                                finish=lambda *args: trace_phase('finish'), abort=lambda *args: trace_phase('abort'))
        case = self
        notice = dict(endpoint='image', sequence=0, reason='request-period-overrun', fixture=True)
        class Companion:
            def __init__(self, port, folder, *, duration_seconds, origin_ns):
                case.assertTrue(concurrent)
                phases.append('load-start')
                if fail_at == 'load-start':
                    raise ValueError('injected-load-start')
                case.assertEqual((port, duration_seconds, origin_ns), (8000, 900, clock['ns']+3_000_000_000))
                folder.mkdir()
                collection.observation.write_json(folder/'started.json', {'fixture': True})
                self.stopped = False
                self.polls = 0
                self.notice = None

            def request_stop(self):
                if not self.stopped:
                    phases.append('load-stop')
                    self.stopped = True

            def poll_trigger(self):
                self.polls += 1
                if fail_at == 'load-poll':
                    raise ValueError('injected-load-poll')
                if notice_at is not None and self.polls >= notice_at:
                    self.notice = notice
                return self.notice

            def finish(self):
                phases.append('load-finish')
                return dict(load_status='FAIL' if fail_at == 'load-finish' else 'CAPTURE_COMPLETE',
                            trigger=notice if late_notice else self.notice,
                            release_gate='HOLD', promotion_allowed=False)

        with patch.object(collection.time, 'perf_counter_ns', lambda: clock['ns']), \
                patch.object(collection, 'ConcurrentApiLoad', Companion):
            result, events, count = self.run_collection(duration=900, stop=stop, trace=trace,
                                                       outlier=True, probes=probe, concurrent=concurrent,
                                                       ready_stacks=ready_stacks)
        return result, count, phases

    def test_concurrent_trigger_stops_trace_before_waiting_for_companion(self):
        result, count, phases = self.run_outlier([200, 200.01, 999], concurrent=True)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 2))
        self.assertEqual(phases, ['begin', 'load-start', 'load-stop', 'finish', 'load-finish'])
        self.assertEqual(result['scope'], 'CPU_CONCURRENT_CAPTURE_NOT_FIELD_PERFORMANCE')
        self.assertEqual(result['trigger']['sequence'], 1)
        for name in ('concurrent-api-started.json', 'concurrent-api-closeout.json'):
            self.assertTrue((self.folder/'evidence'/name).is_file())

    def test_ready_trace_preserves_trigger_cleanup_and_scope(self):
        result, count, phases = self.run_outlier([200, 200.01, 999], concurrent=True, ready_stacks=True)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 2))
        self.assertEqual(result['scope'], 'READY_CONCURRENT_CAPTURE_NOT_FIELD_PERFORMANCE')
        self.assertLess(phases.index('finish'), phases.index('load-finish'))
        self.assertFalse(result['promotion_allowed'])

    def test_concurrent_no_trigger_preserves_full_health_schedule(self):
        result, count, phases = self.run_outlier([10]*450, concurrent=True)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 450))
        self.assertEqual(phases, ['begin', 'load-start', 'finish', 'load-finish'])
        self.assertEqual(result['finished_ns'] - result['origin_ns'], 900_000_000_000)

    def test_companion_notice_before_first_health_preserves_initial_and_final_binding(self):
        result, count, phases = self.run_outlier([], concurrent=True, notice_at=1)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 0))
        self.assertEqual(phases, ['begin', 'load-start', 'load-stop', 'finish', 'load-finish'])
        self.assertEqual(result['trigger']['source'], 'companion')
        self.assertTrue((self.folder/'evidence/runtime-final.json').is_file())

    def test_same_probe_health_outlier_and_companion_notice_both_survive(self):
        result, count, _ = self.run_outlier([250], concurrent=True, notice_at=3)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 1))
        self.assertEqual(result['trigger']['source'], 'health')
        self.assertEqual(result['concurrent_trigger']['endpoint'], 'image')

    def test_final_tail_notice_stops_companion_and_late_notice_cannot_claim_trace_trigger(self):
        # Three polls per health slot, then one after the final interval tail.
        result, count, phases = self.run_outlier([10]*450, concurrent=True, notice_at=1351)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 450))
        self.assertEqual(result['trigger']['source'], 'companion')
        self.assertIn('load-stop', phases)
        self.setUp()
        result, count, _ = self.run_outlier([250], concurrent=True, late_notice=True)
        self.assertEqual((result['collection_status'], count), ('BOUND_WINDOW_CAPTURED', 1))
        self.assertEqual(result['trigger']['source'], 'health')
        self.assertIsNone(result['concurrent_trigger'])
        self.assertEqual(result['late_concurrent_trigger']['endpoint'], 'image')

    def test_poll_failure_aborts_trace_and_still_drains_companion(self):
        result, count, phases = self.run_outlier([], concurrent=True, fail_at='load-poll')
        self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 0))
        self.assertEqual(phases, ['begin', 'load-start', 'load-stop', 'abort', 'load-finish'])

    def test_concurrent_unbound_probe_stops_and_drains_even_if_abort_publication_fails(self):
        for failed in (None, 'trace-abort'):
            self.setUp()
            result, count, phases = self.run_outlier([250], bound=False, concurrent=True, fail_at=failed)
            self.assertEqual((result['collection_status'], count), ('INCOMPLETE', 1))
            self.assertEqual(phases, ['begin', 'load-start', 'load-stop', 'abort', 'load-finish'])
            self.assertIsNone(result['trigger'])
            if failed:
                self.assertIn('trace-abort-publication-failed', json.dumps(result))

    def test_concurrent_start_trace_finish_and_drain_failures_prevent_completion(self):
        expected = {
            'load-start': ['begin', 'load-start', 'abort'],
            'trace-finish': ['begin', 'load-start', 'load-stop', 'finish', 'abort', 'load-finish'],
            'load-finish': ['begin', 'load-start', 'load-stop', 'finish', 'load-finish', 'abort'],
        }
        for failed, phases in expected.items():
            self.setUp()
            result, _, actual = self.run_outlier([250], concurrent=True, fail_at=failed)
            self.assertEqual(result['collection_status'], 'INCOMPLETE')
            self.assertEqual(actual, phases)

    def test_concurrent_mode_cannot_be_enabled_for_short_or_untraced_collection(self):
        for value in (True, 1, None):
            with self.assertRaisesRegex(ValueError, 'concurrent-api-requires-bounded-outlier-trace'):
                self.run_collection(concurrent=value)

    def test_concurrent_real_child_http_and_cleanup_with_synthetic_health_binding(self):
        # Real loopback data/image, spawn, Job, files and exit; app/health/WPR
        # boundaries remain explicit fixtures. This never contacts the server.
        picture = io.BytesIO()
        Image.new('RGB', (2, 2), 'red').save(picture, format='JPEG')
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                body = picture.getvalue() if self.path.endswith('.jpg') else b'{"fixture":true}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Content-Type', 'image/jpeg' if self.path.endswith('.jpg') else 'application/json')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            for fail_trace in (False, True):
                self.setUp()
                self.spec = replace(self.spec, port=server.server_port)
                phases = []
                def slow_probe(*args, **kwargs):
                    time.sleep(.35)
                    return dict(status='REQUEST_AND_RUNTIME_BOUND', probe_id=kwargs['probe_id'],
                        health_record=dict(client_request_and_body_ms=350, response_finished_ns=time.perf_counter_ns()))
                def finish_trace(*args):
                    self.assertFalse((self.folder/'evidence/concurrent-api-closeout.json').exists())
                    phases.append(time.perf_counter_ns())
                    if fail_trace:
                        raise ValueError('injected-trace-save-failure')
                    return {'fixture': True}
                trace = SimpleNamespace(begin=lambda *args: {}, finish=finish_trace, abort=lambda *args: None)
                result, _, count = self.run_collection(duration=900, trace=trace, outlier=True,
                                                       concurrent=True, probes=slow_probe)
                self.assertEqual(count, 1)
                self.assertEqual(result['collection_status'], 'INCOMPLETE' if fail_trace else 'BOUND_WINDOW_CAPTURED')
                closed = json.loads((self.folder/'evidence/concurrent-api-closeout.json').read_bytes())
                self.assertEqual((closed['load_status'], closed['worker_exit_code']), ('CAPTURE_COMPLETE', 0))
                self.assertEqual(closed['job_after_cleanup']['active_processes'], 0)
                self.assertFalse(closed['forced_termination'])
                self.assertLessEqual(closed['stop_requested_ns'], phases[0])
                self.assertLess(phases[0], closed['finished_ns'])
                self.assertEqual(closed['http_component_status'], 'FAIL')
                self.assertGreater(closed['channels']['image']['cancelled_slots'], 0)
            self.assertEqual(set(requests), {'/api/data', '/api/spot/live_image.jpg'})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())

    def test_outlier_uses_strict_threshold_and_finishes_after_first_bound_outlier(self):
        result, count, phases = self.run_outlier([200, 200.01, 999])
        self.assertEqual((count, phases), (2, ['finish']))
        self.assertEqual(result['collection_status'], 'BOUND_WINDOW_CAPTURED')
        self.assertEqual(result['trigger_status'], 'OUTLIER_CAPTURED_REQUIRES_CORRELATION')
        self.assertEqual(result['trigger']['sequence'], 1)
        self.assertLess(result['finished_ns'] - result['origin_ns'], 3_000_000_000)
        trigger = json.loads((self.folder/'evidence/trigger.json').read_bytes())
        self.assertEqual((trigger['probes'], trigger['expected_slots']), (2, 450))
        self.assertEqual(trigger['trigger'], result['trigger'])

    def test_image_overrun_preserves_trace_while_health_stays_fast(self):
        picture = io.BytesIO()
        Image.new('RGB', (2, 2), 'red').save(picture, format='JPEG')
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                is_image = self.path.endswith('.jpg')
                if is_image and requests.count(self.path) == 1:
                    time.sleep(.35)
                body = picture.getvalue() if is_image else b'{"fixture":true}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Content-Type', 'image/jpeg' if is_image else 'application/json')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        stop = threading.Event()
        deadline = threading.Timer(8, stop.set)
        deadline.start()
        phases = []
        try:
            self.spec = replace(self.spec, port=server.server_port)
            def probe(*args, **kwargs):
                return dict(status='REQUEST_AND_RUNTIME_BOUND', probe_id=kwargs['probe_id'],
                    health_record=dict(client_request_and_body_ms=10, response_finished_ns=time.perf_counter_ns()))
            def finish(*args):
                phases.append('trace-finish')
                self.assertFalse((self.folder/'evidence/concurrent-api-closeout.json').exists())
                return {'fixture': True}
            trace = SimpleNamespace(begin=lambda *args: {}, finish=finish, abort=lambda *args: phases.append('abort'))
            result, _, count = self.run_collection(duration=900, stop=stop, trace=trace,
                outlier=True, concurrent=True, probes=probe)
            self.assertEqual(result['collection_status'], 'BOUND_WINDOW_CAPTURED')
            self.assertEqual(phases, ['trace-finish'])
            self.assertLess(count, 450)
            self.assertEqual(result['trigger_status'], 'COMPANION_ANOMALY_CAPTURED_REQUIRES_CORRELATION')
            self.assertEqual(result['trigger']['source'], 'companion')
            self.assertEqual(result['concurrent_trigger']['endpoint'], 'image')
            closed = json.loads((self.folder/'evidence/concurrent-api-closeout.json').read_bytes())
            self.assertEqual(closed['load_status'], 'CAPTURE_COMPLETE')
            self.assertEqual(closed['trigger'], result['concurrent_trigger'])
            self.assertEqual(closed['job_after_cleanup']['active_processes'], 0)
            self.assertFalse(closed['forced_termination'])
        finally:
            deadline.cancel()
            deadline.join()
            server.shutdown()
            server.server_close()
            thread.join(2)
            self.assertFalse(thread.is_alive())

    def test_no_outlier_preserves_all_450_probes_and_does_not_claim_performance_pass(self):
        result, count, phases = self.run_outlier([10] * 450)
        self.assertEqual((count, phases), (450, ['finish']))
        self.assertEqual(result['trigger_status'], 'NO_OUTLIER_OBSERVED')
        self.assertEqual(result['collection_status'], 'BOUND_WINDOW_CAPTURED')
        self.assertIsNone(result['trigger'])
        self.assertEqual(result['finished_ns'] - result['origin_ns'], 900_000_000_000)
        self.assertEqual(len(list((self.folder/'evidence').glob('probe-*.json'))), 450)

    def test_slow_unbound_probe_aborts_without_a_valid_outlier_claim(self):
        result, count, phases = self.run_outlier([250], bound=False)
        self.assertEqual((result['collection_status'], count, phases), ('INCOMPLETE', 1, ['abort']))
        self.assertEqual(result['trigger_status'], 'NOT_EVALUATED')
        self.assertIsNone(result['trigger'])

    def test_outlier_mode_cannot_use_untraced_or_arbitrary_duration_collection(self):
        for seconds in (6, 899, 901, True, 900.0):
            with self.assertRaisesRegex(ValueError, 'outlier-fixed-bounded-trace-required'):
                self.run_collection(duration=seconds, trace=object(), outlier=True)
        with self.assertRaisesRegex(ValueError, 'outlier-fixed-bounded-trace-required'):
            self.run_collection(duration=900, outlier=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
