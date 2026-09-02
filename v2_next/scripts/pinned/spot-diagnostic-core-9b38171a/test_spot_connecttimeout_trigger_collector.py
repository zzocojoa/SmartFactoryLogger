from __future__ import annotations

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

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/observability/errors"):
            with self.server.lock:
                self.server.error_poll_count += 1
                poll_count = self.server.error_poll_count
            repeat = 99 if poll_count >= 3 else 98
            error_at = (
                datetime.now(timezone.utc).isoformat()
                if poll_count >= 3
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
                    "summary": {
                        "queue_size": 1,
                        "repeat_total": repeat,
                    },
                }
            )
            return

        if self.path == "/health":
            time.sleep(6)
            self.server.health_completed_at = datetime.now(timezone.utc)
            self._write_json({"status": "ok"})
            return

        self._write_json({})


def main() -> None:
    repository_root = Path(__file__).resolve().parent.parent
    collector = repository_root / "scripts" / "collect_operational_observability.ps1"
    monitor = repository_root / "scripts" / "monitor-spot-connecttimeout-trigger.ps1"
    temp_root = Path(tempfile.mkdtemp(prefix="sfl-trigger-integration-"))
    output_root = temp_root / "evidence"
    output_root.mkdir()
    signal_path = output_root / "capture_stop_signal.json"

    server = TriggerFixtureServer(("127.0.0.1", 0), TriggerFixtureHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        api_base = f"http://127.0.0.1:{server.server_port}"
        completed = subprocess.run(
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
                "15",
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
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
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
            raise AssertionError("trigger detection exceeded the five-second threshold")
        if signal["monitor_poll_count"] < 2:
            raise AssertionError(
                "dedicated monitor did not poll independently: "
                f"{signal['monitor_poll_count']}"
            )

        detected_at = datetime.fromisoformat(signal["trigger_detected_at"])
        health_completed_at = server.health_completed_at
        if health_completed_at is None or detected_at >= health_completed_at:
            raise AssertionError(
                "the trigger signal was blocked by the slow normal endpoint"
            )

        sessions = sorted(output_root.glob("operational_observability_*"))
        if len(sessions) != 1:
            raise AssertionError("collector session output was not created exactly once")
        summary_path = (
            sessions[0]
            / "sanitized"
            / "operational_observability_summary.json"
        )
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        trigger = summary["event_trigger"]
        if trigger["compact_poll_schema"] != "observability-error-poll-compact-v2":
            raise AssertionError("compact polling schema v2 was not recorded")
        if trigger["monitor_mode"] != "dedicated-background-job":
            raise AssertionError("sanitized summary omitted the monitor mode")
        if trigger["normal_observer_stop_latency_ms"] < 1000:
            raise AssertionError(
                "fixture did not prove independence from the slow normal endpoint"
            )

        print(
            "TRIGGER_COLLECTOR_INTEGRATION_PASS "
            f"polls={signal['monitor_poll_count']} "
            f"detection_latency_ms={signal['trigger_detection_latency_ms']} "
            f"normal_observer_stop_latency_ms="
            f"{trigger['normal_observer_stop_latency_ms']}"
        )

        deadline_output_root = temp_root / "deadline-evidence"
        deadline_output_root.mkdir()
        deadline_signal_path = deadline_output_root / "capture_stop_signal.json"
        fake_monitor = temp_root / "completion-request-monitor.ps1"
        fake_monitor.write_text(
            r'''param(
    [string]$ApiBase,
    [int]$DurationSec,
    [int]$PollIntervalMs,
    [int]$RequestTimeoutMs,
    [string]$RawRoot,
    [string]$CaptureStopSignalPath,
    [string]$CompletionRequestPath,
    [int]$DetectionLatencyWarningMs
)
$ErrorActionPreference = 'Stop'
$deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $deadline) {
    if (-not [string]::IsNullOrWhiteSpace($CompletionRequestPath) -and
        (Test-Path -LiteralPath $CompletionRequestPath -PathType Leaf)) {
        break
    }
    Start-Sleep -Milliseconds 100
}
if ([string]::IsNullOrWhiteSpace($CompletionRequestPath) -or
    -not (Test-Path -LiteralPath $CompletionRequestPath -PathType Leaf)) {
    throw 'The observer completion request was not received.'
}
$request = Get-Content -LiteralPath $CompletionRequestPath -Raw | ConvertFrom-Json
$endedAt = [DateTimeOffset]::Now
$body = '{"items":[],"summary":{"queue_size":0,"repeat_total":0}}'
$envelope = [ordered]@{
    sample = 0
    endpoint = 'observability_errors'
    path = '/api/observability/errors?limit=200'
    collected_at = $endedAt.ToString('o')
    status_code = 200
    ok = $true
    error = $null
    body = $body
}
$envelope | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $RawRoot 'trigger_baseline_observability_errors.json') -Encoding utf8
$envelope | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $RawRoot 'trigger_final_observability_errors.json') -Encoding utf8
'' | Set-Content -LiteralPath (Join-Path $RawRoot 'trigger_observability_errors_compact.jsonl') -Encoding utf8
[ordered]@{
    schema_version = 'spot-trigger-monitor-error-events-raw-v1'
    generated_at = $endedAt.ToString('o')
    error_count = 0
    recovered_error_count = 0
    unrecovered_error_count = 0
    events = @()
} | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $RawRoot 'trigger_monitor_error_events_raw.json') -Encoding utf8
[ordered]@{
    schema_version = 'spot-connecttimeout-trigger-monitor-v1'
    stop_reason = 'observation-completion-requested'
    trigger_detected = $false
    trigger_detection_latency_ms = $null
    trigger_detection_latency_warning_ms = $DetectionLatencyWarningMs
    trigger_detection_quality = 'not-applicable'
    trigger_detection_latency_exceeded = $false
    monitor_poll_count = 0
    monitor_error_count = 0
    monitor_recovered_error_count = 0
    monitor_unrecovered_error_count = 0
    monitor_max_consecutive_error_count = 0
    monitor_integrity_policy = 'recovered-errors-within-detection-threshold-are-complete'
    monitor_integrity_status = 'complete-no-errors'
    change_snapshot_count = 0
    full_snapshot_count = 2
    poll_gap_ms_p95 = $null
    poll_gap_ms_max = $null
    request_elapsed_ms_p95 = $null
    request_elapsed_ms_max = $null
    completion_request_observed = $true
    completion_request_id = $request.request_id
    completion_request_observed_at = $endedAt.ToString('o')
} | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath (Join-Path $RawRoot 'trigger_monitor_summary.json') -Encoding utf8
[ordered]@{
    schema_version = 'spot-connecttimeout-capture-stop-v1'
    stop_reason = 'observation-completion-requested'
    trigger_detected = $false
    trigger_source = $null
    trigger_error_type = $null
    trigger_detected_at = $null
    trigger_error_at = $null
    trigger_detection_latency_ms = $null
    trigger_detection_latency_warning_ms = $DetectionLatencyWarningMs
    trigger_detection_quality = 'not-applicable'
    trigger_detection_latency_exceeded = $false
    baseline_item_count = 0
    baseline_repeat_total = 0
    observed_item_count = 0
    observed_repeat_total = 0
    repeat_delta = 0
    monitor_mode = 'dedicated-background-job'
    monitor_poll_interval_ms = $PollIntervalMs
    monitor_poll_count = 0
    monitor_error_count = 0
    monitor_recovered_error_count = 0
    monitor_unrecovered_error_count = 0
    monitor_max_consecutive_error_count = 0
    monitor_integrity_policy = 'recovered-errors-within-detection-threshold-are-complete'
    monitor_integrity_status = 'complete-no-errors'
    monitor_poll_gap_ms_max = $null
    collection_ended_at = $endedAt.ToString('o')
    completion_request_id = $request.request_id
} | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $CaptureStopSignalPath -Encoding utf8
''',
            encoding="utf-8",
        )

        deadline_completed = subprocess.run(
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
                "1",
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
                str(deadline_output_root),
                "-StopOnNewSpotConnectTimeout",
                "-CaptureStopSignalPath",
                str(deadline_signal_path),
                "-TriggerMonitorPath",
                str(fake_monitor),
                "-DetectionLatencyWarningMs",
                "5000",
            ],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if deadline_completed.returncode != 0:
            raise AssertionError(
                "observer completion handshake failed\n"
                f"stdout:\n{deadline_completed.stdout}\n"
                f"stderr:\n{deadline_completed.stderr}"
            )
        deadline_sessions = sorted(
            deadline_output_root.glob("operational_observability_*")
        )
        if len(deadline_sessions) != 1:
            raise AssertionError("deadline session output was not created exactly once")
        completion_request = (
            deadline_sessions[0]
            / "raw"
            / "trigger_monitor_completion_request.json"
        )
        if not completion_request.is_file():
            raise AssertionError("observer completion request evidence is missing")
        deadline_signal = json.loads(
            deadline_signal_path.read_text(encoding="utf-8-sig")
        )
        if deadline_signal["stop_reason"] != "observation-completion-requested":
            raise AssertionError("monitor did not stop from the observer request")

        monitor_raw_root = temp_root / "parent-request-monitor"
        monitor_raw_root.mkdir()
        monitor_signal_path = monitor_raw_root / "capture_stop_signal.json"
        parent_completion_path = monitor_raw_root / "completion_request.json"
        parent_request_id = "parent-boundary-regression"
        parent_completion_path.write_text(
            json.dumps(
                {
                    "schema_version": "spot-trigger-monitor-completion-request-v1",
                    "request_id": parent_request_id,
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "observation_ended_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "observation-deadline-reached",
                    "request_source": "parent-authoritative-observation-boundary",
                }
            ),
            encoding="utf-8",
        )
        with server.lock:
            server.error_poll_count = 0
        parent_monitor_completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(monitor),
                "-ApiBase",
                api_base,
                "-DurationSec",
                "10",
                "-PollIntervalMs",
                "1000",
                "-RequestTimeoutMs",
                "1000",
                "-RawRoot",
                str(monitor_raw_root),
                "-CaptureStopSignalPath",
                str(monitor_signal_path),
                "-CompletionRequestPath",
                str(parent_completion_path),
                "-DetectionLatencyWarningMs",
                "5000",
            ],
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if parent_monitor_completed.returncode != 0:
            raise AssertionError(
                "parent-authoritative completion monitor failed\n"
                f"stdout:\n{parent_monitor_completed.stdout}\n"
                f"stderr:\n{parent_monitor_completed.stderr}"
            )
        parent_monitor_signal = json.loads(
            monitor_signal_path.read_text(encoding="utf-8-sig")
        )
        with server.lock:
            parent_monitor_server_polls = server.error_poll_count
        if (
            parent_monitor_signal["completion_request_id"] != parent_request_id
            or parent_monitor_signal["completion_request_source"]
            != "parent-authoritative-observation-boundary"
            or parent_monitor_signal["monitor_poll_count"] != 1
            or parent_monitor_server_polls != 2
        ):
            raise AssertionError(
                "parent completion request did not receive one final error poll"
            )

        print(
            "TRIGGER_MONITOR_COMPLETION_HANDSHAKE_PASS "
            f"request={completion_request.name} "
            f"parent_final_poll={parent_monitor_signal['monitor_poll_count']}"
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        shutil.rmtree(temp_root)


if __name__ == "__main__":
    main()
