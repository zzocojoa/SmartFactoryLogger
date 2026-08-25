from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPTS = REPOSITORY / "scripts"
CONTROLLER = SCRIPTS / "invoke-spot-realtime-image-canary-120m.ps1"
VERIFIER = SCRIPTS / "verify-spot-realtime-image-canary-kit.ps1"
BUILDER = SCRIPTS / "build-spot-realtime-image-canary-kit.ps1"
LAUNCHER = SCRIPTS / "run-spot-realtime-image-canary-120m-as-admin.cmd"
GUIDE = (
    REPOSITORY
    / "docs"
    / "04-deploy"
    / "spot-realtime-image-v1021-canary-120m.md"
)


@unittest.skipUnless(os.name == "nt", "canary tooling is Windows-only")
class SpotRealtimeImageCanaryKitTests(unittest.TestCase):
    def test_controller_self_test(self) -> None:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(CONTROLLER),
                "-SelfTest",
            ],
            cwd=REPOSITORY,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "SPOT_REALTIME_IMAGE_CANARY_120M_SELF_TEST_PASS",
            result.stdout,
        )

    def test_launcher_is_fail_closed_and_progress_visible(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")
        verify_index = source.index(
            "verify-spot-realtime-image-canary-kit.ps1"
        )
        preflight_index = source.index("-PreflightOnly")
        full_run_index = source.rindex(
            "invoke-spot-realtime-image-canary-120m.ps1"
        )
        self.assertLess(verify_index, preflight_index)
        self.assertLess(preflight_index, full_run_index)
        self.assertIn("Progress appears every 30 seconds", source)
        self.assertIn('if "%SFL_CANARY_EXIT%"=="10"', source)
        self.assertIn("ROLLBACK REQUIRED", source)
        self.assertIn("verified v1.0.20 cd8cfa6 installer", source)
        self.assertNotIn("v1.0.16", source)

    def test_builder_binds_product_core_and_progress_contract(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn(
            '"077b6b1c45b7bf6023d89ba13ecaa54d22acbe70"',
            source,
        )
        self.assertIn(
            'build_git_commit = "5971fc4fbdeec07ef65681a945319f0ae12d55cb"',
            source,
        )
        self.assertIn("ProgressIntervalSeconds = 30", source)
        self.assertIn("[CANARY PROGRESS]", source)
        self.assertIn(
            "local clock/process only; no added SPOT requests",
            source,
        )
        self.assertIn("--untracked-files=no", source)
        self.assertIn("contains_installer = $false", source)
        self.assertIn("changes_application_or_settings = $false", source)
        self.assertIn(
            'schema_version = "spot-realtime-image-v1021-canary-kit-v2"',
            source,
        )
        self.assertIn(
            'version = "1.0.20"',
            source,
        )
        self.assertIn(
            'build_git_commit = "cd8cfa649203494cf087206cf656dc2197107ea1"',
            source,
        )
        self.assertIn(
            'counter_rate_window = "installed-state-preflight-to-postflight"',
            source,
        )

    def test_builder_preserves_trigger_job_failure_evidence(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        for fragment in (
            "trigger_monitor_failure_raw.json",
            "trigger_monitor_failure.json",
            "spot-connecttimeout-trigger-monitor-failure-v1",
            "trigger-baseline-read-failed",
            "trigger_monitor_failure_reason_code",
        ):
            self.assertIn(fragment, source)

    def test_progress_format_applies_to_the_complete_message(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn(
            '                    ("[CANARY PROGRESS] stage=observing '
            'elapsed={0} remaining={1} " +',
            source,
        )
        self.assertIn(
            '                    "local clock/process only; no added SPOT '
            'requests") -f',
            source,
        )

    def test_controller_has_runtime_packet_and_identity_gates(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        required_fragments = (
            "backend restarted during the 120-minute canary",
            "source_port_pool_exhaustion_count",
            "source_port_reuse_violation_count",
            "image_refresh_failure_count",
            "same-four-tuple-reuse-under-75s",
            "reset-before-response",
            "packet-capture-window-incomplete",
            "SPOT_120M_ROLLBACK_REQUIRED",
            "SPOT_120M_EVIDENCE_HOLD",
            "SPOT_120M_PASS_WITH_SWITCH_LIMITATION",
            "production_promotion_allowed = $false",
            "counter_window_elapsed_seconds",
            "Get-CollectorEvidenceHolds",
            "collector failure was not classified as evidence hold",
            "mismatched rollback baseline was accepted",
        )
        for fragment in required_fragments:
            self.assertIn(fragment, source)

    def test_controller_handles_incomplete_operator_and_switch_evidence(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        for fragment in (
            "Test-SwitchEvidenceLimitation",
            "Test-OperatorVisualConfirmationEligible",
            "NOT_REQUESTED_INCOMPLETE_INTERVAL",
            "prompted = $operatorEligible",
            "switch_evidence_unavailable_declared",
        ):
            self.assertIn(fragment, source)

    def test_verifier_and_guide_fix_exact_deployment_identity(self) -> None:
        verifier = VERIFIER.read_text(encoding="utf-8")
        guide = GUIDE.read_text(encoding="utf-8")
        for expected in (
            "5971fc4fbdeec07ef65681a945319f0ae12d55cb",
            "01CF544C999FB21FADB7F36965DC35FB9E8AEE36D1EEBD3319A1EB7296AD191A",
            "cd8cfa649203494cf087206cf656dc2197107ea1",
            "F3C52902EFA2081A5060D4CD2C579E8B20B9DBA2DE34E174C946390BEDA0DE19",
            "464BF0A540133C5165B7E550430EDA9EDAA07FA866481B43FAD2B0392016A4F8",
            "2E16E28BD695B5D9125EF11822E4E10DA2D422E0D1781EE72A623D1EE0A97063",
        ):
            self.assertIn(expected, verifier)
        for source in (
            BUILDER.read_text(encoding="utf-8"),
            verifier,
            guide,
            LAUNCHER.read_text(encoding="utf-8"),
        ):
            self.assertNotIn("1.0.16", source)
            self.assertNotIn(
                "42A076B37ADA66CEAEE816128A1FC67C40CCD1C5417F9BDED5E885478974F615",
                source,
            )
        self.assertIn("30초마다", guide)
        self.assertIn("추가 호출하지 않으므로", guide)
        self.assertIn("PASS_WITH_SWITCH_LIMITATION", guide)
        self.assertIn("installed-state", guide)
        self.assertIn("EVIDENCE_HOLD", guide)


if __name__ == "__main__":
    unittest.main()
