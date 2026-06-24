import unittest

from backend.FacilityData.process_phase import ProcessPhaseInput, derive_process_phase_candidate


class ProcessPhaseCandidateTests(unittest.TestCase):
    def test_extruding_maps_to_production_stable_without_spot_input(self) -> None:
        decision = derive_process_phase_candidate(
            ProcessPhaseInput(speed=5.0, press=35.0, count=12, extruder_process_state_online="extruding")
        )

        self.assertEqual(decision.process_phase_candidate, "production_stable")
        self.assertEqual(decision.changeover_candidate_id, "")

    def test_low_count_low_motion_maps_to_setup_candidate(self) -> None:
        decision = derive_process_phase_candidate(
            ProcessPhaseInput(speed=0.0, press=0.0, count=1, extruder_process_state_online="unknown")
        )

        self.assertEqual(decision.process_phase_candidate, "setup_candidate")
        self.assertTrue(decision.changeover_candidate_id.startswith("chg_"))

    def test_changeover_candidate_does_not_require_spot_status(self) -> None:
        decision = derive_process_phase_candidate(
            ProcessPhaseInput(
                speed=0.0,
                press=0.0,
                count=40,
                extruder_process_state_online="changeover_candidate",
                product_no="100",
                mold_no="7",
            )
        )

        self.assertEqual(decision.process_phase_candidate, "changeover_candidate")


if __name__ == "__main__":
    unittest.main()
