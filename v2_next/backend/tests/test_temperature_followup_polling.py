"""Real polling loops with independent synthetic wall/monotonic clocks and HTTP I/O."""
import asyncio
import csv
import struct
import tempfile
import threading
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.FacilityData.drivers import real_plc, spot_api
from backend.FacilityData.spot_observation_fact import SpotObservationFactWriter
from backend.FacilityData.spot_observation_queue import SpotObservationQueue
from backend.tests.test_temperature_followup import MelsecSocket


class IndependentClock:
    def __init__(self):
        self.wall = datetime(2026, 9, 21, 23, 59, 59, tzinfo=timezone.utc).timestamp()
        self.mono = 1000.0

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def perf_counter(self):
        return self.mono

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


class AsyncioSleepBoundary:
    def __init__(self, sleep):
        self.sleep = sleep

    def __getattr__(self, name):
        return getattr(asyncio, name)


class TemperaturePollingTests(unittest.IsolatedAsyncioTestCase):
    async def run_loop(self, jumps, *, duration=.2, cancel_during_sleep=False):
        clock = IndependentClock()
        starts, completions, sleeps, utc_completions = [], [], [], []
        sleeping = asyncio.Event()
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            fact_path = Path(tmp) / "facts.csv"
            owner = SpotObservationQueue(lambda: SpotObservationFactWriter(fact_path))
            pending_diagnostics = asyncio.get_running_loop().create_future()
            # Preserve global runtime state; the independent diagnostics sweep is
            # already in-flight, exercising its real suppression gate.
            settings = {"SPOT_URL": "http://spot.test/output?p=temperature",
                        "SPOT_INTERNAL_TEMPERATURE_URL": "", "SPOT_REFRESH_INTERVAL": 1.0,
                        "SPOT_OBSERVATION_FACT_ENABLED": True, "LOG_PATH": tmp}
            for name, value in settings.items():
                stack.enter_context(patch.object(spot_api.config, name, value))
            state = {"time": clock, "_spot_poll_running": False, "_spot_poll_seq": 0,
                     "_spot_observation_seq": 0, "_spot_temperature_snapshot": None,
                     "_spot_last_valid_value_at": None, "_spot_last_valid_value_monotonic": None,
                     "_spot_temperature_cache_suppressed_until_valid": False,
                     "_temperature_cache": dict(spot_api._temperature_cache),
                     "_spot_diagnostics_task": pending_diagnostics,
                     "_spot_diagnostics_inflight_suppressed_count": 0,
                     "_spot_observation_queue": owner, "_spot_observation_queue_path": fact_path.resolve()}
            for name, value in state.items():
                stack.enter_context(patch.object(spot_api, name, value))
            stack.enter_context(patch.object(spot_api, "_active_spot_http_transport", return_value=None))

            async def request(request):
                starts.append(clock.mono)
                clock.advance(duration)
                clock.wall += jumps[len(starts) - 1]
                completions.append(clock.mono)
                utc_completions.append(clock.wall)
                if len(starts) == len(jumps):
                    spot_api._spot_poll_running = False
                return httpx.Response(200, text="500", request=request)

            async def sleep(seconds):
                sleeps.append(seconds)
                self.assertGreaterEqual(seconds, 0)
                sleeping.set()
                if cancel_during_sleep:
                    await asyncio.Event().wait()
                clock.advance(seconds)
                await asyncio.sleep(0)

            stack.enter_context(patch.object(spot_api, "asyncio", AsyncioSleepBoundary(sleep)))
            async with httpx.AsyncClient(transport=httpx.MockTransport(request)) as client:
                stack.enter_context(patch.object(spot_api, "_get_http_client", return_value=client))
                task = asyncio.create_task(spot_api._spot_poll_loop())
                try:
                    if cancel_during_sleep:
                        await asyncio.wait_for(sleeping.wait(), 2)
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        self.assertTrue(task.done())
                        self.assertFalse(spot_api._spot_poll_running)
                    else:
                        await asyncio.wait_for(task, 2)
                finally:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    pending_diagnostics.cancel()
                    self.assertTrue(await asyncio.to_thread(owner.close, 2))
            with fact_path.open(encoding="utf-8-sig", newline="") as stream:
                facts = list(csv.DictReader(stream))
            self.assertEqual([int(row["spot_poll_seq"]) for row in facts], list(range(1, len(starts) + 1)))
            self.assertEqual(len({row["spot_observation_key"] for row in facts}), len(starts))
            for row, stamp in zip(facts, utc_completions):
                actual = datetime.fromisoformat(row["spot_last_poll_completed_at"].replace("Z", "+00:00"))
                self.assertAlmostEqual(actual.timestamp(), stamp, places=3)
            self.assertTrue(owner.snapshot()["writes_drained"])
            return starts, completions, sleeps

    async def test_wall_backward_forward_repeated_preserve_real_poll_cadence(self):
        for jumps in [[-60, 0, 0, 0], [60, 0, 0, 0], [-60, 60, -60, 60]]:
            with self.subTest(jumps=jumps):
                starts, _, sleeps = await self.run_loop(jumps)
                for before, after in zip(starts, starts[1:]):
                    self.assertAlmostEqual(after - before, 1.0)
                self.assertTrue(all(0 < delay <= 1.0 for delay in sleeps), sleeps)

    async def test_http_overrun_reschedules_without_catchup_burst(self):
        starts, completions, sleeps = await self.run_loop([0, 60, -60], duration=2.5)
        self.assertTrue(all(delay >= 1 for delay in sleeps))
        for complete, following in zip(completions, starts[1:]):
            self.assertGreaterEqual(following - complete, 1.0)

    async def test_cancel_during_actual_loop_sleep_drains_fact_owner(self):
        starts, _, _ = await self.run_loop([0, 0], cancel_during_sleep=True)
        self.assertEqual(len(starts), 1)

    async def test_normal_utc_midnight_timestamps_and_identity_survive(self):
        starts, _, _ = await self.run_loop([0, 0, 0])
        self.assertEqual(len(starts), 3)


class WorkerClockTests(unittest.TestCase):
    def test_all_shared_helper_callers_use_monotonic_and_epoch_io_deadline(self):
        for worker in ["_ext_worker_loop", "_ls_worker_loop", "_spot_worker_loop"]:
            for jump in [-60, 60]:
                with self.subTest(worker=worker, jump=jump), ExitStack() as stack:
                    clock = IndependentClock()
                    driver = real_plc.RealPLCDriver()
                    driver.ext_merge_blocks = False
                    driver.sock_ext = MelsecSocket()
                    waits = []
                    stack.enter_context(patch.object(real_plc, "time", clock))
                    stack.enter_context(patch.object(real_plc.select, "select", side_effect=lambda r, w, x, t: (r, w, [])))
                    stack.enter_context(patch.object(real_plc.config, "POSITION_READ_ENABLED", False))
                    stack.enter_context(patch.object(real_plc.config, "SPOT_REFRESH_INTERVAL", 1.0))
                    stack.enter_context(patch.object(real_plc.config, "INTERVAL_SEC", 1.0))
                    stack.enter_context(patch.object(real_plc.socket, "socket", side_effect=AssertionError("real socket forbidden")))
                    def wait(seconds):
                        waits.append(seconds)
                        clock.advance(seconds)
                        if len(waits) == 2:
                            driver._worker_stop.set()

                    # Move wall clock after I/O but before the real sleep helper.
                    # Snapshot publication is wrapped, not replaced.
                    original_update = driver._update_ext_snapshot

                    def publish(payload, captured_at):
                        original_update(payload, captured_at)
                        clock.wall += jump

                    stack.enter_context(patch.object(driver._worker_stop, "wait", side_effect=wait))
                    stack.enter_context(patch.object(driver, "_update_ext_snapshot", side_effect=publish))
                    if worker == "_ls_worker_loop":
                        # Real LS read/packet/parser/deadline path, synthetic socket only.
                        class LSSocket:
                            def settimeout(self, timeout):
                                if not 0 < timeout <= driver.ls_timeout:
                                    raise AssertionError("invalid epoch I/O timeout")
                            def sendall(self, request):
                                count = len(real_plc.config.LS_TARGETS)
                                body = bytes(8) + struct.pack("<H", count) + struct.pack("<HH", 2, 100) * count
                                self.response = bytes(16) + struct.pack("<H", len(body)) + bytes(2) + body
                            def recv(self, size):
                                result, self.response = self.response[:size], self.response[size:]
                                return result
                        driver.sock_ls = LSSocket()
                        original_ls_update = driver._update_ls_snapshot
                        def publish_ls(payload, captured_at):
                            original_ls_update(payload, captured_at)
                            clock.wall += jump
                        stack.enter_context(patch.object(driver, "_update_ls_snapshot", side_effect=publish_ls))
                    if worker == "_spot_worker_loop":
                        def diagnostics():
                            clock.wall += jump
                            return {"spot_poll_status": "success", "temperature_value_origin": "current_observation",
                                    "spot_temperature_effective_c": 500}
                        stack.enter_context(patch.object(real_plc, "get_cached_spot_temp", return_value=500))
                        stack.enter_context(patch.object(real_plc, "get_spot_diagnostics", side_effect=diagnostics))
                    # Hard bound guards a broken helper that never waits on forward jumps.
                    checks = 0
                    actual_is_set = driver._worker_stop.is_set
                    def is_set():
                        nonlocal checks
                        checks += 1
                        return checks > 3 or actual_is_set()
                    stack.enter_context(patch.object(driver._worker_stop, "is_set", side_effect=is_set))
                    getattr(driver, worker)()
                    self.assertEqual(waits, [1.0, 1.0])
                    if worker == "_ext_worker_loop":
                        self.assertEqual(driver.ext_read_failures, 0)  # real epoch deadline never expires from domain mismatch
                        self.assertEqual(driver._ext_snapshot["Count"], 20)
                    elif worker == "_ls_worker_loop":
                        self.assertEqual(driver.ls_read_failures, 0)
                        self.assertEqual(driver._ls_snapshot["Mold1"], 100)

    def test_worker_stop_event_interrupts_real_wait_and_thread_exits(self):
        driver = real_plc.RealPLCDriver()
        waiting = threading.Event()
        original_wait = driver._worker_stop.wait
        def wait(seconds):
            waiting.set()
            return original_wait(seconds)
        with patch.object(real_plc.config, "SPOT_REFRESH_INTERVAL", 60), \
                patch.object(real_plc, "get_cached_spot_temp", return_value=500), \
                patch.object(real_plc, "get_spot_diagnostics", return_value={"spot_temperature_effective_c": 500}), \
                patch.object(driver._worker_stop, "wait", side_effect=wait):
            worker = threading.Thread(target=driver._spot_worker_loop)
            worker.start()
            try:
                self.assertTrue(waiting.wait(1))
            finally:
                driver._worker_stop.set()
                worker.join(1)
            self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
