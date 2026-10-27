import asyncio
import csv
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from backend import app as backend_app
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData import spot_image_fact as image_fact
from backend.FacilityData.spot_image_fact import (
    SPOT_IMAGE_FACT_COLUMNS,
    SpotImageCaptureWriter,
    build_spot_image_fact_manifest,
)
from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_COLUMNS,
    SpotObservationFactWriter,
    summarize_spot_observation_fact,
)
from scripts.validate_csv_v2_shadow import validate_csv_closeout


class ShutdownCloseoutRegressionTests(unittest.TestCase):
    repo_root = Path(__file__).resolve().parents[2]

    def setUp(self) -> None:
        # os._exit is intercepted by these tests; isolate its process-owned
        # evidence registry between test cases without changing any assertion.
        for name in ("_shutdown_evidence_status", "_shutdown_evidence_attempts"):
            isolated = patch.object(backend_app, name, {})
            isolated.start()
            self.addCleanup(isolated.stop)

    def test_large_observation_manifest_is_streamed_with_bounded_memory(self) -> None:
        row_total = 200_000
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writeheader()
                for sequence in range(1, row_total + 1):
                    writer.writerow(
                        {
                            "spot_observation_fact_schema_version": "1.3.0",
                            "spot_observation_key": f"service-1:{sequence}",
                            "spot_service_instance_id": "service-1",
                            "spot_poll_seq": sequence,
                            "spot_observation_seq": sequence,
                            "diagnostics_capture_status": "async_complete",
                            "diagnostics_binding_status": "same_poll",
                            "diagnostics_missing_fields": "[]",
                            "spot_diagnostic_evidence_codes": '["signal_below_threshold"]',
                            "evidence_provenance_json": '{"signal_below_threshold":"signalpc"}',
                            "signalpc": "1.5",
                        }
                    )

            expected_sha256 = hashlib.sha256(fact_path.read_bytes()).hexdigest()
            realtime_rows = [
                {"spot_observation_key": "service-1:1"},
                {"spot_observation_key": f"service-1:{row_total}"},
                {"spot_observation_key": "service-1:missing"},
            ]

            tracemalloc.start()
            try:
                summary = summarize_spot_observation_fact(
                    fact_path=fact_path,
                    realtime_rows=realtime_rows,
                )
                _, peak_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

        self.assertEqual(summary["row_count"], row_total)
        self.assertEqual(summary["distinct_observation_key_count"], row_total)
        self.assertEqual(summary["poll_seq_gap_count"], 0)
        self.assertEqual(summary["sha256"], expected_sha256)
        self.assertEqual(summary["link_coverage"]["linked_rows"], 2)
        self.assertEqual(summary["link_coverage"]["missing_fact_key_rows"], 1)
        self.assertLess(
            peak_bytes,
            64 * 1024 * 1024,
            f"observation manifest peak memory was {peak_bytes} bytes",
        )

    def test_large_realtime_csv_closeout_is_streamed_with_bounded_memory(self) -> None:
        realtime_row_total = 200_000
        distinct_key_total = realtime_row_total // 2
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            csv_path = log_path / "Factory_Integrated_Log_v2_large.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["spot_observation_key"])
                writer.writeheader()
                for sequence in range(realtime_row_total):
                    writer.writerow(
                        {
                            "spot_observation_key": (
                                f"service-1:{(sequence % distinct_key_total) + 1}"
                            )
                        }
                    )
            metadata_path = csv_path.with_suffix(".metadata.json")
            metadata_path.write_text("{}\n", encoding="utf-8")

            fact_path = log_path / "spot_observation_fact.csv"
            with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=SPOT_OBSERVATION_FACT_COLUMNS,
                )
                writer.writeheader()
                for sequence in range(1, distinct_key_total + 1):
                    writer.writerow(
                        {
                            "spot_observation_key": f"service-1:{sequence}",
                            "spot_poll_seq": sequence,
                        }
                    )

            service = CSVLoggerService()
            service._v2_persisted_sample_seq_by_path[str(csv_path)] = (
                realtime_row_total
            )
            service._v2_persisted_at_by_path[str(csv_path)] = (
                "2026-07-29T05:00:00Z"
            )
            tracemalloc.start()
            try:
                with patch(
                    "backend.FacilityData.drivers.spot_api."
                    "get_spot_observation_fact_health",
                    return_value={
                        "enabled": True,
                        "write_failure_count": 0,
                        "spool_pending_count": 0,
                    },
                ):
                    refreshed = service.refresh_spot_observation_fact_manifest_for_csv(
                        csv_path,
                        closeout_reason="shutdown",
                    )
                _, peak_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()

            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            coverage = payload["spot_observation_fact_manifest"]["link_coverage"]
            csv_closeout = payload["csv_closeout"]

        self.assertEqual(refreshed, metadata_path)
        self.assertEqual(
            coverage["realtime_rows_with_observation_key"],
            realtime_row_total,
        )
        self.assertEqual(coverage["linked_rows"], realtime_row_total)
        self.assertEqual(coverage["missing_fact_key_rows"], 0)
        self.assertEqual(coverage["coverage_pct"], 100.0)
        self.assertEqual(
            csv_closeout,
            {
                "finalized": True,
                "closeout_reason": "shutdown",
                "csv_file_name": csv_path.name,
                "logger_service_instance_id": service.logger_service_instance_id,
                "final_persisted_sample_seq": realtime_row_total,
                "persisted_at": "2026-07-29T05:00:00Z",
            },
        )
        self.assertLess(
            peak_bytes,
            64 * 1024 * 1024,
            f"realtime CSV closeout peak memory was {peak_bytes} bytes",
        )

    def test_v2_flush_failure_never_advances_persisted_closeout_state(self) -> None:
        service = CSVLoggerService()
        csv_path = Path("Factory_Integrated_Log_v2_flush_failure.csv")
        service._current_v2_csv_path = csv_path
        contract = service._get_active_v2_contract()
        row = [""] * len(contract.columns)
        row[contract.columns.index("sample_seq")] = "41"
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)

        with patch.object(handle, "flush", side_effect=OSError("simulated final flush failure")), \
                self.assertRaisesRegex(OSError, "simulated final flush failure"):
            service._flush_v2_buffer(
                writer,
                handle,
                [(row, datetime.now().astimezone())],
            )

        self.assertEqual(list(csv.reader(io.StringIO(handle.getvalue()))), [row])
        self.assertNotIn(
            str(csv_path),
            service._v2_persisted_sample_seq_by_path,
        )
        self.assertNotIn(str(csv_path), service._v2_persisted_at_by_path)

    def test_v2_persistence_validation_rejects_rows_before_csv_write(self) -> None:
        service = CSVLoggerService()
        csv_path = Path("Factory_Integrated_Log_v2_prewrite_validation.csv")
        service._current_v2_csv_path = csv_path
        service._v2_persisted_sample_seq_by_path[str(csv_path)] = 41
        contract = service._get_active_v2_contract()
        row = [""] * len(contract.columns)
        row[contract.columns.index("sample_seq")] = "41"
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)

        with patch.object(handle, "flush", wraps=handle.flush) as flush, \
                self.assertRaisesRegex(RuntimeError, "did not advance"):
            service._flush_v2_buffer(
                writer,
                handle,
                [(row, datetime.now().astimezone())],
            )

        self.assertEqual(handle.getvalue(), "")
        flush.assert_not_called()
        self.assertEqual(
            service._v2_persisted_sample_seq_by_path[str(csv_path)],
            41,
        )

    def test_v2_persistence_rejects_non_monotonic_batch_before_csv_write(self) -> None:
        service = CSVLoggerService()
        csv_path = Path("Factory_Integrated_Log_v2_non_monotonic.csv")
        service._current_v2_csv_path = csv_path
        contract = service._get_active_v2_contract()
        rows = []
        for sample_seq in ("42", "41"):
            row = [""] * len(contract.columns)
            row[contract.columns.index("sample_seq")] = sample_seq
            rows.append((row, datetime.now().astimezone()))
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)

        with patch.object(handle, "flush", wraps=handle.flush) as flush, \
                self.assertRaisesRegex(RuntimeError, "not strictly increasing"):
            service._flush_v2_buffer(writer, handle, rows)

        self.assertEqual(handle.getvalue(), "")
        flush.assert_not_called()

    def test_v2_persistence_commit_occurs_only_after_successful_flush(self) -> None:
        service = CSVLoggerService()
        csv_path = Path("Factory_Integrated_Log_v2_successful_flush.csv")
        service._current_v2_csv_path = csv_path
        contract = service._get_active_v2_contract()
        row = [""] * len(contract.columns)
        row[contract.columns.index("sample_seq")] = "42"
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)
        original_flush = handle.flush

        def flush_before_commit():
            self.assertNotIn(str(csv_path), service._v2_persisted_sample_seq_by_path)
            self.assertNotIn(str(csv_path), service._v2_persisted_at_by_path)
            return original_flush()

        with patch.object(handle, "flush", side_effect=flush_before_commit) as flush:
            self.assertTrue(
                service._flush_v2_buffer(
                    writer,
                    handle,
                    [(row, datetime.now().astimezone())],
                )
            )
            flush.assert_called_once_with()

        self.assertEqual(list(csv.reader(io.StringIO(handle.getvalue()))), [row])
        self.assertEqual(
            service._v2_persisted_sample_seq_by_path[str(csv_path)],
            42,
        )
        self.assertIn(str(csv_path), service._v2_persisted_at_by_path)

    def test_validator_rejects_closeout_ahead_of_final_csv_row(self) -> None:
        csv_path = Path("Factory_Integrated_Log_v2_closeout.csv")
        logger_id = "logger-service-closeout-test"
        metadata = {
            "schema_metadata": {
                "logger_service_instance_id": logger_id,
            },
            "csv_closeout": {
                "finalized": True,
                "closeout_reason": "shutdown",
                "csv_file_name": csv_path.name,
                "logger_service_instance_id": logger_id,
                "final_persisted_sample_seq": 42,
                "persisted_at": "2026-07-29T05:00:00Z",
            },
        }

        failures = validate_csv_closeout(
            metadata,
            csv_path,
            [[logger_id, "41"]],
            ["logger_service_instance_id", "sample_seq"],
        )

        self.assertIn(
            "csv_closeout.final_persisted_sample_seq does not match the final CSV row",
            failures,
        )
        self.assertIn(
            "csv_closeout.final_persisted_sample_seq does not match the maximum CSV sample_seq",
            failures,
        )

    def test_validator_covers_csv_closeout_contract_failures(self) -> None:
        csv_path = Path("Factory_Integrated_Log_v2_closeout.csv")
        logger_id = "logger-service-closeout-fixture"
        base_closeout = {
            "finalized": True,
            "closeout_reason": "shutdown",
            "csv_file_name": csv_path.name,
            "logger_service_instance_id": logger_id,
            "final_persisted_sample_seq": 41,
            "persisted_at": "2026-07-29T05:00:00Z",
        }

        def build_metadata(**closeout_overrides: object) -> dict[str, object]:
            return {
                "schema_metadata": {
                    "logger_service_instance_id": logger_id,
                },
                "csv_closeout": {
                    **base_closeout,
                    **closeout_overrides,
                },
            }

        valid_rows = [[logger_id, "41"]]
        valid_header = ["logger_service_instance_id", "sample_seq"]
        self.assertEqual(
            validate_csv_closeout(
                build_metadata(),
                csv_path,
                valid_rows,
                valid_header,
            ),
            [],
        )
        self.assertEqual(
            validate_csv_closeout({}, csv_path, valid_rows, valid_header),
            [],
        )

        malformed_cases = (
            (
                {"csv_closeout": "invalid"},
                "csv_closeout must be an object",
            ),
            (
                build_metadata(finalized=False),
                "csv_closeout.finalized must be true",
            ),
            (
                build_metadata(closeout_reason="unexpected"),
                "csv_closeout.closeout_reason is not recognized",
            ),
            (
                build_metadata(csv_file_name="other.csv"),
                "csv_closeout.csv_file_name does not match the v2 CSV",
            ),
            (
                build_metadata(logger_service_instance_id="other-logger"),
                "csv_closeout.logger_service_instance_id does not match schema metadata",
            ),
        )
        for metadata, expected_failure in malformed_cases:
            with self.subTest(expected_failure=expected_failure):
                self.assertIn(
                    expected_failure,
                    validate_csv_closeout(
                        metadata,
                        csv_path,
                        valid_rows,
                        valid_header,
                    ),
                )

        csv_cases = (
            (
                valid_rows,
                ["logger_service_instance_id"],
                "csv_closeout cannot verify a CSV without sample_seq",
            ),
            (
                [[logger_id]],
                valid_header,
                "csv_closeout cannot verify invalid CSV sample_seq values",
            ),
            (
                [[logger_id, "invalid"]],
                valid_header,
                "csv_closeout cannot verify invalid CSV sample_seq values",
            ),
            (
                [],
                valid_header,
                "csv_closeout cannot verify a CSV without data rows",
            ),
        )
        for rows, header, expected_failure in csv_cases:
            with self.subTest(expected_failure=expected_failure):
                self.assertIn(
                    expected_failure,
                    validate_csv_closeout(
                        build_metadata(),
                        csv_path,
                        rows,
                        header,
                    ),
                )

        for persisted_value in (True, "41", None):
            with self.subTest(persisted_value=persisted_value):
                self.assertIn(
                    "csv_closeout.final_persisted_sample_seq must be an integer",
                    validate_csv_closeout(
                        build_metadata(
                            final_persisted_sample_seq=persisted_value,
                        ),
                        csv_path,
                        valid_rows,
                        valid_header,
                    ),
                )

    def test_runtime_observation_manifest_does_not_reread_historical_fact(self) -> None:
        row_total = 50_000
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            with fact_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=SPOT_OBSERVATION_FACT_COLUMNS,
                )
                writer.writeheader()
                for sequence in range(1, row_total + 1):
                    writer.writerow(
                        {
                            "spot_observation_key": f"service-1:{sequence}",
                            "spot_poll_seq": sequence,
                            "diagnostics_capture_status": "async_complete",
                            "diagnostics_binding_status": "same_poll",
                        }
                    )
            expected_sha256 = hashlib.sha256(fact_path.read_bytes()).hexdigest()
            runtime_writer = SpotObservationFactWriter(fact_path)
            realtime_rows = (
                {"spot_observation_key": "service-1:1"},
                {"spot_observation_key": f"service-1:{row_total}"},
            )
            expected_summary = summarize_spot_observation_fact(
                fact_path=fact_path,
                realtime_rows=realtime_rows,
            )

            with patch.object(
                Path,
                "open",
                side_effect=AssertionError("closeout reread historical fact"),
            ):
                summary = runtime_writer.manifest_summary(
                    realtime_rows=realtime_rows
                )

        self.assertEqual(summary, expected_summary)
        self.assertEqual(summary["row_count"], row_total)
        self.assertEqual(summary["sha256"], expected_sha256)
        self.assertEqual(summary["link_coverage"]["linked_rows"], 2)

    def test_observation_digest_read_failure_does_not_spool_or_duplicate_durable_row(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            runtime_writer = SpotObservationFactWriter(fact_path)
            original_open = Path.open

            def fail_fact_digest_read(
                path: Path,
                mode: str = "r",
                *args: object,
                **kwargs: object,
            ):
                if path == fact_path and mode == "rb":
                    raise OSError("digest read failed after append")
                return original_open(path, mode, *args, **kwargs)

            snapshot = {
                "spot_service_instance_id": "service-1",
                "spot_poll_seq": 1,
                "spot_last_poll_completed_at": "2026-07-29T05:00:00Z",
            }
            with patch.object(Path, "open", new=fail_fact_digest_read):
                first_write = runtime_writer.write_fact(snapshot)

            duplicate_write = runtime_writer.write_fact(snapshot)
            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertIsNotNone(first_write)
            self.assertIsNone(duplicate_write)
            self.assertEqual(len(rows), 1)
            self.assertEqual(runtime_writer.spool_pending_count(), 0)
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                runtime_writer.manifest_summary()

    def test_observation_post_append_stat_failure_does_not_spool_or_duplicate_durable_row(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            runtime_writer = SpotObservationFactWriter(fact_path)
            original_stat = Path.stat
            fact_stat_count = 0

            def fail_first_post_append_stat(
                path: Path,
                *args: object,
                **kwargs: object,
            ):
                nonlocal fact_stat_count
                if path == fact_path:
                    fact_stat_count += 1
                    if fact_stat_count == 3:
                        raise OSError("stat failed after durable append")
                return original_stat(path, *args, **kwargs)

            snapshot = {
                "spot_service_instance_id": "service-1",
                "spot_poll_seq": 1,
                "spot_last_poll_completed_at": "2026-07-29T05:00:00Z",
            }
            with patch.object(Path, "stat", new=fail_first_post_append_stat):
                first_write = runtime_writer.write_fact(snapshot)

            duplicate_write = runtime_writer.write_fact(snapshot)
            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertIsNotNone(first_write)
            self.assertIsNone(duplicate_write)
            self.assertEqual(len(rows), 1)
            self.assertEqual(runtime_writer.failure_count, 0)
            self.assertEqual(runtime_writer.spool_pending_count(), 0)
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                runtime_writer.manifest_summary()

    def test_observation_header_initialization_uses_runtime_manifest_owner(
        self,
    ) -> None:
        from backend.FacilityData.drivers import spot_api

        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            runtime_writer = SpotObservationFactWriter(fact_path)
            service = CSVLoggerService(require_runtime_manifest_state=True)
            snapshot = {
                "spot_service_instance_id": "service-1",
                "spot_poll_seq": 1,
                "spot_last_poll_completed_at": "2026-07-29T05:00:00Z",
            }

            with (
                patch.object(
                    spot_api,
                    "_spot_observation_fact_writer",
                    runtime_writer,
                ),
                patch.object(
                    spot_api.config,
                    "SPOT_OBSERVATION_FACT_ENABLED",
                    True,
                ),
            ):
                initialization_failures = (
                    service._ensure_spot_observation_fact_file(
                        fact_path,
                        enabled=True,
                    )
                )
                written = runtime_writer.write_fact(snapshot)
                summary = runtime_writer.manifest_summary()

            self.assertEqual(initialization_failures, 0)
            self.assertIsNotNone(written)
            self.assertEqual(summary["row_count"], 1)
            self.assertEqual(
                summary["sha256"],
                hashlib.sha256(fact_path.read_bytes()).hexdigest(),
            )

    def test_external_observation_header_interleaving_fails_manifest_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            runtime_writer = SpotObservationFactWriter(fact_path)
            initializer = SpotObservationFactWriter(
                fact_path,
                load_existing_keys=False,
            )
            snapshot = {
                "spot_service_instance_id": "service-1",
                "spot_poll_seq": 1,
                "spot_last_poll_completed_at": "2026-07-29T05:00:00Z",
            }

            self.assertTrue(initializer.ensure_initialized())
            self.assertIsNotNone(runtime_writer.write_fact(snapshot))
            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(runtime_writer.spool_pending_count(), 0)
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                runtime_writer.manifest_summary()

    def test_unowned_observation_write_before_closeout_fails_manifest_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            retained_writer = SpotObservationFactWriter(fact_path)
            self.assertTrue(retained_writer.ensure_initialized())
            discarded_writer = SpotObservationFactWriter(fact_path)
            snapshot = {
                "spot_service_instance_id": "service-1",
                "spot_poll_seq": 1,
                "spot_last_poll_completed_at": "2026-07-29T05:00:00Z",
            }

            self.assertIsNotNone(discarded_writer.write_fact(snapshot))
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                retained_writer.manifest_summary()

    def test_observation_manifest_fails_closed_when_temporary_sqlite_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_text("header\nrow\n", encoding="utf-8")

            with patch(
                "backend.FacilityData.spot_observation_fact.sqlite3.connect",
                side_effect=sqlite3.OperationalError("temporary storage unavailable"),
            ):
                with self.assertRaisesRegex(
                    sqlite3.OperationalError,
                    "temporary storage unavailable",
                ):
                    summarize_spot_observation_fact(fact_path=fact_path)

    def test_observation_manifest_fails_closed_on_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_bytes(
                b"spot_observation_key,spot_poll_seq\nservice-1:1,\xff\n"
            )

            with self.assertRaises(UnicodeDecodeError):
                summarize_spot_observation_fact(fact_path=fact_path)

    def test_observation_manifest_propagates_csv_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_text(
                "spot_observation_key,spot_poll_seq\nservice-1:1,1\n",
                encoding="utf-8-sig",
            )

            with (
                patch(
                    "backend.FacilityData.spot_observation_fact.csv.DictReader",
                    side_effect=csv.Error("malformed fact"),
                ),
                self.assertRaisesRegex(csv.Error, "malformed fact"),
            ):
                summarize_spot_observation_fact(fact_path=fact_path)

    def test_observation_manifest_propagates_transient_open_oserror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_text(
                "spot_observation_key,spot_poll_seq\nservice-1:1,1\n",
                encoding="utf-8-sig",
            )
            original_open = Path.open
            failure_injected = False

            def fail_first_text_open(
                path: Path,
                mode: str = "r",
                *args: object,
                **kwargs: object,
            ):
                nonlocal failure_injected
                if path == fact_path and mode == "r" and not failure_injected:
                    failure_injected = True
                    raise OSError("transient fact read failure")
                return original_open(path, mode, *args, **kwargs)

            with (
                patch.object(Path, "open", new=fail_first_text_open),
                self.assertRaisesRegex(OSError, "transient fact read failure"),
            ):
                summarize_spot_observation_fact(fact_path=fact_path)

    def test_observation_manifest_handles_missing_and_empty_fact_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            missing_path = root / "missing.csv"
            empty_path = root / "empty.csv"
            empty_path.write_bytes(b"")

            for fact_path in (missing_path, empty_path):
                with self.subTest(fact_path=fact_path.name):
                    summary = summarize_spot_observation_fact(
                        fact_path=fact_path,
                        realtime_rows=(
                            {"spot_observation_key": "service-1:1"},
                        ),
                    )

                    self.assertEqual(summary["row_count"], 0)
                    self.assertEqual(summary["distinct_observation_key_count"], 0)
                    self.assertEqual(
                        summary["link_coverage"],
                        {
                            "realtime_rows_with_observation_key": 1,
                            "linked_rows": 0,
                            "missing_fact_key_rows": 1,
                            "coverage_pct": 0.0,
                        },
                    )
                    self.assertEqual(
                        summary["sha256"],
                        hashlib.sha256(b"").hexdigest()
                        if fact_path.exists()
                        else "",
                    )

    def test_manifest_refresh_preserves_sidecar_when_temporary_sqlite_is_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            csv_path = log_path / "Factory_Integrated_Log_v2_test.csv"
            csv_path.write_text(
                "spot_observation_key\nservice-1:1\n",
                encoding="utf-8-sig",
            )
            metadata_path = csv_path.with_suffix(".metadata.json")
            original_metadata = b'{"sentinel":"preserved"}\n'
            metadata_path.write_bytes(original_metadata)
            fact_path = log_path / "spot_observation_fact.csv"
            fact_path.write_text(
                "spot_observation_key,spot_poll_seq\nservice-1:1,1\n",
                encoding="utf-8-sig",
            )
            service = CSVLoggerService()

            with patch(
                "backend.FacilityData.drivers.spot_api."
                "get_spot_observation_fact_manifest_summary",
                side_effect=sqlite3.OperationalError(
                    "runtime manifest state unavailable"
                ),
            ):
                refreshed = service.refresh_spot_observation_fact_manifest_for_csv(
                    csv_path
                )

            self.assertIsNone(refreshed)
            self.assertEqual(metadata_path.read_bytes(), original_metadata)

    def test_manifest_refresh_preserves_sidecar_on_invalid_fact_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            csv_path = log_path / "Factory_Integrated_Log_v2_test.csv"
            csv_path.write_text(
                "spot_observation_key\nservice-1:1\n",
                encoding="utf-8-sig",
            )
            metadata_path = csv_path.with_suffix(".metadata.json")
            original_metadata = b'{"sentinel":"preserved"}\n'
            metadata_path.write_bytes(original_metadata)
            fact_path = log_path / "spot_observation_fact.csv"
            fact_path.write_bytes(
                b"spot_observation_key,spot_poll_seq\nservice-1:1,\xff\n"
            )
            service = CSVLoggerService()

            with patch(
                "backend.FacilityData.drivers.spot_api."
                "get_spot_observation_fact_health",
                return_value={"enabled": False},
            ):
                refreshed = service.refresh_spot_observation_fact_manifest_for_csv(
                    csv_path
                )

            self.assertIsNone(refreshed)
            self.assertEqual(metadata_path.read_bytes(), original_metadata)

    def test_close_invalidates_stale_manifest_when_temporary_sqlite_is_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            csv_path = log_path / "Factory_Integrated_Log_v2_test.csv"
            csv_path.write_text(
                "spot_observation_key\nservice-1:1\n",
                encoding="utf-8-sig",
            )
            metadata_path = csv_path.with_suffix(".metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "spot_observation_fact_manifest": {
                            "row_count": 1,
                            "sha256": "unsafe-stale-hash",
                        }
                    }
                ),
                encoding="utf-8",
            )
            fact_path = log_path / "spot_observation_fact.csv"
            fact_path.write_text(
                "spot_observation_key,spot_poll_seq\nservice-1:1,1\n",
                encoding="utf-8-sig",
            )
            service = CSVLoggerService()
            service._current_v2_csv_path = csv_path

            with patch(
                "backend.FacilityData.drivers.spot_api."
                "get_spot_observation_fact_manifest_summary",
                side_effect=sqlite3.OperationalError(
                    "runtime manifest state unavailable"
                ),
            ):
                closed_cleanly = service._close_v2_file(None)

            payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertFalse(closed_cleanly)
        self.assertTrue(service._runtime_write_failure_observed)
        self.assertNotIn("spot_observation_fact_manifest", payload)
        self.assertEqual(
            payload["spot_observation_fact_closeout"],
            {
                "finalized": False,
                "writes_drained": True,
                "reason": "manifest-refresh-failed",
            },
        )

    def test_close_invalidates_stale_manifest_on_invalid_fact_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            csv_path = log_path / "Factory_Integrated_Log_v2_test.csv"
            csv_path.write_text(
                "spot_observation_key\nservice-1:1\n",
                encoding="utf-8-sig",
            )
            metadata_path = csv_path.with_suffix(".metadata.json")
            metadata_path.write_text(
                json.dumps(
                    {
                        "spot_observation_fact_manifest": {
                            "row_count": 1,
                            "sha256": "unsafe-stale-hash",
                        }
                    }
                ),
                encoding="utf-8",
            )
            fact_path = log_path / "spot_observation_fact.csv"
            fact_path.write_bytes(
                b"spot_observation_key,spot_poll_seq\nservice-1:1,\xff\n"
            )
            service = CSVLoggerService()
            service._current_v2_csv_path = csv_path

            with patch(
                "backend.FacilityData.drivers.spot_api."
                "get_spot_observation_fact_health",
                return_value={"enabled": False},
            ):
                closed_cleanly = service._close_v2_file(None)

            payload = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertFalse(closed_cleanly)
        self.assertTrue(service._runtime_write_failure_observed)
        self.assertNotIn("spot_observation_fact_manifest", payload)
        self.assertEqual(
            payload["spot_observation_fact_closeout"],
            {
                "finalized": False,
                "writes_drained": True,
                "reason": "manifest-refresh-failed",
            },
        )

    def test_closeout_header_initialization_does_not_index_historical_fact_keys(self) -> None:
        from backend.FacilityData.drivers import spot_api

        with tempfile.TemporaryDirectory() as temp_dir:
            fact_path = Path(temp_dir) / "spot_observation_fact.csv"
            fact_path.write_text(
                "\ufeff" + ",".join(SPOT_OBSERVATION_FACT_COLUMNS) + "\n",
                encoding="utf-8",
            )
            runtime_writer = SpotObservationFactWriter(fact_path)
            service = CSVLoggerService(require_runtime_manifest_state=True)

            with (
                patch.object(
                    spot_api,
                    "_spot_observation_fact_writer",
                    runtime_writer,
                ),
                patch.object(
                    SpotObservationFactWriter,
                    "_load_manifest_state_from_output",
                    side_effect=AssertionError(
                        "closeout indexed historical observation keys"
                    ),
                ) as load_manifest_state,
            ):
                failure_count = service._ensure_spot_observation_fact_file(
                    fact_path,
                    enabled=True,
                )

        self.assertEqual(failure_count, 0)
        load_manifest_state.assert_not_called()

    def test_strict_manifest_mismatch_preserves_v2_csv_on_log_path_fallback(
        self,
    ) -> None:
        from backend.FacilityData.drivers import spot_api

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            configured_path = root / "configured"
            fallback_path = root / "fallback"
            configured_path.mkdir()
            runtime_writer = SpotObservationFactWriter(
                configured_path / "spot_observation_fact.csv"
            )
            service = CSVLoggerService(require_runtime_manifest_state=True)
            service.fallback_log_dir = fallback_path
            service.apply_config(
                log_path=configured_path,
                auto_save=True,
                csv_v1_enabled=False,
                csv_v2_enabled=True,
                csv_v2_sidecar_enabled=True,
            )
            original_ensure_dir = service._ensure_dir

            def fail_configured_log_dir(path: Path) -> bool:
                if Path(path) == configured_path:
                    return False
                return original_ensure_dir(path)

            with (
                patch.object(service, "_ensure_dir", side_effect=fail_configured_log_dir),
                patch.object(spot_api.config, "LOG_PATH", configured_path),
                patch.object(
                    spot_api.config,
                    "SPOT_OBSERVATION_FACT_ENABLED",
                    True,
                ),
                patch.object(
                    spot_api,
                    "_spot_observation_fact_writer",
                    runtime_writer,
                ),
                patch.object(spot_api, "_spot_image_capture_writer", None),
                patch.object(spot_api, "_spot_image_capture_writer_signature", None),
            ):
                handle, writer = service._open_v2_log_file(
                    "20260729_150000",
                    "Factory_Integrated_Log_v2",
                )
                self.assertIsNotNone(handle)
                self.assertIsNotNone(writer)
                assert handle is not None
                assert writer is not None
                writer.writerow([""] * len(service._get_active_v2_contract().columns))
                handle.flush()
                csv_path = Path(handle.name)
                service._close_file(handle)

            metadata = json.loads(
                csv_path.with_suffix(".metadata.json").read_text(encoding="utf-8")
            )
            csv_size = csv_path.stat().st_size

        self.assertEqual(csv_path.parent, fallback_path)
        self.assertGreater(csv_size, 0)
        self.assertTrue(service._runtime_write_failure_observed)
        self.assertNotIn("spot_observation_fact_manifest", metadata)
        self.assertNotIn("spot_image_fact_manifest", metadata)
        self.assertEqual(
            metadata["spot_observation_fact_closeout"]["reason"],
            "runtime-manifest-unavailable-at-open",
        )
        self.assertEqual(
            metadata["spot_image_fact_closeout"]["reason"],
            "runtime-manifest-unavailable-at-open",
        )

    def test_live_log_path_change_keeps_v2_csv_when_observation_writer_is_old(
        self,
    ) -> None:
        from backend.FacilityData.drivers import spot_api

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            previous_path = root / "previous"
            next_path = root / "next"
            previous_path.mkdir()
            next_path.mkdir()
            runtime_writer = SpotObservationFactWriter(
                previous_path / "spot_observation_fact.csv"
            )
            self.assertTrue(runtime_writer.ensure_initialized())
            service = CSVLoggerService(require_runtime_manifest_state=True)
            service.fallback_log_dir = next_path
            service.apply_config(
                log_path=next_path,
                auto_save=True,
                csv_v1_enabled=False,
                csv_v2_enabled=True,
                csv_v2_sidecar_enabled=True,
            )

            with (
                patch.object(spot_api.config, "LOG_PATH", next_path),
                patch.object(
                    spot_api.config,
                    "SPOT_OBSERVATION_FACT_ENABLED",
                    True,
                ),
                patch.object(
                    spot_api,
                    "_spot_observation_fact_writer",
                    runtime_writer,
                ),
                patch.object(spot_api, "_spot_image_capture_writer", None),
                patch.object(spot_api, "_spot_image_capture_writer_signature", None),
            ):
                # This case isolates an old observation writer with a ready
                # image writer already bound to the new configuration.
                spot_api._get_spot_image_capture_writer()
                handle, writer = service._open_v2_log_file(
                    "20260729_160000",
                    "Factory_Integrated_Log_v2",
                )
                self.assertIsNotNone(handle)
                self.assertIsNotNone(writer)
                assert handle is not None
                assert writer is not None
                writer.writerow([""] * len(service._get_active_v2_contract().columns))
                handle.flush()
                csv_path = Path(handle.name)
                service._close_file(handle)

            metadata = json.loads(
                csv_path.with_suffix(".metadata.json").read_text(encoding="utf-8")
            )
            csv_size = csv_path.stat().st_size

        self.assertEqual(csv_path.parent, next_path)
        self.assertGreater(csv_size, 0)
        self.assertTrue(service._runtime_write_failure_observed)
        self.assertNotIn("spot_observation_fact_manifest", metadata)
        self.assertEqual(
            metadata["spot_observation_fact_closeout"]["reason"],
            "runtime-manifest-unavailable-at-open",
        )
        self.assertIn("spot_image_fact_manifest", metadata)

    def test_image_manifest_hash_does_not_load_the_entire_fact_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            fact_path.write_text("header\nrow-1\nrow-2\n", encoding="utf-8")

            with patch.object(Path, "read_bytes", side_effect=AssertionError("unbounded read")):
                manifest = build_spot_image_fact_manifest(
                    log_path=log_path,
                    capture_root=log_path / "spot_images",
                    enabled=True,
                    mode="all",
                )

        self.assertEqual(manifest["row_count"], 2)
        self.assertRegex(str(manifest["sha256"]), r"^[0-9a-f]{64}$")

    def test_image_manifest_uses_runtime_stats_without_closeout_file_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            fact_path.write_text("header\nrow-1\nrow-2\n", encoding="utf-8")
            expected_sha256 = hashlib.sha256(fact_path.read_bytes()).hexdigest()

            with patch(
                "backend.FacilityData.spot_image_fact._fact_file_stats",
                side_effect=AssertionError("closeout rescanned image fact"),
            ):
                manifest = build_spot_image_fact_manifest(
                    log_path=log_path,
                    capture_root=log_path / "spot_images",
                    enabled=True,
                    mode="all",
                    runtime_stats={
                        "fact_row_count": 2,
                        "fact_sha256": expected_sha256,
                        "fact_manifest_state_ready": True,
                    },
                )

        self.assertEqual(manifest["row_count"], 2)
        self.assertEqual(manifest["sha256"], expected_sha256)

    def test_image_closeout_rejects_unready_runtime_state_without_fact_scan(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            fact_path.write_text("header\nrow-1\n", encoding="utf-8")
            service = CSVLoggerService(require_runtime_manifest_state=True)

            with (
                patch(
                    "backend.FacilityData.drivers.spot_api."
                    "get_spot_image_capture_manifest_stats",
                    return_value={
                        "fact_row_count": 1,
                        "fact_sha256": None,
                        "fact_manifest_state_ready": False,
                    },
                ),
                patch(
                    "backend.FacilityData.spot_image_fact._fact_file_stats",
                    side_effect=AssertionError("production closeout rescanned image fact"),
                ) as fact_file_stats,
                self.assertRaisesRegex(
                    RuntimeError,
                    "runtime manifest state is unavailable",
                ),
            ):
                service.write_spot_image_fact_final_manifest(log_path)

            fact_file_stats.assert_not_called()

    def test_image_capture_identity_conflict_preserves_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=log_path, capture_root=log_path / "spot_images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8first-capture\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            first = writer.write_capture(**args)
            args["capture_id"] = first["spot_image_capture_id"]
            originals = {path: path.read_bytes() for path in log_path.rglob("*") if path.is_file()}
            with self.assertRaisesRegex(RuntimeError, "capture identity conflicts"):
                writer.write_capture(**dict(args, image_bytes=b"\xff\xd8other-capture\xff\xd9"))
            with self.assertRaisesRegex(RuntimeError, "capture identity conflicts"):
                writer.write_capture(**dict(args, source="different-acquisition"))
            self.assertEqual({path: path.read_bytes() for path in originals}, originals)
            self.assertEqual(writer.write_capture(**args), first)
            restarted = SpotImageCaptureWriter(log_path=log_path, capture_root=log_path / "spot_images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "capture identity conflicts"):
                restarted.write_capture(**dict(args, image_age_ms=500.0))
            self.assertEqual(restarted.write_capture(**args), first)
            self.assertEqual(writer.fact_row_count, 1)
            self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_image_fact_retry_preserves_verified_jpeg(self) -> None:
        for target_size in (1024**2 - 1, 1024**2 + 1, 1_500_000):
            with self.subTest(target_size=target_size):
                data = io.BytesIO()
                Image.new("RGB", (2, 2), (4, 5, 6)).save(data, format="JPEG")
                base = data.getvalue()
                remaining = target_size - len(base)
                comments = bytearray()
                while remaining:
                    size = min(65_537, remaining)
                    if 0 < remaining - size < 4:
                        size -= 4
                    comments.extend(b"\xff\xfe" + (size - 2).to_bytes(2, "big") + b"x" * (size - 4))
                    remaining -= size
                jpeg = base[:2] + comments + base[2:]
                self.assertEqual(len(jpeg), target_size)
                with Image.open(io.BytesIO(jpeg)) as decoded:
                    decoded.load()
                    self.assertEqual(decoded.size, (2, 2))
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
                    args = dict(image_bytes=jpeg, captured_at=1782910800.123456,
                                source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                                link_checked_at=None, observation_snapshot=None)
                    original_open = Path.open

                    def fail_fact_append(path, mode="r", *open_args, **kwargs):
                        if path == writer.fact_path and mode == "ab":
                            raise OSError("injected fact failure after JPEG commit")
                        return original_open(path, mode, *open_args, **kwargs)

                    with patch.object(Path, "open", new=fail_fact_append):
                        with self.assertRaisesRegex(OSError, "injected fact failure"):
                            writer.write_capture(**args)
                    image_path, = root.rglob("*.jpg")
                    self.assertEqual(image_path.read_bytes(), jpeg)
                    os.utime(image_path, ns=(1_700_000_000_123_456_000, 1_700_000_000_123_456_000))
                    before = image_path.stat()
                    fact = writer.write_capture(**args)
                    self.assertEqual(image_path.stat().st_mtime_ns, before.st_mtime_ns,
                                     "verified JPEG must not be rewritten when only fact append failed")
                    self.assertEqual(image_path.read_bytes(), jpeg)
                    with writer.fact_path.open(encoding="utf-8-sig", newline="") as handle:
                        self.assertEqual(list(csv.DictReader(handle)), [fact])
                    self.assertEqual(fact["spot_image_capture_id"], image_path.stem)
                    self.assertEqual(fact["spot_image_sha256"], hashlib.sha256(jpeg).hexdigest())
                    self.assertEqual(writer.written_count, 1)
                    self.assertEqual(writer.write_capture(**args), fact)
                    self.assertEqual(writer.fact_row_count, 1)

    def test_image_file_conflicts_preserve_jpeg_and_fact(self) -> None:
        for recorded in (False, True):
            for shortened in (False, True):
                with self.subTest(recorded=recorded, shortened=shortened), tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
                    args = dict(image_bytes=b"\xff\xd8original-jpeg\xff\xd9", captured_at=1782910800.123456,
                                source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                                link_checked_at=None, observation_snapshot=None)
                    opened = Path.open

                    def fail_append(path, mode="r", *open_args, **kwargs):
                        if path == writer.fact_path and mode == "ab":
                            raise OSError("fact not recorded")
                        return opened(path, mode, *open_args, **kwargs)

                    if recorded:
                        writer.write_capture(**args)
                    else:
                        with patch.object(Path, "open", new=fail_append), self.assertRaises(OSError):
                            writer.write_capture(**args)
                    image_path, = root.rglob("*.jpg")
                    damaged = args["image_bytes"][:-1] if shortened else b"?" + args["image_bytes"][1:]
                    image_path.write_bytes(damaged)
                    originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                    with self.assertRaisesRegex(RuntimeError, "capture file is uncertain"):
                        writer.write_capture(**args)
                    self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
                    self.assertEqual(writer.written_count, int(recorded))

    def test_partial_image_fact_append_blocks_further_writes(self) -> None:
        for failure_mode in ("partial", "short", "close"):
            with self.subTest(failure_mode=failure_mode):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
                    args = dict(image_bytes=b"\xff\xd8partial-fact\xff\xd9", captured_at=1782910800.123456,
                                source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                                link_checked_at=None, observation_snapshot=None)
                    opened = Path.open

                    class PartialAppend:
                        def __init__(self, handle):
                            self.handle = handle

                        def fileno(self):
                            return self.handle.fileno()

                        def __enter__(self):
                            return self

                        def __exit__(self, *exc):
                            outcome = self.handle.__exit__(*exc)
                            if failure_mode == "close":
                                raise OSError("injected fact close failure")
                            return outcome

                        def write(self, payload):
                            if failure_mode == "close":
                                return self.handle.write(payload)
                            count = self.handle.write(payload[:37])
                            self.handle.flush()
                            if failure_mode == "short":
                                return count
                            raise OSError("injected partial fact append")

                    def partial_open(path, mode="r", *open_args, **kwargs):
                        handle = opened(path, mode, *open_args, **kwargs)
                        return PartialAppend(handle) if path == writer.fact_path and mode == "ab" else handle

                    with patch.object(Path, "open", new=partial_open):
                        with self.assertRaisesRegex(OSError, "partial fact append|truncated|fact close failure"):
                            writer.write_capture(**args)
                    if failure_mode == "close":
                        self.assertGreater(writer.fact_path.stat().st_size, 37)
                    else:
                        self.assertEqual(writer.fact_path.stat().st_size, 37)
                    originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                    for timestamp in (args["captured_at"], args["captured_at"] + 1):
                        with self.assertRaisesRegex(RuntimeError, "fact append is uncertain"):
                            writer.write_capture(**dict(args, captured_at=timestamp))
                    self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
                    self.assertEqual(writer.written_count, 0)
                    with self.assertRaisesRegex(RuntimeError, "manifest state is unavailable"):
                        _ = writer.fact_sha256

    def test_image_fact_header_read_failure_preserves_original_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8header-read\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            first = writer.write_capture(**args)
            original = writer.fact_path.read_bytes()
            opened = Path.open

            def fail_header_read(path, mode="r", *open_args, **kwargs):
                if path == writer.fact_path and mode == "r":
                    raise PermissionError(13, "temporary fact header read failure")
                return opened(path, mode, *open_args, **kwargs)

            second_args = dict(args, captured_at=args["captured_at"] + 1)
            with patch.object(Path, "open", new=fail_header_read):
                with self.assertRaisesRegex(PermissionError, "header read failure"):
                    writer.write_capture(**second_args)
            self.assertEqual(writer.fact_path.read_bytes(), original)
            self.assertEqual(list(root.glob("*.schema-mismatch.csv")), [])
            images = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in root.rglob("*.jpg")}
            self.assertEqual(len(images), 2)
            second = writer.write_capture(**second_args)
            self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in images}, images)
            with writer.fact_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_image_capture_id"] for row in rows],
                             [first["spot_image_capture_id"], second["spot_image_capture_id"]])
            self.assertEqual(writer.fact_sha256, hashlib.sha256(writer.fact_path.read_bytes()).hexdigest())

    def test_image_fact_lookup_read_failure_never_becomes_missing_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8lookup-read\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            expected = writer.write_capture(**args)
            originals = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                         for path in root.rglob("*") if path.is_file()}
            recreated = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            opened = Path.open
            failures = []

            def fail_lookup_once(path, mode="r", *open_args, **kwargs):
                if path == writer.fact_path and mode == "r" and not failures:
                    failures.append(path)
                    raise PermissionError(13, "temporary fact lookup read failure")
                return opened(path, mode, *open_args, **kwargs)

            with patch.object(Path, "open", new=fail_lookup_once):
                with self.assertRaisesRegex(PermissionError, "lookup read failure"):
                    recreated.write_capture(**args)
                self.assertEqual(recreated.write_capture(**args), expected)
            self.assertEqual({path: (path.read_bytes(), path.stat().st_mtime_ns) for path in originals}, originals)
            self.assertEqual(recreated.fact_row_count, 1)
            self.assertEqual(recreated.fact_sha256, hashlib.sha256(writer.fact_path.read_bytes()).hexdigest())

    def test_image_partial_history_blocks_restarted_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8history-capture\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            fact = writer.write_capture(**args)
            reopened = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            self.assertEqual(reopened.write_capture(**args), fact)
            self.assertEqual(reopened.fact_row_count, 1)
            with writer.fact_path.open("ab") as handle:
                handle.write(b"spotimg_20260701T120000000000Z_partial,")
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

            restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                restarted.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
            self.assertFalse(restarted.try_manifest_stats()[2])
            again = SpotImageCaptureWriter(log_path=root, capture_root=root / "new_images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                again.write_capture(**args)

    def test_image_unterminated_history_never_accepts_new_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8unterminated-history\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            fact = writer.write_capture(**args)
            valid = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            self.assertEqual(valid.write_capture(**args), fact)
            self.assertEqual(valid.fact_row_count, 1)
            original = writer.fact_path.read_bytes()
            self.assertTrue(original.endswith(b"\r\n"))
            writer.fact_path.write_bytes(original[:-2])
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                restarted.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertFalse(restarted.try_manifest_stats()[2])
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)

    def test_image_unknown_history_schema_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8unknown-schema\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            writer.write_capture(**args)
            original = writer.fact_path.read_bytes()
            writer.fact_path.write_bytes(original.replace(b"spot_image_capture_id", b"unknown_capture_field", 1))
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                restarted.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertFalse(restarted.try_manifest_stats()[2])
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
            self.assertEqual(list(root.glob("*.schema-mismatch.csv")), [])

    def test_image_oversized_history_row_blocks_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8bounded-row\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            expected = writer.write_capture(**args)
            valid = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            self.assertEqual(valid.write_capture(**args), expected)
            self.assertTrue(valid.try_manifest_stats()[2])
            oversized = dict(expected)
            for column in SPOT_IMAGE_FACT_COLUMNS[-12:]:
                oversized[column] = "x" * 100_000
            with writer.fact_path.open("a", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=SPOT_IMAGE_FACT_COLUMNS).writerow(oversized)
            self.assertGreater(writer.fact_path.stat().st_size, 1024 * 1024)
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

            restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            self.assertFalse(restarted.try_manifest_stats()[2], "oversized fact row was accepted as ready")
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                restarted.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)

    def test_image_history_lookup_has_bounded_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8bounded-history\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            fact = writer.write_capture(**args)
            with writer.fact_path.open("a", encoding="utf-8", newline="") as handle:
                output = csv.DictWriter(handle, fieldnames=SPOT_IMAGE_FACT_COLUMNS)
                for index in range(12_000):
                    capture_id = f"spotimg_20260701T120000000000Z_{index:032x}"
                    row = dict(fact, spot_image_capture_id=capture_id,
                               spot_image_path=fact["spot_image_path"].replace(fact["spot_image_capture_id"], capture_id))
                    output.writerow(row)
            before = hashlib.sha256(writer.fact_path.read_bytes()).hexdigest()
            restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
            tracemalloc.start()
            try:
                actual = restarted.write_capture(**args)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertEqual(actual, fact)
            self.assertLess(peak, 4 * 1024 * 1024, "history lookup retained the complete fact file in memory")
            self.assertEqual(hashlib.sha256(writer.fact_path.read_bytes()).hexdigest(), before)
            self.assertEqual(restarted.fact_row_count, 12_001)

            # Evict any recent-row cache, then retry a current capture whose
            # JPEG disappeared. The historical lookup must prevent a new row.
            current = dict(args, captured_at=time.time() + 1)
            first_current = restarted.write_capture(**current)
            for offset in range(1, 4):
                restarted.write_capture(**dict(current, captured_at=current["captured_at"] + offset))
            (root / first_current["spot_image_path"]).unlink()
            self.assertEqual(restarted.write_capture(**current), first_current)
            self.assertEqual(restarted.fact_row_count, 12_005)
            with writer.fact_path.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(sum(1 for _ in csv.DictReader(handle)), 12_005)

    def test_image_history_corruption_guards_preserve_originals(self) -> None:
        for failure in ("utf8", "quotes", "extra_column", "blank_row", "duplicate_id", "lookup_utf8"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                args = dict(image_bytes=b"\xff\xd8corruption-guards\xff\xd9", captured_at=1782910800.123456,
                            source_url="http://synthetic.invalid/image.jpg", source='test\nline,"quoted"',
                            image_age_ms=0.0, link_checked_at=None, observation_snapshot=None)
                writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
                fact = writer.write_capture(**args)
                valid = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
                self.assertEqual(valid.write_capture(**args), fact)
                self.assertEqual(valid.fact_row_count, 1)
                original = writer.fact_path.read_bytes()
                row = original.split(b"\r\n", 1)[1]
                corruptions = {
                    "utf8": original + b"\xff\r\n",
                    "quotes": original + b'"unterminated\r\n',
                    "extra_column": original + row[:-2] + b",extra\r\n",
                    "blank_row": original + b"\r\n",
                    "duplicate_id": original + row,
                    "lookup_utf8": original + b"\xff\r\n",
                }
                if failure == "lookup_utf8":
                    restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
                writer.fact_path.write_bytes(corruptions[failure])
                if failure != "lookup_utf8":
                    restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "spot_images", retention_days=0)
                originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                    restarted.write_capture(**args)
                self.assertFalse(restarted.try_manifest_stats()[2])
                self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
                with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                    restarted.write_capture(**dict(args, captured_at=args["captured_at"] + 1))

    def test_image_uncertainty_survives_writer_recreation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8close-failed\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            opened = Path.open

            class CloseFailure:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    return self.handle

                def __exit__(self, *exc):
                    self.handle.__exit__(*exc)
                    raise OSError("injected complete append close failure")

            def fail_close(path, mode="r", *open_args, **kwargs):
                handle = opened(path, mode, *open_args, **kwargs)
                return CloseFailure(handle) if path == writer.fact_path and mode == "ab" else handle

            with patch.object(Path, "open", new=fail_close):
                with self.assertRaisesRegex(OSError, "close failure"):
                    writer.write_capture(**args)
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            recreated = SpotImageCaptureWriter(log_path=root, capture_root=root / "new-images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "fact append is uncertain"):
                recreated.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
            with self.assertRaisesRegex(RuntimeError, "manifest state is unavailable"):
                _ = recreated.fact_sha256
            independent = SpotImageCaptureWriter(log_path=root / "other", capture_root=root / "other/images")
            independent.write_capture(**args)
            self.assertEqual(independent.written_count, 1)

    def test_uncertain_image_path_latches_are_bounded_without_eviction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(image_fact, "_SPOT_IMAGE_UNCERTAIN_FACT_KEYS", set()), \
             patch.object(image_fact, "_SPOT_IMAGE_UNCERTAIN_FACT_KEY_LIMIT", 2), \
             patch.object(image_fact, "_SPOT_IMAGE_UNCERTAIN_FACT_KEYS_OVERFLOW", False):
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8bounded\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="test", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            opened = Path.open

            class PartialAppend:
                def __init__(self, handle):
                    self.handle = handle

                def fileno(self):
                    return self.handle.fileno()

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return self.handle.__exit__(*exc)

                def write(self, payload):
                    self.handle.write(payload[:37])
                    self.handle.flush()
                    raise OSError("partial write")

            def fail_append(path, mode="r", *open_args, **kwargs):
                handle = opened(path, mode, *open_args, **kwargs)
                return PartialAppend(handle) if path.name == "spot_image_fact.csv" and mode == "ab" else handle

            first_keys = None
            for index in range(3):
                destination = root / str(index)
                writer = SpotImageCaptureWriter(log_path=destination, capture_root=destination / "images")
                with patch.object(Path, "open", new=fail_append):
                    with self.assertRaisesRegex(OSError, "partial write"):
                        writer.write_capture(**args)
                self.assertEqual(writer.fact_path.stat().st_size, 37)
                self.assertLessEqual(len(image_fact._SPOT_IMAGE_UNCERTAIN_FACT_KEYS), 2)
                if index == 1:
                    first_keys = set(image_fact._SPOT_IMAGE_UNCERTAIN_FACT_KEYS)
            self.assertEqual(image_fact._SPOT_IMAGE_UNCERTAIN_FACT_KEYS, first_keys)
            self.assertTrue(all(len(key) == 32 for key in image_fact._SPOT_IMAGE_UNCERTAIN_FACT_KEYS))
            self.assertTrue(image_fact._SPOT_IMAGE_UNCERTAIN_FACT_KEYS_OVERFLOW)
            writer = SpotImageCaptureWriter(log_path=root / "new", capture_root=root / "new/images")
            with self.assertRaisesRegex(RuntimeError, "fact append is uncertain"):
                writer.write_capture(**args)
            self.assertFalse((root / "new").exists())

    def test_image_digest_read_failure_does_not_duplicate_durable_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            runtime_writer = SpotImageCaptureWriter(
                log_path=log_path,
                capture_root=log_path / "spot_images",
            )
            original_open = Path.open

            def fail_fact_digest_read(
                path: Path,
                mode: str = "r",
                *args: object,
                **kwargs: object,
            ):
                if path == fact_path and mode == "rb":
                    raise OSError("digest read failed after append")
                return original_open(path, mode, *args, **kwargs)

            capture_args = {
                "image_bytes": b"\xff\xd8digest-failure\xff\xd9",
                "captured_at": 1782910800.123456,
                "source_url": "http://spot.local/image.jpg",
                "source": "test",
                "image_age_ms": 0.0,
                "link_checked_at": None,
                "observation_snapshot": None,
            }
            with patch.object(Path, "open", new=fail_fact_digest_read):
                first_fact = runtime_writer.write_capture(**capture_args)

            duplicate_fact = runtime_writer.write_capture(**capture_args)
            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(duplicate_fact, first_fact)
            self.assertEqual(len(rows), 1)
            self.assertEqual(runtime_writer.fact_row_count, 1)
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                _ = runtime_writer.fact_sha256

    def test_image_replaced_fact_is_rejected_before_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8file-identity\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="original-capture", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            fact = writer.write_capture(**args)
            self.assertEqual(writer.write_capture(**args), fact)
            before = writer.fact_path.stat()
            original = writer.fact_path.read_bytes()
            changed = original.replace(b"original-capture", b"external-capture", 1)
            self.assertNotEqual(changed, original)
            self.assertEqual(len(changed), len(original))
            replacement = root / "external.csv"
            replacement.write_bytes(changed)
            os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
            replacement.replace(writer.fact_path)
            after = writer.fact_path.stat()
            self.assertEqual((after.st_size, after.st_mtime_ns), (before.st_size, before.st_mtime_ns))
            self.assertNotEqual(after.st_ino, before.st_ino)
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                writer.write_capture(**args)
            self.assertFalse(writer.try_manifest_stats()[2])
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                writer.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)

    def test_image_fact_replacement_during_append_open_preserves_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8open-race\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="original-capture", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer.write_capture(**args)
            original = writer.fact_path.read_bytes()
            replacement_bytes = original.replace(b"original-capture", b"external-capture", 1)
            self.assertNotEqual(replacement_bytes, original)
            replacement = root / "replacement.csv"
            replacement.write_bytes(replacement_bytes)
            opened = Path.open
            replaced = False

            def replace_before_open(path, mode="r", *open_args, **kwargs):
                nonlocal replaced
                if path == writer.fact_path and mode == "ab" and not replaced:
                    replacement.replace(path)
                    replaced = True
                return opened(path, mode, *open_args, **kwargs)

            with patch.object(Path, "open", new=replace_before_open):
                with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                    writer.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertTrue(replaced)
            self.assertEqual(writer.fact_path.read_bytes(), replacement_bytes)
            self.assertEqual(writer.written_count, 1)
            self.assertFalse(writer.try_manifest_stats()[2])
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                writer.write_capture(**args)

    def test_image_fact_replacement_after_close_stays_uncertain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            args = dict(image_bytes=b"\xff\xd8close-race\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="original-capture", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer.write_capture(**args)
            opened = Path.open
            replacements = []

            class ReplaceOnClose:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    return self.handle

                def __exit__(self, *exc):
                    result = self.handle.__exit__(*exc)
                    contents = writer.fact_path.read_bytes().replace(b"original-capture", b"external-capture", 1)
                    replacement = root / "replacement.csv"
                    replacement.write_bytes(contents)
                    replacement.replace(writer.fact_path)
                    replacements.append(contents)
                    return result

            def replace_after_close(path, mode="r", *open_args, **kwargs):
                handle = opened(path, mode, *open_args, **kwargs)
                return ReplaceOnClose(handle) if path == writer.fact_path and mode == "ab" else handle

            with patch.object(Path, "open", new=replace_after_close):
                with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                    writer.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
            self.assertEqual(len(replacements), 1)
            self.assertEqual(writer.fact_path.read_bytes(), replacements[0])
            self.assertFalse(writer.try_manifest_stats()[2])
            self.assertEqual(writer.written_count, 1)
            recreated = SpotImageCaptureWriter(log_path=root, capture_root=root / "new-images", retention_days=0)
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                recreated.write_capture(**args)
            self.assertEqual(writer.fact_path.read_bytes(), replacements[0])

    def test_image_active_fact_change_guards(self) -> None:
        for mutation in ("in_place", "truncate", "delete", "directory"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
                args = dict(image_bytes=b"\xff\xd8change-guards\xff\xd9", captured_at=1782910800.123456,
                            source_url="http://synthetic.invalid/image.jpg", source="original-capture", image_age_ms=0.0,
                            link_checked_at=None, observation_snapshot=None)
                fact = writer.write_capture(**args)
                self.assertEqual(writer.write_capture(**args), fact)
                before = writer.fact_path.stat()
                content = writer.fact_path.read_bytes()
                if mutation == "in_place":
                    writer.fact_path.write_bytes(content.replace(b"original-capture", b"external-capture", 1))
                    os.utime(writer.fact_path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
                elif mutation == "truncate":
                    writer.fact_path.write_bytes(content[:-13])
                else:
                    writer.fact_path.unlink()
                    if mutation == "directory":
                        writer.fact_path.mkdir()
                originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
                with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                    writer.write_capture(**dict(args, captured_at=args["captured_at"] + 1))
                self.assertFalse(writer.try_manifest_stats()[2])
                self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)
                self.assertEqual(writer.written_count, 1)

    def test_image_initialization_change_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = dict(image_bytes=b"\xff\xd8init-race\xff\xd9", captured_at=1782910800.123456,
                        source_url="http://synthetic.invalid/image.jpg", source="original-capture", image_age_ms=0.0,
                        link_checked_at=None, observation_snapshot=None)
            writer = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            writer.write_capture(**args)
            replacement = root / "replacement.csv"
            replacement.write_bytes(writer.fact_path.read_bytes().replace(b"original-capture", b"external-capture", 1))
            opened = Path.open
            replaced = False

            def replace_before_rows(path, mode="r", *open_args, **kwargs):
                nonlocal replaced
                if path == writer.fact_path and mode == "r" and not replaced:
                    replacement.replace(path)
                    replaced = True
                return opened(path, mode, *open_args, **kwargs)

            with patch.object(Path, "open", new=replace_before_rows):
                restarted = SpotImageCaptureWriter(log_path=root, capture_root=root / "images", retention_days=0)
            self.assertTrue(replaced)
            originals = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertFalse(restarted.try_manifest_stats()[2])
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                restarted.write_capture(**args)
            self.assertEqual({path: path.read_bytes() for path in root.rglob("*") if path.is_file()}, originals)

    def test_image_manifest_fails_closed_after_external_fact_append(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            runtime_writer = SpotImageCaptureWriter(
                log_path=log_path,
                capture_root=log_path / "spot_images",
            )
            first_fact = runtime_writer.write_capture(
                image_bytes=b"\xff\xd8first-capture\xff\xd9",
                captured_at=1782910800.123456,
                source_url="http://spot.invalid/image.jpg",
                source="test",
                image_age_ms=0.0,
                link_checked_at=None,
                observation_snapshot=None,
            )
            external_fact = {
                **first_fact,
                "spot_image_capture_id": "external-interleaved-capture",
            }
            with fact_path.open("a", encoding="utf-8-sig", newline="") as handle:
                csv.DictWriter(
                    handle,
                    fieldnames=SPOT_IMAGE_FACT_COLUMNS,
                ).writerow(external_fact)

            originals = {path: path.read_bytes() for path in log_path.rglob("*") if path.is_file()}
            with self.assertRaisesRegex(RuntimeError, "uncertain; manual recovery required"):
                runtime_writer.write_capture(
                    image_bytes=b"\xff\xd8second-capture\xff\xd9",
                    captured_at=1782910801.123456,
                    source_url="http://spot.invalid/image.jpg",
                    source="test",
                    image_age_ms=0.0,
                    link_checked_at=None,
                    observation_snapshot=None,
                )

            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(runtime_writer.fact_row_count, 1)
            self.assertEqual({path: path.read_bytes() for path in log_path.rglob("*") if path.is_file()}, originals)
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                _ = runtime_writer.fact_sha256

    def test_image_manifest_fails_closed_when_external_append_interleaves_digest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir)
            fact_path = log_path / "spot_image_fact.csv"
            runtime_writer = SpotImageCaptureWriter(
                log_path=log_path,
                capture_root=log_path / "spot_images",
            )
            first_fact = runtime_writer.write_capture(
                image_bytes=b"\xff\xd8first-capture\xff\xd9",
                captured_at=1782910800.123456,
                source_url="http://spot.invalid/image.jpg",
                source="test",
                image_age_ms=0.0,
                link_checked_at=None,
                observation_snapshot=None,
            )
            external_fact = {
                **first_fact,
                "spot_image_capture_id": "external-interleaved-capture",
            }
            original_extend = runtime_writer._extend_manifest_digest

            def append_then_extend(
                previous_size: int,
                *,
                expected_size: int,
            ) -> None:
                with fact_path.open(
                    "a",
                    encoding="utf-8-sig",
                    newline="",
                ) as handle:
                    csv.DictWriter(
                        handle,
                        fieldnames=SPOT_IMAGE_FACT_COLUMNS,
                    ).writerow(external_fact)
                original_extend(
                    previous_size,
                    expected_size=expected_size,
                )

            with patch.object(
                runtime_writer,
                "_extend_manifest_digest",
                side_effect=append_then_extend,
            ):
                runtime_writer.write_capture(
                    image_bytes=b"\xff\xd8second-capture\xff\xd9",
                    captured_at=1782910801.123456,
                    source_url="http://spot.invalid/image.jpg",
                    source="test",
                    image_age_ms=0.0,
                    link_checked_at=None,
                    observation_snapshot=None,
                )

            with fact_path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 3)
            self.assertEqual(runtime_writer.fact_row_count, 2)
            with self.assertRaisesRegex(
                RuntimeError,
                "runtime manifest state is unavailable",
            ):
                _ = runtime_writer.fact_sha256

    def test_control_shutdown_subprocess_quiesces_spot_before_logger_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker_path = Path(temp_dir) / "shutdown-order.txt"
            script = textwrap.dedent(
                """
                import asyncio
                from pathlib import Path
                import sys

                from backend import app as backend_app

                marker_path = Path(sys.argv[1])

                def mark(stage):
                    with marker_path.open("a", encoding="utf-8") as handle:
                        handle.write(stage + "\\n")
                    return True

                async def stop_spot_poll_loop():
                    mark("spot_poll_loop")
                    return True

                class LoggerStub:
                    def stop(
                        self,
                        *,
                        timeout_sec=None,
                        finalize_spot_image_manifest=True,
                        finalize_spot_observation_manifest=True,
                    ):
                        del (
                            timeout_sec,
                            finalize_spot_image_manifest,
                            finalize_spot_observation_manifest,
                        )
                        return mark("logger_service")

                backend_app.spot_control.stop_spot_poll_loop = stop_spot_poll_loop
                backend_app.spot_control.stop_spot_image_capture_for_shutdown = (
                    lambda *, timeout_sec=None: mark("spot_image_capture")
                )
                backend_app.plc_service.stop = lambda: mark("plc_service")
                backend_app.logger_service = LoggerStub()
                backend_app.comm_metrics_logger_service.stop = lambda: mark("comm_metrics")
                backend_app.memory_service.stop = lambda: mark("memory_service")
                backend_app.config_sync_agent.stop = lambda: mark("config_sync")
                backend_app.config_watch_service.stop = lambda: mark("config_watch")
                backend_app.spot_control.stop_spot_diagnostic_request_journal = (
                    lambda: mark("spot_diagnostic_journal")
                )

                asyncio.run(backend_app._run_control_shutdown("subprocess-regression"))
                """
            )

            completed = subprocess.run(
                [sys.executable, "-c", script, str(marker_path)],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            order = marker_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertGreaterEqual(len(order), 3)
        self.assertEqual(order[0], "spot_poll_loop")
        self.assertLess(order.index("spot_poll_loop"), order.index("logger_service"))
        self.assertLess(
            order.index("logger_service"),
            order.index("spot_diagnostic_journal"),
        )
        self.assertEqual(order[-1], "spot_diagnostic_journal")

    def test_control_shutdown_spot_failure_still_runs_closeout_and_exits_with_failure(self) -> None:
        async def exercise() -> None:
            downstream_status = {
                key: True
                for key in backend_app._CONTROL_SHUTDOWN_REQUIRED_STATUS_KEYS
                if key != "spot_poll_loop_stopped"
            }
            with (
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_poll_loop",
                    new=AsyncMock(side_effect=RuntimeError("SPOT stop failed")),
                ),
                patch.object(
                    backend_app,
                    "_stop_services_for_control_shutdown",
                    return_value=downstream_status,
                ) as closeout,
                patch.object(
                    backend_app,
                    "_probe_spot_poll_producers_settled",
                    return_value=True,
                ),
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_diagnostic_request_journal",
                    return_value=True,
                ) as stop_journal,
                patch.object(backend_app.os, "_exit") as process_exit,
            ):
                await backend_app._run_control_shutdown("spot-stop-regression")

            closeout.assert_called_once_with(observation_fact_drained=True)
            stop_journal.assert_called_once_with()
            process_exit.assert_called_once_with(2)

        asyncio.run(exercise())

    def test_control_shutdown_drain_probe_failure_still_runs_closeout_and_exits_with_failure(
        self,
    ) -> None:
        async def exercise() -> None:
            downstream_status = {
                key: True
                for key in backend_app._CONTROL_SHUTDOWN_REQUIRED_STATUS_KEYS
                if key != "spot_observation_fact_drained"
            }
            downstream_status["spot_observation_fact_drained"] = False
            with (
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_poll_loop",
                    new=AsyncMock(return_value=True),
                ),
                patch.object(
                    backend_app.spot_control,
                    "spot_observation_fact_writes_drained",
                    side_effect=RuntimeError("drain probe failed"),
                ),
                patch.object(
                    backend_app,
                    "_stop_services_for_control_shutdown",
                    return_value=downstream_status,
                ) as closeout,
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_diagnostic_request_journal",
                    return_value=True,
                ) as stop_journal,
                patch.object(backend_app.os, "_exit") as process_exit,
            ):
                with self.assertLogs("SmartFactoryLoggerV2", level="WARNING"):
                    await backend_app._run_control_shutdown("drain-probe-regression")

            closeout.assert_called_once_with(observation_fact_drained=False)
            stop_journal.assert_called_once_with()
            process_exit.assert_called_once_with(2)

        asyncio.run(exercise())

    def test_control_shutdown_transport_timeout_exits_with_failure(self) -> None:
        async def exercise() -> None:
            downstream_status = {
                key: True
                for key in backend_app._CONTROL_SHUTDOWN_REQUIRED_STATUS_KEYS
                if key != "spot_poll_loop_stopped"
            }
            with (
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_poll_loop",
                    new=AsyncMock(return_value=False),
                ),
                patch.object(
                    backend_app,
                    "_stop_services_for_control_shutdown",
                    return_value=downstream_status,
                ) as closeout,
                patch.object(
                    backend_app,
                    "_probe_spot_poll_producers_settled",
                    return_value=False,
                ),
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_diagnostic_request_journal",
                    return_value=True,
                ) as stop_journal,
                patch.object(backend_app.os, "_exit") as process_exit,
            ):
                await backend_app._run_control_shutdown("transport-timeout-regression")

            closeout.assert_called_once_with(observation_fact_drained=True)
            stop_journal.assert_not_called()
            process_exit.assert_called_once_with(2)

        asyncio.run(exercise())

    def test_control_shutdown_journal_drain_failure_exits_with_failure(self) -> None:
        async def exercise() -> None:
            downstream_status = {
                key: True
                for key in backend_app._CONTROL_SHUTDOWN_REQUIRED_STATUS_KEYS
                if key != "spot_diagnostic_journal_stopped"
            }
            with (
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_poll_loop",
                    new=AsyncMock(return_value=True),
                ),
                patch.object(
                    backend_app,
                    "_stop_services_for_control_shutdown",
                    return_value=downstream_status,
                ),
                patch.object(
                    backend_app.spot_control,
                    "stop_spot_diagnostic_request_journal",
                    return_value=False,
                ) as stop_journal,
                patch.object(backend_app.os, "_exit") as process_exit,
            ):
                await backend_app._run_control_shutdown("journal-drain-regression")

            stop_journal.assert_called_once_with()
            process_exit.assert_called_once_with(2)

        asyncio.run(exercise())

    def test_control_shutdown_schedule_rejects_duplicate_requests(self) -> None:
        async def exercise() -> None:
            release = asyncio.Event()
            calls: list[str] = []

            async def hold_shutdown(reason: str) -> None:
                calls.append(reason)
                await release.wait()

            backend_app._control_shutdown_tasks.clear()
            with patch.object(backend_app, "_run_control_shutdown", side_effect=hold_shutdown):
                backend_app._schedule_control_shutdown("first")
                backend_app._schedule_control_shutdown("duplicate")
                await asyncio.sleep(0)
                self.assertEqual(calls, ["first"])
                self.assertEqual(len(backend_app._control_shutdown_tasks), 1)
                release.set()
                await asyncio.gather(*backend_app._control_shutdown_tasks)
                await asyncio.sleep(0)

            self.assertFalse(backend_app._control_shutdown_tasks)

        asyncio.run(exercise())

    def test_portable_qa_operator_shutdown_checkpoint_behaves_fail_closed(self) -> None:
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is unavailable")

        qa_path = self.repo_root / "scripts" / "qa_spot_temperature_v25.ps1"
        qa_script = qa_path.read_text(encoding="utf-8")

        self.assertNotIn("/api/control/shutdown", qa_script)
        self.assertNotIn("X-SFL-Control-Token", qa_script)
        self.assertLess(
            qa_script.index("Invoke-OperatorShutdownCheckpoint"),
            qa_script.index('[4/5] Checking the finalized CSV and config attestation'),
        )

        exercise = r"""
$source = Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8
$beginMarker = "# BEGIN QA SHUTDOWN HELPERS"
$endMarker = "# END QA SHUTDOWN HELPERS"
$begin = $source.IndexOf($beginMarker)
$end = $source.IndexOf($endMarker)
if ($begin -lt 0 -or $end -lt $begin) {
    throw "QA shutdown helper markers were not found."
}
$helperSource = $source.Substring(
    $begin,
    ($end + $endMarker.Length) - $begin
)
Invoke-Expression $helperSource

$script:successProbeCount = 0
$script:promptCount = 0
$success = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 2 `
    -PollIntervalSeconds 0 `
    -ConsecutiveFailuresRequired 3 `
    -ReachabilityProbe {
        $script:successProbeCount += 1
        return $script:successProbeCount -lt 2
    } `
    -ProductProcessProbe { return $false } `
    -PromptAction { $script:promptCount += 1 } `
    -SleepAction { param([int]$Seconds) }

$alreadyStopped = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 2 `
    -PollIntervalSeconds 0 `
    -ConsecutiveFailuresRequired 3 `
    -ReachabilityProbe { return $false } `
    -ProductProcessProbe { return $false } `
    -PromptAction { throw "prompt must not run" } `
    -SleepAction { param([int]$Seconds) }

$timeout = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 0 `
    -PollIntervalSeconds 0 `
    -ConsecutiveFailuresRequired 3 `
    -ReachabilityProbe { return $true } `
    -ProductProcessProbe { return $true } `
    -PromptAction { $script:promptCount += 1 } `
    -SleepAction { param([int]$Seconds) }

$transientHealthFailure = Invoke-OperatorShutdownCheckpoint `
    -TimeoutSeconds 0 `
    -PollIntervalSeconds 0 `
    -ConsecutiveFailuresRequired 3 `
    -ReachabilityProbe { return $false } `
    -ProductProcessProbe { return $true } `
    -PromptAction { $script:promptCount += 1 } `
    -SleepAction { param([int]$Seconds) }

[PSCustomObject]@{
    success_stopped = [bool]$success.backend_stopped
    success_operator_requested = [bool]$success.operator_shutdown_requested
    success_consecutive_count = [int]$success.consecutive_unreachable_count
    already_stopped = [bool]$alreadyStopped.backend_stopped
    already_operator_requested = [bool]$alreadyStopped.operator_shutdown_requested
    already_consecutive_count = [int]$alreadyStopped.consecutive_unreachable_count
    timeout_stopped = [bool]$timeout.backend_stopped
    timeout_operator_requested = [bool]$timeout.operator_shutdown_requested
    transient_stopped = [bool]$transientHealthFailure.backend_stopped
    transient_operator_requested = [bool]$transientHealthFailure.operator_shutdown_requested
    prompt_count = $script:promptCount
} | ConvertTo-Json -Compress
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            exercise_path = Path(temp_dir) / "exercise-qa-shutdown.ps1"
            exercise_path.write_text(exercise, encoding="utf-8-sig")
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(exercise_path),
                str(qa_path),
            ]
            if sys.platform == "win32":
                command = ["cmd.exe", "/d", "/c", *command]
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertTrue(result["success_stopped"])
        self.assertTrue(result["success_operator_requested"])
        self.assertGreaterEqual(result["success_consecutive_count"], 3)
        self.assertTrue(result["already_stopped"])
        self.assertFalse(result["already_operator_requested"])
        self.assertGreaterEqual(result["already_consecutive_count"], 3)
        self.assertFalse(result["timeout_stopped"])
        self.assertTrue(result["timeout_operator_requested"])
        self.assertFalse(result["transient_stopped"])
        self.assertTrue(result["transient_operator_requested"])
        self.assertEqual(result["prompt_count"], 3)

    def test_portable_qa_metadata_selection_is_bound_to_current_session(self) -> None:
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is unavailable")

        qa_path = self.repo_root / "scripts" / "qa_spot_temperature_v25.ps1"
        expected_instance = "11111111-1111-1111-1111-111111111111"
        expected_commit = "a" * 40
        stale_instance = "22222222-2222-2222-2222-222222222222"
        stale_commit = "b" * 40

        exercise = r"""
$source = Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8
$beginMarker = "# BEGIN QA METADATA HELPERS"
$endMarker = "# END QA METADATA HELPERS"
$begin = $source.IndexOf($beginMarker)
$end = $source.IndexOf($endMarker)
if ($begin -lt 0 -or $end -lt $begin) {
    throw "QA metadata helper markers were not found."
}
$helperSource = $source.Substring(
    $begin,
    ($end + $endMarker.Length) - $begin
)
Invoke-Expression $helperSource

$matched = Find-LatestMetadata `
    -Directories @($args[1]) `
    -ExpectedLoggerServiceInstanceId $args[2] `
    -ExpectedBuildCommit $args[3] `
    -ExpectedMinimumSampleSeq ([long]$args[4]) `
    -ExpectedCsvFileName $args[5]
$missing = Find-LatestMetadata `
    -Directories @($args[1]) `
    -ExpectedLoggerServiceInstanceId "33333333-3333-3333-3333-333333333333" `
    -ExpectedBuildCommit ("c" * 40) `
    -ExpectedMinimumSampleSeq ([long]$args[4]) `
    -ExpectedCsvFileName $args[5]
$wrongCsv = Find-LatestMetadata `
    -Directories @($args[1]) `
    -ExpectedLoggerServiceInstanceId $args[2] `
    -ExpectedBuildCommit $args[3] `
    -ExpectedMinimumSampleSeq ([long]$args[4]) `
    -ExpectedCsvFileName "Factory_Integrated_Log_v2_wrong.csv"

Set-Content -LiteralPath $args[6] -Value "{" -Encoding UTF8
$corruptCurrent = Find-LatestMetadata `
    -Directories @($args[1]) `
    -ExpectedLoggerServiceInstanceId $args[2] `
    -ExpectedBuildCommit $args[3] `
    -ExpectedMinimumSampleSeq ([long]$args[4]) `
    -ExpectedCsvFileName $args[5]

[PSCustomObject]@{
    matched_name = if ($null -ne $matched) { $matched.file.Name } else { "" }
    matched_instance = if ($null -ne $matched) {
        $matched.metadata.schema_metadata.logger_service_instance_id
    } else {
        ""
    }
    matched_final_sample_seq = if ($null -ne $matched) {
        [long]$matched.csv_final_sample_seq
    } else {
        0
    }
    matched_observed_csv_file_name = if ($null -ne $matched) {
        [string]$matched.observed_csv_file_name
    } else {
        ""
    }
    missing_is_null = ($null -eq $missing)
    wrong_csv_is_null = ($null -eq $wrongCsv)
    corrupt_observed_still_matches_shutdown = (
        $null -ne $corruptCurrent -and
        $corruptCurrent.file.Name -eq $matched.file.Name
    )
} | ConvertTo-Json -Compress
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            current_path = temp_path / "Factory_Integrated_Log_v2_20260729_100000.metadata.json"
            shutdown_path = temp_path / "Factory_Integrated_Log_v2_20260729_100100.metadata.json"
            stale_path = temp_path / "Factory_Integrated_Log_v2_20260729_110000.metadata.json"
            older_path = temp_path / "Factory_Integrated_Log_v2_20260729_090000.metadata.json"

            def write_artifact(
                metadata_path: Path,
                logger_instance: str,
                build_commit: str,
                sample_seq: int,
                raw_value: str = "455.0",
                closeout_reason: str = "daily-rollover",
            ) -> None:
                csv_file_name = metadata_path.name.replace(
                    ".metadata.json",
                    ".csv",
                )
                metadata_path.write_text(
                    json.dumps(
                        {
                            "schema_metadata": {
                                "logger_service_instance_id": logger_instance,
                                "git_commit": build_commit,
                            },
                            "spot_configuration_snapshot": {
                                "build_git_commit": build_commit,
                            },
                            "csv_closeout": {
                                "finalized": True,
                                "closeout_reason": closeout_reason,
                                "csv_file_name": csv_file_name,
                                "logger_service_instance_id": logger_instance,
                                "final_persisted_sample_seq": sample_seq,
                                "persisted_at": "2026-07-29T05:00:00Z",
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                csv_path = metadata_path.with_name(csv_file_name)
                with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(
                        [
                            "logger_service_instance_id",
                            "sample_seq",
                            "spot_temperature_raw",
                        ]
                    )
                    writer.writerow([logger_instance, sample_seq, raw_value])

            write_artifact(
                current_path,
                expected_instance,
                expected_commit,
                201,
                "6553.4\r\n",
            )
            write_artifact(
                shutdown_path,
                expected_instance,
                expected_commit,
                202,
                closeout_reason="shutdown",
            )
            write_artifact(older_path, expected_instance, expected_commit, 200)
            write_artifact(
                stale_path,
                stale_instance,
                stale_commit,
                300,
                closeout_reason="shutdown",
            )
            now = time.time()
            os.utime(older_path, (now - 120, now - 120))
            os.utime(current_path, (now - 90, now - 90))
            os.utime(shutdown_path, (now - 60, now - 60))
            os.utime(stale_path, (now, now))
            exercise_path = temp_path / "exercise-qa-metadata.ps1"
            exercise_path.write_text(exercise, encoding="utf-8-sig")
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(exercise_path),
                str(qa_path),
                str(temp_path),
                expected_instance,
                expected_commit,
                "200",
                shutdown_path.name.replace(".metadata.json", ".csv"),
                str(current_path),
            ]
            if sys.platform == "win32":
                command = ["cmd.exe", "/d", "/c", *command]
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(result["matched_name"], shutdown_path.name)
        self.assertEqual(result["matched_instance"], expected_instance)
        self.assertEqual(result["matched_final_sample_seq"], 202)
        self.assertEqual(
            result["matched_observed_csv_file_name"],
            shutdown_path.name.replace(".metadata.json", ".csv"),
        )
        self.assertTrue(result["missing_is_null"])
        self.assertTrue(result["wrong_csv_is_null"])
        self.assertTrue(result["corrupt_observed_still_matches_shutdown"])


if __name__ == "__main__":
    unittest.main()
