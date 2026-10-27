import asyncio
import csv
import hashlib
import io
import json
from contextlib import contextmanager
import os
from pathlib import Path
import queue
import shutil
import stat
import subprocess
import threading
import time
import tracemalloc
from typing import Any
import unittest
from uuid import uuid4
from unittest.mock import patch
from starlette.requests import Request
from starlette.responses import Response
from backend.FacilityData.persistence_validation import validate_csv_persistence_trace

_TEST_ROOT = Path(__file__).resolve().parents[2]
_TEST_APPDATA_ROOT = _TEST_ROOT / ".tmp_test_appdata"
_TEST_TEMP_ROOT = _TEST_ROOT / ".tmp_test_temp"
_TEST_CONFIG_PATH = _TEST_APPDATA_ROOT / "config.ini"

os.environ.setdefault("APPDATA", str(_TEST_APPDATA_ROOT))
os.environ.setdefault("SFL_CONFIG_PATH", str(_TEST_CONFIG_PATH))


def _check_writable_temp_root(temp_root: Path) -> tuple[bool, str]:
    try:
        temp_root.mkdir(parents=True, exist_ok=True)
        probe_dir = temp_root / ".probe_dir"
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe_path = probe_dir / ".probe_write.txt"
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        if probe_dir.exists():
            shutil.rmtree(probe_dir)
    except PermissionError as exc:
        return False, f"temp root permission denied: {exc}"
    except OSError as exc:
        return False, f"temp root not writable: {exc}"
    return True, ""


def _remove_readonly_test_artifact(function: Any, path: str, _exc_info: Any) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)


_TEMP_ROOT_READY, _TEMP_ROOT_REASON = _check_writable_temp_root(_TEST_TEMP_ROOT)

from backend.FacilityData.repository import CSVLoggerService, V2_CSV_COLUMNS
from backend.FacilityData.schemas import FactoryData
from backend import config
from backend import version as backend_version
from backend.version import __version__, get_runtime_info

try:
    from backend import app as backend_app
except Exception:
    backend_app = None


class CSVLoggerServiceTests(unittest.TestCase):
    def test_validator_requires_each_admitted_sink_result(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=True, csv_v2_enabled=True)
            service.start()
            try:
                self.assertEqual(service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))["status"],
                                 "ACCEPTED")
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            paths = sorted(tmp_dir.rglob("*.trace.jsonl"))
            self.assertEqual(validate_csv_persistence_trace(paths)["issues"], [])
            original = {path: path.read_bytes() for path in paths}
            removed = 0
            for path in paths:
                retained = []
                for line in path.read_bytes().splitlines(keepends=True):
                    record = json.loads(line)
                    if record.get("kind") == "csv_row_data" and record["sink_id"] == "csv_v2":
                        removed += 1
                    else:
                        retained.append(line)
                path.write_bytes(b"".join(retained))
            self.assertEqual(removed, 1)
            before = {path: path.read_bytes() for path in paths}
            result = validate_csv_persistence_trace(paths)
            self.assertEqual(result["status"], "INCOMPLETE", "missing required sink evidence was not rejected")
            self.assertIn("missing_required_sink_evidence", result["issues"])
            self.assertEqual({path: path.read_bytes() for path in paths}, before)
            for changes, issue in [({"source_payload_hash": "f" * 64}, "sink_evidence_contract_mismatch"),
                                   ({"config_generation": 999}, "sink_evidence_contract_mismatch"),
                                   ({"producer_seq": 999}, "unadmitted_sink_evidence"),
                                   ({"record_version": True}, "unsupported_csv_row_evidence")]:
                with self.subTest(changes=changes):
                    for path, contents in original.items():
                        lines = []
                        for line in contents.splitlines(keepends=True):
                            record = json.loads(line)
                            if record.get("kind") == "csv_row_data" and record["sink_id"] == "csv_v2":
                                line = (json.dumps(dict(record, **changes)) + "\n").encode()
                            lines.append(line)
                        path.write_bytes(b"".join(lines))
                    result = validate_csv_persistence_trace(paths)
                    self.assertEqual(result["status"], "INCOMPLETE")
                    self.assertIn(issue, result["issues"])
            for path, contents in original.items():
                path.write_bytes(contents)
            records = [json.loads(line) for path in paths for line in path.read_bytes().splitlines()]
            admission = next(record for record in records if record.get("kind") == "csv_admission")
            failure = dict(admission, kind="csv_processing_failure", contract_version="CSV_PROCESSING_FAILURE_V1",
                           sink_id="csv_v2", status="FAILED", reason="fixture_decode_failure")
            for path, contents in original.items():
                path.write_bytes(b"".join((json.dumps(failure) + "\n").encode()
                                          if json.loads(line).get("kind") == "csv_row_data"
                                          and json.loads(line).get("sink_id") == "csv_v2" else line
                                          for line in contents.splitlines(keepends=True)))
            result = validate_csv_persistence_trace(paths)
            self.assertIn("recorded_csv_processing_failure", result["issues"])
            self.assertNotIn("missing_required_sink_evidence", result["issues"])
            for path, contents in original.items():
                path.write_bytes(contents)
            row = next(record for record in records if record.get("kind") == "csv_row_data")
            with paths[-1].open("ab") as handle:
                handle.write((json.dumps(row) + "\n").encode())
            self.assertIn("multiple_sink_outcomes", validate_csv_persistence_trace(paths)["issues"])

    def test_validator_rejects_missing_admission_identity(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            service.start()
            try:
                receipts = [service.enqueue_detailed(self.create_data(f"2026-03-09T07:20:2{i}.000", 30.0 + i))
                            for i in range(3)]
                self.assertTrue(all(receipt["status"] == "ACCEPTED" for receipt in receipts))
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            paths = sorted(tmp_dir.rglob("*.trace.jsonl"))
            self.assertEqual(validate_csv_persistence_trace(paths)["issues"], [])
            removed = 0
            for path in paths:
                retained = []
                for line in path.read_bytes().splitlines(keepends=True):
                    record = json.loads(line)
                    if record.get("kind") == "csv_admission" and record["producer_seq"] == receipts[1]["producer_seq"]:
                        removed += 1
                    else:
                        retained.append(line)
                path.write_bytes(b"".join(retained))
            self.assertEqual(removed, 1)
            before = {path: path.read_bytes() for path in paths}
            result = validate_csv_persistence_trace(paths)
            self.assertEqual(result["status"], "INCOMPLETE", "missing admission identity was not rejected")
            self.assertIn("admission_identity_totals_mismatch", result["issues"])
            self.assertIn("missing_admission_identities", result["issues"])
            self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_persistence_validation_requires_producer_boundaries(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            service.start()
            try:
                service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            paths = sorted(tmp_dir.rglob("*.trace.jsonl"))
            self.assertTrue(paths)
            original = {path: path.read_bytes() for path in paths}
            self.assertEqual(validate_csv_persistence_trace(paths)["issues"], [])
            removed = 0
            for path, contents in original.items():
                kept = []
                for line in contents.splitlines(keepends=True):
                    if json.loads(line).get("kind") == "producer_start":
                        removed += 1
                    else:
                        kept.append(line)
                path.write_bytes(b"".join(kept))
            self.assertEqual(removed, 1)
            before = {path: path.read_bytes() for path in paths}
            result = validate_csv_persistence_trace(paths)
            self.assertEqual(result["status"], "INCOMPLETE", "missing producer boundary was not rejected")
            self.assertIn("missing_producer_start", result["issues"])
            self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
            self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_persistence_validation_rejects_inconsistent_admission_totals(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            service.start()
            try:
                service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            paths = sorted(tmp_dir.rglob("*.trace.jsonl"))
            changed = 0
            for path in paths:
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                for record in records:
                    if record.get("kind") == "admission_summary":
                        record["accepted_count"] += 1
                        changed += 1
                path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8", newline="")
            self.assertEqual(changed, 1)
            result = validate_csv_persistence_trace(paths)
            self.assertEqual(result["status"], "INCOMPLETE", "inconsistent admission totals were not rejected")
            self.assertIn("admission_totals_mismatch", result["issues"])
            self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")

    def test_persistence_validation_rejects_missing_terminal_summary(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            service.start()
            try:
                receipt = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.assertEqual(receipt["status"], "ACCEPTED")
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            paths = sorted(tmp_dir.rglob("*.trace.jsonl"))
            self.assertTrue(paths)
            removed = 0
            for path in paths:
                retained = []
                for line in path.read_bytes().splitlines(keepends=True):
                    if json.loads(line).get("kind") == "admission_summary":
                        removed += 1
                    else:
                        retained.append(line)
                path.write_bytes(b"".join(retained))
            self.assertEqual(removed, 1)
            before = {path: path.read_bytes() for path in paths}
            result = validate_csv_persistence_trace(paths)
            self.assertEqual(result["status"], "INCOMPLETE", "missing terminal evidence was not classified incomplete")
            self.assertIn("missing_admission_summary", result["issues"])
            self.assertEqual(result["data_integrity_status"], "NOT_EVALUATED")
            self.assertEqual({path: path.read_bytes() for path in paths}, before)

    VALID_GIT_COMMIT = "1234567890abcdef1234567890abcdef12345678"

    @contextmanager
    def create_temp_dir(self) -> Path:
        if not _TEMP_ROOT_READY:
            self.skipTest(_TEMP_ROOT_REASON)
        temp_dir = _TEST_TEMP_ROOT / f"case_{int(time.time() * 1000)}_{uuid4().hex[:8]}"
        try:
            temp_dir.mkdir(parents=True, exist_ok=False)
            probe_path = temp_dir / ".probe_write.txt"
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
        except PermissionError as exc:
            self.skipTest(f"temp dir permission denied: {exc}")
        except OSError as exc:
            self.skipTest(f"temp dir not writable: {exc}")
        try:
            yield temp_dir
        finally:
            resolved_temp_root = _TEST_TEMP_ROOT.resolve(strict=False)
            resolved_temp_dir = temp_dir.resolve(strict=False)
            if resolved_temp_root not in resolved_temp_dir.parents:
                raise RuntimeError(f"temp dir outside test root: {resolved_temp_dir}")
            if temp_dir.exists():
                shutil.rmtree(temp_dir, onexc=_remove_readonly_test_artifact)

    def create_service(
        self,
        log_dir: Path,
        auto_save: bool,
        *,
        csv_v1_enabled: bool = True,
        csv_v2_enabled: bool = False,
    ) -> CSVLoggerService:
        service = CSVLoggerService()
        service.fallback_log_dir = log_dir
        service.apply_config(
            log_path=log_dir,
            auto_save=auto_save,
            csv_v1_enabled=csv_v1_enabled,
            csv_v2_enabled=csv_v2_enabled,
            csv_header="Date,Time,Temperature,MainPress,BilletLength,Temp_F,Temp_B,Count,Speed,EndPos,Mold1,Mold2,Mold3,Mold4,Mold5,Mold6,Billet_Temp,At_Pre,At_Temp,DIE_ID,Billet_CycleID",
        )
        return service

    def create_data(self, timestamp_text: str, press_value: float) -> FactoryData:
        return FactoryData(
            Time=timestamp_text,
            Status="Running",
            Press=press_value,
            Spot=100.0,
            Billet_Length=1.0,
            Temp_F=2.0,
            Temp_B=3.0,
            Count=1,
            Speed=4.0,
            EndPos=5.0,
            Mold1=6.0,
            Mold2=7.0,
            Mold3=8.0,
            Mold4=9.0,
            Mold5=10.0,
            Mold6=11.0,
            Billet_Temp=12.0,
            At_Pre=13.0,
            At_Temp=14.0,
            Die_ID="D1",
            Billet_Cycle_ID="C1",
        )

    def capture_partial_csv_batch(self, change_file=None, *, v2=False):
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=not v2, csv_v2_enabled=v2)
            original_open = Path.open
            entered, release = threading.Event(), threading.Event()
            failed = False
            writes = 0
            rows_at_failure = []
            header_at_failure = []
            failure_bytes = b""

            class PartialBatchFile:
                def __init__(self, handle, path):
                    self.handle, self.path = handle, path

                def __getattr__(self, name):
                    return getattr(self.handle, name)

                def write(self, text):
                    nonlocal failed, writes, failure_bytes
                    writes += 1
                    if writes == 9 and not failed:  # Header and seven real data rows.
                        failed = True
                        self.handle.flush()
                        with original_open(self.path, "r", newline="", encoding="utf-8-sig") as reader:
                            records = list(csv.reader(reader))
                            header_at_failure.extend(records[0])
                            rows_at_failure.extend(records[1:])
                        if change_file is not None:
                            change_file(self.path)
                        failure_bytes = self.path.read_bytes()
                        raise OSError("synthetic CSV write failure after seven rows")
                    return self.handle.write(text)

            def partial_open(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                if path.suffix == ".csv" and mode == "a" and path.name.startswith("Factory_Integrated_Log"):
                    entered.set()
                    if not release.wait(5):
                        handle.close()
                        raise TimeoutError("CSV partial batch test did not release writer")
                    return PartialBatchFile(handle, path)
                return handle

            with patch.object(Path, "open", partial_open):
                service.start()
                try:
                    receipts = [service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 0.0))]
                    self.assertTrue(entered.wait(2))
                    receipts.extend(service.enqueue_detailed(self.create_data(
                        f"2026-03-09T07:20:25.{index:03d}", float(index))) for index in range(1, 20))
                finally:
                    release.set()
                    closed = service.stop(timeout_sec=10)
            self.assertTrue(all(receipt["status"] == "ACCEPTED" for receipt in receipts))
            press_index = header_at_failure.index("MainPress")
            self.assertEqual([float(row[press_index]) for row in rows_at_failure], list(range(7)))
            files = list(tmp_dir.glob("Factory_Integrated_Log*.csv"))
            self.assertEqual(len(files), 1)
            rows = self.read_rows(files[0])[1:]
            return {"rows": rows, "header": header_at_failure, "prefix": rows_at_failure, "closed": closed,
                    "state": service.get_runtime_state(), "before_retry": failure_bytes,
                    "after_retry": files[0].read_bytes()}

    def test_partial_csv_batch_retry_preserves_each_row_once(self) -> None:
        for v2 in (False, True):
            with self.subTest(v2=v2):
                result = self.capture_partial_csv_batch(v2=v2)
                press_index = result["header"].index("MainPress")
                self.assertEqual([float(row[press_index]) for row in result["rows"]], list(range(20)),
                                 "partial CSV batch retry duplicated persisted rows")
                self.assertEqual(result["rows"][:7], result["prefix"])
                if v2:
                    sequence_index = result["header"].index("sample_seq")
                    self.assertEqual([int(row[sequence_index]) for row in result["rows"]], list(range(1, 21)))
                self.assertFalse(result["closed"], "recovery must not erase the write failure")
                state = result["state"]
                self.assertEqual(state["pending_event_count"], 0)
                self.assertEqual(state["pending_payload_bytes"], 0)
                self.assertEqual(state["csv_write_failure_count"], 1)
                self.assertEqual(state["last_csv_write_failure_reason"], "csv_write_or_readback_failed")

    def test_csv_retry_preserves_uncertain_file_bytes(self) -> None:
        # Regression guards for the readback checks introduced by the real
        # 7/20-row failure; these are not separate claimed RED/GREEN changes.
        def damage_file(path, mode):
            with path.open("r+b") as handle:
                if mode == "partial_tail":
                    handle.seek(0, 2)
                    handle.write(b"2026-03-09,INCOMPLETE")
                else:
                    handle.readline()
                    handle.write(b"X")

        for mode in ("partial_tail", "changed_record"):
            with self.subTest(mode=mode):
                result = self.capture_partial_csv_batch(lambda path: damage_file(path, mode))
                self.assertEqual(result["after_retry"], result["before_retry"])
                self.assertFalse(result["closed"])
                self.assertEqual(result["state"]["pending_event_count"], 20)
                self.assertEqual(result["state"]["uncertain_csv_file_count"], 1)

    def test_csv_retry_does_not_restore_unexpectedly_removed_rows(self) -> None:
        def remove_written_rows(path):
            with path.open("r+b") as handle:
                header_length = len(handle.readline())
                handle.truncate(header_length)

        result = self.capture_partial_csv_batch(remove_written_rows)
        self.assertEqual(result["after_retry"], result["before_retry"],
                         "CSV retry silently restored unexpectedly removed rows")
        self.assertFalse(result["closed"])
        self.assertEqual(result["state"]["pending_event_count"], 20)

    def test_csv_close_failure_prevents_clean_shutdown(self) -> None:
        original_open = Path.open

        class CloseFailure:
            def __init__(self, handle):
                self.handle = handle

            def __getattr__(self, name):
                return getattr(self.handle, name)

            def close(self):
                if not leave_open:
                    self.handle.close()
                raise OSError("synthetic CSV close failure")

        def failing_open(path, mode="r", *args, **kwargs):
            handle = original_open(path, mode, *args, **kwargs)
            if mode == "a" and path.name.startswith("Factory_Integrated_Log") and path.suffix == ".csv":
                opened.append(handle)
                return CloseFailure(handle)
            return handle

        for v2, leave_open in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(v2=v2, leave_open=leave_open), self.create_temp_dir() as tmp_dir:
                opened = []
                service = self.create_service(tmp_dir, True, csv_v1_enabled=not v2, csv_v2_enabled=v2)
                try:
                    with patch.object(Path, "open", failing_open):
                        service.start()
                        service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                        service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.100", 31.0))
                        closed = service.stop(timeout_sec=5)
                    files = list(tmp_dir.glob("Factory_Integrated_Log*.csv"))
                    self.assertEqual(len(files), 1)
                    self.assertEqual(len(self.read_rows(files[0])), 3)
                    self.assertFalse(closed, "CSV close failure was reported as clean shutdown")
                    state = service.get_runtime_state()
                    self.assertEqual(state["last_csv_write_failure_reason"], "csv_close_failed")
                    self.assertGreaterEqual(state["csv_write_failure_count"], 1)
                    self.assertEqual(state["uncertain_csv_file_count"], 1)
                    self.assertEqual(state["unclosed_csv_handle_count"], int(leave_open))
                    with self.assertRaisesRegex(RuntimeError, "CSV file state"):
                        service.start()
                finally:
                    for handle in opened:
                        handle.close()

    def test_csv_close_uncertainty_blocks_rollover_and_new_admission(self) -> None:
        original_open = Path.open
        for v2 in (False, True):
            for change in ("date", "destination"):
                for leave_open in (False, True):
                    with self.subTest(v2=v2, change=change, leave_open=leave_open), self.create_temp_dir() as tmp_dir:
                        old_dir, new_dir = tmp_dir / "old", tmp_dir / "new"
                        old_dir.mkdir()
                        new_dir.mkdir()
                        entered, release, failed = threading.Event(), threading.Event(), threading.Event()
                        opened = []
                        opened_paths = []
                        service = self.create_service(old_dir, True, csv_v1_enabled=not v2, csv_v2_enabled=v2)

                        class CloseFailure:
                            def __init__(self, handle):
                                self.handle = handle

                            def __getattr__(self, name):
                                return getattr(self.handle, name)

                            def close(self):
                                if not leave_open:
                                    self.handle.close()
                                failed.set()
                                raise OSError("synthetic close uncertainty at rollover")

                        def held_open(path, mode="r", *args, **kwargs):
                            handle = original_open(path, mode, *args, **kwargs)
                            if mode == "a" and path.name.startswith("Factory_Integrated_Log") and path.suffix == ".csv":
                                opened.append(handle)
                                opened_paths.append(path)
                                if len(opened_paths) == 1:
                                    entered.set()
                                    if not release.wait(5):
                                        handle.close()
                                        raise TimeoutError("CSV rollover fixture was not released")
                                    return CloseFailure(handle)
                            return handle

                        try:
                            with patch.object(Path, "open", held_open):
                                service.start()
                                try:
                                    first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                                    self.assertTrue(entered.wait(2))
                                    if change == "destination":
                                        service.apply_config(log_path=new_dir)
                                    timestamp = "2026-03-10T07:20:25.000" if change == "date" else "2026-03-09T07:20:26.000"
                                    second = service.enqueue_detailed(self.create_data(timestamp, 31.0))
                                    queued = [second, *(service.enqueue_detailed(self.create_data(timestamp, value))
                                                        for value in (32.0, 33.0))]
                                    release.set()
                                    self.assertTrue(failed.wait(2))
                                    deadline = time.monotonic() + 2
                                    while (not service.get_runtime_state().get("csv_manual_recovery_required")
                                           and len(opened_paths) == 1 and time.monotonic() < deadline):
                                        time.sleep(.01)
                                    late = service.enqueue_detailed(self.create_data(timestamp, 32.0))
                                finally:
                                    release.set()
                                    closed = service.stop(timeout_sec=5)
                            self.assertEqual(first["status"], "ACCEPTED")
                            self.assertTrue(all(receipt["status"] == "ACCEPTED" for receipt in queued))
                            self.assertEqual(len(opened_paths), 1, "CSV rollover bypassed unresolved close ownership")
                            self.assertEqual(len(list(tmp_dir.rglob("Factory_Integrated_Log*.csv"))), 1)
                            self.assertEqual(len(self.read_rows(opened_paths[0])), 2)
                            self.assertEqual(late["status"], "REJECTED_UNAVAILABLE")
                            self.assertEqual(late["reason"], "csv_owner_requires_manual_recovery")
                            self.assertFalse(closed)
                            state = service.get_runtime_state()
                            self.assertTrue(state["csv_manual_recovery_required"])
                            self.assertEqual(state["pending_event_count"], len(queued))
                            self.assertEqual(state["unclosed_csv_handle_count"], int(leave_open))
                            records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                                       for line in path.read_text(encoding="utf-8").splitlines()[1:]]
                            admissions = [record for record in records if record.get("kind") == "csv_admission"]
                            self.assertEqual({record["producer_seq"] for record in admissions},
                                             {receipt["producer_seq"] for receipt in (first, *queued)},
                                             "terminal trace lost accepted IDs blocked before writer adoption")
                            self.assertEqual(len(admissions), len(queued) + 1)
                            retained = next(record for record in admissions if record["producer_seq"] == second["producer_seq"])
                            self.assertEqual(retained["config_generation"], second["config_generation"])
                            self.assertEqual(Path(retained["admitted_log_dir"]), new_dir if change == "destination" else old_dir)
                            summary = next(record for record in records if record.get("kind") == "admission_summary")
                            self.assertEqual(summary["required_sink_outcomes"]["outstanding_event_count"], len(queued))
                            self.assertEqual(summary["data_integrity_status"], "NOT_EVALUATED")
                        finally:
                            for handle in opened:
                                handle.close()

    def test_trace_publish_failure_prevents_clean_csv_shutdown(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, auto_save=True)
            original_replace = Path.replace

            def fail_trace(source, target):
                if str(target).endswith(".trace.jsonl"):
                    self.assertGreater(source.stat().st_size, 0)
                    raise OSError("synthetic trace publication failure")
                return original_replace(source, target)

            with patch.object(Path, "replace", fail_trace):
                service.start()
                first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                last = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.100", 31.0))
                closed = service.stop(timeout_sec=5)
            self.assertFalse(closed, "CSV shutdown ignored missing producer trace evidence")
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [30.0, 31.0])
            runtime = service.get_runtime_state()
            self.assertEqual(runtime["pending_event_count"], 2,
                             "CSV events completed before their row evidence was committed")
            self.assertEqual(runtime["csv_data_written_evidence_pending_count"], 2)
            self.assertEqual(runtime["csv_evidence_pending_by_sink"], {"csv_v1": 2, "csv_v2": 0})
            state = runtime["persistence_trace"]
            self.assertGreaterEqual(state["failure_count"], 1)
            self.assertGreaterEqual(state["pending_records"], 2)
            self.assertEqual(list(tmp_dir.rglob("*.trace.jsonl")), [])
            pending = list(tmp_dir.rglob("*.pending"))
            self.assertEqual(len(pending), 1)
            records = [json.loads(line) for line in pending[0].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["producer_instance_id"], first["producer_instance_id"])
            boundaries = [record for record in records[1:] if record["kind"] in {"producer_start", "producer_stop"}]
            self.assertEqual([record["kind"] for record in boundaries], ["producer_start", "producer_stop"])
            self.assertEqual(boundaries[0]["after_producer_seq"], first["producer_seq"] - 1)
            self.assertEqual(boundaries[1]["final_producer_seq"], last["producer_seq"])

    def test_csv_evidence_retry_preserves_written_rows(self) -> None:
        for v2 in (False, True):
            with self.subTest(v2=v2), self.create_temp_dir() as tmp_dir:
                service = self.create_service(tmp_dir, True, csv_v2_enabled=v2)
                allow_publish, failed = threading.Event(), threading.Event()
                original_replace = Path.replace

                def fail_row_evidence(source, target):
                    if (str(target).endswith(".trace.jsonl") and not allow_publish.is_set()
                            and b'"kind":"csv_row_data"' in source.read_bytes()):
                        failed.set()
                        raise OSError("injected CSV row evidence publication failure")
                    return original_replace(source, target)

                with patch.object(Path, "replace", fail_row_evidence):
                    service.start()
                    try:
                        receipts = [service.enqueue_detailed(self.create_data(
                            f"2026-03-09T07:20:25.{index}00", 30.0 + index)) for index in range(2)]
                        self.assertTrue(failed.wait(5), "CSV row evidence failure was not exercised")
                        expected_rows = 4 if v2 else 2
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline:
                            before = service.get_runtime_state()
                            if before["csv_data_written_evidence_pending_count"] == expected_rows:
                                break
                            time.sleep(.01)
                        self.assertEqual(before["pending_event_count"], 2)
                        self.assertEqual(before["csv_data_written_evidence_pending_count"], expected_rows)
                        outcomes = before["csv_persistence_outcomes"]
                        self.assertEqual(outcomes["accepted_event_count"], 2)
                        self.assertEqual(outcomes["fully_committed_event_count"], 0)
                        self.assertEqual(outcomes["outstanding_event_count"], 2)
                        self.assertEqual(outcomes["sinks"]["csv_v1"]["committed_count"], 0)
                        self.assertEqual(outcomes["sinks"]["csv_v2"]["committed_count"], 0)
                        self.assertTrue(outcomes["counts_reconciled"])
                        before_bytes = {path: path.read_bytes() for path in tmp_dir.glob("*.csv")}
                        self.assertEqual(len(before_bytes), 2 if v2 else 1)
                        self.assertTrue(all(len(self.read_rows(path)) == 3 for path in before_bytes))
                        allow_publish.set()
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline:
                            after = service.get_runtime_state()
                            if after["pending_event_count"] == 0:
                                break
                            time.sleep(.01)
                        self.assertEqual(after["pending_event_count"], 0, "recovered evidence did not release CSV events")
                        self.assertEqual(after["csv_data_written_evidence_pending_count"], 0)
                        self.assertEqual(after["pending_payload_bytes"], 0)
                        self.assertGreaterEqual(after["persistence_trace"]["failure_count"], 1)
                    finally:
                        allow_publish.set()
                        closed = service.stop(timeout_sec=5)
                self.assertFalse(closed, "evidence recovery erased the historical write failure")
                self.assertEqual({path: path.read_bytes() for path in before_bytes}, before_bytes)
                records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                           for line in path.read_text(encoding="utf-8").splitlines()[1:]]
                evidence = [record for record in records if record["kind"] == "csv_row_data"]
                sinks = {"csv_v1", "csv_v2"} if v2 else {"csv_v1"}
                expected = {(receipt["producer_seq"], sink) for receipt in receipts for sink in sinks}
                self.assertEqual(len(evidence), len(expected))
                self.assertEqual({(record["producer_seq"], record["sink_id"]) for record in evidence}, expected)
                for record in evidence:
                    receipt = next(receipt for receipt in receipts if receipt["producer_seq"] == record["producer_seq"])
                    self.assertEqual(record["source_payload_hash"], receipt["source_payload_hash"])
                    self.assertEqual(record["config_generation"], receipt["config_generation"])
                    path = Path(record["file_path"])
                    offset, length = record["row_byte_offset"], record["row_byte_length"]
                    self.assertEqual(hashlib.sha256(before_bytes[path][offset:offset + length]).hexdigest(),
                                     record["output_bytes_sha256"])
                    info = path.stat()
                    self.assertEqual((record["file_device"], record["file_id"]), (info.st_dev, info.st_ino))

    def test_csv_trace_binds_canonical_output_content(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
            service.start()
            try:
                receipts = []
                for index in range(2):
                    data = self.create_data(f"2026-03-09T07:20:25.{index}00", 30.0 + index)
                    data.Die_ID = '금형,"A"\n😀'
                    receipts.append(service.enqueue_detailed(data))
            finally:
                closed = service.stop(timeout_sec=5)
            self.assertTrue(closed)
            records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                       for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            evidence = [record for record in records if record["kind"] == "csv_row_data"]
            self.assertEqual(len(evidence), 4)
            for record in evidence:
                path = Path(record["file_path"])
                contents = path.read_bytes()
                start, length = record["row_byte_offset"], record["row_byte_length"]
                values = list(csv.reader(io.StringIO(contents[start:start + length].decode("utf-8-sig"))))
                self.assertEqual(len(values), 1)
                canonical = {"contract_version": "CSV_ROW_CONTENT_V1",
                             "columns": self.read_rows(path)[0], "values": values[0]}
                expected = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, allow_nan=False,
                                                    sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                self.assertEqual(record.get("output_payload_hash"), expected,
                                 "CSV evidence lacks the canonical output column/value identity")
                self.assertEqual(record.get("output_contract_version"), "CSV_ROW_CONTENT_V1")
                receipt = next(item for item in receipts if item["producer_seq"] == record["producer_seq"])
                self.assertEqual(record["source_payload_hash"], receipt["source_payload_hash"])
                self.assertNotEqual(record["source_payload_hash"], record["output_payload_hash"])

    def test_restart_refuses_unresolved_csv_outputs(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            original_open = Path.open

            class FailedDataFile:
                def __init__(self, handle):
                    self.handle = handle
                    self.writes = 0

                def __getattr__(self, name):
                    return getattr(self.handle, name)

                def write(self, text):
                    self.writes += 1
                    if self.writes > 1:
                        raise OSError("injected permanent CSV data write failure")
                    return self.handle.write(text)

            def open_file(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                if mode == "a" and path.suffix == ".csv" and path.name.startswith("Factory_Integrated_Log"):
                    return FailedDataFile(handle)
                return handle

            with patch.object(Path, "open", open_file):
                service.start()
                try:
                    service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 33.0))
                    self.assertFalse(service.stop(timeout_sec=5))
                    before = service.get_runtime_state()
                    self.assertEqual(before["pending_event_count"], 1)
                    self.assertEqual(before["persistence_trace"]["pending_records"], 0)
                    with self.assertRaisesRegex(RuntimeError, "CSV.*unresolved",
                                                msg="restart accepted unresolved CSV outputs"):
                        service.start()
                    after = service.get_runtime_state()
                    self.assertEqual(after["admission_summary"], before["admission_summary"])
                    self.assertEqual(after["csv_persistence_outcomes"], before["csv_persistence_outcomes"])
                    self.assertEqual(after["pending_payload_bytes"], before["pending_payload_bytes"])
                finally:
                    service.stop(timeout_sec=5)

    def test_csv_sink_outcomes_do_not_complete_a_partially_saved_event(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
            allow_v2, failed = threading.Event(), threading.Event()
            original_open = Path.open

            class FailingV2File:
                def __init__(self, handle):
                    self.handle = handle
                    self.writes = 0

                def __getattr__(self, name):
                    return getattr(self.handle, name)

                def write(self, text):
                    self.writes += 1
                    if self.writes > 1 and not allow_v2.is_set():
                        failed.set()
                        raise OSError("injected v2-only write failure")
                    return self.handle.write(text)

            def open_file(path, mode="r", *args, **kwargs):
                handle = original_open(path, mode, *args, **kwargs)
                if mode == "a" and path.suffix == ".csv" and path.name.startswith("Factory_Integrated_Log_v2"):
                    return FailingV2File(handle)
                return handle

            with patch.object(Path, "open", open_file):
                service.start()
                try:
                    receipt = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 33.0))
                    self.assertEqual(receipt["required_sinks"], ("csv_v1", "csv_v2"))
                    self.assertTrue(failed.wait(5))
                    deadline = time.monotonic() + 5
                    committed_v1 = []
                    while time.monotonic() < deadline:
                        records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                                   for line in path.read_text(encoding="utf-8").splitlines()]
                        committed_v1 = [record for record in records if record.get("kind") == "csv_row_data"
                                        and record["sink_id"] == "csv_v1"]
                        if committed_v1 and not service.get_runtime_state()["csv_evidence_pending_by_sink"]["csv_v1"]:
                            break
                        time.sleep(.01)
                    self.assertEqual(len(committed_v1), 1)
                    outcomes = service.get_runtime_state().get("csv_persistence_outcomes")
                    self.assertIsNotNone(outcomes, "partially saved CSV outputs have no separate outcome accounting")
                    self.assertEqual(outcomes["accepted_event_count"], 1)
                    self.assertEqual(outcomes["fully_committed_event_count"], 0)
                    self.assertEqual(outcomes["outstanding_event_count"], 1)
                    self.assertEqual(outcomes["sinks"]["csv_v1"],
                                     {"accepted_count": 1, "committed_count": 1, "failed_count": 0, "outstanding_count": 0})
                    self.assertEqual(outcomes["sinks"]["csv_v2"],
                                     {"accepted_count": 1, "committed_count": 0, "failed_count": 0, "outstanding_count": 1})
                    self.assertTrue(outcomes["counts_reconciled"])
                finally:
                    allow_v2.set()
                    closed = service.stop(timeout_sec=5)
            self.assertFalse(closed, "recovery erased the prior v2 write failure")
            outcomes = service.get_runtime_state()["csv_persistence_outcomes"]
            self.assertEqual(outcomes["fully_committed_event_count"], 1)
            self.assertEqual(outcomes["failed_event_count"], 0)
            self.assertEqual(outcomes["outstanding_event_count"], 0)
            self.assertTrue(outcomes["counts_reconciled"])
            for sink in ("csv_v1", "csv_v2"):
                self.assertEqual(outcomes["sinks"][sink],
                                 {"accepted_count": 1, "committed_count": 1, "failed_count": 0, "outstanding_count": 0})
            for path in self.list_v1_files(tmp_dir) + self.list_v2_files(tmp_dir):
                self.assertEqual(len(self.read_rows(path)), 2)

    def test_rejection_only_activation_keeps_its_original_trace_destination(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            original_dir, later_dir = tmp_dir / "original", tmp_dir / "later"
            service = self.create_service(original_dir, False)
            invalid = self.create_data("2026-03-09T07:20:25.000", 30.0)
            invalid.Press = float("nan")
            service.start()
            try:
                # Allow the initially disabled worker to enter its idle queue wait.
                time.sleep(.3)
                self.assertIsNone(service.get_runtime_state()["persistence_trace"])
                service.apply_config(auto_save=True)
                refused = service.enqueue_detailed(invalid)
                service.apply_config(auto_save=False, log_path=later_dir)
            finally:
                closed = service.stop(timeout_sec=5)
            records = [json.loads(line) for path in original_dir.rglob("*.trace.jsonl")
                       for line in path.read_text(encoding="utf-8").splitlines()]
            ranges = [record for record in records if record.get("kind") == "admission_rejection_range"]
            self.assertEqual(len(ranges), 1, "rejection-only activation lost its original trace destination")
            self.assertTrue(closed)
            self.assertEqual(ranges[0]["first_producer_seq"], refused["producer_seq"])
            self.assertEqual(ranges[0]["config_generation"], refused["config_generation"])
            self.assertFalse(list(later_dir.rglob("*.trace.jsonl")))
            self.assertFalse(self.list_v1_files(original_dir))
            summary = next(record for record in records if record.get("kind") == "admission_summary")
            self.assertEqual(summary["committed_rejection_count"], 1)
            self.assertEqual(summary["pending_rejection_count"], 0)

    def test_csv_shutdown_preserves_incomplete_admission_summary(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            invalid = self.create_data("2026-03-09T07:20:25.000", 30.0)
            invalid.Press = float("nan")
            with patch("backend.FacilityData.persistence_trace.ADMISSION_REJECTION_RANGE_LIMIT", 1), \
                 patch("backend.FacilityData.persistence_trace.TRACE_FLUSH_INTERVAL_SEC", 3600):
                service.start()
                try:
                    receipts = []
                    for _ in range(3):
                        service.apply_config(auto_save=True)
                        receipts.append(service.enqueue_detailed(invalid))
                finally:
                    closed = service.stop(timeout_sec=5)
            records = [json.loads(line) for path in sorted(tmp_dir.rglob("*.trace.jsonl"))
                       for line in path.read_text(encoding="utf-8").splitlines()]
            summaries = [record for record in records if record.get("kind") == "admission_summary"]
            self.assertEqual(len(summaries), 1, "CSV shutdown did not persist its incomplete admission summary")
            summary = summaries[0]
            self.assertFalse(closed)
            self.assertEqual(summary["contract_version"], "CSV_ADMISSION_SUMMARY_V1")
            self.assertEqual(summary["coverage"], "PRODUCER_ADMISSION_COUNTS_ONLY")
            self.assertEqual(summary["admission_evidence_status"], "INCOMPLETE")
            self.assertEqual(summary["produced_count"], 3)
            self.assertEqual(summary["rejected_count"], 3)
            self.assertEqual(summary["accepted_count"], 0)
            self.assertEqual(summary["excluded_count"], 0)
            self.assertEqual(summary["pending_rejection_count"], 0)
            self.assertEqual(summary["committed_rejection_count"], 1)
            self.assertEqual(summary["omitted_rejection_count"], 2)
            self.assertEqual(summary["first_omitted_producer_seq"], receipts[1]["producer_seq"])
            self.assertEqual(summary["last_omitted_producer_seq"], receipts[2]["producer_seq"])
            self.assertTrue(summary["details_incomplete"])
            self.assertEqual(records[-1]["kind"], "admission_summary")
            self.assertEqual(len([record for record in records if record.get("kind") == "admission_rejection_range"]), 1)

    def test_rejected_csv_admissions_survive_trace_failure_and_commit_once(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            invalid = self.create_data("2026-03-09T07:20:25.000", 30.0)
            invalid.Press = float("nan")
            allow_publish = threading.Event()
            original_replace = Path.replace

            def replace(path, target):
                if str(target).endswith(".trace.jsonl") and not allow_publish.is_set():
                    raise OSError("injected rejection evidence publication failure")
                return original_replace(path, target)

            with patch.object(Path, "replace", replace):
                service.start()
                try:
                    receipts = [service.enqueue_detailed(invalid), service.enqueue_detailed(invalid)]
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        state = service.get_runtime_state()
                        if state["persistence_trace"] and state["persistence_trace"]["failure_count"]:
                            break
                        time.sleep(.01)
                    self.assertGreater(state["persistence_trace"]["failure_count"], 0)
                    self.assertEqual(state["admission_summary"]["pending_rejection_count"], 2)
                    self.assertEqual(state["admission_summary"]["committed_rejection_count"], 0)
                    allow_publish.set()
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        state = service.get_runtime_state()
                        if state["admission_summary"]["committed_rejection_count"] == 2:
                            break
                        time.sleep(.01)
                    self.assertEqual(state["admission_summary"]["committed_rejection_count"], 2,
                                     "rejected admission evidence was not committed after storage recovered")
                    receipts.append(service.enqueue_detailed(invalid))
                finally:
                    allow_publish.set()
                    closed = service.stop(timeout_sec=5)
            self.assertFalse(closed, "recovery erased the prior trace failure")
            summary = service.get_runtime_state()["admission_summary"]
            self.assertEqual(summary["pending_rejection_count"], 0)
            self.assertEqual(summary["committed_rejection_count"], 3)
            records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                       for line in path.read_text(encoding="utf-8").splitlines()]
            ranges = [record for record in records if record.get("kind") == "admission_rejection_range"]
            saved = {sequence: record for record in ranges
                     for sequence in range(record["first_producer_seq"], record["last_producer_seq"] + 1)}
            self.assertEqual(sorted(saved), [receipt["producer_seq"] for receipt in receipts])
            self.assertEqual(sum(record["last_producer_seq"] - record["first_producer_seq"] + 1
                                 for record in ranges), len(receipts))
            for receipt in receipts:
                self.assertEqual(saved[receipt["producer_seq"]]["status"], receipt["status"])
                self.assertEqual(saved[receipt["producer_seq"]]["reason"], receipt["reason"])
                self.assertEqual(saved[receipt["producer_seq"]]["config_generation"], receipt["config_generation"])

    def test_policy_exclusion_evidence_waits_for_publish_and_preserves_failures(self) -> None:
        for recover in (False, True):
            with self.subTest(recover=recover), self.create_temp_dir() as tmp_dir:
                service = self.create_service(tmp_dir, True)
                release, failed = threading.Event(), threading.Event()
                original_replace = Path.replace

                def blocked_publish(path, target):
                    if str(target).endswith(".trace.jsonl") and not release.is_set():
                        failed.set()
                        raise OSError("policy exclusion evidence unavailable")
                    return original_replace(path, target)

                with patch.object(Path, "replace", blocked_publish):
                    service.start()
                    try:
                        deadline = time.monotonic() + 5
                        while service.get_runtime_state()["persistence_trace"] is None and time.monotonic() < deadline:
                            time.sleep(.01)
                        self.assertIsNotNone(service.get_runtime_state()["persistence_trace"])
                        service.apply_config(auto_save=False)
                        receipts = [service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", value))
                                    for value in (30.0, 31.0)]
                        self.assertEqual([receipt["status"] for receipt in receipts], ["DISABLED", "DISABLED"])
                        self.assertTrue(failed.wait(5))
                        waiting = service.get_runtime_state()["admission_summary"]
                        self.assertEqual(waiting["pending_exclusion_count"], 2)
                        self.assertEqual(waiting["committed_exclusion_count"], 0)
                        self.assertEqual(waiting["rejected_count"], 0)
                        if recover:
                            release.set()
                            deadline = time.monotonic() + 5
                            while time.monotonic() < deadline:
                                if service.get_runtime_state()["admission_summary"]["pending_exclusion_count"] == 0:
                                    break
                                time.sleep(.01)
                            self.assertEqual(service.get_runtime_state()["admission_summary"]["committed_exclusion_count"], 2)
                        self.assertFalse(service.stop(timeout_sec=5))
                        if not recover:
                            with self.assertRaises(RuntimeError):
                                service.start()
                    finally:
                        release.set()
                        service.stop(timeout_sec=5)
                records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                           for line in path.read_text(encoding="utf-8").splitlines()[1:]]
                exclusions = [record for record in records if record.get("kind") == "admission_exclusion_range"]
                self.assertFalse(any(record.get("kind") == "admission_rejection_range" for record in records))
                self.assertFalse(list(tmp_dir.rglob("*.csv")))
                if recover:
                    self.assertEqual(sum(record["last_producer_seq"] - record["first_producer_seq"] + 1
                                         for record in exclusions), 2)
                    ids = {seq for record in exclusions for seq in range(record["first_producer_seq"], record["last_producer_seq"] + 1)}
                    self.assertEqual(ids, {receipt["producer_seq"] for receipt in receipts})
                    summary = next(record for record in records if record.get("kind") == "admission_summary")
                    self.assertEqual(summary["committed_exclusion_count"], 2)
                    self.assertEqual(summary["committed_rejection_count"], 0)
                    self.assertGreater(summary["trace_failure_count"], 0)
                    self.assertEqual(summary["data_integrity_status"], "NOT_EVALUATED")
                else:
                    self.assertEqual(exclusions, [])
                    self.assertFalse(any(record.get("kind") == "admission_summary" for record in records))
                    self.assertEqual(service.get_runtime_state()["admission_summary"]["pending_exclusion_count"], 2)

    def test_admission_summary_tracks_only_active_producer_generation(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, False)
            valid = self.create_data("2026-03-09T07:20:25.000", 33.0)
            invalid = self.create_data("2026-03-09T07:20:25.000", 30.0)
            invalid.Press = float("nan")
            before = service.enqueue_detailed(valid)
            self.assertEqual(before["status"], "REJECTED_CLOSED")
            service.start()
            try:
                receipts = [service.enqueue_detailed(valid), service.enqueue_detailed(valid)]
                service.apply_config(auto_save=True)
                receipts.extend([service.enqueue_detailed(invalid), service.enqueue_detailed(invalid),
                                 service.enqueue_detailed(valid), service.enqueue_detailed(invalid),
                                 service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 34.0))])
            finally:
                service.stop(timeout_sec=5)
            after = service.enqueue_detailed(valid)
            self.assertEqual(after["status"], "REJECTED_CLOSED")
            records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                       for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            exclusions = [record for record in records if record.get("kind") == "admission_exclusion_range"]
            self.assertEqual(len(exclusions), 1, "policy exclusions have no durable producer-ID range")
            self.assertEqual(exclusions[0]["first_producer_seq"], receipts[0]["producer_seq"])
            self.assertEqual(exclusions[0]["last_producer_seq"], receipts[1]["producer_seq"])
            self.assertEqual(exclusions[0]["status"], "DISABLED")
            self.assertEqual(exclusions[0]["reason"], "auto_save_disabled")
            self.assertEqual(exclusions[0]["config_generation"], receipts[0]["config_generation"])
            summary = service.get_runtime_state().get("admission_summary", {})
            self.assertEqual(summary.get("produced_count"), 7,
                             "active admission outcomes were not accounted by producer generation")
            self.assertEqual(summary["accepted_count"], 2)
            self.assertEqual(summary["excluded_count"], 2)
            self.assertEqual(summary["rejected_count"], 3)
            self.assertEqual(summary["outcome_counts"], {"DISABLED": 2, "INVALID": 3, "ACCEPTED": 2})
            self.assertEqual(summary["after_producer_seq"], before["producer_seq"])
            self.assertEqual(summary["last_producer_seq"], receipts[-1]["producer_seq"])
            self.assertEqual(summary["rejection_range_count"], 0)
            self.assertEqual(summary["pending_rejection_count"], 0)
            self.assertEqual(summary["committed_rejection_count"], 3)
            self.assertEqual(summary["committed_exclusion_count"], 2)
            self.assertEqual(summary["pending_exclusion_count"], 0)
            self.assertFalse(summary["details_incomplete"])
            outcomes = service.get_runtime_state()["csv_persistence_outcomes"]
            self.assertEqual(outcomes["accepted_event_count"], 2)
            self.assertEqual(outcomes["fully_committed_event_count"], 2)
            self.assertEqual(outcomes["sinks"]["csv_v2"],
                             {"accepted_count": 0, "committed_count": 0, "failed_count": 0, "outstanding_count": 0})
            self.assertTrue(outcomes["counts_reconciled"])
            rows = [row for path in self.list_v1_files(tmp_dir) for row in self.read_rows(path)[1:]]
            self.assertEqual([float(row[3]) for row in rows], [33., 34.])
            service.start()
            try:
                resumed = service.enqueue_detailed(valid)
            finally:
                service.stop(timeout_sec=5)
            current = service.get_runtime_state()["admission_summary"]
            self.assertEqual(current["produced_count"], 1)
            self.assertEqual(current["outcome_counts"], {"ACCEPTED": 1})
            self.assertEqual(current["after_producer_seq"], after["producer_seq"])
            self.assertEqual(current["last_producer_seq"], resumed["producer_seq"])
            self.assertEqual(current["rejection_range_count"], 0)
            self.assertEqual(summary["produced_count"], 7)
            outcomes = service.get_runtime_state()["csv_persistence_outcomes"]
            self.assertEqual(outcomes["accepted_event_count"], 1)
            self.assertEqual(outcomes["fully_committed_event_count"], 1)
            self.assertEqual(outcomes["sinks"]["csv_v1"]["committed_count"], 1)
            self.assertTrue(outcomes["counts_reconciled"])

    def test_trace_capacity_blocks_new_csv_admission_until_recovered(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            entered, release, allow_publish = threading.Event(), threading.Event(), threading.Event()
            original_open, original_replace = Path.open, Path.replace

            def held_open(path, mode="r", *args, **kwargs):
                if path.suffix == ".csv" and mode == "a":
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("trace capacity test did not release CSV initialization")
                return original_open(path, mode, *args, **kwargs)

            def fail_trace(source, target):
                if str(target).endswith(".trace.jsonl") and not allow_publish.is_set():
                    raise OSError("injected full trace publication failure")
                return original_replace(source, target)

            with patch("backend.FacilityData.persistence_trace.TRACE_SEGMENT_RECORD_LIMIT", 4), \
                    patch.object(Path, "open", held_open), patch.object(Path, "replace", fail_trace):
                service.start()
                try:
                    receipts = [service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))]
                    self.assertTrue(entered.wait(2))
                    for index in range(1, 6):
                        receipts.append(service.enqueue_detailed(self.create_data(
                            f"2026-03-09T07:20:25.{index}00", 30.0 + index)))
                    self.assertTrue(all(receipt["status"] == "ACCEPTED" for receipt in receipts))
                    release.set()
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        state = service.get_runtime_state()
                        if (state["persistence_trace"]["pending_segments"] == 2
                                and state["persistence_trace"]["pending_records"] == 8
                                and state["persistence_trace"]["failure_count"] >= 1):
                            break
                        time.sleep(.01)
                    self.assertEqual(state["persistence_trace"]["pending_records"], 8)
                    self.assertGreaterEqual(state["persistence_trace"]["failure_count"], 1,
                                            "trace publication fault was never exercised")
                    self.assertTrue(list(tmp_dir.rglob("*.pending")))
                    self.assertEqual(state["pending_event_count"], 6)
                    refused = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 40.0))
                    self.assertEqual(refused["status"], "REJECTED_LIMIT",
                                     "CSV admission ignored saturated persistence evidence")
                    self.assertEqual(refused["reason"], "trace_segments_full")
                    self.assertEqual(service.get_runtime_state()["pending_event_count"], 6)
                    allow_publish.set()
                    deadline = time.monotonic() + 5
                    while service.get_runtime_state()["pending_event_count"] and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(service.get_runtime_state()["pending_event_count"], 0)
                    resumed = service.enqueue_detailed(self.create_data("2026-03-09T07:20:27.000", 50.0))
                    self.assertEqual(resumed["status"], "ACCEPTED")
                    self.assertGreater(resumed["producer_seq"], refused["producer_seq"])
                finally:
                    release.set()
                    allow_publish.set()
                    closed = service.stop(timeout_sec=5)
            self.assertFalse(closed, "trace recovery erased earlier persistence failures")
            self.assertEqual([float(row[3]) for row in self.read_rows(self.list_v1_files(tmp_dir)[0])[1:]],
                             [30., 31., 32., 33., 34., 35., 50.])
            state = service.get_runtime_state()
            self.assertEqual(state["pending_event_count"], 0)
            self.assertEqual(state["pending_payload_bytes"], 0)
            self.assertGreaterEqual(state["persistence_trace"]["failure_count"], 1)

    def test_producer_stop_boundary_excludes_post_stop_rejections(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, auto_save=True)
            entered, release = threading.Event(), threading.Event()
            original_open = Path.open
            stop_results = []

            def delayed_open(path, mode="r", *args, **kwargs):
                if path.suffix == ".csv" and mode == "a":
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("CSV boundary test did not release writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", delayed_open):
                service.start()
                first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.assertTrue(entered.wait(2))
                stopper = threading.Thread(target=lambda: stop_results.append(service.stop(timeout_sec=5)))
                stopper.start()
                try:
                    deadline = time.monotonic() + 2
                    while service.running and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertFalse(service.running)
                    late = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.100", 31.0))
                    self.assertEqual(late["status"], "REJECTED_CLOSED")
                finally:
                    release.set()
                    stopper.join(6)
            self.assertEqual(stop_results, [True])
            first_records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                             for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            stop = next(record for record in first_records if record["kind"] == "producer_stop")
            self.assertEqual(stop["final_producer_seq"], first["producer_seq"],
                             "post-stop rejection changed the closed producer interval")
            service.start()
            second = service.enqueue_detailed(self.create_data("2026-03-09T07:21:25.000", 32.0))
            self.assertTrue(service.stop(timeout_sec=5))
            all_records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                           for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            self.assertEqual(sorted(record["after_producer_seq"] for record in all_records
                                    if record["kind"] == "producer_start"), [0, late["producer_seq"]])
            self.assertEqual(sorted(record["final_producer_seq"] for record in all_records
                                    if record["kind"] == "producer_stop"), [first["producer_seq"], second["producer_seq"]])
            stored = [row for path in self.list_v1_files(tmp_dir) for row in self.read_rows(path)[1:]]
            self.assertEqual(sorted(float(row[3]) for row in stored), [30.0, 32.0])

    def read_rows(self, path: Path) -> list[list[str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    def list_v1_files(self, log_dir: Path) -> list[Path]:
        return sorted(
            path for path in log_dir.glob("Factory_Integrated_Log_*.csv") if "_v2_" not in path.name
        )

    def list_v2_files(self, log_dir: Path) -> list[Path]:
        return sorted(log_dir.glob("Factory_Integrated_Log_v2_*.csv"))

    def wait_for_processing(self) -> None:
        time.sleep(0.6)

    def test_admission_freezes_payload_and_identity(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(5):
                        raise TimeoutError("test did not release CSV file open")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                    self.assertTrue(started.wait(2))
                    data = self.create_data("2026-03-09T07:20:25.100", 31.0)
                    data.plc_source_age_ms = 42.0
                    expected_payload = json.dumps(dict(data), ensure_ascii=False,
                                                  sort_keys=True, separators=(",", ":")).encode("utf-8")
                    second = service.enqueue_detailed(data)
                    data.Press = 999.0
                finally:
                    release.set()
                    self.assertTrue(service.stop(timeout_sec=5))
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [30.0, 31.0])
            self.assertEqual(first["status"], "ACCEPTED")
            self.assertEqual(second["status"], "ACCEPTED")
            self.assertEqual(first["producer_instance_id"], service.logger_service_instance_id)
            self.assertEqual(second["producer_instance_id"], first["producer_instance_id"])
            self.assertEqual([first["producer_seq"], second["producer_seq"]], [1, 2])
            self.assertEqual(second["source_payload_hash"], hashlib.sha256(expected_payload).hexdigest())

    def test_queued_records_keep_admitted_sink_after_config_change(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        with self.create_temp_dir() as tmp_dir:
            old_dir, new_dir = tmp_dir / "before", tmp_dir / "after"
            old_dir.mkdir()
            new_dir.mkdir()
            service = self.create_service(old_dir, True)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == old_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(5):
                        raise TimeoutError("test did not release old CSV destination")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                    self.assertTrue(started.wait(2))
                    second = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                    service.apply_config(log_path=new_dir, csv_v1_enabled=False, csv_v2_enabled=True)
                    third = service.enqueue_detailed(self.create_data("2026-03-09T07:20:27.000", 32.0))
                finally:
                    release.set()
                    self.assertTrue(service.stop(timeout_sec=5))
            old_rows = self.read_rows(self.list_v1_files(old_dir)[0])
            self.assertEqual([float(row[3]) for row in old_rows[1:]], [30.0, 31.0])
            new_rows = self.read_rows(self.list_v2_files(new_dir)[0])
            self.assertEqual([float(row[new_rows[0].index("MainPress")]) for row in new_rows[1:]], [32.0])
            self.assertEqual(self.list_v2_files(old_dir), [])
            self.assertEqual(self.list_v1_files(new_dir), [])
            self.assertEqual(first["config_generation"], second["config_generation"])
            self.assertGreater(third["config_generation"], second["config_generation"])
            self.assertEqual(second["required_sinks"], ("csv_v1",))
            self.assertEqual(third["required_sinks"], ("csv_v2",))
            trace_records = [json.loads(line) for path in sorted(tmp_dir.rglob("*.trace.jsonl"))
                             for line in path.read_text(encoding="utf-8").splitlines()[1:]]
            admissions = [record for record in trace_records if record["kind"] == "csv_admission"]
            self.assertEqual(len(admissions), 3, "CSV trace omitted per-ID accepted contracts")
            for record, receipt, destination in zip(admissions, (first, second, third), (old_dir, old_dir, new_dir)):
                self.assertEqual(record["status"], "ACCEPTED")
                self.assertEqual(record["producer_instance_id"], receipt["producer_instance_id"])
                self.assertEqual(record["producer_seq"], receipt["producer_seq"])
                self.assertEqual(record["source_payload_hash"], receipt["source_payload_hash"])
                self.assertEqual(record["config_generation"], receipt["config_generation"])
                self.assertEqual(record["required_sinks"], list(receipt["required_sinks"]))
                self.assertEqual(Path(record["admitted_log_dir"]), destination)
            activations = [record for record in trace_records if record["kind"] == "config_activated"]
            self.assertEqual(len(activations), 2, "CSV trace omitted admitted configuration intervals")
            self.assertEqual([record["effective_from_producer_seq"] for record in activations],
                             [first["producer_seq"], third["producer_seq"]])
            self.assertEqual([record["config_generation"] for record in activations],
                             [first["config_generation"], third["config_generation"]])
            self.assertEqual([record["required_sinks"] for record in activations], [["csv_v1"], ["csv_v2"]])
            self.assertEqual([Path(record["admitted_log_dir"]) for record in activations], [old_dir, new_dir])
            self.assertEqual(activations[1]["csv_v2_schema_version"], "2.3.1")
            state = service.get_runtime_state()["persistence_trace"]
            self.assertEqual(state["pending_records"], 0)
            self.assertEqual(state["failure_count"], 0)

    def test_config_flush_error_preserves_next_generation_event(self) -> None:
        started, release, failed = threading.Event(), threading.Event(), threading.Event()
        original_open = Path.open

        class FailFirstDataWrite:
            def __init__(self, handle):
                self.handle = handle

            def write(self, value):
                if value.startswith("2026-03-09") and not failed.is_set():
                    failed.set()
                    raise OSError("injected pre-write failure at generation handoff")
                return self.handle.write(value)

            def __getattr__(self, name):
                return getattr(self.handle, name)

        with self.create_temp_dir() as tmp_dir:
            old_dir, new_dir = tmp_dir / "before", tmp_dir / "after"
            old_dir.mkdir()
            new_dir.mkdir()
            service = self.create_service(old_dir, True)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == old_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(5):
                        raise TimeoutError("test did not release old CSV destination")
                    return FailFirstDataWrite(original_open(path, mode, *args, **kwargs))
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                    self.assertTrue(started.wait(2))
                    service.apply_config(log_path=new_dir)
                    service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                finally:
                    release.set()
                    self.assertFalse(service.stop(timeout_sec=5), "recovery must retain the original write failure")
            self.assertTrue(failed.is_set())
            self.assertEqual(len(self.list_v1_files(new_dir)), 1)
            old_rows = self.read_rows(self.list_v1_files(old_dir)[0])
            new_rows = self.read_rows(self.list_v1_files(new_dir)[0])
            self.assertEqual([float(row[3]) for row in old_rows[1:]], [30.0])
            self.assertEqual([float(row[3]) for row in new_rows[1:]], [31.0])
            self.assertEqual(service.get_runtime_state()["csv_write_failure_count"], 1)
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)

    def test_csv_pending_limit_includes_inflight_and_both_outputs(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
            service.queue = queue.Queue(maxsize=2)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.name.startswith("Factory_Integrated_Log_v2_") and mode == "a":
                    started.set()
                    if not release.wait(5):
                        raise TimeoutError("test did not release v2 file open")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                    self.assertTrue(started.wait(2))
                    second = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                    rejected = service.enqueue_detailed(self.create_data("2026-03-09T07:20:27.000", 32.0))
                    self.assertEqual(rejected["status"], "REJECTED_LIMIT")
                    self.assertEqual(rejected["reason"], "pending_item_limit")
                    self.assertEqual(rejected["producer_seq"], 3)
                    self.assertEqual([first["status"], second["status"]], ["ACCEPTED", "ACCEPTED"])
                    self.assertEqual(service.get_runtime_state()["pending_event_count"], 2)
                finally:
                    release.set()
                    self.assertTrue(service.stop(timeout_sec=5))
            self.assertEqual(service.get_runtime_state()["pending_event_count"], 0)
            for path in self.list_v1_files(tmp_dir) + self.list_v2_files(tmp_dir):
                rows = self.read_rows(path)
                self.assertEqual([float(row[rows[0].index("MainPress")]) for row in rows[1:]], [30.0, 31.0])
            self.assertEqual(len(self.list_v1_files(tmp_dir)) + len(self.list_v2_files(tmp_dir)), 2)

    def test_csv_serialization_shares_pending_budget_before_allocation(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        budget = 64 * 1024**2
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            first_data = self.create_data("2026-03-09T07:20:25.000", 30.0)
            first_data.Status = "x" * (20 * 1024**2)
            large = self.create_data("2026-03-09T07:20:26.000", 31.0)
            large.Status = "y" * (24 * 1024**2)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(60):
                        raise TimeoutError("test did not release CSV serialization-budget writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    first = service.enqueue_detailed(first_data)
                    self.assertEqual(first["status"], "ACCEPTED")
                    self.assertTrue(started.wait(5))
                    before = service.get_runtime_state()
                    pending = before["pending_source_payload_bytes"]
                    self.assertGreater(pending, 20 * 1024**2)
                    tracemalloc.start()
                    try:
                        rejected = service.enqueue_detailed(large)
                        _, peak = tracemalloc.get_traced_memory()
                    finally:
                        tracemalloc.stop()
                    self.assertEqual(rejected["status"], "REJECTED_LIMIT")
                    self.assertEqual(rejected["reason"], "pending_byte_limit")
                    self.assertEqual(rejected["producer_seq"], 2)
                    self.assertIsNone(rejected["source_payload_hash"])
                    self.assertLess(peak, budget - pending)
                    state = service.get_runtime_state()
                    self.assertEqual(state["pending_source_payload_bytes"], pending)
                    self.assertEqual(state["pending_processing_payload_bytes"], before["pending_processing_payload_bytes"])
                    self.assertEqual(state["pending_payload_bytes"], before["pending_payload_bytes"])
                    self.assertEqual(state["pending_event_count"], 1)
                    self.assertEqual(state["drop_count"], 1)
                    small = self.create_data("2026-03-09T07:20:27.000", 32.0)
                    accepted = service.enqueue_detailed(small)
                    self.assertEqual(accepted["status"], "ACCEPTED")
                    self.assertEqual(accepted["producer_seq"], 3)
                finally:
                    release.set()
                    self.assertTrue(service.stop(timeout_sec=10))
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [30.0, 32.0])
            self.assertEqual(service.get_runtime_state()["pending_source_payload_bytes"], 0)
            self.assertEqual(service.get_runtime_state()["pending_processing_payload_bytes"], 0)
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)

    def test_csv_output_budget_failure_keeps_identity_and_later_rows(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
            large = self.create_data("2026-03-09T07:20:25.000", 30.0)
            large.Die_ID = "D" * (5 * 1024**2)
            with self.assertLogs(service.logger, level="ERROR") as captured:
                service.start()
                try:
                    first = service.enqueue_detailed(large)
                    second = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                    self.assertEqual([first["status"], second["status"]], ["ACCEPTED", "ACCEPTED"])
                    self.assertFalse(service.stop(timeout_sec=30))
                    self.assertEqual(service.get_runtime_state()["processing_failure_count"], 1)
                finally:
                    service.stop(timeout_sec=30)
            state = service.get_runtime_state()
            self.assertEqual(state["processing_failure_count"], 1)
            self.assertEqual(state["last_processing_failure_seq"], first["producer_seq"])
            self.assertEqual(state["last_processing_failure_reason"], "csv_output_byte_limit")
            outcomes = state["csv_persistence_outcomes"]
            self.assertEqual(outcomes["accepted_event_count"], 2)
            self.assertEqual(outcomes["fully_committed_event_count"], 1)
            self.assertEqual(outcomes["failed_event_count"], 1)
            self.assertEqual(outcomes["outstanding_event_count"], 0)
            for sink in ("csv_v1", "csv_v2"):
                self.assertEqual(outcomes["sinks"][sink],
                                 {"accepted_count": 2, "committed_count": 1, "failed_count": 1, "outstanding_count": 0})
            self.assertTrue(outcomes["counts_reconciled"])
            self.assertEqual(state["pending_event_count"], 0)
            self.assertEqual(state["pending_payload_bytes"], 0)
            records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                       for line in path.read_text(encoding="utf-8").splitlines()]
            failed_outputs = [record for record in records if record.get("kind") == "csv_processing_failure"]
            self.assertEqual(len(failed_outputs), 2, "failed CSV outputs have no durable per-ID evidence")
            self.assertEqual({record["sink_id"] for record in failed_outputs}, {"csv_v1", "csv_v2"})
            for record in failed_outputs:
                self.assertEqual(record["producer_instance_id"], first["producer_instance_id"])
                self.assertEqual(record["producer_seq"], first["producer_seq"])
                self.assertEqual(record["source_payload_hash"], first["source_payload_hash"])
                self.assertEqual(record["config_generation"], first["config_generation"])
                self.assertEqual(record["required_sinks"], list(first["required_sinks"]))
                self.assertEqual(record["reason"], "csv_output_byte_limit")
                self.assertEqual(record["status"], "FAILED")
                self.assertEqual(record["admitted_log_dir"], str(tmp_dir))
            summary = next(record for record in records if record.get("kind") == "admission_summary")
            saved_outcomes = summary.get("required_sink_outcomes")
            self.assertIsNotNone(saved_outcomes, "terminal trace omitted required-sink outcomes")
            expected_outcomes = dict(outcomes, coverage="TERMINAL_REQUIRED_SINK_COUNTS")
            self.assertEqual(saved_outcomes, expected_outcomes)
            self.assertEqual(saved_outcomes["data_integrity_status"], "NOT_EVALUATED")
            failures = [record for record in captured.records if record.getMessage() == "CSV processing failed"]
            self.assertEqual({record.sink_id for record in failures}, {"csv_v1", "csv_v2"})
            for record in failures:
                self.assertEqual(record.producer_instance_id, first["producer_instance_id"])
                self.assertEqual(record.producer_seq, first["producer_seq"])
                self.assertEqual(record.source_payload_hash, first["source_payload_hash"])
            files = self.list_v1_files(tmp_dir) + self.list_v2_files(tmp_dir)
            self.assertEqual(len(files), 2)
            for path in files:
                rows = self.read_rows(path)
                self.assertEqual([float(row[rows[0].index("MainPress")]) for row in rows[1:]], [31.0])

    def test_csv_failure_evidence_survives_publish_error(self) -> None:
        # Regression guards for retained failure evidence: recoverable and persistent I/O failure.
        for recover in (False, True):
            with self.subTest(recover=recover), self.create_temp_dir() as tmp_dir:
                service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
                blocked, release = threading.Event(), threading.Event()
                original_replace = Path.replace

                def failed_publish(path, target):
                    if str(target).endswith(".trace.jsonl") and not release.is_set():
                        blocked.set()
                        raise OSError("failure receipt publish unavailable")
                    return original_replace(path, target)

                data = self.create_data("2026-03-09T07:20:25.000", 30.0)
                data.Die_ID = "D" * (5 * 1024**2)
                with self.assertLogs(service.logger, level="ERROR"), patch.object(Path, "replace", failed_publish):
                    service.start()
                    try:
                        receipt = service.enqueue_detailed(data)
                        self.assertEqual(receipt["status"], "ACCEPTED")
                        self.assertTrue(blocked.wait(10), "failure evidence publish was not attempted")
                        state = service.get_runtime_state()
                        self.assertEqual(state["csv_processing_failure_evidence_pending_count"], 2)
                        self.assertEqual(state["pending_event_count"], 1)
                        self.assertGreater(state["pending_payload_bytes"], 0)
                        self.assertEqual(state["csv_persistence_outcomes"]["failed_event_count"], 0)
                        if recover:
                            release.set()
                            deadline = time.monotonic() + 10
                            while time.monotonic() < deadline and service.get_runtime_state()["pending_event_count"]:
                                time.sleep(0.02)
                            self.assertEqual(service.get_runtime_state()["pending_event_count"], 0)
                        self.assertFalse(service.stop(timeout_sec=10))
                        if not recover:
                            with self.assertRaises(RuntimeError):
                                service.start()
                    finally:
                        release.set()
                        service.stop(timeout_sec=10)
                records = [json.loads(line) for path in tmp_dir.rglob("*.trace.jsonl")
                           for line in path.read_text(encoding="utf-8").splitlines()]
                failures = [record for record in records if record.get("kind") == "csv_processing_failure"]
                state = service.get_runtime_state()
                self.assertGreaterEqual(state["persistence_trace"]["failure_count"], 1)
                if recover:
                    self.assertEqual(len(failures), 2)
                    self.assertEqual({record["sink_id"] for record in failures}, {"csv_v1", "csv_v2"})
                    self.assertEqual({record["producer_seq"] for record in failures}, {receipt["producer_seq"]})
                    self.assertEqual({record["source_payload_hash"] for record in failures}, {receipt["source_payload_hash"]})
                    self.assertEqual(state["csv_processing_failure_evidence_pending_count"], 0)
                    self.assertEqual(state["pending_payload_bytes"], 0)
                    self.assertEqual(state["csv_persistence_outcomes"]["failed_event_count"], 1)
                else:
                    self.assertEqual(failures, [])
                    self.assertFalse(any(record.get("kind") == "admission_summary" for record in records))
                    self.assertEqual(state["csv_processing_failure_evidence_pending_count"], 2)
                    self.assertEqual(state["pending_event_count"], 1)

    def test_csv_ema_workspace_reuses_serialization_reservation(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        budget = 64 * 1024**2
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            first_data = self.create_data("2026-03-09T07:20:25.000", 30.0)
            first_data.Status = "x" * (11 * 1024**2)
            next_data = self.create_data("2026-03-09T07:20:26.000", 31.0)
            next_data.Status = "y" * (17 * 1024**2)
            expected_ema = len(first_data.model_dump_json()) * 2 * 0.8 + len(next_data.model_dump_json()) * 2 * 0.2

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(60):
                        raise TimeoutError("test did not release CSV EMA-budget writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    self.assertEqual(service.enqueue_detailed(first_data)["status"], "ACCEPTED")
                    self.assertTrue(started.wait(5))
                    before = service.get_runtime_state()
                    available = budget - before["pending_payload_bytes"]
                    tracemalloc.start()
                    try:
                        admitted = service.enqueue_detailed(next_data)
                        _, peak = tracemalloc.get_traced_memory()
                    finally:
                        tracemalloc.stop()
                    self.assertEqual(admitted["status"], "ACCEPTED")
                    self.assertLessEqual(peak, available, "CSV EMA serialization exceeded available payload budget")
                    state = service.get_runtime_state()
                    self.assertAlmostEqual(state["payload_bytes_ema"], expected_ema)
                    self.assertLessEqual(state["pending_payload_bytes"], budget)
                    self.assertEqual(state["pending_event_count"], 2)
                    self.assertEqual(state["pending_processing_payload_bytes"], before["pending_processing_payload_bytes"])
                    small = service.enqueue_detailed(self.create_data("2026-03-09T07:20:27.000", 32.0))
                    self.assertEqual(small["status"], "ACCEPTED")
                    self.assertEqual(small["producer_seq"], 3)
                finally:
                    release.set()
                    self.assertTrue(service.stop(timeout_sec=20))
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [30.0, 31.0, 32.0])
            state = service.get_runtime_state()
            self.assertEqual(state["pending_payload_bytes"], 0)
            self.assertEqual(state["processing_failure_count"], 0)

    def test_csv_decode_budget_failure_preserves_admitted_identity(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            large = self.create_data("2026-03-09T07:20:26.000", 31.0)
            large.Status = "x" * (20 * 1024**2)
            filler = self.create_data("2026-03-09T07:20:27.000", 32.0)
            filler.Status = "y" * (384 * 1024)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(60):
                        raise TimeoutError("test did not release CSV decode-budget writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open), self.assertLogs(service.logger, level="ERROR") as captured:
                service.start()
                try:
                    first = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                    self.assertEqual(first["status"], "ACCEPTED")
                    self.assertTrue(started.wait(5))
                    large_receipt = service.enqueue_detailed(large)
                    self.assertEqual(large_receipt["status"], "ACCEPTED")
                    for index in range(96):
                        filler.Press = float(32 + index)
                        self.assertEqual(service.enqueue_detailed(filler)["status"], "ACCEPTED")
                    state = service.get_runtime_state()
                    self.assertGreater(state["pending_source_payload_bytes"], 56 * 1024**2)
                    self.assertLessEqual(state["pending_payload_bytes"], 64 * 1024**2)
                finally:
                    release.set()
                    clean_stop = service.stop(timeout_sec=30)
                self.assertFalse(clean_stop)
            failures = [entry for entry in captured.records if entry.msg == "CSV processing failed"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].producer_instance_id, large_receipt["producer_instance_id"])
            self.assertEqual(failures[0].producer_seq, large_receipt["producer_seq"])
            self.assertEqual(failures[0].source_payload_hash, large_receipt["source_payload_hash"])
            self.assertEqual(failures[0].reason, "decode_byte_limit")
            state = service.get_runtime_state()
            self.assertEqual(state["processing_failure_count"], 1)
            self.assertEqual(state["last_processing_failure_seq"], 2)
            self.assertEqual(state["last_processing_failure_reason"], "decode_byte_limit")
            self.assertEqual(state["pending_event_count"], 0)
            self.assertEqual(state["pending_payload_bytes"], 0)
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [30.0, *range(32, 128)])
            # A later successful run must not erase the same owner's failure.
            service.start()
            try:
                self.assertEqual(service.enqueue_detailed(
                    self.create_data("2026-03-09T07:20:28.000", 999.0))["status"], "ACCEPTED")
            finally:
                self.assertFalse(service.stop(timeout_sec=5))
            self.assertEqual(service.get_runtime_state()["processing_failure_count"], 1)
            self.assertEqual(service.get_runtime_state()["last_processing_failure_seq"], 2)
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)
            values = [float(row[3]) for path in self.list_v1_files(tmp_dir) for row in self.read_rows(path)[1:]]
            self.assertEqual(values, [30.0, *range(32, 128), 999.0])

    def test_csv_decode_validation_failure_preserves_identity(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            malformed = self.create_data("2026-03-09T07:20:25.000", 30.0)
            malformed.Status = {"unexpected": "object"}  # JSON-safe mutation after model validation.
            with self.assertLogs(service.logger, level="ERROR") as captured:
                service.start()
                try:
                    bad_receipt = service.enqueue_detailed(malformed)
                    self.assertEqual(bad_receipt["status"], "ACCEPTED")
                    good_receipt = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                    self.assertEqual(good_receipt["status"], "ACCEPTED")
                finally:
                    self.assertFalse(service.stop(timeout_sec=5))
            state = service.get_runtime_state()
            self.assertEqual(state["processing_failure_count"], 1)
            self.assertEqual(state["last_processing_failure_seq"], bad_receipt["producer_seq"])
            self.assertEqual(state["last_processing_failure_reason"], "decode_invalid_payload")
            self.assertEqual(state["pending_event_count"], 0)
            self.assertEqual(state["pending_payload_bytes"], 0)
            failures = [entry for entry in captured.records if entry.msg == "CSV processing failed"]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].producer_instance_id, bad_receipt["producer_instance_id"])
            self.assertEqual(failures[0].producer_seq, bad_receipt["producer_seq"])
            self.assertEqual(failures[0].source_payload_hash, bad_receipt["source_payload_hash"])
            self.assertEqual(failures[0].reason, "decode_invalid_payload")
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [31.0])

    def test_bounded_temperature_text_avoids_full_raw_copies(self) -> None:
        service = CSVLoggerService()
        raw = "=" + "한\r\n둘\r" * (512 * 1024)
        expected = "'" + raw.replace("\r\n", "\n").replace("\r", "\n")[:256]
        tracemalloc.start()
        try:
            actual = service._bounded_csv_text(raw, 256)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLessEqual(peak, 128 * 1024, "bounded CSV text copied the full raw input")
        self.assertEqual(actual, (expected, True))
        for value in (None, "", "\r\n", "\r\r\n", "=\r\n한🙂\rB", "A\r\n" * 300):
            for limit in (-1, 0, 1, 2, 3, 7, 256):
                normalized = (value or "").replace("\r\n", "\n").replace("\r", "\n")
                truncated = len(normalized) > limit if value is not None else False
                text = normalized[:limit] if truncated else normalized
                if text and text[0] in ("=", "+", "-", "@"):
                    text = "'" + text
                self.assertEqual(service._bounded_csv_text(value, limit), (text, truncated))

    def test_csv_escaped_row_copy_remains_in_pending_budget(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        previous_field_limit = csv.field_size_limit(4 * 1024**2)
        self.addCleanup(csv.field_size_limit, previous_field_limit)
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
            data = self.create_data("2026-03-09T07:20:25.000", 30.0)
            data.Die_ID = "=" + "D" * (2 * 1024**2)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(30):
                        raise TimeoutError("test did not release escaped-row CSV writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                tracemalloc.start()
                try:
                    receipt = service.enqueue_detailed(data)
                    self.assertEqual(receipt["status"], "ACCEPTED")
                    self.assertTrue(started.wait(5))
                    allocated, _ = tracemalloc.get_traced_memory()
                    pending = service.get_runtime_state()["pending_payload_bytes"]
                finally:
                    tracemalloc.stop()
                    release.set()
                    stopped = service.stop(timeout_sec=30)
            # Object/thread overhead is separate from the payload byte budget.
            self.assertLessEqual(allocated, pending + 1024**2, "escaped CSV row copy is outside the pending budget")
            self.assertTrue(stopped)
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)
            files = self.list_v1_files(tmp_dir) + self.list_v2_files(tmp_dir)
            self.assertEqual(len(files), 2)
            for path in files:
                rows = self.read_rows(path)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1][rows[0].index("DIE_ID")], "'" + data.Die_ID)

    def test_csv_joined_metadata_remains_in_pending_budget(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        previous_field_limit = csv.field_size_limit(8 * 1024**2)
        self.addCleanup(csv.field_size_limit, previous_field_limit)
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v2_enabled=True)
            data = self.create_data("2026-03-09T07:20:25.000", 30.0)
            fields = ["product_" + "X" * (2 * 1024**2), "mold_" + "Y" * (2 * 1024**2)]
            data.operator_metadata_missing_fields = fields

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(30):
                        raise TimeoutError("test did not release joined-metadata CSV writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                tracemalloc.start()
                try:
                    receipt = service.enqueue_detailed(data)
                    self.assertEqual(receipt["status"], "ACCEPTED")
                    self.assertTrue(started.wait(5))
                    allocated, _ = tracemalloc.get_traced_memory()
                    pending = service.get_runtime_state()["pending_payload_bytes"]
                finally:
                    tracemalloc.stop()
                    release.set()
                    stopped = service.stop(timeout_sec=30)
            self.assertLessEqual(allocated, pending + 1024**2, "joined CSV metadata is outside the pending budget")
            self.assertTrue(stopped)
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)
            files = self.list_v2_files(tmp_dir)
            self.assertEqual(len(files), 1)
            rows = self.read_rows(files[0])
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1][rows[0].index("operator_metadata_missing_fields")], ",".join(fields))

    def test_csv_header_pressure_does_not_strand_admitted_rows(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            data = self.create_data("2026-03-09T07:20:25.000", 1.0)
            data.Die_ID = "D" * (64 * 1024)

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(30):
                        raise TimeoutError("test did not release CSV header-pressure writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open), self.assertLogs(service.logger, level="ERROR") as captured:
                service.start()
                try:
                    first = service.enqueue_detailed(data)
                    self.assertEqual(first["status"], "ACCEPTED")
                    admitted = {first["producer_seq"]: first}
                    self.assertTrue(started.wait(5))
                    for number in range(2, 2048):
                        data.Press = float(number)
                        receipt = service.enqueue_detailed(data)
                        if receipt["status"] != "ACCEPTED":
                            break
                        admitted[receipt["producer_seq"]] = receipt
                    self.assertEqual(receipt["status"], "REJECTED_LIMIT")
                    self.assertEqual(receipt["reason"], "pending_byte_limit")
                finally:
                    release.set()
                    stopped = service.stop(timeout_sec=30)
            state = service.get_runtime_state()
            self.assertFalse(state["pending_event_count"], "admitted CSV events remained after header budget exhaustion")
            self.assertFalse(stopped)
            self.assertEqual(state["pending_payload_bytes"], 0)
            failures = [record for record in captured.records if record.getMessage() == "CSV processing failed"]
            failed = {record.producer_seq for record in failures}
            self.assertTrue(failed)
            for record in failures:
                self.assertEqual(record.producer_instance_id, admitted[record.producer_seq]["producer_instance_id"])
                self.assertEqual(record.source_payload_hash, admitted[record.producer_seq]["source_payload_hash"])
                self.assertTrue(record.reason.endswith("byte_limit"))
            persisted = []
            for path in self.list_v1_files(tmp_dir):
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    rows = csv.DictReader(handle)
                    persisted.extend(int(float(row["MainPress"])) for row in rows)
            self.assertEqual(len(persisted), len(set(persisted)))
            self.assertFalse(set(persisted) & failed)
            self.assertEqual(set(persisted) | failed, set(admitted))
            self.assertEqual(state["processing_failure_count"], len(failed))
            service.start()
            try:
                self.assertEqual(service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 9999.0))["status"], "ACCEPTED")
            finally:
                self.assertFalse(service.stop(timeout_sec=10))
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)
            last = []
            for path in self.list_v1_files(tmp_dir):
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    last.extend(float(row["MainPress"]) for row in csv.DictReader(handle))
            self.assertEqual(last.count(9999.0), 1)

    def test_csv_source_budget_includes_inflight_payloads(self) -> None:
        started, release = threading.Event(), threading.Event()
        original_open = Path.open
        budget = 64 * 1024**2
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            data = self.create_data("2026-03-09T07:20:25.000", 30.0)
            data.Status = "x" * (128 * 1024)
            payload_size = len(json.dumps(dict(data), ensure_ascii=False, allow_nan=False,
                                          sort_keys=True, separators=(",", ":")).encode("utf-8"))

            def blocked_open(path, mode="r", *args, **kwargs):
                if path.parent == tmp_dir and path.suffix == ".csv" and mode == "a":
                    started.set()
                    if not release.wait(30):
                        raise TimeoutError("test did not release CSV byte-budget writer")
                return original_open(path, mode, *args, **kwargs)

            with patch.object(Path, "open", blocked_open):
                service.start()
                try:
                    first = service.enqueue_detailed(data)
                    self.assertEqual(first["status"], "ACCEPTED")
                    self.assertTrue(started.wait(2))
                    accepted = 1
                    for _ in range(budget // payload_size):
                        receipt = service.enqueue_detailed(data)
                        if receipt["status"] != "ACCEPTED":
                            break
                        accepted += 1
                    self.assertEqual(receipt["status"], "REJECTED_LIMIT")
                    self.assertEqual(receipt["reason"], "pending_byte_limit")
                    state = service.get_runtime_state()
                    self.assertEqual(state["pending_source_payload_bytes"], accepted * payload_size)
                    self.assertLessEqual(state["pending_source_payload_bytes"], budget)
                    self.assertEqual(state["pending_event_count"], accepted)
                finally:
                    release.set()
                    self.assertTrue(service.stop(timeout_sec=30))
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual(len(rows) - 1, accepted)
            self.assertEqual(service.get_runtime_state()["pending_source_payload_bytes"], 0)

    def test_invalid_csv_payload_keeps_producer_identity(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            invalid = self.create_data("2026-03-09T07:20:25.000", 30.0)
            invalid.Press = float("nan")  # Mutation after initial Pydantic validation.
            service.start()
            try:
                rejected = service.enqueue_detailed(invalid)
                self.assertEqual(rejected["status"], "INVALID")
                self.assertEqual(rejected["reason"], "snapshot_serialization_failed")
                self.assertEqual(rejected["producer_instance_id"], service.logger_service_instance_id)
                self.assertEqual(rejected["producer_seq"], 1)
                self.assertIsNone(rejected["source_payload_hash"])
                self.assertEqual(service.get_runtime_state()["pending_event_count"], 0)
                self.assertEqual(service.get_runtime_state()["pending_source_payload_bytes"], 0)
                accepted = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                self.assertEqual(accepted["status"], "ACCEPTED")
                self.assertEqual(accepted["producer_seq"], 2)
            finally:
                service.stop(timeout_sec=5)
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [31.0])

    def test_same_date_rows_stay_in_one_file(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                service.enqueue(self.create_data("2026-03-09T07:20:25.100", 31.0))
                service.enqueue(self.create_data("2026-03-09T07:20:25.200", 32.0))
                self.wait_for_processing()
            finally:
                service.stop()

            files = self.list_v1_files(log_dir)
            self.assertEqual(len(files), 1)
            rows = self.read_rows(files[0])
            self.assertEqual([row[0] for row in rows[1:]], ["2026-03-09", "2026-03-09", "2026-03-09"])

    def test_midnight_boundary_rolls_over_to_new_file(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T23:59:59.900", 30.0))
                service.enqueue(self.create_data("2026-03-10T00:00:00.100", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            files = self.list_v1_files(log_dir)
            self.assertEqual([path.name for path in files], [
                "Factory_Integrated_Log_20260309_235959.csv",
                "Factory_Integrated_Log_20260310_000000.csv",
            ])
            first_rows = self.read_rows(files[0])
            second_rows = self.read_rows(files[1])
            self.assertEqual([row[0] for row in first_rows[1:]], ["2026-03-09"])
            self.assertEqual([row[0] for row in second_rows[1:]], ["2026-03-10"])

    def test_multiple_dates_roll_over_to_daily_files(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                service.enqueue(self.create_data("2026-03-10T07:20:25.000", 30.0))
                service.enqueue(self.create_data("2026-03-11T07:20:25.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            files = self.list_v1_files(log_dir)
            self.assertEqual([path.name for path in files], [
                "Factory_Integrated_Log_20260309_072025.csv",
                "Factory_Integrated_Log_20260310_072025.csv",
                "Factory_Integrated_Log_20260311_072025.csv",
            ])
            self.assertEqual([self.read_rows(path)[1][0] for path in files], [
                "2026-03-09",
                "2026-03-10",
                "2026-03-11",
            ])

    def test_v2_midnight_boundary_rolls_over_with_sidecar(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, True, csv_v1_enabled=True, csv_v2_enabled=True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T23:59:59.900", 30.0))
                service.enqueue(self.create_data("2026-03-10T00:00:00.100", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            v1_files = self.list_v1_files(log_dir)
            v2_files = self.list_v2_files(log_dir)
            self.assertEqual([path.name for path in v1_files], [
                "Factory_Integrated_Log_20260309_235959.csv",
                "Factory_Integrated_Log_20260310_000000.csv",
            ])
            self.assertEqual([path.name for path in v2_files], [
                "Factory_Integrated_Log_v2_20260309_235959.csv",
                "Factory_Integrated_Log_v2_20260310_000000.csv",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

            first_rows = self.read_rows(v2_files[0])
            second_rows = self.read_rows(v2_files[1])
            sample_seq_index = first_rows[0].index("sample_seq")
            timestamp_index = first_rows[0].index("Date")
            self.assertEqual(first_rows[1][sample_seq_index], "1")
            self.assertEqual(second_rows[1][sample_seq_index], "2")
            self.assertEqual(first_rows[1][timestamp_index], "2026-03-09")
            self.assertEqual(second_rows[1][timestamp_index], "2026-03-10")

    def test_billet_transition_stays_in_current_file(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T10:00:00.000", 30.0))
                service.enqueue(self.create_data("2026-03-09T10:00:01.000", 0.0))
                time.sleep(0.15)
                service.enqueue(self.create_data("2026-03-09T10:00:02.000", 0.0))
                service.enqueue(self.create_data("2026-03-09T10:00:03.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            files = self.list_v1_files(log_dir)
            self.assertEqual(len(files), 1)

            rows = self.read_rows(files[0])[1:]
            self.assertEqual(
                [row[1] for row in rows],
                ["10:00:00.000", "10:00:01.000", "10:00:02.000", "10:00:03.000"],
            )

    def test_invalid_timestamp_logs_warning_and_uses_fallback(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, True)
            service.start()

            try:
                with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
                    service.enqueue(self.create_data("bad-timestamp", 30.0))
                    self.wait_for_processing()
            finally:
                service.stop()

            self.assertTrue(any("CSV timestamp invalid" in message for message in logs.output))
            files = self.list_v1_files(log_dir)
            self.assertEqual(len(files), 1)

    def test_auto_save_disabled_creates_no_files(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            log_dir = tmp_dir
            service = self.create_service(log_dir, False)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            files = self.list_v1_files(log_dir)
            self.assertEqual(files, [])

    def test_csv_inactive_admission_skips_large_payload_work(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, False)
            large = self.create_data("2026-03-09T07:20:25.000", 30.0)
            large.Status = "x" * (40 * 1024**2)
            service.start()
            try:
                tracemalloc.start()
                try:
                    disabled = service.enqueue_detailed(large)
                    _, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                self.assertEqual(disabled["status"], "DISABLED")
                self.assertEqual(disabled["reason"], "auto_save_disabled")
                self.assertEqual(disabled["required_sinks"], ())
                self.assertIsNone(disabled["source_payload_hash"])
                self.assertLess(peak, 1024**2)
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            closed = service.enqueue_detailed(large)
            self.assertEqual(closed["status"], "REJECTED_CLOSED")
            self.assertEqual(closed["reason"], "persistence_closed")
            self.assertIsNone(closed["source_payload_hash"])
            self.assertEqual([disabled["producer_seq"], closed["producer_seq"]], [1, 2])
            state = service.get_runtime_state()
            self.assertEqual(state["pending_event_count"], 0)
            self.assertEqual(state["pending_payload_bytes"], 0)
            self.assertEqual(state["drop_count"], 0)
            self.assertEqual(list(tmp_dir.iterdir()), [])
            service.apply_config(auto_save=True)
            service.start()
            try:
                accepted = service.enqueue_detailed(self.create_data("2026-03-09T07:20:26.000", 31.0))
                self.assertEqual(accepted["status"], "ACCEPTED")
                self.assertEqual(accepted["producer_seq"], 3)
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            rows = self.read_rows(self.list_v1_files(tmp_dir)[0])
            self.assertEqual([float(row[3]) for row in rows[1:]], [31.0])
            self.assertEqual(service.get_runtime_state()["pending_payload_bytes"], 0)

    def test_disabled_admission_has_no_pending_work(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, False)
            service.start()
            try:
                result = service.enqueue_detailed(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.assertEqual(result["status"], "DISABLED")
                self.assertEqual(result["reason"], "auto_save_disabled")
                self.assertEqual(result["producer_seq"], 1)
                self.assertEqual(result["producer_instance_id"], service.logger_service_instance_id)
                self.assertEqual(result["required_sinks"], ())
                self.assertEqual(service.get_runtime_state()["queue_size"], 0)
                self.assertEqual(service.get_runtime_state()["drop_count"], 0)
            finally:
                self.assertTrue(service.stop(timeout_sec=5))
            self.assertEqual(list(tmp_dir.iterdir()), [])

    def test_v1_enabled_v2_disabled_creates_v1_only(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=True, csv_v2_enabled=False)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            self.assertEqual(len(self.list_v1_files(tmp_dir)), 1)
            self.assertEqual(self.list_v2_files(tmp_dir), [])

    def test_v1_enabled_v2_enabled_creates_both_files(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=True, csv_v2_enabled=True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            self.assertEqual(len(self.list_v1_files(tmp_dir)), 1)
            v2_files = self.list_v2_files(tmp_dir)
            self.assertEqual(len(v2_files), 1)
            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["schema_metadata"]["v1_csv_enabled"])

    def test_v1_disabled_v2_enabled_creates_v2_only(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=False, csv_v2_enabled=True)
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            self.assertEqual(self.list_v1_files(tmp_dir), [])
            v2_files = self.list_v2_files(tmp_dir)
            self.assertEqual(len(v2_files), 1)
            rows = self.read_rows(v2_files[0])
            self.assertIn("schema_version", rows[0])
            self.assertEqual(len(rows), 2)
            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertFalse(metadata["schema_metadata"]["v1_csv_enabled"])

    def test_resolve_clean_git_commit_returns_valid_head_for_clean_checkout(self) -> None:
        clean_status = subprocess.CompletedProcess(["git", "status"], 0, stdout="", stderr="")
        valid_head = subprocess.CompletedProcess(
            ["git", "rev-parse"],
            0,
            stdout=f"{self.VALID_GIT_COMMIT}\n",
            stderr="",
        )

        with patch("backend.version.subprocess.run", side_effect=[clean_status, valid_head]) as git_run:
            commit = backend_version.resolve_clean_git_commit(Path("repo"))

        self.assertEqual(commit, self.VALID_GIT_COMMIT)
        self.assertEqual(git_run.call_count, 2)

    def test_git_commit_validation_requires_exact_lowercase_sha(self) -> None:
        self.assertEqual(backend_version.validate_git_commit(self.VALID_GIT_COMMIT), self.VALID_GIT_COMMIT)
        self.assertIsNone(backend_version.validate_git_commit(f" {self.VALID_GIT_COMMIT}"))
        self.assertIsNone(backend_version.validate_git_commit(self.VALID_GIT_COMMIT.upper()))
        self.assertIsNone(backend_version.validate_git_commit("abc123"))
        self.assertIsNone(backend_version.validate_git_commit(None))

    def test_build_provenance_uses_real_clean_git_head_and_rejects_real_dirty_tree(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            repo_dir = tmp_dir / "repo"
            bundle_path = tmp_dir / "bundle" / backend_version.BUILD_PROVENANCE_FILENAME
            repo_dir.mkdir()

            def run_git(*args: str) -> str:
                result = subprocess.run(
                    ["git", *args],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=10.0,
                    check=True,
                )
                return result.stdout.strip()

            run_git("init")
            run_git("config", "user.email", "build-provenance@example.invalid")
            run_git("config", "user.name", "Build Provenance Test")
            tracked_path = repo_dir / "tracked.txt"
            tracked_path.write_text("clean\n", encoding="utf-8")
            run_git("add", "tracked.txt")
            run_git("commit", "-m", "fixture")
            expected_commit = run_git("rev-parse", "HEAD")

            commit = backend_version.write_build_provenance_file(repo_dir, bundle_path)

            self.assertRegex(expected_commit, r"^[0-9a-f]{40}$")
            self.assertEqual(commit, expected_commit)
            self.assertEqual(backend_version.read_bundled_git_commit(bundle_path), expected_commit)

            tracked_path.write_text("dirty\n", encoding="utf-8")
            self.assertIsNone(backend_version.resolve_clean_git_commit(repo_dir))

    def test_resolve_clean_git_commit_rejects_dirty_source(self) -> None:
        dirty_status = subprocess.CompletedProcess(
            ["git", "status"],
            0,
            stdout=" M backend/version.py\n",
            stderr="",
        )

        with patch("backend.version.subprocess.run", return_value=dirty_status) as git_run:
            commit = backend_version.resolve_clean_git_commit(Path("repo"))

        self.assertIsNone(commit)
        self.assertEqual(git_run.call_count, 1)

    def test_resolve_clean_git_commit_rejects_invalid_or_missing_head(self) -> None:
        clean_status = subprocess.CompletedProcess(["git", "status"], 0, stdout="", stderr="")
        invalid_head = subprocess.CompletedProcess(["git", "rev-parse"], 0, stdout="abc123\n", stderr="")

        with patch("backend.version.subprocess.run", side_effect=[clean_status, invalid_head]):
            self.assertIsNone(backend_version.resolve_clean_git_commit(Path("repo")))
        with patch("backend.version.subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(backend_version.resolve_clean_git_commit(Path("repo")))

    def test_build_provenance_file_round_trips_valid_commit(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            provenance_path = tmp_dir / "backend" / backend_version.BUILD_PROVENANCE_FILENAME
            with patch("backend.version.resolve_clean_git_commit", return_value=self.VALID_GIT_COMMIT):
                commit = backend_version.write_build_provenance_file(tmp_dir, provenance_path)

            payload = json.loads(provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(commit, self.VALID_GIT_COMMIT)
            self.assertEqual(payload["git_commit"], self.VALID_GIT_COMMIT)
            self.assertEqual(payload["schema_version"], backend_version.BUILD_PROVENANCE_SCHEMA_VERSION)
            self.assertEqual(payload["source"], backend_version.BUILD_PROVENANCE_SOURCE)
            self.assertEqual(backend_version.read_bundled_git_commit(provenance_path), self.VALID_GIT_COMMIT)

    def test_build_provenance_file_refuses_unverified_source(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            provenance_path = tmp_dir / backend_version.BUILD_PROVENANCE_FILENAME
            with patch("backend.version.resolve_clean_git_commit", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "clean Git worktree"):
                    backend_version.write_build_provenance_file(tmp_dir, provenance_path)

            self.assertFalse(provenance_path.exists())

    def test_build_source_verification_rejects_dirty_or_changed_commit(self) -> None:
        with patch("backend.version.resolve_clean_git_commit", return_value=self.VALID_GIT_COMMIT):
            self.assertEqual(
                backend_version.verify_build_source_commit(Path("repo"), self.VALID_GIT_COMMIT),
                self.VALID_GIT_COMMIT,
            )

        for actual_commit in (None, "abcdef1234567890abcdef1234567890abcdef12"):
            with self.subTest(actual_commit=actual_commit):
                with patch("backend.version.resolve_clean_git_commit", return_value=actual_commit):
                    with self.assertRaisesRegex(RuntimeError, "Build source changed"):
                        backend_version.verify_build_source_commit(Path("repo"), self.VALID_GIT_COMMIT)

    def test_bundled_git_commit_rejects_missing_or_invalid_payload(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            provenance_path = tmp_dir / backend_version.BUILD_PROVENANCE_FILENAME
            self.assertIsNone(backend_version.read_bundled_git_commit(provenance_path))

            invalid_payloads = [
                {},
                {
                    "git_commit": "abc123",
                    "schema_version": backend_version.BUILD_PROVENANCE_SCHEMA_VERSION,
                    "source": backend_version.BUILD_PROVENANCE_SOURCE,
                },
                {
                    "git_commit": self.VALID_GIT_COMMIT,
                    "schema_version": "invalid",
                    "source": backend_version.BUILD_PROVENANCE_SOURCE,
                },
                {
                    "git_commit": self.VALID_GIT_COMMIT,
                    "schema_version": backend_version.BUILD_PROVENANCE_SCHEMA_VERSION,
                    "source": "untrusted",
                },
            ]
            for payload in invalid_payloads:
                with self.subTest(payload=payload):
                    provenance_path.write_text(json.dumps(payload), encoding="utf-8")
                    self.assertIsNone(backend_version.read_bundled_git_commit(provenance_path))

            provenance_path.write_text("{invalid", encoding="utf-8")
            self.assertIsNone(backend_version.read_bundled_git_commit(provenance_path))

    def test_runtime_commit_uses_bundled_sha_when_frozen_without_git(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            provenance_path = tmp_dir / "backend" / backend_version.BUILD_PROVENANCE_FILENAME
            provenance_path.parent.mkdir(parents=True, exist_ok=True)
            provenance_path.write_text(
                json.dumps(
                    {
                        "git_commit": self.VALID_GIT_COMMIT,
                        "schema_version": backend_version.BUILD_PROVENANCE_SCHEMA_VERSION,
                        "source": backend_version.BUILD_PROVENANCE_SOURCE,
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(backend_version.sys, "frozen", True, create=True),
                patch.object(backend_version, "__file__", str(provenance_path.with_name("version.py"))),
                patch("backend.version.subprocess.run", side_effect=AssertionError("Git must not run")) as git_run,
            ):
                commit = backend_version.resolve_runtime_git_commit()

            self.assertEqual(commit, self.VALID_GIT_COMMIT)
            git_run.assert_not_called()

    def test_runtime_commit_keeps_clean_dev_checkout_behavior(self) -> None:
        with (
            patch.object(backend_version.sys, "frozen", False, create=True),
            patch("backend.version.resolve_clean_git_commit", return_value=self.VALID_GIT_COMMIT) as clean_git,
        ):
            commit = backend_version.resolve_runtime_git_commit(project_root=Path("repo"))

        self.assertEqual(commit, self.VALID_GIT_COMMIT)
        clean_git.assert_called_once_with(Path("repo"))

    def test_v2_sidecar_records_runtime_identity_and_shadow_metadata(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=False, csv_v2_enabled=True)

            with patch.object(service, "_resolve_clean_git_commit", return_value=self.VALID_GIT_COMMIT):
                handle, writer = service._open_v2_log_file(
                    "20260309_072025",
                    "Factory_Integrated_Log_v2",
                )

            self.assertIsNotNone(handle)
            self.assertIsNotNone(writer)
            assert handle is not None
            handle.close()

            v2_path = tmp_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            metadata = json.loads(v2_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))
            schema_metadata = metadata["schema_metadata"]
            shadow_metadata = metadata["spot_temperature_shadow_metadata"]

            self.assertEqual(
                schema_metadata["logger_service_instance_id"],
                service.logger_service_instance_id,
            )
            self.assertEqual(
                schema_metadata["logger_service_started_at"],
                service.logger_service_started_at,
            )
            self.assertEqual(schema_metadata["git_commit"], self.VALID_GIT_COMMIT)
            self.assertEqual(schema_metadata["row_unique_key"], ["logger_service_instance_id", "sample_seq"])
            self.assertIn("spot_observation_fact", schema_metadata["spot_observation_key_scope"])
            self.assertEqual(shadow_metadata["sentinel_map"]["server_pc_verified"], False)
            self.assertEqual(shadow_metadata["sentinel_map"]["verified_no_target_values"], [])
            self.assertEqual(shadow_metadata["poll_freshness_threshold_status"], "candidate_unverified_server_pc")
            self.assertIn("v2.4.0", shadow_metadata["v2_3_policy"])

    def test_v2_sidecar_frozen_runtime_records_bundled_commit_without_git(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            provenance_path = tmp_dir / "bundle" / "backend" / backend_version.BUILD_PROVENANCE_FILENAME
            provenance_path.parent.mkdir(parents=True, exist_ok=True)
            provenance_path.write_text(
                json.dumps(
                    {
                        "git_commit": self.VALID_GIT_COMMIT,
                        "schema_version": backend_version.BUILD_PROVENANCE_SCHEMA_VERSION,
                        "source": backend_version.BUILD_PROVENANCE_SOURCE,
                    }
                ),
                encoding="utf-8",
            )
            service = self.create_service(tmp_dir, True, csv_v1_enabled=False, csv_v2_enabled=True)

            with (
                patch.object(backend_version.sys, "frozen", True, create=True),
                patch.object(backend_version, "__file__", str(provenance_path.with_name("version.py"))),
                patch("backend.version.subprocess.run", side_effect=AssertionError("Git must not run")) as git_run,
            ):
                handle, writer = service._open_v2_log_file(
                    "20260309_072025",
                    "Factory_Integrated_Log_v2",
                )

            self.assertIsNotNone(handle)
            self.assertIsNotNone(writer)
            assert handle is not None
            handle.close()
            git_run.assert_not_called()

            metadata_path = tmp_dir / "Factory_Integrated_Log_v2_20260309_072025.metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_metadata"]["git_commit"], self.VALID_GIT_COMMIT)

    def test_v2_sidecar_rejects_invalid_git_commit_at_metadata_boundary(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=False, csv_v2_enabled=True)

            with patch.object(service, "_resolve_clean_git_commit", return_value="abc123"):
                handle, writer = service._open_v2_log_file(
                    "20260309_072025",
                    "Factory_Integrated_Log_v2",
                )

            self.assertIsNotNone(handle)
            self.assertIsNotNone(writer)
            assert handle is not None
            handle.close()

            metadata_path = tmp_dir / "Factory_Integrated_Log_v2_20260309_072025.metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIsNone(metadata["schema_metadata"]["git_commit"])

    def test_v2_writer_refuses_append_when_existing_header_mismatches_schema(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True, csv_v1_enabled=False, csv_v2_enabled=True)
            v2_path = tmp_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS[:-1])

            with self.assertLogs("SmartFactoryLoggerV2", level="ERROR") as logs:
                handle, writer = service._open_v2_log_file(
                    "20260309_072025",
                    "Factory_Integrated_Log_v2",
                )

            self.assertIsNone(handle)
            self.assertIsNone(writer)
            self.assertTrue(any("schema mismatch" in message for message in logs.output))
            self.assertEqual(self.read_rows(v2_path)[0], V2_CSV_COLUMNS[:-1])
            self.assertFalse(v2_path.with_suffix(".metadata.json").exists())

    def test_v1_disabled_v2_disabled_falls_back_to_v1(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
                service = self.create_service(tmp_dir, True, csv_v1_enabled=False, csv_v2_enabled=False)

            self.assertTrue(service.csv_v1_enabled)
            self.assertTrue(any("cannot disable both v1 and v2 writers" in message for message in logs.output))
            service.start()

            try:
                service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                self.wait_for_processing()
            finally:
                service.stop()

            self.assertEqual(len(self.list_v1_files(tmp_dir)), 1)
            self.assertEqual(self.list_v2_files(tmp_dir), [])

    def test_runtime_state_reports_logging_config(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)

            runtime_state = service.get_runtime_state()

            self.assertTrue(runtime_state["auto_save"])
            self.assertEqual(runtime_state["log_path"], str(tmp_dir))

    def test_rows_are_retained_until_file_open_succeeds(self) -> None:
        with self.create_temp_dir() as tmp_dir:
            service = self.create_service(tmp_dir, True)
            original_open = service._open_log_file
            attempts = {"count": 0}

            def delayed_open(timestamp_str: str, prefix: str):
                attempts["count"] += 1
                if attempts["count"] <= 3:
                    return None, None
                return original_open(timestamp_str, prefix)

            with patch.object(service, "_open_log_file", side_effect=delayed_open):
                service.start()
                try:
                    service.enqueue(self.create_data("2026-03-09T07:20:25.000", 30.0))
                    service.enqueue(self.create_data("2026-03-09T07:20:25.100", 31.0))
                    time.sleep(1.2)
                finally:
                    service.stop()

            files = self.list_v1_files(tmp_dir)
            self.assertEqual(len(files), 1)
            rows = self.read_rows(files[0])
            self.assertEqual([row[1] for row in rows[1:]], ["07:20:25.000", "07:20:25.100"])

    def test_health_exposes_runtime_identifiers(self) -> None:
        if backend_app is None:
            payload = get_runtime_info()
            self.assertEqual(payload["app_version"], __version__)
            self.assertIn(payload["runtime_kind"], {"dev", "frozen"})
            self.assertTrue(payload["executable_path"])
            self.assertIn("executable_mtime", payload)
            return

        payload = asyncio.run(backend_app.health(Request({"type": "http", "headers": []}), Response()))
        self.assertEqual(payload["app_version"], __version__)
        self.assertIn(payload["runtime_kind"], {"dev", "frozen"})
        self.assertTrue(payload["executable_path"])
        self.assertIn("executable_mtime", payload)

    def test_env_float_parses_float_value(self) -> None:
        with patch.dict(os.environ, {"SFL_RUNTIME_FLOAT": "1.5"}, clear=False):
            self.assertEqual(config._env_float("SFL_RUNTIME_FLOAT", 3.0), 1.5)

if __name__ == "__main__":
    unittest.main()
