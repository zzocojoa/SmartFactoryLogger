import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.infer_process_phase_events_for_csv as infer_cli


class InferProcessPhaseEventsForCsvTests(unittest.TestCase):
    def write_input_csv(self, path: Path) -> None:
        rows = [
            {
                "changeover_candidate_id": "chg_1",
                "process_phase_candidate": "setup_candidate",
                "temperature_expectedness_candidate": "expected_candidate",
                "logger_service_instance_id": "logger-1",
                "sample_seq": "1",
                "timestamp_utc": "2026-06-25T00:00:00Z",
            }
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def test_config_flag_false_blocks_fact_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "Factory_Integrated_Log_v2_20260625_000000.csv"
            resolution_output = tmp_path / "changeover_candidate_resolution_fact.csv"
            event_output = tmp_path / "process_phase_event_fact.csv"
            self.write_input_csv(input_path)

            with patch.object(infer_cli.config, "PROCESS_PHASE_EVENT_FACT_ENABLED", False):
                with self.assertRaises(infer_cli.ProcessPhaseEventFactDisabledError):
                    infer_cli.infer_process_phase_events_from_csv(input_path, resolution_output, event_output)

            self.assertFalse(resolution_output.exists())
            self.assertFalse(event_output.exists())

    def test_config_flag_true_writes_resolution_and_event_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "Factory_Integrated_Log_v2_20260625_000000.csv"
            resolution_output = tmp_path / "changeover_candidate_resolution_fact.csv"
            event_output = tmp_path / "process_phase_event_fact.csv"
            self.write_input_csv(input_path)

            with patch.object(infer_cli.config, "PROCESS_PHASE_EVENT_FACT_ENABLED", True):
                resolution_facts, event_facts = infer_cli.infer_process_phase_events_from_csv(
                    input_path,
                    resolution_output,
                    event_output,
                )

            self.assertEqual(len(resolution_facts), 1)
            self.assertEqual(len(event_facts), 1)
            self.assertTrue(resolution_output.exists())
            self.assertTrue(event_output.exists())
            with event_output.open("r", encoding="utf-8-sig", newline="") as handle:
                written_events = list(csv.DictReader(handle))
            self.assertEqual(written_events[0]["source_changeover_candidate_id"], "chg_1")


if __name__ == "__main__":
    unittest.main()
