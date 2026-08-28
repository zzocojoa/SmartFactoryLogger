from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class TriggerFixtureServer(ThreadingHTTPServer):
    error_poll_count = 0
    health_completed_at: datetime | None = None
    invalid_error_baseline = False
    slow_health = False
    trigger_after_poll = 3
    lock = threading.Lock()


class TriggerFixtureHandler(BaseHTTPRequestHandler):
    server: TriggerFixtureServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_json(self, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_invalid_json(self) -> None:
        body = b"{"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/observability/errors"):
            if self.server.invalid_error_baseline:
                self._write_invalid_json()
                return
            with self.server.lock:
                self.server.error_poll_count += 1
                poll_count = self.server.error_poll_count
            repeat = 99 if poll_count >= self.server.trigger_after_poll else 98
            error_at = (
                datetime.now(timezone.utc).isoformat()
                if poll_count >= self.server.trigger_after_poll
                else "2026-07-24T00:00:00+00:00"
            )
            self._write_json(
                {
                    "items": [
                        {
                            "time_iso": error_at,
                            "source": "spot_image",
                            "error_type": "ConnectTimeout",
                            "repeat": repeat,
                        }
                    ],
                    "summary": {"queue_size": 1, "repeat_total": repeat},
                }
            )
            return

        if self.path == "/health" and self.server.slow_health:
            time.sleep(6)
            self.server.health_completed_at = datetime.now(timezone.utc)
        self._write_json({"status": "ok"})


def start_server(
    *,
    invalid_error_baseline: bool,
    slow_health: bool,
    trigger_after_poll: int = 3,
) -> tuple[
    TriggerFixtureServer, threading.Thread
]:
    server = TriggerFixtureServer(("127.0.0.1", 0), TriggerFixtureHandler)
    server.invalid_error_baseline = invalid_error_baseline
    server.slow_health = slow_health
    server.trigger_after_poll = trigger_after_poll
    server.error_poll_count = 0
    server.health_completed_at = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_collector(
    *,
    collector: Path,
    monitor: Path,
    api_base: str,
    output_root: Path,
    signal_path: Path,
    duration_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(collector),
            "-ApiBase",
            api_base,
            "-DurationSec",
            str(duration_seconds),
            "-IntervalSec",
            "1",
            "-NormalEndpointIntervalSec",
            "5",
            "-MemoryStateIntervalSec",
            "30",
            "-MemoryDetailsIntervalSec",
            "60",
            "-TimeoutSec",
            "10",
            "-OutputRoot",
            str(output_root),
            "-StopOnNewSpotConnectTimeout",
            "-CaptureStopSignalPath",
            str(signal_path),
            "-TriggerMonitorPath",
            str(monitor),
            "-DetectionLatencyWarningMs",
            "5000",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def assert_success_path(collector: Path, monitor: Path) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="sfl-trigger-success-"))
    output_root = temp_root / "evidence"
    output_root.mkdir()
    signal_path = output_root / "capture_stop_signal.json"
    server, thread = start_server(
        invalid_error_baseline=False,
        slow_health=True,
    )
    try:
        completed = run_collector(
            collector=collector,
            monitor=monitor,
            api_base=f"http://127.0.0.1:{server.server_port}",
            output_root=output_root,
            signal_path=signal_path,
            duration_seconds=15,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "collector integration failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        signal = json.loads(signal_path.read_text(encoding="utf-8-sig"))
        if signal["monitor_mode"] != "dedicated-background-job":
            raise AssertionError("dedicated monitor mode was not recorded")
        if not signal["trigger_detected"]:
            raise AssertionError("new ConnectTimeout did not trigger collection")
        if signal["trigger_detection_latency_exceeded"]:
            raise AssertionError("trigger detection exceeded the threshold")
        if signal["monitor_poll_count"] < 2:
            raise AssertionError("dedicated monitor did not poll independently")

        detected_at = datetime.fromisoformat(signal["trigger_detected_at"])
        health_completed_at = server.health_completed_at
        if health_completed_at is None or detected_at >= health_completed_at:
            raise AssertionError("trigger signal was blocked by the slow endpoint")

        sessions = sorted(output_root.glob("operational_observability_*"))
        summary_path = sessions[0] / "sanitized" / (
            "operational_observability_summary.json"
        )
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        trigger = summary["event_trigger"]
        if trigger["compact_poll_schema"] != "observability-error-poll-compact-v2":
            raise AssertionError("compact polling schema v2 was not recorded")
        if trigger["normal_observer_stop_latency_ms"] < 1000:
            raise AssertionError("fixture did not prove monitor independence")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        shutil.rmtree(temp_root)


def assert_failure_evidence_path(collector: Path, monitor: Path) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="sfl-trigger-failure-"))
    output_root = temp_root / "evidence"
    output_root.mkdir()
    signal_path = output_root / "capture_stop_signal.json"
    server, thread = start_server(
        invalid_error_baseline=True,
        slow_health=False,
    )
    try:
        completed = run_collector(
            collector=collector,
            monitor=monitor,
            api_base=f"http://127.0.0.1:{server.server_port}",
            output_root=output_root,
            signal_path=signal_path,
            duration_seconds=5,
        )
        if completed.returncode == 0:
            raise AssertionError("invalid baseline unexpectedly passed")
        sessions = sorted(output_root.glob("operational_observability_*"))
        if len(sessions) != 1:
            raise AssertionError("failure session was not retained exactly once")
        raw_root = sessions[0] / "raw"
        safe_path = raw_root / "trigger_monitor_failure.json"
        raw_path = raw_root / "trigger_monitor_failure_raw.json"
        if not safe_path.is_file() or not raw_path.is_file():
            raise AssertionError("trigger monitor failure evidence was not retained")

        safe = json.loads(safe_path.read_text(encoding="utf-8-sig"))
        if safe["schema_version"] != (
            "spot-connecttimeout-trigger-monitor-failure-v1"
        ):
            raise AssertionError("safe trigger failure schema mismatch")
        if safe["reason_code"] != "trigger-baseline-read-failed":
            raise AssertionError(
                f"unexpected failure reason: {safe['reason_code']}"
            )
        if safe["error_message_retained"]:
            raise AssertionError("safe failure evidence retained an error message")

        raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        if "could not read its baseline" not in json.dumps(raw):
            raise AssertionError("raw evidence omitted the underlying exception")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        shutil.rmtree(temp_root)


def assert_long_output_path_failure_evidence(collector: Path, monitor: Path) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="sfl-trigger-long-path-"))
    padding_length = max(1, 176 - len(str(temp_root)) - 1)
    output_root = temp_root / ("x" * padding_length)
    output_root.mkdir()
    signal_path = output_root / "capture_stop_signal.json"
    server, thread = start_server(
        invalid_error_baseline=False,
        slow_health=False,
    )
    try:
        completed = run_collector(
            collector=collector,
            monitor=monitor,
            api_base=f"http://127.0.0.1:{server.server_port}",
            output_root=output_root,
            signal_path=signal_path,
            duration_seconds=5,
        )
        if completed.returncode == 0:
            raise AssertionError("unsafe long evidence path unexpectedly passed")
        sessions = sorted(output_root.glob("operational_observability_*"))
        if len(sessions) != 1:
            raise AssertionError("long-path failure session was not retained once")
        raw_root = sessions[0] / "raw"
        safe = json.loads(
            (raw_root / "trigger_monitor_failure.json").read_text(
                encoding="utf-8-sig"
            )
        )
        raw = json.loads(
            (raw_root / "trigger_monitor_failure_raw.json").read_text(
                encoding="utf-8-sig"
            )
        )
        if safe["reason_code"] != "trigger-evidence-path-too-long":
            raise AssertionError(
                f"long path was not classified safely: {safe['reason_code']}"
            )
        if "trigger evidence path exceeds" not in json.dumps(raw).lower():
            raise AssertionError("raw long-path evidence omitted the root cause")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        shutil.rmtree(temp_root)


def assert_observer_completion_handshake(collector: Path, monitor: Path) -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="sfl-trigger-completion-"))
    output_root = temp_root / "evidence"
    output_root.mkdir()
    signal_path = output_root / "capture_stop_signal.json"
    server, thread = start_server(
        invalid_error_baseline=False,
        slow_health=False,
        trigger_after_poll=100_000,
    )
    try:
        completed = run_collector(
            collector=collector,
            monitor=monitor,
            api_base=f"http://127.0.0.1:{server.server_port}",
            output_root=output_root,
            signal_path=signal_path,
            duration_seconds=2,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "observer completion handshake failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        sessions = sorted(output_root.glob("operational_observability_*"))
        if len(sessions) != 1:
            raise AssertionError("completion session was not retained once")
        raw_root = sessions[0] / "raw"
        request_path = raw_root / "trigger_monitor_completion_request.json"
        summary_path = raw_root / "trigger_monitor_summary.json"
        if not request_path.is_file() or not summary_path.is_file():
            raise AssertionError("completion handshake evidence is missing")

        request = json.loads(request_path.read_text(encoding="utf-8-sig"))
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        signal = json.loads(signal_path.read_text(encoding="utf-8-sig"))
        if signal["trigger_detected"]:
            raise AssertionError("no-trigger completion was classified as a trigger")
        if signal["stop_reason"] != "observation-completion-requested":
            raise AssertionError("monitor ignored the observer completion request")
        if not summary["completion_request_observed"]:
            raise AssertionError("monitor omitted completion acknowledgement")
        if summary["completion_request_id"] != request["request_id"]:
            raise AssertionError("completion request identity was not preserved")
        if datetime.fromisoformat(signal["collection_ended_at"]) != datetime.fromisoformat(
            request["observation_ended_at"]
        ):
            raise AssertionError("observation end was replaced by monitor finalization")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        shutil.rmtree(temp_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector-path", required=True, type=Path)
    parser.add_argument("--monitor-path", required=True, type=Path)
    args = parser.parse_args()
    collector = args.collector_path.resolve(strict=True)
    monitor = args.monitor_path.resolve(strict=True)

    assert_success_path(collector, monitor)
    assert_failure_evidence_path(collector, monitor)
    assert_long_output_path_failure_evidence(collector, monitor)
    assert_observer_completion_handshake(collector, monitor)
    print(
        "TRIGGER_COLLECTOR_INTEGRATION_PASS "
        "success_path=true failure_evidence=true long_path_fail_closed=true "
        "completion_handshake=true"
    )


if __name__ == "__main__":
    main()
