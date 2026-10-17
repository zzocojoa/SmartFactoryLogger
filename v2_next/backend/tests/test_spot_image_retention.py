import csv
import hashlib
import os
import queue
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.FacilityData import spot_image_fact
from backend.FacilityData.spot_image_fact import SpotImageCaptureWriter


class SpotImageRetentionTests(unittest.TestCase):
    def make_files(self, root: Path, count: int, *, modified: float | None = None) -> list[Path]:
        day = root / "2026" / "10" / "01"
        day.mkdir(parents=True, exist_ok=True)
        files = []
        for number in range(count):
            path = day / f"spotimg_20261001T000000000000Z_{number:012x}.jpg"
            path.write_bytes(b"preserved-image")
            if modified is not None:
                os.utime(path, (modified, modified))
            files.append(path)
        return files

    @contextmanager
    def writer(self, directory: str, **kwargs):
        root = Path(directory)
        writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", last_cleanup_at=0, **kwargs)
        try:
            yield writer
        finally:
            close = getattr(writer, "close_retention_scan", None)
            if close is not None:
                close()

    def complete(self, writer, now):
        for _ in range(1000):
            if writer._retention_scan is None:
                return
            writer._cleanup_retention(now, allow_start=False)
        self.fail("retention scan did not finish")

    def capture(self, writer):
        return writer.write_capture(image_bytes=b"new capture", captured_at=time.time(),
                                    source_url="http://spot.invalid/image.jpg", source="test",
                                    image_age_ms=None, link_checked_at=None, observation_snapshot=None)

    def test_one_capture_does_not_wait_for_entire_retained_directory(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            files = self.make_files(writer.capture_root, 600)
            original = writer._is_managed_capture_file
            visited = []

            def inspect(path):
                visited.append(path)
                return original(path)

            with patch.object(writer, "_is_managed_capture_file", side_effect=inspect):
                fact = self.capture(writer)
            self.assertLessEqual(len(visited), 256)
            self.assertTrue(all(path.exists() for path in files))
            self.assertEqual((writer.log_path / fact["spot_image_path"]).read_bytes(), b"new capture")
            with writer.fact_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["spot_image_sha256"], hashlib.sha256(b"new capture").hexdigest())

    def test_elapsed_budget_yields_before_more_files_are_examined(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            self.make_files(writer.capture_root, 20)
            original = writer._is_managed_capture_file
            clock = [0.0]
            visited = []

            def inspect(path):
                visited.append(path)
                clock[0] += 0.006
                return original(path)

            with patch.object(spot_image_fact.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(writer, "_is_managed_capture_file", side_effect=inspect):
                writer._cleanup_retention(time.time())
            self.assertEqual(len(visited), 2)

    def test_slices_finish_without_waiting_another_hour_and_preserve_nonmanaged_files(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as directory, self.writer(directory, retention_days=1) as writer:
            expired = self.make_files(writer.capture_root, 600, modified=now - 172800)
            day = expired[0].parent
            preserved = [day / "operator-note.txt", day / "spotimg_manual.jpg",
                         day / "spotimg_20261001T000000000000Z_abcdef123456.jpg.tmp",
                         writer.capture_root / "spotimg_20261001T000000000000Z_abcdef123456.jpg",
                         writer.capture_root / "manual" / expired[0].name]
            for path in preserved:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"operator-owned")
                os.utime(path, (now - 172800, now - 172800))
            boundary = day / "spotimg_20261001T000000000000Z_abcdef123456.jpg"
            boundary.write_bytes(b"boundary")
            # Read back the representable timestamp to test a strict boundary.
            os.utime(boundary, (now - 86400, now - 86400))
            now = boundary.stat().st_mtime + 86400
            with patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                writer._cleanup_retention(now)
                self.assertTrue(any(path.exists() for path in expired))
                self.complete(writer, now)
            self.assertTrue(all(not path.exists() for path in expired))
            self.assertTrue(all(path.read_bytes() == b"operator-owned" for path in preserved))
            self.assertEqual(boundary.read_bytes(), b"boundary")
            self.assertEqual(writer.last_cleanup_at, now)

    def test_idle_does_not_start_a_new_cycle(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            files = self.make_files(writer.capture_root, 1, modified=now - 864000)
            writer._cleanup_retention(now, allow_start=False)
            self.assertTrue(files[0].exists())
            self.assertEqual(writer.last_cleanup_at, 0)

    def test_only_empty_ancestors_of_managed_day_directories_are_removed(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            for relative in ("2024", "2025/01", "2026/02/02"):
                (writer.capture_root / relative).mkdir(parents=True)
            writer._cleanup_retention(time.time())
            self.complete(writer, time.time())
            self.assertTrue((writer.capture_root / "2024").is_dir())
            self.assertTrue((writer.capture_root / "2025/01").is_dir())
            self.assertFalse((writer.capture_root / "2026").exists())

    def test_wide_nonmanaged_directory_enumeration_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            for number in range(600):
                (writer.capture_root / f"manual-{number}").mkdir(parents=True)
            with patch.object(spot_image_fact, "_is_date_component", wraps=spot_image_fact._is_date_component) as component, \
                    patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                writer._cleanup_retention(time.time())
                self.assertGreater(component.call_count, 0)
                self.assertLessEqual(component.call_count, 256)
            self.complete(writer, time.time())
            self.assertEqual(len(list(writer.capture_root.iterdir())), 600)

    def test_link_and_reparse_entries_are_not_followed(self):
        for kind in ("symlink", "reparse"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
                files = self.make_files(writer.capture_root, 1, modified=time.time() - 864000)
                blocked = writer.capture_root / "2026"
                scandir = os.scandir

                class Entry:
                    def __init__(self, entry):
                        self.entry = entry

                    def __getattr__(self, name):
                        return getattr(self.entry, name)

                    def is_symlink(self):
                        return kind == "symlink" and Path(self.entry.path) == blocked

                    def stat(self, *, follow_symlinks=True):
                        if kind == "reparse" and Path(self.entry.path) == blocked:
                            return SimpleNamespace(st_file_attributes=0x400)
                        return self.entry.stat(follow_symlinks=follow_symlinks)

                @contextmanager
                def entries(path):
                    self.assertNotEqual(Path(path), blocked)
                    with scandir(path) as iterator:
                        yield (Entry(entry) for entry in iterator)

                with patch.object(spot_image_fact.os, "scandir", side_effect=entries):
                    writer._cleanup_retention(time.time())
                    self.complete(writer, time.time())
                self.assertTrue(files[0].exists())

    def test_disable_and_close_release_open_directory_handles(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            self.make_files(writer.capture_root, 600)
            scandir = os.scandir
            active = []

            @contextmanager
            def tracked(path):
                with scandir(path) as entries:
                    active.append(path)
                    try:
                        yield entries
                    finally:
                        active.remove(path)

            with patch.object(spot_image_fact.os, "scandir", side_effect=tracked), \
                    patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                writer._cleanup_retention(time.time())
                self.assertTrue(active)
                writer.retention_days = 0
                writer._cleanup_retention(time.time())
                self.assertEqual(active, [])
                writer.retention_days = 7
                writer.last_cleanup_at = 0
                writer._cleanup_retention(time.time())
                self.assertTrue(active)
                writer.close_retention_scan()
                writer.close_retention_scan()
                self.assertEqual(active, [])
            self.assertIsNone(writer._retention_scan)

    def test_io_error_closes_scan_and_retries_only_next_interval(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer:
            files = self.make_files(writer.capture_root, 1, modified=now - 864000)
            with patch.object(writer, "_is_managed_capture_file", side_effect=OSError("unavailable")):
                writer._cleanup_retention(now)
            self.assertIsNone(writer._retention_scan)
            writer._cleanup_retention(now + 1)
            self.assertTrue(files[0].exists())
            writer._cleanup_retention(now + 3600)
            self.complete(writer, now + 3600)
            self.assertFalse(files[0].exists())
            self.assertFalse(files[0].parent.exists())

    @contextmanager
    def worker_state(self, writer):
        from backend.FacilityData.drivers import spot_api
        pending = queue.Queue()
        stop = threading.Event()
        signature = (writer.log_path, writer.capture_root, writer.retention_days, writer.link_stale_threshold_ms)
        with patch.multiple(spot_api, _SPOT_IMAGE_CAPTURE_QUEUE=pending, _SPOT_IMAGE_CAPTURE_STOP=stop,
                            _spot_image_capture_writer=writer, _spot_image_capture_writer_signature=signature,
                            _get_spot_image_capture_writer=Mock(return_value=writer),
                            _spot_image_capture_config_signature=Mock(return_value=signature),
                            _spot_image_capture_written_count=0, _spot_image_capture_failure_count=0,
                            _spot_image_capture_last_write_at=0.0, _spot_image_capture_last_fact=None,
                            _spot_image_capture_last_error_at=0.0, _spot_image_capture_last_error_code=None,
                            _spot_image_capture_last_error_message=None):
            yield spot_api, pending, stop

    def enqueue(self, api, pending, number=0):
        pending.put(api._SpotImageCaptureEvent(image_bytes=f"new capture {number}".encode(),
                    captured_at=time.time(), source_url="http://spot.invalid/image.jpg", source="test",
                    image_age_ms=None, link_checked_at=None, observation_snapshot=None))

    def test_worker_idle_finishes_started_scan_and_preserves_capture_accounting(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer, self.worker_state(writer) as (api, pending, stop):
            expired = self.make_files(writer.capture_root, 300, modified=time.time() - 864000)
            self.enqueue(api, pending)
            get = pending.get
            idle_calls = []

            def next_event(timeout):
                if not pending.empty():
                    return get(timeout=timeout)
                idle_calls.append(True)
                if len(idle_calls) == 2:
                    stop.set()
                raise queue.Empty

            with patch.object(pending, "get", side_effect=next_event), \
                    patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                api._spot_image_capture_worker()
            self.assertTrue(all(not path.exists() for path in expired))
            self.assertEqual(pending.unfinished_tasks, 0)
            self.assertEqual(api._spot_image_capture_written_count, 1)
            self.assertEqual(api._spot_image_capture_failure_count, 0)
            self.assertIsNone(writer._retention_scan)
            fact = api._spot_image_capture_last_fact
            self.assertEqual((writer.log_path / fact["spot_image_path"]).read_bytes(), b"new capture 0")

    def test_shutdown_closes_partial_scan_after_draining_capture(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer, self.worker_state(writer) as (api, pending, stop):
            expired = self.make_files(writer.capture_root, 600, modified=time.time() - 864000)
            self.enqueue(api, pending)
            stop.set()
            with patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                api._spot_image_capture_worker()
            self.assertTrue(any(path.exists() for path in expired))
            self.assertIsNone(writer._retention_scan)
            self.assertEqual(pending.unfinished_tasks, 0)
            self.assertEqual(api._spot_image_capture_written_count, 1)

    def test_writer_change_closes_each_owned_scan(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second, \
                self.writer(first) as first_writer, self.writer(second) as second_writer, \
                self.worker_state(first_writer) as (api, pending, stop):
            for writer in (first_writer, second_writer):
                self.make_files(writer.capture_root, 600)
            self.enqueue(api, pending, 1)
            self.enqueue(api, pending, 2)
            stop.set()
            api._get_spot_image_capture_writer.side_effect = [first_writer, second_writer]
            with patch.object(first_writer, "close_retention_scan", wraps=first_writer.close_retention_scan) as first_close, \
                    patch.object(second_writer, "close_retention_scan", wraps=second_writer.close_retention_scan) as second_close, \
                    patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                api._spot_image_capture_worker()
                first_close.assert_called_once()
                second_close.assert_called_once()
            self.assertIsNone(first_writer._retention_scan)
            self.assertIsNone(second_writer._retention_scan)
            self.assertEqual(pending.unfinished_tasks, 0)
            self.assertEqual(api._spot_image_capture_written_count, 2)

    def test_idle_configuration_change_cancels_old_directory_scan(self):
        with tempfile.TemporaryDirectory() as directory, self.writer(directory) as writer, self.worker_state(writer) as (api, pending, stop):
            expired = self.make_files(writer.capture_root, 600, modified=time.time() - 864000)
            self.enqueue(api, pending)
            get = pending.get
            remaining = []

            def next_event(timeout):
                if not pending.empty():
                    return get(timeout=timeout)
                if not remaining:
                    remaining.append(sum(path.exists() for path in expired))
                    api._spot_image_capture_config_signature.return_value = None
                else:
                    stop.set()
                raise queue.Empty

            with patch.object(pending, "get", side_effect=next_event), \
                    patch.object(spot_image_fact.time, "monotonic", return_value=0.0):
                api._spot_image_capture_worker()
            self.assertGreater(remaining[0], 0)
            self.assertEqual(sum(path.exists() for path in expired), remaining[0])
            self.assertIsNone(writer._retention_scan)
            self.assertEqual(pending.unfinished_tasks, 0)


if __name__ == "__main__":
    unittest.main()
