import json
import unittest
from unittest.mock import patch

from backend.Observability.memory_service import MemoryService, _calc_slope_bytes_per_min, estimate_size_bytes


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

    def create_empty_service(self) -> MemoryService:
        return MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=12,
        )

    def get_collector(self, items: list[dict[str, object]], name: str) -> dict[str, object]:
        return next(item for item in items if item["name"] == name)

    def apply_memory_snapshot(
        self,
        service: MemoryService,
        captured_at: float,
        *,
        rss_bytes: int | None = None,
        collectors: list[dict[str, object]] | None = None,
    ) -> None:
        sample: dict[str, object] = {"captured_at": captured_at}
        if rss_bytes is not None:
            sample["rss_bytes"] = rss_bytes
        service._apply_snapshot(sample, collectors or [])

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
        collector_item = state["collector_history"][0]["items"][0]
        self.assertIsInstance(collector_item["latency_ms"], float)
        self.assertEqual(collector_item["status"], "ok")
        self.assertIsNotNone(collector_item["last_ok_at"])
        self.assertIsNone(collector_item["last_error_at"])
        self.assertEqual(collector_item["error_count"], 0)
        self.assertFalse(collector_item["stale"])
        self.assertEqual(collector_item["source"], "backend")
        self.assertEqual(collector_item["severity"], "ok")
        self.assertEqual(collector_item["severity_reasons"], [])
        self.assertIsNone(collector_item["budget"])

    def test_budget_severity_warn_and_critical(self) -> None:
        mib = 1024 * 1024
        size_holder = {"bytes": 200 * mib}
        service = self.create_empty_service()
        service.register_collector(
            "facility.plc_history",
            lambda: {
                "name": "facility.plc_history",
                "kind": "deque",
                "exactness": "estimated",
                "bytes": size_holder["bytes"],
                "items": 1,
            },
        )

        state = service.capture_snapshot()
        warn_item = self.get_collector(state["backend_top_consumers"], "facility.plc_history")

        self.assertEqual(warn_item["severity"], "warn")
        self.assertIn("bytes>=", warn_item["severity_reasons"][0])
        self.assertIsNotNone(warn_item["budget"])

        size_holder["bytes"] = 350 * mib
        state = service.capture_snapshot()
        critical_item = self.get_collector(state["backend_top_consumers"], "facility.plc_history")

        self.assertEqual(critical_item["severity"], "critical")
        self.assertIn("bytes>=", critical_item["severity_reasons"][0])

    def test_budget_marks_csv_queue_ratio_critical(self) -> None:
        service = self.create_empty_service()
        service.register_collector(
            "facility.csv_logger",
            lambda: {
                "name": "facility.csv_logger",
                "kind": "queue",
                "exactness": "estimated",
                "bytes": 1024,
                "items": 90,
                "items_capacity": 100,
            },
        )

        state = service.capture_snapshot()
        item = self.get_collector(state["backend_top_consumers"], "facility.csv_logger")

        self.assertEqual(item["severity"], "critical")
        self.assertIn("items_ratio>=0.90", item["severity_reasons"])

    def test_backend_growth_sorts_by_severity_before_delta_and_size(self) -> None:
        mib = 1024 * 1024
        service = self.create_empty_service()
        service.register_collector(
            "ok.collector",
            lambda: {
                "name": "ok.collector",
                "kind": "snapshot",
                "exactness": "estimated",
                "bytes": 400 * mib,
                "items": 1,
            },
        )
        service.register_collector(
            "spot.live_cache",
            lambda: {
                "name": "spot.live_cache",
                "kind": "cache",
                "exactness": "exact",
                "bytes": 12 * mib,
                "items": 1,
            },
        )
        service.register_collector(
            "facility.plc_history",
            lambda: {
                "name": "facility.plc_history",
                "kind": "deque",
                "exactness": "estimated",
                "bytes": 350 * mib,
                "items": 1,
            },
        )

        state = service.capture_snapshot()

        self.assertEqual(
            [item["name"] for item in state["backend_growth"][:3]],
            ["facility.plc_history", "spot.live_cache", "ok.collector"],
        )
        self.assertEqual([item["severity"] for item in state["backend_growth"][:3]], ["critical", "warn", "ok"])

    def test_slope_helper_uses_bytes_per_minute(self) -> None:
        mib = 1024 * 1024

        slope = _calc_slope_bytes_per_min(
            [
                (0.0, 100 * mib),
                (60.0, 110 * mib),
                (120.0, 120 * mib),
                (180.0, 130 * mib),
            ]
        )

        self.assertAlmostEqual(slope, 10 * mib, delta=1.0)

    def test_leak_suspects_empty_until_minimum_sample_count(self) -> None:
        mib = 1024 * 1024
        service = self.create_empty_service()

        for index, value in enumerate([100 * mib, 140 * mib, 180 * mib]):
            self.apply_memory_snapshot(service, index * 60.0, rss_bytes=value)

        self.assertEqual(service.get_details_state()["leak_suspects"], [])

    def test_leak_slope_detects_monotonic_growth(self) -> None:
        mib = 1024 * 1024
        service = self.create_empty_service()

        for index, value in enumerate([100 * mib, 150 * mib, 210 * mib, 280 * mib]):
            self.apply_memory_snapshot(service, index * 60.0, rss_bytes=value)

        suspects = service.get_details_state()["leak_suspects"]

        self.assertEqual(suspects[0]["name"], "process.rss_bytes")
        self.assertEqual(suspects[0]["classification"], "leak_suspect")
        self.assertGreaterEqual(suspects[0]["monotonic_ratio"], 0.75)
        self.assertGreaterEqual(suspects[0]["increase_ratio"], 1.20)

    def test_collector_one_shot_spike_is_not_reported_as_leak_suspect(self) -> None:
        mib = 1024 * 1024
        service = self.create_empty_service()

        for index, value in enumerate([100 * mib, 400 * mib, 105 * mib, 106 * mib]):
            self.apply_memory_snapshot(
                service,
                index * 60.0,
                collectors=[
                    {
                        "name": "facility.plc_history",
                        "kind": "deque",
                        "exactness": "estimated",
                        "bytes": value,
                        "items": 1,
                    }
                ],
            )

        self.assertEqual(service.get_details_state()["leak_suspects"], [])

    def test_gc_snapshot_returns_before_after_delta(self) -> None:
        service = self.create_empty_service()
        before = {
            "captured_at": 100.0,
            "captured_at_iso": "1970-01-01T00:01:40+00:00",
            "rss_bytes": 200,
            "vms_bytes": 1000,
            "uss_bytes": 150,
            "private_bytes": None,
            "thread_count": 1,
            "gc_gen0": 1,
            "gc_gen1": 2,
            "gc_gen2": 3,
        }
        after = {
            "captured_at": 101.0,
            "captured_at_iso": "1970-01-01T00:01:41+00:00",
            "rss_bytes": 180,
            "vms_bytes": 980,
            "uss_bytes": 120,
            "private_bytes": None,
            "thread_count": 1,
            "gc_gen0": 0,
            "gc_gen1": 0,
            "gc_gen2": 0,
        }

        with patch.object(service, "_build_process_sample", side_effect=[before, after]):
            with patch("backend.Observability.memory_service.gc.collect", side_effect=[5, 7, 11]) as collect:
                with patch("backend.Observability.memory_service.time.perf_counter", side_effect=[10.0, 10.125]):
                    snapshot = service.capture_gc_snapshot()

        self.assertEqual([call.args[0] for call in collect.call_args_list], [0, 1, 2])
        self.assertEqual(snapshot["captured_at"], "1970-01-01T00:01:41+00:00")
        self.assertEqual(snapshot["latency_ms"], 125.0)
        self.assertEqual(snapshot["collected"], {"gen0": 5, "gen1": 7, "gen2": 11, "total": 23})
        self.assertEqual(snapshot["delta"]["rss_bytes"], -20)
        self.assertEqual(snapshot["delta"]["uss_bytes"], -30)
        self.assertIsNone(snapshot["delta"]["private_bytes"])
        self.assertEqual(service.get_details_state()["latest_gc_snapshot"], snapshot)

    def test_capture_snapshot_does_not_collect_gc_automatically(self) -> None:
        service = self.create_service()

        with patch("backend.Observability.memory_service.gc.collect") as collect:
            service.capture_snapshot()

        collect.assert_not_called()

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

    def test_memory_collector_exception_does_not_break_sampler(self) -> None:
        service = MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=12,
        )

        def failing_collector() -> dict[str, object]:
            raise RuntimeError("collector boom")

        service.register_collector("bad.collector", failing_collector)

        first_state = service.capture_snapshot()
        second_state = service.capture_snapshot()
        first_item = first_state["collector_history"][0]["items"][0]
        second_item = second_state["collector_history"][1]["items"][0]

        self.assertEqual(first_item["name"], "bad.collector")
        self.assertEqual(first_item["kind"], "error")
        self.assertEqual(first_item["status"], "error")
        self.assertEqual(first_item["bytes"], 0)
        self.assertEqual(first_item["error_count"], 1)
        self.assertEqual(second_item["error_count"], 2)
        self.assertEqual(first_item["note"], "collector failed (RuntimeError)")
        self.assertNotIn("collector boom", first_item["note"])
        self.assertEqual(second_state["backend_top_consumers"][0]["status"], "error")

    def test_collector_slow_status_threshold(self) -> None:
        service = self.create_service()
        service._collector_latency_warn_ms = 0.0

        state = service.capture_snapshot()
        collector_item = state["collector_history"][0]["items"][0]

        self.assertEqual(collector_item["status"], "slow")
        self.assertGreaterEqual(collector_item["latency_ms"], 0.0)
        self.assertEqual(state["backend_growth"][0]["status"], "slow")

    def test_memory_collector_latency_is_recorded(self) -> None:
        service = self.create_service()

        state = service.capture_snapshot()
        collector_item = state["collector_history"][0]["items"][0]

        self.assertEqual(collector_item["name"], "test.collector")
        self.assertIsInstance(collector_item["latency_ms"], float)
        self.assertGreaterEqual(collector_item["latency_ms"], 0.0)
        self.assertEqual(collector_item["status"], "ok")
        self.assertEqual(service.get_collector_runtime_state()["test.collector"]["last_status"], "ok")

    def test_collector_stale_state_is_exposed_after_old_success_fails(self) -> None:
        service = MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=12,
        )
        service._collector_stale_after_sec = 10.0
        should_fail = {"value": False}

        def unstable_collector() -> dict[str, object]:
            if should_fail["value"]:
                raise RuntimeError("stale failure")
            return {
                "name": "unstable.collector",
                "kind": "snapshot",
                "exactness": "estimated",
                "bytes": 128,
                "items": 1,
                "note": "ok",
            }

        service.register_collector("unstable.collector", unstable_collector)

        with patch("backend.Observability.memory_service.time.time", return_value=100.0):
            service.capture_snapshot()

        should_fail["value"] = True
        with patch("backend.Observability.memory_service.time.time", return_value=120.0):
            state = service.capture_snapshot()

        collector_item = state["collector_history"][1]["items"][0]

        self.assertEqual(collector_item["status"], "error")
        self.assertTrue(collector_item["stale"])
        self.assertIsNotNone(collector_item["last_ok_at"])
        self.assertIsNotNone(collector_item["last_error_at"])
        self.assertEqual(collector_item["error_count"], 1)

    def test_slow_collector_reuses_previous_value_without_hard_timeout(self) -> None:
        call_count = {"value": 0}
        service = MemoryService(
            sample_interval_sec=5.0,
            profiler_interval_sec=10.0,
            history_limit=20,
            diff_limit=5,
            collector_history_limit=12,
        )
        service._collector_latency_warn_ms = 0.0
        service._collector_stale_after_sec = 60.0

        def slow_collector() -> dict[str, object]:
            call_count["value"] += 1
            return {
                "name": "slow.collector",
                "kind": "list",
                "exactness": "estimated",
                "bytes": 128 + call_count["value"],
                "items": 1,
                "note": "slow source",
            }

        service.register_collector("slow.collector", slow_collector)

        with patch("backend.Observability.memory_service.time.time", return_value=100.0):
            first = service._run_collectors(force=False)
        with patch("backend.Observability.memory_service.time.time", return_value=101.0):
            second = service._run_collectors(force=False)

        self.assertEqual(call_count["value"], 1)
        self.assertEqual(first[0]["status"], "slow")
        self.assertEqual(second[0]["status"], "stale")
        self.assertFalse(second[0]["stale"])
        self.assertEqual(second[0]["bytes"], first[0]["bytes"])
        self.assertIn("cached previous collector result", second[0]["note"])

    def test_profiler_start_stop_idempotent(self) -> None:
        service = self.create_service()

        start_state = service.start_profiler()
        second_start_state = service.start_profiler()
        stop_state = service.stop_profiler()
        second_stop_state = service.stop_profiler()

        self.assertTrue(start_state["enabled"])
        self.assertFalse(start_state["already_running"])
        self.assertTrue(second_start_state["enabled"])
        self.assertTrue(second_start_state["already_running"])
        self.assertEqual(second_start_state["started_at"], start_state["started_at"])
        self.assertGreater(start_state["remaining_ttl_sec"], 0.0)
        self.assertFalse(stop_state["enabled"])
        self.assertFalse(second_stop_state["enabled"])
        self.assertIsNone(second_stop_state["remaining_ttl_sec"])

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

    def test_export_payload_schema_v2_contains_runtime_and_analysis(self) -> None:
        service = self.create_service()

        service.capture_snapshot()
        payload = service.build_export_payload({"frontend": {"ok": True}})

        self.assertEqual(payload["schema_version"], "memory-export-v2")
        self.assertIn("generated_at", payload)
        self.assertIn("runtime", payload)
        self.assertIn("summary_state", payload)
        self.assertIn("details_state", payload)
        self.assertIn("frontend", payload)
        self.assertIn("analysis", payload)
        self.assertIn("redaction", payload)
        self.assertIn("summary", payload["summary_state"])
        self.assertIn("backend_top_consumers", payload["details_state"])
        self.assertIn("test.collector", payload["analysis"]["budget_results"])
        self.assertIn("collector_runtime_state", payload["analysis"])
        self.assertIn("last_gc_snapshot", payload["analysis"])
        self.assertTrue(payload["redaction"]["applied"])

    def test_export_payload_redacts_sensitive_keys_recursively(self) -> None:
        service = self.create_service()

        service.capture_snapshot()
        payload = service.build_export_payload(
            {
                "password": "plain-password",
                "nested": [
                    {
                        "api_key": "api-key-value",
                        "authorization": "Bearer nested-token",
                        "privateKey": "-----BEGIN PRIVATE KEY-----",
                        "liveImageUrl": "http://10.1.10.50/image.jpg",
                        "safe": "ok",
                    }
                ],
            }
        )
        dumped = json.dumps(payload)

        self.assertNotIn("plain-password", dumped)
        self.assertNotIn("api-key-value", dumped)
        self.assertNotIn("Bearer nested-token", dumped)
        self.assertNotIn("-----BEGIN PRIVATE KEY-----", dumped)
        self.assertNotIn("http://10.1.10.50/image.jpg", dumped)
        self.assertEqual(payload["frontend"]["password"], "[REDACTED]")
        self.assertEqual(payload["frontend"]["nested"][0]["api_key"], "[REDACTED]")
        self.assertEqual(payload["frontend"]["nested"][0]["authorization"], "[REDACTED]")
        self.assertEqual(payload["frontend"]["nested"][0]["privateKey"], "[REDACTED]")
        self.assertEqual(payload["frontend"]["nested"][0]["liveImageUrl"], "[REDACTED]")
        self.assertEqual(payload["frontend"]["nested"][0]["safe"], "ok")
        self.assertGreaterEqual(payload["redaction"]["redacted_fields"], 5)

    def test_export_payload_succeeds_without_frontend_snapshot(self) -> None:
        service = self.create_service()

        service.capture_snapshot()
        payload = service.build_export_payload(None)

        self.assertEqual(payload["schema_version"], "memory-export-v2")
        self.assertEqual(payload["frontend"], {})

    def test_export_payload_includes_electron_snapshot(self) -> None:
        service = self.create_service()
        electron_snapshot = {
            "supported": True,
            "generated_at": "2026-06-27T00:00:00+00:00",
            "metrics": [{"pid": 123, "type": "renderer", "memory": {"workingSetSize": 4096}}],
        }

        service.capture_snapshot()
        payload = service.build_export_payload({"electron": electron_snapshot})

        self.assertEqual(payload["frontend"]["electron"], electron_snapshot)

    def test_export_runtime_argv_is_redacted(self) -> None:
        service = self.create_service()

        service.capture_snapshot()
        with patch(
            "backend.Observability.memory_service.sys.argv",
            ["app.py", "--api-key=supersecret", "--password", "next-secret", "--safe=ok"],
        ):
            payload = service.build_export_payload({})
        dumped = json.dumps(payload)

        self.assertNotIn("supersecret", dumped)
        self.assertNotIn("next-secret", dumped)
        self.assertEqual(
            payload["runtime"]["argv"],
            ["app.py", "--api-key=[REDACTED]", "--password", "[REDACTED]", "--safe=ok"],
        )

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
