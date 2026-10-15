"""Unelevated loopback workload for a separately owned, bounded WPR recording.

The fixture never starts/stops WPR or an installed application. A ready receipt
from the trace guardian is required by the CLI. Completion is not trace quality.
"""
from datetime import datetime, timezone
import ctypes
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import threading
import time

import field_http_sampling as sampling
import field_native_timing as timing

PROFILE_SHA = '603c872d5bb638661eb6e133f2b23b4f778e8bab5f440dbda3017c09ea0ff486'
CASES = ('baseline', 'server_sleep', 'client_cpu') * 3


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def local_path(path):
    path = Path(path)
    require(path.is_absolute() and path.drive and not str(path).startswith('\\\\')
            and '..' not in path.parts and ':' not in str(path)[2:]
            and not re.search(r'[\x00-\x1f]', str(path)) and len(str(path)) <= 230, 'local-path-budget')
    for node in (path, *path.parents):
        try:
            info = node.lstat()
        except FileNotFoundError:
            continue
        require(not info.st_file_attributes & 0x400, 'reparse-path')
    return path


def publish(directory, name, value):
    target = local_path(directory / name)
    temporary = target.with_name(name + '.writing')
    raw = (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode('utf-8')
    require(len(raw) <= 1024**2, 'fixture-result-budget')
    with temporary.open('xb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    # Windows rename rejects an existing destination; never replace evidence.
    os.rename(temporary, target)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read_fact(path):
    path = local_path(path)
    require(path.stat().st_size <= 65536, 'fixture-json-budget')
    with path.open('rb') as stream:
        raw = stream.read(65537)
    require(len(raw) <= 65536, 'fixture-json-budget')
    parsed = json.loads(raw, object_pairs_hook=sampling._strict_object,
                        parse_constant=sampling._invalid_constant)
    require(isinstance(parsed, dict), 'fixture-json-object')
    return parsed, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def validate_binding(binding, run_id, identity, desktop_parent):
    require(binding['schema'] == 'sfl-request-trace-binding-v1' and binding['run_id'] == run_id,
            'trace-binding-schema-run')
    require(binding['fixture_pid'] == identity['pid']
            and str(binding['fixture_created_filetime']) == str(identity['process_created_filetime']),
            'fixture-generation-binding')
    run = local_path(Path(binding['trace_run_path']))
    require(run.parent == desktop_parent and re.fullmatch(r'T[0-9a-f]{12}', run.name), 'trace-run-boundary')
    lease, lease_fact = read_fact(run / 'lease.json')
    ready, ready_fact = read_fact(run / 'ready.json')
    guard, _ = read_fact(run / 'guard-process.json')
    require(lease_fact['sha256'] == binding['lease_sha256']
            and ready_fact['sha256'] == binding['ready_sha256'], 'trace-binding-pin')
    require(lease['schema'] == 'sfl-local-trace-lease-v1'
            and lease['scope'] == 'LOCAL_CONTROLLER_VALIDATION_ONLY'
            and lease['profile_sha256'] == PROFILE_SHA and lease['guard_seconds'] == 8
            and lease['stop_timeout_seconds'] == 60 and lease['run_path'] == str(run), 'trace-lease-contract')
    require(ready['lease_sha256'] == binding['lease_sha256']
            and ready['instance'] == lease['instance'] == binding['instance'], 'trace-ready-binding')
    require(guard['pid'] == binding['guard_pid']
            and str(guard['created_filetime']) == str(binding['guard_created_filetime']), 'trace-guard-binding')
    require(not (run / 'result.json').exists() and not (run / 'stop-request.json').exists(), 'trace-already-ending')
    require(binding['release_gate'] == lease['release_gate'] == 'HOLD'
            and binding['promotion_allowed'] is False and lease['promotion_allowed'] is False, 'trace-gates')
    return dict(binding=binding, lease=lease_fact, ready=ready_fact)


def run_workload(run_id, binding):
    """Use the actual sampler with explicit, recorded fixture-only injections."""
    server_rows, client_rows, errors = [], [], []
    current = {'index': 0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            index = current['index']
            if self.path != '/health' or index >= len(CASES):
                self.send_error(404)
                return
            begin = timing.capture()
            if CASES[index] == 'server_sleep':
                time.sleep(.080)
            before_headers = timing.capture()
            raw = json.dumps({'run_id': run_id, 'index': index, 'case': CASES[index]}).encode('ascii')
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()
            server_rows.append(dict(index=index, case=CASES[index], begin=begin,
                                    before_headers=before_headers, end=timing.capture()))

        def log_message(self, *_args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.timeout = .1
    server_thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01},
                                     name='SFLFixtureServer-' + run_id)
    server_thread.start()
    original_connection = sampling._LoopbackConnection
    injected = []
    stop_requested = threading.Event()

    class FixtureConnection(original_connection):
        def getresponse(self):
            if CASES[current['index']] == 'client_cpu':
                begin = timing.capture()
                target_cpu = time.thread_time_ns() + 80_000_000
                wall_deadline = time.perf_counter_ns() + 500_000_000
                while time.thread_time_ns() < target_cpu:
                    require(time.perf_counter_ns() < wall_deadline, 'fixture-cpu-injection-budget')
                injected.append(dict(index=current['index'], begin=begin, end=timing.capture()))
            return super().getresponse()

    def worker():
        try:
            sampling._LoopbackConnection = FixtureConnection
            for index, case in enumerate(CASES):
                require(not stop_requested.is_set(), 'fixture-workload-cancelled')
                current['index'] = index
                record, raw = sampling.fetch_sample(server.server_port, sampling.ENDPOINTS[0], timeout_seconds=1)
                require(record['request_success'], 'fixture-request-failed')
                require(json.loads(raw) == {'run_id': run_id, 'index': index, 'case': case}, 'fixture-response-binding')
                require(record['native_timing']['status'] == 'CORRELATABLE_BOUNDARIES', 'fixture-native-clock')
                client_rows.append(dict(index=index, case=case, request=record,
                                        response_body=raw.decode('ascii')))
                time.sleep(.01)
        except Exception as error:
            errors.append({'type': type(error).__name__, 'reason': str(error)[:1024]})
        finally:
            sampling._LoopbackConnection = original_connection

    # This client thread is created only after trace readiness, permitting a
    # real Thread/Start record to bind its PID/TID within this recording.
    client_thread = threading.Thread(target=worker, name='SFLFixtureClient-' + run_id)
    started = timing.capture()
    try:
        client_thread.start()
        client_thread.join(5)
        if client_thread.is_alive():
            stop_requested.set()
            client_thread.join(2)
        require(not client_thread.is_alive(), 'fixture-client-terminal-timeout')
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(2)
    ended = timing.capture()
    require(not server_thread.is_alive() and not errors, 'fixture-worker-failed:' + repr(errors))
    require(len(client_rows) == len(server_rows) == 9 and len(injected) == 3, 'fixture-row-count')
    return dict(schema='sfl-request-trace-workload-v1', status='WORKLOAD_COMPLETE_REQUIRES_TRACE_CORRELATION',
                run_id=run_id, trace_binding=binding, main_begin=started, main_end=ended,
                client=client_rows, server=server_rows, injections=injected,
                injection_contract={'server_sleep_seconds': .080, 'client_cpu_target_ns': 80_000_000,
                                    'client_cpu_wall_limit_ns': 500_000_000},
                production_sampler_source_unchanged=True, fixture_connection_override=True,
                shared_python_gil=True, trace_quality='NOT_EVALUATED', field_gate='NOT_EVALUATED',
                release_gate='HOLD', promotion_allowed=False)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--desktop-parent', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    require(not ctypes.windll.shell32.IsUserAnAdmin(), 'fixture-must-be-unelevated')
    require(re.fullmatch(r'[0-9a-f]{32}', args.run_id), 'fixture-run-id')
    directory = local_path(args.output)
    parent = local_path(args.desktop_parent)
    require(parent in directory.parents and directory.name == 'fixture', 'fixture-output-boundary')
    directory.mkdir()
    sample = timing.capture()
    require(sample['status'] == 'OBSERVED', 'fixture-native-identity')
    identity = sample['identity']
    deadline = time.monotonic() + 600
    publish(directory, 'armed.json', dict(schema='sfl-request-trace-armed-v1', run_id=args.run_id,
            identity=identity, armed_at_utc=datetime.now(timezone.utc).isoformat(), wait_seconds=600,
            executable=str(Path(os.sys.executable).resolve()), output_directory=str(directory),
            source_files={Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                          for p in (__file__, sampling.__file__, timing.__file__)},
            elevated=False, release_gate='HOLD', promotion_allowed=False))
    try:
        while not (directory / 'trace-binding.json').exists():
            require(time.monotonic() < deadline, 'fixture-arming-expired')
            time.sleep(.05)
        binding, binding_fact = read_fact(directory / 'trace-binding.json')
        checked = validate_binding(binding, args.run_id, identity, parent)
        checked['binding_file'] = binding_fact
        workload = run_workload(args.run_id, checked)
        result_fact = publish(directory, 'workload.json', workload)
        publish(directory, 'complete.json', dict(schema='sfl-request-trace-fixture-complete-v1',
                run_id=args.run_id, identity=identity, status='WORKLOAD_COMPLETE_REQUIRES_TRACE_CORRELATION',
                workload=result_fact, release_gate='HOLD', promotion_allowed=False))
        print(json.dumps(dict(status=workload['status'], result=result_fact)), flush=True)
    except Exception as error:
        publish(directory, 'failure.json', dict(status='FAIL', run_id=args.run_id,
                error_type=type(error).__name__, reason=str(error)[:2048], release_gate='HOLD', promotion_allowed=False))
        raise


if __name__ == '__main__':
    main()
