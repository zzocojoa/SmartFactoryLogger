import unittest

from backend.FacilityData.changeover_candidate_resolution_fact import (
    infer_changeover_candidate_resolution_facts,
    infer_process_phase_event_facts,
)


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


if __name__ == "__main__":
    unittest.main()
