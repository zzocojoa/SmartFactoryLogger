"""Production image worker and shutdown evidence regressions; no device I/O."""
import asyncio
import copy
import csv
from contextlib import ExitStack
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tracemalloc
import unittest
from unittest.mock import patch

from PIL import Image
from backend import app
from backend.FacilityData.drivers import spot_api as spot
from backend.FacilityData import shutdown_evidence as evidence
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.persistence_pressure import StoragePressureController


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
        return spot._maybe_enqueue_spot_image_capture(
            image_bytes=data.getvalue(), captured_at=1790640000. + self.sequence,
            image_url='http://synthetic.invalid/image.jpg', source='test', image_age_ms=0,
        )

    def history(self, count=13):
        def fail(path, data):
            if path.is_relative_to(self.root / 'images'):
                # This fixture creates terminal historical failures. Temporary
                # OSError now remains pending and is covered by owned recovery.
                raise RuntimeError('synthetic terminal capture failure')
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

    def test_queued_captures_keep_admitted_destinations(self):
        entered, release = self.block_write()
        self.enqueue()
        self.assertTrue(entered.wait(3))
        self.enqueue()
        new_log = self.root / 'new-log'
        new_images = self.root / 'new-images'
        with patch.object(spot.config, 'LOG_PATH', str(new_log)), \
             patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_PATH', str(new_images)):
            self.enqueue()
            release.set()
            self.assertTrue(spot.flush_spot_image_capture_queue(3))
            self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 2)
            self.assertEqual(len(list(new_images.rglob('*.jpg'))), 1)
            with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
                old_rows = list(csv.DictReader(handle))
            with (new_log / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
                new_rows = list(csv.DictReader(handle))
            self.assertEqual(len(old_rows), 2)
            self.assertEqual(len(new_rows), 1)
            for row, parent in [(row, self.root / 'images') for row in old_rows] + \
                               [(row, new_images) for row in new_rows]:
                image = next(parent.rglob(row['spot_image_capture_id'] + '.jpg'))
                self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(),
                                 row['spot_image_sha256'])
            final = spot.get_spot_image_capture_shutdown_status()
            self.assertEqual(final['written_count'], 3)
            self.assertEqual(final['pending_payload_bytes'], 0)
            self.assertTrue(final['accounting_consistent'])

    def test_distinct_acquisitions_with_same_time_and_bytes_keep_both_images(self):
        import httpx

        image = io.BytesIO()
        Image.new('RGB', (2, 2), (31, 2, 3)).save(image, format='JPEG')
        payload = image.getvalue()
        for name in ('_img_cache_entry', '_img_refresh_success_count',
                     '_img_upstream_request_count', '_img_last_upstream_started_at',
                     '_img_last_upstream_completed_at', '_img_failure_count',
                     '_img_last_error_code', '_img_last_error_message', '_img_last_success_at'):
            self.stack.enter_context(patch.object(spot, name, getattr(spot, name)))

        async def receive():
            async with httpx.AsyncClient() as client:
                with patch.object(spot, '_http_client', client), \
                     patch.object(spot, '_request_spot_image', return_value=payload) as request, \
                     patch.object(spot.time, 'time', return_value=1790640000.):
                    first = await spot._refresh_spot_image_cache('http://synthetic.invalid/image.jpg')
                    second = await spot._refresh_spot_image_cache('http://synthetic.invalid/image.jpg')
                    self.assertEqual(request.await_count, 2)
                    self.assertEqual(first.captured_at_epoch, second.captured_at_epoch)
                    self.assertEqual(first.image_bytes, second.image_bytes)

        self.loop.run_until_complete(receive())
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2, 'separate acquisitions must not collapse into one fact')
        self.assertEqual(len({row['spot_image_capture_id'] for row in rows}), 2)
        images = list((self.root / 'images').rglob('*.jpg'))
        self.assertEqual(len(images), 2)
        for row in rows:
            stored = self.root / row['spot_image_path']
            self.assertEqual(stored.read_bytes(), payload)
            self.assertEqual(hashlib.sha256(stored.read_bytes()).hexdigest(), row['spot_image_sha256'])
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 2)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertTrue(final['accounting_consistent'])

    def test_capture_pending_limit_includes_inflight(self):
        self.stack.enter_context(patch.object(spot, '_SPOT_IMAGE_CAPTURE_QUEUE_MAX', 2))
        self.stack.enter_context(patch.object(spot._SPOT_IMAGE_CAPTURE_QUEUE, 'maxsize', 2))
        entered, release = self.block_write()
        self.enqueue()
        self.assertTrue(entered.wait(3))
        self.enqueue()
        self.enqueue()
        pending = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(pending['unfinished_tasks'], 2)
        self.assertEqual(pending['queue_size'], 1)
        self.assertEqual(pending['inflight_count'], 1)
        self.assertEqual(pending['enqueued_count'], 2)
        self.assertEqual(pending['dropped_count'], 1)
        self.assertEqual(pending['dropped_pending_limit_count'], 1)
        self.assertEqual(pending['dropped_queue_full_count'], 0)
        self.assertTrue(pending['accounting_consistent'])
        release.set()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        finished = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(finished['unfinished_tasks'], 0)
        self.assertEqual(finished['written_count'], 3)
        self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 3)
        self.assertEqual(spot.get_spot_image_capture_health()['fact_row_count'], 3)
        self.assertTrue(finished['accounting_consistent'])

    def test_capture_admission_reports_pending_limit_with_identity(self):
        self.stack.enter_context(patch.object(spot, '_SPOT_IMAGE_CAPTURE_QUEUE_MAX', 2))
        entered, release = self.block_write()
        image = io.BytesIO()
        Image.new('RGB', (2, 2), (31, 2, 3)).save(image, format='JPEG')
        payload = image.getvalue()
        identities = [f'spotimg_20260929T000000000000Z_{n:032x}' for n in range(1, 4)]

        def submit(identity):
            return spot._maybe_enqueue_spot_image_capture(
                image_bytes=payload, captured_at=1790640000.,
                image_url='http://synthetic.invalid/image.jpg', source='test',
                capture_id=identity,
            )

        first = submit(identities[0])
        self.assertTrue(entered.wait(3))
        second = submit(identities[1])
        rejected = submit(identities[2])
        self.assertEqual(rejected.status, 'REJECTED_LIMIT')
        self.assertEqual(rejected.reason, 'pending_item_limit')
        self.assertEqual(rejected.capture_id, identities[2])
        self.assertFalse(rejected.accepted)
        self.assertEqual([first.status, second.status], ['ACCEPTED', 'ACCEPTED'])
        self.assertEqual([first.capture_id, second.capture_id], identities[:2])
        self.assertTrue(first.accepted and second.accepted)
        release.set()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([r['spot_image_capture_id'] for r in rows], identities[:2])
        self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 2)
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['dropped_pending_limit_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertTrue(final['accounting_consistent'])

    def test_capture_interval_starts_at_successful_admission(self):
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC', 1.))
        clock = [100.]
        original_put = queue.Queue.put_nowait

        def delayed_put(target, item):
            # Real queue insertion succeeds two seconds after its producer
            # started. The clock boundary is deterministic, without sleeping.
            original_put(target, item)
            if target is spot._SPOT_IMAGE_CAPTURE_QUEUE:
                clock[0] = 102.

        with patch.object(spot.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(queue.Queue, 'put_nowait', delayed_put):
            self.assertTrue(self.enqueue().accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        with patch.object(spot.time, 'monotonic', return_value=102.5):
            receipt = self.enqueue()
        self.assertEqual((receipt.status, receipt.reason), ('DISABLED', 'policy_skipped_interval'))
        with patch.object(spot.time, 'monotonic', return_value=103.):
            self.assertTrue(self.enqueue().accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 2)
        self.assertEqual(final['pending_payload_bytes'], 0)
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row['spot_image_captured_at'] for row in rows],
                         ['2026-09-29T00:00:01Z', '2026-09-29T00:00:03Z'])

    def test_capture_interval_ignores_wall_clock_changes(self):
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC', 1.))

        def submit(wall, monotonic):
            with patch.object(spot.time, 'time', return_value=wall), \
                 patch.object(spot.time, 'monotonic', return_value=monotonic):
                return self.enqueue()

        self.assertTrue(submit(10000., 100.).accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        skipped = submit(100000., 100.5)
        self.assertEqual(skipped.status, 'DISABLED')
        self.assertEqual(skipped.reason, 'policy_skipped_interval')
        # A rejected attempt after the interval must not move its next deadline.
        with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MAX_BYTES', 1):
            rejected = submit(8000., 101.)
        self.assertEqual(rejected.reason, 'image_too_large')
        self.assertTrue(submit(7000., 101.1).accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['enqueued_count'], 2)
        self.assertEqual(final['written_count'], 2)
        self.assertEqual(final['dropped_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['spot_image_captured_at'] for row in rows],
                         ['2026-09-29T00:00:01Z', '2026-09-29T00:00:04Z'])
        self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 2)

    def test_rejected_live_capture_keeps_image_and_reports_identity(self):
        import httpx

        self.stack.enter_context(patch.object(spot, '_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT', 1))
        image = io.BytesIO()
        Image.new('RGB', (2, 2), (31, 2, 3)).save(image, format='JPEG')
        payload = image.getvalue()
        for name in ('_img_cache_entry', '_img_refresh_success_count',
                     '_img_upstream_request_count', '_img_last_upstream_started_at',
                     '_img_last_upstream_completed_at', '_img_failure_count',
                     '_img_last_error_code', '_img_last_error_message', '_img_last_success_at'):
            self.stack.enter_context(patch.object(spot, name, getattr(spot, name)))

        async def receive():
            async with httpx.AsyncClient() as client:
                with patch.object(spot, '_http_client', client), \
                     patch.object(spot, '_request_spot_image', return_value=payload) as request:
                    entry = await spot._refresh_spot_image_cache('http://synthetic.invalid/image.jpg')
                    self.assertEqual(request.await_count, 1)
                    return entry

        with self.assertLogs('spot_control', level='WARNING') as logs:
            entry = self.loop.run_until_complete(receive())
        self.assertEqual(len(logs.records), 1)
        receipt = json.loads(logs.records[0].getMessage().split('rejected ', 1)[1])
        self.assertEqual(receipt['status'], 'REJECTED_LIMIT')
        self.assertEqual(receipt['reason'], 'pending_byte_limit')
        self.assertEqual(receipt['capture_id'], entry.capture_id)
        self.assertTrue(entry.capture_id)
        self.assertNotIn('synthetic.invalid', logs.records[0].getMessage())
        self.assertEqual(entry.image_bytes, payload)
        self.assertIs(spot._img_cache_entry, entry)
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['enqueued_count'], 0)
        self.assertEqual(final['dropped_payload_limit_count'], 1)
        self.assertEqual(final['failure_count'], 0)
        self.assertFalse((self.root / 'spot_image_fact.csv').exists())
        self.assertFalse(list((self.root / 'images').rglob('*.jpg')))

    def test_capture_during_config_apply_uses_complete_previous_settings(self):
        from backend.Configuration import Configuration_DB_Manager as settings

        manager = settings.ConfigManager()
        new_log = self.root / 'new-log'
        new_images = self.root / 'new-images'
        manager._snapshot = {'values': {
            'settings': {'logpath': str(new_log), 'autosave': True},
            'spot': {'image_capture': {'enabled': True, 'mode': 'all',
                                      'path': str(new_images), 'retention_days': 0,
                                      'min_interval_sec': 0, 'link_to_observation': False}},
        }}
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        normalize = settings._normalize_spot_image_capture_mode
        results = []

        def delayed_mode(*args):
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test config release missing')
            return normalize(*args)

        self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        with patch.dict(spot.config.__dict__, spot.config.__dict__.copy()), \
             patch.object(settings.logger_service, 'apply_config'), \
             patch.object(settings, '_normalize_spot_image_capture_mode', delayed_mode):
            apply_thread = threading.Thread(target=lambda: results.append(manager.apply_changes({
                'settings.logpath': {}, 'spot.image_capture.path': {},
            })))
            self.controllers.append(apply_thread)
            apply_thread.start()
            try:
                self.assertTrue(entered.wait(3))
                # Configuration preparation must not block live capture admission.
                self.enqueue()
                self.assertTrue(spot.flush_spot_image_capture_queue(3))
                self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 2)
                self.assertEqual(len(list((new_log / 'images').rglob('*.jpg'))), 0)
            finally:
                release.set()
                apply_thread.join(3)
            self.assertFalse(apply_thread.is_alive())
            self.assertEqual(results[0]['pending'], [])
            self.enqueue()
            self.assertTrue(spot.flush_spot_image_capture_queue(3))
            self.assertEqual(len(list(new_images.rglob('*.jpg'))), 1)
            for log_path, count in [(self.root, 2), (new_log, 1)]:
                with (log_path / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
                    self.assertEqual(len(list(csv.DictReader(handle))), count)
            self.assertEqual(spot.get_spot_image_capture_shutdown_status()['written_count'], 3)

    def test_image_pressure_uses_original_pending_stage(self):
        clock = [100.0]
        with patch.object(spot.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(spot.time, 'time', return_value=1790640000.):
            spot._activate_spot_image_storage()
            deadline = time.perf_counter() + 3
            while time.perf_counter() < deadline:
                samples = spot.get_spot_image_storage_pressure_samples()
                if len(samples) == 2 and all(sample.availability == 'available' for sample in samples):
                    break
                time.sleep(.01)
            else:
                self.fail('image destinations were not initialized')
            entered, release = self.block_write()
            self.assertTrue(self.enqueue().accepted)
            self.assertTrue(entered.wait(3))
            clock[0] = 103.25
            with patch.object(Path, 'open', side_effect=AssertionError('pressure reader opened a file')), \
                 patch.object(Path, 'stat', side_effect=AssertionError('pressure reader statted a file')):
                samples = spot.get_spot_image_storage_pressure_samples()
            decision = StoragePressureController().evaluate(samples, now_monotonic=clock[0])
            self.assertEqual(decision.state, 'PRESSURED')
            self.assertEqual(decision.oldest_pending_age_seconds, 3.25)
            self.assertEqual(decision.max_stage_overdue_seconds, 3.25)
            self.assertEqual({sample.sink_id for sample in samples}, {'image_fact', 'image_jpeg'})
            pending = spot.get_spot_image_capture_shutdown_status()
            self.assertEqual(decision.max_occupancy_ratio,
                             max(1 / 128, pending['pending_payload_bytes'] / (128 * 1024**2)))
            original_bindings = {(s.config_generation, s.destination_key) for s in samples}
            with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MODE', 'off'):
                spot._activate_spot_image_storage()
                retained = spot.get_spot_image_storage_pressure_samples()
                self.assertEqual({(s.config_generation, s.destination_key) for s in retained}, original_bindings)
                self.assertTrue(all(not s.enabled and s.pending_count == 1 for s in retained))
                self.assertEqual(StoragePressureController().evaluate(retained, now_monotonic=clock[0]).state,
                                 'PRESSURED')
                release.set()
                self.assertTrue(spot.flush_spot_image_capture_queue(3))
                complete = spot.get_spot_image_storage_pressure_samples()
                self.assertTrue(all(s.pending_count == 0 and s.pending_bytes == 0 for s in complete))
                self.assertEqual(StoragePressureController().evaluate(complete, now_monotonic=clock[0]).state,
                                 'NORMAL')

    def test_pending_images_keep_admitted_destinations_after_config_change(self):
        clock = [1000.0]
        entered, release = self.block_write()
        new_root = self.root / 'next-generation'
        def key(path):
            return hashlib.sha256(os.fsencode(os.path.normcase(os.path.abspath(path)))).hexdigest()
        with patch.object(spot.time, 'monotonic', side_effect=lambda: clock[0]):
            self.assertTrue(self.enqueue().accepted)
            self.assertTrue(entered.wait(3))
            clock[0] = 1005.0
            with patch.object(spot.config, 'LOG_PATH', str(new_root)):
                self.assertTrue(self.enqueue().accepted)
                pending = spot.get_spot_image_capture_shutdown_status()
                destinations = pending.get('pending_destinations', [])
                self.assertEqual(len(destinations), 4)
                by_key = {item['destination_key']: item for item in destinations}
                old_fact = by_key[key(self.root / 'spot_image_fact.csv')]
                new_fact = by_key[key(new_root / 'spot_image_fact.csv')]
                self.assertIsInstance(old_fact['config_generation'], int)
                self.assertGreater(new_fact['config_generation'], old_fact['config_generation'])
                self.assertEqual(old_fact['oldest_pending_monotonic'], 1000.0)
                self.assertEqual(new_fact['oldest_pending_monotonic'], 1005.0)
                self.assertEqual(old_fact['pending_count'], 1)
                self.assertEqual(new_fact['pending_count'], 1)
                for root, fact in ((self.root, old_fact), (new_root, new_fact)):
                    jpeg = by_key[key(root / 'images' / '2026' / '09' / '29')]
                    self.assertEqual(jpeg['config_generation'], fact['config_generation'])
                    self.assertEqual(jpeg['stage_due_monotonic'], fact['oldest_pending_monotonic'])
                    self.assertGreater(jpeg['pending_bytes'], 0)
                with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MODE', 'off'):
                    spot._activate_spot_image_storage()
                    self.assertEqual(spot.get_spot_image_capture_shutdown_status()['pending_destinations'], destinations)
                    release.set()
                    self.assertTrue(spot.flush_spot_image_capture_queue(3))
            final = spot.get_spot_image_capture_shutdown_status()
            self.assertEqual(final['pending_destinations'], [])
            self.assertEqual(final['pending_payload_bytes'], 0)
        for root in (self.root, new_root):
            self.assertEqual(len(list((root / 'images').rglob('*.jpg'))), 1)
            with (root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)

    def test_idle_image_probe_keeps_workspace_binding_after_disable(self):
        clock, pause = [100.0], [False]
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        replace_file = os.replace

        def stalled(source, target):
            if (pause[0] and Path(source).name.startswith('.sfl-storage-probe-')
                    and Path(source).parent.is_relative_to(self.root / 'images')):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('probe release missing')
            return replace_file(source, target)

        with patch.object(spot.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(spot.time, 'time', return_value=1790640000.), \
                patch.object(os, 'replace', stalled):
            spot._activate_spot_image_storage()
            deadline = time.perf_counter() + 3
            while time.perf_counter() < deadline:
                samples = spot.get_spot_image_storage_pressure_samples()
                if len(samples) == 2 and all(s.availability == 'available' for s in samples):
                    break
                time.sleep(.01)
            else:
                self.fail('initial destination checks did not complete')
            generation = samples[0].config_generation
            jpeg_key = next(s.destination_key for s in samples if s.sink_id == 'image_jpeg')
            pause[0] = True
            clock[0] = 101.0
            self.assertTrue(entered.wait(3))
            with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MODE', 'off'):
                spot._activate_spot_image_storage()
                clock[0] = 104.25
                with patch.object(Path, 'open', side_effect=AssertionError('state reader did file I/O')):
                    samples = spot.get_spot_image_storage_pressure_samples()
                pending = [s for s in samples if s.has_pending]
                self.assertEqual([s.sink_id for s in pending], ['image_jpeg'])
                sample, = pending
                self.assertEqual((sample.config_generation, sample.destination_key), (generation, jpeg_key))
                self.assertEqual((sample.pending_count, sample.pending_bytes), (0, 128))
                self.assertEqual((sample.oldest_pending_monotonic, sample.stage_due_monotonic), (101., 101.))
                self.assertFalse(sample.enabled)
                decision = StoragePressureController().evaluate(samples, now_monotonic=clock[0])
                self.assertEqual(decision.state, 'PRESSURED')
                self.assertEqual(decision.max_stage_overdue_seconds, 3.25)
                release.set()
                self.assertTrue(spot.stop_spot_image_capture_writer(3))
                complete = spot.get_spot_image_storage_pressure_samples()
                self.assertTrue(all(not s.has_pending for s in complete))
                self.assertEqual(spot.get_spot_image_capture_shutdown_status()['pending_payload_bytes'], 0)
                self.assertEqual(StoragePressureController().evaluate(complete, now_monotonic=clock[0]).state, 'NORMAL')
        self.assertEqual(list(self.root.rglob('.sfl-storage-probe-*')), [])
        self.assertEqual(spot.get_spot_image_capture_shutdown_status()['enqueued_count'], 0)

    def test_transient_fact_open_failure_retries_owned_capture(self):
        image = io.BytesIO()
        Image.new('RGB', (2, 2), (3, 4, 5)).save(image, format='JPEG')
        base = image.getvalue()
        padding = bytearray()
        remaining = 1_500_000 - len(base)
        while remaining:
            size = min(remaining, 65537)
            if 0 < remaining - size < 4:
                size -= 4 - (remaining - size)
            padding.extend(b'\xff\xfe' + (size - 2).to_bytes(2, 'big') + b'x' * (size - 4))
            remaining -= size
        jpeg = base[:2] + bytes(padding) + base[2:]
        with Image.open(io.BytesIO(jpeg)) as decoded:
            decoded.verify()
        opened = Path.open
        failures = []

        def fail_once(path, mode='r', *args, **kwargs):
            if path == self.root / 'spot_image_fact.csv' and mode == 'ab' and not failures:
                failures.append(time.monotonic())
                raise PermissionError(13, 'transient fact open failure')
            return opened(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', new=fail_once):
            receipt = spot._maybe_enqueue_spot_image_capture(
                image_bytes=jpeg, captured_at=1790640001.,
                image_url='http://synthetic.invalid/image.jpg', source='test', image_age_ms=7,
                capture_id='spotimg_20260929T000001000000Z_' + 'b' * 32,
            )
            self.assertTrue(receipt.accepted)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                pending = spot.get_spot_image_capture_shutdown_status()
                if pending.get('retry_error_count') or pending['failure_count']:
                    break
                time.sleep(.01)
            self.assertEqual(pending['unfinished_tasks'], 1, 'failed capture must remain owned for recovery')
            self.assertEqual(pending['pending_payload_bytes'], len(jpeg))
            self.assertEqual(pending['pending_recovery'], 1)
            self.assertEqual(pending['retry_error_count'], 1)
            self.assertEqual(pending['failure_count'], 0)
            self.assertTrue(pending['accounting_consistent'])
            image_path, = self.root.rglob('*.jpg')
            sentinel = 1700000000123456000
            os.utime(image_path, ns=(sentinel, sentinel))
            new_root = self.root / 'new-destination'
            with patch.object(spot.config, 'LOG_PATH', str(new_root)), \
                 patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MAX_BYTES', 1024):
                self.assertTrue(spot.flush_spot_image_capture_queue(4))
            self.assertFalse(new_root.exists())
        self.assertEqual(image_path.read_bytes(), jpeg)
        self.assertEqual(image_path.stat().st_mtime_ns, sentinel)
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['spot_image_capture_id'], receipt.capture_id)
        self.assertEqual(rows[0]['spot_image_sha256'], hashlib.sha256(jpeg).hexdigest())
        self.assertEqual(rows[0]['spot_image_age_ms'], '7.000')
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 1)
        self.assertEqual(final['pending_recovery'], 0)
        self.assertEqual(final['retry_error_count'], 1)
        self.assertEqual(final['recovered_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertTrue(final['accounting_consistent'])

    def test_image_retry_backoff_and_shutdown_preserve_pending(self):
        clock = [1000.0]
        real_monotonic = time.monotonic
        should_fail = [True]
        attempts = []

        def write(path, data):
            if path.is_relative_to(self.root / 'images') and should_fail[0]:
                attempts.append(clock[0])
                raise PermissionError(13, 'temporary JPEG write failure')
            return self.write_bytes(path, data)

        def await_retry(count):
            deadline = real_monotonic() + 3
            while real_monotonic() < deadline:
                state = spot.get_spot_image_capture_shutdown_status()
                if state['retry_error_count'] == count:
                    return state
                time.sleep(.01)
            self.fail(f'retry count {count} was not observed')

        with patch.object(Path, 'write_bytes', new=write), \
             patch.object(spot.time, 'monotonic', side_effect=lambda: clock[0]):
            empty = spot.get_spot_image_capture_shutdown_status()
            self.assertIsNone(empty.get('oldest_pending_monotonic'))
            self.assertTrue(self.enqueue().accepted)
            for number, delay in enumerate((1., 2., 4., 8., 16., 30., 30.), 1):
                pending = await_retry(number)
                self.assertEqual(pending['next_retry_at_monotonic'], clock[0] + delay)
                self.assertEqual(pending['pending_recovery'], 1)
                self.assertEqual(pending['unfinished_tasks'], 1)
                self.assertEqual(pending['queue_size'], 0)
                self.assertGreater(pending['pending_payload_bytes'], 0)
                self.assertTrue(pending['accounting_consistent'])
                self.assertEqual(pending.get('oldest_pending_monotonic'), 1000.0)
                self.assertEqual(pending.get('stage_due_monotonic'), 1000.0)
                self.assertFalse(pending.get('pending_clock_unknown', True))
                due = pending['next_retry_at_monotonic']
                clock[0] = due - .25
                time.sleep(.03)
                self.assertEqual(len(attempts), number)
                if number == 7:
                    should_fail[0] = False
                clock[0] = due
            self.assertTrue(spot.flush_spot_image_capture_queue(3))
            complete = spot.get_spot_image_capture_shutdown_status()
            self.assertEqual(complete['written_count'], 1)
            self.assertEqual(complete['recovered_count'], 1)
            self.assertEqual(complete['retry_error_count'], 7)
            self.assertEqual(complete['pending_payload_bytes'], 0)
            self.assertIsNone(complete.get('oldest_pending_monotonic'))
            with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)

            should_fail[0] = True
            self.assertTrue(self.enqueue().accepted)
            pending = await_retry(8)
            self.assertEqual(pending['next_retry_at_monotonic'], clock[0] + 1.)
            self.assertEqual(pending.get('oldest_pending_monotonic'), clock[0])
            before = spot.begin_spot_image_capture_shutdown()
            clock[0] += 100
            self.assertFalse(spot.stop_spot_image_capture_for_shutdown(3))
            final = spot.get_spot_image_capture_shutdown_status()
            self.assertEqual(len(attempts), 8, 'shutdown must not schedule a new retry')
            self.assertFalse(final['worker_alive'])
            self.assertFalse(final['writes_drained'])
            self.assertTrue(final['integrity_unresolved'])
            self.assertTrue(final['accounting_consistent'])
            self.assertEqual(final['historical_retry_errors'], 8)
            self.assertEqual(final['pending_recovery'], 1)
            self.assertEqual(final['unfinished_tasks'], 1)
            self.assertEqual(final['pending_payload_bytes'], before['pending_payload_bytes'])
            self.assertEqual(final['failure_count'], 0)
            self.assertEqual(final.get('oldest_pending_monotonic'), before['oldest_pending_monotonic'])

    def test_partial_fact_failure_never_retries_after_config_change(self):
        opened = Path.open
        attempts = []

        class PartialAppend:
            def __init__(self, handle):
                self.handle = handle

            def fileno(self):
                return self.handle.fileno()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return self.handle.__exit__(*exc)

            def write(self, data):
                attempts.append(len(data))
                self.handle.write(data[:37])
                self.handle.flush()
                raise OSError('partial image fact write')

        def fail_append(path, mode='r', *args, **kwargs):
            handle = opened(path, mode, *args, **kwargs)
            return PartialAppend(handle) if path == self.root / 'spot_image_fact.csv' and mode == 'ab' else handle

        with patch.object(Path, 'open', new=fail_append):
            self.assertTrue(self.enqueue().accepted)
            self.assertTrue(spot.flush_spot_image_capture_queue(3))
            originals = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
            with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_PATH', 'replacement-images'):
                self.assertTrue(self.enqueue().accepted)
                self.assertTrue(spot.flush_spot_image_capture_queue(3))
        self.assertEqual(len(attempts), 1)
        self.assertEqual({path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}, originals)
        state = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(state['failure_count'], 2)
        self.assertEqual(state['retry_error_count'], 0)
        self.assertEqual(state['pending_recovery'], 0)
        self.assertEqual(state['pending_payload_bytes'], 0)
        self.assertTrue(state['accounting_consistent'])

    def test_existing_capture_verification_reserves_worker_payload(self):
        data = io.BytesIO()
        Image.new('RGB', (2, 2), (3, 4, 5)).save(data, format='JPEG')
        base = data.getvalue()
        jpeg = base[:2] + b'\xff\xfe\x20\x02' + b'x' * 8192 + base[2:]
        args = dict(image_bytes=jpeg, captured_at=1790640001.,
                    image_url='http://synthetic.invalid/image.jpg', source='test', image_age_ms=0,
                    capture_id='spotimg_20260929T000001000000Z_' + 'a' * 32)
        self.assertTrue(spot._maybe_enqueue_spot_image_capture(**args).accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        image_path, = self.root.rglob('*.jpg')
        original = {path: path.read_bytes() for path in (image_path, self.root / 'spot_image_fact.csv')}
        opened = Path.open
        reads = []

        class Reader:
            def __init__(self, handle):
                self.handle = handle

            def __getattr__(self, name):
                return getattr(self.handle, name)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return self.handle.__exit__(*exc)

            def readinto(self, buffer):
                reads.append((len(buffer), spot.get_spot_image_capture_shutdown_status()['pending_payload_bytes']))
                return self.handle.readinto(buffer)

        def observe_reads(path, mode='r', *open_args, **kwargs):
            handle = opened(path, mode, *open_args, **kwargs)
            return Reader(handle) if path == image_path and mode == 'rb' else handle

        with patch.object(Path, 'open', new=observe_reads):
            with patch.object(spot, '_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT', len(jpeg) + 4095):
                self.assertTrue(spot._maybe_enqueue_spot_image_capture(**args).accepted)
                self.assertTrue(spot.flush_spot_image_capture_queue(3))
                state = spot.get_spot_image_capture_shutdown_status()
                self.assertEqual(state['failure_count'], 1,
                                 'existing JPEG verification must reserve its read buffer before reading')
                self.assertEqual(state['pending_payload_bytes'], 0)
                self.assertEqual(reads, [])
            with patch.object(spot, '_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT', len(jpeg) + 4096):
                self.assertTrue(spot._maybe_enqueue_spot_image_capture(**args).accepted)
                self.assertTrue(spot.flush_spot_image_capture_queue(3))
        self.assertTrue(reads)
        self.assertTrue(all(0 < size <= 4096 and pending == len(jpeg) + 4096 for size, pending in reads))
        self.assertEqual(spot.get_spot_image_capture_shutdown_status()['pending_payload_bytes'], 0)
        self.assertEqual(spot.get_spot_image_capture_shutdown_status()['failure_count'], 1)
        self.assertEqual({path: path.read_bytes() for path in original}, original)

    def test_capture_payload_budget_includes_inflight_and_linked_snapshot(self):
        # Two retained captures (~4.5 MiB), the writer's decoded snapshot and
        # admission workspace fit; a third capture must still be refused.
        limit = 7 * 1024**2
        self.stack.enter_context(patch.object(spot, '_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT', limit))
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION', True))
        self.stack.enter_context(patch.object(spot, '_spot_temperature_snapshot', None))
        entered, release = self.block_write()
        accepted_hashes = []
        payload_sizes = []

        def capture(number):
            data = io.BytesIO()
            Image.new('RGB', (2, 2), (number, 2, 3)).save(data, format='JPEG')
            jpeg = data.getvalue()
            # Valid JPEG comment segments make a permitted >1 MiB capture.
            comment = b'\xff\xfe\xff\xff' + bytes([65 + number]) * 65533
            image = jpeg[:2] + comment * 24 + jpeg[2:]
            snapshot = {'spot_service_instance_id': 'budget-fixture', 'spot_poll_seq': number,
                        'spot_last_poll_completed_at': f'2026-09-29T00:00:0{number}Z',
                        'diagnostic_text': 'x' * (768 * 1024)}
            spot._spot_temperature_snapshot = snapshot
            snapshot_bytes = json.dumps(snapshot, ensure_ascii=False, allow_nan=False,
                                        separators=(',', ':'), sort_keys=True).encode('utf-8')
            payload_sizes.append(len(image) + len(snapshot_bytes))
            spot._maybe_enqueue_spot_image_capture(
                image_bytes=image, captured_at=1790640000. + number,
                image_url='http://synthetic.invalid/image.jpg', source='test', image_age_ms=0,
            )
            if number != 3:
                accepted_hashes.append(hashlib.sha256(image).hexdigest())

        capture(1)
        self.assertTrue(entered.wait(3))
        capture(2)
        capture(3)
        pending = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(pending['enqueued_count'], 2)
        self.assertEqual(pending['unfinished_tasks'], 2)
        self.assertGreaterEqual(pending['pending_payload_bytes'], sum(payload_sizes[:2]) + 768 * 1024)
        self.assertLessEqual(pending['pending_payload_bytes'], limit)
        self.assertEqual(pending['dropped_payload_limit_count'], 1)
        self.assertEqual(pending['dropped_oversize_count'], 0)
        release.set()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        self.assertEqual(spot.get_spot_image_capture_health()['pending_payload_bytes'], 0)
        capture(4)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertEqual(final['written_count'], 3)
        self.assertTrue(final['accounting_consistent'])
        files = list((self.root / 'images').rglob('*.jpg'))
        self.assertEqual(sorted(hashlib.sha256(path.read_bytes()).hexdigest() for path in files),
                         sorted(accepted_hashes))
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row['spot_image_linked_observation_key'] for row in rows],
                         ['budget-fixture:1', 'budget-fixture:2', 'budget-fixture:4'])

    def test_image_decode_budget_failure_preserves_capture_identity(self):
        self.stack.enter_context(patch.object(spot, '_SPOT_IMAGE_CAPTURE_PAYLOAD_BYTE_LIMIT', 5 * 1024**2))
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION', True))
        snapshot = {'spot_service_instance_id': 'decode-limit', 'spot_poll_seq': 1,
                    'spot_last_poll_completed_at': '2026-09-29T00:00:01Z',
                    'diagnostic_text': 'x' * (2 * 1024**2)}
        data = io.BytesIO()
        Image.new('RGB', (2, 2), (4, 5, 6)).save(data, format='JPEG')
        jpeg = data.getvalue()
        with patch.object(spot, '_spot_temperature_snapshot', snapshot), self.assertLogs('spot_control', 'WARNING') as logs:
            receipt = spot._maybe_enqueue_spot_image_capture(
                image_bytes=jpeg, captured_at=1790640001., image_url='http://synthetic.invalid/image.jpg',
                source='test', capture_id='original-decode-limit-capture',
            )
            self.assertTrue(receipt.accepted)
            self.assertTrue(spot.flush_spot_image_capture_queue(3))
            self.assertTrue(spot.stop_spot_image_capture_writer(3))
        failures = [json.loads(record.getMessage().split('SPOT image capture writer failed ', 1)[1])
                    for record in logs.records if record.getMessage().startswith('SPOT image capture writer failed ')]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['capture_id'], receipt.capture_id)
        self.assertEqual(failures[0]['image_sha256'], hashlib.sha256(jpeg).hexdigest())
        self.assertEqual(failures[0]['reason'], 'snapshot_decode_byte_limit')
        failed = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(failed['failure_count'], 1)
        self.assertEqual(failed['pending_payload_bytes'], 0)
        self.assertFalse(failed['writes_drained'])
        self.assertFalse(list((self.root / 'images').rglob('*.jpg')))
        snapshot['diagnostic_text'] = 'normal'
        snapshot['spot_poll_seq'] = 2
        with patch.object(spot, '_spot_temperature_snapshot', snapshot):
            self.assertTrue(self.enqueue().accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 1)
        self.assertEqual(final['failure_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertFalse(final['writes_drained'])
        self.assertTrue(final['accounting_consistent'])
        self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 1)

    def test_image_snapshot_decode_remains_in_pending_budget(self):
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION', True))
        clock = [100.0]
        self.stack.enter_context(patch.object(spot.time, 'monotonic', side_effect=lambda: clock[0]))
        self.stack.enter_context(patch.object(spot.time, 'time', return_value=1790640000.))
        spot._activate_spot_image_storage()
        deadline = time.perf_counter() + 3
        while time.perf_counter() < deadline:
            samples = spot.get_spot_image_storage_pressure_samples()
            if len(samples) == 2 and all(s.availability == 'available' for s in samples):
                break
            time.sleep(.01)
        else:
            self.fail('image destinations were not initialized')
        snapshot = {'spot_service_instance_id': 'decode-fixture', 'spot_poll_seq': 1,
                    'spot_last_poll_completed_at': '2026-09-29T00:00:01Z',
                    'diagnostic_text': 'x' * (2 * 1024**2)}
        entered, release = self.block_write()
        with patch.object(spot, '_spot_temperature_snapshot', snapshot):
            tracemalloc.start()
            try:
                self.assertTrue(self.enqueue().accepted)
                self.assertTrue(entered.wait(3))
                allocated, _ = tracemalloc.get_traced_memory()
                pending = spot.get_spot_image_capture_shutdown_status()['pending_payload_bytes']
                clock[0] = 103.25
                samples = spot.get_spot_image_storage_pressure_samples()
                self.assertNotIn('image_pending_unbound', {s.sink_id for s in samples},
                                 'decoded snapshot reservation lost its admitted destination')
                decision = StoragePressureController().evaluate(samples, now_monotonic=clock[0])
                self.assertEqual(decision.state, 'PRESSURED')
                self.assertEqual(decision.max_stage_overdue_seconds, 3.25)
                self.assertEqual(decision.max_occupancy_ratio, max(1 / 128, pending / (128 * 1024**2)))
                bindings = {(s.config_generation, s.destination_key) for s in samples}
                with patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_MODE', 'off'):
                    spot._activate_spot_image_storage()
                    retained = spot.get_spot_image_storage_pressure_samples()
                    self.assertEqual({(s.config_generation, s.destination_key) for s in retained}, bindings)
                    self.assertTrue(all(not s.enabled for s in retained))
            finally:
                tracemalloc.stop()
                release.set()
        self.assertLessEqual(allocated, pending + 1024**2,
                             'decoded image snapshot is outside the pending budget')
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertTrue(final['accounting_consistent'])
        self.assertTrue(all(s.pending_bytes == 0 for s in spot.get_spot_image_storage_pressure_samples()))
        self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 1)
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row['spot_image_linked_observation_key'] for row in rows], ['decode-fixture:1'])

    def test_oversized_image_snapshot_is_rejected_before_serialization(self):
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION', True))
        snapshot = {'spot_service_instance_id': 'preflight-fixture', 'spot_poll_seq': 1,
                    'spot_last_poll_completed_at': '2026-09-29T00:00:01Z',
                    'diagnostic_text': 'x' * (128 * 1024**2)}
        with patch.object(spot, '_spot_temperature_snapshot', snapshot):
            tracemalloc.start()
            try:
                receipt = self.enqueue()
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        self.assertEqual((receipt.status, receipt.reason), ('REJECTED_LIMIT', 'pending_byte_limit'))
        self.assertLessEqual(peak, 2 * 1024**2,
                             'oversized image snapshot was serialized before budget rejection')
        rejected = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(rejected['pending_payload_bytes'], 0)
        self.assertEqual(rejected['enqueued_count'], 0)
        self.assertEqual(rejected['dropped_payload_limit_count'], 1)
        snapshot['diagnostic_text'] = 'normal'
        snapshot['spot_poll_seq'] = 2
        with patch.object(spot, '_spot_temperature_snapshot', snapshot):
            self.assertTrue(self.enqueue().accepted)
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertEqual(final['dropped_payload_limit_count'], 1)
        self.assertTrue(final['accounting_consistent'])
        self.assertEqual(len(list((self.root / 'images').rglob('*.jpg'))), 1)
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row['spot_image_linked_observation_key'] for row in rows], ['preflight-fixture:2'])

    def test_invalid_link_snapshot_rejects_capture_and_next_capture_succeeds(self):
        self.stack.enter_context(patch.object(spot.config, 'SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION', True))
        invalid = {'spot_service_instance_id': 'invalid-fixture', 'spot_poll_seq': 1,
                   'spot_last_poll_completed_at': '2026-09-29T00:00:01Z', 'signalpc': float('nan')}
        with patch.object(spot, '_spot_temperature_snapshot', invalid):
            self.enqueue()
        rejected = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(rejected['enqueued_count'], 0)
        self.assertEqual(rejected['pending_payload_bytes'], 0)
        self.assertEqual(rejected['unfinished_tasks'], 0)
        self.assertEqual(rejected['dropped_count'], 1)
        self.assertEqual(rejected['dropped_invalid_count'], 1)
        self.assertEqual(spot.get_spot_image_capture_health()['last_error_code'],
                         'snapshot_serialization_failed')
        valid = dict(invalid, spot_poll_seq=2, signalpc=80.0)
        with patch.object(spot, '_spot_temperature_snapshot', valid):
            self.enqueue()
        self.assertTrue(spot.flush_spot_image_capture_queue(3))
        final = spot.get_spot_image_capture_shutdown_status()
        self.assertEqual(final['written_count'], 1)
        self.assertEqual(final['pending_payload_bytes'], 0)
        self.assertEqual(final['dropped_invalid_count'], 1)
        self.assertEqual(final['failure_count'], 0)
        self.assertTrue(final['accounting_consistent'])
        with (self.root / 'spot_image_fact.csv').open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row['spot_image_linked_observation_key'] for row in rows], ['invalid-fixture:2'])

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

    def test_final_system_log_is_flushed_before_real_process_exit(self):
        # Real app coroutine, logging queue/file handler and os._exit. Only the
        # file stream boundary is controlled: it needs the event loop to yield
        # before releasing the final write, making the former race repeatable.
        script = textwrap.dedent('''
            import asyncio, json, os, threading
            from pathlib import Path
            from backend import app

            async def run():
                loop = asyncio.get_running_loop()
                final_release = threading.Event()
                handler = next(h for listener in app._log_queue_listeners
                    for h in listener.handlers
                    if isinstance(h, app.SafeRotatingFileHandler)
                    and Path(h.baseFilename).name == 'system.log')
                original = handler.stream
                class Stream:
                    def __getattr__(self, name):
                        return getattr(original, name)
                    def write(self, value):
                        if 'Control shutdown complete' in value:
                            loop.call_soon_threadsafe(final_release.set)
                            if not final_release.wait(3):
                                raise OSError('final log never released')
                        return original.write(value)
                handler.stream = Stream()
                Path(os.environ['FINAL_LOG_IDENTITY']).write_text(json.dumps({
                    'pid': os.getpid(), 'session': app._app_session_id,
                    'log': handler.baseFilename,
                }), encoding='utf-8')
                await app._run_control_shutdown('real-final-log-regression')
            asyncio.run(run())
        ''')
        identity = self.root / 'child-identity.json'
        child_env = os.environ.copy()
        child_env.update(APPDATA=str(self.root/'child-appdata'),
                         LOCALAPPDATA=str(self.root/'child-localappdata'),
                         PYTHON_DOTENV_DISABLED='1', V2_MODE='MOCK',
                         FINAL_LOG_IDENTITY=str(identity))
        completed = subprocess.run(
            [sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[2],
            env=child_env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        owner = json.loads(identity.read_text(encoding='utf-8'))
        records = [json.loads(line) for line in Path(owner['log']).read_text(encoding='utf-8').splitlines()
                   if 'Control shutdown complete' in line]
        final = [row for row in records if 'Control shutdown complete' in row['message']
                 and f"pid={owner['pid']} " in row['message']
                 and f"session={owner['session']} " in row['message']]
        self.assertEqual(len(final), 1, 'Actual process exit lost the final system.log record')
        self.assertIn('success=True exit_code=0', final[0]['message'])

    def final_log_sink(self, *, block=False, error=None):
        """Use the production handler with only its external stream controlled."""
        path = self.root / f'final-{time.monotonic_ns()}.log'
        handler = app.SafeRotatingFileHandler(path, encoding='utf-8')
        handler.setFormatter(app.CustomJsonFormatter('%(message)s'))
        original = handler.stream
        entered, release = threading.Event(), threading.Event()
        self.releases.append(release)
        state = {'fault': error, 'final_write': False, 'entered_at': None}
        class Stream:
            def __getattr__(self, name):
                return getattr(original, name)
            def write(self, value):
                state['final_write'] = 'Control shutdown complete' in value
                if state['final_write']:
                    if not entered.is_set():
                        state['entered_at'] = time.monotonic()
                        entered.set()
                    if block and not release.wait(5):
                        raise OSError('test final log release missing')
                    if state['fault'] == 'write':
                        raise OSError('synthetic final write failure')
                return original.write(value)
            def flush(self):
                if state['final_write'] and state['fault'] == 'flush':
                    raise OSError('synthetic final flush failure')
                return original.flush()
        handler.stream = Stream()
        log_queue = queue.Queue()
        logger = logging.Logger('isolated-shutdown')
        logger.addHandler(logging.handlers.QueueHandler(log_queue))
        listener = logging.handlers.QueueListener(log_queue, handler)
        listener.start()
        self.stack.enter_context(patch.object(app, '_logger', logger))
        def cleanup():
            release.set()
            state['fault'] = None
            listener.enqueue_sentinel()
            listener._thread.join(3)
            self.assertFalse(listener._thread.is_alive(), 'log listener leaked')
            handler.close()
        self.addCleanup(cleanup)
        return path, entered, release, log_queue, state

    def test_final_log_inflight_is_not_a_drained_empty_queue(self):
        path, entered, release, log_queue, _ = self.final_log_sink(block=True)
        async def run():
            task = asyncio.create_task(app._run_control_shutdown('log-inflight'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                self.assertTrue(log_queue.empty())
                self.assertFalse(task.done())
                exit_process.assert_not_called()
            finally:
                release.set()
                await task
        with patch.object(app.os, '_exit') as exit_process:
            self.loop.run_until_complete(run())
        exit_process.assert_called_once_with(0)
        final = [json.loads(line) for line in path.read_text().splitlines()
                 if 'Control shutdown complete' in line]
        self.assertEqual(len(final), 1)
        self.assertNotIn('_shutdown_log_ack', final[0])

    def test_final_log_stall_is_bounded_and_late_ack_cannot_reverse_exit(self):
        _, entered, release, _, state = self.final_log_sink(block=True)
        try:
            self.assertEqual(self.run_control(), 2)
            elapsed = time.monotonic() - state['entered_at']
            self.assertTrue(entered.is_set())
            self.assertFalse(release.is_set())
            self.assertLess(elapsed, 0.6, 'Final log wait exceeded the shared 0.2s budget')
            self.assertTrue(app._get_shutdown_evidence_status()['control']['receipt_verified'])
        finally:
            release.set()

    def test_final_log_write_and_flush_errors_cannot_acknowledge_success(self):
        for boundary in ('write', 'flush'):
            with self.subTest(boundary=boundary):
                self.final_log_sink(error=boundary)
                with patch.object(sys, 'stderr', io.StringIO()):
                    self.assertEqual(self.run_control(), 2)
                self.assertTrue(app._get_shutdown_evidence_status()['control']['receipt_verified'])

    def test_cancel_final_log_wait_preserves_failure_exit(self):
        _, entered, release, _, _ = self.final_log_sink(block=True)
        async def run():
            task = asyncio.create_task(app._run_control_shutdown('cancel-final-log'))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                task.cancel()
                await task
                exit_process.assert_called_once_with(2)
            finally:
                release.set()
                if not task.done():
                    await task
        with patch.object(app.os, '_exit') as exit_process:
            self.loop.run_until_complete(run())

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
                    # Fail receipt I/O only. Mutating the shared os module also
                    # faults the real CSV producer trace, a different scenario.
                    receipt_os = stack.enter_context(patch.object(evidence, 'os', wraps=os))
                    receipt_os.fsync.side_effect = OSError('receipt failure')
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
                    trace_state = logger.get_runtime_state()['persistence_trace']
                    self.assertEqual(trace_state['failure_count'], 0)
                    self.assertEqual(trace_state['pending_records'], 0)
                    self.assertTrue(list((self.root / '.sfl_trace' / logger.logger_service_instance_id).glob('*.trace.jsonl')))

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
        self.run_overlapping_cleanup()

    def test_control_waits_for_pending_peer_final_receipt(self):
        # This checks peer ordering, not native filesystem latency. Real receipt
        # I/O must not spend the deadline while the test intentionally holds a
        # peer. Timeout behaviour is covered by the explicit stall tests.
        with patch.object(app, 'time', wraps=time) as clock:
            clock.monotonic.return_value = time.monotonic()
            self.run_overlapping_cleanup(hold_peer_final=True)

    async def wait_control_receipt(self, *, timeout_sec=3):
        async with asyncio.timeout(timeout_sec):
            while True:
                state = app._get_shutdown_evidence_status().get('control', {})
                if state.get('receipt_verified') and not state['writer_alive']:
                    return
                await asyncio.sleep(.001)

    async def peer_between_receipt_phases(self):
        peer = await app._begin_shutdown_evidence('lifespan')
        await asyncio.to_thread(peer._io_thread.join, 3)
        self.assertFalse(peer.status()['writer_alive'])
        self.assertTrue(peer.status()['before_verified'])
        self.assertFalse(peer.status()['receipt_verified'])
        self.assertIsNone(peer.status()['error_phase'])
        return peer

    def test_cancel_pending_peer_wait_cannot_exit_successfully(self):
        async def run():
            await self.peer_between_receipt_phases()
            task = asyncio.create_task(app._run_control_shutdown('cancel-peer-wait'))
            try:
                await self.wait_control_receipt()
                await asyncio.sleep(.03)
                exit_process.assert_not_called()
                self.assertFalse(app._all_shutdown_evidence_verified())
                task.cancel()
                await task
                exit_process.assert_called_once_with(2)
            finally:
                if not task.done():
                    task.cancel()
                    await task
        # Reach the pending-peer state even if real receipt I/O is slow; this
        # test's cancellation must be the reason that successful exit is denied.
        with patch.object(app, 'time', wraps=time) as clock, \
             patch.object(app.os, '_exit') as exit_process:
            clock.monotonic.return_value = time.monotonic()
            self.loop.run_until_complete(run())

    def test_peer_and_log_wait_share_one_final_deadline(self):
        _, log_entered, log_release, _, _ = self.final_log_sink(block=True)
        tick = time.monotonic()
        async def run():
            nonlocal tick
            peer = await self.peer_between_receipt_phases()
            task = asyncio.create_task(app._run_control_shutdown('shared-final-budget'))
            try:
                await self.wait_control_receipt()
                await asyncio.sleep(.03)
                exit_process.assert_not_called()
                # Spend part of the existing budget with the peer still pending.
                tick += .1
                self.assertTrue(peer.start_finish(
                    image=spot.get_spot_image_capture_shutdown_status(), stages={}, stage_exit_code=0,
                ))
                self.assertTrue(await asyncio.to_thread(log_entered.wait, 3))
                self.assertTrue(app._all_shutdown_evidence_verified())
                self.assertFalse(log_release.is_set())
                # This exceeds the original budget, but not a fresh .2s budget
                # incorrectly started after the peer finished. Only the clock
                # and the actual file stream boundary are substituted.
                tick += .11
                done, _ = await asyncio.wait({task}, timeout=.5)
                self.assertIn(task, done, 'log wait restarted the final deadline')
                await task
                exit_process.assert_called_once_with(2)
            finally:
                # A failed assertion must not leave a pending task at a frozen
                # tick. This advance is cleanup only, after the exit assertion.
                tick += 2.
                log_release.set()
                await task
        with patch.object(app, 'time', wraps=time) as clock, patch.object(app.os, '_exit') as exit_process:
            clock.monotonic.side_effect = lambda: tick
            self.loop.run_until_complete(run())

    def run_overlapping_cleanup(self, *, hold_peer_final=False):
        # The frozen-clock peer-ordering case retains real file publication and
        # readback. Give its host I/O a separate bounded watchdog; the product's
        # 1s receipt / 0.2s final deadlines and explicit stall tests stay intact.
        host_timeout = 10 if hold_peer_final else 3
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
        peer_entered, peer_release = threading.Event(), threading.Event()
        self.releases.append(peer_release)
        original_fsync = os.fsync
        def fsync(fd):
            name = threading.current_thread().name
            if hold_peer_final and name == 'shutdown-evidence-final-lifespan':
                peer_entered.set()
                if not peer_release.wait(host_timeout):
                    raise RuntimeError('peer final release missing')
            if hold_peer_final and name == 'shutdown-evidence-final-control':
                if not peer_entered.wait(host_timeout):
                    raise RuntimeError('peer final did not start')
            return original_fsync(fd)
        def fail_start():
            csv_threads.append(logger.thread)
            raise OSError('partial lifecycle start')
        def stop_config():
            with lock:
                stopped.append(True)
                if len(stopped) == 2:
                    reached.set()
            return release.wait(max(5, host_timeout))
        async def partial():
            async with app.lifespan(app.app):
                self.fail('partial startup should fail')
        async def run():
            tasks = [asyncio.create_task(partial()), asyncio.create_task(app._run_control_shutdown('overlap'))]
            try:
                self.assertTrue(await asyncio.to_thread(reached.wait, host_timeout))
                release.set()
                if hold_peer_final:
                    await self.wait_control_receipt(timeout_sec=host_timeout)
                    # Hold the real peer fsync beyond the control writer's poll
                    # tick, then release within the existing final 0.2s budget.
                    await asyncio.sleep(.03)
                    self.assertTrue(peer_entered.is_set())
                    peer = app._get_shutdown_evidence_status()['lifespan']
                    self.assertTrue(peer['writer_alive'])
                    self.assertFalse(peer['receipt_verified'])
                    self.assertIsNone(peer['error_phase'])
                    exit_process.assert_not_called()
            finally:
                release.set()
                peer_release.set()
                # The test-controlled app clock must not make a broken peer
                # handshake hang the runner. asyncio retains its real clock.
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=host_timeout,
                )
            self.assertIsInstance(results[0], OSError)
            self.assertIsNone(results[1])
        try:
            with patch.object(app, 'logger_service', logger), \
                 patch.object(app, '_lock_path', self.root / 'instance.lock'), \
                 patch.object(app.config_sync_agent, 'start', side_effect=fail_start), \
                 patch.object(app.config_sync_agent, 'stop', side_effect=stop_config), \
                 patch.object(evidence.os, 'fsync', fsync), \
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
        path, log_entered, log_release, _, _ = self.final_log_sink(block=True)
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
        async def run():
            task = asyncio.create_task(app._run_control_shutdown('peer-during-log-ack'))
            try:
                self.assertTrue(await asyncio.to_thread(log_entered.wait, 3))
                self.assertTrue(app._get_shutdown_evidence_status()['control']['receipt_verified'])
                peers.append(await app._begin_shutdown_evidence('lifespan'))
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
            finally:
                log_release.set()
                await task
        try:
            with patch.object(evidence.os, 'fsync', fsync), patch.object(app.os, '_exit') as exit_process:
                self.loop.run_until_complete(run())
            exit_process.assert_called_once_with(2)
            self.assertEqual(len(peers), 1)
            self.assertTrue(peers[0].status()['writer_alive'])
            self.assertFalse(app._all_shutdown_evidence_verified())
            final = [json.loads(line) for line in path.read_text().splitlines()
                     if 'Control shutdown complete' in line]
            self.assertEqual(len(final), 2)
            self.assertIn('success=False exit_code=2', final[-1]['message'])
            self.assertEqual(final[-1]['shutdown_log_revision'], 2)
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
