# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Safeguard reads, watcher failure paths and payload edge cases
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A laser is only allowed to be "fine" when every safeguard says so right now: any failure, partial read or odd value must read as unsafe."""

import json
import unittest

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict

from hydra_umc_bridge_laser import (
    GpioLineSettings,
    GpioSafetyLines,
    GpioSafetyProbe,
    LaserMqttBridge,
    build_edge_watch_on_failure,
    watch_for_interlock_edges,
)
from hydra_umc_bridge_laser.mqtt_transport import (
    MAX_PAYLOAD_BYTES,
    STOP_VERBS,
    TOPIC_PREFIX,
    connect_with_retry,
)


class Line:
    def __init__(self, value=True, error=None):
        self.value, self.error = value, error

    def read(self):
        if self.error:
            raise self.error
        return self.value


def lines(key=True, enclosure=True, interlock=True):
    return GpioSafetyLines(Line(key), Line(enclosure), Line(interlock))


def bridge(gpio=None, controller="IDLE"):
    return LaserMqttBridge(gpio or lines(), lambda: controller, lambda: CellState.READY)


def answer(publishes):
    return json.loads(publishes[0].payload)


class EachSafeguardAloneTests(unittest.TestCase):
    def test_any_one_open_safeguard_stops_the_cell_and_all_three_must_agree_to_run(self):
        for name, args in (("key", dict(key=False)), ("enclosure", dict(enclosure=False)), ("interlock", dict(interlock=False))):
            snapshot = GpioSafetyProbe().read_snapshot("IDLE", lines(**args))
            self.assertEqual(snapshot.machine_state(), MachineState.SAFE_STOP, name)
        self.assertNotEqual(GpioSafetyProbe().read_snapshot("IDLE", lines()).machine_state(), MachineState.SAFE_STOP)

    def test_a_failure_reading_any_single_line_makes_all_three_unsatisfied(self):
        for broken in range(3):
            parts = [Line(), Line(), Line()]
            parts[broken] = Line(error=OSError("line released"))
            snapshot = GpioSafetyProbe().read_snapshot("IDLE", GpioSafetyLines(*parts))
            self.assertEqual((snapshot.key_enabled, snapshot.enclosure_closed, snapshot.interlock_healthy), (False, False, False), broken)

    def test_a_chip_that_fails_in_the_single_read_is_treated_the_same(self):
        def boom():
            raise RuntimeError("ioctl failed")

        snapshot = GpioSafetyProbe().read_snapshot("IDLE", GpioSafetyLines(Line(), Line(), Line(), read_all=boom))
        self.assertEqual(snapshot.machine_state(), MachineState.SAFE_STOP)

    def test_the_single_read_wins_over_the_individual_readers(self):
        calls = []

        def read_all():
            calls.append(1)
            return (True, True, True)

        snapshot = GpioSafetyProbe().read_snapshot("IDLE", GpioSafetyLines(Line(False), Line(False), Line(False), read_all=read_all))
        self.assertEqual(calls, [1])
        self.assertNotEqual(snapshot.machine_state(), MachineState.SAFE_STOP)

    def test_the_default_bias_makes_a_cut_wire_read_unsafe(self):
        self.assertEqual(GpioLineSettings(active_low=True).resolved_bias(), "pull-up")
        self.assertEqual(GpioLineSettings(active_low=False).resolved_bias(), "pull-down")
        for bias in ("pull-up", "pull-down", "disabled", "as-is"):
            self.assertEqual(GpioLineSettings(active_low=True, bias=bias).resolved_bias(), bias)
        for bad in ("up", "", "PULL-UP"):
            with self.assertRaises(ValueError):
                GpioLineSettings(active_low=True, bias=bad).resolved_bias()
        with self.assertRaises(ValueError):
            GpioLineSettings(active_low=True, debounce_ms=-1).resolved_bias()


class WatcherTests(unittest.TestCase):
    class Source:
        fd = 3

        def __init__(self, events):
            self.events = events

        def read_edge_events(self):
            if isinstance(self.events, Exception):
                raise self.events
            return self.events

    def run_watcher(self, source, on_change, on_failure, runs=2):
        state = {"n": 0}
        sleeps = []

        def should_stop():
            state["n"] += 1
            return state["n"] > runs

        watch_for_interlock_edges(
            source, on_change, poll=lambda fd, timeout: True, should_stop=should_stop,
            on_failure=on_failure, retry_seconds=0.25, sleep=sleeps.append,
        )
        return sleeps

    def test_a_failure_of_on_change_is_reported_then_retried_after_the_pause(self):
        failures = []

        def on_change():
            raise ValueError("publish failed")

        sleeps = self.run_watcher(self.Source(["edge"]), on_change, failures.append)
        self.assertEqual([type(f) for f in failures], [ValueError, ValueError])
        self.assertEqual(sleeps, [0.25, 0.25])

    def test_a_failing_failure_handler_does_not_end_the_watcher(self):
        def on_failure(error):
            raise RuntimeError("cannot publish the failure either")

        sleeps = self.run_watcher(self.Source(OSError("fd closed")), lambda: None, on_failure, runs=3)
        self.assertEqual(len(sleeps), 3)

    def test_without_a_failure_handler_the_loop_still_keeps_going(self):
        sleeps = self.run_watcher(self.Source(OSError("fd closed")), lambda: None, None, runs=2)
        self.assertEqual(len(sleeps), 2)

    def test_the_failure_state_names_the_error_type_and_clears_every_safeguard(self):
        published = []
        b = bridge()
        build_edge_watch_on_failure(b, published.append)(OSError("fd closed"))
        state = json.loads(published[0].payload)
        self.assertEqual(published[0].topic, f"{TOPIC_PREFIX}state")
        self.assertTrue(published[0].retain)
        self.assertEqual((state["key_enabled"], state["enclosure_closed"], state["interlock_healthy"]), (False, False, False))
        self.assertIn("OSError", state["reason"])
        self.assertEqual(state["machine_state"], MachineState.SAFE_STOP.value)


class PayloadTests(unittest.TestCase):
    def test_json_that_is_not_a_job_object_is_always_a_refusal(self):
        for payload in (b"null", b"[]", b"7", b'"x"', b"true", b"", b"{", b"\xff\xfe", b'{"phase":"load"}'):
            publishes = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", payload)
            self.assertEqual(len(publishes), 1, payload)
            self.assertFalse(answer(publishes)["allowed"], payload)

    def test_the_size_limit_is_exact_and_the_refusal_goes_to_the_verbs_result_topic(self):
        ok = bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", b" " * MAX_PAYLOAD_BYTES)
        self.assertNotIn("larger than", answer(ok)["reason"])
        over = bridge().handle_message(f"{TOPIC_PREFIX}cmd/status", b" " * (MAX_PAYLOAD_BYTES + 1))
        self.assertEqual(over[0].topic, f"{TOPIC_PREFIX}cmd/status/result")

    def test_other_topics_and_retained_messages_get_no_answer(self):
        b = bridge()
        for topic in ("other/cmd/job", "cmd/job", f"{TOPIC_PREFIX}cmd/unknown", f"{TOPIC_PREFIX}cmd/a/b", f"{TOPIC_PREFIX}state"):
            self.assertEqual(b.handle_message(topic, b"{}"), [], topic)
        self.assertEqual(b.handle_message(f"{TOPIC_PREFIX}cmd/status", b"", retained=True), [])
        self.assertEqual(b.handle_message(f"{TOPIC_PREFIX}cmd/job", b"{}", retained=True), [])

    def test_this_bridge_has_no_stop_verb_and_an_abort_says_nothing_was_stopped(self):
        self.assertEqual(STOP_VERBS, frozenset())
        payload = json.dumps(job_to_dict(BridgeJob("j", "k", "orchestrator", JobPhase.ABORT, MachineState.IDLE, {}))).encode()
        result = answer(bridge().handle_message(f"{TOPIC_PREFIX}cmd/job", payload))
        self.assertIs(result["forwarded"], False)
        self.assertIn("physical E-STOP", result["reason"])

    def test_a_job_is_refused_while_any_safeguard_is_open_and_allowed_when_all_are_closed(self):
        payload = json.dumps(job_to_dict(BridgeJob("j", "k", "orchestrator", JobPhase.LOAD, MachineState.IDLE, {}))).encode()
        self.assertFalse(answer(bridge(lines(enclosure=False)).handle_message(f"{TOPIC_PREFIX}cmd/job", payload))["allowed"])
        self.assertTrue(answer(bridge(lines()).handle_message(f"{TOPIC_PREFIX}cmd/job", payload))["allowed"])

    def test_the_status_answer_with_a_broken_line_is_a_safe_stop_not_an_error(self):
        broken = GpioSafetyLines(Line(error=OSError("x")), Line(), Line())
        state = answer(bridge(broken).handle_message(f"{TOPIC_PREFIX}cmd/status", b""))
        self.assertEqual(state["machine_state"], MachineState.SAFE_STOP.value)


class ConnectRetryTests(unittest.TestCase):
    def test_it_retries_only_oserror_and_gives_up_after_the_last_attempt(self):
        attempts, sleeps = [], []

        def connect():
            attempts.append(1)
            raise OSError("refused")

        with self.assertRaises(RuntimeError):
            connect_with_retry(connect, max_attempts=3, retry_delay_seconds=0.5, sleep=sleeps.append)
        self.assertEqual((len(attempts), sleeps), (3, [0.5, 0.5]))

    def test_another_exception_is_not_retried(self):
        attempts = []

        def connect():
            attempts.append(1)
            raise ValueError("bug")

        with self.assertRaises(ValueError):
            connect_with_retry(connect, sleep=lambda s: None)
        self.assertEqual(len(attempts), 1)

    def test_success_after_a_failure_returns_quietly(self):
        results = [OSError("refused"), None]

        def connect():
            outcome = results.pop(0)
            if outcome:
                raise outcome

        connect_with_retry(connect, sleep=lambda s: None)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
