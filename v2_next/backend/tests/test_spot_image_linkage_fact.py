import csv
import json
import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.spot_image_linkage_fact import (
    SPOT_IMAGE_LINKAGE_FACT_COLUMNS,
    infer_spot_image_linkage_facts,
)
from scripts.infer_spot_image_linkage_for_csv import infer_spot_image_linkage_from_csv
from scripts.validate_csv_v2_shadow import validate_spot_image_linkage_fact_manifest
from scripts.write_server_smoke_closeout import _validator_args


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


class SpotImageLinkageFactTests(unittest.TestCase):
    source_header = [
        "sample_seq",
        "timestamp_utc",
        "spot_observation_key",
        "spot_image_capture_id_nearest",
    ]
    image_fact_header = [
        "spot_image_capture_id",
        "spot_image_path",
        "spot_image_sha256",
        "spot_image_link_status",
        "spot_image_link_age_ms",
        "spot_image_linked_observation_key",
    ]

    def test_infers_match_no_key_no_fact_and_ambiguous_rows(self) -> None:
        source_rows = [
            {
                "sample_seq": "1",
                "timestamp_utc": "2026-07-03T00:00:00Z",
                "spot_observation_key": "svc-1:1",
                "spot_image_capture_id_nearest": "spotimg_1",
            },
            {
                "sample_seq": "2",
                "timestamp_utc": "2026-07-03T00:00:01Z",
                "spot_observation_key": "",
                "spot_image_capture_id_nearest": "",
            },
            {
                "sample_seq": "3",
                "timestamp_utc": "2026-07-03T00:00:02Z",
                "spot_observation_key": "svc-1:missing",
                "spot_image_capture_id_nearest": "",
            },
            {
                "sample_seq": "4",
                "timestamp_utc": "2026-07-03T00:00:03Z",
                "spot_observation_key": "svc-1:dup",
                "spot_image_capture_id_nearest": "spotimg_dup_a",
            },
        ]
        image_fact_rows = [
            self._image_fact("spotimg_1", "svc-1:1"),
            self._image_fact("spotimg_dup_a", "svc-1:dup"),
            self._image_fact("spotimg_dup_b", "svc-1:dup"),
        ]

        facts = infer_spot_image_linkage_facts(
            source_rows,
            image_fact_rows,
            source_csv_sha256="a" * 64,
        )

        self.assertEqual([fact["linkage_status"] for fact in facts], [
            "matched",
            "no_observation_key",
            "no_image_fact",
            "ambiguous",
        ])
        self.assertEqual(facts[0]["realtime_pointer_status"], "same_as_posthoc")
        self.assertEqual(facts[1]["realtime_pointer_status"], "not_applicable")
        self.assertEqual(facts[3]["match_count"], "2")
        self.assertEqual(facts[3]["matched_spot_image_capture_id"], "")

    def test_generator_writes_fact_report_and_metadata_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_csv, image_fact, metadata_path = self._write_artifact_inputs(tmp_path)
            linkage_fact = tmp_path / "spot_image_linkage_fact.csv"
            linkage_report = tmp_path / "spot_image_linkage_report.json"

            facts, report = infer_spot_image_linkage_from_csv(
                input_path=source_csv,
                spot_image_fact_path=image_fact,
                fact_output_path=linkage_fact,
                report_output_path=linkage_report,
                metadata_path=metadata_path,
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            failures, summary = validate_spot_image_linkage_fact_manifest(
                metadata,
                metadata_path,
                source_csv,
                spot_image_fact_path=image_fact,
                linkage_fact_path=linkage_fact,
                linkage_report_path=linkage_report,
            )

        self.assertEqual(failures, [])
        self.assertEqual(len(facts), 3)
        self.assertEqual(report["counts"]["matched"], 1)
        self.assertEqual(report["counts"]["ambiguous"], 1)
        self.assertFalse(any(report["redaction"].values()))
        self.assertIn("spot_image_linkage_fact_manifest", metadata)
        self.assertEqual(
            metadata["spot_image_linkage_fact_manifest"]["required_columns"],
            SPOT_IMAGE_LINKAGE_FACT_COLUMNS,
        )
        self.assertEqual(summary["spot_image_linkage_fact_row_count_match"], "true")
        self.assertEqual(summary["spot_image_linkage_report_redaction_passed"], "true")

    def test_validator_rejects_report_with_full_internal_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_csv, image_fact, metadata_path = self._write_artifact_inputs(tmp_path)
            linkage_fact = tmp_path / "spot_image_linkage_fact.csv"
            linkage_report = tmp_path / "spot_image_linkage_report.json"
            infer_spot_image_linkage_from_csv(
                input_path=source_csv,
                spot_image_fact_path=image_fact,
                fact_output_path=linkage_fact,
                report_output_path=linkage_report,
                metadata_path=metadata_path,
            )
            report = json.loads(linkage_report.read_text(encoding="utf-8-sig"))
            report["source_csv"]["file"] = str(source_csv)
            report["redaction"] = {
                "raw_image_included": False,
                "raw_camera_url_included": False,
                "secret_included": False,
                "full_internal_path_included": False,
            }
            linkage_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))

            failures, summary = validate_spot_image_linkage_fact_manifest(
                metadata,
                metadata_path,
                source_csv,
                spot_image_fact_path=image_fact,
                linkage_fact_path=linkage_fact,
                linkage_report_path=linkage_report,
            )

        self.assertIn("spot_image_linkage_report contains non-sanitized values", failures)
        self.assertEqual(summary["spot_image_linkage_report_redaction_passed"], "false")

    def test_validator_rejects_source_csv_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_csv, image_fact, metadata_path = self._write_artifact_inputs(tmp_path)
            linkage_fact = tmp_path / "spot_image_linkage_fact.csv"
            linkage_report = tmp_path / "spot_image_linkage_report.json"
            infer_spot_image_linkage_from_csv(
                input_path=source_csv,
                spot_image_fact_path=image_fact,
                fact_output_path=linkage_fact,
                report_output_path=linkage_report,
                metadata_path=metadata_path,
            )
            _write_csv(
                source_csv,
                self.source_header,
                [["99", "2026-07-03T00:01:00Z", "svc-1:other", ""]],
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))

            failures, summary = validate_spot_image_linkage_fact_manifest(
                metadata,
                metadata_path,
                source_csv,
                spot_image_fact_path=image_fact,
                linkage_fact_path=linkage_fact,
                linkage_report_path=linkage_report,
            )

        self.assertTrue(any("source CSV" in failure for failure in failures))
        self.assertEqual(summary["spot_image_linkage_source_csv_sha256_match"], "false")

    def test_closeout_validator_args_include_linkage_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            csv_file = bundle / "Factory_Integrated_Log_v2_20260703_000000.csv"
            metadata_file = csv_file.with_suffix(".metadata.json")
            for path in (
                csv_file,
                metadata_file,
                bundle / "spot_image_fact.csv",
                bundle / "spot_image_linkage_fact.csv",
                bundle / "spot_image_linkage_report.json",
            ):
                path.write_text("", encoding="utf-8")

            args, display, paths = _validator_args(
                python_executable="python",
                bundle_path=bundle,
                mode="copied",
                csv_file=csv_file,
                metadata_file=metadata_file,
            )

        self.assertIn("--spot-image-linkage-fact", args)
        self.assertIn("--spot-image-linkage-report", args)
        self.assertIn("spot_image_linkage_fact.csv", display)
        self.assertEqual(paths["spot_image_linkage_fact"].name, "spot_image_linkage_fact.csv")
        self.assertEqual(paths["spot_image_linkage_report"].name, "spot_image_linkage_report.json")

    def _write_artifact_inputs(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        source_csv = tmp_path / "Factory_Integrated_Log_v2_20260703_000000.csv"
        image_fact = tmp_path / "spot_image_fact.csv"
        metadata_path = source_csv.with_suffix(".metadata.json")
        _write_csv(
            source_csv,
            self.source_header,
            [
                ["1", "2026-07-03T00:00:00Z", "svc-1:1", "spotimg_1"],
                ["2", "2026-07-03T00:00:01Z", "svc-1:missing", ""],
                ["3", "2026-07-03T00:00:02Z", "svc-1:dup", "spotimg_dup_a"],
            ],
        )
        _write_csv(
            image_fact,
            self.image_fact_header,
            [
                self._image_fact_row("spotimg_1", "svc-1:1"),
                self._image_fact_row("spotimg_dup_a", "svc-1:dup"),
                self._image_fact_row("spotimg_dup_b", "svc-1:dup"),
            ],
        )
        metadata_path.write_text(
            json.dumps({"schema_metadata": {"schema_version": "2.4.0"}}, indent=2),
            encoding="utf-8",
        )
        return source_csv, image_fact, metadata_path

    def _image_fact(self, capture_id: str, observation_key: str) -> dict[str, str]:
        return dict(zip(self.image_fact_header, self._image_fact_row(capture_id, observation_key), strict=True))

    def _image_fact_row(self, capture_id: str, observation_key: str) -> list[str]:
        return [
            capture_id,
            f"spot_images/2026/07/03/{capture_id}.jpg",
            "b" * 64,
            "fresh",
            "100.000",
            observation_key,
        ]


if __name__ == "__main__":
    unittest.main()
