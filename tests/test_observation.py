# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Read-only controller safety tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hydra_umc_sdk.bridge_contract import MachineState
from hydra_umc_bridge_laser.observation import snapshot_from_fresh_mapping, snapshot_from_mapping


class LaserObservationTests(unittest.TestCase):
    def test_complete_idle_safety_evidence_maps_to_idle(self):
        snapshot = snapshot_from_mapping({"state": "idle", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True})
        self.assertEqual(snapshot.machine_state(), MachineState.IDLE)

    def test_missing_or_string_safeguards_fail_closed(self):
        self.assertEqual(snapshot_from_mapping({"state": "IDLE"}).machine_state(), MachineState.SAFE_STOP)
        self.assertEqual(snapshot_from_mapping({"state": "IDLE", "key_enabled": "true", "enclosure_closed": True, "interlock_healthy": True}).machine_state(), MachineState.SAFE_STOP)

    def test_non_mapping_input_never_crashes_or_arms(self):
        self.assertEqual(snapshot_from_mapping(None).machine_state(), MachineState.SAFE_STOP)

    def test_unknown_state_stays_offline_when_all_safeguards_are_true(self):
        self.assertEqual(snapshot_from_mapping({"state": "mystery", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True}).machine_state(), MachineState.OFFLINE)

    def test_stale_or_invalid_interlock_evidence_fails_closed(self):
        payload = {"state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True, "observed_at_ms": 9_500}
        self.assertEqual(snapshot_from_fresh_mapping(payload, now_ms=10_000, max_age_ms=500).machine_state(), MachineState.IDLE)
        self.assertEqual(snapshot_from_fresh_mapping(payload, now_ms=10_001, max_age_ms=500).machine_state(), MachineState.SAFE_STOP)
        self.assertEqual(snapshot_from_fresh_mapping({**payload, "observed_at_ms": 10_001}, now_ms=10_000, max_age_ms=500).machine_state(), MachineState.SAFE_STOP)
        self.assertEqual(snapshot_from_fresh_mapping({"state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True}, now_ms=10_000, max_age_ms=500).machine_state(), MachineState.SAFE_STOP)

    def test_offline_cli_reads_saved_evidence_without_laser_connection(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            evidence.write_text(json.dumps({"state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True}), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(root / "tools" / "inspect_controller_evidence.py"), str(evidence)], text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["machine_state"], "IDLE")


if __name__ == "__main__":
    unittest.main()
