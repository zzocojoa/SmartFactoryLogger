"""Actual bounded reader/HTTP integration plus fail-closed stream contracts."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import threading
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import field_python_stream as stream
import field_runner as runner
from field_host_sampling import WindowsProcessReader
import test_field_observation as fixture
from test_field_timing_observation import TIMING_SOURCE


ROOT = Path(os.environ['SFL_PYTHON_STREAM_TEST_ROOT'])
TOOL = Path(os.environ['SFL_PYTHON_STREAM_TOOL'])


def raw_record(value):
    return json.dumps(value, separators=(',', ':')).encode()+b'\n'


def traced_fixture_worker_entry(*args):
    # This test substitutes only the trace handshake. Actual WPR and the frozen
    # launcher are checked in offline Sandbox; memory reads and HTTP are real.
    original_companion, original_collect = stream.companion, stream.collection.collect
    trace = SimpleNamespace(begin=lambda *a: {}, finish=lambda *a: {}, abort=lambda *a: {})
    def companion(*a):
        return original_companion(*a, allow_read_gaps=True)
    def collect(*a, **kw):
        return original_collect(*a, **kw, _trace=trace)
    with patch.object(stream, 'companion', companion), patch.object(stream.collection, 'collect', collect):
        stream.worker_entry(*args)


class DecoderTests(unittest.TestCase):
    def rows(self):
        ready = dict(event='ready', schema='sfl-persistent-python-window-v1', pid=100, created_filetime=200,
            qpc_frequency=10_000_000, init_begin=10, init_end=20, sample_limit=350, interval_ms=20,
            nonblocking=True, atomic_snapshot=False, exact_sample_instant=False)
        frame = dict(name='known_work', filename='fixture.py', module=None, short_filename='fixture.py',
            line=1, locals=None, is_entry=False, is_shim_entry=False)
        stack = dict(pid=100, thread_id=2, thread_name='fixture', os_thread_id=3,
            active=False, owns_gil=False, frames=[frame], process_info=None)
        return [ready, *[dict(event='sample', sequence=i, qpc_begin=30+i*10, qpc_end=31+i*10,
            stacks=[stack], error=None) for i in range(350)], dict(event='finished', samples=350, errors=0,
            cancelled=False, release_gate='HOLD', field_gate='NOT_EVALUATED')]

    def decode(self, rows):
        return stream.decode(b''.join(map(raw_record, rows)), 100, 200, {3: dict(created_filetime=300, stable=True)})

    def test_complete_raw_stream_preserves_native_identity_and_windows(self):
        value = self.decode(self.rows())
        self.assertEqual(len(value['samples']), 350)
        self.assertEqual(value['samples'][4]['parsed']['rows'][0]['created_filetime'], 300)
        self.assertFalse(value['ready']['exact_sample_instant'])

    def test_missing_duplicate_reordered_cancelled_or_failed_samples_rejected(self):
        for kind in ('missing', 'duplicate', 'reversed', 'cancelled', 'failure', 'pid', 'birth', 'extra', 'boolean'):
            rows = self.rows()
            if kind == 'missing': rows.pop(10)
            elif kind == 'duplicate': rows[10]['sequence'] = rows[9]['sequence']
            elif kind == 'reversed': rows[10]['qpc_begin'] = 0
            elif kind == 'cancelled': rows[-1]['cancelled'] = True
            elif kind == 'failure': rows[10]['error'] = 'unreadable'
            elif kind == 'pid': rows[0]['pid'] = 101
            elif kind == 'birth': rows[0]['created_filetime'] = 201
            elif kind == 'extra': rows[0]['extra'] = 1
            else: rows[-1]['errors'] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.decode(rows)

    def test_truncated_and_duplicate_json_keys_rejected(self):
        raw = b''.join(map(raw_record, self.rows()))
        for bad in (raw[:-1], raw.replace(b'"pid":100', b'"pid":100,"pid":100', 1)):
            with self.assertRaises(ValueError): stream.decode(bad, 100, 200, {})

    def test_unbound_thread_remains_unbound(self):
        value = stream.decode(b''.join(map(raw_record, self.rows())), 100, 200, {})
        self.assertEqual(value['samples'][0]['parsed']['status'], 'PARTIAL')

    def test_previous_reader_protocol_and_sample_limit_are_rejected(self):
        for kind in ('schema', 'limit'):
            rows = self.rows()
            rows[0][kind if kind == 'schema' else 'sample_limit'] = (
                'sfl-persistent-python-local-v1' if kind == 'schema' else 100)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.decode(rows)

    def window_fixture(self):
        rows = self.rows()
        for i, row in enumerate(rows[1:-1]):
            row.update(qpc_begin=30+i*200_000, qpc_end=31+i*200_000)
        parsed = self.decode(rows)
        def boundary(qpc):
            return dict(schema='sfl-self-thread-clock-v1', status='OBSERVED', error=None,
                identity=dict(pid=1, native_thread_id=2, process_created_filetime=3, thread_created_filetime=4),
                boundary=dict(qpc_frequency=10_000_000, qpc_ticks=qpc,
                    perf_before_ns=qpc*100, perf_after_ns=qpc*100+1, thread_cpu_ns=qpc))
        runs = [(None, dict(native_begin=boundary(0), native_end=boundary(80_000_000)))]
        return [parsed], runs, dict(origin_ns=250_000_000, duration_seconds=6)

    def test_one_reader_schedule_conservatively_spans_whole_observation(self):
        value = stream.observation_coverage(*self.window_fixture())
        self.assertEqual(value['status'], 'READ_SCHEDULE_SPANS_OBSERVATION_WINDOW')
        self.assertEqual(value['reader_processes'], 1)
        self.assertEqual(value['max_read_start_gap_ms'], 20)
        self.assertFalse(value['continuous_frame_coverage'])

    def test_incomplete_window_restart_and_clock_uncertainty_rejected(self):
        for kind in ('starts-late', 'ends-early', 'restart', 'origin-bool', 'duration', 'clock', 'frequency'):
            decoded, runs, window = self.window_fixture()
            if kind == 'starts-late': window['origin_ns'] = 3000
            elif kind == 'ends-early': window['origin_ns'] = 1_000_000_000
            elif kind == 'restart': decoded *= 2; runs *= 2
            elif kind == 'origin-bool': window['origin_ns'] = True
            elif kind == 'duration': window['duration_seconds'] = 5
            elif kind == 'clock': runs[0][1]['native_end']['identity']['native_thread_id'] = 99
            else: decoded[0]['ready']['qpc_frequency'] = 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                stream.observation_coverage(decoded, runs, window)

    def test_explicit_gap_policy_retains_failed_window_without_frames(self):
        rows = self.rows()
        rows[15].update(stacks=None, error='Failed to call get_stack_trace for thread 3')
        rows[-1]['errors'] = 1
        raw = b''.join(map(raw_record, rows))
        with self.assertRaisesRegex(ValueError, 'stream-sample-read-failed'):
            stream.decode(raw, 100, 200, {})
        parsed = stream.decode(raw, 100, 200, {}, allow_read_gaps=True)
        self.assertEqual(len(parsed['samples']), 350)
        self.assertEqual(parsed['read_errors'][0]['sequence'], 14)
        self.assertIsNone(parsed['samples'][14]['parsed'])
        self.assertEqual(stream.reader_outcome(1, b'SFL_READER_ERROR=reader-incomplete\r\n', parsed),
                         'CAPTURED_WITH_READ_GAPS')
        for code, stderr in ((0, b''), (1, b''), (1, b'other error\n'), (124, b'SFL_READER_ERROR=reader-incomplete\n')):
            with self.subTest(code=code, stderr=stderr), self.assertRaises(ValueError):
                stream.reader_outcome(code, stderr, parsed)

    def test_gap_policy_still_rejects_inconsistent_cancelled_and_all_failed_streams(self):
        for kind in ('count', 'all', 'cancelled', 'non-null-stack', 'empty-error', 'missing', 'clock'):
            rows = self.rows()
            rows[15].update(stacks=None, error='unreadable')
            rows[-1]['errors'] = 1
            if kind == 'count': rows[-1]['errors'] = 2
            elif kind == 'all':
                for row in rows[1:-1]: row.update(stacks=None, error='unreadable')
                rows[-1]['errors'] = 350
            elif kind == 'cancelled': rows[-1]['cancelled'] = True
            elif kind == 'non-null-stack': rows[15]['stacks'] = rows[14]['stacks']
            elif kind == 'empty-error': rows[15]['error'] = ''
            elif kind == 'missing': rows.pop(15)
            else: rows[15]['qpc_end'] = 0
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                stream.decode(b''.join(map(raw_record, rows)), 100, 200, {}, allow_read_gaps=True)

    def test_correlation_excludes_failed_reads_and_rechecks_error_receipt(self):
        rows = self.rows()
        rows[15].update(stacks=None, error='unreadable')
        rows[-1]['errors'] = 1
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder/'stdout.bin').write_bytes(b''.join(map(raw_record, rows)))
            (folder/'stderr.bin').write_bytes(b'SFL_READER_ERROR=reader-incomplete\n')
            result = dict(status='CAPTURED_WITH_READ_GAPS', reader_exit=1,
                threads_after={3:dict(created_filetime=300, stable=True)},
                streams={key:stream.observation.file_fact(folder/(key+'.bin')) for key in ('stdout','stderr')})
            spec = type('Spec',(),dict(backend=type('Backend',(),dict(pid=100))(), backend_created_filetime=200))()
            valid = dict(status='REQUEST_AND_NATIVE_CLOCK_BOUND', qpc_frequency=10_000_000,
                qpc_offset_upper_ns=0,qpc_offset_lower_ns=0,
                checkpoint_qpc_bounds={key:[20,4000] for key in stream.timing.POINTS},
                threads={'worker':dict(tid=3,created_filetime=300)})
            probe = dict(status='REQUEST_AND_RUNTIME_BOUND',probe_id='fixture',health_body_hex=b'{}'.hex(),
                health_record=dict(started_ns=0,response_finished_ns=400_000,client_request_and_body_ms=.4))
            with patch.object(stream.timing,'validate_health_sample',return_value=valid):
                joined = stream.correlate(spec,[(folder,result)],[probe],allow_read_gaps=True)
                self.assertEqual(joined['successful_reads'],349)
                self.assertEqual(joined['failed_reads'],1)
                self.assertEqual(joined['requests'][0]['read_gaps'][0]['sequence'],14)
                self.assertNotIn(14,[s['sequence'] for s in joined['requests'][0]['matches']])
                self.assertEqual(len(joined['requests'][0]['matches']),349)
                self.assertEqual(joined['release_gate'],'HOLD')
                (folder/'stderr.bin').write_bytes(b'other failure\n')
                result['streams']['stderr']=stream.observation.file_fact(folder/'stderr.bin')
                with self.assertRaisesRegex(ValueError,'stream-reader-failed'):
                    stream.correlate(spec,[(folder,result)],[probe],allow_read_gaps=True)

    def test_request_does_not_accept_reader_path_duration_or_other_candidate(self):
        candidate = stream.binding.CANDIDATE_1030
        spec = asdict(stream.observation.TimingObservationSpec('unused', 'unused', None, None, 8000,
            candidate_commit=candidate.commit, backend_created_filetime=200,
            reference_sha256=stream.binding.candidate_reference_sha256(candidate)))
        for role in ('main', 'backend'): spec[role] = dict(pid=1, created=1.0, exe='unused')
        request = dict(schema=runner.SCHEMA, mode='python-health', candidate_commit=candidate.commit,
            signature_policy='UNSIGNED_INTERNAL', duration_seconds=6, spec=spec)
        self.assertEqual(runner.validate_request(request), 'python-health')
        for kind in ('tool', 'duration', 'candidate'):
            bad = deepcopy(request)
            if kind == 'tool': bad['spec']['tool'] = str(TOOL)
            elif kind == 'duration': bad['duration_seconds'] = 900
            else:
                bad['candidate_commit'] = bad['spec']['candidate_commit'] = stream.binding.CANDIDATE_1029.commit
            with self.subTest(kind=kind), self.assertRaises(ValueError): runner.validate_request(bad)

    def test_empty_stack_is_explicit_gap_and_does_not_change_reader_error_count(self):
        for native_error in (False, True):
            rows = self.rows()
            rows[313] = deepcopy(rows[313])
            rows[313]['stacks'][0]['frames'] = []
            if native_error:
                rows[15].update(stacks=None, error='unreadable')
                rows[-1]['errors'] = 1
            raw = b''.join(map(raw_record, rows))
            with self.subTest(native_error=native_error):
                with self.assertRaises(ValueError): stream.decode(raw, 100, 200, {})
                parsed = stream.decode(raw, 100, 200, {}, allow_read_gaps=True)
                self.assertEqual(len(parsed['read_errors']), int(native_error))
                self.assertEqual(parsed['finished']['errors'], int(native_error))
                self.assertEqual(parsed['frame_gaps'], [dict(sequence=312, qpc_begin=3150, qpc_end=3151,
                    error='empty-python-stack', threads=[dict(thread_id=2, os_thread_id=3)])])
                self.assertIsNone(parsed['samples'][312]['parsed'])
                stderr = b'SFL_READER_ERROR=reader-incomplete\n' if native_error else b''
                self.assertEqual(stream.reader_outcome(int(native_error), stderr, parsed), 'CAPTURED_WITH_READ_GAPS')
                with self.assertRaises(ValueError): stream.reader_outcome(1-int(native_error), stderr, parsed)

    def test_empty_stack_policy_does_not_hide_bad_rows_or_all_empty_samples(self):
        for kind in ('pid', 'duplicate', 'flag', 'none', 'oversize', 'later-locals', 'all-empty', 'bad-policy'):
            rows = self.rows()
            rows[15] = deepcopy(rows[15])
            row = rows[15]['stacks'][0]
            row['frames'] = []
            if kind == 'pid': row['pid'] += 1
            elif kind == 'duplicate': rows[15]['stacks'].append(deepcopy(row))
            elif kind == 'flag': row['owns_gil'] = 1
            elif kind == 'none': row['frames'] = None
            elif kind == 'oversize': row['frames'] = deepcopy(rows[14]['stacks'][0]['frames'])*513
            elif kind == 'later-locals':
                other = deepcopy(rows[14]['stacks'][0]);other['thread_id'] = 4;other['os_thread_id'] = 5
                other['frames'][0]['locals'] = {'not-allowed': 'value'}
                rows[15]['stacks'].append(other)
            elif kind == 'all-empty':
                for sample in rows[1:-1]: sample['stacks'][0]['frames'] = []
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                stream.decode(b''.join(map(raw_record, rows)), 100, 200, {},
                              allow_read_gaps=1 if kind == 'bad-policy' else True)

    def test_empty_stack_sample_never_becomes_a_request_function_match(self):
        rows = self.rows()
        rows[15] = deepcopy(rows[15]);rows[15]['stacks'][0]['frames'] = []
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder/'stdout.bin').write_bytes(b''.join(map(raw_record, rows)))
            (folder/'stderr.bin').write_bytes(b'')
            result = dict(status='CAPTURED_WITH_READ_GAPS', reader_exit=0,
                threads_after={3:dict(created_filetime=300, stable=True)},
                streams={key:stream.observation.file_fact(folder/(key+'.bin')) for key in ('stdout','stderr')})
            spec = SimpleNamespace(backend=SimpleNamespace(pid=100), backend_created_filetime=200)
            valid = dict(status='REQUEST_AND_NATIVE_CLOCK_BOUND', qpc_frequency=10_000_000,
                qpc_offset_upper_ns=0, qpc_offset_lower_ns=0,
                checkpoint_qpc_bounds={key:[20,4000] for key in stream.timing.POINTS},
                threads={'worker':dict(tid=3,created_filetime=300)})
            probe = dict(status='REQUEST_AND_RUNTIME_BOUND',probe_id='fixture',health_body_hex=b'{}'.hex(),
                health_record=dict(started_ns=0,response_finished_ns=400_000,client_request_and_body_ms=.4))
            with patch.object(stream.timing,'validate_health_sample',return_value=valid):
                joined = stream.correlate(spec,[(folder,result)],[probe],allow_read_gaps=True)
            self.assertEqual(joined['failed_reads'],0)
            self.assertEqual(joined['successful_reads'],350)
            self.assertEqual(joined['frame_gap_reads'],1)
            self.assertEqual(joined['usable_reads'],349)
            request = joined['requests'][0]
            self.assertEqual(request['coverage'],'READ_GAPS_OVERLAP_REQUEST')
            self.assertEqual(request['read_gaps'][0]['frame_gap']['threads'],[dict(thread_id=2,os_thread_id=3)])
            self.assertNotIn(14,[s['sequence'] for s in request['matches']])
            self.assertEqual(len(request['matches']),349)
            self.assertEqual(joined['release_gate'],'HOLD')


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def collect(self, mode='timing-slow', *, cancel=False, wrong_generation=False, wrong_tool=False):
        folder = ROOT/self._testMethodName
        folder.mkdir()
        # One stable HTTP loop and a prestarted worker allow independent TID
        # creation handles to cover the entire read interval in this fixture.
        source = fixture.BACKEND_SOURCE.replace('class Handler(', TIMING_SOURCE+
            '\nexecutor.submit(lambda: None).result()\nclass Handler(')
        source = source.replace('ThreadingHTTPServer', 'HTTPServer')
        source = source.replace("self.send_response(status);self.send_header('Content-Length',str(len(body)))",
            "self.send_response(status);probe=self.headers.get('X-SFL-Health-Probe');"
            "self.send_header('X-SFL-Health-Timing',diagnostic_header(probe)) if probe else None;"
            "self.send_header('Content-Length',str(len(body)))")
        with patch.object(fixture, 'BACKEND_SOURCE', source), fixture.fixture_app(folder, mode,
                disabled_low_signal=True, candidate=stream.binding.CANDIDATE_1030) as base:
            native = WindowsProcessReader().read(base.backend.pid)
            self.assertEqual(native['status'], 'CAPTURED')
            spec = stream.PythonHealthSpec(**base.__dict__, backend_created_filetime=native['created_100ns']+int(wrong_generation),
                                          tool=str(TOOL))
            if wrong_tool:
                tool = folder/stream.TOOL_NAME
                tool.write_bytes(b'wrong pinned bytes')
                spec = replace(spec, tool=str(tool))
            stop = threading.Event()
            def cancel_after_start():
                deadline = time.monotonic()+20
                while not (folder/'out/evidence/python-started.json').exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                time.sleep(.2)
                stop.set()
            timer = threading.Thread(target=cancel_after_start) if cancel else None
            if timer: timer.start()
            try:
                result = stream.observation.supervise_observation(spec, folder/'out', duration_seconds=6,
                    preparation_timeout=40, finalization_timeout=45, stop_event=stop, _worker_target=traced_fixture_worker_entry)
            finally:
                if timer: timer.join(22)
            self.assertFalse(result['worker_still_alive'])
            self.assertFalse(result['event_reader_still_alive'])
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
            self.assertEqual(result['release_gate'], 'HOLD')
            self.assertFalse(result['promotion_allowed'])
            after = WindowsProcessReader().read(base.backend.pid)
            self.assertEqual(after['status'], 'CAPTURED')
            self.assertEqual(after['created_100ns'], native['created_100ns'])
            worker = json.loads((folder/'out/worker-result.json').read_bytes())
        self.assertEqual(json.loads((folder/'fixture-exit.json').read_bytes())['exit_code'], 0)
        return folder, result, worker

    def test_slow_requests_join_known_function_and_native_generations(self):
        folder, result, worker = self.collect()
        self.assertEqual(result['supervisor_status'], 'PASS', worker['errors'])
        self.assertEqual(worker['observation_status'], 'PASS', worker['errors'])
        joined = json.loads((folder/'out/python-stream/correlation.json').read_bytes())
        self.assertEqual(len(joined['requests']), 3)
        for request in joined['requests']:
            self.assertGreater(request['request_ms'], 200)
            matched = [role for match in request['matches'] if 'plc_done' in match['contained_intervals']
                       for role in match['bound_roles'] if role['role'] == 'worker'
                       and any(frame['name'] == 'work' for frame in role['frames'])]
            self.assertTrue(matched, request)
        self.assertEqual(joined['latency_cause'], 'UNDETERMINED')
        self.assertEqual(joined['etw_coverage'], 'NOT_EVALUATED')
        self.assertEqual(joined['observation_window']['reader_processes'], 1)
        self.assertEqual(joined['observation_window']['status'], 'READ_SCHEDULE_SPANS_OBSERVATION_WINDOW')
        self.assertFalse(joined['observation_window']['continuous_frame_coverage'])
        self.assertFalse((folder/'out/python-stream/burst-1').exists())
        for index in range(1):
            burst = json.loads((folder/f'out/python-stream/burst-{index}/result.json').read_bytes())
            self.assertEqual(burst['reader_exit'], int(burst['failed_reads'] > 0))
            self.assertEqual(len(burst['read_windows']), 350)
            self.assertTrue(burst['reader_threads_closed'])
        # The persisted validation verdict is not trusted in place of the raw
        # HTTP evidence, and raw body tampering cannot produce a frame join.
        ready = json.loads((folder/'fixture-ready.json').read_bytes())
        probe = json.loads((folder/'out/evidence/probe-000.json').read_bytes())
        spec = type('Identity', (), dict(backend=type('Backend', (), dict(pid=ready['ready']['backend']['pid']))(),
                                      backend_created_filetime=probe['expected_backend_created_filetime']))()
        runs = [(folder/f'out/python-stream/burst-{i}',
                 json.loads((folder/f'out/python-stream/burst-{i}/result.json').read_bytes())) for i in range(1)]
        spoofed = deepcopy(probe)
        spoofed['validation'] = {'status': 'FAKE_VERDICT'}
        self.assertEqual(len(stream.correlate(spec, runs, [spoofed], allow_read_gaps=True)['requests']), 1)
        spoofed['health_body_hex'] = b'{}'.hex()
        with self.assertRaisesRegex(ValueError, 'stream-request-clock'):
            stream.correlate(spec, runs, [spoofed], allow_read_gaps=True)
        wrong_birth = type('Identity', (), dict(backend=spec.backend, backend_created_filetime=spec.backend_created_filetime+1))()
        with self.assertRaisesRegex(ValueError, 'stream-ready-identity'):
            stream.correlate(wrong_birth, runs, [probe], allow_read_gaps=True)

    def test_changed_configuration_fails_after_raw_capture(self):
        folder, result, worker = self.collect('configuration-changed')
        self.assertEqual(result['supervisor_status'], 'FAIL')
        self.assertIn('final-configuration-binding', json.dumps(worker))
        self.assertTrue((folder/'out/python-stream/correlation.json').is_file())

    def test_cancel_preserves_target_and_partial_raw_bytes(self):
        folder, result, worker = self.collect(cancel=True)
        self.assertEqual(result['supervisor_status'], 'FAIL')
        self.assertTrue(worker['stop_requested'])
        self.assertTrue((folder/'out/python-stream/burst-0/stdout.bin').is_file())
        self.assertFalse((folder/'out/python-stream/correlation.json').exists())
        aborted = json.loads((folder/'out/evidence/python-abort.json').read_bytes())
        self.assertTrue(aborted['background_closed'])
        self.assertIn('burst-0/stdout.bin', aborted['files'])

    def test_wrong_generation_prevents_reader(self):
        folder, result, worker = self.collect(wrong_generation=True)
        self.assertEqual(result['supervisor_status'], 'FAIL')
        self.assertFalse((folder/'out/python-stream').exists())
        self.assertEqual(worker['samples'], [])

    def test_wrong_tool_prevents_reader_and_probes(self):
        folder, result, worker = self.collect(wrong_tool=True)
        self.assertEqual(result['supervisor_status'], 'FAIL')
        self.assertEqual(worker['samples'], [])
        burst = json.loads((folder/'out/python-stream/burst-0/result.json').read_bytes())
        self.assertIsNone(burst['reader_pid'])
        self.assertIn('stream-tool-pin', json.dumps(burst))


if __name__ == '__main__': unittest.main()
