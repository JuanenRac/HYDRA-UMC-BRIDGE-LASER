# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Hostile payloads, honest answers, one GPIO request and a watcher that says when it fails
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""What a client of the broker can do to this bridge must never end its loop, the answers must not claim more than the bridge did, and the GPIO side must be fail-safe."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_sdk.job_intake import IdempotencyStore

from hydra_umc_bridge_laser import (
    GpioLineSettings,
    GpioSafetyLines,
    GpioSafetyProbe,
    LaserMqttBridge,
    LaserSafetySnapshot,
    build_edge_watch_on_failure,
    open_gpio_safety,
    watch_for_interlock_edges,
)
from hydra_umc_bridge_laser.mqtt_transport import AVAILABILITY_TOPIC, MAX_PAYLOAD_BYTES, TOPIC_PREFIX, MessageDispatcher


class Line:
    def __init__(self, value=True):
        self.value = value

    def read(self):
        return self.value


def healthy_lines():
    return GpioSafetyLines(Line(), Line(), Line())


def bridge(lines=None, controller="IDLE", store=None, clock=lambda: 100.0):
    return LaserMqttBridge(lines or healthy_lines(), lambda: controller, lambda: CellState.READY, store, clock=clock)


def job_payload(key="k1", phase=JobPhase.LOAD):
    return json.dumps(job_to_dict(BridgeJob("job-1", key, "orchestrator", phase, MachineState.IDLE, {}))).encode("utf-8")


class HostilePayloadTests(unittest.TestCase):
    def test_a_deeply_nested_json_is_a_refusal_not_an_exception(self):
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", b"[" * 100_000)
        self.assertEqual(len(publishes), 1)
        self.assertFalse(json.loads(publishes[0].payload)["allowed"])

    def test_a_payload_over_the_limit_is_refused(self):
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", b" " * (MAX_PAYLOAD_BYTES + 1))
        self.assertIn("larger than", json.loads(publishes[0].payload)["reason"])

    def test_a_failure_while_gating_is_a_refusal_and_leaves_an_honest_answer_for_the_key(self):
        def broken():
            raise RuntimeError("controller link down")

        store = IdempotencyStore()
        failing = LaserMqttBridge(healthy_lines(), broken, lambda: CellState.READY, store)
        first = failing.handle_message(f"{TOPIC_PREFIX}cmd/job", job_payload())[0]
        again = failing.handle_message(f"{TOPIC_PREFIX}cmd/job", job_payload())[0]
        self.assertFalse(json.loads(first.payload)["allowed"])
        self.assertEqual(again.payload, first.payload)

    def test_a_failure_while_reading_status_is_a_refusal(self):
        def broken():
            raise RuntimeError("controller link down")

        publishes = LaserMqttBridge(healthy_lines(), broken, lambda: CellState.READY).handle_message(f"{TOPIC_PREFIX}cmd/status", b"")
        self.assertEqual(publishes[0].topic, f"{TOPIC_PREFIX}cmd/status/result")


class AbortAnswerTests(unittest.TestCase):
    def test_an_abort_says_that_nothing_was_stopped(self):
        result = json.loads(bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", job_payload(phase=JobPhase.ABORT))[0].payload)
        self.assertIs(result["forwarded"], False)
        self.assertEqual(result["mode"], "gate-only")
        self.assertIn("nothing was stopped", result["reason"])


class StateTests(unittest.TestCase):
    def test_the_state_carries_the_moment_it_was_observed(self):
        publish = bridge(clock=lambda: 1234.5).handle_message(f"{TOPIC_PREFIX}cmd/status", b"")[0]
        self.assertTrue(publish.retain)
        self.assertEqual(json.loads(publish.payload)["observed_at"], 1234500)


class FailClosedReadTests(unittest.TestCase):
    def test_any_exception_while_reading_fails_every_safeguard(self):
        class Released(Exception):
            """Not an OSError, like libgpiod v2's RequestReleasedError."""

        class Broken:
            def read(self):
                raise Released("request released")

        snapshot = GpioSafetyProbe().read_snapshot("IDLE", GpioSafetyLines(Line(), Broken(), Line()))
        self.assertEqual(snapshot.machine_state(), MachineState.SAFE_STOP)
        self.assertFalse(snapshot.key_enabled or snapshot.enclosure_closed or snapshot.interlock_healthy)

    def test_the_three_lines_are_read_in_one_operation_when_the_chip_offers_it(self):
        calls = []

        def read_all():
            calls.append(1)
            return True, True, True

        lines = GpioSafetyLines(Line(False), Line(False), Line(False), read_all)
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", lines)
        self.assertEqual(calls, [1])
        self.assertTrue(snapshot.key_enabled and snapshot.enclosure_closed and snapshot.interlock_healthy)


class ControllerVocabularyTests(unittest.TestCase):
    def state(self, token):
        return LaserSafetySnapshot(token, True, True, True).machine_state()

    def test_grbl_tokens_with_a_substate_are_understood(self):
        self.assertEqual(self.state("Hold:0"), MachineState.HOLDING)
        self.assertEqual(self.state("Alarm:1"), MachineState.FAULT)
        self.assertEqual(self.state("Jog"), MachineState.RUNNING)
        self.assertEqual(self.state("Home"), MachineState.RUNNING)
        self.assertEqual(self.state("Door:1"), MachineState.SAFE_STOP)

    def test_the_older_tokens_still_mean_what_they_meant(self):
        self.assertEqual(self.state("IDLE"), MachineState.IDLE)
        self.assertEqual(self.state("paused"), MachineState.HOLDING)
        self.assertEqual(self.state("whatever"), MachineState.OFFLINE)


class WatcherFailureTests(unittest.TestCase):
    def test_a_failing_watcher_publishes_a_fail_closed_state_and_keeps_trying(self):
        class Source:
            fd = 3

            def __init__(self):
                self.reads = 0

            def read_edge_events(self):
                self.reads += 1
                if self.reads == 1:
                    raise RuntimeError("device went away")
                return [object()]

            def close(self):
                return None

        source = Source()
        published = []
        changes = []
        stop = {"calls": 0}

        def should_stop():
            stop["calls"] += 1
            return stop["calls"] > 2

        watch_for_interlock_edges(
            source,
            lambda: changes.append(1),
            poll=lambda fd, timeout: True,
            should_stop=should_stop,
            on_failure=build_edge_watch_on_failure(bridge(), published.append),
            sleep=lambda seconds: None,
        )
        self.assertEqual(len(published), 1)
        state = json.loads(published[0].payload)
        self.assertEqual(state["machine_state"], "SAFE_STOP")
        self.assertIn("edge watcher failed", state["reason"])
        self.assertEqual(changes, [1])


class FakeLineSettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeRequest:
    def __init__(self, config):
        self.config = config
        self.fd = 7
        self.get_values_calls = []
        self.released = False

    def get_values(self, offsets):
        self.get_values_calls.append(list(offsets))
        return ["ACTIVE", "ACTIVE", "INACTIVE"]

    def read_edge_events(self):
        return [object()]

    def release(self):
        self.released = True


def fake_gpiod():
    requests = []
    gpiod = types.ModuleType("gpiod")
    gpiod.LineSettings = FakeLineSettings

    def request_lines(chip_path, consumer, config):
        request = FakeRequest(config)
        requests.append((chip_path, consumer, request))
        return request

    gpiod.request_lines = request_lines
    line = types.ModuleType("gpiod.line")
    line.Bias = types.SimpleNamespace(PULL_UP="PULL_UP", PULL_DOWN="PULL_DOWN", DISABLED="DISABLED", AS_IS="AS_IS")
    line.Direction = types.SimpleNamespace(INPUT="INPUT")
    line.Edge = types.SimpleNamespace(BOTH="BOTH")
    line.Value = types.SimpleNamespace(ACTIVE="ACTIVE", INACTIVE="INACTIVE")
    gpiod.line = line
    return {"gpiod": gpiod, "gpiod.line": line}, requests


class OneGpioRequestTests(unittest.TestCase):
    def open(self, **wiring):
        modules, requests = fake_gpiod()
        key = wiring.get("key", GpioLineSettings(active_low=False))
        enclosure = wiring.get("enclosure", GpioLineSettings(active_low=True))
        interlock = wiring.get("interlock", GpioLineSettings(active_low=True, bias="disabled", debounce_ms=0))
        with mock.patch.dict(sys.modules, modules):
            safety = open_gpio_safety("/dev/gpiochip0", 4, 5, 6, key=key, enclosure=enclosure, interlock=interlock)
        return safety, requests

    def test_the_levels_and_the_edge_watcher_share_one_request(self):
        safety, requests = self.open()
        self.assertEqual(len(requests), 1, "a second request for the same lines would be refused as busy")
        self.assertEqual(safety.watcher.fd, 7)
        self.assertEqual(safety.watcher.read_edge_events() != [], True)

    def test_polarity_bias_and_debounce_reach_the_line_settings(self):
        _, requests = self.open()
        config = requests[0][2].config
        self.assertEqual(config[4].active_low, False)
        self.assertEqual(config[5].active_low, True)
        self.assertEqual(config[6].active_low, True)
        self.assertEqual(config[4].edge_detection, "BOTH")
        self.assertEqual(config[4].direction, "INPUT")
        # the default bias makes a cut wire read as unsafe: pull-up for active-low, pull-down for active-high
        self.assertEqual(config[4].bias, "PULL_DOWN")
        self.assertEqual(config[5].bias, "PULL_UP")
        self.assertEqual(config[6].bias, "DISABLED")
        self.assertEqual(config[4].debounce_period, timedelta(milliseconds=10))
        self.assertEqual(config[6].debounce_period, timedelta(0))

    def test_the_three_levels_come_from_one_get_values_call(self):
        safety, requests = self.open()
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", safety.lines)
        self.assertEqual(requests[0][2].get_values_calls, [[4, 5, 6]])
        self.assertEqual((snapshot.key_enabled, snapshot.enclosure_closed, snapshot.interlock_healthy), (True, True, False))
        self.assertEqual(snapshot.machine_state(), MachineState.SAFE_STOP)

    def test_two_safeguards_on_the_same_line_are_refused(self):
        modules, _ = fake_gpiod()
        wiring = GpioLineSettings(active_low=False)
        with mock.patch.dict(sys.modules, modules), self.assertRaises(ValueError):
            open_gpio_safety("/dev/gpiochip0", 4, 4, 6, key=wiring, enclosure=wiring, interlock=wiring)

    def test_an_unknown_bias_is_refused(self):
        modules, _ = fake_gpiod()
        wiring = GpioLineSettings(active_low=False)
        with mock.patch.dict(sys.modules, modules), self.assertRaises(ValueError):
            open_gpio_safety("/dev/gpiochip0", 4, 5, 6, key=GpioLineSettings(active_low=False, bias="sideways"), enclosure=wiring, interlock=wiring)

    def test_the_polarity_has_to_be_declared(self):
        with self.assertRaises(TypeError):
            GpioLineSettings()  # type: ignore[call-arg]


class ConcurrentReadTests(unittest.TestCase):
    def test_the_mqtt_thread_and_the_watcher_never_read_at_the_same_time(self):
        inside = {"now": 0, "max": 0}
        guard = threading.Lock()

        def read_all():
            with guard:
                inside["now"] += 1
                inside["max"] = max(inside["max"], inside["now"])
            threading.Event().wait(0.002)
            with guard:
                inside["now"] -= 1
            return True, True, True

        shared = bridge(GpioSafetyLines(Line(), Line(), Line(), read_all))
        threads = [threading.Thread(target=lambda: [shared.refresh_status() for _ in range(10)]) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(inside["max"], 1)


class InspectToolTests(unittest.TestCase):
    def test_a_failed_inspection_reports_the_canonical_state_value(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory) / "evidence.json"
            evidence.write_text("{not json", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(root / "tools" / "inspect_controller_evidence.py"), str(evidence)],
                capture_output=True, text=True, env=os.environ.copy(),
            )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["machine_state"], "SAFE_STOP")


class DispatcherTests(unittest.TestCase):
    def test_messages_are_answered_in_order_off_the_network_thread(self):
        client = mock.MagicMock()
        dispatcher = MessageDispatcher(bridge())
        for _ in range(3):
            dispatcher.on_message(client, None, mock.MagicMock(topic=f"{TOPIC_PREFIX}cmd/status", payload=b"", retain=False))
        dispatcher.close()
        self.assertEqual(client.publish.call_count, 3)

    def test_a_retained_message_is_never_queued(self):
        client = mock.MagicMock()
        dispatcher = MessageDispatcher(bridge())
        dispatcher.on_message(client, None, mock.MagicMock(topic=f"{TOPIC_PREFIX}cmd/status", payload=b"", retain=True))
        dispatcher.close()
        client.publish.assert_not_called()


class FakeClient:
    instances: list = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.will = None
        self.published = []
        self.subscribed = []
        self.reconnect = None
        FakeClient.instances.append(self)

    def username_pw_set(self, *args, **kwargs):
        pass

    def tls_set(self, *args, **kwargs):
        pass

    def reconnect_delay_set(self, min_delay=1, max_delay=120):
        self.reconnect = (min_delay, max_delay)

    def will_set(self, topic, payload=None, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def connect(self, *args, **kwargs):
        pass

    def subscribe(self, topic, *args, **kwargs):
        self.subscribed.append(topic)

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))

    def loop_forever(self):
        return None


class RunForeverTests(unittest.TestCase):
    def run_it(self, **kwargs):
        paho = types.ModuleType("paho")
        mqtt_package = types.ModuleType("paho.mqtt")
        client_module = types.ModuleType("paho.mqtt.client")
        client_module.Client = FakeClient
        client_module.CallbackAPIVersion = types.SimpleNamespace(VERSION2="v2")
        paho.mqtt = mqtt_package
        mqtt_package.client = client_module
        modules = {"paho": paho, "paho.mqtt": mqtt_package, "paho.mqtt.client": client_module}
        from hydra_umc_bridge_laser import run_forever

        FakeClient.instances.clear()
        with mock.patch.dict(sys.modules, modules):
            run_forever(bridge(), "127.0.0.1", **kwargs)
        return FakeClient.instances[-1]

    def test_the_client_uses_the_version_2_callbacks(self):
        self.assertEqual(self.run_it().args[0], "v2")

    def test_a_last_will_marks_the_bridge_offline_and_connecting_marks_it_online(self):
        client = self.run_it()
        self.assertEqual(client.will, (AVAILABILITY_TOPIC, "offline", 1, True))
        client.on_connect(client, None, {}, types.SimpleNamespace(is_failure=False), None)
        self.assertIn((AVAILABILITY_TOPIC, "online", 1, True), client.published)
        self.assertEqual(client.subscribed, [f"{TOPIC_PREFIX}cmd/#"])

    def test_a_refused_connection_does_not_announce_the_bridge_online(self):
        client = self.run_it()
        client.on_connect(client, None, {}, types.SimpleNamespace(is_failure=True), None)
        self.assertEqual(client.published, [])

    def test_the_edge_watcher_that_is_given_is_the_one_that_is_watched(self):
        watcher = mock.MagicMock()
        with mock.patch("hydra_umc_bridge_laser.mqtt_transport.start_edge_watch_thread") as start:
            self.run_it(edge_watcher=watcher)
        self.assertIs(start.call_args.args[2], watcher)


if __name__ == "__main__":
    unittest.main()
