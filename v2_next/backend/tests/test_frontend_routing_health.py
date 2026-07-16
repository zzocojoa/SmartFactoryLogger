import asyncio
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as backend_app


class FrontendRoutingHealthTests(unittest.TestCase):
    def write_frontend_dist(self, root: Path) -> Path:
        dist_path = root / "frontend" / "dist"
        assets_path = dist_path / "assets"
        assets_path.mkdir(parents=True)

        (dist_path / "index.html").write_text(
            '<script type="module" src="./assets/index-test.js"></script>'
            '<link rel="stylesheet" href="./assets/index-test.css">',
            encoding="utf-8",
        )
        (dist_path / "manifest.json").write_text("{}", encoding="utf-8")
        (dist_path / "favicon.ico").write_bytes(b"ico")
        (dist_path / "logo192.png").write_bytes(b"png")
        (dist_path / "logo512.png").write_bytes(b"png")
        (assets_path / "index-test.js").write_text("console.log('ok');", encoding="utf-8")
        (assets_path / "index-test.css").write_text("body{}", encoding="utf-8")
        (assets_path / "logo_white.png").write_bytes(b"png")
        (assets_path / "logo_color.png").write_bytes(b"png")

        return dist_path

    def test_nested_deep_link_asset_and_public_files_resolve_to_dist_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dist_path = self.write_frontend_dist(Path(temp_dir))

            nested_asset = backend_app.resolve_nested_frontend_file(
                dist_path,
                "/factory/line/1/assets/index-test.js",
            )
            nested_manifest = backend_app.resolve_nested_frontend_file(
                dist_path,
                "/factory/line/1/manifest.json",
            )

            self.assertEqual(nested_asset, dist_path / "assets" / "index-test.js")
            self.assertEqual(nested_manifest, dist_path / "manifest.json")

    def test_frontend_file_and_api_route_classification_prevents_spa_fallback(self) -> None:
        self.assertTrue(backend_app.is_frontend_file_request("/factory/line/1/assets/index-test.js"))
        self.assertTrue(backend_app.is_frontend_file_request("/factory/line/1/manifest.json"))
        self.assertTrue(backend_app.is_frontend_file_request("/factory/line/1/favicon.ico"))
        self.assertTrue(backend_app.is_api_route_request("/api"))
        self.assertTrue(backend_app.is_api_route_request("/api/unknown"))

        self.assertFalse(backend_app.is_frontend_file_request("/factory/line/1/dashboard"))
        self.assertFalse(backend_app.is_api_route_request("/factory/line/1/dashboard"))

    def test_frontend_status_reports_runtime_class_and_missing_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dist_path = self.write_frontend_dist(root)
            candidate_specs = [
                backend_app.FrontendResolutionCandidateSpec("sidecar", "project", dist_path),
            ]

            ready_status = backend_app.get_frontend_static_status(
                dist_path,
                "frozen",
                "sidecar",
                "project",
                "selected",
                candidate_specs,
            )

            self.assertEqual(ready_status["frontend_runtime_class"], "portable-sidecar")
            self.assertEqual(ready_status["frontend_runtime_warning"], "none")
            self.assertEqual(ready_status["frontend_missing_assets"], [])
            self.assertTrue(ready_status["frontend_static_ready"])

            (dist_path / "assets" / "index-test.js").unlink()

            missing_status = backend_app.get_frontend_static_status(
                dist_path,
                "frozen",
                "sidecar",
                "project",
                "selected",
                candidate_specs,
            )

            self.assertEqual(missing_status["frontend_runtime_warning"], "missing_assets")
            self.assertIn("assets/index-test.js", missing_status["frontend_missing_assets"])
            self.assertFalse(missing_status["frontend_static_ready"])

    def test_frontend_runtime_class_marks_packaged_and_legacy_modes(self) -> None:
        self.assertEqual(backend_app.get_frontend_runtime_class("frozen", "resources"), "packaged-resources")
        self.assertEqual(backend_app.get_frontend_runtime_class("frozen", "meipass"), "legacy-one-file")
        self.assertEqual(backend_app.get_frontend_runtime_warning("meipass", []), "legacy_meipass")

    def test_frontend_file_response_keeps_entry_public_and_unversioned_files_uncached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assets_path = root / "assets"
            assets_path.mkdir()
            paths = [
                root / "index.html",
                root / "manifest.json",
                assets_path / "logo_white.png",
            ]
            for path in paths:
                path.write_text("ok", encoding="utf-8")

            for path in paths:
                response = backend_app.frontend_file_response(path)

                self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
                self.assertEqual(response.headers["Pragma"], "no-cache")
                self.assertEqual(response.headers["Expires"], "0")
                self.assertFalse(backend_app.is_frontend_immutable_asset(path))

    def test_frontend_file_response_uses_immutable_cache_for_hashed_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            asset_path = Path(temp_dir) / "assets" / "OperatorMetadataWidget-DeoraY-r.js"
            asset_path.parent.mkdir()
            asset_path.write_text("console.log('ok');", encoding="utf-8")

            response = backend_app.frontend_file_response(asset_path)

            self.assertTrue(backend_app.is_frontend_immutable_asset(asset_path))
            self.assertEqual(response.headers["Cache-Control"], "public, max-age=31536000, immutable")
            self.assertNotIn("Pragma", response.headers)
            self.assertNotIn("Expires", response.headers)

    def test_frontend_file_request_status_distinguishes_missing_assets_from_not_found(self) -> None:
        missing_assets_status = {
            "frontend_assets_exists": False,
            "frontend_dist_exists": True,
        }
        ready_status = {
            "frontend_assets_exists": True,
            "frontend_dist_exists": True,
        }

        self.assertEqual(
            backend_app.get_frontend_file_request_status(missing_assets_status, "/nested/assets/missing.js"),
            503,
        )
        self.assertEqual(
            backend_app.get_frontend_file_request_status(ready_status, "/nested/assets/missing.js"),
            404,
        )

    def test_backend_address_discovery_does_not_block_readiness_caller(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocking_address_discovery() -> None:
            entered.set()
            release.wait(timeout=2.0)

        try:
            with patch.object(backend_app, "_log_backend_access_urls", blocking_address_discovery):
                started = time.perf_counter()
                worker = backend_app._start_backend_access_log_thread()
                elapsed = time.perf_counter() - started

            self.assertTrue(entered.wait(timeout=1.0))
            self.assertLess(elapsed, 0.5)
            self.assertTrue(worker.daemon)
            self.assertEqual(worker.name, "BackendAccessUrlLogger")
        finally:
            release.set()
            if "worker" in locals():
                worker.join(timeout=1.0)

    def test_slow_health_response_logs_stage_timings(self) -> None:
        with (
            patch.object(backend_app.plc_service, "get_health", return_value={"running": True}),
            patch.object(backend_app, "get_runtime_info", return_value={"runtime_kind": "test"}),
            patch.object(
                backend_app,
                "get_frontend_static_status",
                return_value={"frontend_static_ready": True},
            ),
            patch.object(
                backend_app.time,
                "perf_counter",
                side_effect=[10.0, 10.6, 10.7, 10.8],
            ),
            patch.object(backend_app._logger, "warning") as warning,
        ):
            payload = backend_app.build_health_payload()

        self.assertTrue(payload["running"])
        self.assertEqual(payload["runtime_kind"], "test")
        self.assertTrue(payload["frontend_static_ready"])
        warning.assert_called_once()
        self.assertEqual(warning.call_args.args[0], "[Health] Slow response")
        log_fields = warning.call_args.kwargs["extra"]
        self.assertEqual(log_fields["health_total_ms"], 800.0)
        self.assertEqual(log_fields["health_plc_service_ms"], 600.0)
        self.assertEqual(log_fields["health_runtime_info_ms"], 100.0)
        self.assertEqual(log_fields["health_frontend_static_ms"], 100.0)

    def test_health_payload_runs_outside_the_event_loop_thread(self) -> None:
        event_loop_thread_id = threading.get_ident()
        health_thread_ids: list[int] = []

        def build_health() -> dict[str, bool]:
            health_thread_ids.append(threading.get_ident())
            return {"running": True}

        with patch.object(backend_app, "build_health_payload", side_effect=build_health):
            payload = asyncio.run(backend_app.health())

        self.assertTrue(payload["running"])
        self.assertEqual(len(health_thread_ids), 1)
        self.assertNotEqual(health_thread_ids[0], event_loop_thread_id)


if __name__ == "__main__":
    unittest.main()
