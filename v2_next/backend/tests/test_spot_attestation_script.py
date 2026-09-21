from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTESTATION_SCRIPT = REPO_ROOT / "scripts" / "apply_spot_temperature_v25_attestation.ps1"


class SpotAttestationScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if cls.powershell is None:
            raise unittest.SkipTest("PowerShell is required for the attestation script tests")

    def _run_attestation(
        self,
        *,
        drift_fields: list[str],
        attestation_status: str,
        readback_status: str = "not_supported",
        schema_version: object = "2.5.0",
        hardening_enabled: bool = True,
        comparator_verified: bool = True,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.ini"
            config_path.write_text(
                "[SPOT]\n"
                "low_signal_comparator = lt\n"
                "low_signal_comparator_verified = true\n"
                "config_operator_verified = true\n"
                "config_verified_at = 2026-07-12T00:00:00Z\n"
                "config_verified_by = previous_operator\n"
                f"config_verified_fingerprint_sha256 = {'b' * 64}\n",
                encoding="utf-8",
            )
            metadata_path = root / "Factory_Integrated_Log_v2_test.metadata.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "schema_metadata": {
                            "active_schema_version": schema_version,
                            "csv_v2_temperature_hardening_enabled": hardening_enabled,
                        },
                        "spot_configuration_snapshot": {
                            "spot_config_fingerprint_sha256": "a" * 64,
                            "build_git_commit": "c" * 40,
                            "config_drift_detected": bool(drift_fields),
                            "config_drift_fields": drift_fields,
                            "config_attestation_status": attestation_status,
                            "device_config_readback_status": readback_status,
                            "low_signal_comparator_configured_verified": comparator_verified,
                            "spot_model_info": "SPOT+ AL",
                            "spot_app_mode": "App1: AL E",
                            "low_signal_alarm_enabled": False,
                            "low_signal_threshold_pc": 2.0,
                            "low_signal_comparator": "lt",
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(self.powershell),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ATTESTATION_SCRIPT),
                    "-BackendBaseUrl",
                    "http://127.0.0.1:1",
                    "-ConfigPath",
                    str(config_path),
                    "-MetadataPath",
                    str(metadata_path),
                    "-OperatorId",
                    "qa_operator",
                    "-Confirm",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            updated_config = config_path.read_text(encoding="utf-8")
            return result, updated_config

    def test_allows_explicit_fingerprint_only_reattestation(self) -> None:
        result, updated_config = self._run_attestation(
            drift_fields=["spot_config_fingerprint_sha256"],
            attestation_status="fingerprint_mismatch",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ATTESTATION APPLIED", result.stdout)
        self.assertIn("config_operator_verified = true", updated_config)
        self.assertIn(f"config_verified_fingerprint_sha256 = {'a' * 64}", updated_config)

    def test_blocks_device_readback_drift(self) -> None:
        result, _updated_config = self._run_attestation(
            drift_fields=["spot_config_fingerprint_sha256", "device_config_readback_status"],
            attestation_status="device_readback_blocked",
            readback_status="mismatch",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("blocking config drift", result.stdout + result.stderr)

    def test_accepts_schema_251_without_changing_comparator(self) -> None:
        result, updated_config = self._run_attestation(
            drift_fields=["spot_config_fingerprint_sha256"],
            attestation_status="fingerprint_mismatch",
            schema_version="2.5.1",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ATTESTATION APPLIED", result.stdout)
        self.assertIn(f"config_verified_fingerprint_sha256 = {'a' * 64}", updated_config)
        self.assertIn("low_signal_comparator = lt", updated_config)

    def test_accepts_schema_252_without_changing_comparator(self) -> None:
        result, updated_config = self._run_attestation(drift_fields=["spot_config_fingerprint_sha256"],
            attestation_status="fingerprint_mismatch", schema_version="2.5.2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ATTESTATION APPLIED", result.stdout)
        self.assertIn("low_signal_comparator = lt", updated_config)

    def test_rejects_unsupported_schema_without_writing_config(self) -> None:
        for version in (None, "", "2.4.1", "2.5.3", "2.5.10", "3.0.0"):
            with self.subTest(version=version):
                result, config = self._run_attestation(
                    drift_fields=[], attestation_status="not_requested", schema_version=version,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("schema", result.stdout + result.stderr)
                self.assertIn("config_verified_by = previous_operator", config)
                self.assertIn(f"config_verified_fingerprint_sha256 = {'b' * 64}", config)

    def test_schema_251_preserves_hardening_comparator_and_drift_gates(self) -> None:
        cases = (
            ({"hardening_enabled": False}, "hardening"),
            ({"comparator_verified": False}, "comparator"),
            ({"drift_fields": ["device_config_readback_status"],
              "readback_status": "mismatch"}, "blocking config drift"),
        )
        for version, (overrides, message) in ((version, case) for version in ["2.5.1", "2.5.2"] for case in cases):
            with self.subTest(gate=message, version=version):
                options = {"drift_fields": [], "attestation_status": "not_requested",
                           "schema_version": version, **overrides}
                result, config = self._run_attestation(**options)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertIn("config_verified_by = previous_operator", config)
                self.assertIn(f"config_verified_fingerprint_sha256 = {'b' * 64}", config)


if __name__ == "__main__":
    unittest.main()
