import csv
import json
import tempfile
import tracemalloc
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.FacilityData.spot_observation_fact import (
    SPOT_OBSERVATION_FACT_COLUMNS,
    SPOT_OBSERVATION_FACT_SCHEMA_VERSION,
    SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS,
    SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION,
    SpotObservationFactWriter,
    build_spot_observation_fact,
    build_spot_observation_fact_manifest,
    build_spot_observation_key,
    derive_spot_diagnostic_evidence_codes,
    encode_spot_diagnostic_evidence_codes,
)
from backend.FacilityData.spot_diagnostics import SPOT_DIAGNOSTIC_OUTPUT_FIELDS
from scripts.validate_csv_v2_shadow import validate_spot_observation_fact_invariants


class SpotObservationFactTests(unittest.TestCase):
    def diagnostics_metadata(
        self,
        poll_seq: int,
        *,
        success_fields: tuple[str, ...] = SPOT_DIAGNOSTIC_OUTPUT_FIELDS,
        collection_mode: str = "async_same_poll",
    ) -> dict[str, object]:
        success = set(success_fields)
        field_status = {
            field: "success" if field in success else "missing"
            for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS
        }
        missing_fields = [
            field for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS if field not in success
        ]
        return {
            "diagnostics_snapshot_id": f"svc-1:diag:{poll_seq}",
            "diagnostics_source_poll_seq": poll_seq,
            "diagnostics_captured_at": "2026-06-26T00:00:00Z",
            "diagnostics_capture_status": (
                "async_complete" if not missing_fields else "async_partial"
            ),
            "diagnostics_collection_mode": collection_mode,
            "diagnostics_source": "spot_output_parameter_get",
            "diagnostics_binding_status": "same_poll",
            "diagnostics_age_ms": 10.0,
            "diagnostics_max_age_ms": 6000.0,
            "diagnostics_field_status": field_status,
            "diagnostics_missing_fields": missing_fields,
        }

    def current_fact_row(self, poll_seq: int = 9, **overrides: object) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": poll_seq,
            "spot_observation_seq": poll_seq,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "0",
            "signalpc": "6.0",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": False,
            "peak_picker_enabled": False,
            **self.diagnostics_metadata(poll_seq),
        }
        snapshot.update(overrides)
        return build_spot_observation_fact(snapshot)

    def test_observation_key_is_service_instance_and_poll_seq(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }

        self.assertEqual(build_spot_observation_key(snapshot), "svc-1:42")

    def test_observation_key_requires_positive_poll_seq_completed_at_and_non_startup_state(self) -> None:
        base = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "spot_poll_status": "success",
        }

        self.assertEqual(build_spot_observation_key({**base, "spot_poll_seq": 0}), "")
        self.assertEqual(build_spot_observation_key({**base, "spot_poll_seq": -1}), "")
        self.assertEqual(build_spot_observation_key({**base, "spot_last_poll_completed_at": ""}), "")
        self.assertEqual(build_spot_observation_key({**base, "spot_poll_status": "not_attempted"}), "")
        self.assertEqual(build_spot_observation_key({**base, "temperature_output_status": "startup_pending"}), "")
        self.assertEqual(build_spot_observation_key({**base, "temperature_status_shadow": "startup_pending"}), "")

    def test_writer_is_idempotent_per_poll_key(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_observation_seq": 42,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)

            first = writer.write_fact(snapshot)
            second = writer.write_fact(snapshot)

            self.assertIsNotNone(first)
            self.assertIsNone(second)
            rows = output_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(rows), 2)

    def test_writer_initializes_header_only_fact_before_first_poll(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)

            self.assertTrue(writer.ensure_initialized())
            self.assertTrue(writer.ensure_initialized())

            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows, [SPOT_OBSERVATION_FACT_COLUMNS])

    def test_writer_loads_existing_key_index_after_restart(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 42,
            "spot_observation_seq": 42,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            first_writer = SpotObservationFactWriter(output_path)
            self.assertIsNotNone(first_writer.write_fact(snapshot))

            restarted_writer = SpotObservationFactWriter(output_path)
            self.assertIsNone(restarted_writer.write_fact(snapshot))

            rows = output_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(rows), 2)

    def test_fact_manifest_summarizes_file_and_realtime_link_coverage(self) -> None:
        base_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_observation_seq": 1,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "450.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "0",
            "signalpc": "3.2",
            "d1temperature": "31.0",
            "d2temperature": "31.1",
            "e1out": "1.0",
            "e2out": "1.1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)
            success_fields = (
                "alarmstatus",
                "signalpc",
                "d1temperature",
                "d2temperature",
                "e1out",
                "e2out",
            )
            self.assertIsNotNone(
                writer.write_fact(
                    {
                        **base_snapshot,
                        "spot_poll_seq": 1,
                        **self.diagnostics_metadata(1, success_fields=success_fields),
                    }
                )
            )
            self.assertIsNotNone(
                writer.write_fact(
                    {
                        **base_snapshot,
                        "spot_poll_seq": 3,
                        **self.diagnostics_metadata(3, success_fields=success_fields),
                    }
                )
            )

            manifest = build_spot_observation_fact_manifest(
                fact_path=output_path,
                enabled=True,
                write_failure_count=0,
                spool_pending_count=0,
                realtime_rows=[
                    {"spot_observation_key": "svc-1:1"},
                    {"spot_observation_key": "svc-1:3"},
                    {"spot_observation_key": "svc-1:99"},
                ],
            )

        self.assertTrue(manifest["enabled"])
        self.assertEqual(manifest["schema_version"], "1.4.0")
        self.assertEqual(manifest["row_count"], 2)
        self.assertEqual(manifest["distinct_observation_key_count"], 2)
        self.assertEqual(manifest["first_poll_seq"], 1)
        self.assertEqual(manifest["last_poll_seq"], 3)
        self.assertEqual(manifest["poll_seq_gap_count"], 1)
        self.assertRegex(manifest["sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(manifest["link_coverage"]["realtime_rows_with_observation_key"], 3)
        self.assertEqual(manifest["link_coverage"]["linked_rows"], 2)
        self.assertEqual(manifest["link_coverage"]["missing_fact_key_rows"], 1)
        self.assertEqual(manifest["diagnostic_field_coverage"]["signalpc_nonblank_count"], 2)
        self.assertEqual(manifest["diagnostics_capture_status_counts"], {"async_partial": 2})
        self.assertEqual(manifest["diagnostics_binding_status_counts"], {"same_poll": 2})

    def test_spool_recovery_processes_at_most_twenty_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            spool.write_text("".join(json.dumps(self.current_fact_row(seq)) + "\n"
                                     for seq in range(1, 24)), encoding="utf-8")
            writer = SpotObservationFactWriter(output, spool_path=spool)
            self.assertEqual(writer.spool_pending_count(), 23)
            writer._flush_spool()
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 20)
            self.assertEqual(writer.spool_pending_count(), 3)
            self.assertEqual([row["spot_observation_key"] for row in rows],
                             [f"svc-1:{seq}" for seq in range(1, 21)])
            writer._flush_spool()
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_observation_key"] for row in rows],
                             [f"svc-1:{seq}" for seq in range(1, 24)])
            self.assertEqual(writer.spool_pending_count(), 0)
            self.assertEqual(writer.manifest_summary()["row_count"], 23)

    def test_spool_recovery_read_budget_preserves_utf8_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            info = "온" * 120000
            spool.write_text("".join(json.dumps(self.current_fact_row(seq, instrument_info=info),
                                               ensure_ascii=False) + "\n"
                                     for seq in range(1, 4)), encoding="utf-8")
            self.assertGreater(spool.stat().st_size, 1024**2)
            writer = SpotObservationFactWriter(output, spool_path=spool)
            original_open = Path.open
            read_totals = []

            class ObservedReader:
                def __init__(self, handle):
                    self.handle = handle
                    self.read_bytes = 0

                def __getattr__(self, name):
                    return getattr(self.handle, name)

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    read_totals.append(self.read_bytes)
                    self.handle.close()

                def readline(self, size=-1):
                    data = self.handle.readline(size)
                    self.read_bytes += len(data)
                    return data

            def observe_open(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                return ObservedReader(handle) if path == spool and mode == "rb" else handle

            with patch.object(Path, "open", observe_open):
                writer._flush_spool()
                with output.open(encoding="utf-8-sig", newline="") as handle:
                    first = list(csv.DictReader(handle))
                self.assertEqual(len(first), 2)
                self.assertLessEqual(read_totals[-1], 1024**2)
                self.assertEqual(writer.spool_pending_count(), 1)
                writer._flush_spool()
            self.assertTrue(all(0 < size <= 1024**2 for size in read_totals))
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_observation_key"] for row in rows],
                             ["svc-1:1", "svc-1:2", "svc-1:3"])
            self.assertEqual([row["instrument_info"] for row in rows], [info] * 3)
            self.assertEqual(writer.spool_pending_count(), 0)

    def test_oversized_spool_row_is_preserved_and_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            first = (json.dumps(self.current_fact_row(1)) + "\n").encode("utf-8")
            large = (json.dumps(self.current_fact_row(2, instrument_info="x" * 1024**2))
                     + "\n").encode("utf-8")
            original = first + large
            spool.write_bytes(original)
            writer = SpotObservationFactWriter(output, spool_path=spool)
            writer._flush_spool()
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, "UNCERTAIN.*spool-row-too-large") as error:
                    writer._flush_spool()
                self.assertIn(str(spool), str(error.exception))
                self.assertIn(f"offset={len(first)}", str(error.exception))
                self.assertEqual(spool.read_bytes(), original)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_observation_key"] for row in rows], ["svc-1:1"])
            self.assertEqual(writer.spool_pending_count(), 1)
            self.assertEqual(writer.manifest_summary()["row_count"], 1)
            self.assertEqual(list(Path(tmp).glob("*.schema-mismatch.*")), [])

    def test_spool_pending_count_uses_bounded_reads(self) -> None:
        from backend.FacilityData.spot_observation_fact import _spool_pending_count

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            archive = Path(tmp) / "facts.failed.20261027T000000Z.schema-mismatch.jsonl"
            spool.write_bytes(b"\n \t\n" + b"x" * (1024**2 + 100) + b"\nlast-row")
            archive.write_bytes(b"legacy-row\n" + b"\t" * (1024**2 + 100) + b"\n")
            writer = SpotObservationFactWriter(output, spool_path=spool)
            original_open = Path.open
            reads = []

            def bounded_open(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                if path not in (spool, archive) or "r" not in mode:
                    return handle
                guarded = MagicMock(wraps=handle)
                guarded.__enter__.return_value = guarded
                guarded.__exit__.side_effect = lambda *args: handle.close()
                guarded.__iter__.side_effect = AssertionError("unbounded spool count read")

                def readline(size=-1):
                    self.assertTrue(0 < size <= 1024**2, "unbounded spool count read")
                    data = handle.readline(size)
                    reads.append(len(data))
                    return data

                guarded.readline.side_effect = readline
                return guarded

            with patch.object(Path, "open", bounded_open):
                self.assertEqual(writer.spool_pending_count(), 3)
                self.assertEqual(_spool_pending_count(spool), 3)
            self.assertGreater(len(reads), 4)
            with patch.object(Path, "open", side_effect=AssertionError("cached count performed I/O")):
                self.assertEqual(writer.spool_pending_count(), 3)

    def test_manifest_rejects_unreadable_spool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = output.with_name(output.name + ".failed.jsonl")
            original = (json.dumps(self.current_fact_row(1)) + "\n").encode("utf-8")
            spool.write_bytes(original)
            original_open = Path.open

            def unreadable_open(path, mode="r", *args, **kwargs):
                if path == spool and mode == "rb":
                    raise PermissionError("injected unreadable spool")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", unreadable_open):
                with self.assertRaisesRegex(OSError, "unreadable spool"):
                    build_spot_observation_fact_manifest(fact_path=output, enabled=True)
            manifest = build_spot_observation_fact_manifest(fact_path=output, enabled=True)
            self.assertEqual(manifest["spool_pending_count"], 1)
            self.assertEqual(manifest["row_count"], 0)
            self.assertEqual(spool.read_bytes(), original)

    def test_manifest_counts_unresolved_spool_archives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = output.with_name(output.name + ".failed.jsonl")
            archive = spool.with_name(spool.stem + ".20261027T000000Z.schema-mismatch.jsonl")
            original = (json.dumps(self.current_fact_row(1)) + "\n").encode("utf-8")
            spool.write_bytes(original)
            archive.write_bytes(b"unresolved-legacy-row\n")
            writer = SpotObservationFactWriter(output, spool_path=spool)
            writer._spool_fact(self.current_fact_row(2))
            self.assertEqual(writer.spool_pending_count(), 3)
            manifest = build_spot_observation_fact_manifest(fact_path=output, enabled=True)
            self.assertEqual(manifest["spool_pending_count"], 3)
            original_open = Path.open

            def unreadable_open(path, mode="r", *args, **kwargs):
                if path == archive and mode == "rb":
                    raise PermissionError("injected unreadable archived spool")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", unreadable_open):
                with self.assertRaisesRegex(OSError, "unreadable archived spool"):
                    build_spot_observation_fact_manifest(fact_path=output, enabled=True)
            self.assertEqual(spool.read_bytes(), original)
            self.assertEqual(archive.read_bytes(), b"unresolved-legacy-row\n")
            self.assertFalse(output.exists())

    def test_spool_byte_limit_preserves_existing_pending_files(self) -> None:
        from backend.FacilityData import spot_observation_fact as fact_module

        with tempfile.TemporaryDirectory() as tmp:
            spool = Path(tmp) / "facts.failed.jsonl"
            archive = Path(tmp) / "facts.failed.20261027T000000Z.schema-mismatch.jsonl"
            first = (json.dumps(self.current_fact_row(1), sort_keys=True, ensure_ascii=False)
                     + "\n").encode("utf-8")
            second = (json.dumps(self.current_fact_row(2), sort_keys=True, ensure_ascii=False)
                      + "\n").encode("utf-8")
            spool.write_bytes(first)
            archive.write_bytes(b"unresolved-legacy-row\n")
            archive_before = archive.read_bytes()
            writer = SpotObservationFactWriter(Path(tmp) / "facts.csv", spool_path=spool)
            self.assertEqual(writer.spool_pending_count(), 2)
            budget = len(first) + len(archive_before) + len(second) - 1
            with patch.object(fact_module, "FACT_SPOOL_PENDING_BYTE_LIMIT", budget, create=True):
                writer._spool_fact(self.current_fact_row(2))
            self.assertEqual(writer.spool_failure_count, 1)
            self.assertEqual(writer.spool_last_error_code, "spool_byte_limit")
            self.assertEqual(spool.read_bytes(), first)
            self.assertEqual(archive.read_bytes(), archive_before)
            self.assertEqual(writer.spool_pending_count(), 2)

    def test_spool_rejects_rows_above_recovery_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            directory = spool.with_name(spool.name + ".segments-v1")
            limit = 1024**2
            fact = self.current_fact_row(1, instrument_info="")
            overhead = len((json.dumps(fact, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
            fact["instrument_info"] = "x" * (limit - overhead)
            payload = (json.dumps(fact, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
            self.assertEqual(len(payload), limit)
            writer = SpotObservationFactWriter(output, spool_path=spool)
            writer._spool_fact(fact)
            first = list(directory.glob("*.jsonl"))
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0].read_bytes(), payload)
            large = self.current_fact_row(2, instrument_info=fact["instrument_info"] + "x")
            writer._spool_fact(large)
            self.assertEqual(writer.spool_failure_count, 1)
            self.assertEqual(writer.spool_last_error_code, "spool_row_too_large")
            self.assertEqual(first[0].read_bytes(), payload)
            self.assertEqual(writer.spool_pending_count(), 1)
            writer._spool_fact(self.current_fact_row(3))
            self.assertEqual(writer.spool_pending_count(), 2)
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 1)
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 0)
            self.assertEqual(writer.spool_failure_count, 1)
            self.assertEqual(list(directory.glob("*.jsonl")), [])
            previous_limit = csv.field_size_limit(limit * 2)
            try:
                with output.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            finally:
                csv.field_size_limit(previous_limit)
            self.assertEqual([row["spot_observation_key"] for row in rows], ["svc-1:1", "svc-1:3"])
            self.assertEqual(rows[0]["instrument_info"], fact["instrument_info"])

    def test_oversized_spool_rejects_before_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            writer = SpotObservationFactWriter(output, spool_path=spool)
            writer._spool_fact(self.current_fact_row(1))
            directory = spool.with_name(spool.name + ".segments-v1")
            segment = next(directory.glob("*.jsonl"))
            original = segment.read_bytes()
            oversized = self.current_fact_row(2, instrument_info="x" * (12 * 1024**2))
            # Input creation is outside the measurement: inspect only the new
            # allocations made while rejecting the unsupported spool row.
            self.assertFalse(tracemalloc.is_tracing())
            tracemalloc.start()
            try:
                writer._spool_fact(oversized)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertLessEqual(peak, 16 * 1024**2, "oversized row must be rejected before serialization copies")
            self.assertEqual(writer.spool_failure_count, 1)
            self.assertEqual(writer.spool_last_error_code, "spool_row_too_large")
            self.assertEqual(segment.read_bytes(), original)
            self.assertEqual(writer.spool_pending_count(), 1)
            writer._spool_fact(self.current_fact_row(3))
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 0)
            self.assertEqual(writer.spool_failure_count, 1)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_observation_key"] for row in rows], ["svc-1:1", "svc-1:3"])

    def test_spool_encoder_growth_stays_within_two_copy_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            writer = SpotObservationFactWriter(output, spool_path=spool)
            writer._spool_fact(self.current_fact_row(1))
            segment = next(spool.with_name(spool.name + ".segments-v1").glob("*.jsonl"))
            original = segment.read_bytes()
            fact = self.current_fact_row(2, instrument_info="x" * 900000)
            expected = (json.dumps(fact, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
            self.assertLess(len(expected), 1024**2)
            tracemalloc.start()
            try:
                writer._spool_fact(fact)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            # Allow bounded path/container/file overhead in addition to the
            # two payload copies. Input and expected bytes predate measurement.
            self.assertLessEqual(peak, 2 * len(expected) + 64 * 1024,
                                 "Spool JSON encoding exceeded two-copy budget")
            self.assertEqual(segment.read_bytes(), original + expected)
            self.assertEqual(writer.spool_failure_count, 0)
            writer._spool_fact(self.current_fact_row(3))
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 0)
            previous_limit = csv.field_size_limit(1024**2)
            try:
                with output.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            finally:
                csv.field_size_limit(previous_limit)
            self.assertEqual([row["spot_observation_key"] for row in rows], ["svc-1:1", "svc-1:2", "svc-1:3"])
            self.assertEqual(rows[1]["instrument_info"], fact["instrument_info"])

    def test_recovery_reserves_expanded_container_text(self) -> None:
        reserved = 0

        @contextmanager
        def reserve(size, reason):
            nonlocal reserved
            self.assertEqual(reason, "spool_recovery_byte_limit")
            reserved += size
            try:
                yield
            finally:
                reserved -= size

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            writer = SpotObservationFactWriter(path)
            self.assertTrue(writer.ensure_initialized())
            fact = build_spot_observation_fact({"spot_service_instance_id": "legacy",
                                                "spot_poll_seq": 1, "spot_poll_status": "success",
                                                "spot_last_poll_completed_at": "2026-06-26T00:00:00Z"})
            self.assertEqual(fact["spot_observation_key"], "legacy:1")
            value = {"nested": "'" * 40000 + '\"\U0001f600'}
            fact["instrument_info"] = value
            writer._spool_fact(fact)
            spool = writer._active_spool_segment
            self.assertIsNotNone(spool)
            writer.payload_reservation = reserve
            with ExitStack() as retained:
                rows, end = writer._read_spool_batch(spool, retained)
                self.assertEqual(len(rows), 1)
                text = rows[0][0]["instrument_info"]
                self.assertEqual(text, str(value))
                self.assertEqual(end, spool.stat().st_size)
                self.assertGreaterEqual(reserved, len(text.encode("utf-32-le")),
                                        "recovered text exceeds retained payload reservation")
                rows.clear()
                text = None
            self.assertEqual(reserved, 0)
            writer.payload_reservation = None
            writer._flush_spool()
            with path.open(encoding="utf-8-sig", newline="") as handle:
                stored = list(csv.DictReader(handle))
            self.assertEqual([row["instrument_info"] for row in stored], [str(value)])
            self.assertEqual(writer.spool_pending_count(), 0)

    def test_segmented_spool_rotates_and_preserves_legacy_source(self) -> None:
        from backend.FacilityData.spot_observation_fact import _spool_pending_count

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            legacy = (json.dumps(self.current_fact_row(1)) + "\n").encode("utf-8")
            spool.write_bytes(legacy)
            writer = SpotObservationFactWriter(output, spool_path=spool)
            info = "온" * 120000
            for seq in range(2, 14):
                writer._spool_fact(self.current_fact_row(seq, instrument_info=info))
            self.assertEqual(spool.stat().st_size, len(legacy))
            self.assertEqual(spool.read_bytes(), legacy)
            segments_dir = spool.with_name(spool.name + ".segments-v1")
            segments = sorted(segments_dir.glob("*.jsonl"))
            self.assertEqual(len(segments), 2)
            self.assertTrue(all(0 < path.stat().st_size <= 4 * 1024**2 for path in segments))
            stored_keys = []
            for path in segments:
                stored_keys.extend(json.loads(line)["spot_observation_key"]
                                   for line in path.read_text(encoding="utf-8").splitlines())
            self.assertEqual(stored_keys, [f"svc-1:{seq}" for seq in range(2, 14)])
            self.assertEqual(writer.spool_failure_count, 0)
            self.assertEqual(writer.spool_pending_count(), 13)
            self.assertEqual(_spool_pending_count(spool), 13)
            for _ in range(20):
                if not writer.spool_pending_count():
                    break
                writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 0)
            self.assertEqual(spool.read_bytes(), legacy)
            self.assertEqual(list(segments_dir.glob("*.jsonl")), [])
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_observation_key"] for row in rows],
                             [f"svc-1:{seq}" for seq in range(1, 14)])
            self.assertEqual([row["instrument_info"] for row in rows[1:]], [info] * 12)
            restarted = SpotObservationFactWriter(output, spool_path=spool)
            restarted._flush_spool()
            self.assertEqual(restarted.spool_pending_count(), 0)
            self.assertEqual(restarted.manifest_summary()["row_count"], 13)
            self.assertEqual(spool.read_bytes(), legacy)

    def test_spool_close_failure_blocks_later_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            directory = spool.with_name(spool.name + ".segments-v1")
            writer = SpotObservationFactWriter(output, spool_path=spool)
            self.assertEqual(writer.spool_pending_count(), 0)
            original_open = Path.open

            class FailedClose:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    return self.handle

                def __exit__(self, *args):
                    self.handle.close()
                    raise OSError("injected close failure after actual spool write")

            def failing_open(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                return FailedClose(handle) if path.parent == directory and mode == "xb" else handle

            with patch.object(Path, "open", failing_open):
                writer._spool_fact(self.current_fact_row(1))
            first = list(directory.glob("*.jsonl"))
            self.assertEqual(len(first), 1)
            original = first[0].read_bytes()
            self.assertEqual(json.loads(original)["spot_observation_key"], "svc-1:1")
            writer._spool_fact(self.current_fact_row(2))
            self.assertEqual(len(list(directory.glob("*.jsonl"))), 1)
            self.assertEqual(first[0].read_bytes(), original)
            self.assertEqual(writer.spool_failure_count, 2)
            self.assertEqual(writer.spool_last_error_code, "spool_write_uncertain")
            with self.assertRaisesRegex(ValueError, "UNCERTAIN.*spool"):
                writer._flush_spool()
            self.assertFalse(output.exists())
            self.assertEqual(writer.spool_pending_count(), 1)

    def test_short_spool_write_blocks_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "facts.csv"
            spool = Path(tmp) / "facts.failed.jsonl"
            directory = spool.with_name(spool.name + ".segments-v1")
            writer = SpotObservationFactWriter(output, spool_path=spool)
            self.assertEqual(writer.spool_pending_count(), 0)
            original_open = Path.open
            fact = self.current_fact_row(1, instrument_info="온도")
            payload = (json.dumps(fact, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")

            class ShortWrite:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    return self

                def write(self, data):
                    return self.handle.write(data[:len(data) // 2])

                def __exit__(self, *args):
                    self.handle.close()

            def short_open(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                return ShortWrite(handle) if path.parent == directory and mode == "xb" else handle

            with patch.object(Path, "open", short_open):
                writer._spool_fact(fact)
            self.assertEqual(writer.spool_failure_count, 1)
            self.assertEqual(writer.spool_last_error_code, "spool_write_uncertain")
            segments = list(directory.glob("*.jsonl"))
            self.assertEqual(len(segments), 1)
            self.assertEqual(segments[0].read_bytes(), payload[:len(payload) // 2])
            writer._spool_fact(self.current_fact_row(2))
            self.assertEqual(writer.spool_failure_count, 2)
            self.assertEqual(list(directory.glob("*.jsonl")), segments)
            self.assertEqual(segments[0].read_bytes(), payload[:len(payload) // 2])
            with self.assertRaisesRegex(ValueError, "UNCERTAIN.*spool"):
                writer._flush_spool()
            self.assertFalse(output.exists())
            self.assertEqual(writer.spool_pending_count(), 1)

    def test_failed_write_spools_and_next_success_flushes_pending_fact(self) -> None:
        failed_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 7,
            "spot_observation_seq": 7,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        success_snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 8,
            "spot_observation_seq": 8,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "455.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:01Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            invalid_parent = tmp_path / "not_a_dir"
            invalid_parent.write_text("occupied", encoding="utf-8")
            spool_path = tmp_path / "spot_observation_fact.failed.jsonl"

            failing_writer = SpotObservationFactWriter(
                invalid_parent / "spot_observation_fact.csv",
                spool_path=spool_path,
            )
            self.assertIsNone(failing_writer.write_fact(failed_snapshot))
            self.assertEqual(failing_writer.failure_count, 1)
            segments = spool_path.with_name(spool_path.name + ".segments-v1")
            self.assertFalse(spool_path.exists())
            self.assertEqual(len(list(segments.glob("*.jsonl"))), 1)

            output_path = tmp_path / "spot_observation_fact.csv"
            retrying_writer = SpotObservationFactWriter(output_path, spool_path=spool_path)
            self.assertIsNotNone(retrying_writer.write_fact(success_snapshot))

            rows = output_path.read_text(encoding="utf-8-sig").splitlines()
            self.assertEqual(len(rows), 3)
            self.assertIn("svc-1:7", rows[1])
            self.assertIn("svc-1:8", rows[2])
            self.assertFalse(spool_path.exists())
            self.assertEqual(list(segments.glob("*.jsonl")), [])

    def test_initial_read_retry_rebuilds_partial_index_without_duplicates(self) -> None:
        original_open = Path.open
        snapshot = {"spot_service_instance_id": "initial-read", "spot_poll_seq": 1,
                    "spot_observation_seq": 1, "spot_poll_status": "success",
                    "spot_raw_validity": "valid_temperature", "spot_raw_value_text": "455.0",
                    "spot_last_poll_completed_at": "2026-06-26T00:00:00Z"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            seed = SpotObservationFactWriter(path)
            self.assertIsNotNone(seed.write_fact(snapshot))
            self.assertIsNotNone(seed.write_fact({**snapshot, "spot_poll_seq": 2, "spot_observation_seq": 2}))
            before = path.read_bytes()

            class InterruptedRows:
                def __init__(self, stream):
                    self.stream, self.lines = stream, 0

                def __getattr__(self, name):
                    return getattr(self.stream, name)

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.stream.close()

                def __iter__(self):
                    return self

                def __next__(self):
                    if self.lines == 2:
                        raise OSError("synthetic interrupted history read")
                    self.lines += 1
                    return next(self.stream)

            def interrupted_open(target, mode="r", *args, **kwargs):
                stream = original_open(target, mode, *args, **kwargs)
                return InterruptedRows(stream) if target == path and mode == "r" else stream

            with patch.object(Path, "open", interrupted_open):
                writer = SpotObservationFactWriter(path)
                self.assertFalse(writer.ensure_initialized())
            self.assertTrue(writer.ensure_initialized(), "the same readable original must recover its initial index")
            self.assertEqual(writer.manifest_summary()["row_count"], 2)
            self.assertEqual(writer.manifest_summary()["duplicate_observation_key_count"], 0)
            self.assertGreater(writer.failure_count, 0)
            self.assertIsNone(writer.write_fact(snapshot))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(tmp).glob("*.schema-mismatch.*")), [])

    def test_initial_read_recovery_holds_replaced_deleted_and_unclosed_files(self) -> None:
        original_open = Path.open
        for failure in ("replace", "delete", "close", "invalid_utf8"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "facts.csv"
                seed = SpotObservationFactWriter(path)
                self.assertTrue(seed.ensure_initialized())
                before = path.read_bytes()

                class FailedClose:
                    def __init__(self, stream):
                        self.stream = stream

                    def __getattr__(self, name):
                        return getattr(self.stream, name)

                    def close(self):
                        self.stream.close()
                        raise OSError("synthetic initial reader close failure")

                def failed_open(target, mode="r", *args, **kwargs):
                    if target == path and mode == "rb":
                        if failure == "close":
                            return FailedClose(original_open(target, mode, *args, **kwargs))
                        raise PermissionError("synthetic initial open failure")
                    return original_open(target, mode, *args, **kwargs)

                if failure == "invalid_utf8":
                    path.write_bytes(before + b"\xff\n")
                    writer = SpotObservationFactWriter(path)
                else:
                    with patch.object(Path, "open", failed_open):
                        writer = SpotObservationFactWriter(path)
                if failure == "replace":
                    replacement = path.with_suffix(".replacement")
                    replacement.write_bytes(before)
                    replacement.replace(path)
                elif failure == "delete":
                    path.unlink()
                retained = path.read_bytes() if path.exists() else None
                self.assertFalse(writer.ensure_initialized())
                self.assertTrue(writer.initialization_manual_recovery)
                self.assertFalse(writer.initialization_retryable)
                self.assertEqual(path.read_bytes() if path.exists() else None, retained)
                self.assertEqual(list(Path(tmp).glob("*.schema-mismatch.*")), [])
                # An external repair does not silently clear the uncertainty.
                path.write_bytes(before)
                self.assertFalse(writer.ensure_initialized())
                self.assertEqual(path.read_bytes(), before)

    def test_header_read_failure_preserves_original_and_recovers_pending_fact(self) -> None:
        snapshot = {"spot_service_instance_id": "header-read", "spot_poll_seq": 1,
                    "spot_observation_seq": 1, "spot_poll_status": "success",
                    "spot_raw_validity": "valid_temperature", "spot_raw_value_text": "455.0",
                    "spot_last_poll_completed_at": "2026-06-26T00:00:00Z"}
        original_open = Path.open
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "facts.csv"
            writer = SpotObservationFactWriter(path)
            self.assertIsNotNone(writer.write_fact(snapshot))
            before = path.read_bytes()
            identity = path.stat().st_ino

            def locked_header(target, mode="r", *args, **kwargs):
                if target == path and mode == "r":
                    raise PermissionError("synthetic header read failure")
                return original_open(target, mode, *args, **kwargs)

            with patch.object(Path, "open", locked_header):
                result = writer.write_fact({**snapshot, "spot_poll_seq": 2, "spot_observation_seq": 2})
            self.assertEqual(path.read_bytes(), before, "unreadable header must not replace the original fact")
            self.assertEqual(path.stat().st_ino, identity)
            self.assertEqual(list(Path(tmp).glob("*.schema-mismatch.*")), [])
            self.assertIsNone(result)
            self.assertEqual(writer.failure_count, 1)
            self.assertEqual(writer.spool_pending_count(), 1)
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 0)
            self.assertEqual(writer.failure_count, 1)
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["spot_observation_key"] for row in rows], ["header-read:1", "header-read:2"])

    def test_writer_archives_existing_fact_when_header_mismatches_current_schema(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-current",
            "spot_poll_seq": 10,
            "spot_observation_seq": 10,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "455.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            old_columns = SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(old_columns)
                writer.writerow(["legacy"] * len(old_columns))

            writer = SpotObservationFactWriter(output_path)
            fact = writer.write_fact(snapshot)

            self.assertIsNotNone(fact)
            archives = list(output_path.parent.glob("spot_observation_fact.*.schema-mismatch.csv"))
            self.assertEqual(len(archives), 1)
            with archives[0].open("r", encoding="utf-8-sig", newline="") as handle:
                archived_rows = list(csv.reader(handle))
            self.assertEqual(archived_rows[0], old_columns)
            self.assertEqual(len(archived_rows[1]), len(old_columns))

            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], SPOT_OBSERVATION_FACT_COLUMNS)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[1]), len(SPOT_OBSERVATION_FACT_COLUMNS))
            self.assertIn("svc-current:10", rows[1])

    def test_spool_flush_archives_mismatched_existing_fact_before_writing_pending_rows(self) -> None:
        pending_snapshot = {
            "spot_service_instance_id": "svc-spooled",
            "spot_poll_seq": 11,
            "spot_observation_seq": 11,
            "spot_poll_status": "timeout",
            "spot_raw_validity": "not_received",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
        }
        success_snapshot = {
            "spot_service_instance_id": "svc-current",
            "spot_poll_seq": 12,
            "spot_observation_seq": 12,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "456.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:01Z",
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "spot_observation_fact.csv"
            spool_path = tmp_path / "spot_observation_fact.failed.jsonl"
            old_columns = SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(old_columns)
                writer.writerow(["legacy"] * len(old_columns))
            spool_path.write_text(
                json.dumps(build_spot_observation_fact(pending_snapshot), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            original_spool = spool_path.read_bytes()

            writer = SpotObservationFactWriter(output_path, spool_path=spool_path)
            fact = writer.write_fact(success_snapshot)

            self.assertIsNotNone(fact)
            self.assertEqual(spool_path.read_bytes(), original_spool)
            archives = list(output_path.parent.glob("spot_observation_fact.*.schema-mismatch.csv"))
            self.assertEqual(len(archives), 1)
            with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], SPOT_OBSERVATION_FACT_COLUMNS)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(len(row) == len(SPOT_OBSERVATION_FACT_COLUMNS) for row in rows[1:]))
            self.assertIn("svc-spooled:11", rows[1])
            self.assertIn("svc-current:12", rows[2])

    def test_spool_flush_preserves_legacy_schema_without_rewriting_it_as_current(self) -> None:
        success_snapshot = {
            "spot_service_instance_id": "svc-current",
            "spot_poll_seq": 12,
            "spot_observation_seq": 12,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "456.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:01Z",
        }
        legacy_fact = {column: "" for column in SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS}
        legacy_fact.update(
            {
                "spot_observation_fact_schema_version": SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION,
                "spot_observation_key": "svc-legacy:11",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "spot_observation_fact.csv"
            spool_path = tmp_path / "spot_observation_fact.failed.jsonl"
            spool_path.write_text(json.dumps(legacy_fact) + "\n", encoding="utf-8")
            original_spool = spool_path.read_bytes()

            writer = SpotObservationFactWriter(output_path, spool_path=spool_path)
            fact = writer.write_fact(success_snapshot)

            self.assertIsNone(fact)
            self.assertEqual(writer.failure_count, 1)
            self.assertTrue(spool_path.exists())
            archives = list(
                tmp_path.glob("spot_observation_fact.failed.*.schema-mismatch.jsonl")
            )
            self.assertEqual(archives, [])
            self.assertEqual(spool_path.read_bytes(), original_spool)
            segments = list(spool_path.with_name(spool_path.name + ".segments-v1").glob("*.jsonl"))
            self.assertEqual(len(segments), 1)
            self.assertIn("svc-current:12", segments[0].read_text(encoding="utf-8"))
            self.assertFalse(output_path.exists())
            restarted_writer = SpotObservationFactWriter(
                output_path,
                spool_path=spool_path,
            )
            self.assertEqual(restarted_writer.spool_pending_count(), 2)

    def test_spool_pending_count_caches_archives_and_tracks_active_spool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_path = tmp_path / "spot_observation_fact.csv"
            spool_path = tmp_path / "spot_observation_fact.failed.jsonl"
            archive_path = (
                tmp_path
                / "spot_observation_fact.failed.20260731T000000Z.schema-mismatch.jsonl"
            )
            first_fact = self.current_fact_row(1)
            second_fact = self.current_fact_row(2)
            spool_path.write_text(
                json.dumps(first_fact) + "\n",
                encoding="utf-8",
            )
            archive_path.write_text("legacy-one\nlegacy-two\n", encoding="utf-8")
            writer = SpotObservationFactWriter(
                output_path,
                spool_path=spool_path,
            )

            self.assertEqual(writer.spool_pending_count(), 3)
            with patch.object(
                Path,
                "open",
                side_effect=AssertionError("cached health read rescanned spool files"),
            ):
                self.assertEqual(writer.spool_pending_count(), 3)

            writer._spool_fact(second_fact)
            self.assertEqual(writer.spool_pending_count(), 4)
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 3)
            writer._flush_spool()
            self.assertEqual(writer.spool_pending_count(), 2)

    def test_spool_flush_preserves_invalid_rows_and_fails_closed(self) -> None:
        success_snapshot = {
            "spot_service_instance_id": "svc-current",
            "spot_poll_seq": 12,
            "spot_observation_seq": 12,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_raw_value_text": "456.0",
            "spot_last_poll_completed_at": "2026-06-26T00:00:01Z",
        }
        invalid_rows = {
            "malformed-json": '{"spot_observation_key":"truncated"',
            "non-object-json": '["not", "a", "fact"]',
        }
        for label, invalid_row in invalid_rows.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                output_path = tmp_path / "spot_observation_fact.csv"
                spool_path = tmp_path / "spot_observation_fact.failed.jsonl"
                spool_path.write_text(f"{invalid_row}\n", encoding="utf-8")

                writer = SpotObservationFactWriter(
                    output_path,
                    spool_path=spool_path,
                )
                fact = writer.write_fact(success_snapshot)

                self.assertIsNone(fact)
                self.assertEqual(writer.failure_count, 1)
                archives = list(
                    tmp_path.glob(
                        "spot_observation_fact.failed.*.schema-mismatch.jsonl"
                    )
                )
                self.assertEqual(archives, [])
                self.assertEqual(spool_path.read_text(encoding="utf-8").strip(), invalid_row)
                self.assertTrue(spool_path.exists())
                segments = list(spool_path.with_name(spool_path.name + ".segments-v1").glob("*.jsonl"))
                self.assertEqual(len(segments), 1)
                self.assertIn(
                    "svc-current:12",
                    segments[0].read_text(encoding="utf-8"),
                )

                restarted_writer = SpotObservationFactWriter(
                    output_path,
                    spool_path=spool_path,
                )
                self.assertEqual(restarted_writer.failure_count, 0)
                self.assertEqual(restarted_writer.spool_pending_count(), 2)

    def test_build_fact_uses_missing_diagnostics_status(self) -> None:
        fact = build_spot_observation_fact(
            {
                "spot_service_instance_id": "svc-1",
                "spot_poll_seq": 1,
                "spot_poll_status": "timeout",
                "spot_raw_validity": "not_received",
                "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            }
        )

        self.assertEqual(fact["diagnostics_capture_status"], "missing")
        self.assertEqual(fact["spot_observation_key"], "svc-1:1")

    def test_build_fact_preserves_diagnostics_and_derives_evidence_codes(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 2,
            "spot_poll_status": "success",
            "spot_raw_validity": "invalid_sentinel",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "LOW SIGNAL",
            "signalpc": "3.2",
            "peak_picker_enabled": True,
            "peak_picker_off_mode": "reset",
            "actuator_scan_state": "scanning",
            "spot_diagnostic_evidence_codes": '["target_absent_verified"]',
            **self.diagnostics_metadata(
                2,
                success_fields=("alarmstatus", "signalpc"),
            ),
        }

        fact = build_spot_observation_fact(snapshot)
        evidence_codes = derive_spot_diagnostic_evidence_codes(snapshot)

        self.assertEqual(fact["diagnostics_capture_status"], "async_partial")
        self.assertEqual(fact["diagnostics_binding_status"], "same_poll")
        self.assertEqual(fact["diagnostics_age_ms"], "10.0")
        self.assertEqual(fact["diagnostics_source"], "async_same_poll")
        self.assertTrue(json.loads(fact["evidence_provenance_json"]))
        self.assertIn("alarm_low_signal", fact["spot_diagnostic_evidence_codes"])
        self.assertEqual(fact["alarmstatus"], "LOW SIGNAL")
        self.assertEqual(fact["signalpc"], "3.2")
        self.assertEqual(fact["peak_picker_off_mode"], "reset")
        self.assertEqual(fact["actuator_scan_state"], "scanning")
        self.assertEqual(
            set(evidence_codes),
            {
                "actuator_scanning",
                "alarm_low_signal",
                "peak_picker_off_mode_reset_configured",
                "signalpc_present_threshold_unknown",
                "target_absent_verified",
            },
        )
        self.assertEqual(
            encode_spot_diagnostic_evidence_codes(snapshot),
            '["actuator_scanning","alarm_low_signal","peak_picker_off_mode_reset_configured","signalpc_present_threshold_unknown","target_absent_verified"]',
        )

    def test_build_fact_preserves_parse_failure_raw_value_without_using_it_as_evidence(self) -> None:
        metadata = self.diagnostics_metadata(
            3,
            success_fields=tuple(
                field for field in SPOT_DIAGNOSTIC_OUTPUT_FIELDS if field != "signalpc"
            ),
        )
        field_status = dict(metadata["diagnostics_field_status"])
        field_status["signalpc"] = "parse_error"
        metadata["diagnostics_field_status"] = field_status
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 3,
            "spot_poll_status": "success",
            "spot_raw_validity": "valid_temperature",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "diagnostics_raw_values": {"signalpc": "6553.4"},
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": False,
            **metadata,
        }

        fact = build_spot_observation_fact(snapshot)

        self.assertNotIn("signalpc", snapshot)
        self.assertEqual(fact["signalpc"], "6553.4")
        self.assertEqual(
            json.loads(fact["diagnostics_field_status_json"])["signalpc"],
            "parse_error",
        )
        self.assertEqual(fact["spot_diagnostic_evidence_codes"], "")
        self.assertEqual(fact["evidence_provenance_json"], "")
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)
            self.assertIsNotNone(writer.write_fact(snapshot))
            self.assertEqual(validate_spot_observation_fact_invariants(output_path), [])

    def test_numeric_alarmstatus_bit_four_derives_alarm_low_signal(self) -> None:
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes({"alarmstatus": "16"}),
            ("alarm_low_signal",),
        )
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes({"alarmstatus": "0x10"}),
            ("alarm_low_signal",),
        )
        self.assertEqual(derive_spot_diagnostic_evidence_codes({"alarmstatus": "0"}), ())

    def test_signalpc_with_configured_lte_threshold_derives_signal_below_threshold_when_alarm_enabled(self) -> None:
        snapshot = {
            "signalpc": "3.2",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lte",
            "low_signal_comparator_verified": True,
        }

        self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ("signal_below_threshold",))
        self.assertEqual(encode_spot_diagnostic_evidence_codes(snapshot), '["signal_below_threshold"]')

    def test_signalpc_below_threshold_alarm_disabled_records_non_causal_evidence(self) -> None:
        snapshot = {
            "signalpc": "1.5",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": True,
        }

        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(snapshot),
            ("signal_below_configured_threshold_alarm_disabled",),
        )

    def test_signalpc_threshold_edge_respects_lt_and_lte_comparators(self) -> None:
        lte_snapshot = {
            "signalpc": "5.0",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lte",
            "low_signal_comparator_verified": True,
        }
        lt_snapshot = {
            "signalpc": "5.0",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "5.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": True,
        }

        self.assertEqual(derive_spot_diagnostic_evidence_codes(lte_snapshot), ("signal_below_threshold",))
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(lt_snapshot),
            ("signal_at_or_above_configured_threshold",),
        )

    def test_signalpc_without_threshold_records_threshold_unknown(self) -> None:
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes({"signalpc": "3.2"}),
            ("signalpc_present_threshold_unknown",),
        )

    def test_signalpc_at_or_above_configured_threshold_records_non_low_evidence(self) -> None:
        snapshot = {
            "signalpc": "6.0",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": True,
        }

        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(snapshot),
            ("signal_at_or_above_configured_threshold",),
        )

    def test_signalpc_with_unverified_comparator_records_non_causal_evidence(self) -> None:
        snapshot = {
            "signalpc": "1.5",
            "low_signal_alarm_enabled": True,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": False,
            "spot_diagnostic_evidence_codes": '["signal_below_threshold"]',
        }

        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(snapshot),
            ("signalpc_present_comparator_unverified",),
        )

    def test_invalid_signalpc_value_does_not_set_low(self) -> None:
        cases = [
            {"signalpc": "not-a-number", "low_signal_threshold_pc": "5.0", "low_signal_comparator": "lte"},
            {"signalpc": "nan", "low_signal_threshold_pc": "5.0", "low_signal_comparator": "lte"},
            {"signalpc": "101", "low_signal_threshold_pc": "5.0", "low_signal_comparator": "lte"},
        ]

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ())

    def test_valid_signalpc_with_invalid_threshold_records_threshold_unknown(self) -> None:
        self.assertEqual(
            derive_spot_diagnostic_evidence_codes(
                {"signalpc": "3.2", "low_signal_threshold_pc": "nan", "low_signal_comparator": "lte"}
            ),
            ("signalpc_present_threshold_unknown",),
        )

    def test_peak_picker_disabled_does_not_emit_reset_evidence(self) -> None:
        snapshot = {"peak_picker_enabled": False, "peak_picker_off_mode": "reset"}

        self.assertEqual(derive_spot_diagnostic_evidence_codes(snapshot), ())

    def test_spot_observation_fact_validator_accepts_alarmstatus_bit4_with_evidence(self) -> None:
        snapshot = {
            "spot_service_instance_id": "svc-1",
            "spot_poll_seq": 9,
            "spot_observation_seq": 9,
            "spot_poll_status": "success",
            "spot_raw_validity": "invalid_sentinel",
            "spot_last_poll_completed_at": "2026-06-26T00:00:00Z",
            "alarmstatus": "0x10",
            "signalpc": "6.0",
            "low_signal_alarm_enabled": False,
            "low_signal_threshold_pc": "2.0",
            "low_signal_comparator": "lt",
            "low_signal_comparator_verified": False,
            "peak_picker_enabled": False,
            **self.diagnostics_metadata(9),
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            writer = SpotObservationFactWriter(output_path)
            fact = writer.write_fact(snapshot)

            self.assertIsNotNone(fact)
            assert fact is not None
            self.assertIn("spot_diagnostic_evidence_codes", fact)
            self.assertIn("alarm_low_signal", fact["spot_diagnostic_evidence_codes"])
            self.assertEqual(validate_spot_observation_fact_invariants(output_path), [])

    def test_validator_rejects_numeric_evidence_when_comparator_is_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            row = self.current_fact_row(
                signalpc="1.5",
                low_signal_alarm_enabled=True,
            )
            row.update(
                {
                    "spot_diagnostic_evidence_codes": '["signal_below_threshold"]',
                }
            )
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

            failures = validate_spot_observation_fact_invariants(output_path)

        self.assertTrue(any("numeric low-signal evidence is forbidden" in failure for failure in failures))

    def test_spot_observation_fact_validator_rejects_row_length_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writerow([""] * (len(SPOT_OBSERVATION_FACT_COLUMNS) - 1))

            failures = validate_spot_observation_fact_invariants(output_path)

        self.assertTrue(any("columns, expected" in failure for failure in failures))

    def test_spot_observation_fact_validator_rejects_alarmstatus_bit4_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact.csv"
            row = self.current_fact_row(alarmstatus="16")
            row.update(
                {
                    "spot_diagnostic_evidence_codes": "[]",
                }
            )
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=SPOT_OBSERVATION_FACT_COLUMNS)
                writer.writeheader()
                writer.writerow(row)

            failures = validate_spot_observation_fact_invariants(output_path)

        self.assertTrue(any("alarmstatus bit4 requires alarm_low_signal" in failure for failure in failures))

    def test_historical_v1_2_1_fact_schema_remains_valid(self) -> None:
        row = {column: "" for column in SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS}
        row.update(
            {
                "spot_observation_fact_schema_version": SPOT_OBSERVATION_FACT_V1_2_1_SCHEMA_VERSION,
                "spot_poll_seq": "9",
                "diagnostics_capture_status": "async_enriched",
                "diagnostics_age_ms": "10.0",
                "spot_diagnostic_evidence_codes": "[]",
                "low_signal_alarm_enabled": "false",
                "low_signal_comparator_verified": "false",
                "peak_picker_enabled": "false",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "spot_observation_fact-v1.2.1.csv"
            with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=SPOT_OBSERVATION_FACT_V1_2_1_COLUMNS,
                )
                writer.writeheader()
                writer.writerow(row)

            failures = validate_spot_observation_fact_invariants(output_path)

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
