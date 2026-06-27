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
        self.assertEqual(decision.changeover_candidate_id, "")

    def test_low_count_high_motion_maps_to_setup_alignment_candidate(self) -> None:
        cases = (
            ProcessPhaseInput(speed=1.0, press=35.0, count=0, extruder_process_state_online="unknown"),
            ProcessPhaseInput(speed=0.0, press=35.0, count=2, extruder_process_state_online="extruding"),
        )
        for case in cases:
            with self.subTest(case=case):
                decision = derive_process_phase_candidate(case)

                self.assertEqual(decision.process_phase_candidate, "setup_alignment_candidate")
                self.assertEqual(decision.changeover_candidate_id, "")

    def test_count_three_high_motion_maps_to_production_stabilizing(self) -> None:
        decision = derive_process_phase_candidate(
            ProcessPhaseInput(speed=1.0, press=35.0, count=3, extruder_process_state_online="extruding")
        )

        self.assertEqual(decision.process_phase_candidate, "production_stabilizing")
        self.assertEqual(decision.changeover_candidate_id, "")

    def test_count_four_high_motion_can_promote_to_production_stable(self) -> None:
        decision = derive_process_phase_candidate(
            ProcessPhaseInput(speed=1.0, press=35.0, count=4, extruder_process_state_online="extruding")
        )

        self.assertEqual(decision.process_phase_candidate, "production_stable")
        self.assertEqual(decision.changeover_candidate_id, "")

    def test_recent_production_stop_maps_to_possible_pre_changeover_hold(self) -> None:
        decision = derive_process_phase_candidate(
            ProcessPhaseInput(
                speed=0.0,
                press=0.0,
                count=12,
                extruder_process_state_online="stopped",
                count_held_sec=30.0,
                recent_production_motion=True,
            )
        )

        self.assertEqual(decision.process_phase_candidate, "possible_pre_changeover_hold")
        self.assertEqual(decision.changeover_candidate_id, "")

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
