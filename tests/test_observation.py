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
from hydra_umc_bridge_laser.observation import (
    snapshot_from_fresh_mapping,
    snapshot_from_independently_observed_mapping,
    snapshot_from_mapping,
)


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

    def test_independent_observation_accepts_a_genuinely_new_reading_from_the_expected_origin(self):
        payload = {
            "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True,
            "observed_at_ms": 10_000, "origin": "gpio-safety-daemon", "generation": 5,
        }
        result = snapshot_from_independently_observed_mapping(
            payload, now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=None,
        )
        self.assertEqual(result.snapshot.machine_state(), MachineState.IDLE)
        self.assertEqual(result.generation, 5)

    def test_independent_observation_rejects_the_wrong_origin(self):
        payload = {
            "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True,
            "observed_at_ms": 10_000, "origin": "some-other-process", "generation": 5,
        }
        result = snapshot_from_independently_observed_mapping(
            payload, now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=None,
        )
        self.assertEqual(result.snapshot.machine_state(), MachineState.SAFE_STOP)
        self.assertIsNone(result.generation)

    def test_independent_observation_rejects_a_missing_or_empty_origin(self):
        for origin in (None, "", 42, True):
            payload = {
                "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True,
                "observed_at_ms": 10_000, "origin": origin, "generation": 5,
            }
            result = snapshot_from_independently_observed_mapping(
                payload, now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=None,
            )
            self.assertEqual(result.snapshot.machine_state(), MachineState.SAFE_STOP, f"origin={origin!r}")
            self.assertIsNone(result.generation, f"origin={origin!r}")

    def test_independent_observation_rejects_a_replay_that_does_not_advance_the_generation(self):
        payload = {
            "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True,
            "observed_at_ms": 10_000, "origin": "gpio-safety-daemon", "generation": 5,
        }
        # Same generation already accepted before - a real replay, no
        # matter how fresh this capture's own timestamp claims to be.
        same_gen = snapshot_from_independently_observed_mapping(
            payload, now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=5,
        )
        self.assertEqual(same_gen.snapshot.machine_state(), MachineState.SAFE_STOP)
        self.assertIsNone(same_gen.generation)

        # An OLDER generation than one already accepted is rejected too.
        older_gen = snapshot_from_independently_observed_mapping(
            {**payload, "generation": 4}, now_ms=10_000, max_age_ms=500,
            expected_origin="gpio-safety-daemon", min_generation=5,
        )
        self.assertEqual(older_gen.snapshot.machine_state(), MachineState.SAFE_STOP)
        self.assertIsNone(older_gen.generation)

        # A genuinely newer generation is accepted.
        newer_gen = snapshot_from_independently_observed_mapping(
            {**payload, "generation": 6}, now_ms=10_000, max_age_ms=500,
            expected_origin="gpio-safety-daemon", min_generation=5,
        )
        self.assertEqual(newer_gen.snapshot.machine_state(), MachineState.IDLE)
        self.assertEqual(newer_gen.generation, 6)

    def test_independent_observation_rejects_a_non_integer_or_boolean_generation(self):
        for generation in (None, "5", 5.0, True, -1):
            payload = {
                "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True,
                "observed_at_ms": 10_000, "origin": "gpio-safety-daemon", "generation": generation,
            }
            result = snapshot_from_independently_observed_mapping(
                payload, now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=None,
            )
            self.assertEqual(result.snapshot.machine_state(), MachineState.SAFE_STOP, f"generation={generation!r}")
            self.assertIsNone(result.generation, f"generation={generation!r}")

    def test_independent_observation_still_fails_closed_on_a_stale_or_already_unhealthy_capture(self):
        stale = snapshot_from_independently_observed_mapping(
            {
                "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": True,
                "observed_at_ms": 9_000, "origin": "gpio-safety-daemon", "generation": 5,
            },
            now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=None,
        )
        self.assertEqual(stale.snapshot.machine_state(), MachineState.SAFE_STOP)
        self.assertIsNone(stale.generation)

        already_unhealthy = snapshot_from_independently_observed_mapping(
            {
                "state": "IDLE", "key_enabled": True, "enclosure_closed": True, "interlock_healthy": False,
                "observed_at_ms": 10_000, "origin": "gpio-safety-daemon", "generation": 5,
            },
            now_ms=10_000, max_age_ms=500, expected_origin="gpio-safety-daemon", min_generation=None,
        )
        self.assertEqual(already_unhealthy.snapshot.machine_state(), MachineState.SAFE_STOP)
        self.assertIsNone(already_unhealthy.generation)

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
