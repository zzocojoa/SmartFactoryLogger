from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_SCRIPT = REPO_ROOT / "scripts" / "qa_spot_temperature_v25.ps1"


class SpotTemperatureQaSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if cls.powershell is None:
            raise unittest.SkipTest("Windows PowerShell is required for portable QA tests")

    def _run_qa(self, runtime_version: object, sidecar_version: object) -> dict:
        """Run the shipped script with synthetic health/files, without a validator.

        The missing validator must still fail the overall QA. These tests inspect
        real runtime/sidecar schema decisions, not a duplicated expression or a
        claim that the synthetic CSV has passed full data validation.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scripts = root / "scripts"
            scripts.mkdir()
            script = scripts / QA_SCRIPT.name
            script.write_bytes(QA_SCRIPT.read_bytes())
            data = root / "data"
            data.mkdir()
            csv_name = "Factory_Integrated_Log_v2_schema_test.csv"
            (data / csv_name).write_text("sample_seq\n3\n", encoding="utf-8")
            (data / "spot_observation_fact.csv").write_text("spot_poll_seq\n1\n", encoding="utf-8")
            config = root / "config.ini"
            config.write_text("[SETTINGS]\n", encoding="utf-8")
            instance = "11111111-1111-1111-1111-111111111111"
            commit = "c" * 40
            fingerprint = "a" * 64
            metadata = {
                "schema_metadata": {
                    "active_schema_version": sidecar_version,
                    "csv_v2_temperature_hardening_enabled": True,
                    "logger_service_instance_id": instance,
                    "git_commit": commit,
                },
                "csv_closeout": {
                    "finalized": True, "closeout_reason": "shutdown",
                    "csv_file_name": csv_name, "logger_service_instance_id": instance,
                    "final_persisted_sample_seq": 3,
                },
                "spot_configuration_snapshot": {
                    "build_git_commit": commit,
                    "config_operator_verified": True,
                    "config_attestation_status": "verified",
                    "config_drift_detected": False,
                    "spot_config_fingerprint_sha256": fingerprint,
                    "spot_config_verified_fingerprint_sha256": fingerprint,
                    "low_signal_comparator_configured_verified": True,
                    "low_signal_comparator_verified": True,
                    "device_config_readback_status": "not_supported",
                },
                "spot_observation_fact_manifest": {
                    "enabled": True, "write_failure_count": 0, "spool_pending_count": 0,
                },
            }
            (data / csv_name.replace(".csv", ".metadata.json")).write_text(
                json.dumps(metadata), encoding="utf-8",
            )
            health = {
                "mode": "REAL",
                "spot_temperature": {
                    "diagnostics_available": True, "build_git_commit": commit,
                    "spot_poll_status": "success", "spot_raw_validity": "valid_temperature",
                    "spot_source_freshness": "fresh", "temperature_value_origin": "current_observation",
                    "v2_4_operational": {
                        "enabled": True, "schema_version": runtime_version,
                        "temperature_hardening_enabled": True, "observation_fact_enabled": True,
                        "logger_service_instance_id": instance, "rows_total": 0, "last_sample_seq": 3,
                        "current_v2_csv_file_name": csv_name,
                        "observation_fact_write_failure_count": 0, "observation_fact_link_failure_count": 0,
                        "origin_decision_mismatch_count": 0, "value_age_clock_anomaly_count": 0,
                    },
                },
            }
            health_file = root / "health.json"
            health_file.write_text(json.dumps(health), encoding="utf-8")
            output = root / "qa.json"
            harness = root / "run.ps1"
            harness.write_text(r'''
param($QaScript, $HealthPath, $ConfigPath, $LogPath, $OutputPath)
$ErrorActionPreference = "Stop"
$global:qaFixtureHealth = Get-Content -LiteralPath $HealthPath -Raw | ConvertFrom-Json
$global:qaFixtureCalls = 0
function Invoke-RestMethod {
    param($Uri, $Method, $TimeoutSec)
    if ($Uri -ne "http://127.0.0.1:1/health") { throw "Unexpected external request" }
    $global:qaFixtureCalls++
    $global:qaFixtureHealth.spot_temperature.v2_4_operational.rows_total = $global:qaFixtureCalls
    return $global:qaFixtureHealth
}
& $QaScript -BackendBaseUrl "http://127.0.0.1:1" -ConfigPath $ConfigPath `
    -LogPath $LogPath -OutputPath $OutputPath -ObservationSeconds 5 `
    -SampleIntervalSeconds 5 -SkipStopPrompt
exit $LASTEXITCODE
''', encoding="utf-8-sig")
            result = subprocess.run(
                [self.powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness),
                 str(script), str(health_file), str(config), str(data), str(output)],
                env={**os.environ, "APPDATA": str(root / "appdata"), "SFL_CONFIG_PATH": str(config)},
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue(output.exists(), result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding="utf-8-sig"))
            checks = {entry["name"]: entry for entry in report["checks"]}
            self.assertFalse(checks["Full CSV validator"]["passed"])
            self.assertEqual(checks["Full CSV validator"]["actual"], "validator prerequisites missing")
            self.assertTrue(checks["Current-session metadata sidecar"]["passed"])
            self.assertEqual(config.read_text(encoding="utf-8"), "[SETTINGS]\n")
            return checks

    def test_accepts_supported_runtime_and_matching_sidecar_versions(self) -> None:
        for version in ("2.5.0", "2.5.1", "2.5.2"):
            with self.subTest(version=version):
                checks = self._run_qa(version, version)
                self.assertTrue(checks["CSV schema"]["passed"])
                self.assertTrue(checks["Sidecar schema"]["passed"])
                self.assertEqual([name for name, check in checks.items() if not check["passed"]],
                                 ["Full CSV validator"])

    def test_rejects_missing_unknown_and_non_hardening_schema(self) -> None:
        for version in (None, "", "2.4.1", "2.5.3", "2.5.10", "3.0.0"):
            with self.subTest(version=version):
                checks = self._run_qa(version, version)
                self.assertFalse(checks["CSV schema"]["passed"])
                self.assertFalse(checks["Sidecar schema"]["passed"])

    def test_rejects_sidecar_version_mismatch_in_same_session(self) -> None:
        for runtime, sidecar in (("2.5.1", "2.5.0"), ("2.5.0", "2.5.1"), ("2.5.1", None), ("2.5.2", "2.5.1"), ("2.5.1", "2.5.2")):
            with self.subTest(runtime=runtime, sidecar=sidecar):
                checks = self._run_qa(runtime, sidecar)
                self.assertTrue(checks["CSV schema"]["passed"])
                self.assertFalse(checks["Sidecar schema"]["passed"])


if __name__ == "__main__":
    unittest.main()
