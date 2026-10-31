# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Safety event stream tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
import json
import unittest

from hydra_umc_sdk.bridge_contract import CellState
from hydra_umc_bridge_laser import GpioSafetyLines, LaserMqttBridge, LaserSafetySnapshot, SafetyEventTracker
from hydra_umc_sdk.bridge_transport import MqttPublish
from hydra_umc_bridge_laser.events import INTERLOCK_OPEN_TOPIC, SAFETY_EVENT_TOPIC, EventPublish
from hydra_umc_bridge_laser.mqtt_transport import build_edge_watch_on_change, build_edge_watch_on_failure


class Line:
    def __init__(self, value=True):
        self.value = value

    def read(self):
        return self.value


def make_bridge():
    key, door, interlock = Line(), Line(), Line()
    clock = iter(range(1000, 100000))
    bridge = LaserMqttBridge(GpioSafetyLines(key, door, interlock), lambda: "IDLE", lambda: CellState.READY, clock=lambda: next(clock))
    return bridge, key, door, interlock


class EventPublishTests(unittest.TestCase):
    def test_an_event_is_a_qos_one_publish_of_the_sdk(self):
        event = EventPublish("t", "p")
        self.assertEqual(event.qos, 1)
        self.assertFalse(event.retain)
        self.assertEqual(event, MqttPublish("t", "p", False, 1))
        self.assertEqual(EventPublish("t", "p", qos=2).qos, 2)
        with self.assertRaises(ValueError):
            EventPublish("t", "p", qos=3)


class SafetyEventTests(unittest.TestCase):
    def test_first_reading_is_only_a_baseline(self):
        tracker = SafetyEventTracker(clock=lambda: 1.0)
        self.assertEqual(tracker.observe(LaserSafetySnapshot("IDLE", False, False, False)), [])

    def test_unchanged_reading_makes_no_event(self):
        tracker = SafetyEventTracker(clock=lambda: 1.0)
        tracker.observe(LaserSafetySnapshot("IDLE", True, True, True))
        self.assertEqual(tracker.observe(LaserSafetySnapshot("IDLE", True, True, True)), [])

    def test_open_door_logs_the_change_and_signals_interlock_open(self):
        tracker = SafetyEventTracker(clock=lambda: 2.0)
        tracker.observe(LaserSafetySnapshot("IDLE", True, True, True))
        events = tracker.observe(LaserSafetySnapshot("IDLE", True, False, True))
        self.assertEqual([e.topic for e in events], [SAFETY_EVENT_TOPIC, INTERLOCK_OPEN_TOPIC])
        log = json.loads(events[0].payload)
        self.assertEqual((log["safeguard"], log["from"], log["to"], log["at_ms"]), ("enclosure_closed", True, False, 2000))
        opened = json.loads(events[1].payload)
        self.assertEqual(opened["reasons"], ["enclosure_closed"])
        self.assertGreater(opened["sequence"], log["sequence"])
        for event in events:
            self.assertEqual(event.qos, 1)
            self.assertFalse(event.retain)

    def test_a_second_unsafe_change_is_logged_but_does_not_repeat_interlock_open(self):
        tracker = SafetyEventTracker(clock=lambda: 1.0)
        tracker.observe(LaserSafetySnapshot("IDLE", True, True, True))
        tracker.observe(LaserSafetySnapshot("IDLE", True, False, True))
        events = tracker.observe(LaserSafetySnapshot("IDLE", False, False, True))
        self.assertEqual([e.topic for e in events], [SAFETY_EVENT_TOPIC])

    def test_recovery_is_logged_without_interlock_open(self):
        tracker = SafetyEventTracker(clock=lambda: 1.0)
        tracker.observe(LaserSafetySnapshot("IDLE", True, False, True))
        events = tracker.observe(LaserSafetySnapshot("IDLE", True, True, True))
        self.assertEqual([e.topic for e in events], [SAFETY_EVENT_TOPIC])
        self.assertTrue(json.loads(events[0].payload)["to"])

    def test_simulated_edge_watch_publishes_state_then_events(self):
        bridge, _, door, _ = make_bridge()
        published = []
        on_change = build_edge_watch_on_change(bridge, published.append)
        on_change()  # baseline
        self.assertEqual(len(published), 1)
        door.value = False
        on_change()
        topics = [m.topic for m in published]
        self.assertEqual(topics[1:], ["hydra/bridges/laser/state", SAFETY_EVENT_TOPIC, INTERLOCK_OPEN_TOPIC])

    def test_a_failing_watcher_reports_a_fail_closed_state_and_the_open_interlock(self):
        bridge, *_ = make_bridge()
        published = []
        build_edge_watch_on_change(bridge, published.append)()
        published.clear()
        build_edge_watch_on_failure(bridge, published.append)(OSError("gone"))
        topics = [m.topic for m in published]
        self.assertIn(INTERLOCK_OPEN_TOPIC, topics)
        self.assertIn("edge watcher failed", json.loads(published[-1].payload)["reason"])

    def test_cmd_status_answer_is_unchanged(self):
        bridge, *_ = make_bridge()
        answer = bridge.handle_message("hydra/bridges/laser/cmd/status", b"")
        self.assertEqual([m.topic for m in answer], ["hydra/bridges/laser/state"])


if __name__ == "__main__":
    unittest.main()
