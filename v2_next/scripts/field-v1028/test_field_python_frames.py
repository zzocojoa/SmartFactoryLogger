"""Fixed-input contracts and real read-only native identities on owned fixtures."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import unittest
from unittest.mock import patch

import field_native_timing as clock
import field_python_frames as frames
import field_runner as runner
from field_thread_identity import NativeTarget
from field_resource_sampling import ProcessIdentity

ROOT = Path(os.environ['SFL_PYTHON_FRAMES_TEST_ROOT'])
FIXTURE_ROOT = Path(os.environ['SFL_PYTHON_FRAMES_FIXTURE_ROOT'])


def request():
    candidate = frames.binding.CANDIDATE_1030
    spec = frames.observation.TimingObservationSpec(str(ROOT/'app'), str(ROOT/'payload.json'),
        ProcessIdentity(10, 1.0, str(ROOT/'app/main.exe')),
        ProcessIdentity(20, 2.0, str(ROOT/'app/backend.exe')), 8000,
        reference_sha256=frames.binding.candidate_reference_sha256(candidate),
        configuration_reference=str(ROOT/'configuration.json'), configuration_reference_sha256='a'*64,
        candidate_commit=candidate.commit, backend_created_filetime=134367234222163258)
    return dict(schema=runner.SCHEMA, mode='python-frames', signature_policy='UNSIGNED_INTERNAL',
                candidate_commit=candidate.commit, duration_seconds=6, spec=asdict(spec))


class FrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)
        (ROOT/'app').mkdir()
        (ROOT/'package').mkdir()
        for name in ('payload.json', 'configuration.json', 'wrong.exe', 'package/py-spy.exe'):
            (ROOT/name).write_text('{}', encoding='utf-8')

    def test_request_rejects_unfixed_duration_tool_and_candidate(self):
        good = request()
        self.assertEqual(runner.validate_request(good), 'python-frames')
        for duration in (True, 0, 3, 6.0, 7, 900):
            bad = deepcopy(good);bad['duration_seconds'] = duration
            with self.assertRaises(ValueError):runner.validate_request(bad)
        for name, value in [('tool', 'C:/other.exe'), ('argv', ['--locals']), ('sample_count', 900)]:
            bad = deepcopy(good);bad['spec'][name] = value
            with self.assertRaises(ValueError):runner.validate_request(bad)
        bad = deepcopy(good);bad['candidate_commit'] = bad['spec']['candidate_commit'] = frames.binding.CANDIDATE_1029.commit
        with self.assertRaises(ValueError):runner.validate_request(bad)
        for value in (True, 0, -1):
            bad = deepcopy(good);bad['spec']['backend_created_filetime'] = value
            with self.assertRaises(ValueError):runner.validate_request(bad)

    def test_runner_uses_only_package_tool_and_preserves_failure(self):
        good = request()
        with patch.object(runner.observation, 'supervise_observation', return_value={'supervisor_status':'FAIL'}) as call:
            result, passed = runner.execute_phase(good, ROOT, ROOT/'package')
        self.assertFalse(passed)
        self.assertEqual(result['supervisor_status'], 'FAIL')
        self.assertEqual(call.call_args.args[0].tool, str(ROOT/'package/py-spy.exe'))
        self.assertIs(call.call_args.kwargs['_worker_target'], frames.worker_entry)
        self.assertEqual(call.call_args.kwargs['duration_seconds'], 6)

    def test_parser_preserves_unbound_threads_and_rejects_bad_shapes(self):
        rows = json.loads((FIXTURE_ROOT/'frozen-dump-0.stdout.log').read_bytes())
        pid = rows[0]['pid']
        generations = {r['os_thread_id']:dict(created_filetime=123, stable=True) for r in rows}
        good = frames.interpret(json.dumps(rows).encode(), pid, generations)
        self.assertEqual(good['status'], 'GENERATIONS_BOUND')
        generations.pop(rows[0]['os_thread_id'])
        partial = frames.interpret(json.dumps(rows).encode(), pid, generations)
        self.assertEqual(partial['status'], 'PARTIAL')
        self.assertIsNone(partial['rows'][0]['created_filetime'])
        for mode in ('locals', 'other-pid', 'duplicate-id', 'duplicate-native-id', 'empty-stack', 'extra-option', 'huge-string', 'bool-line'):
            bad = deepcopy(rows)
            if mode == 'locals':bad[0]['frames'][0]['locals'] = {'test':'secret'}
            elif mode == 'other-pid':bad[0]['pid'] += 1
            elif mode == 'duplicate-id':bad[1]['thread_id'] = bad[0]['thread_id']
            elif mode == 'duplicate-native-id':bad[1]['os_thread_id'] = bad[0]['os_thread_id']
            elif mode == 'empty-stack':bad[0]['frames'] = []
            elif mode == 'extra-option':bad[0]['extra'] = True
            elif mode == 'huge-string':bad[0]['frames'][0]['name'] = 'x'*8193
            else:bad[0]['frames'][0]['line'] = True
            with self.subTest(mode=mode), self.assertRaises(ValueError):frames.interpret(json.dumps(bad).encode(), pid, generations)

    def test_native_handle_generation_and_ended_thread(self):
        identity = clock._clock().identity()
        created = identity['process_created_filetime']
        executable = ProcessIdentity.read(os.getpid()).exe
        with self.assertRaises(ValueError), NativeTarget(os.getpid(), created+1, executable):pass
        with self.assertRaises(ValueError), NativeTarget(os.getpid(), created, str(ROOT/'wrong.exe')):pass
        ready = queue.Queue();stop = threading.Event()
        def work():
            ready.put(clock._clock().identity());stop.wait(5)
        thread = threading.Thread(target=work);thread.start()
        try:
            declared = ready.get(timeout=2)
            with NativeTarget(os.getpid(), created, executable) as target, target.threads() as owned:
                tid = declared['native_thread_id']
                self.assertEqual(owned.before[tid], declared['thread_created_filetime'])
                self.assertTrue(owned.finish()[tid]['stable'])
                stop.set();thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(target.api.WaitForSingleObject(owned.handles[tid], 2000), 0)
                self.assertFalse(owned.finish()[tid]['stable'])
        finally:
            stop.set();thread.join(2)
        self.assertEqual(owned.handles, {})
        self.assertIsNone(target.handle)

    def test_actual_frozen_target_fixed_dump_and_bad_tool(self):
        fixture = FIXTURE_ROOT/'freeze-dist/sfl-frame-fixture/sfl-frame-fixture.exe'
        child = subprocess.Popen([str(fixture)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        messages = queue.Queue();out=[];err=[]
        def drain(stream, records, notify=False):
            try:
                for line in stream:
                    records.append(line)
                    if notify:messages.put(json.loads(line))
            finally:stream.close()
        readers = [threading.Thread(target=drain,args=(child.stdout,out,True)),threading.Thread(target=drain,args=(child.stderr,err))]
        for reader in readers:reader.start()
        try:
            declared = messages.get(timeout=5)
            with NativeTarget(child.pid, declared['process_created_filetime'], str(fixture)) as target:
                stop=threading.Event()
                result=frames.capture(target, FIXTURE_ROOT/'py-spy.exe', ROOT/'real-dump', stop)
                self.assertEqual(result['status'], 'CAPTURED', result['errors'])
                self.assertEqual(result['reader_exit'], 0)
                self.assertTrue(result['reader_threads_closed'])
                window = result['read_window']
                self.assertEqual(window['status'], 'BOUNDED')
                self.assertEqual(window['scope'], 'READER_ENVELOPE_ONLY')
                self.assertFalse(window['sample_instant_available'])
                self.assertLess(window['qpc_begin'], window['qpc_end'])
                self.assertLessEqual(result['native_begin']['boundary']['perf_after_ns'], result['read_finished_ns'])
                self.assertGreaterEqual(result['native_end']['boundary']['perf_before_ns'], result['read_finished_ns'])
                for known in declared['threads']:
                    row=next(r for r in result['parsed']['rows'] if r['os_thread_id']==known['native_id'])
                    self.assertEqual(row['created_filetime'], known['created_filetime'])
                    self.assertEqual(row['thread_name'], known['name'])
                    self.assertTrue(any(Path(f['filename']).name=='fixture.py' for f in row['frames']))
                # Valid frames must survive unavailable clocks, but cannot gain a false time join.
                original_capture = clock.capture
                calls = []
                def changed_generation():
                    sample = original_capture()
                    if calls:sample['identity']['thread_created_filetime'] += 1
                    calls.append(sample)
                    return sample
                with patch.object(frames.clock, 'capture', side_effect=changed_generation):
                    unbound = frames.capture(target, FIXTURE_ROOT/'py-spy.exe', ROOT/'unbound-clock', stop)
                self.assertEqual(unbound['status'], 'CAPTURED', unbound['errors'])
                self.assertEqual(unbound['read_window']['status'], 'UNAVAILABLE')
                self.assertNotIn('qpc_begin', unbound['read_window'])
                self.assertEqual(unbound['release_gate'], 'HOLD')
                fake=ROOT/'bad-tool';fake.mkdir();(fake/'py-spy.exe').write_bytes(b'not-executable')
                bad=frames.capture(target, fake/'py-spy.exe', ROOT/'bad-dump', stop)
                self.assertEqual(bad['status'],'FAIL');self.assertNotIn('reader_pid',bad)
                stop.set()
                cancelled=frames.capture(target,FIXTURE_ROOT/'py-spy.exe',ROOT/'cancelled-dump',stop)
                self.assertEqual(cancelled['status'],'FAIL');self.assertNotIn('reader_pid',cancelled)
                target.recheck()
            self.assertIsNone(child.poll())
        finally:
            if child.poll() is None:
                child.stdin.write('stop\n');child.stdin.flush();child.stdin.close()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
            for reader in readers:reader.join(3)
            (ROOT/'fixture.stdout.log').write_text(''.join(out),encoding='utf-8')
            (ROOT/'fixture.stderr.log').write_text(''.join(err),encoding='utf-8')
        self.assertEqual(child.returncode,0)
        self.assertFalse(err)
        self.assertFalse(any(r.is_alive() for r in readers))


if __name__ == '__main__':unittest.main()
