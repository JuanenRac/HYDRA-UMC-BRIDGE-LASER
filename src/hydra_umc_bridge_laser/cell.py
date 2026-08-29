# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Laser cell boundary
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Reject cell work unless external laser safeguards report a safe idle state."""

from __future__ import annotations

from dataclasses import dataclass

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, GateDecision, MachineState, evaluate_job


@dataclass(frozen=True)
class LaserSafetySnapshot:
    controller_state: str
    key_enabled: bool
    enclosure_closed: bool
    interlock_healthy: bool

    def machine_state(self) -> MachineState:
        if not self.key_enabled or not self.enclosure_closed or not self.interlock_healthy:
            return MachineState.SAFE_STOP
        if not isinstance(self.controller_state, str):
            return MachineState.OFFLINE
        state = self.controller_state.upper()
        if state == "IDLE":
            return MachineState.IDLE
        if state in {"RUN", "RUNNING", "PAUSED"}:
            return MachineState.RUNNING
        if state in {"FAULT", "ALARM", "ERROR"}:
            return MachineState.FAULT
        return MachineState.OFFLINE


class LaserCellBridge:
    """Coordinates only external auxiliaries; it cannot arm or fire a laser."""

    def plan(self, job: BridgeJob, cell_state: CellState, laser: LaserSafetySnapshot) -> GateDecision:
        observed = BridgeJob(job.job_id, job.idempotency_key, job.source, job.phase, laser.machine_state(), job.parameters)
        return evaluate_job(observed, cell_state)
