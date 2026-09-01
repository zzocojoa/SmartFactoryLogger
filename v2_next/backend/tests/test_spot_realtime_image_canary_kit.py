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
    / "spot-realtime-image-v1022-validation.md"
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
        self.assertLess(verify_index, preflight_index)
        self.assertIn("separate 15-minute diagnostic", source)
        self.assertIn("intentionally blocks the 120-minute observation", source)
        self.assertIn('set "SFL_CANARY_EXIT=3"', source)
        self.assertEqual(
            source.count("invoke-spot-realtime-image-canary-120m.ps1"),
            1,
        )
        self.assertNotIn("v1.0.16", source)

    def test_builder_binds_product_core_and_progress_contract(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn(
            '"9b38171a00616a732d1aa64853d114c946f3bb78"',
            source,
        )
        self.assertIn(
            'build_git_commit = "5cc34b4fffd70195ec7fdd9d27acf4880cecbd80"',
            source,
        )
        self.assertNotIn(
            '    Add-CanaryProgressContract `',
            source,
        )
        self.assertNotIn(
            '    Add-TriggerMonitorFailureContract `',
            source,
        )
        self.assertNotIn(
            '    Add-TriggerMonitorPathBudgetContract `',
            source,
        )
        self.assertIn("--untracked-files=no", source)
        self.assertIn("contains_installer = $false", source)
        self.assertIn("changes_application_or_settings = $false", source)
        self.assertIn(
            'schema_version = "spot-realtime-image-v1022-canary-kit-v8"',
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
            'counter_rate_window = "observation-start-to-observation-end"',
            source,
        )
        self.assertIn(
            'general_request_event_drop_policy = '
            '"bounded-journal-eviction-observability-only"',
            source,
        )
        self.assertIn('framing_schema = "spot-http-framing-evidence-v10"', source)
        self.assertIn(
            'observation_boundary_schema = "spot-canary-observation-boundary-v1"',
            source,
        )
        self.assertIn(
            'trigger_monitor_completion_policy =',
            source,
        )
        self.assertIn(
            '"observer-deadline-atomic-request"',
            source,
        )
        self.assertIn(
            '"spot-trigger-monitor-completion-request-v1"',
            source,
        )
        for expected in (
            'result = "PENDING_SERVER_VALIDATION"',
            'full_120m_allowed = $false',
            'source_port_policy_version = "spot-source-port-quarantine-v3"',
            "source_port_minimum_required_reuse_interval_seconds = 75.0",
            "source_port_quarantine_safety_margin_seconds = 2.0",
            "source_port_quarantine_seconds = 77.0",
            "source_port_pool_capacity = 768",
            "source_port_minimum_required_pool_capacity = 462",
        ):
            self.assertIn(expected, source)

    def test_builder_preserves_trigger_job_failure_evidence(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn(
            '"9b38171a00616a732d1aa64853d114c946f3bb78"',
            source,
        )
        self.assertNotIn('    Add-TriggerMonitorFailureContract `', source)

    def test_controller_uses_a_short_fail_closed_runtime_evidence_root(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        for fragment in (
            "RuntimeEvidenceBase",
            "LOCALAPPDATA",
            "SFLCanary",
            "Get-ProjectedRuntimeEvidencePath",
            "Assert-CanaryRuntimeEvidencePathBudget",
            "runtime_evidence_projected_path_chars",
            "runtime_evidence_path_limit_chars",
        ):
            self.assertIn(fragment, source)

    def test_progress_format_applies_to_the_complete_message(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn(
            'counter_rate_window = $identity.canary.counter_rate_window',
            source,
        )
        self.assertIn(
            'postprocess_integrity_failures',
            source,
        )

    def test_controller_has_runtime_packet_and_identity_gates(self) -> None:
        source = CONTROLLER.read_text(encoding="utf-8")
        required_fragments = (
            "observation-state-changed",
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
            "canary-observation-start.json",
            "canary-observation-end.json",
            "canary-postprocess-state.json",
            "failure_events",
            "postprocess_integrity_failures",
            "packet-clock-calibration-incomplete",
            "bidirectional-rst-observed",
            "Get-CollectorEvidenceHolds",
            "collector failure was not classified as evidence hold",
            "mismatched rollback baseline was accepted",
            "spot-source-port-quarantine-v3",
            "source_port_quarantine_safety_margin_seconds",
            "source_port_minimum_required_pool_capacity",
            "120-minute observation is blocked until the v1.0.22",
            "preHandshakeAppSuccessDiscrepancyEligible",
            "pre_handshake_packet_capture_or_flow_attribution_discrepancy_attempts",
            "no_response_after_handshake_packet_capture_or_flow_attribution_discrepancy_attempts",
            "self-test incomplete pre-handshake app outcome was not held",
            "self-test pre-handshake SYN retransmission was not rejected",
            "self-test pre-handshake reset evidence was not rejected",
        )
        for fragment in required_fragments:
            self.assertIn(fragment, source)

    def test_controller_baselines_historical_failures_and_rejects_new_deltas(
        self,
    ) -> None:
        controller = CONTROLLER.read_text(encoding="utf-8")
        builder = BUILDER.read_text(encoding="utf-8")
        verifier = VERIFIER.read_text(encoding="utf-8")
        guide = GUIDE.read_text(encoding="utf-8")

        for fragment in (
            "Get-CumulativeFailureCounterNames",
            "Confirm-StableHistoricalFailureBaseline",
            "historical-failure-baseline.json",
            "spot-canary-historical-failure-baseline-v1",
            "STABLE_HISTORICAL_FAILURE_BASELINE",
            "failure_counter_deltas",
            "SPOT failure counter increased during canary",
            "[PREFLIGHT BASELINE PROGRESS]",
        ):
            self.assertIn(fragment, controller)

        self.assertIn(
            'historical_failure_counter_policy = '
            '"stable-preflight-baseline-and-zero-canary-delta"',
            builder,
        )
        self.assertIn("historical_failure_stability_seconds = 30", builder)
        self.assertIn(
            "historical_failure_progress_interval_seconds -ne 10",
            verifier,
        )
        self.assertIn("신규 transport/image/temperature", guide)
        self.assertIn("77초", guide)

        failure_names_start = controller.index(
            "function Get-CumulativeFailureCounterNames"
        )
        failure_names_end = controller.index(
            "function Get-CumulativeFailureCounterSnapshot"
        )
        failure_names = controller[failure_names_start:failure_names_end]
        self.assertNotIn("source_port_request_event_drop_count", failure_names)
        self.assertIn(
            "source_port_request_failure_event_drop_count",
            failure_names,
        )
        self.assertIn(
            '"source_port_request_event_drop_count"',
            controller[:failure_names_start],
        )
        self.assertIn(
            "bounded-journal-eviction-observability-only",
            verifier,
        )
        self.assertIn("failure event journal", guide)

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
            "5cc34b4fffd70195ec7fdd9d27acf4880cecbd80",
            "77577ABB08BD901365B2D366B5ABAF101217E90B8AA5F2E9CB47971FF03123E2",
            "cd8cfa649203494cf087206cf656dc2197107ea1",
            "F3C52902EFA2081A5060D4CD2C579E8B20B9DBA2DE34E174C946390BEDA0DE19",
            "E171DF1C3EB3C8DB78700E95913E87E7B1EE95460990F6B342AD4E0165448C2C",
            "B13909D1A6067E94EC945750C82F17948FC597D3A29060323E807193650F0327",
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
        self.assertIn("every 30 seconds", guide)
        self.assertIn("does not add SPOT or", guide)
        self.assertIn("backend API requests", guide)
        self.assertIn("PASS_WITH_SWITCH_LIMITATION", guide)
        self.assertIn("PENDING_SERVER_VALIDATION", BUILDER.read_text(encoding="utf-8"))
        self.assertIn("EVIDENCE_HOLD", guide)


if __name__ == "__main__":
    unittest.main()
