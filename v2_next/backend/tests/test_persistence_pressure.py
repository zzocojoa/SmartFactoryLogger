from dataclasses import replace
import threading
import time
import unittest

from backend.FacilityData.persistence_pressure import (
    StoragePressureController, StoragePressureMonitor, StoragePressureSample,
)


class StoragePressureTests(unittest.TestCase):
    def sample(self, **changes):
        baseline = StoragePressureSample("image_jpeg", 1, "destination-A", True, "available",
                                         count_limit=128, byte_limit=128 * 1024**2, spool_limit=64 * 1024**2)
        return replace(baseline, **changes)

    def test_unknown_active_sink_blocks_with_an_empty_queue(self):
        sample = self.sample(availability="unknown")
        decision = StoragePressureController().evaluate([sample], now_monotonic=100.0)
        self.assertEqual(decision.state, "PERSISTENCE_BLOCKED")
        self.assertEqual(decision.current_storage_availability, "unknown")
        self.assertIn("storage_unknown", decision.reasons)
        excluded = StoragePressureController().evaluate([replace(sample, enabled=False)], now_monotonic=100.0)
        self.assertEqual(excluded.state, "NORMAL")
        self.assertEqual(excluded.current_storage_availability, "available")

    def test_pressure_uses_capacity_and_stage_overdue(self):
        baseline = self.sample(count_limit=100, byte_limit=100, spool_limit=100,
                               pending_count=1, oldest_pending_monotonic=0.0, stage_due_monotonic=101.0)
        cases = (
            ({"pending_count": 80}, "PRESSURED", "occupancy_high"),
            ({"pending_count": 79}, "NORMAL", None),
            ({"pending_count": 100}, "PERSISTENCE_BLOCKED", "budget_exhausted"),
            ({"pending_bytes": 80}, "PRESSURED", "occupancy_high"),
            ({"pending_bytes": 101}, "PERSISTENCE_BLOCKED", "budget_exhausted"),
            ({"spool_bytes": 80}, "PRESSURED", "occupancy_high"),
            ({"spool_bytes": 100}, "PERSISTENCE_BLOCKED", "budget_exhausted"),
            ({"stage_due_monotonic": 98.0}, "PRESSURED", "stage_overdue"),
            ({"stage_due_monotonic": 98.01}, "NORMAL", None),
            ({"manual_recovery_required": True}, "PERSISTENCE_BLOCKED", "manual_recovery"),
            ({"writer_alive": False}, "PERSISTENCE_BLOCKED", "writer_stopped"),
        )
        for changes, expected, reason in cases:
            with self.subTest(changes=changes):
                decision = StoragePressureController().evaluate([replace(baseline, **changes)], now_monotonic=100.0)
                self.assertEqual(decision.state, expected)
                self.assertEqual(decision.oldest_pending_age_seconds, 100.0)
                self.assertEqual(decision.max_stage_overdue_seconds,
                                 max(0.0, 100.0 - changes.get("stage_due_monotonic", 101.0)))
                if reason:
                    self.assertIn(reason, decision.reasons)
        scheduled = StoragePressureController().evaluate([baseline], now_monotonic=100.0)
        self.assertEqual(scheduled.state, "NORMAL")
        self.assertEqual(scheduled.max_stage_overdue_seconds, 0.0)
        self.assertEqual(scheduled.max_occupancy_ratio, 0.01)

    def test_normal_recovery_requires_three_control_ticks_with_continuing_pending(self):
        controller = StoragePressureController()
        healthy = self.sample(count_limit=100, pending_count=1, oldest_pending_monotonic=0.0,
                              stage_due_monotonic=200.0)
        self.assertEqual(controller.evaluate([replace(healthy, availability="unknown")], now_monotonic=100.0).state,
                         "PERSISTENCE_BLOCKED")
        first = controller.evaluate([healthy], now_monotonic=101.0)
        self.assertEqual(first.state, "PRESSURED")
        self.assertEqual(first.normal_confirmations, 1)
        for now in (101.0, 101.1, 101.5, 101.999):
            self.assertEqual(controller.evaluate([healthy], now_monotonic=now), first)
        self.assertEqual(controller.evaluate([healthy], now_monotonic=102.0).normal_confirmations, 2)
        normal = controller.evaluate([healthy], now_monotonic=103.0)
        self.assertEqual(normal.state, "NORMAL")
        self.assertEqual(normal.normal_confirmations, 3)
        self.assertEqual(normal.oldest_pending_age_seconds, 103.0)

        timeline = (
            (104.0, replace(healthy, pending_count=80), "PRESSURED", 0),
            (105.0, replace(healthy, pending_count=60), "PRESSURED", 0),
            (106.0, healthy, "PRESSURED", 1),
            (107.0, replace(healthy, stage_due_monotonic=106.0), "PRESSURED", 0),
            (108.0, healthy, "PRESSURED", 1),
            (109.0, replace(healthy, pending_recovery=1), "PRESSURED", 0),
            (110.0, healthy, "PRESSURED", 1),
            (111.0, healthy, "PRESSURED", 2),
            (112.0, healthy, "NORMAL", 3),
        )
        for now, sample, expected, count in timeline:
            with self.subTest(now=now):
                decision = controller.evaluate([sample], now_monotonic=now)
                self.assertEqual(decision.state, expected)
                self.assertEqual(decision.normal_confirmations, count)

    def test_foreign_clock_or_missing_deadline_blocks_recovery(self):
        valid = self.sample(pending_count=1, oldest_pending_monotonic=99.0, stage_due_monotonic=100.0)
        for changes in ({"clock_domain": "other-process"}, {"stage_due_monotonic": None},
                        {"oldest_pending_monotonic": None}, {"stage_due_monotonic": float("nan")}):
            with self.subTest(changes=changes):
                decision = StoragePressureController().evaluate([replace(valid, **changes)], now_monotonic=100.0)
                self.assertEqual(decision.state, "PERSISTENCE_BLOCKED")
                self.assertIsNone(decision.max_stage_overdue_seconds)
                self.assertIsNone(decision.oldest_pending_age_seconds)
                self.assertIn("pending_clock_unavailable", decision.reasons)
        normal = StoragePressureController().evaluate([valid], now_monotonic=100.0)
        self.assertEqual(normal.state, "NORMAL")
        self.assertEqual(normal.max_stage_overdue_seconds, 0.0)
        self.assertEqual(normal.oldest_pending_age_seconds, 1.0)

    def test_monitor_evaluates_without_ui_and_owns_one_thread(self):
        first_sample = threading.Event()
        sample_lock = threading.Lock()
        current = self.sample(availability="unknown")
        calls = []

        def sample_provider():
            with sample_lock:
                calls.append((time.monotonic(), threading.get_ident()))
                result = current
            first_sample.set()
            return [result]

        monitor = StoragePressureMonitor(sample_provider)
        try:
            monitor.start()
            self.assertTrue(first_sample.wait(2.0), "monitor never sampled without a UI request")
            deadline = time.monotonic() + 2.0
            while "storage_unknown" not in monitor.snapshot().reasons and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIn("storage_unknown", monitor.snapshot().reasons)
            self.assertFalse(monitor.start(), "a second evaluator thread was started")
            with sample_lock:
                current = replace(current, availability="available")
                count = len(calls)
            for _ in range(100):
                self.assertEqual(monitor.snapshot().state, "PERSISTENCE_BLOCKED")
            with sample_lock:
                self.assertEqual(len(calls), count, "snapshot reads advanced the controller")
            started = time.monotonic()
            deadline = started + 5.0
            while monitor.snapshot().state != "NORMAL" and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(monitor.snapshot().state, "NORMAL")
            self.assertGreaterEqual(time.monotonic() - started, 2.0)
            with sample_lock:
                self.assertEqual(len({thread for _, thread in calls}), 1)
                self.assertNotEqual(calls[0][1], threading.get_ident())
                self.assertTrue(all(second[0] - first[0] >= 0.99 for first, second in zip(calls, calls[1:])))
        finally:
            self.assertTrue(monitor.stop(timeout=2.0))
        with sample_lock:
            stopped_count = len(calls)
        time.sleep(1.1)
        with sample_lock:
            self.assertEqual(len(calls), stopped_count)

    def test_monitor_failure_and_stop_do_not_retain_normal_decision(self):
        fail = threading.Event()
        failed = threading.Event()

        def sample_provider():
            if fail.is_set():
                failed.set()
                raise OSError("injected status sampling failure")
            return [self.sample()]

        def wait_for(monitor, state):
            deadline = time.monotonic() + 5.0
            while monitor.snapshot().state != state and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(monitor.snapshot().state, state)

        monitor = StoragePressureMonitor(sample_provider)
        try:
            self.assertTrue(monitor.start())
            wait_for(monitor, "NORMAL")
            fail.set()
            self.assertTrue(failed.wait(2.0))
            wait_for(monitor, "PERSISTENCE_BLOCKED")
            self.assertIn("sampling_failed", monitor.snapshot().reasons)
            count = monitor.snapshot().sampling_failure_count
            self.assertGreaterEqual(count, 1)
            fail.clear()
            restored = time.monotonic()
            wait_for(monitor, "NORMAL")
            self.assertGreaterEqual(time.monotonic() - restored, 2.0)
            self.assertEqual(monitor.snapshot().sampling_failure_count, count)
        finally:
            self.assertTrue(monitor.stop(timeout=2.0))
        self.assertEqual(monitor.snapshot().state, "PERSISTENCE_BLOCKED")
        self.assertIn("monitor_stopped", monitor.snapshot().reasons)
        self.assertGreaterEqual(monitor.snapshot().sampling_failure_count, 1)

    def test_disabled_generation_remains_active_until_its_pending_drains(self):
        controller = StoragePressureController()
        old = self.sample(enabled=False, availability="blocked", pending_count=1,
                          oldest_pending_monotonic=90.0, stage_due_monotonic=100.0)
        current = self.sample(config_generation=2, destination_key="destination-B")
        self.assertEqual(controller.evaluate([old, current], now_monotonic=100.0).state, "PERSISTENCE_BLOCKED")
        drained = replace(old, pending_count=0)
        for now, expected in ((101.0, "PRESSURED"), (102.0, "PRESSURED"), (103.0, "NORMAL")):
            self.assertEqual(controller.evaluate([drained, current], now_monotonic=now).state, expected)
        changed = replace(current, config_generation=3, destination_key="destination-C", availability="unknown")
        self.assertEqual(controller.evaluate([current, changed], now_monotonic=104.0).state, "PERSISTENCE_BLOCKED")

    def test_monitor_stop_timeout_does_not_spawn_a_replacement(self):
        block = threading.Event()
        entered = threading.Event()
        release = threading.Event()

        def sample_provider():
            if block.is_set():
                entered.set()
                release.wait(5.0)
            return [self.sample()]

        monitor = StoragePressureMonitor(sample_provider)
        try:
            self.assertTrue(monitor.start())
            deadline = time.monotonic() + 2.0
            while monitor.snapshot().state != "NORMAL" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(monitor.snapshot().state, "NORMAL")
            block.set()
            self.assertTrue(entered.wait(2.0))
            self.assertFalse(monitor.stop(timeout=0.01))
            self.assertEqual(monitor.snapshot().state, "PERSISTENCE_BLOCKED")
            self.assertIn("monitor_stopping", monitor.snapshot().reasons)
            self.assertFalse(monitor.start(), "a live sampling owner was replaced after a timeout")
        finally:
            release.set()
            self.assertTrue(monitor.stop(timeout=2.0))
        self.assertIn("monitor_stopped", monitor.snapshot().reasons)


if __name__ == "__main__":
    unittest.main()
