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


if __name__ == "__main__":
    unittest.main()
