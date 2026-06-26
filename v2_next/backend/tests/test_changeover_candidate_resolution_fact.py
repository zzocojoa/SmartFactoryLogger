import unittest

from backend.FacilityData.changeover_candidate_resolution_fact import (
    infer_changeover_candidate_resolution_facts,
    infer_process_phase_event_facts,
)


def _row(
    sample_seq: int,
    *,
    candidate_id: str = "chg_pre",
    phase: str = "pre_changeover_hold_candidate",
    count: int = 12,
    timestamp_utc: str = "2026-06-25T00:00:00Z",
    product_no: str = "100",
    mold_no: str = "7",
    expectedness: str = "expected_candidate",
) -> dict[str, str]:
    return {
        "changeover_candidate_id": candidate_id,
        "process_phase_candidate": phase,
        "temperature_expectedness_candidate": expectedness,
        "Product_No_operator": product_no,
        "Mold_No_operator": mold_no,
        "Count": str(count),
        "logger_service_instance_id": "logger-1",
        "sample_seq": str(sample_seq),
        "timestamp_utc": timestamp_utc,
    }


class ChangeoverCandidateResolutionFactTests(unittest.TestCase):
    def test_each_candidate_gets_one_terminal_resolution(self) -> None:
        rows = [
            {
                "changeover_candidate_id": "chg_1",
                "process_phase_candidate": "changeover_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "10",
                "timestamp_utc": "2026-06-25T00:00:00Z",
            },
            {
                "changeover_candidate_id": "chg_1",
                "process_phase_candidate": "changeover_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "11",
                "timestamp_utc": "2026-06-25T00:00:01Z",
            },
        ]

        facts = infer_changeover_candidate_resolution_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["changeover_candidate_id"], "chg_1")
        self.assertEqual(facts[0]["confirmation_outcome"], "confirmed")
        self.assertEqual(facts[0]["sample_seq_start"], "10")
        self.assertEqual(facts[0]["sample_seq_end"], "11")

    def test_process_phase_event_maps_candidate_to_confirmed_phase(self) -> None:
        rows = [
            {
                "changeover_candidate_id": "chg_2",
                "process_phase_candidate": "setup_alignment_candidate",
                "temperature_expectedness_candidate": "expected_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "20",
                "timestamp_utc": "2026-06-25T00:00:00Z",
            }
        ]

        facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["process_phase_confirmed"], "setup_alignment")
        self.assertEqual(facts[0]["temperature_expectedness_confirmed"], "expected")

    def test_pre_changeover_hold_without_future_evidence_is_rejected(self) -> None:
        rows = [
            _row(100, timestamp_utc="2026-06-25T00:00:00Z"),
            _row(101, timestamp_utc="2026-06-25T00:00:01Z"),
            _row(
                102,
                candidate_id="",
                phase="production_stable",
                count=12,
                timestamp_utc="2026-06-25T00:02:00Z",
            ),
        ]

        resolution_facts = infer_changeover_candidate_resolution_facts(rows, source_file_id="sha256:abc")
        event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(resolution_facts[0]["confirmation_outcome"], "rejected")
        self.assertEqual(
            resolution_facts[0]["resolution_reason"],
            "pre_changeover_hold_candidate_without_future_evidence",
        )
        self.assertEqual(event_facts[0]["process_phase_confirmed"], "unknown")
        self.assertEqual(event_facts[0]["phase_confirmation_state"], "posthoc_rejected")
        self.assertEqual(event_facts[0]["temperature_expectedness_confirmed"], "indeterminate")

    def test_pre_changeover_hold_confirms_with_future_evidence(self) -> None:
        evidence_rows = (
            _row(202, candidate_id="", phase="production_stable", count=0),
            _row(202, candidate_id="", phase="production_stable", product_no="200", mold_no="8"),
            _row(202, candidate_id="", phase="die_change_candidate"),
        )
        for evidence_row in evidence_rows:
            with self.subTest(evidence_row=evidence_row):
                rows = [
                    _row(200, timestamp_utc="2026-06-25T00:00:00Z"),
                    _row(201, timestamp_utc="2026-06-25T00:00:01Z"),
                    {**evidence_row, "timestamp_utc": "2026-06-25T00:03:00Z"},
                ]

                resolution_facts = infer_changeover_candidate_resolution_facts(rows, source_file_id="sha256:abc")
                event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

                self.assertEqual(resolution_facts[0]["confirmation_outcome"], "confirmed")
                self.assertEqual(event_facts[0]["process_phase_confirmed"], "pre_changeover_hold")
                self.assertEqual(event_facts[0]["phase_confirmation_state"], "posthoc_confirmed")

    def test_pre_changeover_hold_confirms_when_only_product_changes(self) -> None:
        rows = [
            _row(300, timestamp_utc="2026-06-25T00:00:00Z", product_no="100", mold_no="7"),
            _row(301, timestamp_utc="2026-06-25T00:00:01Z", product_no="100", mold_no="7"),
            _row(
                302,
                candidate_id="",
                phase="production_stable",
                timestamp_utc="2026-06-25T00:03:00Z",
                product_no="200",
                mold_no="7",
            ),
        ]

        event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(event_facts[0]["process_phase_confirmed"], "pre_changeover_hold")
        self.assertEqual(event_facts[0]["phase_confirmation_state"], "posthoc_confirmed")
        self.assertEqual(
            event_facts[0]["confirmation_reason"],
            "pre_changeover_hold_candidate_confirmed_by_future_operator_context_changed",
        )

    def test_pre_changeover_hold_confirms_when_only_mold_changes(self) -> None:
        rows = [
            _row(400, timestamp_utc="2026-06-25T00:00:00Z", product_no="100", mold_no="7"),
            _row(401, timestamp_utc="2026-06-25T00:00:01Z", product_no="100", mold_no="7"),
            _row(
                402,
                candidate_id="",
                phase="production_stable",
                timestamp_utc="2026-06-25T00:03:00Z",
                product_no="100",
                mold_no="8",
            ),
        ]

        event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(event_facts[0]["process_phase_confirmed"], "pre_changeover_hold")
        self.assertEqual(event_facts[0]["phase_confirmation_state"], "posthoc_confirmed")
        self.assertEqual(
            event_facts[0]["confirmation_reason"],
            "pre_changeover_hold_candidate_confirmed_by_future_operator_context_changed",
        )

    def test_general_idle_candidate_id_is_ignored_by_changeover_facts(self) -> None:
        rows = [
            _row(500, candidate_id="chg_idle", phase="idle_candidate", timestamp_utc="2026-06-25T00:00:00Z"),
            _row(501, candidate_id="chg_idle", phase="idle_candidate", timestamp_utc="2026-06-25T00:00:01Z"),
        ]

        resolution_facts = infer_changeover_candidate_resolution_facts(rows, source_file_id="sha256:abc")
        event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(resolution_facts, [])
        self.assertEqual(event_facts, [])

    def test_lifecycle_candidate_confirms_terminal_production_stabilizing_phase(self) -> None:
        rows = [
            _row(600, candidate_id="chg_lifecycle", phase="die_change_candidate"),
            _row(601, candidate_id="chg_lifecycle", phase="setup_alignment_candidate"),
            _row(602, candidate_id="chg_lifecycle", phase="production_stabilizing"),
        ]

        resolution_facts = infer_changeover_candidate_resolution_facts(rows, source_file_id="sha256:abc")
        event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(len(resolution_facts), 1)
        self.assertEqual(resolution_facts[0]["confirmation_outcome"], "confirmed")
        self.assertEqual(resolution_facts[0]["resolution_reason"], "production_stabilizing_mapped_posthoc")
        self.assertEqual(event_facts[0]["process_phase_confirmed"], "production_stabilizing")
        self.assertEqual(event_facts[0]["phase_confirmation_state"], "posthoc_confirmed")
    def test_same_candidate_id_across_noncontiguous_rows_is_one_lifecycle(self) -> None:
        rows = [
            {
                "changeover_candidate_id": "chg_repeat",
                "process_phase_candidate": "setup_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "1",
                "timestamp_utc": "2026-06-25T00:00:00Z",
            },
            {
                "changeover_candidate_id": "chg_repeat",
                "process_phase_candidate": "setup_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "2",
                "timestamp_utc": "2026-06-25T00:00:01Z",
            },
            {
                "changeover_candidate_id": "",
                "process_phase_candidate": "production_stable",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "3",
                "timestamp_utc": "2026-06-25T00:00:02Z",
            },
            {
                "changeover_candidate_id": "chg_repeat",
                "process_phase_candidate": "setup_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "4",
                "timestamp_utc": "2026-06-25T00:00:03Z",
            },
        ]

        resolution_facts = infer_changeover_candidate_resolution_facts(rows, source_file_id="sha256:abc")
        event_facts = infer_process_phase_event_facts(rows, source_file_id="sha256:abc")

        self.assertEqual(len(resolution_facts), 1)
        self.assertEqual(resolution_facts[0]["changeover_candidate_id"], "chg_repeat")
        self.assertEqual(resolution_facts[0]["sample_seq_start"], "1")
        self.assertEqual(resolution_facts[0]["sample_seq_end"], "4")
        self.assertEqual(len(event_facts), 1)
        self.assertEqual(event_facts[0]["source_changeover_candidate_id"], "chg_repeat")


if __name__ == "__main__":
    unittest.main()
