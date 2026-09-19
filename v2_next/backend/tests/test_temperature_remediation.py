"""Production-path regressions. Clocks and I/O are synthetic, not field measurements."""
import unittest
import csv
import json
import tempfile
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.FacilityData.temperature_operational import (
    TemperatureOperationalInput, derive_temperature_operational_fields, derive_spot_row_freshness,
)
from backend.FacilityData.freshness import clock_domain_id
from backend.FacilityData.repository import CSVLoggerService
from backend.FacilityData.repository import V2_5_CSV_COLUMNS
from backend.FacilityData.schemas import FactoryData
from backend.FacilityData.drivers import spot_api
from backend.FacilityData.drivers.real_plc import RealPLCDriver
from backend.FacilityData.spot_observation import classify_spot_raw_response
from backend.FacilityData.process_phase import ProcessPhaseInput, derive_process_phase_candidate


class CacheAtRowTests(unittest.TestCase):
    def cached(self, age, clock="ok"):
        return derive_temperature_operational_fields(TemperatureOperationalInput(
            poll_status="timeout", raw_validity="not_evaluated", source_freshness="fresh",
            cache_fallback_allowed=True, has_ttl_valid_cache=True, has_previous_valid_value=True,
            temperature_value_origin="cached_observation", spot_effective_age_ms_at_row=100,
            spot_effective_value_age_ms_at_row=age, spot_value_age_clock_status=clock,
        ))

    def test_ttl_boundary(self):
        for age, accepted in [(14999, True), (15000, True), (15001, False)]:
            with self.subTest(age=age):
                self.assertEqual(self.cached(age).cached_fallback_accepted, accepted)

    def test_invalid_value_age_or_clock_never_reuses(self):
        for age in [None, True, False, "bad", float("nan"), float("inf"), -float("inf"), -1]:
            with self.subTest(age=age):
                result = self.cached(age)
                self.assertFalse(result.cached_fallback_accepted)
                self.assertTrue(result.cached_fallback_rejected_reason)
        for clock in ["unknown", "clock_anomaly"]:
            self.assertFalse(self.cached(100, clock).cached_fallback_accepted)

    def test_snapshot_14900_row_15100_rejected(self):
        data = FactoryData(Time="2026-09-09T00:00:00Z", Status="Running",
            Spot=500, spot_poll_status="timeout", spot_raw_validity="not_evaluated",
            spot_source_freshness="fresh", spot_cache_status="reused",
            cache_fallback_allowed=True, temperature_value_origin="cached_observation",
            spot_last_valid_value_at="2026-09-09T00:00:00Z",
            spot_last_valid_value_monotonic=100, spot_last_poll_completed_monotonic=115,
            spot_clock_domain_id=clock_domain_id(),
            spot_value_age_ms=14900)
        result = CSVLoggerService()._derive_temperature_operational_decision(
            data, "unknown", datetime(2026, 9, 9, tzinfo=timezone.utc), 115.1, True)
        self.assertFalse(result.cached_fallback_accepted)
        self.assertNotEqual(result.temperature_output_status, "valid")

    def test_driver_sentinel_timeout_recovery_and_wall_clock_reversal(self):
        with ExitStack() as stack:
            for name, value in {
                "_spot_temperature_snapshot": None, "_spot_observation_seq": 0,
                "_spot_last_valid_value_at": None, "_spot_last_valid_value_monotonic": None,
                "_spot_temperature_cache_suppressed_until_valid": False,
                "_temperature_cache": {},
            }.items():
                stack.enter_context(patch.object(spot_api, name, value))
            stack.enter_context(patch.object(spot_api, "_spot_configuration_snapshot", return_value={}))
            stack.enter_context(patch.object(spot_api, "_latest_spot_diagnostics_for_poll", return_value={}))
            clock = stack.enter_context(patch.object(spot_api.time, "monotonic", return_value=100))

            def publish(body, seq, mono):
                spot_api._publish_spot_temperature_snapshot(
                    poll_seq=seq, poll_started_at=1000 + seq, poll_completed_at=1000 + seq,
                    poll_completed_monotonic=mono, temp_url="",
                    classification=classify_spot_raw_response(
                        poll_status="timeout" if body is None else "success", body=body))

            for sentinel in [b"6553.4", b"6553.5"]:
                spot_api._spot_observation_seq = 0
                for seq, body in enumerate([b"500", sentinel, None, b"501", None], 1):
                    publish(body, seq, 100 + seq)
                    clock.return_value = 100 + seq + .1
                    metadata = spot_api._build_spot_temperature_snapshot_diagnostics(900)  # wall reversed
                    fields = RealPLCDriver._spot_metadata_to_factory_fields(None, metadata)
                    data = FactoryData(Time="2026-09-09T00:00:00Z", Status="Running", **fields)
                    result = CSVLoggerService()._derive_temperature_operational_decision(
                        data, "unknown", datetime.fromtimestamp(1000 + seq + .1, timezone.utc),
                        clock.return_value, True)
                    if seq in [2, 3]:
                        self.assertFalse(result.cached_fallback_accepted)
                        self.assertEqual(result.temperature_value_origin, "none")
                    elif seq == 5:
                        self.assertTrue(result.cached_fallback_accepted)
                # Snapshot poll is fresh, but cached value has exceeded TTL despite wall rollback.
                publish(None, 6, 119.1)
                clock.return_value = 119.1
                metadata = spot_api._build_spot_temperature_snapshot_diagnostics(900)
                self.assertNotEqual(metadata["temperature_value_origin"], "cached_observation")
                self.assertAlmostEqual(metadata["spot_value_age_ms"], 15100)
                clock.return_value = 103  # monotonic reversal cannot extend TTL either
                metadata = spot_api._build_spot_temperature_snapshot_diagnostics(900)
                self.assertNotEqual(metadata["temperature_value_origin"], "cached_observation")


class RowFreshnessTests(unittest.TestCase):
    def test_factory_data_cannot_coerce_bool_into_clock_or_source_proof(self):
        for field, value in [("spot_last_poll_completed_monotonic", True),
                             ("spot_last_valid_value_monotonic", True),
                             ("spot_cache_expiry_threshold_sec", True),
                             ("plc_source_age_ms", True), ("plc_source_freshness_threshold_ms", True),
                             ("plc_source_error", 0), ("plc_source_usable", 1)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                FactoryData(Time="2026-09-09T00:00:00Z", Status="Running", **{field: value})
        for field in ["spot_last_poll_completed_monotonic", "spot_last_valid_value_monotonic",
                      "plc_source_age_ms", "plc_source_freshness_threshold_ms"]:
            for value in [float("nan"), float("inf"), -float("inf")]:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    FactoryData(Time="2026-09-09T00:00:00Z", Status="Running", **{field: value})

    def test_clock_domain_and_ingest_wall_fallback(self):
        base = FactoryData(Time="2026-09-09T04:05:03Z", Status="Running", Spot=500,
            spot_poll_status="success", spot_raw_validity="valid_temperature",
            spot_source_freshness="fresh", temperature_value_origin="current_observation",
            spot_last_poll_completed_at="2026-09-09T04:05:00Z",
            spot_last_poll_completed_monotonic=100)
        decision_at = datetime.fromisoformat("2026-09-09T04:08:09+00:00")
        service = CSVLoggerService()
        for domain, expected in [(None, "stale"), ("previous-process", "unknown"),
                                 (clock_domain_id(), "valid")]:
            with self.subTest(domain=bool(domain)):
                result = service._derive_temperature_operational_decision(
                    base.model_copy(update={"spot_clock_domain_id": domain}),
                    "unknown", decision_at, 101, True)
                self.assertEqual(result.temperature_output_status, expected)
        missing_endpoint = base.model_copy(update={"spot_clock_domain_id": clock_domain_id(),
                                                   "spot_last_poll_completed_monotonic": None})
        self.assertEqual(service._derive_temperature_operational_decision(
            missing_endpoint, "unknown", decision_at, 101, True).temperature_output_status, "unknown")
        negative_endpoint = base.model_copy(update={"spot_clock_domain_id": clock_domain_id(),
                                                    "spot_last_poll_completed_monotonic": -1})
        self.assertEqual(service._derive_temperature_operational_decision(
            negative_endpoint, "unknown", decision_at, 101, True).temperature_output_status, "unknown")

    def test_invalid_age_and_threshold_fail_closed(self):
        invalid = [None, True, False, "bad", float("nan"), float("inf"), -float("inf")]
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(derive_spot_row_freshness(value)[0], "unknown")
                self.assertEqual(derive_spot_row_freshness(1, threshold_ms=value)[0], "unknown")
        for threshold in [0, -1]:
            self.assertEqual(derive_spot_row_freshness(1, threshold_ms=threshold)[0], "unknown")
        self.assertEqual(derive_spot_row_freshness(-1), ("unknown", "clock_anomaly"))
        self.assertEqual(derive_spot_row_freshness(9000), ("fresh", "ok"))
        for age, expected in [(2999, "fresh"), (3000, "fresh"), (3001, "stale")]:
            self.assertEqual(derive_spot_row_freshness(age, threshold_ms=3000), (expected, "ok"))

    def test_unknown_cannot_be_valid_but_sentinel_and_transport_evidence_survive(self):
        for age in [None, True, float("nan")]:
            result = derive_temperature_operational_fields(TemperatureOperationalInput(
                poll_status="success", raw_validity="valid_temperature", source_freshness="fresh",
                temperature_value_origin="current_observation", spot_effective_age_ms_at_row=age))
            self.assertEqual(result.temperature_output_status, "unknown")
        for status, raw, device, expected in [
            ("success", "invalid_sentinel", "temperature_under_range", "under_range"),
            ("success", "invalid_sentinel", "temperature_over_range", "over_range"),
            ("timeout", "not_received", None, "source_error"),
        ]:
            result = derive_temperature_operational_fields(TemperatureOperationalInput(
                poll_status=status, raw_validity=raw, source_freshness="fresh",
                spot_device_status_code=device))
            self.assertEqual(result.temperature_output_status, expected)

    def test_seq26_27_declared_synthetic_clock_never_switches_to_sample_age(self):
        service = CSVLoggerService()
        # Fixture timestamps; injected monotonic endpoints are synthetic, not recorded evidence.
        ages = []
        for timestamp, clock in [("2026-09-09T04:05:03.703769+00:00", 288.437),
                                 ("2026-09-09T04:05:03.904425+00:00", 288.439)]:
            ages.append(service._effective_age_ms_at_row(
                row_timestamp=datetime.fromisoformat(timestamp), row_created_monotonic=clock,
                explicit_age_ms=None, source_completed_monotonic=100,
                source_timestamp="2026-09-09T04:05:00.811337Z", fallback_age_ms=None,
                row_freshness_threshold_ms=3000))
        self.assertGreaterEqual(ages[1], ages[0])
        self.assertGreater(ages[1], 188000)


class PlcSourceTests(unittest.TestCase):
    def source(self, *, count=20, age=0, error=False, usable=True, **kwargs):
        return FactoryData(Time="2026-09-09T00:00:00Z", Status="Running", Count=count,
            Speed=1, Press=30, plc_source_age_ms=age, plc_source_error=error,
            plc_source_usable=usable, plc_source_freshness_threshold_ms=5000,
            extruder_process_state_online="unknown", **kwargs)

    def test_plc_stale_error_gate_preserves_spot_and_freezes_lifecycle(self):
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True, csv_v2_temperature_hardening_enabled=True)
        stamp = datetime(2026, 9, 9, tzinfo=timezone.utc)
        start = self.source(process_phase_candidate="die_change_candidate")
        active = service._derive_process_phase_decision(start, stamp, 1).changeover_candidate_id
        self.assertTrue(active)
        for count in [0, 20]:
            for age, error, usable in [(5001, False, True), (0, True, True), (None, False, True), (0, None, True)]:
                for kind in ["valid", "under_range", "over_range"]:
                    with self.subTest(count=count, age=age, error=error, kind=kind):
                        data = self.source(count=count, age=age, error=error, usable=usable,
                            process_phase_candidate="production_stable", Spot=500,
                            spot_poll_status="success", spot_source_freshness="fresh",
                            spot_raw_validity="valid_temperature" if kind == "valid" else "invalid_sentinel",
                            spot_device_status_code=None if kind == "valid" else "temperature_" + kind,
                            temperature_value_origin="current_observation" if kind == "valid" else "none",
                            spot_last_poll_completed_at=stamp.isoformat())
                        row = service._build_v2_row(data, stamp, stamp, 2, service._build_row(data, stamp))
                        result = dict(zip(V2_5_CSV_COLUMNS, row))
                        self.assertEqual(result["process_phase_candidate"], "unknown")
                        self.assertEqual(result["changeover_candidate_id"], "")
                        self.assertEqual(result["temperature_output_status"], kind)
                        self.assertEqual(result["temperature_expectedness_candidate"],
                            "" if kind == "valid" else "unexpected_candidate" if kind == "over_range" else "unknown")
                        self.assertEqual(service._process_phase_runtime_state.active_changeover_candidate_id, active)
                        self.assertEqual(data.Count, count)
        recovered = service._derive_process_phase_decision(self.source(), stamp, 3)
        self.assertEqual(recovered.process_phase_candidate, "production_stabilizing")
        self.assertEqual(recovered.changeover_candidate_id, active)
        for count in range(3):
            self.assertEqual(service._derive_process_phase_decision(
                self.source(count=count, process_phase_candidate="production_stable"), stamp, 4)
                             .process_phase_candidate, "setup_alignment_candidate")

    def test_real_driver_service_collection_gate_and_writer_backlog(self):
        from backend.FacilityData.service import PLCService
        driver = RealPLCDriver()
        service = PLCService(use_mock=True)
        stamp = datetime(2026, 9, 9, tzinfo=timezone.utc)
        epoch = stamp.timestamp()
        for age, error, expected in [(0, None, True), (60, None, False), (0, "synthetic_error", False),
                                      (-1, None, False), (0, None, True)]:
            with patch.object(driver, "_read_cached_snapshot_with_metadata", return_value=(
                {"Count": 0, "Speed": 1.0, "Press": 30}, {}, 500, epoch-age, None, epoch,
                error, None, None, {})), patch("backend.FacilityData.drivers.real_plc.time.time", return_value=epoch):
                raw = driver.read_data()
            composed = service._compose_data(raw, epoch)
            self.assertEqual(composed.plc_source_usable, expected)
            self.assertEqual(composed.Count, 0)
            logger = CSVLoggerService()
            phase = logger._derive_process_phase_decision(composed, stamp, 1)
            self.assertEqual(phase.process_phase_candidate, "setup_alignment_candidate" if expected else "unknown")
            # No row-decision/persistence time may age the already sampled PLC input.
            phase_later = logger._derive_process_phase_decision(composed, stamp, 2)
            self.assertEqual(phase_later.process_phase_candidate, phase.process_phase_candidate)

    def test_missing_source_and_external_phase_cannot_bypass_gate(self):
        self.assertEqual(derive_process_phase_candidate(ProcessPhaseInput(
            speed=1, press=30, count=20)).process_phase_candidate, "unknown")
        service = CSVLoggerService()
        for count in [0, 20]:
            for external in [None, "production_stable", "die_change_candidate"]:
                with self.subTest(count=count, external=external):
                    data = FactoryData(Time="2026-09-09T00:00:00Z", Status="Running",
                        Count=count, Speed=1, Press=30, process_phase_candidate=external)
                    phase = service._derive_process_phase_decision(data, datetime.now(timezone.utc), 1)
                    self.assertEqual(phase.process_phase_candidate, "unknown")
                    self.assertEqual(phase.changeover_candidate_id, "")


class ValidatorAndRolloverTests(unittest.TestCase):
    def test_validator_accepts_unknown_clock_without_erasing_observed_value(self):
        from scripts.validate_csv_v2_shadow import (
            validate_temperature_value_origin_invariants, validate_v2_4_operational_invariants,
            validate_v2_5_temperature_hardening_invariants,
        )
        stamp = datetime(2026, 9, 9, tzinfo=timezone.utc)
        data = FactoryData(Time=stamp.isoformat(), Status="Running", Spot=500,
            spot_poll_status="success", spot_raw_validity="valid_temperature", spot_source_freshness="fresh",
            spot_cache_status="fresh", spot_temperature_observed_c=500,
            temperature_value_origin="current_observation", spot_clock_domain_id="foreign-process",
            spot_last_valid_value_at=stamp.isoformat(), spot_last_poll_completed_at=stamp.isoformat())
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True, csv_v2_temperature_hardening_enabled=True)
        row = service._build_v2_row(data, stamp, stamp, 1, service._build_row(data, stamp))
        self.assertEqual(row[V2_5_CSV_COLUMNS.index("temperature_output_status")], "unknown")
        for validate in [validate_temperature_value_origin_invariants, validate_v2_4_operational_invariants,
                         validate_v2_5_temperature_hardening_invariants]:
            self.assertEqual(validate([row], V2_5_CSV_COLUMNS), [])

    def cached_row(self):
        stamp = datetime(2026, 9, 9, tzinfo=timezone.utc)
        data = FactoryData(Time=stamp.isoformat(), Status="Running", Spot=500,
            spot_poll_status="timeout", spot_raw_validity="not_evaluated", spot_source_freshness="fresh",
            spot_cache_status="reused", cache_fallback_allowed=True, temperature_value_origin="cached_observation",
            spot_last_valid_value_at=stamp.isoformat(), spot_last_poll_completed_at=stamp.isoformat())
        service = CSVLoggerService()
        service.apply_config(csv_v2_operational_fields_enabled=True, csv_v2_temperature_hardening_enabled=True)
        return service._build_v2_row(data, stamp, stamp, 1, service._build_row(data, stamp))

    def test_validator_cache_ttl_and_explicit_invalid_metadata(self):
        from scripts.validate_csv_v2_shadow import (
            validate_v2_5_temperature_hardening_invariants as validate_cache,
            validate_v2_4_operational_invariants as validate_age,
            _metadata_row_time_freshness_threshold_ms as metadata_threshold,
        )
        row = self.cached_row()
        self.assertEqual(row[V2_5_CSV_COLUMNS.index("temperature_output_status")], "valid")
        for age, valid in [("14999", True), ("15000", True), ("15001", False), ("NaN", False), ("", False)]:
            changed = list(row)
            changed[V2_5_CSV_COLUMNS.index("spot_effective_value_age_ms_at_row")] = age
            self.assertEqual(not validate_cache([changed], V2_5_CSV_COLUMNS), valid)
        self.assertEqual(metadata_threshold({}), 9000)
        for value in [None, True, False, "bad", float("nan"), float("inf"), 0, -1]:
            with self.subTest(value=value):
                threshold = metadata_threshold({"spot_temperature_shadow_metadata": {"poll_freshness_threshold_sec": value}})
                self.assertIsNone(threshold)
                self.assertTrue(validate_age([row], V2_5_CSV_COLUMNS, row_time_freshness_threshold_ms=threshold))
                self.assertTrue(validate_cache([row], V2_5_CSV_COLUMNS, cache_ttl_ms=value))

    def test_same_header_old_version_rolls_over_without_rewriting(self):
        for include_row, include_sidecar in [(True, True), (True, False), (False, True), (False, False)]:
            with self.subTest(row=include_row, sidecar=include_sidecar), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                path = directory / "Factory_Integrated_Log_v2_20260909_000000.csv"
                with path.open("w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(V2_5_CSV_COLUMNS)
                    if include_row:
                        row = self.cached_row()
                        row[0] = "2.5.0"
                        writer.writerow(row)
                if include_sidecar:
                    path.with_suffix(".metadata.json").write_text(json.dumps({"schema_metadata": {"schema_version": "2.5.0"}}))
                before = path.read_bytes()
                service = CSVLoggerService()
                service.apply_config(log_path=directory, auto_save=True, csv_v2_enabled=True,
                    csv_v2_operational_fields_enabled=True, csv_v2_temperature_hardening_enabled=True)
                handle, _ = service._open_v2_log_file("20260909_000000", "Factory_Integrated_Log_v2")
                try:
                    self.assertIsNotNone(handle)
                    if include_row or include_sidecar:
                        self.assertNotEqual(service._current_v2_csv_path, path)
                    else:  # Header only, no historical rows or metadata semantics to preserve.
                        self.assertEqual(service._current_v2_csv_path, path)
                    self.assertEqual(path.read_bytes(), before)
                finally:
                    service._close_file(handle)


if __name__ == "__main__":
    unittest.main()
