"""Separate-process health clock/generation integration with normal owned shutdown."""
from contextlib import ExitStack
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import field_health_timing as timing
import field_http_sampling as sampling
from field_host_sampling import WindowsProcessReader
import field_native_timing


def backend_fixture(channel):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import uvicorn
    from backend import app
    mode = {'value': 'baseline'}

    def stage(name, result):
        def read(*_args):
            if mode['value'] == name:
                time.sleep(.08)
            return result
        return read

    with ExitStack() as stack:
        stack.enter_context(patch.object(app.plc_service, 'get_health', stage('plc', {'running': True})))
        stack.enter_context(patch.object(app, 'get_runtime_info', stage('runtime', {'runtime_kind': 'test'})))
        stack.enter_context(patch.object(app, 'get_frontend_static_status', stage('frontend', {'frontend_static_ready': True})))
        listener = stack.enter_context(socket.socket())
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app.app, lifespan='off', access_log=False,
                                              log_level='warning', proxy_headers=False))
        worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]})
        worker.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and worker.is_alive() and time.monotonic() < deadline:
                time.sleep(.01)
            if not server.started:
                raise RuntimeError('test server not ready')
            channel.send({'pid': os.getpid(), 'port': port, 'native': field_native_timing.capture()})
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if not channel.poll(.1):
                    continue
                command = channel.recv()
                if command == 'stop':
                    break
                if command not in ('baseline', 'plc', 'runtime', 'frontend'):
                    raise ValueError('fixture mode')
                mode['value'] = command
                channel.send({'mode': command})
            else:
                raise TimeoutError('test controller did not close fixture')
        finally:
            server.should_exit = True
            worker.join(5)
            channel.close()
        if worker.is_alive() or server.force_exit:
            raise RuntimeError('test HTTP server did not exit normally')


class SeparateProcessTests(unittest.TestCase):
    def test_live_process_generation_and_cross_process_clock_join(self):
        root = Path(os.environ['SFL_HEALTH_PROCESS_ROOT'])
        self.assertTrue(root.is_absolute())
        root.mkdir(exist_ok=False)
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe()
        process = context.Process(target=backend_fixture, args=(child,))
        records, probes = [], set()
        process.start()
        child.close()
        forced = False
        try:
            self.assertTrue(parent.poll(15), 'child readiness timeout')
            ready = parent.recv()
            self.assertEqual(ready['pid'], process.pid)
            self.assertNotEqual(process.pid, os.getpid())
            expected = WindowsProcessReader().read(process.pid)
            self.assertEqual(expected['status'], 'CAPTURED', expected)
            self.assertEqual(ready['native']['status'], 'OBSERVED')
            self.assertEqual(expected['created_100ns'], ready['native']['identity']['process_created_filetime'])
            for case, component in [('baseline', None), ('plc', 'plc_done'),
                                    ('runtime', 'runtime_done'), ('frontend', 'frontend_done')]:
                parent.send(case)
                self.assertTrue(parent.poll(2))
                self.assertEqual(parent.recv(), {'mode': case})
                probe = uuid4().hex
                self.assertNotIn(probe, probes)
                probes.add(probe)
                record, raw = sampling.fetch_sample(ready['port'], sampling.ENDPOINTS[0], health_probe_id=probe)
                after = WindowsProcessReader().read(process.pid)
                self.assertTrue(process.is_alive())
                self.assertEqual(after['status'], 'CAPTURED', after)
                self.assertEqual(after['created_100ns'], expected['created_100ns'])
                result = timing.validate_health_sample(record, raw, probe_id=probe,
                    backend_pid=process.pid, backend_created_filetime=expected['created_100ns'])
                entry = {'case': case, 'request': record, 'validation': result,
                         'backend_before': expected, 'backend_after': after}
                records.append(entry)
                (root / (case + '.body.json')).write_bytes(raw)
                (root / (case + '.record.json')).write_text(json.dumps(entry, indent=2), encoding='utf-8')
                self.assertEqual(result['status'], 'REQUEST_AND_NATIVE_CLOCK_BOUND', result)
                self.assertEqual(result['collector_identity']['pid'], os.getpid())
                self.assertNotEqual(result['collector_identity']['pid'], result['backend_identity']['pid'])
                if component:
                    self.assertGreaterEqual(result['stages_ns'][component], 70_000_000)
                self.assertEqual(result['etw_coverage'], 'NOT_EVALUATED')
                self.assertEqual(result['release_gate'], 'HOLD')
                expected = after
        finally:
            try:
                if process.is_alive():
                    parent.send('stop')
            except (EOFError, OSError):
                pass
            parent.close()
            process.join(8)
            if process.is_alive():
                forced = True
                process.terminate()  # Only this explicitly owned synthetic test child.
                process.join(5)
            (root / 'shutdown.json').write_text(json.dumps({
                'pid': process.pid, 'exit_code': process.exitcode, 'alive': process.is_alive(),
                'forced': forced, 'requests': len(records), 'field_gate': 'NOT_EVALUATED',
                'release_gate': 'HOLD', 'promotion_allowed': False,
            }, indent=2), encoding='utf-8')
        self.assertFalse(forced)
        self.assertFalse(process.is_alive())
        self.assertEqual(process.exitcode, 0)
        process.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
