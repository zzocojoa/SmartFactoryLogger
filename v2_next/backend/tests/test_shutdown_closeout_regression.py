import asyncio
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import tracemalloc
import unittest
from unittest.mock import AsyncMock, patch

from backend import app as backend_app
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.spot_image_fact import build_spot_image_fact_manifest
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_COLUMNS,
    SpotObservationFactWriter,
    summarize_spot_observation_fact,
)


class ShutdownCloseoutRegressionTests(unittest.TestCase):
    repo_root = Path(__file__).resolve().parents[2]

    def test_large_observation_manifest_is_streamed_with_bounded_memory(self) -> None:
        row_total = 200_000
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writeheader()
                for sequence in range(1, row_total + 1):
                    writer.writerow(
                        {
                            "spot_observation_fact_schema_version": "1.3.0",
                            "spot_observation_key": f"service-1:{sequence}",
                            "spot_service_instance_id": "service-1",
                            "spot_poll_seq": sequence,
                            "spot_observation_seq": sequence,
                            "diagnostics_capture_status": "async_complete",
                            "diagnostics_binding_status": "same_poll",
                            "diagnostics_missing_fields": "[]",
                            "spot_diagnostic_evidence_codes": '["signal_below_threshold"]',
                            "evidence_provenance_json": '{"signal_below_threshold":"signalpc"}',
                            "signalpc": "1.5",
                        }
                    )

            expected_sha256 = hashlib.sha256(fact_path.read_bytes()).hexdigest()
            realtime_rows = [
                {"spot_observation_key": "service-1:1"},
                {"spot_observation_key": f"service-1:{row_total}"},
                {"spot_observation_key": "service-1:missing"},
            ]

            tracemalloc.start()
            try:
                summary = summarize_spot_observation_fact(
                    fact_path=fact_path,
                    realtime_rows=realtime_rows,
                )
                _, peak_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

        self.assertEqual(summary["row_count"], row_total)
        self.assertEqual(summary["distinct_observation_key_count"], row_total)
        self.assertEqual(summary["poll_seq_gap_count"], 0)
        self.assertEqual(summary["sha256"], expected_sha256)
        self.assertEqual(summary["link_coverage"]["linked_rows"], 2)
        self.assertEqual(summary["link_coverage"]["missing_fact_key_rows"], 1)
        self.assertLess(
            peak_bytes,
            64 * 1024 * 1024,
            f"observation manifest peak memory was {peak_bytes} bytes",
        )

    def test_observation_manifest_fails_closed_when_temporary_sqlite_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_text("header\nrow\n", encoding="utf-8")
            expected_sha256 = hashlib.sha256(fact_path.read_bytes()).hexdigest()

            with patch(
                "backend.FacilityData.spot_observation_fact.sqlite3.connect",
                side_effect=sqlite3.OperationalError("temporary storage unavailable"),
            ):
                summary = summarize_spot_observation_fact(fact_path=fact_path)

        self.assertEqual(summary["row_count"], 0)
        self.assertEqual(summary["distinct_observation_key_count"], 0)
        self.assertEqual(summary["sha256"], expected_sha256)

    def test_closeout_header_initialization_does_not_index_historical_fact_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_text(
                "\ufeff" + ",".join(SPOT_OBSERVATION_FACT_COLUMNS) + "\n",
                encoding="utf-8",
            )
            service = CSVLoggerService()

            with patch.object(
                SpotObservationFactWriter,
                "_load_seen_keys_from_output",
                side_effect=AssertionError("closeout indexed historical observation keys"),
            ) as load_seen_keys:
                failure_count = service._ensure_spot_observation_fact_file(
                    fact_path,
                    enabled=True,
                )

        self.assertEqual(failure_count, 0)
        load_seen_keys.assert_not_called()

    def test_image_manifest_hash_does_not_load_the_entire_fact_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            fact_path.write_text("header\nrow-1\nrow-2\n", encoding="utf-8")

            with patch.object(Path, "read_bytes", side_effect=AssertionError("unbounded read")):
                manifest = build_spot_image_fact_manifest(
                    log_path=log_path,
                    capture_root=log_path / "spot_images",
                    enabled=True,
                    mode="all",
                )

        self.assertEqual(manifest["row_count"], 2)
        self.assertRegex(str(manifest["sha256"]), r"^[0-9a-f]{64}$")

    def test_control_shutdown_subprocess_quiesces_spot_before_logger_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker_path = Path(temp_dir) / "shutdown-order.txt"
            script = textwrap.dedent(
                """
                import asyncio
                from pathlib import Path
                import sys

                from backend import app as backend_app

                marker_path = Path(sys.argv[1])

                def mark(stage):
                    with marker_path.open("a", encoding="utf-8") as handle:
                        handle.write(stage + "\\n")
                    return True

                async def stop_spot_poll_loop():
                    mark("spot_poll_loop")
                    return True

                class LoggerStub:
                    def stop(self, *, timeout_sec=None, finalize_spot_image_manifest=True):
                        return mark("logger_service")

                backend_app.spot_control.stop_spot_poll_loop = stop_spot_poll_loop
                backend_app.spot_control.stop_spot_image_capture_for_shutdown = (
                    lambda *, timeout_sec=None: mark("spot_image_capture")
                )
                backend_app.plc_service.stop = lambda: mark("plc_service")
                backend_app.logger_service = LoggerStub()
                backend_app.comm_metrics_logger_service.stop = lambda: mark("comm_metrics")
                backend_app.memory_service.stop = lambda: mark("memory_service")
                backend_app.config_sync_agent.stop = lambda: mark("config_sync")
                backend_app.config_watch_service.stop = lambda: mark("config_watch")

                asyncio.run(backend_app._run_control_shutdown("subprocess-regression"))
                """
            )

            completed = subprocess.run(
                [sys.executable, "-c", script, str(marker_path)],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            order = marker_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertGreaterEqual(len(order), 3)
        self.assertEqual(order[0], "spot_poll_loop")
        self.assertLess(order.index("spot_poll_loop"), order.index("logger_service"))

    def test_control_shutdown_spot_failure_still_runs_closeout_and_exits_with_failure(self) -> None:
        async def exercise() -> None:
            downstream_status = {
                key: True
                for key in backend_app._CONTROL_SHUTDOWN_REQUIRED_STATUS_KEYS
                if key != "spot_poll_loop_stopped"
            }
            with (
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_poll_loop",
                    new=AsyncMock(side_effect=RuntimeError("SPOT stop failed")),
                ),
                patch.object(
                    backend_app,
                    "_stop_services_for_control_shutdown",
                    return_value=downstream_status,
                ) as closeout,
                patch.object(backend_app.os, "_exit") as process_exit,
            ):
                await backend_app._run_control_shutdown("spot-stop-regression")

            closeout.assert_called_once_with()
            process_exit.assert_called_once_with(2)

        asyncio.run(exercise())

    def test_control_shutdown_transport_timeout_exits_with_failure(self) -> None:
        async def exercise() -> None:
            downstream_status = {
                key: True
                for key in backend_app._CONTROL_SHUTDOWN_REQUIRED_STATUS_KEYS
                if key != "spot_poll_loop_stopped"
            }
            with (
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_poll_loop",
                    new=AsyncMock(return_value=False),
                ),
                patch.object(
                    backend_app,
                    "_stop_services_for_control_shutdown",
                    return_value=downstream_status,
                ) as closeout,
                patch.object(backend_app.os, "_exit") as process_exit,
            ):
                await backend_app._run_control_shutdown("transport-timeout-regression")

            closeout.assert_called_once_with()
            process_exit.assert_called_once_with(2)

        asyncio.run(exercise())

    def test_control_shutdown_schedule_rejects_duplicate_requests(self) -> None:
        async def exercise() -> None:
            release = asyncio.Event()
            calls: list[str] = []

            async def hold_shutdown(reason: str) -> None:
                calls.append(reason)
                await release.wait()

            backend_app._control_shutdown_tasks.clear()
            with patch.object(backend_app, "_run_control_shutdown", side_effect=hold_shutdown):
                backend_app._schedule_control_shutdown("first")
                backend_app._schedule_control_shutdown("duplicate")
                await asyncio.sleep(0)
                self.assertEqual(calls, ["first"])
                self.assertEqual(len(backend_app._control_shutdown_tasks), 1)
                release.set()
                await asyncio.gather(*backend_app._control_shutdown_tasks)
                await asyncio.sleep(0)

            self.assertFalse(backend_app._control_shutdown_tasks)

        asyncio.run(exercise())

    def test_portable_qa_operator_shutdown_checkpoint_behaves_fail_closed(self) -> None:
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is unavailable")

        qa_path = self.repo_root / "scripts" / "qa_spot_temperature_v25.ps1"
        qa_script = qa_path.read_text(encoding="utf-8")

        self.assertNotIn("/api/control/shutdown", qa_script)
        self.assertNotIn("X-SFL-Control-Token", qa_script)
        self.assertLess(
            qa_script.index("Invoke-OperatorShutdownCheckpoint"),
            qa_script.index('[4/5] Checking the finalized CSV and config attestation'),
        )

        exercise = r"""
$source = Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8
$beginMarker = "# BEGIN QA SHUTDOWN HELPERS"
$endMarker = "# END QA SHUTDOWN HELPERS"
$begin = $source.IndexOf($beginMarker)
$end = $source.IndexOf($endMarker)
if ($begin -lt 0 -or $end -lt $begin) {
    throw "QA shutdown helper markers were not found."
}
$helperSource = $source.Substring(
    $begin,
    ($end + $endMarker.Length) - $begin
)
Invoke-Expression $helperSource

$script:successProbeCount = 0
$script:promptCount = 0
$success = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 2 `
    -PollIntervalSeconds 0 `
    -ReachabilityProbe {
        $script:successProbeCount += 1
        return $script:successProbeCount -lt 2
    } `
    -PromptAction { $script:promptCount += 1 } `
    -SleepAction { param([int]$Seconds) }

$alreadyStopped = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 2 `
    -PollIntervalSeconds 0 `
    -ReachabilityProbe { return $false } `
    -PromptAction { throw "prompt must not run" } `
    -SleepAction { param([int]$Seconds) }

$timeout = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 0 `
    -PollIntervalSeconds 0 `
    -ReachabilityProbe { return $true } `
    -PromptAction { $script:promptCount += 1 } `
    -SleepAction { param([int]$Seconds) }

[PSCustomObject]@{
    success_stopped = [bool]$success.backend_stopped
    success_operator_requested = [bool]$success.operator_shutdown_requested
    already_stopped = [bool]$alreadyStopped.backend_stopped
    already_operator_requested = [bool]$alreadyStopped.operator_shutdown_requested
    timeout_stopped = [bool]$timeout.backend_stopped
    timeout_operator_requested = [bool]$timeout.operator_shutdown_requested
    prompt_count = $script:promptCount
} | ConvertTo-Json -Compress
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exercise_path = Path(temp_dir) / "exercise-qa-shutdown.ps1"
            exercise_path.write_text(exercise, encoding="utf-8-sig")
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(exercise_path),
                str(qa_path),
            ]
            if sys.platform == "win32":
                command = ["cmd.exe", "/d", "/c", *command]
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertTrue(result["success_stopped"])
        self.assertTrue(result["success_operator_requested"])
        self.assertTrue(result["already_stopped"])
        self.assertFalse(result["already_operator_requested"])
        self.assertFalse(result["timeout_stopped"])
        self.assertTrue(result["timeout_operator_requested"])
        self.assertEqual(result["prompt_count"], 2)


if __name__ == "__main__":
    unittest.main()
