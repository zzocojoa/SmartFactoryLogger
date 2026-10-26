import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
import threading
import time
import unittest
from unittest.mock import patch

import httpx
from starlette.requests import Request
from starlette.responses import Response

from backend import app as backend_app
from backend.Observability.health_timing import PROBE_HEADER, TIMING_HEADER, start_health_timing


PROBE = "0123456789abcdef" * 2
POINTS = ("route_enter", "submitted", "worker_enter", "plc_done", "runtime_done",
          "frontend_done", "worker_exit", "route_resume")
BODY = {"running": True, "runtime_kind": "test", "frontend_static_ready": True}


def request(probe=PROBE, *, peer="127.0.0.1", headers=()):
    pairs = list(headers)
    if probe is not None:
        pairs.append((PROBE_HEADER.lower().encode(), probe.encode()))
    return Request({"type": "http", "headers": pairs,
                    "client": (peer, 54321) if peer is not None else None})


class HealthTimingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.plc = self.patches.enter_context(patch.object(
            backend_app.plc_service, "get_health", return_value={"running": True}))
        self.runtime = self.patches.enter_context(patch.object(
            backend_app, "get_runtime_info", return_value={"runtime_kind": "test"}))
        self.frontend = self.patches.enter_context(patch.object(
            backend_app, "get_frontend_static_status", return_value={"frontend_static_ready": True}))

    def read_timing(self, response, probe=PROBE):
        raw = response.headers[TIMING_HEADER]
        self.assertLess(len(raw.encode("ascii")), 4096)
        timing = json.loads(raw)
        self.assertEqual(timing["v"], 2)
        self.assertEqual(timing["probe_id"], probe)
        self.assertEqual(timing["clock"], "perf_counter_ns")
        self.assertEqual(timing["pid"], os.getpid())
        self.assertEqual(timing["loop_tid"], threading.get_native_id())
        self.assertGreater(timing["worker_tid"], 0)
        self.assertNotEqual(timing["worker_tid"], timing["loop_tid"])
        points = timing["checkpoints"]
        self.assertEqual(tuple(points), POINTS)
        self.assertTrue(all(type(value) is int and value > 0 for value in points.values()))
        self.assertEqual(list(points.values()), sorted(points.values()))
        self.assertEqual(set(timing["native"]), {"loop_begin", "worker_begin", "worker_end", "loop_end"})
        return timing

    async def test_http_opt_in_preserves_body_and_trace_id(self):
        for peer in ("127.0.0.1", "::1"):
            transport = httpx.ASGITransport(app=backend_app.app, client=(peer, 54321))
            async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
                normal = await client.get("/health")
                measured = await client.get("/health", headers={PROBE_HEADER: PROBE})
            self.assertEqual(normal.status_code, 200)
            self.assertEqual(measured.status_code, 200)
            self.assertEqual(normal.json(), BODY)
            self.assertEqual(measured.json(), BODY)
            self.assertNotIn(TIMING_HEADER, normal.headers)
            self.assertIn("X-Trace-ID", measured.headers)
            self.read_timing(measured)

    async def test_invalid_or_nonlocal_probes_keep_ordinary_path(self):
        cases = [request(None), request("x"), request(PROBE.upper()), request(PROBE + "\n"),
                 request(peer=None), request(peer="localhost"), request(peer="192.0.2.1"),
                 request(headers=[(b"x-sfl-health-probe", PROBE.encode())]),
                 request(headers=[(b"origin", b"http://localhost")]),
                 request(headers=[(b"referer", b"")])]
        for incoming in cases:
            with self.subTest(scope=incoming.scope):
                response = Response()
                with patch.object(backend_app, "build_health_payload", return_value=BODY) as builder:
                    self.assertEqual(await backend_app.health(incoming, response), BODY)
                builder.assert_called_once_with()
                self.assertNotIn(TIMING_HEADER, response.headers)
                self.assertIsNone(start_health_timing(incoming))

    async def test_worker_stage_delays_are_in_the_corresponding_interval(self):
        for service, before, after, value in (
            (self.plc, "worker_enter", "plc_done", {"running": True}),
            (self.runtime, "plc_done", "runtime_done", {"runtime_kind": "test"}),
            (self.frontend, "runtime_done", "frontend_done", {"frontend_static_ready": True}),
        ):
            def delayed(*_args):
                time.sleep(.06)
                return value
            service.side_effect = delayed
            try:
                response = Response()
                self.assertEqual(await backend_app.health(request(), response), BODY)
                points = self.read_timing(response)["checkpoints"]
                self.assertGreaterEqual(points[after] - points[before], 50_000_000)
            finally:
                service.side_effect = None

    async def test_executor_backlog_is_separate_from_worker_execution(self):
        loop = asyncio.get_running_loop()
        submitted = asyncio.Event()

        class ObservedExecutor(ThreadPoolExecutor):
            def submit(self, *args, **kwargs):
                future = super().submit(*args, **kwargs)
                submitted.set()
                return future

        loop.set_default_executor(ObservedExecutor(max_workers=1))
        entered, release = threading.Event(), threading.Event()

        def occupy_worker():
            entered.set()
            if not release.wait(3):
                raise TimeoutError("test worker was not released")

        occupied = loop.run_in_executor(None, occupy_worker)
        try:
            deadline = loop.time() + 2
            while not entered.is_set() and loop.time() < deadline:
                await asyncio.sleep(.001)
            self.assertTrue(entered.is_set())
            response = Response()
            submitted.clear()
            # Scheduling the route is distinct from submitting its worker.
            loop.call_soon(time.sleep, .03)
            pending = asyncio.create_task(backend_app.health(request(), response))
            await asyncio.wait_for(submitted.wait(), 2)
            await asyncio.sleep(.06)
            self.assertFalse(pending.done())
            self.assertFalse(self.plc.called)
            release.set()
            self.assertEqual(await asyncio.wait_for(pending, 2), BODY)
            points = self.read_timing(response)["checkpoints"]
            self.assertGreaterEqual(points["worker_enter"] - points["submitted"], 50_000_000,
                                    "executor backlog was shorter than fixture hold")
        finally:
            release.set()
            await occupied

    async def test_event_loop_delay_after_worker_is_measured_as_resume_delay(self):
        loop = asyncio.get_running_loop()
        original = backend_app.HealthTiming.mark
        blocked = threading.Event()

        def block_loop():
            blocked.set()
            time.sleep(.06)

        def mark(timing, name):
            original(timing, name)
            if name == "worker_exit":
                loop.call_soon_threadsafe(block_loop)
                if not blocked.wait(2):
                    raise TimeoutError("loop callback was not entered")

        with patch.object(backend_app.HealthTiming, "mark", mark):
            response = Response()
            self.assertEqual(await backend_app.health(request(), response), BODY)
        points = self.read_timing(response)["checkpoints"]
        self.assertGreaterEqual(points["route_resume"] - points["worker_exit"], 50_000_000)

    async def test_concurrent_requests_do_not_share_probe_state(self):
        barrier = threading.Barrier(2)

        def concurrent_plc():
            barrier.wait(2)
            return {"running": True}

        self.plc.side_effect = concurrent_plc
        responses = [Response(), Response()]
        ids = ["a" * 32, "b" * 32]
        payloads = await asyncio.gather(*[
            backend_app.health(request(probe), response) for probe, response in zip(ids, responses)
        ])
        self.assertEqual(payloads, [BODY, BODY])
        timings = [self.read_timing(response, probe) for response, probe in zip(responses, ids)]
        self.assertNotEqual(timings[0]["worker_tid"], timings[1]["worker_tid"])
        self.assertNotEqual(timings[0]["checkpoints"], timings[1]["checkpoints"])

    async def test_failed_builder_does_not_emit_complete_timing(self):
        self.plc.side_effect = RuntimeError("health test failure")
        response = Response()
        with self.assertRaisesRegex(RuntimeError, "health test failure"):
            await backend_app.health(request(), response)
        self.assertNotIn(TIMING_HEADER, response.headers)
        self.plc.side_effect = None
        self.assertEqual(await backend_app.health(request(), response), BODY)
        self.read_timing(response)

    async def test_native_failure_preserves_health_and_marks_anchors_unavailable(self):
        with patch("backend.Observability.health_clock._api", side_effect=OSError("private provider text")):
            response = Response()
            self.assertEqual(await backend_app.health(request(), response), BODY)
            timing = self.read_timing(response)
        self.assertTrue(all(value == {"status": "UNAVAILABLE", "error_type": "OSError"}
                            for value in timing["native"].values()))
        self.assertNotIn("private provider", response.headers[TIMING_HEADER])

    async def test_cancelled_request_does_not_emit_timing_when_worker_finishes(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        def wait_plc():
            entered.set()
            try:
                if not release.wait(3):
                    raise TimeoutError("test worker was not released")
                return {"running": True}
            finally:
                finished.set()

        self.plc.side_effect = wait_plc
        response = Response()
        pending = asyncio.create_task(backend_app.health(request(), response))
        try:
            deadline = asyncio.get_running_loop().time() + 2
            while not entered.is_set() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(.001)
            self.assertTrue(entered.is_set())
            pending.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await pending
        finally:
            release.set()
        await asyncio.to_thread(finished.wait, 2)
        self.assertTrue(finished.is_set())
        self.assertNotIn(TIMING_HEADER, response.headers)


if __name__ == "__main__":
    unittest.main()
