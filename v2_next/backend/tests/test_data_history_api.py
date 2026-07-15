import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import Any

from fastapi.testclient import TestClient

from backend import app as backend_app
from backend.FacilityData.schemas import FactoryData


class DataHistoryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clear_history()

    def tearDown(self) -> None:
        self.clear_history()

    def clear_history(self) -> None:
        backend_app.plc_service.clear_data_history()

    def build_sample(self, time_value: str, spot_value: float, count_value: int) -> FactoryData:
        return FactoryData(
            Time=time_value,
            Status="Running",
            Speed=1.0,
            Press=2.0,
            Count=count_value,
            EndPos=3.0,
            Billet_Length=4.0,
            Spot=spot_value,
            Temp_F=5.0,
            Temp_B=6.0,
            Billet_Temp=7.0,
            Mold1=8.0,
            Mold2=9.0,
            Mold3=10.0,
            Mold4=11.0,
            Mold5=12.0,
            Mold6=13.0,
            At_Temp=14.0,
            At_Pre=15.0,
        )

    def get_history(self, client: TestClient, since_ms: int, limit: int) -> dict[str, Any]:
        response = client.get(f"/api/data/history?since_ms={since_ms}&limit={limit}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, dict)
        self.assertIsInstance(payload["samples"], list)
        return payload

    def test_history_returns_samples_since_last_visible_timestamp(self) -> None:
        base_sec = time.time() - 10.0
        timestamp_ms = [int((base_sec + offset_sec) * 1000) for offset_sec in [1.0, 2.0, 3.0]]
        samples = [
            self.build_sample("2026-05-21T00:00:01.000Z", 10.0, 1),
            self.build_sample("2026-05-21T00:00:02.000Z", 20.0, 2),
            self.build_sample("2026-05-21T00:00:03.000Z", 30.0, 3),
        ]

        backend_app.plc_service._record_history_sample(samples[0], base_sec + 1.0)
        backend_app.plc_service._record_history_sample(samples[1], base_sec + 2.0)
        backend_app.plc_service._record_history_sample(samples[2], base_sec + 3.0)

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response_payload = self.get_history(client, int((base_sec + 1.5) * 1000), 10)
        finally:
            client.close()

        history = response_payload["samples"]
        self.assertEqual([item["timestamp_ms"] for item in history], timestamp_ms[1:])
        self.assertEqual([item["data"]["Spot"] for item in history], [20.0, 30.0])
        self.assertEqual([item["data"]["Count"] for item in history], [2, 3])
        self.assertEqual([item["data"]["timestamp_ms"] for item in history], timestamp_ms[1:])
        self.assertEqual(response_payload["oldest_timestamp_ms"], timestamp_ms[0])
        self.assertEqual(response_payload["newest_timestamp_ms"], timestamp_ms[2])
        self.assertFalse(response_payload["truncated"])

    def test_unknown_api_route_returns_json_404_not_spa_html(self) -> None:
        # Regression: QA found removed MES API paths falling through to the SPA shell.
        # Found by /qa on 2026-05-26.
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.get("/api/mes/status")
        finally:
            client.close()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["content-type"].split(";", 1)[0], "application/json")
        self.assertEqual(response.json(), {"detail": "API route not found"})

    def test_history_read_is_idempotent_and_respects_limit(self) -> None:
        base_sec = time.time() - 10.0
        timestamp_ms = [int((base_sec + offset_sec) * 1000) for offset_sec in [1.0, 2.0, 3.0]]
        samples = [
            self.build_sample("2026-05-21T00:00:01.000Z", 10.0, 1),
            self.build_sample("2026-05-21T00:00:02.000Z", 20.0, 2),
            self.build_sample("2026-05-21T00:00:03.000Z", 30.0, 3),
        ]

        backend_app.plc_service._record_history_sample(samples[0], base_sec + 1.0)
        backend_app.plc_service._record_history_sample(samples[1], base_sec + 2.0)
        backend_app.plc_service._record_history_sample(samples[2], base_sec + 3.0)

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            first_payload = self.get_history(client, 0, 2)
            second_payload = self.get_history(client, 0, 2)
        finally:
            client.close()

        first_history = first_payload["samples"]
        second_history = second_payload["samples"]
        self.assertEqual([item["timestamp_ms"] for item in first_history], timestamp_ms[1:])
        self.assertEqual(second_history, first_history)

    def test_history_marks_truncated_when_since_is_before_retention(self) -> None:
        base_sec = time.time() - 10.0
        timestamp_ms = [int((base_sec + offset_sec) * 1000) for offset_sec in [2.0, 3.0]]
        samples = [
            self.build_sample("2026-05-21T00:00:02.000Z", 20.0, 2),
            self.build_sample("2026-05-21T00:00:03.000Z", 30.0, 3),
        ]

        backend_app.plc_service._record_history_sample(samples[0], base_sec + 2.0)
        backend_app.plc_service._record_history_sample(samples[1], base_sec + 3.0)

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response_payload = self.get_history(client, int((base_sec + 1.0) * 1000), 10)
        finally:
            client.close()

        self.assertTrue(response_payload["truncated"])
        self.assertEqual(response_payload["oldest_timestamp_ms"], timestamp_ms[0])
        self.assertEqual([item["timestamp_ms"] for item in response_payload["samples"]], timestamp_ms)

    def test_history_memory_summary_estimates_from_bounded_sample(self) -> None:
        base_sec = time.time() - 10.0
        for idx in range(4):
            backend_app.plc_service._record_history_sample(
                self.build_sample(f"2026-05-21T00:00:0{idx}.000Z", float(idx), idx),
                base_sec + idx,
            )

        summary = backend_app.plc_service.get_history_memory_summary(sample_size=2)

        self.assertEqual(summary["count"], 4)
        self.assertEqual(summary["max_samples"], backend_app.plc_service.HISTORY_MAX_SAMPLES)
        self.assertEqual(summary["sample_size"], 2)
        self.assertGreater(summary["sampled_bytes"], 0)
        self.assertGreater(summary["estimated_bytes"], 0)
        self.assertGreater(summary["avg_bytes_per_sample"], 0)
        self.assertAlmostEqual(
            summary["fill_ratio"],
            4 / backend_app.plc_service.HISTORY_MAX_SAMPLES,
        )
        self.assertIsNotNone(summary["oldest_timestamp_ms"])
        self.assertIsNotNone(summary["newest_timestamp_ms"])

    def test_history_memory_summary_empty_history_is_zero_safe(self) -> None:
        summary = backend_app.plc_service.get_history_memory_summary(sample_size=128)

        self.assertEqual(summary["count"], 0)
        self.assertEqual(summary["sample_size"], 0)
        self.assertEqual(summary["sampled_bytes"], 0)
        self.assertEqual(summary["estimated_bytes"], 0)
        self.assertEqual(summary["avg_bytes_per_sample"], 0)
        self.assertEqual(summary["fill_ratio"], 0)
        self.assertIsNone(summary["oldest_timestamp_ms"])
        self.assertIsNone(summary["newest_timestamp_ms"])

    def test_plc_history_collector_estimates_without_holding_lock(self) -> None:
        base_sec = time.time() - 10.0
        for idx in range(2):
            backend_app.plc_service._record_history_sample(
                self.build_sample(f"2026-05-21T00:01:0{idx}.000Z", float(idx), idx),
                base_sec + idx,
            )

        def estimate_without_lock(sample_items: list[object]) -> int:
            self.assertFalse(backend_app.plc_service.history_lock.locked())
            self.assertEqual(len(sample_items), 1)
            return 2048

        with patch(
            "backend.FacilityData.service.estimate_size_bytes",
            side_effect=estimate_without_lock,
        ) as estimator:
            summary = backend_app.plc_service.get_history_memory_summary(sample_size=1)

        estimator.assert_called_once()
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["sample_size"], 1)
        self.assertEqual(summary["sampled_bytes"], 2048)
        self.assertEqual(summary["estimated_bytes"], 4096)

    def test_plc_history_collector_is_registered_and_reports_summary(self) -> None:
        backend_app.plc_service._record_history_sample(
            self.build_sample("2026-05-21T00:02:00.000Z", 42.0, 1),
            time.time(),
        )

        self.assertIn("facility.plc_history", backend_app.memory_service._collectors)
        collector_item = backend_app._collect_plc_history()

        self.assertEqual(collector_item["name"], "facility.plc_history")
        self.assertEqual(collector_item["kind"], "deque")
        self.assertEqual(collector_item["items"], 1)
        self.assertGreater(collector_item["bytes"], 0)
        self.assertIn("count=1", collector_item["note"])
        self.assertIn("fill=", collector_item["note"])
        self.assertIn("avg=", collector_item["note"])


class MemoryApiTests(unittest.TestCase):
    def test_memory_gc_endpoint_returns_snapshot(self) -> None:
        expected = {
            "captured_at": "2026-06-27T17:30:00+00:00",
            "latency_ms": 12.5,
            "collected": {"gen0": 1, "gen1": 2, "gen2": 3, "total": 6},
            "before": {"rss_bytes": 100, "uss_bytes": 80, "private_bytes": None},
            "after": {"rss_bytes": 90, "uss_bytes": 70, "private_bytes": None},
            "delta": {"rss_bytes": -10, "uss_bytes": -10, "private_bytes": None},
        }

        with patch.object(backend_app.memory_service, "capture_gc_snapshot", return_value=expected):
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            try:
                response = client.post("/api/memory/gc")
            finally:
                client.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_memory_gc_endpoint_returns_500_on_failure(self) -> None:
        with patch.object(backend_app.memory_service, "capture_gc_snapshot", side_effect=RuntimeError("gc boom")):
            with patch.object(backend_app._logger, "error") as error_log:
                client = TestClient(backend_app.app, raise_server_exceptions=False)
                try:
                    response = client.post("/api/memory/gc")
                finally:
                    client.close()

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "gc boom")
        self.assertTrue(
            any(call.args[0] == "Memory GC snapshot failed: %s" for call in error_log.call_args_list)
        )


class ElectronPreloadContractTests(unittest.TestCase):
    repo_root = Path(__file__).resolve().parents[2]

    def test_main_correlates_and_allowlists_operational_startup_events(self) -> None:
        main_text = (self.repo_root / "main.js").read_text(encoding="utf-8")

        self.assertIn("const startupSessionId =", main_text)
        self.assertIn("session_id: startupSessionId", main_text)
        for event_name in (
            "renderer.backend-health-ready",
            "renderer.first-live-data",
            "renderer.dashboard-operational-timeout",
            "renderer.dashboard-operational-ready",
        ):
            self.assertIn(f"'{event_name}'", main_text)
        self.assertIn("sanitizeStartupPayload(payload)", main_text)
        self.assertIn("MAX_RENDERER_STARTUP_EVENTS_PER_NAME", main_text)

    def test_renderer_wires_existing_health_data_and_paint_responses(self) -> None:
        index_text = (self.repo_root / "frontend" / "src" / "index.tsx").read_text(
            encoding="utf-8"
        )
        app_text = (self.repo_root / "frontend" / "src" / "App.tsx").read_text(
            encoding="utf-8"
        )
        controller_text = (
            self.repo_root
            / "frontend"
            / "src"
            / "domains"
            / "FacilityData"
            / "components"
            / "MetricsDataController.tsx"
        ).read_text(encoding="utf-8")
        telemetry_text = (
            self.repo_root
            / "frontend"
            / "src"
            / "shared"
            / "startup"
            / "startupTelemetry.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("armDashboardOperationalReadyTimeout();", index_text)
        self.assertIn("markBackendHealthReady(health);", app_text)
        self.assertIn("markFirstLiveDataReady(data);", controller_text)
        self.assertIn("timestampMs > 0", telemetry_text)
        self.assertIn("data.Status.trim().toLowerCase() === 'running'", telemetry_text)
        self.assertIn("ready_strategy: 'raf'", telemetry_text)

    def test_package_identity_is_consistent_for_new_nsis(self) -> None:
        root_package = json.loads((self.repo_root / "package.json").read_text(encoding="utf-8"))
        frontend_package = json.loads(
            (self.repo_root / "frontend" / "package.json").read_text(encoding="utf-8")
        )
        backend_version = (self.repo_root / "backend" / "version.py").read_text(
            encoding="utf-8"
        )

        self.assertEqual(root_package["version"], "1.0.14")
        self.assertEqual(frontend_package["version"], "1.0.14")
        self.assertIn('__version__ = "1.0.14"', backend_version)
        self.assertEqual(
            root_package["build"]["nsis"]["artifactName"],
            "smart-factory-logger-v2 Setup ${version}.${ext}",
        )
        packaged_resources = root_package["build"]["extraResources"]
        self.assertIn(
            {
                "from": "scripts/measure_nsis_operational_ready.ps1",
                "to": "qa/measure_nsis_operational_ready.ps1",
            },
            packaged_resources,
        )

    def test_measurement_script_has_strict_failure_and_session_contract(self) -> None:
        script_text = (
            self.repo_root / "scripts" / "measure_nsis_operational_ready.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("Set-StrictMode -Version Latest", script_text)
        self.assertIn("Get-ContaminatingProcesses", script_text)
        self.assertIn('status                  = "CONTAMINATED"', script_text)
        self.assertIn("startup_session_id", script_text)
        self.assertIn("launcher_observed_operational_ready_ms", script_text)
        self.assertIn("renderer.dashboard-operational-timeout", script_text)
        self.assertIn("RECOVERED_AFTER_DIAGNOSTIC_TIMEOUT", script_text)
        self.assertIn("operational_timeout_observed", script_text)
        self.assertNotIn(
            '$TerminalReason = "OPERATIONAL_TIMEOUT"\n                break',
            script_text,
        )
        self.assertIn("Invoke-SelfTest", script_text)

    def test_preload_exposes_only_constrained_electron_bridge(self) -> None:
        preload_text = (self.repo_root / "preload.js").read_text(encoding="utf-8")

        self.assertIn("contextBridge.exposeInMainWorld('smartFactoryElectron'", preload_text)
        self.assertIn("getMemory: () => ipcRenderer.invoke('sfl:get-electron-memory')", preload_text)
        self.assertIn(
            "return ipcRenderer.invoke('sfl:record-startup-event', name, createRendererTimingPayload(payload))",
            preload_text,
        )
        self.assertIn(
            "recordStartupEvent: (name, payload) => recordPreloadStartupEvent(name, payload)",
            preload_text,
        )
        self.assertEqual(preload_text.count("ipcRenderer.invoke"), 2)
        self.assertNotIn("ipcRenderer.send", preload_text)
        self.assertNotIn("ipcRenderer.on", preload_text)
        self.assertNotIn("ipcRenderer.once", preload_text)
        self.assertNotIn("...args", preload_text)

    def test_main_registers_memory_ipc_and_packaged_files_include_preload(self) -> None:
        main_text = (self.repo_root / "main.js").read_text(encoding="utf-8")
        package_payload = json.loads((self.repo_root / "package.json").read_text(encoding="utf-8"))

        self.assertIn("preload: resolvePreloadPath()", main_text)
        self.assertIn("ipcMain.handle('sfl:get-electron-memory'", main_text)
        self.assertIn("ipcMain.handle('sfl:record-startup-event'", main_text)
        self.assertIn("STARTUP_RENDERER_EVENT_NAMES", main_text)
        self.assertIn("preload.js", package_payload["build"]["files"])


if __name__ == "__main__":
    unittest.main()
