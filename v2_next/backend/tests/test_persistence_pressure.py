from dataclasses import replace
import unittest

from backend.FacilityData.persistence_pressure import StoragePressureController, StoragePressureSample


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


if __name__ == "__main__":
    unittest.main()
