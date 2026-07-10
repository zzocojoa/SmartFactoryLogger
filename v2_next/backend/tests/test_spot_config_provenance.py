from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from backend.FacilityData.spot_config_provenance import (
    build_spot_configuration_snapshot,
    compute_settings_file_sha256,
)


BUILD_COMMIT = "a" * 40
VERIFIED_AT = "2026-07-11T01:02:03Z"
VERIFIED_BY = "operator-01"


def config_namespace(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "CONFIG_PATH": None,
        "SPOT_IP": "10.1.10.50",
        "SPOT_MODEL_INFO": "SPOT+ AL",
        "SPOT_APP_MODE": "App1: AL E",
        "SPOT_RANGE_MIN_C": 200.0,
        "SPOT_RANGE_MAX_C": 900.0,
        "SPOT_ANALOG_4MA_C": 200.0,
        "SPOT_ANALOG_20MA_C": 800.0,
        "SPOT_LOW_SIGNAL_ALARM_ENABLED": True,
        "SPOT_LOW_SIGNAL_THRESHOLD_PC": 2.0,
        "SPOT_LOW_SIGNAL_COMPARATOR": "lt",
        "SPOT_LOW_SIGNAL_COMPARATOR_VERIFIED": True,
        "SPOT_LOW_SIGNAL_CONFIG_SOURCE": "spot_web_server_alarms_screen",
        "SPOT_CONFIG_OPERATOR_VERIFIED": False,
        "SPOT_CONFIG_VERIFIED_AT": "",
        "SPOT_CONFIG_VERIFIED_BY": "",
        "SPOT_CONFIG_VERIFIED_FINGERPRINT_SHA256": "",
        "SPOT_PEAK_PICKER_ENABLED": False,
        "SPOT_LIMITER_ENABLED": False,
        "SPOT_AVERAGER_ENABLED": False,
        "SPOT_MODEMASTER_ENABLED": False,
        "SPOT_RATIO_RAW_ENABLED": False,
        "SPOT_WINDOW_OBSCURATION_PC": 12.0,
        "SPOT_FOCUS_MM": 6071,
        "SPOT_DIAGNOSTICS_COLLECTION_MODE": "async_fact_only",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def attest(config: SimpleNamespace, fingerprint: str) -> SimpleNamespace:
    values = vars(config).copy()
    values.update(
        {
            "SPOT_CONFIG_OPERATOR_VERIFIED": True,
            "SPOT_CONFIG_VERIFIED_AT": VERIFIED_AT,
            "SPOT_CONFIG_VERIFIED_BY": VERIFIED_BY,
            "SPOT_CONFIG_VERIFIED_FINGERPRINT_SHA256": fingerprint,
        }
    )
    return SimpleNamespace(**values)


class SpotConfigProvenanceTests(unittest.TestCase):
    def snapshot(self, config: SimpleNamespace, **overrides: object) -> dict[str, object]:
        return build_spot_configuration_snapshot(
            config,
            runtime_git_commit=str(overrides.pop("runtime_git_commit", BUILD_COMMIT)),
            captured_at="2026-07-11T01:03:00Z",
            **overrides,
        )

    def test_new_deploy_is_unverified_and_disables_numeric_comparator(self) -> None:
        snapshot = self.snapshot(config_namespace())

        self.assertFalse(snapshot["config_operator_verified"])
        self.assertFalse(snapshot["low_signal_comparator_verified"])
        self.assertEqual(snapshot["config_attestation_status"], "not_requested")
        self.assertFalse(snapshot["config_drift_detected"])

    def test_exact_attestation_enables_operator_and_comparator_verification(self) -> None:
        initial = self.snapshot(config_namespace())
        snapshot = self.snapshot(
            attest(config_namespace(), str(initial["spot_config_fingerprint_sha256"]))
        )

        self.assertTrue(snapshot["config_operator_verified"])
        self.assertTrue(snapshot["low_signal_comparator_verified"])
        self.assertEqual(snapshot["config_attestation_status"], "verified")
        self.assertEqual(snapshot["config_drift_fields"], [])

    def test_spot_ip_change_invalidates_attestation(self) -> None:
        initial = self.snapshot(config_namespace())
        changed = attest(
            config_namespace(SPOT_IP="10.1.10.51"),
            str(initial["spot_config_fingerprint_sha256"]),
        )

        snapshot = self.snapshot(changed)

        self.assertFalse(snapshot["config_operator_verified"])
        self.assertEqual(snapshot["config_attestation_status"], "fingerprint_mismatch")
        self.assertIn("spot_config_fingerprint_sha256", snapshot["config_drift_fields"])

    def test_operational_config_changes_invalidate_attestation(self) -> None:
        initial = self.snapshot(config_namespace())
        fingerprint = str(initial["spot_config_fingerprint_sha256"])
        cases = {
            "SPOT_APP_MODE": "App2: AL E",
            "SPOT_LOW_SIGNAL_THRESHOLD_PC": 3.0,
            "SPOT_LOW_SIGNAL_COMPARATOR": "lte",
            "SPOT_PEAK_PICKER_ENABLED": True,
        }

        for key, value in cases.items():
            with self.subTest(key=key):
                snapshot = self.snapshot(attest(config_namespace(**{key: value}), fingerprint))
                self.assertFalse(snapshot["config_operator_verified"])
                self.assertTrue(snapshot["config_drift_detected"])

    def test_build_commit_change_invalidates_attestation(self) -> None:
        initial = self.snapshot(config_namespace())
        attested = attest(config_namespace(), str(initial["spot_config_fingerprint_sha256"]))

        snapshot = self.snapshot(attested, runtime_git_commit="b" * 40)

        self.assertFalse(snapshot["config_operator_verified"])
        self.assertTrue(snapshot["config_drift_detected"])

    def test_missing_or_invalid_build_commit_cannot_be_attested(self) -> None:
        initial = self.snapshot(config_namespace())
        attested = attest(config_namespace(), str(initial["spot_config_fingerprint_sha256"]))

        snapshot = self.snapshot(attested, runtime_git_commit=None)

        self.assertFalse(snapshot["config_operator_verified"])
        self.assertIn("build_git_commit", snapshot["config_drift_fields"])

    def test_semantic_settings_change_invalidates_but_attestation_keys_do_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "[SPOT]\nappmode = App1: AL E\npassword = placeholder-a\n"
                "config_operator_verified = false\n",
                encoding="utf-8",
            )
            base_config = config_namespace(CONFIG_PATH=config_path)
            initial = self.snapshot(base_config)
            initial_settings_hash = compute_settings_file_sha256(config_path)
            fingerprint = str(initial["spot_config_fingerprint_sha256"])

            config_path.write_text(
                "[SPOT]\nappmode = App1: AL E\npassword = placeholder-b\n"
                "config_operator_verified = true\n"
                f"config_verified_fingerprint_sha256 = {fingerprint}\n",
                encoding="utf-8",
            )
            self.assertEqual(compute_settings_file_sha256(config_path), initial_settings_hash)
            self.assertTrue(self.snapshot(attest(base_config, fingerprint))["config_operator_verified"])

            config_path.write_text(
                "[SPOT]\nappmode = App2: AL E\npassword = placeholder-b\n"
                "config_operator_verified = true\n"
                f"config_verified_fingerprint_sha256 = {fingerprint}\n",
                encoding="utf-8",
            )
            changed = self.snapshot(attest(base_config, fingerprint))
            self.assertFalse(changed["config_operator_verified"])
            self.assertTrue(changed["config_drift_detected"])

    def test_readback_mismatch_and_error_fail_closed(self) -> None:
        initial = self.snapshot(config_namespace())
        attested = attest(config_namespace(), str(initial["spot_config_fingerprint_sha256"]))

        for status in ("mismatch", "error", "partial", "not_attempted"):
            with self.subTest(status=status):
                snapshot = self.snapshot(attested, device_readback_status=status)
                self.assertFalse(snapshot["config_operator_verified"])
                self.assertIn("device_config_readback_status", snapshot["config_drift_fields"])


if __name__ == "__main__":
    unittest.main()
