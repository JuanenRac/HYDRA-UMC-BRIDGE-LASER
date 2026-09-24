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

    def test_a_job_always_re_reads_the_real_gpio_lines_even_if_one_was_cached(self):
        # regression: this used to reuse whatever
        # refresh_status() last saw instead of reading the real GPIO
        # lines again - even after an explicit earlier refresh_status()
        # call, handle_message() must still re-read live right before
        # gating. Here the enclosure was OPEN at the earlier refresh and
        # is now CLOSED - a job must be allowed based on the CURRENT
        # (safe) reading, not the stale unsafe one.
        b = bridge(enclosure=False)
        b.refresh_status()
        b._lines.enclosure_closed.value = True  # noqa: SLF001 - real, intentional white-box check
        publishes = b.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode("utf-8"))
        self.assertTrue(json.loads(publishes[0].payload)["allowed"])

    def test_a_job_refuses_a_real_enclosure_open_between_refresh_and_job_regression_for_laser_01(self):
        # The exact real reproduction: enclosure closed at
        # an earlier refresh, then it opens before a job command actually
        # arrives - the job must never be allowed on the stale reading.
        b = bridge(enclosure=True)
        b.refresh_status()  # an earlier, now-stale poll while everything was safe
        b._lines.enclosure_closed.value = False  # noqa: SLF001 - real, intentional white-box check
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

    def test_password_without_username_is_rejected_before_ever_touching_paho_mqtt(self):
        # catches the most likely real misconfiguration (a password
        # set without a username) as a real, immediate error - never a
        # silent unauthenticated connection to a broker that actually
        # requires MQTT_AUTH_JSON credentials.
        from hydra_umc_bridge_laser import run_forever

        with self.assertRaises(ValueError) as context:
            run_forever(bridge(), "127.0.0.1", password="secret")
        self.assertIn("password was given without a username", str(context.exception))

    def test_configures_broker_credentials_when_given(self):
        # HYDRA-UMC-MQTT-BROKER's own MQTT_AUTH_JSON authentication
        # is real but this bridge previously had no way at all to supply
        # a username/password to reach a broker that requires it.
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.skipTest("paho-mqtt is not installed in this environment - nothing to prove here")
        from unittest.mock import MagicMock, patch

        from hydra_umc_bridge_laser import run_forever

        fake_client = MagicMock()
        with patch.object(mqtt, "Client", return_value=fake_client):
            run_forever(bridge(), "127.0.0.1", username="hydra-umc-bridge-laser", password="s3cret")
        fake_client.username_pw_set.assert_called_once_with("hydra-umc-bridge-laser", "s3cret")

    def test_does_not_touch_credentials_when_none_are_given(self):
        # Authentication stays opt-in on the client side too, matching the
        # broker's own opt-in MQTT_AUTH_JSON.
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.skipTest("paho-mqtt is not installed in this environment - nothing to prove here")
        from unittest.mock import MagicMock, patch

        from hydra_umc_bridge_laser import run_forever

        fake_client = MagicMock()
        with patch.object(mqtt, "Client", return_value=fake_client):
            run_forever(bridge(), "127.0.0.1")
        fake_client.username_pw_set.assert_not_called()

    def test_on_message_passes_the_real_retain_flag_through_to_handle_message(self):
        # end to end: a real paho-mqtt MQTTMessage's own `.retain`
        # flag must reach handle_message(), or every retained-command
        # protection below would be dead code in the one real path that
        # actually needs it.
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.skipTest("paho-mqtt is not installed in this environment - nothing to prove here")
        from unittest.mock import MagicMock, patch

        from hydra_umc_bridge_laser import run_forever

        fake_client = MagicMock()
        with patch.object(mqtt, "Client", return_value=fake_client):
            run_forever(bridge(), "127.0.0.1")
        on_message = fake_client.on_message
        message = MagicMock(topic=f"{TOPIC_PREFIX}cmd/job", payload=b"", retain=True)
        # Must not raise even though the payload is empty (not real job
        # JSON) - a retained delivery is ignored before payload parsing
        # ever happens.
        on_message(fake_client, None, message)
        fake_client.publish.assert_not_called()


class RetainedMessageTests(unittest.TestCase):
    """a real broker replays every currently-retained message on the
    subscribed wildcard immediately upon (re)subscribe - which happens on
    every reconnect, not just once at startup. Neither of this bridge's
    `cmd/*` topics is ever meant to be retained by a legitimate live
    command, so a retained delivery must never reach a real action."""

    def test_a_retained_status_request_is_ignored(self):
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/status", b"", retained=True)
        self.assertEqual(publishes, [])

    def test_a_retained_job_command_is_never_gated_or_applied(self):
        payload = json.dumps(job_to_dict(job())).encode("utf-8")
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", payload, retained=True)
        self.assertEqual(publishes, [])

    def test_a_retained_malformed_payload_is_still_ignored_not_reported_as_an_error(self):
        # Even a payload that would normally fail closed with a real
        # "malformed job payload" result must be ignored outright when
        # retained - it never reaches parsing at all.
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", b"{not valid json", retained=True)
        self.assertEqual(publishes, [])

    def test_a_live_non_retained_message_is_unaffected(self):
        publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/status", b"", retained=False)
        self.assertEqual(len(publishes), 1)


class ConnectWithRetryTests(unittest.TestCase):
    """connect_with_retry() is pure - no real paho-mqtt/broker needed to
    prove the real startup-race tolerance that was missing here (this bridge's process used to die outright
    if it started before HYDRA-UMC-MQTT-BROKER was listening yet)."""

    def test_succeeds_on_the_first_try_without_sleeping(self):
        from hydra_umc_bridge_laser import connect_with_retry

        sleeps: list = []
        connect_with_retry(lambda: None, sleep=sleeps.append)
        self.assertEqual(sleeps, [])

    def test_retries_a_transient_connection_failure_then_succeeds(self):
        from hydra_umc_bridge_laser import connect_with_retry

        attempts = {"n": 0}
        sleeps: list = []

        def flaky_connect() -> None:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise ConnectionRefusedError("broker not up yet")

        connect_with_retry(flaky_connect, max_attempts=5, retry_delay_seconds=1.5, sleep=sleeps.append)
        self.assertEqual(attempts["n"], 3)
        self.assertEqual(sleeps, [1.5, 1.5])

    def test_gives_up_after_max_attempts_with_a_clear_error(self):
        from hydra_umc_bridge_laser import connect_with_retry

        def always_fails() -> None:
            raise ConnectionRefusedError("broker still not up")

        with self.assertRaises(RuntimeError) as context:
            connect_with_retry(always_fails, max_attempts=3, retry_delay_seconds=0.01, sleep=lambda _: None)
        self.assertIn("after 3 attempts", str(context.exception))
        self.assertIn("broker still not up", str(context.exception))

    def test_a_non_os_error_is_never_retried(self):
        from hydra_umc_bridge_laser import connect_with_retry

        def broken_connect() -> None:
            raise ValueError("not an OSError - a real bug, not a broker being down")

        with self.assertRaises(ValueError):
            connect_with_retry(broken_connect, sleep=lambda _: None)


class EdgeWatchOnChangeTests(unittest.TestCase):
    def test_on_change_re_reads_live_lines_and_publishes_retained_state(self):
        from hydra_umc_bridge_laser.mqtt_transport import build_edge_watch_on_change

        real_bridge = bridge(key=True, enclosure=False, interlock=True)
        published = []
        on_change = build_edge_watch_on_change(real_bridge, published.append)

        on_change()

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].topic, f"{TOPIC_PREFIX}state")
        self.assertTrue(published[0].retain)
        payload = json.loads(published[0].payload)
        self.assertTrue(payload["key_enabled"])
        self.assertFalse(payload["enclosure_closed"])

    def test_each_call_re_reads_live_rather_than_reusing_a_stale_reading(self):
        # The real point of edge-triggered watching: a line that changed
        # between two edge events must be reflected each time, not a
        # snapshot captured once when the watcher started.
        from hydra_umc_bridge_laser.mqtt_transport import build_edge_watch_on_change

        lines = GpioSafetyLines(FakeLine(True), FakeLine(True), FakeLine(True))
        real_bridge = LaserMqttBridge(lines, lambda: "IDLE", lambda: CellState.READY)
        published = []
        on_change = build_edge_watch_on_change(real_bridge, published.append)

        on_change()
        lines.enclosure_closed.value = False
        on_change()

        first_payload = json.loads(published[0].payload)
        second_payload = json.loads(published[1].payload)
        self.assertTrue(first_payload["enclosure_closed"])
        self.assertFalse(second_payload["enclosure_closed"])


class StartEdgeWatchThreadTests(unittest.TestCase):
    def test_opens_the_watcher_with_the_given_chip_and_offsets_and_starts_a_daemon_thread(self):
        from hydra_umc_bridge_laser.mqtt_transport import start_edge_watch_thread

        opened_with = {}

        def fake_open_watcher(chip_path, key_offset, enclosure_offset, interlock_offset):
            opened_with["args"] = (chip_path, key_offset, enclosure_offset, interlock_offset)
            return object()

        watch_calls = []

        def fake_watch(source, on_change, **kwargs):
            watch_calls.append((source, on_change, kwargs))

        real_bridge = bridge()
        thread = start_edge_watch_thread(
            real_bridge,
            lambda publish: None,
            "/dev/gpiochip0",
            0,
            1,
            2,
            open_watcher=fake_open_watcher,
            watch=fake_watch,
        )
        thread.join(timeout=2)

        self.assertEqual(opened_with["args"], ("/dev/gpiochip0", 0, 1, 2))
        self.assertTrue(thread.daemon)
        self.assertEqual(len(watch_calls), 1)


if __name__ == "__main__":
    unittest.main()
