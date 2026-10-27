"""CSV startup must not wait for historical image-manifest initialization."""
import asyncio
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from backend.FacilityData.drivers import spot_api
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData import spot_image_fact
from backend.FacilityData.spot_image_fact import SpotImageCaptureWriter


class CsvImageStartupTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(spot_api._reset_spot_image_capture_state_for_tests)
        self.request_initializer = spot_api._request_spot_image_manifest_initialization
        self.initialization_request = self.stack.enter_context(
            patch.object(spot_api, '_request_spot_image_manifest_initialization'))
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for name, value in {'LOG_PATH': self.root, 'SPOT_IMAGE_CAPTURE_ENABLED': True,
                            'SPOT_IMAGE_CAPTURE_MODE': 'all', 'SPOT_IMAGE_CAPTURE_PATH': 'spot_images'}.items():
            self.stack.enter_context(patch.object(spot_api.config, name, value))
        for name in ['_spot_image_capture_writer', '_spot_image_capture_writer_signature']:
            self.stack.enter_context(patch.object(spot_api, name, None))
        self.logger = CSVLoggerService(require_runtime_manifest_state=True)
        self.logger.apply_config(log_path=self.root, auto_save=True, csv_v1_enabled=False,
                                 csv_v2_enabled=True, csv_v2_operational_fields_enabled=True,
                                 csv_v2_temperature_hardening_enabled=True)
        # Isolate the image startup path; observation closeout has its own suite.
        self.stack.enter_context(patch.object(self.logger, '_spot_observation_fact_manifest',
                                             return_value={'enabled': False}))

    def open_csv(self):
        handle, writer = self.logger._open_v2_log_file('20261019_220821', 'Factory_Integrated_Log_v2')
        self.assertIsNotNone(handle)
        try:
            self.assertIsNotNone(writer)
            return json.loads(self.logger._current_v2_csv_path.with_suffix('.metadata.json').read_text(encoding='utf-8'))
        finally:
            if handle is not None:
                handle.close()

    def assert_pending(self, metadata):
        self.assertNotIn('spot_image_fact_manifest', metadata)
        self.assertFalse(metadata['spot_image_fact_closeout']['finalized'])
        self.assertFalse(metadata['spot_image_fact_closeout']['writes_drained'])
        self.assertEqual(metadata['spot_image_fact_closeout']['reason'], 'image-persistence-pending-at-open')
        self.assertFalse(self.logger._runtime_write_failure_observed)

    def test_poll_start_initializes_image_owner_without_capture(self):
        started, release = threading.Event(), threading.Event()
        initialize = SpotImageCaptureWriter._initialize_manifest_state
        owners = []

        def blocked(writer):
            owners.append(threading.current_thread())
            started.set()
            if not release.wait(5):
                raise TimeoutError('test initializer not released')
            initialize(writer)

        async def idle_poll():
            await asyncio.Event().wait()

        async def exercise():
            try:
                await asyncio.wait_for(spot_api.start_spot_poll_loop(), timeout=.5)
                self.assertTrue(await asyncio.to_thread(started.wait, .5),
                                'image owner did not start without a capture or UI request')
                task = spot_api._spot_poll_task
                self.assertFalse(task.done())
                await spot_api.start_spot_poll_loop()
                self.assertIs(spot_api._spot_poll_task, task)
                self.assertEqual(len(owners), 1)
                self.assertIsNot(owners[0], threading.current_thread())
                self.assertEqual(spot_api._spot_image_capture_enqueued_count, 0)
                self.assertEqual(spot_api._SPOT_IMAGE_CAPTURE_QUEUE.unfinished_tasks, 0)
            finally:
                release.set()
                task = spot_api._spot_poll_task
                if task is not None:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                self.assertTrue(spot_api.stop_spot_image_capture_writer(timeout_sec=2))

        with patch.object(spot_api, '_request_spot_image_manifest_initialization', self.request_initializer), \
                patch.object(SpotImageCaptureWriter, '_initialize_manifest_state', blocked), \
                patch.object(spot_api.config, 'SPOT_OBSERVATION_FACT_ENABLED', False), \
                patch.object(spot_api, '_get_spot_diagnostic_request_journal', return_value=None), \
                patch.object(spot_api, '_start_spot_http_transport'), \
                patch.object(spot_api, '_spot_poll_loop', idle_poll), \
                patch.object(spot_api, '_spot_poll_task', None), \
                patch.object(spot_api, '_spot_poll_running', False), \
                patch.object(spot_api, '_img_accepting_requests', False), \
                patch.object(spot_api, '_spot_diagnostic_journal_shutdown_started', False):
            asyncio.run(exercise())

    def test_csv_opens_while_image_writer_initialization_is_blocked(self):
        started, release, opened = threading.Event(), threading.Event(), threading.Event()
        initialize = SpotImageCaptureWriter._initialize_manifest_state

        def blocked(writer):
            started.set()
            if not release.wait(5):
                raise TimeoutError('test initialization not released')
            initialize(writer)

        def open_csv():
            metadata = self.open_csv()
            opened.set()
            return metadata

        with patch.object(SpotImageCaptureWriter, '_initialize_manifest_state', blocked):
            with ThreadPoolExecutor(max_workers=2) as executor:
                construction = executor.submit(spot_api._get_spot_image_capture_writer)
                self.assertTrue(started.wait(2))
                opening = executor.submit(open_csv)
                try:
                    self.assertTrue(opened.wait(.5), 'CSV startup waited for image fact initialization')
                    self.assert_pending(opening.result(timeout=.5))
                finally:
                    release.set()
                    construction.result(timeout=2)
                    opening.result(timeout=2)

    def test_cold_csv_open_does_not_initialize_image_writer(self):
        with patch.object(SpotImageCaptureWriter, '_initialize_manifest_state',
                          side_effect=AssertionError('startup started historical scan')):
            self.assert_pending(self.open_csv())
        self.assertIsNone(spot_api._spot_image_capture_writer)
        self.initialization_request.assert_called_once_with()

    def test_cold_csv_schedules_owned_initialization_before_shutdown(self):
        started, release = threading.Event(), threading.Event()
        initialize = SpotImageCaptureWriter._initialize_manifest_state

        def blocked(writer):
            started.set()
            if not release.wait(5):
                raise TimeoutError('test initializer not released')
            initialize(writer)

        try:
            with patch.object(spot_api.config, 'SPOT_IMAGE_CAPTURE_ENABLED', False), \
                    patch.object(spot_api, '_request_spot_image_manifest_initialization', self.request_initializer), \
                    patch.object(SpotImageCaptureWriter, '_initialize_manifest_state', blocked):
                self.assert_pending(self.open_csv())
                self.assertTrue(started.wait(.5), 'initialization was deferred until shutdown')
                self.assertFalse(spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=.01))
                release.set()
                self.assertTrue(spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=2))
                with patch.object(SpotImageCaptureWriter, '_initialize_manifest_state',
                                  side_effect=AssertionError('shutdown started a historical scan')):
                    self.logger.write_spot_image_fact_final_manifest()
        finally:
            release.set()
            spot_api._reset_spot_image_capture_state_for_tests()

    def test_initialization_failure_is_not_counted_as_a_lost_capture(self):
        with patch.object(spot_api, '_request_spot_image_manifest_initialization', self.request_initializer), \
                patch.object(SpotImageCaptureWriter, '_initialize_manifest_state',
                             side_effect=OSError('injected manifest read failure')):
            self.open_csv()
            self.assertFalse(spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=2))
        status = spot_api.get_spot_image_capture_shutdown_status()
        self.assertFalse(status['worker_alive'])
        self.assertTrue(status['manifest_initialization_failed'])
        self.assertTrue(status['accounting_consistent'])
        self.assertEqual(status['enqueued_count'], 0)
        self.assertEqual(status['failure_count'], 0)
        self.assertTrue(status['integrity_unresolved'])
        with patch.object(SpotImageCaptureWriter, '_initialize_manifest_state',
                          side_effect=AssertionError('closeout retried failed initialization')) as initialize:
            with self.assertRaisesRegex(RuntimeError, 'state is unavailable'):
                self.logger.write_spot_image_fact_final_manifest()
            initialize.assert_not_called()

    def test_reconfiguration_during_owned_initialization_is_not_lost(self):
        started, release = threading.Event(), threading.Event()
        initialize = SpotImageCaptureWriter._initialize_manifest_state
        calls = []

        def blocked_first(writer):
            calls.append(writer.retention_days)
            if len(calls) == 1:
                started.set()
                if not release.wait(5):
                    raise TimeoutError('test initializer not released')
            initialize(writer)

        try:
            with patch.object(spot_api, '_request_spot_image_manifest_initialization', self.request_initializer), \
                    patch.object(SpotImageCaptureWriter, '_initialize_manifest_state', blocked_first):
                self.assert_pending(self.open_csv())
                self.assertTrue(started.wait(.5))
                with patch.object(spot_api.config, 'SPOT_IMAGE_CAPTURE_RETENTION_DAYS', 99):
                    self.request_initializer()
                    release.set()
                    self.assertTrue(spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=2))
                    self.assertEqual(spot_api._spot_image_capture_writer.retention_days, 99)
                    self.assertEqual(len(calls), 2)
                    self.assertTrue(spot_api.get_spot_image_capture_shutdown_status()['accounting_consistent'])
        finally:
            release.set()
            spot_api._reset_spot_image_capture_state_for_tests()

    def test_shutdown_rejects_a_new_initialization_request(self):
        self.assertTrue(spot_api.stop_spot_image_capture_for_shutdown(timeout_sec=2))
        self.request_initializer()
        self.assertFalse(spot_api._SPOT_IMAGE_MANIFEST_INITIALIZATION_REQUESTED.is_set())
        self.assertIsNone(spot_api._spot_image_capture_thread)

    def test_ready_image_manifest_still_has_verified_runtime_hash(self):
        writer = spot_api._get_spot_image_capture_writer()
        metadata = self.open_csv()
        self.assertNotIn('spot_image_fact_closeout', metadata)
        manifest = metadata['spot_image_fact_manifest']
        self.assertEqual(manifest['row_count'], writer.fact_row_count)
        self.assertEqual(manifest['sha256'], writer.fact_sha256)
        self.assertFalse(self.logger._runtime_write_failure_observed)

    def test_final_manifest_path_remains_strict(self):
        spot_api._get_spot_image_capture_writer()
        with self.assertRaisesRegex(RuntimeError, 'path does not match'):
            self.logger._spot_image_fact_manifest(self.root / 'different')

    def test_cold_writer_with_wrong_path_is_failure_not_pending(self):
        with self.assertRaisesRegex(RuntimeError, 'path does not match'):
            self.logger._spot_image_fact_manifest(self.root / 'different', wait_for_manifest=False)
        self.assertIsNone(spot_api._spot_image_capture_writer)

    def test_stale_writer_does_not_start_replacement_during_csv_open(self):
        previous = spot_api._get_spot_image_capture_writer()
        with patch.object(spot_api.config, 'SPOT_IMAGE_CAPTURE_RETENTION_DAYS', 99):
            self.assert_pending(self.open_csv())
        self.assertIs(spot_api._spot_image_capture_writer, previous)

    def test_busy_image_file_does_not_hold_csv_startup(self):
        spot_api._get_spot_image_capture_writer()
        held, release = threading.Event(), threading.Event()

        def hold_file():
            with spot_image_fact._SPOT_IMAGE_FACT_FILE_LOCK:
                held.set()
                if not release.wait(5):
                    raise TimeoutError('test image lock not released')

        with ThreadPoolExecutor(max_workers=2) as executor:
            holding = executor.submit(hold_file)
            self.assertTrue(held.wait(2))
            opening = executor.submit(self.open_csv)
            try:
                self.assert_pending(opening.result(timeout=.5))
            finally:
                release.set()
                holding.result(timeout=2)
                opening.result(timeout=2)

    def test_invalid_ready_manifest_remains_real_failure(self):
        writer = spot_api._get_spot_image_capture_writer()
        writer._manifest_state_ready = False
        metadata = self.open_csv()
        self.assertEqual(metadata['spot_image_fact_closeout']['reason'],
                         'runtime-manifest-unavailable-at-open')
        self.assertTrue(self.logger._runtime_write_failure_observed)
        with self.assertRaisesRegex(RuntimeError, 'state is unavailable'):
            self.logger.write_spot_image_fact_final_manifest()

    def test_pending_startup_does_not_replace_final_manifest_validation(self):
        self.assert_pending(self.open_csv())
        writer = spot_api._get_spot_image_capture_writer()
        path = self.logger.write_spot_image_fact_final_manifest()
        final = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(final['fact_path'], str(writer.fact_path))
        self.assertEqual(final['row_count'], writer.fact_row_count)
        self.assertEqual(final['sha256'], writer.fact_sha256)


if __name__ == '__main__':
    unittest.main()
