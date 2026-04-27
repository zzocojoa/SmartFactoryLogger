import unittest
from unittest.mock import patch

from backend.Observability.memory_service import MemoryService, estimate_size_bytes


class MemoryServiceTests(unittest.TestCase):
    def create_service(self) -> MemoryService:
        service = MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=12,
        )
        service.register_collector(
            "test.collector",
            lambda: {
                "name": "test.collector",
                "kind": "list",
                "exactness": "estimated",
                "bytes": 128,
                "items": 2,
                "note": "sample",
            },
        )
        return service

    def test_estimate_size_handles_cycles(self) -> None:
        payload: dict[str, object] = {}
        payload["self"] = payload

        size = estimate_size_bytes(payload)

        self.assertGreater(size, 0)

    def test_capture_snapshot_returns_summary_and_collectors(self) -> None:
        service = self.create_service()

        state = service.capture_snapshot()
        summary_state = service.get_summary_state()
        details_state = service.get_details_state()

        self.assertIn("summary", state)
        self.assertIn("history", state)
        self.assertIn("backend_growth", state)
        self.assertIn("collector_history", state)
        self.assertIn("sampling", state)
        self.assertIn("capture_latency", state)
        self.assertNotIn("backend_growth", summary_state)
        self.assertNotIn("summary", details_state)
        self.assertEqual(state["backend_top_consumers"][0]["name"], "test.collector")
        self.assertEqual(state["backend_growth"][0]["name"], "test.collector")
        self.assertEqual(state["collector_history"][0]["items"][0]["name"], "test.collector")
        self.assertEqual(state["sampling"]["collector_history_limit"], 12)
        self.assertEqual(details_state["capture_latency"], state["capture_latency"])

    def test_capture_snapshot_records_step_latency(self) -> None:
        service = self.create_service()

        state = service.capture_snapshot()
        latency = state["capture_latency"]
        step_names = [step["name"] for step in latency["steps"]]

        self.assertGreaterEqual(latency["total_ms"], 0.0)
        self.assertEqual(
            step_names,
            [
                "expire_profiler",
                "build_process_sample",
                "run_collectors",
                "apply_snapshot",
                "capture_profiler_diff",
                "build_state",
            ],
        )
        for step in latency["steps"]:
            self.assertGreaterEqual(step["latency_ms"], 0.0)

    def test_collector_history_respects_limit_and_growth_updates(self) -> None:
        size_holder = {"bytes": 64}
        service = MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=2,
        )
        service.register_collector(
            "dynamic.collector",
            lambda: {
                "name": "dynamic.collector",
                "kind": "list",
                "exactness": "estimated",
                "bytes": size_holder["bytes"],
                "items": 1,
                "note": "dynamic",
            },
        )

        service.capture_snapshot()
        size_holder["bytes"] = 256
        state = service.capture_snapshot()
        size_holder["bytes"] = 512
        state = service.capture_snapshot()

        self.assertEqual(len(state["collector_history"]), 2)
        self.assertEqual(state["backend_growth"][0]["name"], "dynamic.collector")
        self.assertEqual(state["backend_growth"][0]["delta_bytes"], 256)

    def test_profiler_start_and_stop_updates_state(self) -> None:
        service = self.create_service()

        start_state = service.start_profiler()
        stop_state = service.stop_profiler()

        self.assertTrue(start_state["enabled"])
        self.assertFalse(start_state["already_running"])
        self.assertGreater(start_state["remaining_ttl_sec"], 0.0)
        self.assertFalse(stop_state["enabled"])
        self.assertIsNone(stop_state["remaining_ttl_sec"])

    def test_profiler_reuses_cached_collectors_between_samples(self) -> None:
        call_count = {"value": 0}
        service = MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=12,
        )
        service.register_collector(
            "cached.collector",
            lambda: {
                "name": "cached.collector",
                "kind": "list",
                "exactness": "estimated",
                "bytes": 64 + (call_count.__setitem__("value", call_count["value"] + 1) or 0),
                "items": 1,
                "note": "cached",
            },
        )

        service.capture_snapshot()
        service.start_profiler()

        first = service._run_collectors(force=False)
        second = service._run_collectors(force=False)

        service.stop_profiler()

        self.assertEqual(call_count["value"], 1)
        self.assertEqual(first, second)

    def test_tracemalloc_diff_serializes(self) -> None:
        service = self.create_service()
        service.start_profiler()
        holder = ["a" * 1000]

        try:
            service.capture_snapshot()
            holder.append("b" * 1000)
            state = service.capture_snapshot()
        finally:
            service.stop_profiler()

        self.assertIn("latest_tracemalloc_diff", state)
        self.assertIsInstance(state["latest_tracemalloc_diff"], list)
        self.assertGreaterEqual(len(holder), 2)

    def test_export_payload_contains_summary_and_details(self) -> None:
        service = self.create_service()

        service.capture_snapshot()
        payload = service.build_export_payload({"frontend": {"ok": True}})

        self.assertIn("summary_state", payload)
        self.assertIn("details_state", payload)
        self.assertIn("frontend", payload)
        self.assertIn("summary", payload["summary_state"])
        self.assertIn("backend_top_consumers", payload["details_state"])

    def test_profiler_auto_stops_after_ttl(self) -> None:
        service = self.create_service()
        service._profiler_max_runtime_sec = 1.0

        with patch("backend.Observability.memory_service.time.time", return_value=100.0):
            service.start_profiler()
        with patch.object(service._logger, "warning") as warning_log:
            with patch.object(service._logger, "info") as info_log:
                with patch("backend.Observability.memory_service.time.time", return_value=102.0):
                    service._expire_profiler_if_needed()

        profiler_state = service.get_profiler_state()

        warning_log.assert_not_called()
        info_log.assert_called_once()
        self.assertFalse(profiler_state["enabled"])
        self.assertEqual(profiler_state["last_stop_reason"], "ttl_expired")
        self.assertTrue(profiler_state["last_stop_expected"])
        self.assertIsNotNone(profiler_state["last_stop_at"])

        stop_state = service.stop_profiler()

        self.assertEqual(stop_state["last_stop_reason"], "ttl_expired")
        self.assertTrue(stop_state["last_stop_expected"])

    def test_profiler_start_while_active_keeps_existing_session(self) -> None:
        service = self.create_service()
        service._profiler_max_runtime_sec = 30.0

        try:
            with patch("backend.Observability.memory_service.time.time", return_value=100.0):
                first = service.start_profiler()
            with patch("backend.Observability.memory_service.time.time", return_value=110.0):
                second = service.start_profiler()
        finally:
            service.stop_profiler()

        self.assertEqual(first["started_at"], second["started_at"])
        self.assertFalse(first["already_running"])
        self.assertTrue(second["already_running"])
        self.assertEqual(second["remaining_ttl_sec"], 20.0)


if __name__ == "__main__":
    unittest.main()
