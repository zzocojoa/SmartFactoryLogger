"""Production image worker and shutdown evidence regressions; no device I/O."""
import asyncio
import copy
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image
from backend import app
from backend.FacilityData.drivers import spot_api as spot
from backend.FacilityData import shutdown_evidence as evidence
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.schemas import FactoryData


class ImageShutdownEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        # Windows asyncio creates its private socketpair before the network guard.
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.loop.close)
        self.network = [self.stack.enter_context(patch.object(
            socket.socket, name, side_effect=AssertionError('device I/O forbidden')
        )) for name in ('connect', 'connect_ex', 'sendto')]
        spot._reset_spot_image_capture_state_for_tests()
        for name in ('_shutdown_evidence_status', '_shutdown_evidence_attempts'):
            self.stack.enter_context(patch.object(app, name, {}))
        for name in (
            '_spot_shutdown_task_states', '_spot_shutdown_image_refresh_stopped',
            '_spot_shutdown_transport_stopped', '_spot_shutdown_started_monotonic',
            '_spot_http_transport_shutdown_started', '_img_accepting_requests',
            '_spot_diagnostic_journal_shutdown_started', '_spot_diagnostic_journal_closed_snapshot',
        ):
            self.stack.enter_context(patch.object(spot, name, copy.deepcopy(getattr(spot, name))))
        for key, value in {
            'APP_DATA_DIR': self.root / 'appdata', 'LOG_PATH': str(self.root),
            'SPOT_IMAGE_CAPTURE_MODE': 'all', 'SPOT_IMAGE_CAPTURE_ENABLED': True,
            'SPOT_IMAGE_CAPTURE_PATH': 'images', 'SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC': 0.,
            'SPOT_IMAGE_CAPTURE_RETENTION_DAYS': 0, 'SPOT_IMAGE_CAPTURE_MAX_BYTES': 2000000,
            'SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION': False,
            'SPOT_IMAGE_CAPTURE_SHUTDOWN_TIMEOUT_SEC': 2.,
        }.items():
            self.stack.enter_context(patch.object(spot.config, key, value))
        self.releases = []
        self.controllers = []
        self.sequence = 0
        self.write_bytes = Path.write_bytes

    def tearDown(self):
        for event in self.releases:
            event.set()
        for thread in self.controllers:
            thread.join(3)
            self.assertFalse(thread.is_alive())
        for attempt in list(app._shutdown_evidence_attempts.values()):
            worker = attempt._io_thread
            if worker is not None and worker.ident is not None:
                worker.join(3)
                self.assertFalse(worker.is_alive(), 'evidence writer leaked')
        spot.stop_spot_image_capture_writer(3)
        worker = spot._spot_image_capture_thread
        self.assertFalse(worker is not None and worker.is_alive())
        spot._reset_spot_image_capture_state_for_tests()
        self.assertEqual(sum(guard.call_count for guard in self.network), 0)

    def enqueue(self):
        self.sequence += 1
        data = io.BytesIO()
        Image.new('RGB', (2, 2), (self.sequence % 255, 2, 3)).save(data, format='JPEG')
        spot._maybe_enqueue_spot_image_capture(
            image_bytes=data.getvalue(), captured_at=1790640000. + self.sequence,
            image_url='http://synthetic.invalid/image.jpg', source='test', image_age_ms=0,
        )

    def history(self, count=13):
        def fail(path, data):
            if path.is_relative_to(self.root / 'images'):
                raise OSError('synthetic file write failure')
            return self.write_bytes(path, data)
        with patch.object(Path, 'write_bytes', fail):
            for _ in range(count):
                self.enqueue()
            self.assertTrue(spot.flush_spot_image_capture_queue(3))

    def block_write(self, fail=False):
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        def write(path, data):
            if path.is_relative_to(self.root / 'images'):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('test release missing')
                if fail:
                    raise OSError('synthetic drain failure')
            return self.write_bytes(path, data)
        self.stack.enter_context(patch.object(Path, 'write_bytes', write))
        return entered, release

    def test_history_preserved_after_real_drain_and_repeat_stop(self):
        self.history()
        before = spot.begin_spot_image_capture_shutdown()
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        worker = spot._spot_image_capture_thread
        self.assertFalse(spot.stop_spot_image_capture_for_shutdown(2))
        self.assertFalse(spot.stop_spot_image_capture_for_shutdown(2))
        after = spot.get_spot_image_capture_shutdown_status()
        self.assertIs(worker, spot._spot_image_capture_thread)
        self.assertFalse(worker.is_alive())
        self.assertTrue(after['writes_drained'])
        self.assertTrue(after['integrity_unresolved'])
        self.assertTrue(after['accounting_consistent'])
        self.assertEqual(after['historical_failures'], 13)
        self.assertEqual(after['new_failures_during_drain'], 0)
        self.assertEqual(after['failure_count'], 13)
        self.assertEqual(after['historical_last_error_at'], before['historical_last_error_at'])
        self.assertEqual(after['shutdown_id'], before['shutdown_id'])
        self.enqueue()
        self.assertEqual(spot.get_spot_image_capture_shutdown_status()['enqueued_count'], 14)

    def test_inflight_and_queued_timeout_late_exit_are_distinct(self):
        entered, release = self.block_write()
        self.enqueue()
        self.assertTrue(entered.wait(3))
        initial = spot.begin_spot_image_capture_shutdown()
        self.assertEqual(initial['queue_size'], 0)
        self.assertEqual(initial['unfinished_tasks'], 1)
        self.assertEqual(initial['inflight_count'], 1)
        self.enqueue()
        self.assertFalse(spot.stop_spot_image_capture_for_shutdown(.01))
        timed_out = spot.get_spot_image_capture_shutdown_status()
        self.assertTrue(timed_out['worker_alive'])
        self.assertFalse(timed_out['writes_drained'])
        self.assertTrue(timed_out['integrity_unresolved'])
        self.assertEqual(timed_out['unfinished_tasks'], 2)
        release.set()
        self.assertTrue(spot.stop_spot_image_capture_for_shutdown(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertTrue(final['writes_drained'])
        self.assertEqual(final['shutdown_id'], initial['shutdown_id'])
        self.assertEqual(final['written_count'], 2)
        self.assertTrue(timed_out['worker_alive'], 'prior snapshot must remain immutable')

    def test_concurrent_begin_and_stop_keep_first_baseline(self):
        self.history()
        entered, release = self.block_write(fail=True)
        self.enqueue()
        self.assertTrue(entered.wait(3))
        before = spot.begin_spot_image_capture_shutdown()
        results = []
        def stop():
            results.append((spot.begin_spot_image_capture_shutdown(),
                            spot.stop_spot_image_capture_for_shutdown(.01)))
        for _ in range(4):
            thread = threading.Thread(target=stop)
            self.controllers.append(thread)
            thread.start()
        for thread in self.controllers:
            thread.join(3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 4)
        self.assertTrue(all(value['shutdown_id'] == before['shutdown_id'] and not ok
                            for value, ok in results))
        release.set()
        self.assertFalse(spot.stop_spot_image_capture_for_shutdown(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['historical_failures'], 13)
        self.assertEqual(final['new_failures_during_drain'], 1)
        self.assertEqual(final['failure_count'], 14)
        self.assertTrue(final['writes_drained'])

    def test_status_is_pure_memory_and_copies_baseline(self):
        with patch.object(spot, '_get_spot_image_capture_writer', side_effect=AssertionError), \
             patch.object(spot, '_start_spot_image_capture_worker', side_effect=AssertionError):
            idle = spot.get_spot_image_capture_shutdown_status()
            self.assertIsNone(idle['historical_failures'])
            self.assertFalse(idle['writes_drained'])
            before = spot.begin_spot_image_capture_shutdown()
            before['historical_failures'] = 400
            self.assertEqual(spot.get_spot_image_capture_shutdown_status()['historical_failures'], 0)

    def test_receipt_no_clobber_tamper_missing_sidecar_and_fsync_failure(self):
        path = self.root / 'receipt.json'
        payload = {'historical_failures': 13}
        evidence.preserve_receipt(path, payload)
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            evidence.preserve_receipt(path, {'historical_failures': 0})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(evidence.read_receipt(path), payload)
        path.write_bytes(b'{}')
        with self.assertRaises(ValueError):
            evidence.read_receipt(path)
        missing = self.root / 'missing.json'
        missing.write_text('{}')
        with self.assertRaises(FileNotFoundError):
            evidence.read_receipt(missing)
        for index, fail in enumerate(([OSError('data fsync')], [None, OSError('hash fsync')])):
            target = self.root / f'fsync-{index}.json'
            with patch.object(evidence.os, 'fsync', side_effect=fail):
                with self.assertRaises(OSError):
                    evidence.preserve_receipt(target, payload)
            self.assertFalse(target.with_name(target.name + '.sha256').exists())
            with self.assertRaises(FileNotFoundError):
                evidence.read_receipt(target)
            self.assertTrue(list(self.root.glob(target.name + '*.pending')))

    def test_receipt_open_link_readback_and_redirect_fail_closed(self):
        for name, target, method in (
            ('open', Path, 'open'), ('link', evidence.os, 'link'), ('readback', Path, 'read_bytes'),
        ):
            with self.subTest(name=name), patch.object(target, method, side_effect=OSError(name)):
                with self.assertRaises(OSError):
                    evidence.preserve_receipt(self.root / f'{name}.json', {'x': 1})
        original_lstat = Path.lstat
        redirected = self.root / 'redirected'
        class JunctionStat:
            st_mode = 0
            st_file_attributes = 0x400
        def lstat(path):
            return JunctionStat() if path == redirected else original_lstat(path)
        with patch.object(Path, 'lstat', lstat):
            with self.assertRaisesRegex(OSError, 'redirected'):
                evidence.preserve_receipt(redirected / 'record.json', {'x': 1})
        self.assertFalse(redirected.exists())

    def test_attempt_binding_distinct_callers_and_late_observations(self):
        async def run():
            return await asyncio.gather(app._begin_shutdown_evidence('control'),
                                        app._begin_shutdown_evidence('lifespan'))
        control, lifespan = self.loop.run_until_complete(run())
        for attempt in (control, lifespan):
            attempt._io_thread.join(3)
            self.assertFalse(attempt._io_thread.is_alive())
        self.assertNotEqual(control.attempt_id, lifespan.attempt_id)
        root = self.root / 'appdata' / 'shutdown_evidence'
        first = evidence.read_receipt(root / f'{control.attempt_id}.begin.json')
        second = evidence.read_receipt(root / f'{lifespan.attempt_id}.begin.json')
        self.assertEqual(first['image_shutdown_id'], second['image_shutdown_id'])
        self.assertEqual(first['identity']['backend_process_id'], os.getpid())
        self.assertEqual(first['identity']['backend_session_id'], app._app_session_id)
        self.assertEqual(first['identity']['backend_generation_id'], app._backend_generation_id)
        self.assertEqual(first['identity']['started_at'], app._app_started_at_iso)
        bad = {**spot.get_spot_image_capture_shutdown_status(), 'shutdown_id': 'different'}
        self.assertFalse(control.finish(image=bad, stages={}, stage_exit_code=0))
        self.assertFalse(control.status()['receipt_verified'])
        self.assertTrue(spot.stop_spot_image_capture_for_shutdown(2))
        self.assertTrue(lifespan.finish(image=spot.get_spot_image_capture_shutdown_status(),
                                       stages={}, stage_exit_code=0))
        final = evidence.read_receipt(root / f'{lifespan.attempt_id}.final.json')
        self.assertFalse(final['installation_clearance'])
        self.assertFalse(final['process_exit_observed'])
        self.assertEqual(final['begin_sha256'], hashlib.sha256(
            (root / f'{lifespan.attempt_id}.begin.json').read_bytes()).hexdigest())
        self.assertFalse(lifespan.finish(image=spot.get_spot_image_capture_shutdown_status(),
                                        stages={}, stage_exit_code=0), 'repeat must not replace a final')
        self.assertEqual(evidence.read_receipt(root / f'{lifespan.attempt_id}.final.json'), final)

    def run_control(self):
        with patch.object(app.os, '_exit') as exit_process:
            self.loop.run_until_complete(app._run_control_shutdown('must-not-appear-in-receipt'))
        exit_process.assert_called_once()
        return exit_process.call_args.args[0]

    def final_control(self):
        state = app._get_shutdown_evidence_status()['control']
        path = self.root / 'appdata' / 'shutdown_evidence' / f"{state['attempt_id']}.final.json"
        return evidence.read_receipt(path)

    def test_control_real_image_csv_shutdown_preserves_history_and_old_manifest(self):
        self.history()
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        old = self.root / 'spot_image_fact_manifest.final.json'
        old_bytes = b'{"previous_generation":true}\n'
        old.write_bytes(old_bytes)
        logger = CSVLoggerService()
        logger.fallback_log_dir = self.root
        logger.apply_config(log_path=self.root, auto_save=True, csv_v2_enabled=True)
        logger.start()
        thread = logger.thread
        logger.enqueue(FactoryData(Time='2026-09-30T10:00:00+09:00', Count=0, Press=0., Speed=0.))
        try:
            with patch.object(app, 'logger_service', logger):
                self.assertEqual(self.run_control(), 2)
            self.assertFalse(thread.is_alive())
            result = self.final_control()
            self.assertFalse(result['stages']['spot_image_capture_drained'])
            self.assertTrue(result['stages']['logger_service_stopped'])
            self.assertTrue(result['image_capture']['writes_drained'])
            self.assertEqual(result['image_capture']['historical_failures'], 13)
            self.assertEqual(result['image_capture']['new_failures_during_drain'], 0)
            self.assertEqual(result['stage_exit_code'], 2)
            self.assertTrue(app._get_shutdown_evidence_status()['control']['receipt_verified'])
            self.assertEqual(old.read_bytes(), old_bytes)
            files = list(self.root.glob('Factory_Integrated_Log_v2_*.metadata.json'))
            self.assertEqual(len(files), 1)
            closeout = json.loads(files[0].read_text('utf-8-sig'))['csv_closeout']
            self.assertTrue(closeout['finalized'])
            self.assertEqual(closeout['final_persisted_sample_seq'], 1)
            self.assertEqual(closeout['logger_service_instance_id'], logger.logger_service_instance_id)
            self.assertNotIn('must-not-appear-in-receipt', json.dumps(result))
            self.assertNotIn('synthetic.invalid', json.dumps(result))
        finally:
            self.assertTrue(logger.stop(timeout_sec=3, finalize_spot_image_manifest=False))
            self.assertFalse(thread.is_alive())

    def test_control_baseline_precedes_real_transport_drain(self):
        self.history()
        entered, release = self.block_write(fail=True)
        self.enqueue()
        self.assertTrue(entered.wait(3))
        observed = []
        class Transport:
            async def close(transport_self, *, timeout_sec):
                observed.append(spot.get_spot_image_capture_shutdown_status())
                release.set()
                self.assertTrue(await asyncio.to_thread(spot.flush_spot_image_capture_queue, 3))
                return True
        with patch.object(spot, '_spot_http_transport', Transport()):
            self.assertEqual(self.run_control(), 2)
        self.assertEqual(observed[0]['historical_failures'], 13)
        result = self.final_control()['image_capture']
        self.assertEqual(result['failure_count'], 14)
        self.assertEqual(result['historical_failures'], 13)
        self.assertEqual(result['new_failures_during_drain'], 1)

    def test_control_receipt_failure_still_stops_worker_and_exits_two(self):
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        with patch.object(evidence.os, 'fsync', side_effect=OSError('evidence failure')):
            self.assertEqual(self.run_control(), 2)
        self.assertTrue(spot.get_spot_image_capture_shutdown_status()['writes_drained'])
        status = app._get_shutdown_evidence_status()['control']
        self.assertFalse(status['before_verified'])
        self.assertFalse(status['receipt_verified'])

    def test_control_clean_shutdown_verified_receipt_and_exit_zero(self):
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        self.assertEqual(self.run_control(), 0, self.final_control())
        result = self.final_control()
        self.assertEqual(result['stage_exit_code'], 0)
        self.assertTrue(result['image_capture']['writes_drained'])
        self.assertFalse(result['image_capture']['integrity_unresolved'])

    def test_control_timeout_receipt_is_not_rewritten_by_late_worker_exit(self):
        entered, release = self.block_write()
        self.enqueue()
        self.assertTrue(entered.wait(3))
        worker = spot._spot_image_capture_thread
        with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_SHUTDOWN_TIMEOUT_SEC', .01):
            self.assertEqual(self.run_control(), 2)
        state = app._get_shutdown_evidence_status()['control']
        path = self.root / 'appdata' / 'shutdown_evidence' / f"{state['attempt_id']}.final.json"
        original = path.read_bytes()
        timed_out = evidence.read_receipt(path)
        self.assertTrue(timed_out['image_capture']['worker_alive'])
        self.assertEqual(timed_out['image_capture']['unfinished_tasks'], 1)
        release.set()
        self.assertTrue(spot.stop_spot_image_capture_for_shutdown(3))
        self.assertIs(worker, spot._spot_image_capture_thread)
        self.assertFalse(worker.is_alive())
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.run_control(), 0)
        later = self.final_control()
        self.assertNotEqual(later['attempt_id'], timed_out['attempt_id'])
        self.assertEqual(later['image_shutdown_id'], timed_out['image_shutdown_id'])
        self.assertEqual(path.read_bytes(), original)

    def test_final_receipt_failure_preserves_begin_and_never_exits_zero(self):
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        original_fsync = os.fsync
        calls = []
        def fsync(fd):
            calls.append(fd)
            if len(calls) == 3:
                raise OSError('final receipt fsync')
            return original_fsync(fd)
        with patch.object(evidence.os, 'fsync', fsync):
            self.assertEqual(self.run_control(), 2)
        state = app._get_shutdown_evidence_status()['control']
        self.assertTrue(state['before_verified'])
        self.assertFalse(state['receipt_verified'])
        self.assertFalse(state['final_verified'])
        self.assertTrue(spot.get_spot_image_capture_shutdown_status()['writes_drained'])
        root = self.root / 'appdata' / 'shutdown_evidence'
        self.assertTrue((root / f"{state['attempt_id']}.begin.json").exists())
        self.assertFalse((root / f"{state['attempt_id']}.final.json").exists())

    def test_lifespan_partial_start_keeps_primary_error_and_records_real_csv_stop(self):
        for fail_receipt in (False, True):
            with self.subTest(fail_receipt=fail_receipt), ExitStack() as stack:
                logger = CSVLoggerService()
                logger.fallback_log_dir = self.root
                logger.apply_config(log_path=self.root, auto_save=True, csv_v2_enabled=True)
                stack.enter_context(patch.object(app, 'logger_service', logger))
                stack.enter_context(patch.object(app, '_lock_path', self.root / 'instance.lock'))
                # Inject a partial startup error at the unrelated config service
                # boundary. App lifespan, CSV start/stop and receipts stay real.
                csv_threads = []
                def fail_start():
                    csv_threads.append(logger.thread)
                    raise OSError('primary startup failure')
                stack.enter_context(patch.object(app.config_sync_agent, 'start', side_effect=fail_start))
                if fail_receipt:
                    stack.enter_context(patch.object(evidence.os, 'fsync', side_effect=OSError('receipt failure')))
                async def run():
                    async with app.lifespan(app.app):
                        self.fail('startup should not succeed')
                try:
                    with self.assertRaisesRegex(OSError, 'primary startup failure'):
                        self.loop.run_until_complete(run())
                    self.assertEqual(len(csv_threads), 1)
                    self.assertIsNotNone(csv_threads[0])
                    self.assertFalse(csv_threads[0].is_alive())
                    self.assertFalse((self.root / 'instance.lock').exists())
                    state = app._get_shutdown_evidence_status()['lifespan']
                    self.assertEqual(state['receipt_verified'], not fail_receipt)
                    if not fail_receipt:
                        path = self.root / 'appdata' / 'shutdown_evidence' / f"{state['attempt_id']}.final.json"
                        value = evidence.read_receipt(path)
                        self.assertEqual(value['stages']['started_services'], ['config_sync', 'csv_logger'])
                        self.assertTrue(value['stages']['primary_error'])
                        self.assertFalse(value['stages']['spot_start_attempted'])
                        self.assertEqual(value['stage_exit_code'], 2)
                finally:
                    self.assertTrue(logger.stop(timeout_sec=3, finalize_spot_image_manifest=False))
                    self.assertTrue(all(not thread.is_alive() for thread in csv_threads))

    def test_evidence_io_stall_never_prevents_real_worker_cleanup(self):
        for phase in ('begin', 'final'):
            with self.subTest(phase=phase), ExitStack() as stack:
                for name in ('_shutdown_evidence_status', '_shutdown_evidence_attempts'):
                    stack.enter_context(patch.object(app, name, {}))
                spot._reset_spot_image_capture_state_for_tests()
                self.enqueue()
                self.assertTrue(spot.flush_spot_image_capture_queue(3))
                entered, release = threading.Event(), threading.Event()
                self.releases.append(release)
                real_fsync = os.fsync
                def fsync(fd):
                    if threading.current_thread().name.startswith(f'shutdown-evidence-{phase}'):
                        entered.set()
                        if not release.wait(10):
                            raise RuntimeError('test did not release receipt')
                    return real_fsync(fd)
                stack.enter_context(patch.object(evidence.os, 'fsync', fsync))
                stack.enter_context(patch.object(app, '_SHUTDOWN_EVIDENCE_WAIT_SEC', .05))
                try:
                    self.assertEqual(self.run_control(), 2)
                    self.assertTrue(entered.is_set())
                    self.assertFalse(release.is_set())
                    self.assertTrue(spot.get_spot_image_capture_shutdown_status()['writes_drained'])
                    state = app._get_shutdown_evidence_status()['control']
                    self.assertTrue(state['writer_alive'])
                    self.assertFalse(state['receipt_verified'])
                    self.assertEqual(state['error_type'], 'EvidenceWriteTimeout')
                    attempt = app._shutdown_evidence_attempts[state['attempt_id']]
                finally:
                    release.set()
                    for current in list(app._shutdown_evidence_attempts.values()):
                        current._io_thread.join(3)
                        self.assertFalse(current._io_thread.is_alive())
                self.assertFalse(attempt.status()['receipt_verified'], 'late I/O cannot reverse timeout')

    def test_cancel_evidence_wait_keeps_cleanup_and_failure_decision(self):
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        real_fsync = os.fsync
        def fsync(fd):
            if threading.current_thread().name.startswith('shutdown-evidence-final'):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('test did not release receipt')
            return real_fsync(fd)
        async def run():
            task = asyncio.create_task(app._run_control_shutdown('cancel-boundary'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                self.assertTrue(spot.get_spot_image_capture_shutdown_status()['writes_drained'])
                task.cancel()
                await asyncio.wait_for(task, 3)
            finally:
                release.set()
                if not task.done():
                    await task
        with patch.object(evidence.os, 'fsync', fsync), patch.object(app.os, '_exit') as exit_process:
            self.loop.run_until_complete(run())
        exit_process.assert_called_once_with(2)
        state = app._get_shutdown_evidence_status()['control']
        self.assertEqual(state['error_type'], 'EvidenceWaitCancelled')
        attempt = app._shutdown_evidence_attempts[state['attempt_id']]
        attempt._io_thread.join(3)
        self.assertFalse(attempt._io_thread.is_alive())
        self.assertFalse(attempt.status()['receipt_verified'])

    def test_control_and_partial_lifespan_cleanup_overlap_without_mixing_receipts(self):
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        logger = CSVLoggerService()
        logger.fallback_log_dir = self.root
        logger.apply_config(log_path=self.root, auto_save=True, csv_v2_enabled=True)
        reached, release = threading.Event(), threading.Event()
        self.releases.append(release)
        lock = threading.Lock()
        stopped = []
        csv_threads = []
        def fail_start():
            csv_threads.append(logger.thread)
            raise OSError('partial lifecycle start')
        def stop_config():
            with lock:
                stopped.append(True)
                if len(stopped) == 2:
                    reached.set()
            return release.wait(5)
        async def partial():
            async with app.lifespan(app.app):
                self.fail('partial startup should fail')
        async def run():
            tasks = [asyncio.create_task(partial()), asyncio.create_task(app._run_control_shutdown('overlap'))]
            try:
                self.assertTrue(await asyncio.to_thread(reached.wait, 3))
            finally:
                release.set()
                results = await asyncio.gather(*tasks, return_exceptions=True)
            self.assertIsInstance(results[0], OSError)
            self.assertIsNone(results[1])
        try:
            with patch.object(app, 'logger_service', logger), \
                 patch.object(app, '_lock_path', self.root / 'instance.lock'), \
                 patch.object(app.config_sync_agent, 'start', side_effect=fail_start), \
                 patch.object(app.config_sync_agent, 'stop', side_effect=stop_config), \
                 patch.object(app.os, '_exit') as exit_process:
                self.loop.run_until_complete(run())
            exit_process.assert_called_once_with(0)
            self.assertEqual(len(csv_threads), 1)
            self.assertFalse(csv_threads[0].is_alive())
            status = app._get_shutdown_evidence_status()
            receipts = [evidence.read_receipt(self.root / 'appdata' / 'shutdown_evidence' /
                        f"{status[key]['attempt_id']}.final.json") for key in ('control', 'lifespan')]
            self.assertNotEqual(receipts[0]['attempt_id'], receipts[1]['attempt_id'])
            self.assertEqual(receipts[0]['image_shutdown_id'], receipts[1]['image_shutdown_id'])
            self.assertEqual(receipts[0]['identity'], receipts[1]['identity'])
            self.assertEqual(receipts[0]['stage_exit_code'], 0)
            self.assertEqual(receipts[1]['stage_exit_code'], 2)
            self.assertIn('logger_service_stopped', receipts[0]['stages'])
            self.assertNotIn('logger_service_stopped', receipts[1]['stages'])
        finally:
            release.set()
            self.assertTrue(logger.stop(timeout_sec=3, finalize_spot_image_manifest=False))
            self.assertTrue(all(not thread.is_alive() for thread in csv_threads))

    def test_partial_receipt_write_is_preserved_without_publication(self):
        original_open = Path.open
        class PartialFile:
            def __init__(self, handle):
                self.handle = handle
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.handle.close()
            def write(self, data):
                return self.handle.write(data[:4])
        def open_file(path, *args, **kwargs):
            handle = original_open(path, *args, **kwargs)
            return PartialFile(handle) if path.name.endswith('.pending') else handle
        target = self.root / 'partial.json'
        with patch.object(Path, 'open', open_file):
            with self.assertRaisesRegex(OSError, 'short'):
                evidence.preserve_receipt(target, {'historical_failures': 13})
        self.assertFalse(target.exists())
        self.assertEqual((self.root / 'partial.json.pending').stat().st_size, 4)

    def test_other_entrypoint_receipt_stall_or_failure_blocks_control_exit(self):
        for phase in ('begin', 'final'):
            for fail in (False, True):
                with self.subTest(phase=phase, fail=fail), ExitStack() as stack:
                    for name in ('_shutdown_evidence_status', '_shutdown_evidence_attempts'):
                        stack.enter_context(patch.object(app, name, {}))
                    entered, release = threading.Event(), threading.Event()
                    self.releases.append(release)
                    original_fsync = os.fsync
                    def fsync(fd):
                        if threading.current_thread().name == f'shutdown-evidence-{phase}-lifespan':
                            entered.set()
                            if fail:
                                raise OSError('peer evidence failure')
                            if not release.wait(10):
                                raise RuntimeError('test release missing')
                        return original_fsync(fd)
                    stack.enter_context(patch.object(evidence.os, 'fsync', fsync))
                    async def prepare_peer():
                        peer = await app._begin_shutdown_evidence('lifespan')
                        if phase == 'final':
                            await asyncio.to_thread(peer._io_thread.join, 3)
                            self.assertFalse(peer._io_thread.is_alive())
                            peer.start_finish(image=spot.get_spot_image_capture_shutdown_status(),
                                              stages={}, stage_exit_code=0)
                        self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                        return peer
                    peer = self.loop.run_until_complete(prepare_peer())
                    try:
                        self.assertEqual(self.run_control(), 2)
                        self.assertTrue(app._get_shutdown_evidence_status()['control']['receipt_verified'])
                        self.assertFalse(app._all_shutdown_evidence_verified())
                        self.assertTrue(spot.get_spot_image_capture_shutdown_status()['writes_drained'])
                        if fail:
                            peer._io_thread.join(3)
                            self.assertIsNotNone(peer.status()['error_type'])
                        else:
                            self.assertTrue(peer.status()['writer_alive'])
                    finally:
                        release.set()
                        peer._io_thread.join(3)
                        self.assertFalse(peer._io_thread.is_alive())

    def test_peer_start_during_last_exit_delay_is_rechecked(self):
        original_sleep = asyncio.sleep
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        original_fsync = os.fsync
        peers = []
        def fsync(fd):
            if threading.current_thread().name == 'shutdown-evidence-begin-lifespan':
                entered.set()
                if not release.wait(10):
                    raise RuntimeError('test release missing')
            return original_fsync(fd)
        async def delay(seconds):
            if seconds == .2:
                self.assertTrue(app._get_shutdown_evidence_status()['control']['receipt_verified'])
                peers.append(await app._begin_shutdown_evidence('lifespan'))
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
            await original_sleep(seconds)
        try:
            with patch.object(evidence.os, 'fsync', fsync), patch.object(app.asyncio, 'sleep', delay):
                self.assertEqual(self.run_control(), 2)
            self.assertEqual(len(peers), 1)
            self.assertTrue(peers[0].status()['writer_alive'])
        finally:
            release.set()
            for peer in peers:
                peer._io_thread.join(3)
                self.assertFalse(peer._io_thread.is_alive())

    def test_failed_attempt_cannot_be_hidden_by_new_successful_receipt(self):
        with patch.object(evidence.os, 'fsync', side_effect=OSError('first attempt failed')):
            self.assertEqual(self.run_control(), 2)
        failed_id = app._get_shutdown_evidence_status()['control']['attempt_id']
        self.assertEqual(self.run_control(), 2)
        status = app._get_shutdown_evidence_status()['control']
        self.assertNotEqual(status['attempt_id'], failed_id)
        self.assertTrue(status['receipt_verified'])
        self.assertFalse(app._shutdown_evidence_attempts[failed_id].status()['receipt_verified'])
        self.assertFalse(app._all_shutdown_evidence_verified())
        state = app._get_shutdown_evidence_status()
        self.assertFalse(state['all_attempts_verified'])
        self.assertEqual([item['attempt_id'] for item in state['failed_attempts']], [failed_id])

    def test_changed_begin_receipt_never_binds_to_successful_final(self):
        attempt = self.loop.run_until_complete(app._begin_shutdown_evidence('control'))
        attempt._io_thread.join(3)
        self.assertFalse(attempt._io_thread.is_alive())
        path = self.root / 'appdata' / 'shutdown_evidence' / f'{attempt.attempt_id}.begin.json'
        original = evidence.read_receipt(path)
        changed = {**original, 'identity': {**original['identity'], 'backend_generation_id': 'another'}}
        data = json.dumps(changed).encode()
        path.write_bytes(data)
        path.with_name(path.name + '.sha256').write_text(hashlib.sha256(data).hexdigest())
        self.assertFalse(attempt.finish(image=spot.get_spot_image_capture_shutdown_status(),
                                        stages={}, stage_exit_code=0))
        self.assertEqual(attempt.status()['error_phase'], 'binding')
        self.assertFalse(attempt.status()['receipt_verified'])

    def test_control_health_preserves_auth_and_additive_model_without_io(self):
        import httpx
        async def exercise():
            for address, expected in (('127.0.0.1', 200), ('192.0.2.10', 403)):
                transport = httpx.ASGITransport(app=app.app, client=(address, 4567))
                async with httpx.AsyncClient(transport=transport, base_url='http://local.test') as client:
                    response = await client.get('/api/control/health')
                self.assertEqual(response.status_code, expected)
                if expected == 200:
                    body = response.json()
                    self.assertEqual(body['backend_process_id'], os.getpid())
                    self.assertEqual(body['backend_session_id'], app._app_session_id)
                    self.assertIn('unfinished_tasks', body['image_capture_shutdown'])
                    self.assertIn('shutdown_evidence', body)
        with patch.dict(os.environ, {'SFL_CONTROL_TOKEN': ''}), \
             patch.object(spot, '_get_spot_image_capture_writer', side_effect=AssertionError), \
             patch.object(spot, '_start_spot_image_capture_worker', side_effect=AssertionError):
            self.loop.run_until_complete(exercise())


if __name__ == '__main__':
    unittest.main()
