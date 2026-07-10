import asyncio
import csv
import json
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from typing import Any
import unittest
from uuid import uuid4
from unittest.mock import patch

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

        payload = asyncio.run(backend_app.health())
        self.assertEqual(payload["app_version"], __version__)
        self.assertIn(payload["runtime_kind"], {"dev", "frozen"})
        self.assertTrue(payload["executable_path"])
        self.assertIn("executable_mtime", payload)

    def test_env_float_parses_float_value(self) -> None:
        with patch.dict(os.environ, {"SFL_RUNTIME_FLOAT": "1.5"}, clear=False):
            self.assertEqual(config._env_float("SFL_RUNTIME_FLOAT", 3.0), 1.5)

if __name__ == "__main__":
    unittest.main()
