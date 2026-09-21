"""Synthetic transport/clock regressions: no physical PLC or SPOT connection."""
import os
import tempfile
import time
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.FacilityData.drivers import real_plc
from backend.FacilityData.operator_metadata import OperatorMetadataStore
from backend.FacilityData.repository import CSVLoggerService, V2_5_CSV_COLUMNS
from backend.FacilityData.process_phase import ProcessPhaseInput, derive_process_phase_candidate
from backend.FacilityData.schemas import OperatorMetadataUpdate
from backend.FacilityData.service import PLCService


class MelsecSocket:
    """Respond to the real command encoder; select is the only socket boundary stub."""
    def __init__(self, fail_addr=None, *, zero=False):
        self.fail_addr = fail_addr
        self.zero = zero
        self.commands = []
        self.response = b""

    def send(self, command):
        address, count = command.decode().strip()[5:].split()
        self.commands.append(address)
        values = [0] * int(count)
        if not self.zero:
            for addr, index, value in [("D0020", 3, 300), ("D0020", 11, 400),
                                       ("D0020", 12, 410), ("B1502", 0, 10),
                                       ("D1500", 10, 20), ("D0420", 1, 100),
                                       ("D1900", 11, 500)]:
                if address == addr:
                    values[index] = value
        self.response = (b"01OK000G\r\n" if address == self.fail_addr else
                         ("01OK" + "".join(f"{v:04X}" for v in values) + "\r\n").encode())
        return len(command)

    def recv(self, size):
        response, self.response = self.response, b""
        return response


class PlcFixture(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(real_plc.config, "APP_DATA_DIR", self.root))
        self.store = OperatorMetadataStore(self.root / "metadata.json")
        self.stack.enter_context(patch.dict(os.environ, {"V2_MODE": "MOCK"}))
        self.stack.enter_context(patch("backend.FacilityData.service.operator_metadata_store", self.store))
        self.stack.enter_context(patch.object(real_plc.config, "POSITION_READ_ENABLED", True))
        self.stack.enter_context(patch.object(real_plc.select, "select", side_effect=lambda r, w, x, t: (r, w, [])))
        # Any accidental real connection fails immediately, including recovery paths.
        self.stack.enter_context(patch.object(real_plc.socket, "socket", side_effect=AssertionError("real socket forbidden")))
        self.driver = real_plc.RealPLCDriver()
        self.driver.ext_merge_blocks = False
        self.service = PLCService(use_mock=True, operator_metadata_runtime_state_path=self.root / "runtime.json")
        self.logger = CSVLoggerService()
        self.logger.apply_config(log_path=self.root, csv_v2_operational_fields_enabled=True,
                                 csv_v2_temperature_hardening_enabled=True)

    def cycle(self, transport=None):
        if transport is not None:
            self.driver.sock_ext = transport
        self.driver._worker_stop.clear()
        # Run the actual worker body, stopping at its Event.wait boundary after one cycle.
        with patch.object(self.driver._worker_stop, "wait", side_effect=lambda timeout: self.driver._worker_stop.set()):
            self.driver._ext_worker_loop()
        return self.driver.read_data()

    def row(self, raw, kind="under_range", external=None):
        now = datetime.now(timezone.utc)
        enriched = raw.model_copy(update={
            "Spot": 500 if kind == "valid" else None,
            "spot_poll_status": "success", "spot_source_freshness": "fresh",
            "spot_raw_validity": "valid_temperature" if kind == "valid" else "invalid_sentinel",
            "spot_device_status_code": None if kind == "valid" else "temperature_" + kind,
            "temperature_value_origin": "current_observation" if kind == "valid" else "none",
            "spot_last_poll_completed_at": now.isoformat(),
            "process_phase_candidate": external,
        })
        composed = self.service._compose_data(enriched, now.timestamp())
        row = self.logger._build_v2_row(composed, now, now, 1, self.logger._build_row(composed, now))
        return dict(zip(V2_5_CSV_COLUMNS, row))


class PlcPartialReadTests(PlcFixture):
    def test_count_failure_through_transport_worker_service_repository(self):
        transport = MelsecSocket("D1500")
        raw = self.cycle(transport)
        self.assertEqual(transport.commands[:3], ["D0020", "B1502", "D1500"])
        self.assertEqual(self.driver.ext_invalid_responses, 1)
        self.assertEqual(raw.Press, 30)
        self.assertEqual(raw.Speed, 1)
        self.assertIsNone(raw.Count)
        row = self.row(raw)
        self.assertEqual(row["process_phase_candidate"], "unknown")
        self.assertEqual(row["temperature_expectedness_candidate"], "unknown")
        self.assertFalse(raw.plc_source_usable)
        self.assertTrue(raw.plc_source_error)
        self.assertTrue(self.driver.ext_in_error)
        self.assertIsNone(self.driver.ext_last_success_time)

    def test_other_required_failures_and_zero_values(self):
        for address in ["B1502", "D0020"]:
            with self.subTest(address=address):
                self.driver.ext_skip_counter = 0
                raw = self.cycle(MelsecSocket(address))
                self.assertFalse(raw.plc_source_usable)
                self.assertEqual(self.row(raw)["process_phase_candidate"], "unknown")
        self.driver.ext_skip_counter = 0
        raw = self.cycle(MelsecSocket(zero=True))
        self.assertEqual((raw.Count, raw.Speed, raw.Press), (0, 0, 0))
        self.assertTrue(raw.plc_source_usable)
        self.assertEqual(self.row(raw)["process_phase_candidate"], "setup_candidate")

    def test_optional_position_failure_keeps_required_source_and_spot(self):
        for merged in [False, True]:
            with self.subTest(merged=merged):
                self.driver.ext_merge_blocks = merged
                self.driver.ext_skip_counter = 0
                raw = self.cycle(MelsecSocket("D0010"))
                self.assertEqual((raw.Count, raw.Speed, raw.Press), (20, 1, 30))
                self.assertTrue(raw.plc_source_usable)
                self.assertIsNone(raw.MainRamPosition_D0010)
                self.assertTrue(raw.Die_ID)
                self.assertEqual(raw.Billet_Cycle_ID, "20")
                self.assertTrue(self.driver.ext_in_error)  # transport health remains failed
                self.assertEqual(float(self.row(raw, "valid")["Temperature"]), 500)
                previous_at = raw.captured_at_extruder
                skipped = self.cycle()
                self.assertTrue(skipped.plc_source_usable)
                self.assertEqual(skipped.captured_at_extruder, previous_at)
                self.assertTrue(self.driver.ext_in_error)

    def test_merged_partial_and_split_retry_use_complete_current_attempt(self):
        self.driver.ext_merge_blocks = True
        self.driver.ext_merge_fail_threshold = 1
        self.driver.ext_merge_retry_current = 2
        partial = self.cycle(MelsecSocket("D1500"))
        self.assertEqual(partial.Press, 30)
        self.assertIsNone(partial.Count)
        self.assertFalse(partial.plc_source_usable)
        self.assertFalse(self.driver.ext_merge_blocks)
        self.assertEqual(self.driver.ext_split_success_count, 0)
        for _ in range(5):
            self.assertFalse(self.cycle().plc_source_usable)
        first = self.cycle(MelsecSocket())
        self.assertTrue(first.plc_source_usable)
        self.assertFalse(self.driver.ext_merge_blocks)
        self.assertEqual(self.driver.ext_split_success_count, 1)
        self.cycle(MelsecSocket("D1500"))
        self.assertEqual(self.driver.ext_split_success_count, 0)
        for _ in range(5):
            self.cycle()
        self.cycle(MelsecSocket())
        self.cycle(MelsecSocket())
        self.assertTrue(self.driver.ext_merge_blocks)
        self.assertTrue(self.driver.ext_merge_retry_pending)
        self.assertTrue(self.cycle(MelsecSocket()).plc_source_usable)
        self.assertFalse(self.driver.ext_merge_retry_pending)

    def test_required_field_proof_rejects_missing_nonfinite_boolean_and_invalid_count(self):
        for name in ["Count", "Speed", "Press"]:
            for value in [None, True, float("nan"), float("inf"), -float("inf")]:
                with self.subTest(name=name, value=value):
                    payload = {"Count": 0, "Speed": 0, "Press": 0, name: value}
                    self.driver._update_ext_snapshot(payload, time.time())
                    self.assertIsNotNone(self.driver._ext_snapshot_error)
                    self.assertNotEqual(self.driver.get_comm_metrics()["extruder"]["process_input_status"][name], "valid")
        for count in [-1, .5]:
            self.assertIsNotNone(self.driver._ext_required_input_error({"Count": count, "Speed": 0, "Press": 0}))
        self.assertIsNone(self.driver._ext_required_input_error({"Count": 0, "Speed": 0, "Press": 0}))

    def test_first_partial_cannot_open_changeover(self):
        failed = self.cycle(MelsecSocket("D1500"))
        self.assertEqual(self.row(failed, external="die_change_candidate")["changeover_candidate_id"], "")
        self.assertFalse(self.logger._process_phase_runtime_state.active_changeover_candidate_id)

    def test_claimed_usable_cannot_bypass_missing_required_values(self):
        normal = self.cycle(MelsecSocket())
        for field in ["Count", "Speed", "Press"]:
            with self.subTest(field=field):
                incomplete = normal.model_copy(update={field: None, "process_phase_candidate": "die_change_candidate"})
                phase = self.logger._derive_process_phase_decision(incomplete, datetime.now(timezone.utc), 1)
                self.assertEqual(phase.process_phase_candidate, "unknown")
                values = {"count": 20, "speed": 1, "press": 30, field.lower(): None}
                decision = derive_process_phase_candidate(ProcessPhaseInput(
                    plc_source_age_ms=0, plc_source_freshness_threshold_ms=5000,
                    plc_source_error=False, plc_source_usable=True, **values))
                self.assertEqual(decision.process_phase_candidate, "unknown")

    def test_partial_skip_recovery_does_not_refresh_old_values(self):
        raw = self.cycle(MelsecSocket())
        last_success = self.driver.ext_last_success_time
        self.assertTrue(raw.plc_source_usable)
        raw = self.cycle(MelsecSocket("D1500"))
        failed_at = raw.captured_at_extruder
        self.assertFalse(raw.plc_source_usable)
        self.assertIsNone(raw.Count)
        self.assertEqual(self.driver.ext_last_success_time, last_success)
        for _ in range(5):
            raw = self.cycle()
            self.assertFalse(raw.plc_source_usable)
            self.assertIsNone(raw.Count)
            self.assertEqual(raw.captured_at_extruder, failed_at)
        raw = self.cycle(MelsecSocket())
        self.assertTrue(raw.plc_source_usable)
        self.assertFalse(self.driver.ext_in_error)
        self.assertEqual(self.driver.ext_recovery_count, 1)
        self.assertEqual(raw.Count, 20)

    def test_partial_count_zero_cannot_advance_derived_ids_or_persisted_state(self):
        normal = self.cycle(MelsecSocket())
        logic = self.driver.logic
        before = (vars(logic).copy(), logic.state_path.read_bytes(),
                  logic.state_path.stat().st_mtime_ns)
        self.driver.ext_merge_blocks = True
        partial = self.cycle(MelsecSocket("B1502", zero=True))
        self.assertEqual(partial.Count, 0)  # Preserve the actual partial response.
        self.assertIsNone(partial.Speed)
        self.assertFalse(partial.plc_source_usable)
        for raw in [partial] + [self.cycle() for _ in range(5)]:
            self.assertEqual((raw.Die_ID, raw.Billet_Cycle_ID), ("", ""))
            self.assertEqual((vars(logic).copy(), logic.state_path.read_bytes(),
                              logic.state_path.stat().st_mtime_ns), before)
        recovered = self.cycle(MelsecSocket(zero=True))
        self.assertTrue(recovered.plc_source_usable)
        self.assertEqual(logic.last_counter, 0)
        self.assertEqual(logic.die_seq, before[0]["die_seq"] + 1)
        self.assertNotEqual(recovered.Die_ID, normal.Die_ID)
        repeated = self.cycle(MelsecSocket(zero=True))
        self.assertEqual(repeated.Die_ID, recovered.Die_ID)
        self.assertEqual(logic.die_seq, before[0]["die_seq"] + 1)

    def test_first_partial_count_cannot_create_derived_state_file(self):
        self.driver.ext_merge_blocks = True
        before = vars(self.driver.logic).copy()
        partial = self.cycle(MelsecSocket("B1502", zero=True))
        self.assertEqual(partial.Count, 0)
        self.assertEqual((partial.Die_ID, partial.Billet_Cycle_ID), ("", ""))
        self.assertEqual(vars(self.driver.logic), before)
        self.assertFalse(self.driver.logic.state_path.exists())

    def test_spot_independence_external_phase_and_lifecycle_freeze(self):
        normal = self.cycle(MelsecSocket())
        stamp = datetime.now(timezone.utc)
        self.logger._derive_process_phase_decision(normal.model_copy(update={
            "process_phase_candidate": "die_change_candidate"}), stamp, 1)
        candidate = self.logger._process_phase_runtime_state.active_changeover_candidate_id
        self.assertTrue(candidate)
        failed = self.cycle(MelsecSocket("D1500"))
        for kind in ["valid", "under_range", "over_range"]:
            for external in [None, "production_stable", "die_change_candidate"]:
                with self.subTest(kind=kind, external=external):
                    row = self.row(failed, kind, external)
                    self.assertEqual(row["process_phase_candidate"], "unknown")
                    self.assertEqual(row["changeover_candidate_id"], "")
                    self.assertEqual(row["temperature_output_status"], kind)
                    self.assertEqual(row["temperature_expectedness_candidate"],
                                     "" if kind == "valid" else "unexpected_candidate" if kind == "over_range" else "unknown")
                    self.assertEqual(self.logger._process_phase_runtime_state.active_changeover_candidate_id, candidate)


class MetadataSourceTests(PlcFixture):
    def seed(self):
        self.store.update(OperatorMetadataUpdate(product_no="10001", operator_mold_no="1"))
        raw = self.cycle(MelsecSocket())
        self.service._compose_data(raw, raw.captured_at_extruder)
        self.assertTrue(self.store.get().valid)
        self.assertEqual(self.service.operator_metadata_previous_count, 20)
        return raw

    def state(self):
        runtime = self.service.operator_metadata_runtime_state_path
        return (self.store.get().model_dump(), self.store._path.read_bytes(),
                runtime.read_bytes() if runtime.exists() else None,
                self.service.operator_metadata_previous_count,
                self.service.operator_metadata_last_normal_sample_at,
                self.service.operator_metadata_last_state_write_at,
                self.service._process_operator_context,
                self.store._path.stat().st_mtime_ns,
                runtime.stat().st_mtime_ns if runtime.exists() else None)

    def test_invalid_source_zero_does_not_mutate_store_runtime_or_context(self):
        raw = self.seed()
        before = self.state()
        now = raw.captured_at_extruder
        cases = [
            {"plc_sample_monotonic": raw.plc_source_completed_monotonic + 100}, {"plc_source_error": True},
            {"plc_source_usable": None}, {"plc_sample_monotonic": raw.plc_source_completed_monotonic - 1},
            {"captured_at_extruder": None}, {"captured_at_extruder": float("nan")},
            {"Speed": None}, {"Press": None},
        ]
        for invalid in cases:
            with self.subTest(invalid=invalid):
                data = raw.model_copy(update={"Count": 0, "extruder_process_state_online": "stopped", **invalid})
                self.service._compose_data(data, now)
                self.assertEqual(self.state(), before)

    def test_transport_partial_count_zero_blocks_automatic_changes_repeatedly(self):
        self.seed()
        before = self.state()
        self.driver.ext_merge_blocks = True
        raw = self.cycle(MelsecSocket("B1502", zero=True))
        self.assertEqual(raw.Count, 0)
        self.assertIsNone(raw.Speed)
        self.assertFalse(raw.plc_source_usable)
        for offset in [0, 60, 3600, 8 * 3600 + 1]:
            composed = self.service._compose_data(raw, raw.captured_at_extruder + offset)
            self.assertEqual(self.state(), before)
            self.assertEqual(composed.extruder_process_state_online, "unknown")

    def test_auto_reset_helper_rechecks_source(self):
        raw = self.seed()
        before = self.state()
        invalid = raw.model_copy(update={"Count": 0, "plc_source_usable": False})
        self.service._apply_operator_metadata_auto_reset(invalid, raw.captured_at_extruder)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.service._derive_metadata_process_state_candidate(
            invalid, self.store.get(), raw.captured_at_extruder), "unknown")
        self.service._persist_operator_metadata_runtime_state(
            sample_at_sec=raw.captured_at_extruder, raw_data=invalid, force=True)
        self.assertEqual(self.state(), before)

    def test_valid_twenty_to_zero_and_repeated_zero_preserve_new_manual_input(self):
        self.seed()
        raw = self.cycle(MelsecSocket(zero=True))
        self.service._compose_data(raw, raw.captured_at_extruder)
        self.assertFalse(self.store.get().valid)
        self.assertEqual(self.store.get().source, "auto_count_transition_to_zero")
        self.store.update(OperatorMetadataUpdate(product_no="10002", operator_mold_no="2"))
        before = self.store._path.read_bytes()
        raw = self.cycle(MelsecSocket(zero=True))
        self.service._compose_data(raw, raw.captured_at_extruder)
        self.assertEqual(self.store._path.read_bytes(), before)

    def test_downtime_boundary_compares_previous_normal_before_recovery_update(self):
        for delta, reset in [(8 * 3600 - .001, False), (8 * 3600, True), (8 * 3600 + .001, True)]:
            with self.subTest(delta=delta):
                self.stack.enter_context(patch.object(real_plc.config, "OPERATOR_METADATA_DOWNTIME_RESET_HOURS", 8))
                raw = self.seed()
                prior_at = raw.captured_at_extruder
                failed = raw.model_copy(update={"plc_source_usable": False})
                before = self.state()
                self.service._compose_data(failed, prior_at + delta - .1)
                self.assertEqual(self.state(), before)
                recovered_at = prior_at + delta
                recovered = raw.model_copy(update={"captured_at_extruder": recovered_at})
                self.service._compose_data(recovered, recovered_at)
                self.assertEqual(self.store.get().valid, not reset)
                if reset:
                    self.assertEqual(self.store.get().source, "auto_downtime_threshold")
                self.assertEqual(self.service.operator_metadata_last_normal_sample_at, recovered_at)

    def test_manual_edit_during_outage_survives_recovery_without_valid_reset_trigger(self):
        raw = self.seed()
        failed = raw.model_copy(update={"Count": 0, "plc_source_usable": False})
        self.store.update(OperatorMetadataUpdate(product_no="10003", operator_mold_no="3"))
        before = self.state()
        self.service._compose_data(failed, raw.captured_at_extruder)
        self.assertEqual(self.state(), before)
        recovered = self.cycle(MelsecSocket())
        composed = self.service._compose_data(recovered, recovered.captured_at_extruder)
        self.assertEqual(composed.Product_No_operator, "10003")
        self.assertEqual(self.store._path.read_bytes(), before[1])


if __name__ == "__main__":
    unittest.main()
