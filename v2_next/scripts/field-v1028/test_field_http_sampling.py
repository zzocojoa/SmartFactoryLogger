"""Real loopback faults and scheduling tests for the field HTTP component."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import socket
import threading
import time
import unittest

from PIL import Image

import field_http_sampling as sampling


class FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):  # noqa: N802
        server = self.server
        with server.lock:
            server.starts.setdefault(self.path, []).append(time.perf_counter_ns())
            server.active[self.path] = server.active.get(self.path, 0) + 1
            server.maximum[self.path] = max(server.maximum.get(self.path, 0), server.active[self.path])
        mode = server.modes.get(self.path, 'normal')
        try:
            body = server.jpeg if self.path.endswith('.jpg') else b'{"ok":true}'
            status = 200
            if mode == 'slow':
                time.sleep(.24)
            if mode == 'slow-headers':
                for value in b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n':
                    self.connection.sendall(bytes([value]))
                    time.sleep(.02)
                self.connection.sendall(body)
                return
            if mode == 'bad-json':
                body = b'{"ok":'
            if mode == 'duplicate-json':
                body = b'{"ok":true,"ok":false}'
            if mode == 'nan-json':
                body = b'{"value":NaN}'
            if mode == 'bad-jpeg':
                body = b'not an image'
            if mode == 'failure':
                status = 503
            if mode == 'oversize':
                body = b'x' * (1024 * 1024 + 1)
            if mode == 'empty-object':
                body = b'null'
            if mode == 'chunked':
                self.send_response(200)
                self.send_header('Transfer-Encoding', 'chunked')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(b'5\r\n{"ok"\r\n6\r\n:true}\r\n0\r\n\r\n')
                return
            if mode == 'redirect':
                status = 302
            self.send_response(status)
            self.send_header('Content-Length', str(len(body) + (20 if mode == 'truncated' else 0)))
            self.send_header('Connection', 'close')
            if mode == 'large-headers':
                self.send_header('X-Large-1', 'x' * 40000)
                self.send_header('X-Large-2', 'x' * 40000)
            if mode == 'redirect':
                self.send_header('Location', 'http://example.invalid/not-followed')
            self.end_headers()
            if mode == 'slow-body':
                for value in body:
                    self.wfile.write(bytes([value]))
                    self.wfile.flush()
                    time.sleep(.02)
            else:
                self.wfile.write(body)
        except (OSError, ConnectionError):
            pass
        finally:
            self.close_connection = True
            with server.lock:
                server.active[self.path] -= 1

    def log_message(self, *_args):
        return


@contextmanager
def local_server():
    jpeg = io.BytesIO()
    Image.new('RGB', (32, 24), (32, 96, 160)).save(jpeg, 'JPEG')
    instance = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
    instance.daemon_threads = True
    instance.jpeg = jpeg.getvalue()
    instance.lock = threading.Lock()
    instance.starts, instance.active, instance.maximum, instance.modes = {}, {}, {}, {}
    worker = threading.Thread(target=instance.serve_forever, kwargs={'poll_interval': .01})
    worker.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        worker.join(2)
        assert not worker.is_alive()


def test_normal_full_bytes_and_decoding(server):
    for endpoint in sampling.ENDPOINTS:
        record, body = sampling.fetch_sample(server.server_port, endpoint)
        assert record['request_success'] and record['body_complete'] and record['decode_complete']
        assert record['status'] == 200 and record['error_type'] is None
        assert record['body_sha256'] == hashlib.sha256(body).hexdigest()
        assert record['body_bytes'] == len(body)
        assert math.isclose(record['client_request_and_body_ms'], sum(record[key] for key in ('connect_ms', 'send_ms', 'headers_wait_ms', 'body_ms')), abs_tol=.00001)
        assert record['finished_ns'] >= record['response_finished_ns'] >= record['started_ns']


def test_failed_samples_keep_received_bytes(server, mode, kind, error):
    endpoint = next(item for item in sampling.ENDPOINTS if item.name == kind)
    server.modes[endpoint.path] = mode
    record, body = sampling.fetch_sample(server.server_port, endpoint)
    assert not record['request_success']
    assert record['error_type'] == error
    assert body and record['body_sha256'] == hashlib.sha256(body).hexdigest()
    if mode in ('truncated', 'oversize'):
        assert not record['body_complete']
    else:
        assert record['body_complete']


def test_total_deadline_applies_to_continuous_small_reads(server, mode):
    server.modes['/health'] = mode
    record, body = sampling.fetch_sample(server.server_port, sampling.ENDPOINTS[0], timeout_seconds=.09)
    assert record['timeout'] and not record['request_success'] and not record['body_complete']
    assert 70 <= record['client_request_and_body_ms'] < 500
    if mode == 'slow-body':
        assert body and len(body) < len(b'{"ok":true}')


def test_chunked_body(server):
    server.modes['/health'] = 'chunked'
    record, body = sampling.fetch_sample(server.server_port, sampling.ENDPOINTS[0])
    assert record['request_success'] and body == b'{"ok":true}'


def test_large_headers_are_bounded_and_cannot_pass(server):
    server.modes['/health'] = 'large-headers'
    record, body = sampling.fetch_sample(server.server_port, sampling.ENDPOINTS[0])
    assert not record['request_success'] and record['error_reason'] == 'header-byte-budget'
    assert record['headers_truncated'] and record['headers_bytes'] > 65536
    assert len(record['headers_sha256']) == 64 and record['headers'] == [] and not body


def test_refused_connection_is_recorded():
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
        record, body = sampling.fetch_sample(port, sampling.ENDPOINTS[0], timeout_seconds=.1)
    assert not record['request_success'] and record['error_type']
    assert body == b'' and record['client_request_and_body_ms'] >= 0


def test_independent_channels_no_overlap_no_catchup_and_manifest(server, tmp_path):
    server.modes['/api/spot/live_image.jpg'] = 'slow'
    endpoints = tuple(replace(item, interval_seconds=.08) for item in sampling.ENDPOINTS)
    result = sampling.collect_http_window(server.server_port, tmp_path / 'run', duration_seconds=.64, endpoints=endpoints)
    assert result['channels']['health']['requests'] == 8
    assert result['channels']['health']['missed_slots'] == 0
    assert result['channels']['data']['requests'] == 8
    assert result['channels']['image']['missed_slots'] >= 4
    assert result['http_component_status'] == 'FAIL'
    assert result['field_gate'] == 'NOT_EVALUATED' and result['release_gate'] == 'HOLD'
    assert result['finished_ns'] - result['origin_ns'] >= result['duration_ns']
    assert set(server.maximum.values()) == {1}
    image_starts = server.starts['/api/spot/live_image.jpg']
    assert all(right - left >= 240_000_000 for left, right in zip(image_starts, image_starts[1:]))
    manifest = json.loads((tmp_path / 'run/manifest.json').read_bytes())
    paths = {p.name for p in (tmp_path / 'run').iterdir()}
    assert paths == set(manifest['files']) | {'manifest.json'}
    for name, fact in manifest['files'].items():
        data = (tmp_path / 'run' / name).read_bytes()
        assert len(data) == fact['bytes'] and hashlib.sha256(data).hexdigest() == fact['sha256']


def test_first_failure_is_not_removed_from_percentiles():
    endpoint = sampling.ENDPOINTS[0]
    records = [{'kind': 'request', 'sequence': index, 'request_success': index != 0, 'timeout': index == 0,
                'client_request_and_body_ms': value, 'start_lateness_ms': 0}
               for index, value in enumerate([230, 20, 30])]
    report = sampling.summarize_channel(endpoint, records, 3)
    assert report['first_ms'] == report['max_ms'] == report['p95_ms'] == report['p99_ms'] == 230
    assert report['p50_ms'] == 30 and report['threshold_failures'] == 1 and report['request_errors'] == 1
    assert report['http_component_status'] == 'FAIL'


def test_exact_failure_threshold_and_image_no_invented_limit():
    record = {'kind': 'request', 'sequence': 0, 'request_success': True, 'timeout': False,
              'client_request_and_body_ms': 200, 'start_lateness_ms': 0}
    health = sampling.summarize_channel(sampling.ENDPOINTS[0], [record], 1)
    assert health['threshold_failures'] == 0 and health['warnings'] == 1
    image = sampling.summarize_channel(sampling.ENDPOINTS[2], [{**record, 'client_request_and_body_ms': 501}], 1)
    assert image['failure_threshold_ms'] is None and image['threshold_failures'] is None and image['warnings'] == 1


def test_invalid_timing_cannot_be_a_pass():
    for value in (float('nan'), float('inf'), -1, True, None):
        record = {'kind': 'request', 'sequence': 0, 'request_success': True, 'timeout': False,
                  'client_request_and_body_ms': value, 'start_lateness_ms': 0}
        result = sampling.summarize_channel(sampling.ENDPOINTS[0], [record], 1)
        assert result['http_component_status'] == 'NOT_MEASURED'
        assert result['invalid_record_count'] == 1 and result['first_ms'] is None


def test_duplicate_or_missing_slots_cannot_be_complete():
    record = {'kind': 'request', 'sequence': 0, 'request_success': True, 'timeout': False,
              'client_request_and_body_ms': 20, 'start_lateness_ms': 0}
    result = sampling.summarize_channel(sampling.ENDPOINTS[0], [record, record], 2)
    assert not result['schedule_complete'] and result['http_component_status'] == 'NOT_MEASURED'
    assert result['unaccounted_slots'] == 1


def test_default_cadences_with_actual_clock(server, tmp_path):
    output = tmp_path / 'default'
    result = sampling.collect_http_window(server.server_port, output, duration_seconds=6.2)
    assert {name: item['requests'] for name, item in result['channels'].items()} == {'health': 4, 'data': 2, 'image': 25}
    assert result['http_component_status'] == 'PASS'
    assert result['field_gate'] == 'NOT_EVALUATED' and result['release_gate'] == 'HOLD'
    health = [json.loads(path.read_bytes()) for path in sorted(output.glob('health-*.json'))]
    assert [right['scheduled_ns'] - left['scheduled_ns'] for left, right in zip(health, health[1:])] == [2_000_000_000] * 3
    assert all(1_800_000_000 < right['started_ns'] - left['started_ns'] < 2_200_000_000 for left, right in zip(health, health[1:]))
    data = [json.loads(path.read_bytes()) for path in sorted(output.glob('data-*.json'))]
    assert data[1]['scheduled_ns'] - data[0]['scheduled_ns'] == 6_000_000_000
    assert 5_800_000_000 < data[1]['started_ns'] - data[0]['started_ns'] < 6_200_000_000


def test_cancel_preserves_unobserved_slot_count(server, tmp_path):
    stop = threading.Event()
    stop.set()
    result = sampling.collect_http_window(server.server_port, tmp_path / 'cancel', duration_seconds=900, stop_event=stop)
    assert result['http_component_status'] == 'FAIL' and result['stop_requested']
    assert not server.starts
    assert sum(item['cancelled_slots'] for item in result['channels'].values()) == 4200
    assert all(item['unaccounted_slots'] == 0 for item in result['channels'].values())


def test_body_budget_failure_cannot_pass(server, tmp_path):
    result = sampling.collect_http_window(server.server_port, tmp_path / 'budget', duration_seconds=.02, body_byte_budget=1)
    assert result['http_component_status'] == 'FAIL'
    assert result['worker_errors'] and any('body-byte-budget' in row['reason'] for row in result['worker_errors'])
    assert result['promotion_allowed'] is False


def test_output_cannot_be_reused_or_escape_parent(server, tmp_path):
    existing = tmp_path / 'existing'
    existing.mkdir()
    (existing / 'keep.txt').write_bytes(b'keep')
    with unittest.TestCase().assertRaises(FileExistsError):
        sampling.collect_http_window(server.server_port, existing, duration_seconds=.01)
    with unittest.TestCase().assertRaises(ValueError):
        sampling.collect_http_window(server.server_port, tmp_path / '..' / 'escape', duration_seconds=.01)
    assert (existing / 'keep.txt').read_bytes() == b'keep' and not server.starts


def test_invalid_contract_refused_before_write(tmp_path, kwargs):
    output = tmp_path / 'invalid'
    with unittest.TestCase().assertRaises(ValueError):
        sampling.collect_http_window(8000, output, **kwargs)
    assert not output.exists()


def load_tests(_loader, _tests, _pattern):
    root = Path(os.environ['SFL_HTTP_TEST_ROOT'])
    if not root.is_absolute() or not root.parent.is_dir():
        raise ValueError('SFL_HTTP_TEST_ROOT must name a new absolute test directory')
    root.mkdir()
    cases = [
        (test_normal_full_bytes_and_decoding, {}),
        (test_chunked_body, {}),
        (test_large_headers_are_bounded_and_cannot_pass, {}),
        (test_refused_connection_is_recorded, {}),
        (test_independent_channels_no_overlap_no_catchup_and_manifest, {}),
        (test_first_failure_is_not_removed_from_percentiles, {}),
        (test_exact_failure_threshold_and_image_no_invented_limit, {}),
        (test_invalid_timing_cannot_be_a_pass, {}),
        (test_duplicate_or_missing_slots_cannot_be_complete, {}),
        (test_default_cadences_with_actual_clock, {}),
        (test_cancel_preserves_unobserved_slot_count, {}),
        (test_body_budget_failure_cannot_pass, {}),
        (test_output_cannot_be_reused_or_escape_parent, {}),
    ]
    for mode, kind, error in [
        ('bad-json', 'health', 'JSONDecodeError'), ('duplicate-json', 'health', 'ValueError'),
        ('nan-json', 'health', 'ValueError'), ('empty-object', 'health', 'ValueError'),
        ('bad-jpeg', 'image', 'UnidentifiedImageError'), ('truncated', 'health', 'IncompleteRead'),
        ('oversize', 'health', 'ValueError'), ('failure', 'health', None), ('redirect', 'health', None),
    ]:
        cases.append((test_failed_samples_keep_received_bytes, {'mode': mode, 'kind': kind, 'error': error}))
    for mode in ('slow-headers', 'slow-body'):
        cases.append((test_total_deadline_applies_to_continuous_small_reads, {'mode': mode}))
    for kwargs in [
        {'duration_seconds': float('nan')}, {'duration_seconds': 0}, {'duration_seconds': 7201},
        {'duration_seconds': 1, 'endpoints': ()}, {'duration_seconds': 1, 'timeout_seconds': 0},
        {'duration_seconds': 1, 'endpoints': (replace(sampling.ENDPOINTS[0], interval_seconds=.000001),)},
        {'duration_seconds': 1, 'endpoints': (replace(sampling.ENDPOINTS[0], path='/change-settings'),)},
    ]:
        cases.append((test_invalid_contract_refused_before_write, {'kwargs': kwargs}))
    suite = unittest.TestSuite()
    for index, (function, arguments) in enumerate(cases):
        label = f'{index:02d}_{function.__name__}' + ('_' + arguments['mode'] if 'mode' in arguments else '')

        def run_case(function=function, arguments=arguments, label=label):
            import inspect
            parameters = inspect.signature(function).parameters
            values = dict(arguments)
            if 'tmp_path' in parameters:
                directory = root / label[:65]
                directory.mkdir()
                values['tmp_path'] = directory
            if 'server' in parameters:
                with local_server() as server:
                    function(server=server, **values)
            else:
                function(**values)

        run_case.__name__ = label
        suite.addTest(unittest.FunctionTestCase(run_case, description=label))
    return suite


if __name__ == '__main__':
    unittest.main(verbosity=2)
