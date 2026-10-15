"""Real loopback HTTP integration; app lifespan/hardware services stay disabled."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend import app as backend_app
import field_http_sampling as sampling
import field_health_timing as health_timing
import field_native_timing


class FieldHealthTimingTests(unittest.TestCase):
    def test_bad_probe_is_rejected_before_network_access(self):
        with patch.object(sampling, '_LoopbackConnection', side_effect=AssertionError('network used')):
            for endpoint, probe in [(sampling.ENDPOINTS[0], value) for value in ('', 'g' * 32, 1, 'a' * 33)] + [
                    (sampling.ENDPOINTS[1], 'a' * 32), (sampling.CONTROL_HEALTH, 'a' * 32)]:
                with self.subTest(endpoint=endpoint.name, probe=probe), self.assertRaises(ValueError):
                    sampling.fetch_sample(1, endpoint, health_probe_id=probe)

    def test_real_backend_probe_headers_and_raw_sampler_evidence(self):
        root = Path(os.environ['SFL_HEALTH_TIMING_HTTP_ROOT'])
        root.mkdir(exist_ok=False)
        with ExitStack() as stack:
            plc = stack.enter_context(patch.object(backend_app.plc_service, 'get_health', return_value={'running': True}))
            runtime = stack.enter_context(patch.object(backend_app, 'get_runtime_info', return_value={'runtime_kind': 'test'}))
            frontend = stack.enter_context(patch.object(backend_app, 'get_frontend_static_status', return_value={'frontend_static_ready': True}))
            listener = stack.enter_context(socket.socket())
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(backend_app.app, lifespan='off', access_log=False,
                                                  log_level='warning', proxy_headers=False))
            worker = threading.Thread(target=server.run, kwargs={'sockets': [listener]})
            worker.start()
            records = []
            expected = field_native_timing.capture()['identity']
            try:
                deadline = time.monotonic() + 5
                while not server.started and worker.is_alive() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(server.started)
                for name, service, before, after, value in (
                    ('ordinary', None, None, None, None),
                    ('baseline', None, None, None, None),
                    ('plc_wait', plc, 'worker_enter', 'plc_done', {'running': True}),
                    ('runtime_wait', runtime, 'plc_done', 'runtime_done', {'runtime_kind': 'test'}),
                    ('frontend_wait', frontend, 'runtime_done', 'frontend_done', {'frontend_static_ready': True}),
                ):
                    def delayed(*_args):
                        time.sleep(.08)
                        return value
                    if service is not None:
                        service.side_effect = delayed
                    try:
                        probe = uuid4().hex if name != 'ordinary' else None
                        record, raw = sampling.fetch_sample(port, sampling.ENDPOINTS[0], health_probe_id=probe)
                    finally:
                        if service is not None:
                            service.side_effect = None
                    record['test_case'] = name
                    records.append(record)
                    (root / (name + '.body.json')).write_bytes(raw)
                    self.assertTrue(record['request_success'], record)
                    self.assertEqual(json.loads(raw), {'running': True, 'runtime_kind': 'test', 'frontend_static_ready': True})
                    self.assertEqual(record['body_sha256'], hashlib.sha256(raw).hexdigest())
                    headers = {key.lower(): val for key, val in record['headers']}
                    self.assertIn('x-trace-id', headers)
                    if probe is None:
                        self.assertNotIn('x-sfl-health-timing', headers)
                        self.assertNotIn('health_probe_id', record)
                        continue
                    bound = health_timing.validate_health_sample(record, raw, probe_id=probe,
                        backend_pid=expected['pid'], backend_created_filetime=expected['process_created_filetime'])
                    self.assertEqual(bound['status'], 'REQUEST_AND_NATIVE_CLOCK_BOUND', bound)
                    record['timing_validation'] = bound
                    timing = json.loads(headers['x-sfl-health-timing'])
                    self.assertEqual(timing['probe_id'], probe)
                    self.assertEqual(record['health_probe_id'], probe)
                    self.assertEqual(timing['pid'], os.getpid())
                    self.assertEqual(timing['loop_tid'], worker.native_id)
                    self.assertNotEqual(timing['worker_tid'], worker.native_id)
                    points = timing['checkpoints']
                    self.assertEqual(list(points.values()), sorted(points.values()))
                    self.assertLessEqual(record['started_ns'], points['route_enter'])
                    self.assertLessEqual(points['route_resume'], record['response_finished_ns'])
                    self.assertLess(len(headers['x-sfl-health-timing'].encode('ascii')), 4096)
                    if service is not None:
                        self.assertGreaterEqual(points[after] - points[before], 70_000_000)
            finally:
                server.should_exit = True
                worker.join(5)
                (root / 'requests.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
            self.assertFalse(worker.is_alive(), 'test HTTP server did not exit normally')
            self.assertFalse(server.force_exit)
            (root / 'summary.json').write_text(json.dumps({
                'scope': 'LOCAL_SOURCE_HTTP_HEALTH_TIMING_ONLY', 'request_count': len(records),
                'normal_exit': True, 'lifespan_enabled': False, 'hardware_services_started': False,
                'field_latency_cause': 'UNDETERMINED', 'release_gate': 'HOLD', 'promotion_allowed': False,
            }, indent=2), encoding='utf-8')


if __name__ == '__main__':
    unittest.main(verbosity=2)
