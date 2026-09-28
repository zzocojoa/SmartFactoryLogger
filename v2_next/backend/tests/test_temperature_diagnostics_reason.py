"""D1 exclusion evidence through production decisions, service and CSV writer.

Only synthetic inputs and temporary files are used; no physical device I/O.
"""
import csv
import json
import tempfile
import time
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend import config
from backend.FacilityData.freshness import clock_domain_id
from backend.FacilityData.operator_metadata import OperatorMetadataStore
from backend.FacilityData.repository import (
    CSVLoggerService,
    CSV_SCHEMA_VERSION_V2_3,
    V2_3_CSV_COLUMNS,
    V2_5_CSV_COLUMNS,
)
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.service import PLCService
from backend.FacilityData.temperature_operational import (
    TemperatureOperationalInput,
    derive_temperature_operational_fields,
)
from scripts.validate_csv_v2_shadow import (
    validate_spot_configuration_snapshot,
    validate_v2_4_operational_invariants,
)


CASES = {
    "fact_only": {"diagnostics_collection_mode": "async_fact_only"},
    "previous_poll": {"diagnostics_source_poll_seq": 13, "diagnostics_binding_status": "previous_poll"},
    "stale": {"diagnostics_age_ms": 7000.0},
    "capture_missing": {"diagnostics_capture_status": "missing"},
    "required_field_failed": {"diagnostics_field_status": {"alarmstatus": "timeout"}},
}


def diagnostic_fields(**updates):
    fields = {
        "alarmstatus": 16,
        "diagnostics_snapshot_id": "synthetic-d1:diag:14",
        "diagnostics_source_poll_seq": 14,
        "diagnostics_capture_status": "async_complete",
        "diagnostics_collection_mode": "async_same_poll",
        "diagnostics_binding_status": "same_poll",
        "diagnostics_age_ms": 10.0,
        "diagnostics_max_age_ms": 6000.0,
        "diagnostics_field_status": {"alarmstatus": "success"},
    }
    fields.update(updates)
    return fields


def under_range(**updates):
    fields = {
        "poll_status": "success", "raw_validity": "invalid_sentinel",
        "source_freshness": "fresh", "temperature_value_origin": "none",
        "spot_device_status_code": "temperature_under_range",
        "spot_effective_age_ms_at_row": 10.0,
        "diagnostics_current_poll_seq": 14,
        "diagnostics_current_service_instance_id": "synthetic-d1",
        **diagnostic_fields(),
    }
    fields.update(updates)
    return TemperatureOperationalInput(**fields)


class DiagnosticsReasonTests(unittest.TestCase):
    def test_five_exclusion_reasons_are_distinct_without_causal_promotion(self):
        for reason, changes in CASES.items():
            with self.subTest(reason=reason):
                decision = derive_temperature_operational_fields(under_range(**changes))
                self.assertEqual(decision.temperature_output_status, "under_range")
                self.assertEqual(decision.temperature_unavailable_reason, "under_range")
                self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")
                self.assertEqual(decision.temperature_cause_confidence, 0.0)
                self.assertEqual(decision.temperature_value_origin, "none")
                self.assertTrue(decision.diagnostics_cause_suppressed)
                self.assertEqual(decision.diagnostics_cause_suppressed_reason, reason)
                self.assertEqual(json.loads(decision.temperature_cause_evidence_codes),
                                 ["diagnostics_excluded_" + reason])

    def test_fact_only_policy_precedes_missing_stale_and_failed_fields(self):
        for other_reason, changes in CASES.items():
            with self.subTest(other_reason=other_reason):
                decision = derive_temperature_operational_fields(under_range(
                    **{**changes, "diagnostics_collection_mode": "async_fact_only"}))
                self.assertEqual(decision.diagnostics_cause_suppressed_reason, "fact_only")
                self.assertEqual(json.loads(decision.temperature_cause_evidence_codes),
                                 ["diagnostics_excluded_fact_only"])
                self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")

    def test_external_reason_labels_cannot_override_current_eligibility(self):
        decision = derive_temperature_operational_fields(under_range(
            diagnostics_collection_mode="async_fact_only",
            evidence_codes=("alarm_low_signal", "diagnostics_missing_or_stale",
                            "diagnostics_excluded_stale", "diagnostics_excluded_previous_poll")))
        self.assertEqual(json.loads(decision.temperature_cause_evidence_codes),
                         ["diagnostics_excluded_fact_only"])
        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")

    def test_eligible_diagnostics_and_unverified_comparator_keep_existing_gates(self):
        eligible = derive_temperature_operational_fields(under_range())
        self.assertEqual(eligible.temperature_under_range_cause_candidate, "low_signal_candidate")
        self.assertEqual(json.loads(eligible.temperature_cause_evidence_codes), ["alarm_low_signal"])
        self.assertFalse(eligible.diagnostics_cause_suppressed)
        unverified = derive_temperature_operational_fields(under_range(
            alarmstatus=0, signalpc=1.0,
            diagnostics_field_status={"alarmstatus": "success", "signalpc": "success"},
            low_signal_threshold_pc=2.0, low_signal_alarm_enabled=True,
            low_signal_comparator="lt", low_signal_comparator_verified=False))
        self.assertEqual(unverified.temperature_under_range_cause_candidate, "unknown")
        self.assertNotIn("signal_below_threshold", json.loads(unverified.temperature_cause_evidence_codes))

    def test_non_under_range_rows_keep_blank_cause_evidence(self):
        cases = [
            ({"raw_validity": "valid_temperature", "spot_device_status_code": None,
              "temperature_value_origin": "current_observation"}, "valid"),
            ({"spot_device_status_code": "temperature_over_range"}, "over_range"),
            ({"source_freshness": "stale", "spot_effective_age_ms_at_row": 10000}, "stale"),
            ({"spot_effective_age_ms_at_row": -1}, "unknown"),
        ]
        for changes, status in cases:
            with self.subTest(status=status):
                decision = derive_temperature_operational_fields(under_range(
                    **{**changes, "diagnostics_collection_mode": "async_fact_only"}))
                self.assertEqual(decision.temperature_output_status, status)
                self.assertEqual(decision.temperature_cause_evidence_codes, "")
                self.assertFalse(decision.diagnostics_cause_suppressed)

    def test_no_diagnostic_material_keeps_existing_suppression_scope(self):
        decision = derive_temperature_operational_fields(under_range(
            alarmstatus=None, signalpc=None, diagnostics_collection_mode="async_fact_only"))
        self.assertFalse(decision.diagnostics_cause_suppressed)
        self.assertEqual(decision.diagnostics_cause_suppressed_reason, "")
        self.assertEqual(json.loads(decision.temperature_cause_evidence_codes), [])
        self.assertEqual(decision.temperature_under_range_cause_candidate, "unknown")


class DiagnosticsReasonCsvTests(unittest.TestCase):
    def _prepare_existing_schema_rollover(self, root, rule):
        writer = CSVLoggerService()
        writer.apply_config(log_path=root, auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True,
                            csv_v2_sidecar_enabled=True, csv_v2_operational_fields_enabled=True,
                            csv_v2_temperature_hardening_enabled=True)
        timestamp = datetime(2026, 9, 29, 1, 0, 0, tzinfo=timezone.utc)
        stamp = writer._filename_timestamp(timestamp)
        base = root / f"Factory_Integrated_Log_v2_{stamp}.csv"
        schema_target = base.with_name(f"{base.stem}_2_5_2.csv")
        for path, columns, schema in (
            (base, V2_3_CSV_COLUMNS, CSV_SCHEMA_VERSION_V2_3),
            (schema_target, V2_5_CSV_COLUMNS, "2.5.2"),
        ):
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                csv.writer(handle).writerows([columns, [schema] + [""] * (len(columns) - 1)])
        base.with_suffix(".metadata.json").write_text(json.dumps({
            "schema_metadata": {"schema_version": CSV_SCHEMA_VERSION_V2_3},
        }), encoding="utf-8")
        if rule is not None:
            schema_target.with_suffix(".metadata.json").write_text(json.dumps({
                "schema_metadata": {
                    "schema_version": "2.5.2", "temperature_operational_rule_version": rule,
                },
            }), encoding="utf-8")
        preserved = {path: path.read_bytes() for path in root.iterdir()}
        return writer, timestamp, base, schema_target, preserved

    def test_worker_writes_v6_after_existing_old_or_unknown_rule_schema_rollover(self):
        for old_rule in ("temperature-operational-v5", None):
            with self.subTest(old_rule=old_rule), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(config, "SPOT_OBSERVATION_FACT_ENABLED", False), \
                    patch.object(config, "SPOT_IMAGE_CAPTURE_ENABLED", False):
                root = Path(tmp)
                writer, timestamp, base, schema_target, preserved = self._prepare_existing_schema_rollover(
                    root, old_rule)
                writer.start()
                try:
                    for count in (3, 4):
                        writer.enqueue(FactoryData(Time=timestamp.isoformat(), Status="Running", Count=count))
                finally:
                    stopped = writer.stop()
                self.assertTrue(stopped)
                target = schema_target.with_name(f"{schema_target.stem}_temperature_operational_v6.csv")
                self.assertTrue(target.is_file())
                self.assertEqual(len(list(root.glob("*.csv"))), 3)
                with target.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual([row["sample_seq"] for row in rows], ["1", "2"])
                self.assertEqual([row["Count"] for row in rows], ["3", "4"])
                metadata = json.loads(target.with_suffix(".metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(metadata["schema_metadata"]["temperature_operational_rule_version"],
                                 "temperature-operational-v6")
                for path, original in preserved.items():
                    self.assertEqual(path.read_bytes(), original)
                if old_rule is None:
                    self.assertFalse(schema_target.with_suffix(".metadata.json").exists())

    def test_compatible_schema_rollover_is_reused_without_another_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            writer, timestamp, _, schema_target, preserved = self._prepare_existing_schema_rollover(
                root, "temperature-operational-v6")
            handle, csv_writer = writer._open_v2_log_file(writer._filename_timestamp(timestamp),
                                                        "Factory_Integrated_Log_v2")
            try:
                self.assertIsNotNone(handle)
                self.assertIsNotNone(csv_writer)
                self.assertEqual(writer._current_v2_csv_path, schema_target)
            finally:
                writer._close_file(handle)
            self.assertEqual(set(root.iterdir()), set(preserved))
            for path, original in preserved.items():
                self.assertEqual(path.read_bytes(), original)

    def test_conflicting_rule_target_after_schema_rollover_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            writer, timestamp, _, schema_target, _ = self._prepare_existing_schema_rollover(
                root, "temperature-operational-v5")
            target = schema_target.with_name(f"{schema_target.stem}_temperature_operational_v6.csv")
            target.write_bytes(schema_target.read_bytes())
            target.with_suffix(".metadata.json").write_bytes(schema_target.with_suffix(".metadata.json").read_bytes())
            preserved = {path: path.read_bytes() for path in root.iterdir()}
            handle, csv_writer = writer._open_v2_log_file(writer._filename_timestamp(timestamp),
                                                        "Factory_Integrated_Log_v2")
            try:
                self.assertIsNone(handle)
                self.assertIsNone(csv_writer)
            finally:
                writer._close_file(handle)
            self.assertEqual(set(root.iterdir()), set(preserved))
            for path, original in preserved.items():
                self.assertEqual(path.read_bytes(), original)

    def test_unknown_rule_rollover_and_incompatible_target_preserve_existing_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_path = root / "Factory_Integrated_Log_v2_20260923_000000.csv"
            with old_path.open("w", encoding="utf-8-sig", newline="") as stream:
                csv.writer(stream).writerows([V2_5_CSV_COLUMNS, ["2.5.2"] + [""] * (len(V2_5_CSV_COLUMNS) - 1)])
            original = old_path.read_bytes()
            writer = CSVLoggerService()
            writer.apply_config(log_path=root, auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True,
                                csv_v2_sidecar_enabled=True, csv_v2_operational_fields_enabled=True,
                                csv_v2_temperature_hardening_enabled=True)
            handle, _ = writer._open_v2_log_file("20260923_000000", "Factory_Integrated_Log_v2")
            self.assertIsNotNone(handle)
            writer._close_file(handle)
            target = writer._current_v2_csv_path
            self.assertNotEqual(target, old_path)
            self.assertEqual(old_path.read_bytes(), original)
            self.assertFalse(old_path.with_suffix(".metadata.json").exists())
            # A conflicting pre-existing rollover target must never be overwritten.
            target_sidecar = target.with_suffix(".metadata.json")
            metadata = json.loads(target_sidecar.read_text(encoding="utf-8"))
            metadata["schema_metadata"]["temperature_operational_rule_version"] = "temperature-operational-v5"
            target_sidecar.write_text(json.dumps(metadata), encoding="utf-8")
            preserved = (target.read_bytes(), target_sidecar.read_bytes())
            handle, csv_writer = writer._open_v2_log_file("20260923_000000", "Factory_Integrated_Log_v2")
            self.assertIsNone(handle)
            self.assertIsNone(csv_writer)
            self.assertEqual((target.read_bytes(), target_sidecar.read_bytes()), preserved)
            self.assertEqual(old_path.read_bytes(), original)

    def test_rule_change_rolls_over_without_relabelling_or_appending_old_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_path = root / "Factory_Integrated_Log_v2_20260923_000000.csv"
            with old_path.open("w", encoding="utf-8-sig", newline="") as stream:
                csv.writer(stream).writerows([V2_5_CSV_COLUMNS, ["2.5.2"] + [""] * (len(V2_5_CSV_COLUMNS) - 1)])
            sidecar = old_path.with_suffix(".metadata.json")
            sidecar.write_text(json.dumps({"schema_metadata": {
                "schema_version": "2.5.2", "temperature_operational_rule_version": "temperature-operational-v5"
            }}), encoding="utf-8")
            original = (old_path.read_bytes(), sidecar.read_bytes())
            writer = CSVLoggerService()
            writer.apply_config(log_path=root, auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True,
                                csv_v2_sidecar_enabled=True, csv_v2_operational_fields_enabled=True,
                                csv_v2_temperature_hardening_enabled=True)
            handle, _ = writer._open_v2_log_file("20260923_000000", "Factory_Integrated_Log_v2")
            self.assertIsNotNone(handle)
            writer._close_file(handle)
            new_path = writer._current_v2_csv_path
            self.assertNotEqual(new_path, old_path)
            self.assertEqual((old_path.read_bytes(), sidecar.read_bytes()), original)
            self.assertEqual(json.loads(new_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))[
                "schema_metadata"]["temperature_operational_rule_version"], "temperature-operational-v6")
            # The exact new rule can be reopened without making another generation of files.
            handle, _ = writer._open_v2_log_file("20260923_000000", "Factory_Integrated_Log_v2")
            self.assertIsNotNone(handle)
            writer._close_file(handle)
            self.assertEqual(writer._current_v2_csv_path, new_path)
            self.assertEqual(len(list(root.glob("*.csv"))), 2)

    def test_v5_provenance_gate_remains_enabled_after_rule_version_bump(self):
        for version in ("temperature-operational-v5", "temperature-operational-v6"):
            with self.subTest(version=version):
                failures = validate_spot_configuration_snapshot(
                    {"schema_metadata": {"temperature_operational_rule_version": version},
                     "spot_configuration_snapshot": {}}, [], V2_5_CSV_COLUMNS)
                self.assertTrue(any("spot_config_revision" in failure for failure in failures), failures)

    def test_service_writer_persists_exact_reason_and_preserves_blank_temperature(self):
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            stack.enter_context(patch.object(config, "APP_DATA_DIR", root))
            stack.enter_context(patch.object(config, "SPOT_REFRESH_INTERVAL", 3.0))
            stack.enter_context(patch.object(config, "SPOT_OBSERVATION_FACT_ENABLED", False))
            stack.enter_context(patch.object(config, "SPOT_IMAGE_CAPTURE_ENABLED", False))
            store = OperatorMetadataStore(root / "metadata.json")
            stack.enter_context(patch("backend.FacilityData.service.operator_metadata_store", store))
            service = PLCService(use_mock=True, operator_metadata_runtime_state_path=root / "runtime.json")
            writer = CSVLoggerService()
            writer.apply_config(log_path=root, auto_save=True, csv_v1_enabled=False,
                                csv_v2_enabled=True, csv_v2_sidecar_enabled=True,
                                csv_v2_operational_fields_enabled=True,
                                csv_v2_temperature_hardening_enabled=True)
            writer.start()
            try:
                for reason, changes in CASES.items():
                    now = datetime.now(timezone.utc)
                    mono = time.monotonic()
                    data = FactoryData(
                        Time=now.isoformat(), Status="Running", Spot=None, Count=1, Speed=0, Press=0,
                        spot_service_instance_id="synthetic-d1", spot_poll_seq=14, spot_observation_seq=14,
                        spot_poll_status="success", spot_raw_validity="invalid_sentinel",
                        spot_source_freshness="fresh", spot_device_status_code="temperature_under_range",
                        spot_temperature_raw="6553.4", temperature_value_origin="none",
                        spot_last_poll_completed_at=now.isoformat(), spot_last_poll_completed_monotonic=mono,
                        spot_clock_domain_id=clock_domain_id(), spot_snapshot_age_ms=0,
                        **{**diagnostic_fields(**changes), "alarmstatus": "0x10"})
                    composed = service._compose_data(data, now.timestamp())
                    self.assertIsNone(composed.Spot)
                    writer.enqueue(composed)
            finally:
                self.assertTrue(writer.stop())
            paths = list(root.glob("Factory_Integrated_Log_v2_*.csv"))
            self.assertEqual(len(paths), 1)
            with paths[0].open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                self.assertEqual(reader.fieldnames, V2_5_CSV_COLUMNS)
            self.assertEqual(len(rows), len(CASES))
            for row, reason in zip(rows, CASES):
                self.assertEqual(row["Temperature"], "")
                self.assertEqual(row["temperature_output_status"], "under_range")
                self.assertEqual(row["temperature_under_range_cause_candidate"], "unknown")
                self.assertEqual(json.loads(row["temperature_cause_evidence_codes"]),
                                 ["diagnostics_excluded_" + reason])
            raw_rows = [[row[column] for column in V2_5_CSV_COLUMNS] for row in rows]
            self.assertEqual(validate_v2_4_operational_invariants(
                raw_rows, V2_5_CSV_COLUMNS, operational_rule_version="temperature-operational-v6"), [])
            evidence_index = V2_5_CSV_COLUMNS.index("temperature_cause_evidence_codes")
            for evidence, message in [
                (["diagnostics_missing_or_stale"], "specific diagnostics exclusion reason"),
                (["diagnostics_excluded_bad_value"], "unknown diagnostics exclusion reason"),
                (["diagnostics_excluded_fact_only", "diagnostics_excluded_stale"], "multiple diagnostics exclusion reasons"),
            ]:
                invalid = list(raw_rows[0])
                invalid[evidence_index] = json.dumps(evidence)
                failures = validate_v2_4_operational_invariants(
                    [invalid], V2_5_CSV_COLUMNS, operational_rule_version="temperature-operational-v6")
                self.assertTrue(any(message in item for item in failures), failures)
            legacy = list(raw_rows[0])
            legacy[evidence_index] = '["diagnostics_missing_or_stale"]'
            self.assertEqual(validate_v2_4_operational_invariants(
                [legacy], V2_5_CSV_COLUMNS, operational_rule_version="temperature-operational-v5"), [])
            summary = writer.get_v2_4_operational_summary()
            self.assertEqual(summary["diagnostics_cause_suppressed_reason_counts"],
                             dict.fromkeys(CASES, 1))
            metadata = json.loads(paths[0].with_suffix(".metadata.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(metadata["schema_metadata"]["temperature_operational_rule_version"],
                             "temperature-operational-v6")
