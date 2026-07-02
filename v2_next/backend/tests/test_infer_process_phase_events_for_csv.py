import csv
import hashlib
import json
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

    def test_writes_process_phase_fact_manifests_to_existing_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "Factory_Integrated_Log_v2_20260625_000000.csv"
            metadata_path = input_path.with_suffix(".metadata.json")
            resolution_output = tmp_path / "changeover_candidate_resolution_fact.csv"
            event_output = tmp_path / "process_phase_event_fact.csv"
            self.write_input_csv(input_path)
            metadata_path.write_text(
                json.dumps({"schema_metadata": {"schema_version": "2.4.0"}}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(infer_cli.config, "PROCESS_PHASE_EVENT_FACT_ENABLED", True):
                infer_cli.infer_process_phase_events_from_csv(
                    input_path,
                    resolution_output,
                    event_output,
                )

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            source_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
            resolution_hash = hashlib.sha256(resolution_output.read_bytes()).hexdigest()
            event_hash = hashlib.sha256(event_output.read_bytes()).hexdigest()

        manifest_keys = metadata["schema_metadata"]["posthoc_fact_manifests"]
        self.assertIn("changeover_candidate_resolution_fact_manifest", manifest_keys)
        self.assertIn("process_phase_event_fact_manifest", manifest_keys)
        resolution_manifest = metadata["changeover_candidate_resolution_fact_manifest"]
        event_manifest = metadata["process_phase_event_fact_manifest"]
        self.assertEqual(resolution_manifest["row_count"], 1)
        self.assertEqual(resolution_manifest["sha256"], resolution_hash)
        self.assertEqual(resolution_manifest["source_csv_sha256"], source_hash)
        self.assertEqual(resolution_manifest["source_file_id"], f"sha256:{source_hash}")
        self.assertEqual(event_manifest["row_count"], 1)
        self.assertEqual(event_manifest["sha256"], event_hash)
        self.assertEqual(event_manifest["source_csv_sha256"], source_hash)
        self.assertEqual(event_manifest["source_file_id"], f"sha256:{source_hash}")


if __name__ == "__main__":
    unittest.main()
