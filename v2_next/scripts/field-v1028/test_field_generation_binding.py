"""Authenticated loopback faults, credential containment and native process binding."""
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psutil

import field_generation_binding as generation
import field_http_sampling as http
import field_installation_binding as binding
import field_observation as observation
from field_resource_sampling import ProcessIdentity
from test_field_observation import fixture_app

ROOT = Path(os.environ['SFL_GENERATION_TEST_ROOT'])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        server = self.server
        server.requests.append(dict(path=self.path, correct_token=self.headers.get('X-SFL-Control-Token') == server.token))
        mode = server.mode
        raw = json.dumps(dict(ok=True, echo=server.token.upper() if mode == 'body-echo' else '')).encode()
        if mode == 'escaped-body-echo':
            raw = ('{"echo":"' + ''.join('\\u%04x' % ord(c) for c in server.token) + '"}').encode()
        self.send_response(403 if mode == 'denied' else 302 if mode == 'redirect' else 200)
        self.send_header('Content-Length', str(len(raw)))
        if mode == 'header-echo':
            self.send_header('X-Echo', server.token)
        if mode == 'redirect':
            self.send_header('Location', 'http://example.invalid/must-not-follow')
        self.end_headers()
        try:
            if mode == 'slow-body':
                for char in raw:
                    self.wfile.write(bytes([char]))
                    self.wfile.flush()
                    time.sleep(.03)
            else:
                self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *args):
        pass


@contextmanager
def server_fixture(mode):
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.token, server.mode, server.requests = secrets.token_hex(32), mode, []
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .02})
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
        assert not thread.is_alive()


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ROOT.mkdir(exist_ok=False)

    def setUp(self):
        self.folder = ROOT / self._testMethodName
        self.folder.mkdir()
        self.backend = ProcessIdentity(101, time.time() - 30, 'c:\\fixture\\resources\\backend\\smartfactorybackend.exe')
        self.main = ProcessIdentity(100, self.backend.created - 1, 'c:\\fixture\\smart-factory.exe')
        self.payload = SimpleNamespace(root=Path('C:/fixture'), active=True)
        self.generation = 'a' * 32
        self.body = dict(running=True, backend_process_id=101, backend_generation_id=self.generation,
                         backend_session_id='123456abcdef', started_at=datetime.now(timezone.utc).isoformat())

    def test_schema_and_mismatched_identity(self):
        self.assertEqual(generation.control_identity(self.body, self.backend, self.generation),
                         {k: v for k, v in self.body.items() if k != 'running'})
        cases = [('running', False), ('running', 1), ('backend_process_id', True), ('backend_process_id', 102),
                 ('backend_generation_id', 'b' * 32), ('backend_generation_id', 'a' * 31),
                 ('backend_session_id', 'g' * 12), ('backend_session_id', 'a' * 32),
                 ('started_at', '2026-10-14T00:00:00'), ('started_at', None),
                 ('started_at', '2000-01-01T00:00:00+00:00'), ('started_at', '2999-01-01T00:00:00+00:00')]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises((ValueError, OverflowError)):
                generation.control_identity(dict(self.body, **{key: value}), self.backend, self.generation)
        observation.write_json(self.folder / 'schema-cases.json', dict(valid=1, rejected=len(cases)))

    def test_token_contract_and_endpoint_scope_before_connect(self):
        with patch.object(http._LoopbackConnection, 'connect') as connect:
            for token in (None, '', 'a' * 63, 'A' * 64, 'a' * 64 + '\r\nInjected: value'):
                with self.subTest(token_kind=type(token).__name__), self.assertRaises(ValueError):
                    http.fetch_sample(8000, http.CONTROL_HEALTH, control_token=token)
            with self.assertRaises(ValueError):
                http.fetch_sample(8000, http.ENDPOINTS[0], control_token='a' * 64)
            connect.assert_not_called()

    def test_authenticated_wire_request_does_not_persist_request_header(self):
        with server_fixture('normal') as server:
            record, raw = http.fetch_sample(server.server_port, http.CONTROL_HEALTH, control_token=server.token)
            self.assertTrue(record['request_success'])
            self.assertEqual(server.requests, [dict(path='/api/control/health', correct_token=True)])
            self.assertNotIn(server.token, json.dumps(record))
            self.assertNotIn(server.token.encode(), raw)
            observation.write_json(self.folder / 'record.json', dict(record=record, body_hex=raw.hex(),
                                                                    requests=server.requests))

    def test_echoed_credential_body_or_headers_are_withheld(self):
        for mode in ('body-echo', 'header-echo', 'escaped-body-echo'):
            with self.subTest(mode=mode), server_fixture(mode) as server:
                record, raw = http.fetch_sample(server.server_port, http.CONTROL_HEALTH, control_token=server.token)
                self.assertFalse(record['request_success'])
                self.assertTrue(record['sensitive_response_withheld'])
                self.assertEqual(raw, b'')
                self.assertNotIn(server.token, json.dumps(record).lower())
                observation.write_json(self.folder / (mode + '.json'), record)

    def test_denial_redirect_and_total_deadline(self):
        for mode in ('denied', 'redirect', 'slow-body'):
            with self.subTest(mode=mode), server_fixture(mode) as server:
                record, raw = http.fetch_sample(server.server_port, http.CONTROL_HEALTH, control_token=server.token,
                                                 timeout_seconds=.12)
                self.assertFalse(record['request_success'])
                self.assertEqual(len(server.requests), 1)
                if mode == 'slow-body':
                    self.assertTrue(record['timeout'])
                    self.assertLess(record['client_request_and_body_ms'], 350)
                observation.write_json(self.folder / (mode + '.json'), dict(record=record, body_hex=raw.hex()))

    def test_environment_error_never_returns_exception_secrets(self):
        token = secrets.token_hex(32)
        with patch.object(binding, 'read_process_binding', return_value={}), \
                patch.object(psutil, 'Process') as process, patch.object(http, 'fetch_sample') as request:
            process.return_value.environ.side_effect = RuntimeError('provider leak ' + token)
            result = generation.capture_generation(self.payload, self.main, self.backend, 8000)
            self.assertEqual(result['generation_status'], 'FAIL')
            self.assertNotIn(token, json.dumps(result))
            request.assert_not_called()
            observation.write_json(self.folder / 'capture.json', result)

    def test_missing_environment_or_process_change_blocks_transmission(self):
        token = secrets.token_hex(32)
        environment = dict(SFL_CONTROL_TOKEN=token, SFL_BACKEND_GENERATION_ID=self.generation, SFL_EMBEDDED_ELECTRON='1')
        for mode in ('missing', 'changed'):
            with self.subTest(mode=mode), patch.object(binding, 'read_process_binding') as identity, \
                    patch.object(psutil, 'Process') as process, patch.object(http, 'fetch_sample') as request:
                identity.side_effect = [{}, {'changed': True}]
                process.return_value.environ.return_value = {} if mode == 'missing' else environment
                result = generation.capture_generation(self.payload, self.main, self.backend, 8000)
                self.assertEqual(result['generation_status'], 'FAIL')
                request.assert_not_called()
                self.assertNotIn(token, json.dumps(result))
                observation.write_json(self.folder / (mode + '.json'), result)

    def test_real_windows_environment_and_bound_generation(self):
        with fixture_app(self.folder) as spec:
            token = psutil.Process(spec.backend.pid).environ()['SFL_CONTROL_TOKEN']
            with binding.InstalledPayload(spec.root, spec.reference, expected_reference_sha256=spec.reference_sha256) as payload:
                first = generation.capture_generation(payload, spec.main, spec.backend, spec.port)
                self.assertEqual(first['generation_status'], 'PASS', first)
                second = generation.capture_generation(payload, spec.main, spec.backend, spec.port,
                                                         expected_identity=first['identity'])
                self.assertEqual(second['generation_status'], 'PASS', second)
                changed = generation.capture_generation(payload, spec.main, spec.backend, spec.port,
                    expected_identity=dict(first['identity'], backend_session_id='ffffffffffff'))
                self.assertEqual(changed['generation_status'], 'FAIL')
                for name, result in [('first', first), ('second', second), ('wrong-session', changed)]:
                    self.assertNotIn(token, json.dumps(result))
                    self.assertNotIn(token.encode(), bytes.fromhex(result['control_body_hex']))
                    observation.write_json(self.folder / (name + '.json'), result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
