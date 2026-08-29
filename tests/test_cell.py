# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Laser cell boundary tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
import unittest
from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState
from hydra_umc_bridge_laser import LaserCellBridge, LaserSafetySnapshot


def job(phase=JobPhase.LOAD):
    return BridgeJob("laser-1", "laser-key-1", "laser", phase, MachineState.IDLE, {})


class LaserCellTests(unittest.TestCase):
    def test_safe_idle_laser_allows_auxiliary_load_plan(self):
        decision = LaserCellBridge().plan(job(), CellState.READY, LaserSafetySnapshot("IDLE", True, True, True))
        self.assertTrue(decision.allowed)

    def test_open_enclosure_fails_safe(self):
        decision = LaserCellBridge().plan(job(), CellState.READY, LaserSafetySnapshot("IDLE", True, False, True))
        self.assertFalse(decision.allowed)

    def test_abort_remains_available_when_interlock_has_failed(self):
        decision = LaserCellBridge().plan(job(JobPhase.ABORT), CellState.FAULT, LaserSafetySnapshot("FAULT", True, True, False))
        self.assertTrue(decision.allowed)

    def test_non_text_controller_state_fails_safe_instead_of_crashing(self):
        state = LaserSafetySnapshot(None, True, True, True).machine_state()  # type: ignore[arg-type]
        self.assertEqual(state, MachineState.OFFLINE)


if __name__ == "__main__": unittest.main()
