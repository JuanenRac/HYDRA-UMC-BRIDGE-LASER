# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Real MQTT transport tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Tests LaserMqttBridge's real topic dispatch against fake GPIO line
readers - no real MQTT broker or GPIO chip required, same "small
Protocol + fake" pattern test_gpio_safety.py already uses."""

import json
import unittest

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_bridge_laser import GpioSafetyLines, LaserMqttBridge
from hydra_umc_bridge_laser.mqtt_transport import TOPIC_PREFIX


class FakeLine:
    def __init__(self, value: bool = True):
        self.value = value

    def read(self) -> bool:
        return self.value


def bridge(key=True, enclosure=True, interlock=True, controller_state="IDLE", cell_state=CellState.READY):
    lines = GpioSafetyLines(FakeLine(key), FakeLine(enclosure), FakeLine(interlock))
    return LaserMqttBridge(lines, lambda: controller_state, lambda: cell_state)


def job(phase=JobPhase.LOAD, machine_state=MachineState.IDLE):
    return BridgeJob("job-1", "key-1", "orchestrator", phase, machine_state, {})


class TopicRoutingTests(unittest.TestCase):
    def test_unknown_prefix_is_ignored(self):
        self.assertEqual(bridge().handle_message("some/other/topic", b""), [])

    def test_unrecognised_cmd_topic_is_ignored_not_an_error(self):
        self.assertEqual(bridge().handle_message(f"{TOPIC_PREFIX}cmd/fire", b""), [])


class StatusCommandTests(unittest.TestCase):
    def test_status_publishes_retained_state_with_derived_machine_state(self):
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/status", b"")
        self.assertEqual(len(publishes), 1)
        publish = publishes[0]
        self.assertEqual(publish.topic, f"{TOPIC_PREFIX}state")
        self.assertTrue(publish.retain)
        payload = json.loads(publish.payload)
        self.assertEqual(payload["machine_state"], "IDLE")

    def test_a_single_false_safeguard_is_reflected_as_safe_stop(self):
        publishes = bridge(enclosure=False).handle_message(f"{TOPIC_PREFIX}cmd/status", b"")
        payload = json.loads(publishes[0].payload)
        self.assertEqual(payload["machine_state"], "SAFE_STOP")
        self.assertFalse(payload["enclosure_closed"])


class JobCommandTests(unittest.TestCase):
    def test_a_valid_job_against_a_ready_idle_cell_is_allowed(self):
        b = bridge()
        publishes = b.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode("utf-8"))
        self.assertEqual(publishes[0].topic, f"{TOPIC_PREFIX}cmd/job/result")
        self.assertTrue(json.loads(publishes[0].payload)["allowed"])

    def test_a_job_is_rejected_when_a_safeguard_is_open(self):
        b = bridge(key=False)
        publishes = b.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode("utf-8"))
        decision = json.loads(publishes[0].payload)
        self.assertFalse(decision["allowed"])

    def test_malformed_json_fails_closed_with_a_real_result_not_a_crash(self):
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", b"{not valid json")
        decision = json.loads(publishes[0].payload)
        self.assertFalse(decision["allowed"])
        self.assertIn("malformed job payload", decision["reason"])

    def test_missing_field_fails_closed_with_a_real_result_not_a_crash(self):
        payload = job_to_dict(job())
        del payload["source"]
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(payload).encode("utf-8"))
        decision = json.loads(publishes[0].payload)
        self.assertFalse(decision["allowed"])

    def test_abort_is_always_allowed_even_with_an_open_safeguard(self):
        b = bridge(interlock=False, cell_state=CellState.FAULT)
        job_payload = job_to_dict(job(phase=JobPhase.ABORT, machine_state=MachineState.FAULT))
        publishes = b.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_payload).encode("utf-8"))
        self.assertTrue(json.loads(publishes[0].payload)["allowed"])

    def test_a_job_reuses_the_last_refreshed_snapshot_without_a_fresh_read(self):
        b = bridge(enclosure=False)
        b.refresh_status()
        # Flip the underlying line after the last refresh - handle_message
        # must still use the remembered snapshot, not silently re-read.
        b._lines.enclosure_closed.value = True  # noqa: SLF001 - real, intentional white-box check
        publishes = b.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode("utf-8"))
        self.assertFalse(json.loads(publishes[0].payload)["allowed"])


class RunForeverTests(unittest.TestCase):
    def test_missing_paho_mqtt_raises_a_clear_runtime_error_not_an_import_error(self):
        try:
            import paho.mqtt.client  # noqa: F401

            self.skipTest("paho-mqtt is installed in this environment - nothing to prove here")
        except ImportError:
            pass
        from hydra_umc_bridge_laser import run_forever

        with self.assertRaises(RuntimeError) as context:
            run_forever(bridge(), "127.0.0.1")
        self.assertIn("paho-mqtt is not installed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
