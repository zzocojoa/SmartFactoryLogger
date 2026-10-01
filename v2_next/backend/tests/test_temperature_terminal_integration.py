"""Native loopback recovery and terminal ownership proof in an isolated process.

Only device boundaries and the final os._exit are substituted. Production poll,
driver/service loops, writers, close/stop and shutdown orchestration all run.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest


def run_child(root: Path, recover: bool) -> None:
    import asyncio
    import csv
    import hashlib
    import http.server
    import io
    import threading
    import time
    from contextlib import ExitStack
    from types import SimpleNamespace
    from unittest.mock import patch
    from urllib.parse import parse_qs, urlsplit
    from PIL import Image

    # The caller sets isolated APPDATA/config paths before any production import.
    from backend import app, config
    from backend.FacilityData import service as service_module
    from backend.FacilityData.drivers import real_plc, spot_api
    from backend.FacilityData.operator_metadata import OperatorMetadataStore
    from backend.FacilityData.repository import CSVLoggerService
    from backend.tests.test_temperature_worker_lifecycle import FakeSocket

    jpeg = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(jpeg, 'JPEG')
    requests = []
    temperature_requests = 0
    diagnostic_requests = 0

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            nonlocal temperature_requests, diagnostic_requests
            parsed = urlsplit(self.path)
            key = parse_qs(parsed.query).get('p', [''])[0]
            requests.append((self.path, self.client_address[1]))
            status = 200
            if 'image' in parsed.path.lower():
                body = jpeg.getvalue()
            else:
                values = {'temperature': '500', 'alarmstatus': '0', 'signalpc': '55',
                          'd1temperature': '500', 'd2temperature': '499', 'e1out': '57',
                          'e2out': '53', 'itemperature': '41.2', 'appnumber': '7'}
                body = values.get(key, '0').encode()
                if key == 'temperature':
                    temperature_requests += 1
                    if recover and temperature_requests == 1:
                        status, body = 503, b'synthetic first-read failure'
                if key == 'alarmstatus':
                    diagnostic_requests += 1
                    if recover and diagnostic_requests == 1:
                        status, body = 503, b'synthetic diagnostic failure'
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Type', 'image/jpeg' if 'image' in parsed.path.lower() else 'text/plain')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, name='Synthetic-SPOT')
    server_thread.start()
    owned = {}
    tasks = []
    exit_codes = []
    result = {}
    root.mkdir(parents=True, exist_ok=True)
    log_root = root / 'data'
    with ExitStack() as stack:
        base = f'http://127.0.0.1:{server.server_port}'
        overrides = dict(LOG_PATH=log_root, APP_DATA_DIR=root, AUTO_SAVE=True,
                         CSV_V1_ENABLED=False, CSV_V2_ENABLED=True, CSV_V2_SIDECAR_ENABLED=True,
                         CSV_V2_OPERATIONAL_FIELDS_ENABLED=True, CSV_V2_TEMPERATURE_HARDENING_ENABLED=True,
                         SPOT_OBSERVATION_FACT_ENABLED=True, PROCESS_PHASE_EVENT_FACT_ENABLED=True,
                         SPOT_IMAGE_CAPTURE_ENABLED=True, SPOT_IMAGE_CAPTURE_MODE='all',
                         SPOT_IMAGE_CAPTURE_PATH=str(log_root/'spot_images'),
                         SPOT_IP=f'127.0.0.1:{server.server_port}', SPOT_URL=base+'/output?p=temperature',
                         SPOT_INTERNAL_TEMPERATURE_URL=base+'/output?p=itemperature',
                         SPOT_FOCUS_URL=base+'/control?p=focus', SPOT_ACTUATOR_URL=base+'/control?p=actuator')
        for name, value in overrides.items():
            stack.enter_context(patch.object(config, name, value))
        assert Path(config.SPOT_IMAGE_CAPTURE_PATH).resolve().is_relative_to(root.resolve())
        stack.enter_context(patch.object(service_module, 'operator_metadata_store',
                                        OperatorMetadataStore(root/'metadata.json')))
        logger = CSVLoggerService(require_runtime_manifest_state=True)
        service = service_module.PLCService(use_mock=False,
                        operator_metadata_runtime_state_path=root/'runtime.json')
        driver = service.driver
        # Replace only the driver's socket module reference, leaving native HTTP sockets real.
        socket_proxy = SimpleNamespace(**{name: getattr(socket, name) for name in dir(socket)})
        socket_proxy.socket = lambda *_args, **_kwargs: FakeSocket()
        stack.enter_context(patch.object(real_plc, 'socket', socket_proxy))
        stack.enter_context(patch.object(driver, '_read_extruder',
                                        return_value={'Count': 20, 'Speed': 1, 'Press': 30}))
        stack.enter_context(patch.object(driver, '_read_ls', return_value={'Temp_F': 450}))
        stack.enter_context(patch.object(service_module, 'logger_service', logger))
        stack.enter_context(patch.object(app, 'logger_service', logger))
        stack.enter_context(patch.object(app, 'plc_service', service))
        stack.enter_context(patch.object(app.os, '_exit', side_effect=exit_codes.append))

        async def exercise():
            transport = observation = journal = None
            write_entered, write_release = threading.Event(), threading.Event()
            shutdown_task = None
            try:
                logger.start()
                await spot_api.start_spot_poll_loop()
                service.start()
                owned.update(csv=logger.thread, service=service.thread, driver_reader=service.driver_thread)
                owned.update({f'driver_worker_{i}': thread for i, thread in enumerate(driver._worker_threads)})
                assert len(driver._worker_threads) == 3
                transport = spot_api._spot_http_transport
                observation = spot_api._spot_observation_queue
                journal = spot_api._spot_diagnostic_journal
                owned.update(http_executor=transport._executor._thread,
                             http_watchdog=transport._response_deadline_thread,
                             observation_writer=observation._thread, journal_writer=journal._writer_thread)
                deadline = time.monotonic() + 20
                next_image = 0.0
                while time.monotonic() < deadline:
                    if time.monotonic() >= next_image:
                        body, _ = await spot_api.fetch_image_async()
                        assert body == jpeg.getvalue()
                        next_image = time.monotonic() + 3.1
                    if (temperature_requests >= 3 and observation.snapshot()['completed_count'] >= 3
                            and spot_api.get_spot_image_capture_health()['written_count'] >= 2
                            and logger._sample_seq > 0):
                        break
                    await asyncio.sleep(.05)
                else:
                    raise AssertionError('Production owners did not produce required evidence')
                owned['image_writer'] = spot_api._spot_image_capture_thread
                tasks.extend(task for task in (spot_api._spot_poll_task, spot_api._spot_diagnostics_task,
                    spot_api._internal_temperature_task) if task is not None)
                assert all(thread is not None and thread.is_alive() for thread in owned.values())
                before_journal = journal.snapshot()
                if recover:
                    assert before_journal['failure_count_total'] >= 1
                    # Hold a real fact write at the file I/O boundary. The
                    # production queue and shutdown must retain this unfinished
                    # work until it is released; no stop/close method is mocked.
                    original_write = observation._writer.write_fact
                    def delayed_write(*args, **kwargs):
                        write_entered.set()
                        if not write_release.wait(10):
                            raise AssertionError('test did not release fact write')
                        return original_write(*args, **kwargs)
                    stack.enter_context(patch.object(observation._writer, 'write_fact', side_effect=delayed_write))
                    assert await asyncio.to_thread(write_entered.wait, 5)
                    assert observation.snapshot()['inflight'] is True
                    assert observation.snapshot()['pending_write_count'] >= 1
                result['before'] = dict(observation=observation.snapshot(), journal=before_journal,
                                       csv=logger.get_runtime_state(), transport=transport.diagnostics())
                # Invoke the actual app shutdown. os._exit alone is intercepted for final inspection.
                shutdown_task = asyncio.create_task(app._run_control_shutdown(
                    'synthetic-terminal-recovery' if recover else 'synthetic-terminal'))
                if recover:
                    assert await asyncio.to_thread(observation._stop.wait, 1)
                    assert not shutdown_task.done()
                    assert observation._thread.is_alive()
                    assert observation.snapshot()['pending_write_count'] >= 1
                    write_release.set()
                await shutdown_task
                assert exit_codes == [0], exit_codes
                # Retain the merged image evidence/final-log shutdown contract.
                # This writer is created during shutdown, after the active-owner snapshot.
                from backend.FacilityData.shutdown_evidence import read_receipt
                evidence = app._get_shutdown_evidence_status()
                assert evidence['all_attempts_verified'] is True
                assert evidence['pending_writers'] == evidence['failed_attempts'] == []
                receipts = []
                for attempt in app._shutdown_evidence_attempts.values():
                    state = attempt.status()
                    assert state['receipt_verified'] and not state['writer_alive']
                    assert attempt._io_thread is not None and not attempt._io_thread.is_alive()
                    begin = read_receipt(attempt.root / f'{attempt.attempt_id}.begin.json')
                    final = read_receipt(attempt.root / f'{attempt.attempt_id}.final.json')
                    assert final['begin_sha256'] == state['begin_sha256']
                    assert begin['attempt_id'] == final['attempt_id'] == attempt.attempt_id
                    assert final['stage_exit_code'] == 0
                    assert final['process_exit_observed'] is False
                    receipts.append(state)
                assert receipts
                result['shutdown_evidence'] = dict(status=evidence, receipts=receipts)
                assert all(task.done() for task in tasks)
                assert all(not thread.is_alive() for thread in owned.values())
                assert driver._worker_threads == []
                assert not transport._active_connections
                obs = observation.snapshot()
                assert obs['writes_drained'] and not obs['writer_alive'] and not obs['accepting']
                for key in ('pending_write_count', 'queue_depth', 'inflight', 'write_failure_count',
                            'spool_failure_count', 'spool_pending_count', 'rejected_count'):
                    assert obs[key] == 0, (key, obs[key])
                image = spot_api.get_spot_image_capture_health()
                assert spot_api._SPOT_IMAGE_CAPTURE_QUEUE.unfinished_tasks == 0
                for key in ('queue_size', 'failure_count', 'dropped_count'):
                    assert image[key] == 0, (key, image[key])
                assert image['written_count'] == image['enqueued_count'] >= 2
                final_journal = journal.snapshot()
                for key in ('active_request_count', 'pending_persist_count', 'write_failure_count',
                            'persist_queue_drop_count', 'invalid_transition_count'):
                    assert final_journal[key] == 0, (key, final_journal[key])
                assert not final_journal['accepting_persistence']
                assert final_journal['failure_count_total'] == before_journal['failure_count_total']
                for event in before_journal['failure_events']:
                    assert event in final_journal['failure_events']
                csv_state = logger.get_runtime_state()
                assert csv_state['queue_size'] == csv_state['buffer_size'] == csv_state['drop_count'] == 0
                assert logger._shutdown_flush_succeeded is True
                assert not logger._runtime_write_failure_observed
                diag = transport.diagnostics()
                assert diag['source_port_transport_pending_count'] == 0
                assert diag['source_port_pool_leased_count'] == 0
                assert diag['source_port_pool_guarded_count'] == 0
                assert diag['source_port_bind_collision_count'] == 0
                result['after'] = dict(observation=obs, image=image, journal=final_journal,
                    csv=csv_state, transport=diag, poll=spot_api.get_spot_poll_shutdown_status(),
                    thread_objects={role: dict(ident=thread.ident, name=thread.name, alive=thread.is_alive())
                                    for role, thread in owned.items()}, task_count=len(tasks), exit_codes=exit_codes)
            finally:
                # No test-owned wait is left behind, even when an assertion fails.
                write_release.set()
                if shutdown_task is not None:
                    await asyncio.gather(shutdown_task, return_exceptions=True)
                await spot_api.stop_spot_poll_loop()
                service.stop()
                spot_api.stop_spot_image_capture_for_shutdown()
                logger.stop()
                spot_api.stop_spot_diagnostic_request_journal()
                for attempt in app._shutdown_evidence_attempts.values():
                    if attempt._io_thread is not None:
                        attempt._io_thread.join(3)
                        assert not attempt._io_thread.is_alive()
                for thread in owned.values():
                    if thread is not None:
                        thread.join(3)
                        assert not thread.is_alive(), thread.name

        try:
            asyncio.run(exercise())
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(3)
            assert not server_thread.is_alive()
    csv_paths = list(log_root.glob('Factory_Integrated_Log_v2_*.csv'))
    assert csv_paths, list(log_root.iterdir())
    rows = []
    for path in csv_paths:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows.extend(csv.DictReader(stream))
    assert rows and any(row.get('spot_observation_key') for row in rows)
    metadata_paths = list(log_root.glob('Factory_Integrated_Log_v2_*.metadata.json'))
    assert metadata_paths
    observation_path = log_root/'spot_observation_fact.csv'
    with observation_path.open(encoding='utf-8-sig', newline='') as stream:
        observations = list(csv.DictReader(stream))
    if recover:
        first = observations[0]
        assert first['spot_poll_status'] == 'http_error' and first['spot_http_status_code'] == '503'
        assert any(row['spot_poll_status'] == 'success' and row['spot_raw_validity'] == 'valid_temperature'
                   and float(row['spot_temperature_raw']) == 500
                   and row['spot_service_instance_id'] == first['spot_service_instance_id']
                   and int(row['spot_poll_seq']) > int(first['spot_poll_seq']) for row in observations[1:])
        failed_events = [json.loads(line) for line in
                         (log_root/'spot_diagnostic_request_failures.jsonl').read_text(encoding='utf-8').splitlines()]
        for event in result['before']['journal']['failure_events']:
            assert event in failed_events
    for path in metadata_paths:
        metadata = json.loads(path.read_text(encoding='utf-8'))
        assert metadata['csv_closeout']['finalized'] is True
        assert metadata['csv_closeout']['closeout_reason'] == 'shutdown'
        manifest = metadata['spot_observation_fact_manifest']
        assert manifest['sha256'] == hashlib.sha256(observation_path.read_bytes()).hexdigest()
        assert manifest['link_coverage']['missing_fact_key_rows'] == 0
        assert manifest['spool_pending_count'] == manifest['write_failure_count'] == 0
    # The image manifest embedded when CSV opens is a startup snapshot. The
    # separate final manifest is the existing authoritative image closeout.
    image_manifest = json.loads((log_root/'spot_image_fact_manifest.final.json').read_text(encoding='utf-8'))
    assert image_manifest['sha256'] == hashlib.sha256((log_root/'spot_image_fact.csv').read_bytes()).hexdigest()
    assert image_manifest['row_count'] == result['after']['image']['written_count']
    result.update(recovered= recover, http_requests=len(requests), csv_rows=len(rows),
                  files=[dict(path=str(path.relative_to(root)), size=path.stat().st_size,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                         for path in log_root.rglob('*') if path.is_file()])
    (root/'result.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'recovered': recover, 'csv_rows': len(rows), 'owned_threads': len(owned),
                      'exit_codes': exit_codes, 'terminal_drain_verified': True}))


@unittest.skipUnless(sys.platform == 'win32', 'Requires production Windows source-port enforcement')
class TerminalIntegrationTests(unittest.TestCase):
    def test_production_recovery_and_normal_terminal_drain(self):
        for recover in (False, True):
            with self.subTest(recover=recover), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                env = dict(os.environ, APPDATA=str(root/'appdata'), SFL_CONFIG_PATH=str(root/'config.ini'),
                           V2_MODE='MOCK', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
                process = subprocess.run([sys.executable, '-B', '-m',
                    'backend.tests.test_temperature_terminal_integration', '--child', str(root), str(int(recover))],
                    cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True,
                    encoding='utf-8', timeout=60)
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                result = json.loads((root/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(result['after']['exit_codes'], [0])
                print(process.stdout)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        run_child(Path(sys.argv[2]), bool(int(sys.argv[3])))
    else:
        unittest.main()
