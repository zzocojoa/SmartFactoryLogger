import asyncio
import csv
import json
import hashlib
import os
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from backend.FacilityData.drivers import spot_api
from backend.FacilityData.spot_observation_fact import SpotObservationFactWriter
from backend.FacilityData.spot_observation_queue import SpotObservationQueue, FactPersistencePending
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.drivers.real_plc import RealPLCDriver


class FactPollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logger_loop_daily_rollover_and_stop_propagate_deferred_failure(self):
        for successful in [True, False]:
            written = threading.Event()
            original = CSVLoggerService._flush_v2_buffer
            def flushed(logger, writer, handle, buffer):
                rows = list(buffer)
                result = original(logger, writer, handle, rows)
                if result and rows and logger._sample_seq == 2:
                    written.set()
                return result
            with self.subTest(successful=successful), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                fact_path = Path(tmp) / "spot_observation_fact.csv"
                owner = SpotObservationQueue(lambda: SpotObservationFactWriter(fact_path))
                for name, value in {"_spot_observation_queue": owner, "_spot_observation_queue_path": fact_path.resolve()}.items():
                    stack.enter_context(patch.object(spot_api, name, value))
                stack.enter_context(patch.object(spot_api.config, "SPOT_OBSERVATION_FACT_ENABLED", True))
                stack.enter_context(patch.object(spot_api.config, "LOG_PATH", tmp))
                stack.enter_context(patch.object(CSVLoggerService, "_flush_v2_buffer", flushed))
                owner.enqueue(observation())
                await asyncio.to_thread(owner._queue.join)
                logger = CSVLoggerService(require_runtime_manifest_state=True)
                logger.apply_config(log_path=Path(tmp), auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True,
                    csv_v2_operational_fields_enabled=True, csv_v2_temperature_hardening_enabled=True)
                logger.start()
                try:
                    for day in [9, 10]:
                        logger.enqueue(FactoryData(Time=f"2026-09-{day:02d}T00:00:00Z", Status="Running"))
                    self.assertTrue(await asyncio.to_thread(written.wait, 3))
                    self.assertEqual(len(logger._deferred_observation_closeouts), 1)
                    self.assertFalse(logger._runtime_write_failure_observed)
                    first = next(iter(logger._deferred_observation_closeouts))
                    if not successful:
                        first.with_suffix(".metadata.json").write_text("{invalid", encoding="utf-8")
                finally:
                    self.assertTrue(await asyncio.to_thread(owner.close, 2))
                    self.assertEqual(await asyncio.to_thread(logger.stop, timeout_sec=3), successful)
                paths = list(Path(tmp).glob("Factory_Integrated_Log_v2*.metadata.json"))
                self.assertEqual(len(paths), 2)
                if successful:
                    self.assertTrue(all(json.loads(path.read_text(encoding="utf-8"))["csv_closeout"]["finalized"] for path in paths))
                else:
                    self.assertEqual(len(logger._deferred_observation_closeouts), 1)

    @unittest.skipUnless(os.environ.get("TEMPERATURE_GOAL_PACKAGE"), "private F01 fixture supplied only for goal verification")
    async def test_f01_raw_inputs_poll_publish_csv_continue_during_fact_initialization(self):
        fixture = Path(os.environ["TEMPERATURE_GOAL_PACKAGE"]) / "fixtures/F01_startup_and_poll1.csv"
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),
                         "bab8f61354124b5fdfa155abdb289255a2514fb710f4fa5e23a7e43418dec4b4")
        with fixture.open(encoding="utf-8-sig", newline="") as stream:
            historical = list(csv.DictReader(stream))
        self.assertEqual(len(historical), 940)
        inputs = [historical[14], historical[908]]
        self.assertEqual([row["spot_poll_seq"] for row in inputs], ["1", "2"])
        started, release, written = threading.Event(), threading.Event(), threading.Event()
        original_load, original_flush = SpotObservationFactWriter._load_manifest_state_from_output, CSVLoggerService._flush_v2_buffer
        timings = {"kind": "synthetic Event/I-O timing using verified F01 raw payloads; not historical monotonic evidence"}
        def blocked(writer):
            timings["fact_initialization_entered"] = time.monotonic()
            started.set()
            if not release.wait(15):
                raise TimeoutError("F01 test did not release initialization")
            result = original_load(writer)
            timings["fact_existing_file_scan_completed"] = time.monotonic()
            return result
        def flushed(logger, writer, handle, buffer):
            rows = list(buffer)
            result = original_flush(logger, writer, handle, rows)
            if result and rows:
                timings["csv_persisted"] = time.monotonic()
                written.set()
            return result
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            for name, value in {"LOG_PATH": tmp, "SPOT_OBSERVATION_FACT_ENABLED": True,
                                "SPOT_URL": "http://spot.test/output"}.items():
                stack.enter_context(patch.object(spot_api.config, name, value))
            for name, value in {"_spot_observation_fact_writer": None, "_spot_observation_queue": None,
                                "_spot_observation_queue_path": None, "_spot_poll_seq": 0,
                                "_spot_observation_seq": 0, "_spot_temperature_snapshot": None}.items():
                stack.enter_context(patch.object(spot_api, name, value))
            stack.enter_context(patch.object(spot_api, "_active_spot_http_transport", return_value=None))
            # Seed a different synthetic service so initialization really hashes/indexes an existing file.
            SpotObservationFactWriter(Path(tmp) / "spot_observation_fact.csv").write_fact(observation())
            stack.enter_context(patch.object(SpotObservationFactWriter, "_load_manifest_state_from_output", blocked))
            stack.enter_context(patch.object(CSVLoggerService, "_flush_v2_buffer", flushed))
            logger = CSVLoggerService(require_runtime_manifest_state=True)
            logger.apply_config(log_path=Path(tmp), auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True,
                csv_v2_operational_fields_enabled=True, csv_v2_temperature_hardening_enabled=True)
            logger.start()
            try:
                responses = iter(inputs)
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                    httpx.Response(200, text=next(responses)["spot_temperature_raw"], request=request))) as client:
                    for index in range(2):
                        timings[f"poll_{index+1}_requested"] = time.monotonic()
                        await spot_api._refresh_spot_temperature(client)
                        timings[f"poll_{index+1}_published"] = time.monotonic()
                        metadata = spot_api._build_spot_temperature_snapshot_diagnostics(time.time())
                        fields = RealPLCDriver._spot_metadata_to_factory_fields(None, metadata)
                        logger.enqueue(FactoryData(Time=datetime.now(timezone.utc).isoformat(), Status="Running", **fields))
                        timings[f"csv_{index+1}_enqueued"] = time.monotonic()
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                self.assertTrue(await asyncio.to_thread(written.wait, 3))
                self.assertFalse(release.is_set())
                self.assertEqual(spot_api._spot_temperature_snapshot["spot_poll_seq"], 2)
                self.assertFalse(logger._runtime_write_failure_observed)
            finally:
                release.set()
                self.assertTrue(await spot_api.wait_for_spot_observation_fact_writes_drain(3))
                self.assertTrue(await asyncio.to_thread(logger.stop, timeout_sec=3))
            timings["fact_health"] = spot_api.get_spot_observation_fact_health()["persistence"]
            timings["csv_build_duration_ms"] = logger._last_row_build_duration_ms
            timings["csv_flush_duration_ms"] = logger._last_csv_flush_duration_ms
            metadata_path = next(Path(tmp).glob("Factory_Integrated_Log_v2*.metadata.json"))
            final = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertTrue(final["csv_closeout"]["finalized"])
            self.assertEqual(final["spot_observation_fact_manifest"]["row_count"], 3)
        output = os.environ.get("TEMPERATURE_EVIDENCE_OUTPUT")
        if output:
            (Path(output) / "f01_event_timing.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")

    async def test_actual_poll_stop_then_logger_closeout_success_and_timeout(self):
        for timeout in [False, True]:
            started, release = threading.Event(), threading.Event()
            original = SpotObservationFactWriter._append_fact
            def blocked(writer, fact):
                started.set()
                if not release.wait(5):
                    raise TimeoutError("test append not released")
                return original(writer, fact)
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                path = Path(tmp) / "spot_observation_fact.csv"
                stack.enter_context(patch.object(spot_api.config, "SPOT_OBSERVATION_FACT_ENABLED", True))
                stack.enter_context(patch.object(SpotObservationFactWriter, "_append_fact", blocked))
                owner = SpotObservationQueue(lambda: SpotObservationFactWriter(path))
                for name, value in {"_spot_observation_queue": owner, "_spot_observation_queue_path": path.resolve(),
                                    "_spot_poll_task": None, "_spot_diagnostics_task": None, "_internal_temperature_task": None,
                                    "_spot_poll_running": False, "_spot_shutdown_started_monotonic": None,
                                    "_spot_shutdown_image_refresh_stopped": False, "_spot_shutdown_transport_stopped": False,
                                    "_spot_shutdown_task_states": dict(spot_api._spot_shutdown_task_states),
                                    "_SPOT_OBSERVATION_FACT_DRAIN_TIMEOUT_SEC": .02 if timeout else 1}.items():
                    stack.enter_context(patch.object(spot_api, name, value))
                # External image/HTTP shutdown I/O is unrelated to the real fact owner being tested.
                stack.enter_context(patch.object(spot_api, "_stop_spot_image_refresh_for_shutdown", return_value=True))
                stack.enter_context(patch.object(spot_api, "_stop_spot_http_transport", return_value=True))
                owner.enqueue(observation())
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                logger = CSVLoggerService(require_runtime_manifest_state=True)
                csv_path = Path(tmp) / "sample.csv"
                csv_path.write_text("sample_seq,spot_observation_key\n1,synthetic-A:1\n", encoding="utf-8")
                csv_path.with_suffix(".metadata.json").write_text("{}", encoding="utf-8")
                logger._current_v2_csv_path = csv_path
                logger._v2_persisted_sample_seq_by_path[str(csv_path)] = 1
                logger._v2_persisted_at_by_path[str(csv_path)] = "2026-09-09T00:00:00Z"
                try:
                    if not timeout:
                        release.set()
                        await asyncio.to_thread(owner._queue.join)
                    stopped = await spot_api.stop_spot_poll_loop()
                    self.assertEqual(stopped, not timeout)
                    logger._finalize_spot_observation_manifest_on_stop = stopped
                    self.assertEqual(logger._close_v2_file(None, closeout_reason="shutdown"), not timeout)
                    payload = json.loads(csv_path.with_suffix(".metadata.json").read_text())
                    self.assertEqual(payload.get("csv_closeout", {}).get("finalized", False), not timeout)
                finally:
                    release.set()
                    self.assertTrue(await spot_api.wait_for_spot_observation_fact_writes_drain(2))

    async def test_cancelled_drain_keeps_writer_owned_until_actual_completion(self):
        started, release = threading.Event(), threading.Event()
        original = SpotObservationFactWriter._append_fact
        def blocked(writer, fact):
            started.set()
            if not release.wait(5):
                raise TimeoutError("test did not release append")
            return original(writer, fact)
        with tempfile.TemporaryDirectory() as tmp, patch.object(SpotObservationFactWriter, "_append_fact", blocked):
            owner = SpotObservationQueue(lambda: SpotObservationFactWriter(Path(tmp) / "facts.csv"))
            with patch.object(spot_api, "_spot_observation_queue", owner):
                owner.enqueue(observation())
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                drain = asyncio.create_task(spot_api.wait_for_spot_observation_fact_writes_drain(2))
                try:
                    await asyncio.sleep(0)  # Yield to cancellation boundary, not a timing proof.
                    drain.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await drain
                    self.assertFalse(spot_api.spot_observation_fact_writes_drained())
                    self.assertIs(spot_api._spot_observation_queue, owner)
                    self.assertTrue(spot_api.get_spot_observation_fact_health()["persistence"]["writer_alive"])
                finally:
                    release.set()
                    self.assertTrue(await spot_api.wait_for_spot_observation_fact_writes_drain(2))

    async def test_initial_fact_scan_does_not_hold_next_poll(self):
        await self._assert_next_poll_during_writer_block("_load_manifest_state_from_output")

    async def test_fact_append_does_not_hold_next_poll(self):
        await self._assert_next_poll_during_writer_block("_append_fact")

    async def _assert_next_poll_during_writer_block(self, method):
        started, release, polled = threading.Event(), threading.Event(), asyncio.Event()
        original = getattr(SpotObservationFactWriter, method)
        def blocked(writer, *args):
            started.set()
            if not release.wait(5):
                raise TimeoutError("test did not release initialization")
            return original(writer, *args)
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(spot_api.config, "LOG_PATH", tmp))
            stack.enter_context(patch.object(spot_api.config, "SPOT_OBSERVATION_FACT_ENABLED", True))
            stack.enter_context(patch.object(spot_api.config, "SPOT_URL", "http://spot.test/output"))
            stack.enter_context(patch.object(spot_api, "_spot_observation_fact_writer", None))
            stack.enter_context(patch.object(spot_api, "_spot_observation_queue", None))
            stack.enter_context(patch.object(spot_api, "_spot_observation_queue_path", None))
            stack.enter_context(patch.object(spot_api, "_spot_poll_seq", 0))
            stack.enter_context(patch.object(spot_api, "_spot_observation_seq", 0))
            stack.enter_context(patch.object(spot_api, "_active_spot_http_transport", return_value=None))
            stack.enter_context(patch.object(SpotObservationFactWriter, method, blocked))
            async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, text="500", request=request))) as client:
                async def producer():
                    await spot_api._refresh_spot_temperature(client)
                    await spot_api._refresh_spot_temperature(client)
                    polled.set()
                task = asyncio.create_task(producer())
                try:
                    self.assertTrue(await asyncio.to_thread(started.wait, 2))
                    await asyncio.wait_for(polled.wait(), .5)
                    self.assertEqual(spot_api._spot_temperature_snapshot["spot_poll_seq"], 2)
                    logger = CSVLoggerService()
                    logger.apply_config(csv_v2_operational_fields_enabled=True,
                                        csv_v2_temperature_hardening_enabled=True)
                    logger._require_runtime_manifest_state = True
                    csv_path = Path(tmp) / "startup.csv"
                    await asyncio.wait_for(asyncio.to_thread(logger._write_v2_sidecar, csv_path), .5)
                    metadata = json.loads(csv_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))
                    self.assertFalse(metadata["spot_observation_fact_closeout"]["finalized"])
                    self.assertFalse(logger._runtime_write_failure_observed)
                    health = spot_api.get_spot_observation_fact_health()
                    if method == "_load_manifest_state_from_output":
                        self.assertEqual(health["persistence"]["initialization_state"], "pending")
                    else:
                        self.assertTrue(health["persistence"]["inflight"])
                finally:
                    release.set()
                    await asyncio.wait_for(task, 3)
                    self.assertTrue(await spot_api.wait_for_spot_observation_fact_writes_drain(3))


def observation(seq=1):
    return {"spot_service_instance_id": "synthetic-A", "spot_poll_seq": seq,
            "spot_observation_seq": seq, "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature", "spot_raw_value_text": "500",
            "spot_last_poll_completed_at": "2026-09-09T00:00:00Z", "signalpc": "11"}


class FactQueueTests(unittest.TestCase):
    def test_rollover_deferred_until_owner_stops_and_all_paths_finalize(self):
        for successful in [True, False]:
            with self.subTest(successful=successful), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                fact_path = Path(tmp) / "spot_observation_fact.csv"
                owner = SpotObservationQueue(lambda: SpotObservationFactWriter(fact_path))
                stack.enter_context(patch.object(spot_api.config, "SPOT_OBSERVATION_FACT_ENABLED", True))
                stack.enter_context(patch.object(spot_api, "_spot_observation_queue", owner))
                stack.enter_context(patch.object(spot_api, "_spot_observation_queue_path", fact_path.resolve()))
                owner.enqueue(observation())
                owner._queue.join()
                logger = CSVLoggerService(require_runtime_manifest_state=True)
                paths = [Path(tmp) / "day1.csv", Path(tmp) / "day2.csv"]
                try:
                    for index, path in enumerate(paths, 1):
                        path.write_text(f"sample_seq,spot_observation_key\n{index},synthetic-A:1\n", encoding="utf-8")
                        path.with_suffix(".metadata.json").write_text("{}", encoding="utf-8")
                        logger._current_v2_csv_path = path
                        logger._v2_persisted_sample_seq_by_path[str(path)] = index
                        logger._v2_persisted_at_by_path[str(path)] = "2026-09-09T00:00:00Z"
                        self.assertTrue(logger._close_v2_file(None, closeout_reason="daily-rollover"))
                        pending = json.loads(path.with_suffix(".metadata.json").read_text())
                        self.assertFalse(pending["spot_observation_fact_closeout"]["finalized"])
                    self.assertFalse(logger._runtime_write_failure_observed)
                    self.assertEqual(len(logger._deferred_observation_closeouts), 2)
                    self.assertFalse(logger._finalize_deferred_observation_closeouts(safe=True))
                    owner.enqueue(observation(2))
                finally:
                    self.assertTrue(owner.close(2))
                if not successful:
                    paths[1].with_suffix(".metadata.json").write_text("{invalid", encoding="utf-8")
                self.assertEqual(logger._finalize_deferred_observation_closeouts(safe=True), successful)
                self.assertEqual(len(logger._deferred_observation_closeouts), 0 if successful else 1)
                payload = json.loads(paths[0].with_suffix(".metadata.json").read_text())
                self.assertTrue(payload["csv_closeout"]["finalized"])
                self.assertEqual(payload["spot_observation_fact_manifest"]["row_count"], 2)
                self.assertEqual(payload["spot_observation_fact_manifest"]["sha256"], hashlib.sha256(fact_path.read_bytes()).hexdigest())

    def test_manifest_rejects_live_generation_change_and_external_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            owner = SpotObservationQueue(lambda: SpotObservationFactWriter(path))
            owner.enqueue(observation())
            # Wait for actual completion via the queue's join, not a guessed sleep.
            owner._queue.join()
            def rows():
                owner.enqueue(observation(2))
                owner._queue.join()
                yield {"spot_observation_key": "synthetic-A:2"}
            try:
                with self.assertRaises(FactPersistencePending):
                    owner.manifest_summary(realtime_rows=rows())
            finally:
                self.assertTrue(owner.close(2))
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaises(RuntimeError):
                owner.manifest_summary()

    def read_rows(self, path):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_append_block_immutable_fifo_timeout_then_drain(self):
        started, release = threading.Event(), threading.Event()
        original = SpotObservationFactWriter._append_fact
        def blocked(writer, fact):
            started.set()
            if not release.wait(5):
                raise TimeoutError("test append not released")
            return original(writer, fact)
        with tempfile.TemporaryDirectory() as tmp, patch.object(SpotObservationFactWriter, "_append_fact", blocked):
            path = Path(tmp) / "facts.csv"
            owner = SpotObservationQueue(lambda: SpotObservationFactWriter(path), capacity=2)
            try:
                snapshot = observation()
                self.assertTrue(owner.enqueue(snapshot))
                self.assertTrue(started.wait(2))
                snapshot["signalpc"] = "99"
                self.assertTrue(owner.enqueue(observation(2)))
                self.assertEqual(owner.snapshot()["pending_write_count"], 2)
                self.assertFalse(owner.close(.01))
                self.assertTrue(owner.snapshot()["writer_alive"])
            finally:
                release.set()
                self.assertTrue(owner.close(2))
            rows = self.read_rows(path)
            self.assertEqual([r["spot_poll_seq"] for r in rows], ["1", "2"])
            self.assertEqual(rows[0]["signalpc"], "11")
            self.assertTrue(owner.snapshot()["writes_drained"])

    def test_queue_saturation_is_bounded_and_cannot_be_clean(self):
        started, release = threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as tmp:
            def factory():
                started.set()
                if not release.wait(5):
                    raise TimeoutError("test init not released")
                return SpotObservationFactWriter(Path(tmp) / "facts.csv")
            owner = SpotObservationQueue(factory, capacity=2)
            try:
                self.assertTrue(started.wait(2))
                self.assertTrue(owner.enqueue(observation(1)))
                self.assertTrue(owner.enqueue(observation(2)))
                self.assertFalse(owner.enqueue(observation(3)))
                state = owner.snapshot()
                self.assertEqual(state["queue_depth"], 2)
                self.assertEqual(state["rejected_count"], 1)
                self.assertEqual(state["last_error_code"], "queue_full")
                self.assertFalse(owner.close(.01))
            finally:
                release.set()
                self.assertFalse(owner.close(2))
            self.assertEqual(len(self.read_rows(Path(tmp) / "facts.csv")), 2)

    def test_disk_and_spool_failure_observable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            writer = SpotObservationFactWriter(path)
            self.assertTrue(writer.ensure_initialized())
            original = Path.open
            def failing_open(target, mode="r", *args, **kwargs):
                if "a" in mode and (target == path or target == writer._effective_spool_path()):
                    raise OSError("synthetic disk failure")
                return original(target, mode, *args, **kwargs)
            with patch.object(Path, "open", failing_open):
                owner = SpotObservationQueue(lambda: writer)
                self.assertTrue(owner.enqueue(observation()))
                self.assertFalse(owner.close(2))
            state = owner.snapshot()
            self.assertGreater(state["write_failure_count"], 0)
            self.assertEqual(state["spool_failure_count"], 1)
            self.assertFalse(state["writes_drained"])

    def test_restart_spool_recovery_and_duplicate_current_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            writer = SpotObservationFactWriter(path)
            with patch.object(writer, "_append_fact", side_effect=OSError("synthetic disk failure")):
                writer.write_fact(observation())
            self.assertEqual(writer.spool_pending_count(), 1)
            # Production writer must also deduplicate when recovery occurs inside write_fact.
            recovered = SpotObservationFactWriter(path)
            recovered.write_fact(observation())
            self.assertEqual(len(self.read_rows(path)), 1)
            owner = SpotObservationQueue(lambda: SpotObservationFactWriter(path))
            owner.enqueue(observation())
            owner.enqueue(observation(2))
            self.assertTrue(owner.close(2))
            self.assertEqual([r["spot_poll_seq"] for r in self.read_rows(path)], ["1", "2"])

    def test_initialization_failure_and_empty_close(self):
        def fail():
            raise OSError("synthetic initialization failure")
        owner = SpotObservationQueue(fail)
        self.assertFalse(owner.close(2))
        self.assertEqual(owner.snapshot()["initialization_state"], "failed")
        with tempfile.TemporaryDirectory() as tmp:
            empty = SpotObservationQueue(lambda: SpotObservationFactWriter(Path(tmp) / "facts.csv"))
            self.assertTrue(empty.close(2))
            self.assertEqual(empty.manifest_summary()["row_count"], 0)
