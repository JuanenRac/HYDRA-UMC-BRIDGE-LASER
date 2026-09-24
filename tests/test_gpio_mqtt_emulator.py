# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Bridge <-> realistic GPIO chip + MQTT broker tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Run this bridge's REAL LaserMqttBridge.handle_message() + GpioSafetyProbe
end to end against a libgpiod-shaped GPIO chip and a real MQTT broker
(retained messages, wildcard subscriptions, an inbound queue) - driving
the physical safeguards and going through a real broker round trip, not a
`FakeLine` + bare list.
"""
from __future__ import annotations

import json
import unittest

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_bridge_laser import LaserMqttBridge
from hydra_umc_bridge_laser.mqtt_transport import TOPIC_PREFIX

from gpio_mqtt_emulator import GpioChipEmulator, MqttBrokerEmulator

STATE_TOPIC = f"{TOPIC_PREFIX}state"
STATUS_TOPIC = f"{TOPIC_PREFIX}cmd/status"
JOB_TOPIC = f"{TOPIC_PREFIX}cmd/job"
RESULT_TOPIC = f"{TOPIC_PREFIX}cmd/job/result"


def _job() -> bytes:
    return json.dumps(job_to_dict(BridgeJob("j-1", "idem-1", "cell-a", JobPhase.LOAD, MachineState.IDLE, {}))).encode("utf-8")


class BridgeAgainstGpioAndBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chip = GpioChipEmulator()  # all 3 safeguards start "safe to operate"
        self.broker = MqttBrokerEmulator()
        self.cell_state = CellState.READY
        self.bridge = LaserMqttBridge(
            self.chip.as_safety_lines(),
            controller_state=lambda: "IDLE",
            cell_state=lambda: self.cell_state,
        )

    def _last_state(self) -> dict:
        raw = self.broker.retained(STATE_TOPIC)
        self.assertIsNotNone(raw, "no retained state has been published yet")
        return json.loads(raw)

    def test_cmd_status_publishes_a_real_retained_state_from_the_live_gpio_lines(self) -> None:
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        published = [p for p in self.broker.published if p[0] == STATE_TOPIC]
        self.assertEqual(len(published), 1)
        self.assertTrue(published[0][2], "the state publish MUST be retained")
        state = self._last_state()
        self.assertTrue(state["key_enabled"] and state["enclosure_closed"] and state["interlock_healthy"])
        self.assertEqual(state["machine_state"], "IDLE")

    def test_opening_the_enclosure_moves_the_next_published_state_to_safe_stop(self) -> None:
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        self.assertEqual(self._last_state()["machine_state"], "IDLE")

        self.chip.open_enclosure()  # a real physical change between two messages
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        state = self._last_state()
        self.assertFalse(state["enclosure_closed"])
        self.assertEqual(state["machine_state"], "SAFE_STOP")

    def test_a_late_subscriber_gets_the_current_retained_safety_state(self) -> None:
        self.chip.set_interlock_healthy(False)
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)

        # A dashboard connecting only now still learns the real, current state.
        sub = self.broker.subscribe(f"{TOPIC_PREFIX}#")
        state_msgs = [json.loads(p) for t, p in sub.received if t == STATE_TOPIC]
        self.assertEqual(len(state_msgs), 1)
        self.assertFalse(state_msgs[0]["interlock_healthy"])
        self.assertEqual(state_msgs[0]["machine_state"], "SAFE_STOP")

    def test_a_faulted_gpio_chip_fails_closed_never_assumes_safe(self) -> None:
        self.chip.fault_chip()  # unplugged ribbon / chip offline
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        state = self._last_state()
        # A transport-level GPIO failure reads every safeguard as unsatisfied.
        self.assertFalse(state["key_enabled"])
        self.assertFalse(state["enclosure_closed"])
        self.assertFalse(state["interlock_healthy"])
        self.assertEqual(state["machine_state"], "SAFE_STOP")

    def test_active_low_interlock_wiring_reads_healthy_at_logic_zero(self) -> None:
        # The default interlock line is active-low: healthy = 0V on the wire.
        # Prove the bridge still sees a safe cell (the emulator inverts, a
        # plain FakeLine(True) never would).
        self.assertFalse(self.chip.interlock_relay._wire_value)  # logic 0 on the wire
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        self.assertTrue(self._last_state()["interlock_healthy"])
        self.assertEqual(self._last_state()["machine_state"], "IDLE")

    def test_a_job_is_gated_against_the_live_safeguard_snapshot_not_a_stale_one(self) -> None:
        # A cmd/status says IDLE...
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        self.assertEqual(self._last_state()["machine_state"], "IDLE")

        # ...then the key is turned off, THEN a job arrives (the
        # gate must re-read live, not reuse the last snapshot).
        self.chip.turn_key(False)
        self.broker.enqueue_inbound(JOB_TOPIC, _job())
        self.broker.pump(self.bridge)
        result = json.loads(next(p for t, p, _ in self.broker.published if t == RESULT_TOPIC))
        self.assertFalse(result["allowed"])

    def test_a_job_beside_a_fully_safe_cell_and_ready_state_is_allowed(self) -> None:
        self.broker.enqueue_inbound(JOB_TOPIC, _job())
        self.broker.pump(self.bridge)
        result = json.loads(next(p for t, p, _ in self.broker.published if t == RESULT_TOPIC))
        self.assertTrue(result["allowed"], result.get("reason"))

    def test_an_unrecognised_cmd_subtopic_is_silently_ignored_by_the_round_trip(self) -> None:
        self.broker.enqueue_inbound(f"{TOPIC_PREFIX}cmd/fire", b"")
        self.broker.pump(self.bridge)
        self.assertEqual(self.broker.published, [])


if __name__ == "__main__":
    unittest.main()
