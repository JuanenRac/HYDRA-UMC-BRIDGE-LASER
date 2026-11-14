# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - A job in doubt is looked up, and the GRBL state words are read by the shared table
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A repeat whose first attempt left no answer is answered with what the cell reports (switch off by default) and never evaluated again; the state word of a GRBL report is read by the table of the SDK. Simulated lines, evidence=simulator."""

import json
import os
import unittest
from unittest import mock

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_sdk.grbl_status import GRBL_STATES, grbl_machine_state
from hydra_umc_sdk.job_intake import IdempotencyStore

from hydra_umc_bridge_laser import GpioSafetyLines, LaserMqttBridge
from hydra_umc_bridge_laser.cell import LaserSafetySnapshot
from hydra_umc_bridge_laser.mqtt_transport import IN_DOUBT_CONSULT_ENVIRONMENT, TOPIC_PREFIX

JOB_TOPIC = f"{TOPIC_PREFIX}cmd/job"


class FakeLine:
    def __init__(self, value=True):
        self.value = value

    def read(self):
        return self.value


def job_message(key="key-1"):
    return json.dumps(job_to_dict(BridgeJob("job-1", key, "orchestrator", JobPhase.LOAD, MachineState.IDLE, {}))).encode("utf-8")


def make(store, state="Idle", enclosure=True, **options):
    lines = GpioSafetyLines(FakeLine(True), FakeLine(enclosure), FakeLine(True))
    reads = []

    def controller_state():
        reads.append(1)
        return state() if callable(state) else state

    bridge = LaserMqttBridge(lines, controller_state, lambda: CellState.READY, store, **options)
    return bridge, reads


def in_doubt_store(key="key-1"):
    store = IdempotencyStore()
    assert store.claim(key)  # the first attempt claimed the key and never stored an answer
    return store


class InDoubtOffByDefaultTests(unittest.TestCase):
    def test_off_by_default_a_job_in_doubt_is_refused_as_before(self):
        bridge, reads = make(in_doubt_store())
        body = json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)
        self.assertFalse(body["allowed"])
        self.assertIn("not run again", body["reason"])
        self.assertNotIn("in_doubt", body)
        self.assertEqual(reads, [], "the cell is not even read while the switch is off")

    def test_the_environment_switch_turns_it_on(self):
        with mock.patch.dict(os.environ, {IN_DOUBT_CONSULT_ENVIRONMENT: "1"}):
            bridge, _ = make(in_doubt_store())
        self.assertTrue(json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)["in_doubt"])


class InDoubtConsultTests(unittest.TestCase):
    def test_the_repeat_is_answered_with_what_the_cell_reports_and_is_not_evaluated_again(self):
        bridge, _ = make(in_doubt_store(), state="Run", in_doubt_consult=True)
        body = json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)
        self.assertEqual((body["allowed"], body["in_doubt"], body["forwarded"], body["machine_state"]), (False, True, False, "RUNNING"))
        self.assertEqual((body["controller_state"], body["key_enabled"], body["enclosure_closed"], body["interlock_healthy"]), ("Run", True, True, True))

    def test_an_open_enclosure_shows_in_the_reading(self):
        bridge, _ = make(in_doubt_store(), enclosure=False, in_doubt_consult=True)
        body = json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)
        self.assertEqual((body["machine_state"], body["enclosure_closed"]), ("SAFE_STOP", False))

    def test_the_answer_is_stored_so_a_further_repeat_gets_the_same_one_without_reading_again(self):
        states = ["Hold:0", "Idle"]
        bridge, reads = make(in_doubt_store(), state=lambda: states.pop(0) if len(states) > 1 else states[0], in_doubt_consult=True)
        first = bridge.handle_message(JOB_TOPIC, job_message())[0]
        asked = len(reads)
        second = bridge.handle_message(JOB_TOPIC, job_message())[0]
        self.assertEqual(second.payload, first.payload)
        self.assertEqual(json.loads(first.payload)["machine_state"], "HOLDING")
        self.assertEqual(len(reads), asked)

    def test_a_controller_that_reports_nothing_leaves_the_repeat_refused(self):
        bridge, _ = make(in_doubt_store(), state="", in_doubt_consult=True)
        body = json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)
        self.assertFalse(body["allowed"])
        self.assertNotIn("in_doubt", body)

    def test_a_controller_that_raises_leaves_the_repeat_refused_and_does_not_end_the_loop(self):
        def broken():
            raise OSError("port lost")

        bridge, _ = make(in_doubt_store(), state=broken, in_doubt_consult=True)
        body = json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)
        self.assertFalse(body["allowed"])
        self.assertNotIn("in_doubt", body)

    def test_an_idle_ready_cell_does_not_turn_a_repeat_into_a_new_job(self):
        bridge, _ = make(in_doubt_store(), state="Idle", in_doubt_consult=True)
        self.assertFalse(json.loads(bridge.handle_message(JOB_TOPIC, job_message())[0].payload)["allowed"])

    def test_a_key_with_a_stored_answer_still_gets_that_answer(self):
        bridge, _ = make(IdempotencyStore(), in_doubt_consult=True)
        first = bridge.handle_message(JOB_TOPIC, job_message())[0]
        second = bridge.handle_message(JOB_TOPIC, job_message())[0]
        self.assertEqual(second.payload, first.payload)
        self.assertNotIn("in_doubt", json.loads(second.payload))

    def test_a_new_key_is_evaluated_normally_with_the_switch_on(self):
        bridge, _ = make(in_doubt_store("other"), in_doubt_consult=True)
        self.assertTrue(json.loads(bridge.handle_message(JOB_TOPIC, job_message("key-2"))[0].payload)["allowed"])


class SharedGrblTableTests(unittest.TestCase):
    def state(self, word):
        return LaserSafetySnapshot(word, True, True, True).machine_state()

    def test_every_word_of_the_shared_table_is_read_the_same_way_with_any_substate_or_case(self):
        for word, expected in GRBL_STATES.items():
            for spelled in (word, word.title(), word.lower(), f"{word.title()}:0", f"{word}:3"):
                self.assertEqual(self.state(spelled), expected, spelled)
                self.assertEqual(self.state(spelled), grbl_machine_state(spelled), spelled)

    def test_the_words_this_bridge_always_read_keep_their_state(self):
        expected = {"Idle": MachineState.IDLE, "IDLE": MachineState.IDLE, "Run": MachineState.RUNNING, "Jog": MachineState.RUNNING, "Home": MachineState.RUNNING,
                    "Hold:0": MachineState.HOLDING, "Hold:1": MachineState.HOLDING, "paused": MachineState.HOLDING, "Alarm:1": MachineState.FAULT,
                    "FAULT": MachineState.FAULT, "error": MachineState.FAULT, "Door:2": MachineState.SAFE_STOP}
        for word, state in expected.items():
            self.assertEqual(self.state(word), state, word)

    def test_a_word_nobody_knows_and_a_value_that_is_not_text_are_offline_never_idle(self):
        for word in ("Check", "Sleep", "Idle2", "", "Bogus:1", None, 5, b"Idle"):
            self.assertEqual(self.state(word), MachineState.OFFLINE, repr(word))

    def test_the_safeguards_still_win_over_the_word(self):
        for flags in ((False, True, True), (True, False, True), (True, True, False)):
            self.assertEqual(LaserSafetySnapshot("Idle", *flags).machine_state(), MachineState.SAFE_STOP)

    def test_only_idle_allows_work(self):
        allowing = [word for word in list(GRBL_STATES) + ["Bogus"] if self.state(word) is MachineState.IDLE]
        self.assertEqual(allowing, ["IDLE"])


if __name__ == "__main__":
    unittest.main()
