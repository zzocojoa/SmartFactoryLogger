"""C2: acquisition-time PLC proof through actual transport, state, queue and CSV."""
import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from backend.FacilityData import service as service_module
from backend.FacilityData.drivers import real_plc
from backend.FacilityData.freshness import clock_domain_id
from backend.FacilityData.process_phase import ProcessPhaseInput, derive_process_phase_candidate
from backend.FacilityData.schemas import FactoryData, OperatorMetadataUpdate
from backend.tests.test_temperature_followup import PlcFixture, MelsecSocket
from backend.tests.test_temperature_clock_service import IndependentClock


PROOF_FIELDS = ('plc_source_completed_monotonic', 'plc_sample_monotonic', 'plc_clock_domain_id')


class PlcSourceClockTests(PlcFixture):
    def setUp(self):
        super().setUp()
        self.clock = IndependentClock()
        fake_time = SimpleNamespace(time=self.clock.time, monotonic=self.clock.monotonic)
        self.stack.enter_context(patch.object(real_plc, 'time', fake_time))
        self.stack.enter_context(patch.object(service_module, 'time', fake_time))
        self.stack.enter_context(patch.object(real_plc.config, 'INTERVAL_SEC', .25))
        self.driver.ext_timeout = .5  # Existing grace formula -> 1s in this fixture.

    def state(self):
        paths = [self.driver.logic.state_path, self.store._path, self.service.operator_metadata_runtime_state_path]
        return (vars(self.driver.logic).copy(), self.store.get().model_dump(),
                self.service.operator_metadata_previous_count, self.service.operator_metadata_last_normal_sample_at,
                self.service.operator_metadata_last_state_write_at, self.service._process_operator_context,
                [(p.read_bytes(), p.stat().st_mtime_ns) if p.exists() else None for p in paths])

    def test_old_complete_source_rollback_through_temperature_and_automatic_state(self):
        self.store.update(OperatorMetadataUpdate(product_no='10001', operator_mold_no='1'))
        normal = self.cycle(MelsecSocket())
        self.service._compose_data(normal, self.clock.wall)
        stamp = datetime.now(timezone.utc)
        self.logger._derive_process_phase_decision(normal.model_copy(update={'process_phase_candidate':'die_change_candidate'}), stamp, 1)
        candidate = self.logger._process_phase_runtime_state.active_changeover_candidate_id
        before = self.state()
        self.clock.advance(10.5, -10)
        raw = self.driver.read_data()
        self.assertEqual((raw.Count, raw.Speed, raw.Press), (20, 1, 30))
        self.assertFalse(raw.plc_source_error)  # No new read and no newly recorded error.
        self.assertAlmostEqual(raw.plc_source_age_ms, 10500)
        self.assertFalse(raw.plc_source_usable)
        self.assertEqual((raw.Die_ID, raw.Billet_Cycle_ID), ('', ''))
        composed = self.service._compose_data(raw, self.clock.wall)
        self.assertFalse(composed.plc_source_usable)
        self.assertEqual(self.state(), before)
        for kind in ['valid', 'under_range', 'over_range']:
            row = self.row(raw, kind, external='die_change_candidate')
            self.assertEqual(row['process_phase_candidate'], 'unknown')
            self.assertEqual(row['temperature_output_status'], kind)
            self.assertEqual(row['temperature_expectedness_candidate'], '' if kind=='valid' else 'unexpected_candidate' if kind=='over_range' else 'unknown')
            self.assertEqual(row['changeover_candidate_id'], '')
        self.assertEqual(self.logger._process_phase_runtime_state.active_changeover_candidate_id, candidate)

    def test_fresh_grace_boundary_and_forward_backward_wall(self):
        for elapsed in [0, .999, 1, 1.001]:
            for jump in [-60, 0, 60]:
                with self.subTest(elapsed=elapsed, jump=jump):
                    self.cycle(MelsecSocket())
                    self.clock.advance(elapsed, jump)
                    raw = self.driver.read_data()
                    self.assertAlmostEqual(raw.plc_source_age_ms, elapsed*1000, places=5)
                    self.assertEqual(raw.plc_source_usable, elapsed<=1)
                    self.assertEqual(self.service._plc_source_at_sample(raw, self.clock.wall)[1], elapsed<=1)

    def test_fresh_adoption_survives_service_writer_delay_copy_and_queue(self):
        raw = self.cycle(MelsecSocket())
        self.clock.advance(.2)
        adopted = self.driver.read_data()
        original_proof = [getattr(adopted, key) for key in PROOF_FIELDS]
        self.clock.advance(100, -60)
        composed = self.service._compose_data(adopted.model_copy(deep=True), self.clock.wall)
        self.assertTrue(composed.plc_source_usable)
        self.assertAlmostEqual(composed.plc_source_age_ms, 200, places=5)
        self.assertEqual([getattr(composed, key) for key in PROOF_FIELDS], original_proof)
        self.logger.running = True
        self.logger.enqueue(composed)
        queued = self.logger.queue.get_nowait()
        self.clock.advance(1000, 60)
        self.assertEqual([getattr(queued, key) for key in PROOF_FIELDS], original_proof)
        phase = self.logger._derive_process_phase_decision(queued, datetime.now(timezone.utc), 1)
        self.assertEqual(phase.process_phase_candidate, 'production_stable')
        self.assertFalse(self.driver.read_data().plc_source_usable)  # A new adoption ages the old source.
        public = json.loads(raw.model_dump_json())
        self.assertTrue(all(key not in public for key in PROOF_FIELDS))
        replay = FactoryData.model_validate(public)
        self.assertFalse(self.service._plc_source_at_sample(replay, self.clock.wall)[1])
        self.assertEqual(self.row(replay, 'valid')['process_phase_candidate'], 'unknown')

    def test_invalid_proof_cannot_bypass_service_helpers_or_external_phase(self):
        self.store.update(OperatorMetadataUpdate(product_no='10001', operator_mold_no='1'))
        raw = self.cycle(MelsecSocket())
        self.service._compose_data(raw, self.clock.wall)
        before = self.state()
        changes = [{field:value} for field in PROOF_FIELDS[:2] for value in [None, True, float('nan'), float('inf'), -float('inf'), -1, '1000']]
        changes += [{'plc_clock_domain_id':v} for v in [None, '', True, 'foreign-process']]
        changes += [{'plc_sample_monotonic':999}, {'plc_source_usable':False}]
        for change in changes:
            with self.subTest(change=change):
                invalid = raw.model_copy(update={'Count':0, 'process_phase_candidate':'die_change_candidate', **change})
                self.assertFalse(self.service._plc_source_at_sample(invalid, self.clock.wall)[1])
                self.service._apply_operator_metadata_auto_reset(invalid, self.clock.wall)
                self.service._persist_operator_metadata_runtime_state(sample_at_sec=self.clock.wall, raw_data=invalid, force=True)
                self.assertEqual(self.service._derive_metadata_process_state_candidate(invalid, self.store.get(), self.clock.wall), 'unknown')
                self.assertEqual(self.state(), before)
                self.assertEqual(self.row(invalid)['process_phase_candidate'], 'unknown')
        direct = ProcessPhaseInput(plc_source_age_ms=0, plc_source_freshness_threshold_ms=1000,
                                   plc_source_error=False, plc_source_usable=True, count=20, speed=1, press=30)
        self.assertEqual(derive_process_phase_candidate(direct).process_phase_candidate, 'unknown')

    def test_skip_keeps_source_clocks_partial_then_complete_recovery_and_manual_edit(self):
        self.cycle(MelsecSocket())
        self.clock.advance(10.5, -10)
        self.assertFalse(self.driver.read_data().plc_source_usable)
        partial = self.cycle(MelsecSocket('D1500'))
        source_at = partial.plc_source_completed_monotonic
        for _ in range(5):
            self.clock.advance(.2)
            skipped = self.cycle()
            self.assertEqual(skipped.plc_source_completed_monotonic, source_at)
            self.assertEqual(skipped.captured_at_extruder, partial.captured_at_extruder)
            self.assertFalse(skipped.plc_source_usable)
        self.store.update(OperatorMetadataUpdate(product_no='10002', operator_mold_no='2'))
        recovered = self.cycle(MelsecSocket())
        self.assertTrue(recovered.plc_source_usable)
        self.service._compose_data(recovered, self.clock.wall)
        self.assertEqual(self.store.get().product_no, '10002')
        for count in [0, 1, 2]:
            self.driver._update_ext_snapshot({'Count':count, 'Speed':0, 'Press':0}, self.clock.wall)
            raw = self.driver.read_data()
            self.assertTrue(raw.plc_source_usable)
            self.assertEqual(self.row(raw)['process_phase_candidate'], 'setup_candidate')
        optional = self.cycle(MelsecSocket('D0010'))
        self.assertTrue(optional.plc_source_usable)

    def test_invalid_source_clock_does_not_drop_entire_temperature_sample(self):
        for value in [True, float('nan'), float('inf'), -1]:
            with self.subTest(value=value):
                with patch.object(real_plc.time, 'monotonic', return_value=value):
                    self.driver._update_ext_snapshot({'Count':20, 'Speed':1, 'Press':30}, self.clock.wall)
                    raw = self.driver.read_data()
                self.assertFalse(raw.plc_source_usable)
                self.assertEqual(self.row(raw, 'valid')['Temperature'], '500')
        for field in PROOF_FIELDS[:2]:
            for value in [True, float('nan'), float('inf')]:
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    FactoryData(Time='', **{field:value})

    def test_invalid_audit_timestamp_cannot_mutate_runtime_state(self):
        self.store.update(OperatorMetadataUpdate(product_no='10001', operator_mold_no='1'))
        raw = self.cycle(MelsecSocket())
        self.service._compose_data(raw, self.clock.wall)
        before = self.state()
        for stamp in [True, float('nan'), float('inf'), -float('inf')]:
            with self.subTest(stamp=stamp):
                zero = raw.model_copy(update={'Count':0})
                self.assertFalse(self.service._plc_source_at_sample(zero, stamp)[1])
                self.service._apply_operator_metadata_auto_reset(zero, stamp)
                self.service._persist_operator_metadata_runtime_state(sample_at_sec=stamp, raw_data=zero, force=True)
                self.assertEqual(self.state(), before)
                self.assertFalse(self.driver._is_ext_snapshot_usable(stamp, None, self.clock.wall,
                    source_completed_monotonic=raw.plc_source_completed_monotonic,
                    sample_monotonic=raw.plc_sample_monotonic, source_clock_domain=raw.plc_clock_domain_id))

    def test_atomic_payload_and_proof_generation(self):
        ready, consumed = threading.Event(), threading.Event()
        failures = []
        def publish():
            try:
                for seq in range(1, 21):
                    self.clock.wall = 1_800_000_000 + seq
                    self.clock.mono = 1000 + seq
                    self.driver._update_ext_snapshot({'Count':seq, 'Speed':1, 'Press':30}, self.clock.wall)
                    ready.set()
                    if not consumed.wait(1):
                        raise AssertionError('consumer did not acknowledge')
                    consumed.clear()
            except BaseException as exc:
                failures.append(exc)
                ready.set()
        worker = threading.Thread(target=publish)
        worker.start()
        try:
            for seq in range(1, 21):
                self.assertTrue(ready.wait(1))
                ready.clear()
                try:
                    raw = self.driver.read_data()
                    self.assertEqual((raw.Count, raw.captured_at_extruder, raw.plc_source_completed_monotonic),
                                     (seq, 1_800_000_000+seq, 1000+seq))
                    self.assertEqual(raw.plc_clock_domain_id, clock_domain_id())
                finally:
                    consumed.set()
        finally:
            consumed.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(failures)
