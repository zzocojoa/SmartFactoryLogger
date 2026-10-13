"""Owned-worker faults and real Windows/loopback integration with a synthetic app.

The fixture uses copied local Python binaries, synthetic candidate metadata and
an explicit fixture reference hash. It is never evidence of candidate field QA.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
import psutil

import field_installation_binding as binding
import field_observation as observation
from field_resource_sampling import ProcessIdentity


ROOT = Path(os.environ['SFL_OBSERVATION_TEST_ROOT'])


def hang_worker(spec, output, duration, stop, sender):
    observation.write_json(Path(output) / 'hung-worker.json', {'pid': os.getpid()})
    while True:
        time.sleep(1)


def orphan_worker(spec, output, duration, stop, sender):
    child = subprocess.Popen([sys._base_executable, '-c', 'import time; time.sleep(180)'],
                             creationflags=subprocess.CREATE_NO_WINDOW)
    observation.write_json(Path(output) / 'descendant.json', {'pid': child.pid, 'parent': os.getpid()})
    os._exit(9)


def killed_supervisor_entry(spec, output):
    observation.supervise_observation(spec, output, duration_seconds=1,
                                      preparation_timeout=180, _worker_target=hang_worker)


def exit_worker(spec, output, duration, stop, sender):
    sender.close()


def bad_message_worker(spec, output, duration, stop, sender):
    sender.send_bytes(b'{"phase":"observing","origin_ns":true}')
    while True:
        time.sleep(1)


def premature_final_worker(spec, output, duration, stop, sender):
    sender.send_bytes(b'{"phase":"finalizing","origin_ns":1}')
    sender.close()


def serialization_failure_worker(spec, output, duration, stop, sender):
    try:
        sender.send_bytes(b'{' * 65537)
    except BrokenPipeError:
        pass  # Receiver rejected the oversized message and closed its end.
    finally:
        sender.close()


def open_pipe_exit_worker(spec, output, duration, stop, sender):
    os._exit(9)


def after_ready_hang_worker(spec, output, duration, stop, sender):
    sender.send_bytes(json.dumps({'phase': 'observing', 'origin_ns': time.perf_counter_ns()}).encode())
    while True:
        time.sleep(1)


MAIN_SOURCE = '''import json,os,secrets,subprocess,sys
from pathlib import Path
r=Path(__file__).parent
env=dict(os.environ,SFL_CONTROL_TOKEN=secrets.token_hex(32),SFL_BACKEND_GENERATION_ID=secrets.token_hex(16),SFL_EMBEDDED_ELECTRON='1')
p=subprocess.Popen([str(r/'resources/backend/SmartFactoryBackend.exe'),str(r/'backend.py'),sys.argv[1]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=sys.stderr,text=True,env=env)
line=p.stdout.readline()
if not line: raise RuntimeError('Backend fixture failed to start')
print(json.dumps(dict(main_pid=os.getpid(),backend=json.loads(line))),flush=True)
sys.stdin.readline()
out,_=p.communicate('stop\\n',timeout=10)
assert p.returncode==0,p.returncode
'''

BACKEND_SOURCE = '''import json,os,sys,threading,time
from datetime import datetime,timezone
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
r=Path(__file__).parent
mode=sys.argv[1]
count=0
control_count=0
started=datetime.now(timezone.utc).isoformat(timespec='seconds')
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  global count,control_count
  status=200
  if self.path=='/health':
   count+=1
   if mode=='slow-first' and count==1: time.sleep(.25)
   if mode=='initial-error' and count==1: status=503
   logger='22222222-2222-4222-8222-222222222222'
   if mode=='changed-service' and count>=3: logger='33333333-3333-4333-8333-333333333333'
   body=json.dumps(dict(app_version='1.0.28',runtime_kind='frozen',mode='REAL',executable_path=sys.executable,frontend_source='resources',frontend_static_ready=True,spot_temperature=dict(build_git_commit='4cc7393e1bafbf90a329726aed9470fe0daacb21',diagnostics_available=True,spot_service_instance_id='11111111-1111-4111-8111-111111111111',v2_4_operational=dict(enabled=True,logger_service_instance_id=logger)))).encode()
  elif self.path=='/api/control/health':
   control_count+=1
   if mode=='slow-control': time.sleep(.25)
   session='abcdef123456'
   if mode=='control-changed' and control_count>=2: session='abcdef654321'
   if self.headers.get('X-SFL-Control-Token')!=os.environ['SFL_CONTROL_TOKEN']: status=403
   body=json.dumps(dict(running=True,backend_process_id=os.getpid(),backend_generation_id=os.environ['SFL_BACKEND_GENERATION_ID'],backend_session_id=session,started_at=started)).encode()
  elif self.path=='/api/spot/live_image.jpg': body=(r/'image.jpg').read_bytes()
  elif self.path=='/api/data': body=b'{"fixture":true}'
  else: status=404;body=b'{}'
  self.send_response(status);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def log_message(self,*args): pass
s=ThreadingHTTPServer(('127.0.0.1',0),Handler)
t=threading.Thread(target=s.serve_forever,kwargs={'poll_interval':.02});t.start()
print(json.dumps(dict(pid=os.getpid(),port=s.server_port)),flush=True)
sys.stdin.readline();s.shutdown();s.server_close();t.join(2)
assert not t.is_alive()
'''


def raw_fact(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


@contextmanager
def fixture_app(folder, mode='normal'):
    root = folder / 'app'
    root.mkdir()
    source = Path(sys._base_executable).parent
    backend = root / binding.BACKEND
    backend.parent.mkdir(parents=True)
    origin_files = []
    for directory, executable in ((root, 'smart-factory.exe'), (backend.parent, backend.name)):
        for original, name in [(source / 'python.exe', executable),
                               *[(p, p.name) for p in source.glob('vcruntime*.dll')],
                               (source / 'python312.dll', 'python312.dll')]:
            target = directory / name
            shutil.copyfile(original, target)
            assert raw_fact(original.read_bytes()) == raw_fact(target.read_bytes())
            origin_files.append(dict(source=str(original), target=str(target), **raw_fact(target.read_bytes())))
    provenance = root / binding.PROVENANCE
    provenance.parent.mkdir(parents=True)
    observation.write_json(provenance, dict(schema_version='1.0.0', source='clean_git_head', git_commit=binding.BUILD))
    (root / 'resources/app.asar').write_bytes(b'SYNTHETIC TEST ONLY; no Electron app')
    (root / 'main.py').write_text(MAIN_SOURCE, encoding='utf-8')
    (root / 'backend.py').write_text(BACKEND_SOURCE, encoding='utf-8')
    picture = io.BytesIO()
    Image.new('RGB', (32, 24), (20, 80, 120)).save(picture, 'JPEG')
    (root / 'image.jpg').write_bytes(picture.getvalue())
    files = {p.relative_to(root).as_posix(): raw_fact(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    reference = folder / 'fixture-reference.json'
    reference_fact = observation.write_json(reference, dict(candidate_commit=binding.BUILD, version=binding.VERSION,
        installer_sha256=binding.INSTALLER_SHA, installer_bytes=164618981, payload_files=files,
        payload_file_count=len(files), payload_content_bytes=sum(x['bytes'] for x in files.values())))
    observation.write_json(folder / 'synthetic-provenance.json', dict(classification='PYTHON_PROCESS_AND_HTTP_FIXTURE_NOT_PRODUCT',
                                                                   origins=origin_files))
    environment = dict(os.environ, PYTHONHOME=str(source), PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.Popen([str(root / 'smart-factory.exe'), str(root / 'main.py'), mode],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        line = process.stdout.readline()
        if not line:
            stdout, stderr = process.communicate(timeout=10)
            raise RuntimeError(f'Fixture launch failed: {process.returncode} {stdout} {stderr}')
        ready = json.loads(line)
        spec = observation.ObservationSpec(str(root), str(reference), ProcessIdentity.read(ready['main_pid']),
                                           ProcessIdentity.read(ready['backend']['pid']), ready['backend']['port'],
                                           reference_sha256=reference_fact['sha256'])
        observation.write_json(folder / 'fixture-ready.json', dict(main_pid=process.pid, ready=ready))
        yield spec
    finally:
        if process.poll() is None:
            stdout, stderr = process.communicate('stop\n', timeout=15)
        else:
            stdout, stderr = process.communicate(timeout=5)
        observation.write_json(folder / 'fixture-exit.json', dict(exit_code=process.returncode, stdout=stdout, stderr=stderr))
        assert process.returncode == 0 and not stderr, (process.returncode, stderr)


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()
        self.reference = self.folder / 'empty-reference.json'
        self.reference.write_text('{}')
        self.spec = observation.ObservationSpec(str(self.folder), str(self.reference),
            ProcessIdentity(100, 1.0, 'C:\\main.exe'), ProcessIdentity(101, 2.0, 'C:\\backend.exe'), 8000)

    def run_worker(self, target, **kwargs):
        result = observation.supervise_observation(self.spec, self.folder / 'out', duration_seconds=.2,
                                                   preparation_timeout=2, finalization_timeout=1,
                                                   _worker_target=target, **kwargs)
        self.assertEqual(result['supervisor_status'], 'FAIL')
        self.assertFalse(result['worker_still_alive'])
        self.assertFalse(result['event_reader_still_alive'])
        self.assertEqual(result['field_gate'], 'NOT_EVALUATED')
        self.assertFalse(result['promotion_allowed'])
        self.assertFalse(psutil.pid_exists(result['worker_pid']))
        return result

    def test_hung_owned_worker_is_terminated(self):
        result = self.run_worker(hang_worker)
        self.assertTrue(result['termination_requested'])
        self.assertEqual(result['errors'][0]['type'], 'TimeoutError')

    def test_early_wait_return_does_not_start_before_deadline(self):
        external = threading.Event()
        stop = observation.ObservationStop(external)
        try:
            with patch.object(stop.local, 'wait', side_effect=lambda delay: time.sleep(.001) or False) as wait:
                started = time.perf_counter()
                self.assertFalse(stop.wait(.05))
                self.assertGreaterEqual(time.perf_counter() - started, .05)
                self.assertGreater(wait.call_count, 2)
            external.set()
            self.assertTrue(stop.wait(.5))
        finally:
            stop.close()

    def test_missing_result_and_abrupt_exit_fail(self):
        result = self.run_worker(exit_worker)
        self.assertEqual(result['errors'][0]['type'], 'MissingResult')

    def test_abrupt_exit_is_not_restarted(self):
        result = self.run_worker(open_pipe_exit_worker)
        self.assertEqual(result['worker_exit_code'], 9)
        self.assertFalse(result['termination_requested'])

    def test_orphan_descendant_is_contained(self):
        result = self.run_worker(orphan_worker)
        child, _ = observation.read_json(self.folder / 'out/descendant.json')
        self.assertFalse(psutil.pid_exists(child['pid']))
        # A Windows venv launcher may add an intermediate Python process.
        self.assertGreaterEqual(result['job_before_close']['total_processes'], 2)
        self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
        self.assertTrue(result['termination_requested'])

    def test_job_assignment_failure_never_opens_worker_gate(self):
        with patch.object(observation.CollectorJob, 'assign_owned_process', side_effect=OSError('injected assignment')):
            result = self.run_worker(hang_worker)
        self.assertFalse((self.folder / 'out/hung-worker.json').exists())
        self.assertNotIn('job_assignment_before_gate', result)
        self.assertEqual(result['errors'][0]['type'], 'OSError')

    def test_job_query_failure_closes_handle_and_preserves_failure(self):
        with patch.object(observation.CollectorJob, 'accounting', side_effect=OSError('injected query')):
            result = self.run_worker(orphan_worker)
        self.assertTrue(any(e.get('reason') == 'injected query' for e in result['errors']), result)
        child, _ = observation.read_json(self.folder / 'out/descendant.json')
        deadline = time.perf_counter() + 5
        while psutil.pid_exists(child['pid']) and time.perf_counter() < deadline:
            time.sleep(.05)
        self.assertFalse(psutil.pid_exists(child['pid']))

    def test_supervisor_death_closes_job_and_terminates_only_owned_worker(self):
        context = multiprocessing.get_context('spawn')
        parent = context.Process(target=killed_supervisor_entry, args=(self.spec, self.folder / 'out'))
        parent.start()
        try:
            ready = self.folder / 'out/hung-worker.json'
            deadline = time.perf_counter() + 10
            while not ready.exists() and time.perf_counter() < deadline:
                time.sleep(.05)
            self.assertTrue(ready.exists())
            worker, _ = observation.read_json(ready)
            self.assertTrue(psutil.pid_exists(worker['pid']))
            parent.terminate()  # Stable HANDLE of this test's own supervisor.
            parent.join(10)
            self.assertFalse(parent.is_alive())
            deadline = time.perf_counter() + 5
            while psutil.pid_exists(worker['pid']) and time.perf_counter() < deadline:
                time.sleep(.05)
            self.assertFalse(psutil.pid_exists(worker['pid']))
            self.assertFalse((self.folder / 'out/supervisor.json').exists())
            observation.write_json(self.folder / 'parent-death-verified.json',
                                   dict(parent_exit=parent.exitcode, worker_pid=worker['pid'], worker_alive=False))
        finally:
            if parent.is_alive():
                parent.terminate()
                parent.join(10)
            parent.close()

    def test_invalid_origin_and_premature_phase_fail(self):
        self.run_worker(bad_message_worker)

    def test_premature_finalization_fail(self):
        self.run_worker(premature_final_worker)

    def test_oversized_ipc_frame_fails_without_hanging_supervisor(self):
        self.run_worker(serialization_failure_worker)

    def test_deadline_after_ready_is_not_extended(self):
        result = self.run_worker(after_ready_hang_worker)
        self.assertTrue(result['termination_requested'])
        self.assertLess((result['finished_ns'] - result['started_ns']) / 1e9, 8)

    def test_operator_stop_is_preserved(self):
        stop = threading.Event()
        timer = threading.Timer(.7, stop.set)
        timer.start()
        try:
            result = self.run_worker(hang_worker, stop_event=stop)
            self.assertEqual(result['errors'][0]['type'], 'InterruptedError')
        finally:
            timer.cancel()

    def test_invalid_arguments_leave_no_output(self):
        for value in (True, -1, float('nan'), 7201):
            with self.subTest(value=value), self.assertRaises(ValueError):
                observation.supervise_observation(self.spec, self.folder / 'out', duration_seconds=value)
        self.assertFalse((self.folder / 'out').exists())

    def test_output_reuse_refused(self):
        out = self.folder / 'out'
        out.mkdir()
        with self.assertRaises(FileExistsError):
            observation.supervise_observation(self.spec, out, duration_seconds=1)

    def test_manifest_larger_than_payload_tree_budget(self):
        folder = self.folder / 'component'
        folder.mkdir()
        files = {}
        for index in range(6001):
            name = f'{index:05d}.body'
            (folder / name).write_bytes(b'')
            files[name] = raw_fact(b'')
        observation.write_json(folder / 'manifest.json', dict(files=files))
        result = observation.verify_component_manifest(folder, 6010)
        self.assertEqual(result['files'], 6001)
        (folder / '00000.body').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'component-file-hash'):
            observation.verify_component_manifest(folder, 6010)

    def test_real_component_integration_and_own_worker_isolation(self):
        with fixture_app(self.folder) as spec:
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=6.2)
            self.assertEqual(result['supervisor_status'], 'PASS', result)
            worker, _ = observation.read_json(self.folder / 'out/worker-result.json')
            self.assertEqual(worker['review']['health_requests_including_boundaries'], 6)
            self.assertEqual(worker['review']['summary']['http']['persistence']['persisted_records'], 31)
            self.assertEqual(worker['review']['resource_rows_checked_for_backend'], 2)
            self.assertEqual(worker['review']['summary']['resources']['resource_coverage_status'], 'NOT_MEASURED')
            self.assertEqual(worker['field_gate'], 'NOT_EVALUATED')
            self.assertEqual(result['job_after_cleanup']['active_processes'], 0)
            self.assertEqual(result['job_after_cleanup']['total_processes'], 4)
            self.assertEqual(ProcessIdentity.read(spec.main.pid), spec.main)
            self.assertEqual(ProcessIdentity.read(spec.backend.pid), spec.backend)
            hung = observation.supervise_observation(spec, self.folder / 'hung', duration_seconds=.2,
                preparation_timeout=2, finalization_timeout=1, _worker_target=orphan_worker)
            self.assertEqual(hung['supervisor_status'], 'FAIL')
            self.assertTrue(hung['termination_requested'])
            descendant, _ = observation.read_json(self.folder / 'hung/descendant.json')
            self.assertFalse(psutil.pid_exists(descendant['pid']))
            self.assertEqual(ProcessIdentity.read(spec.main.pid), spec.main)
            self.assertEqual(ProcessIdentity.read(spec.backend.pid), spec.backend)
            binding.read_process_binding(spec.main, spec.backend, spec.port)

    def test_first_health_delay_is_not_discarded(self):
        with fixture_app(self.folder, 'slow-first') as spec:
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            worker, _ = observation.read_json(self.folder / 'out/worker-result.json')
            self.assertGreater(worker['review']['first_health_ms'], 200)
            self.assertIn('all-health-including-boundaries-failed', worker['review']['issues'])

    def test_changed_service_during_window_is_not_passed(self):
        with fixture_app(self.folder, 'changed-service') as spec:
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=2.2)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            worker, _ = observation.read_json(self.folder / 'out/worker-result.json')
            self.assertIn('health-1-session', worker['review']['issues'])

    def test_authenticated_backend_session_change_is_not_passed(self):
        with fixture_app(self.folder, 'control-changed') as spec:
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            worker, _ = observation.read_json(self.folder / 'out/worker-result.json')
            self.assertEqual(worker['control_binding']['initial']['generation_status'], 'PASS')
            self.assertEqual(worker['control_binding']['final']['generation_status'], 'FAIL')

    def test_first_authenticated_health_latency_is_not_discarded(self):
        with fixture_app(self.folder, 'slow-control') as spec:
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            control, _ = observation.read_json(self.folder / 'out/control-initial.json')
            self.assertGreater(control['control_record']['client_request_and_body_ms'], 200)
            self.assertEqual(control['generation_status'], 'FAIL')
            self.assertFalse((self.folder / 'out/http').exists())

    def test_initial_failure_is_durable_and_collection_does_not_start(self):
        with fixture_app(self.folder, 'initial-error') as spec:
            result = observation.supervise_observation(spec, self.folder / 'out', duration_seconds=.5)
            self.assertEqual(result['supervisor_status'], 'FAIL')
            self.assertFalse((self.folder / 'out/http').exists())
            initial, _ = observation.read_json(self.folder / 'out/initial.json')
            self.assertEqual(initial['health_record']['status'], 503)

    def test_parent_receipt_write_error_is_not_silent_success(self):
        original = observation.write_json
        def failing(path, value):
            if Path(path).name == 'supervisor.json':
                raise OSError('injected parent fsync failure')
            return original(path, value)
        with patch.object(observation, 'write_json', side_effect=failing):
            with self.assertRaisesRegex(OSError, 'injected parent fsync failure'):
                observation.supervise_observation(self.spec, self.folder / 'out', duration_seconds=.2,
                                                   preparation_timeout=2, _worker_target=exit_worker)


if __name__ == '__main__':
    unittest.main(verbosity=2)
