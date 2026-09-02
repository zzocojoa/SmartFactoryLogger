from __future__ import annotations

import argparse
import asyncio
import io
import json
import math
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.FacilityData.drivers import spot_api  # noqa: E402


def _jpeg_payload() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color=(32, 96, 160)).save(
        buffer,
        format="JPEG",
        quality=85,
    )
    return buffer.getvalue()


class _LoopbackSpotServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, jpeg_payload: bytes, response_delay_sec: float) -> None:
        super().__init__(("127.0.0.1", 0), _LoopbackSpotHandler)
        self.jpeg_payload = jpeg_payload
        self.response_delay_sec = response_delay_sec
        self.request_timestamps: list[float] = []
        self.active_requests = 0
        self.maximum_active_requests = 0
        self.failures = 0
        self.state_lock = threading.Lock()


class _LoopbackSpotHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802
        server = self.server
        assert isinstance(server, _LoopbackSpotServer)
        with server.state_lock:
            server.active_requests += 1
            server.maximum_active_requests = max(
                server.maximum_active_requests,
                server.active_requests,
            )
            server.request_timestamps.append(time.monotonic())
        try:
            if self.path != "/image.jpg":
                with server.state_lock:
                    server.failures += 1
                self.send_error(404)
                return
            if server.response_delay_sec:
                time.sleep(server.response_delay_sec)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(server.jpeg_payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(server.jpeg_payload)
            self.close_connection = True
        finally:
            with server.state_lock:
                server.active_requests -= 1

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


async def _run_benchmark(duration_sec: float, response_delay_sec: float) -> dict[str, Any]:
    server = _LoopbackSpotServer(_jpeg_payload(), response_delay_sec)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    original_config = {
        "SPOT_IP": spot_api.config.SPOT_IP,
        "SPOT_URL": spot_api.config.SPOT_URL,
        "SPOT_INTERNAL_TEMPERATURE_URL": spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL,
        "SPOT_REFRESH_INTERVAL": spot_api.config.SPOT_REFRESH_INTERVAL,
        "SPOT_IMAGE_CAPTURE_ENABLED": spot_api.config.SPOT_IMAGE_CAPTURE_ENABLED,
    }
    response_latencies_ms: list[float] = []
    successful_frames = 0
    failure_messages: list[str] = []
    started_at = time.monotonic()
    diagnostics: dict[str, Any] = {}
    try:
        await spot_api._reset_spot_http_transport_state_for_tests()
        spot_api._reset_spot_image_request_state_for_tests()
        spot_api.config.SPOT_IP = "loopback.invalid"
        spot_api.config.SPOT_URL = ""
        spot_api.config.SPOT_INTERNAL_TEMPERATURE_URL = ""
        spot_api.config.SPOT_REFRESH_INTERVAL = 3.0
        spot_api.config.SPOT_IMAGE_CAPTURE_ENABLED = False
        if not spot_api._start_spot_http_transport():
            raise RuntimeError("guarded SPOT transport did not start")

        live_interval_sec = spot_api.get_spot_live_image_refresh_interval_sec()
        loopback_url = f"http://127.0.0.1:{server.server_port}/image.jpg"
        with patch.object(spot_api, "_resolve_spot_image_url", return_value=loopback_url):
            while time.monotonic() - started_at < duration_sec:
                request_started_at = time.monotonic()
                try:
                    image_bytes, metadata = await spot_api.fetch_image_async(
                        profile="operator_live"
                    )
                    if not image_bytes.startswith(b"\xff\xd8") or metadata["profile"] != "operator_live":
                        raise RuntimeError("invalid benchmark image response")
                    successful_frames += 1
                    response_latencies_ms.append(
                        (time.monotonic() - request_started_at) * 1000.0
                    )
                except Exception as exc:  # pragma: no cover - reported as benchmark failure
                    failure_messages.append(exc.__class__.__name__)
                await asyncio.sleep(live_interval_sec)
            diagnostics = spot_api.get_spot_diagnostics()
    finally:
        elapsed_sec = time.monotonic() - started_at
        try:
            await spot_api._reset_spot_http_transport_state_for_tests()
        finally:
            spot_api._reset_spot_image_request_state_for_tests()
            for name, value in original_config.items():
                setattr(spot_api.config, name, value)
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2.0)

    upstream_count = len(server.request_timestamps)
    effective_live_fps = float(diagnostics.get("live_image_max_fps_effective") or 0.0)
    displayed_fps = successful_frames / elapsed_sec
    upstream_fps = upstream_count / elapsed_sec
    maximum_upstream_count = math.ceil(effective_live_fps * elapsed_sec) + 1
    checks = {
        "duration_met": elapsed_sec >= duration_sec,
        "displayed_fps_met": displayed_fps >= 3.5,
        "upstream_rate_capped": upstream_count <= maximum_upstream_count,
        "zero_client_failures": not failure_messages,
        "zero_server_failures": server.failures == 0,
        "single_upstream_in_flight": server.maximum_active_requests <= 1,
        "source_port_enforcement_active": diagnostics.get("source_port_enforcement_active") is True,
        "zero_pool_exhaustion": diagnostics.get("source_port_pool_exhaustion_count") == 0,
        "zero_reuse_violation": diagnostics.get("source_port_reuse_violation_count") == 0,
        "zero_transport_failures": diagnostics.get("source_port_transport_failure_count") == 0,
        "request_budget_within_target": diagnostics.get("request_budget_within_target") is True,
    }
    return {
        "schema_version": "spot-realtime-image-performance-v1",
        "scope": "localhost-http10-close-guarded-transport",
        "passed": all(checks.values()),
        "duration_sec": round(elapsed_sec, 3),
        "successful_frames": successful_frames,
        "displayed_fps": round(displayed_fps, 4),
        "upstream_requests": upstream_count,
        "upstream_fps": round(upstream_fps, 4),
        "effective_live_fps_cap": round(effective_live_fps, 4),
        "effective_live_interval_ms": round(
            float(diagnostics.get("live_image_refresh_interval_sec_effective") or 0.0) * 1000.0,
            3,
        ),
        "response_latency_ms_p95": (
            round(value, 3)
            if (value := _percentile(response_latencies_ms, 0.95)) is not None
            else None
        ),
        "maximum_upstream_concurrency": server.maximum_active_requests,
        "source_port_policy_version": diagnostics.get("source_port_policy_version"),
        "source_port_pool_capacity": diagnostics.get("source_port_pool_capacity"),
        "source_port_pool_exhaustion_count": diagnostics.get(
            "source_port_pool_exhaustion_count"
        ),
        "source_port_reuse_violation_count": diagnostics.get(
            "source_port_reuse_violation_count"
        ),
        "source_port_transport_failure_count": diagnostics.get(
            "source_port_transport_failure_count"
        ),
        "client_failure_types": sorted(set(failure_messages)),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate budgeted SPOT operator-image performance on localhost."
    )
    parser.add_argument("--duration-sec", type=float, default=10.0)
    parser.add_argument("--response-delay-ms", type=float, default=5.0)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("this guarded source-port performance check requires Windows")
    if not math.isfinite(args.duration_sec) or args.duration_sec < 2.0:
        parser.error("--duration-sec must be at least 2 seconds")
    if not math.isfinite(args.response_delay_ms) or args.response_delay_ms < 0.0:
        parser.error("--response-delay-ms must be non-negative")

    result = asyncio.run(
        _run_benchmark(
            duration_sec=args.duration_sec,
            response_delay_sec=args.response_delay_ms / 1000.0,
        )
    )
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
