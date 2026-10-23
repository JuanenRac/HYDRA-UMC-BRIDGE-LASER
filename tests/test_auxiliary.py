# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Auxiliary safeguard tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
import json
import unittest

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_bridge_laser import AuxiliaryCheck, AuxiliarySupervisor, GpioSafetyLines, LaserMqttBridge


class Sim:
    """A simulated input: a level or a temperature that a test can change."""

    def __init__(self, value):
        self.value = value

    def __call__(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value

    def read(self):
        return True


def bridge_with(extraction, tube):
    lines = GpioSafetyLines(Sim(True), Sim(True), Sim(True))
    supervisor = AuxiliarySupervisor([AuxiliaryCheck("extraction", extraction), AuxiliaryCheck("tube_temperature", tube, max_celsius=30.0)])
    return LaserMqttBridge(lines, lambda: "IDLE", lambda: CellState.READY, auxiliary=supervisor)


def job_payload(phase=JobPhase.LOAD, key="k1"):
    return json.dumps(job_to_dict(BridgeJob("j", key, "laser", phase, MachineState.IDLE, {}))).encode()


def ask(bridge, payload):
    return json.loads(bridge.handle_message("hydra/bridges/laser/cmd/job", payload)[0].payload)


class AuxiliaryTests(unittest.TestCase):
    def test_everything_satisfied_passes(self):
        result = AuxiliarySupervisor([AuxiliaryCheck("a", lambda: True), AuxiliaryCheck("t", lambda: 25.0, max_celsius=30)]).evaluate()
        self.assertEqual(result, {"a": True, "t": True})

    def test_hot_tube_fails(self):
        self.assertFalse(AuxiliarySupervisor([AuxiliaryCheck("t", lambda: 31.0, max_celsius=30)]).evaluate()["t"])

    def test_unreadable_or_odd_values_fail_closed(self):
        def broken():
            raise OSError("sensor")

        checks = [
            AuxiliaryCheck("broken", broken),
            AuxiliaryCheck("text", lambda: "yes"),
            AuxiliaryCheck("nan", lambda: float("nan"), max_celsius=30),
            AuxiliaryCheck("bool_as_temp", lambda: True, max_celsius=30),
        ]
        self.assertEqual(AuxiliarySupervisor(checks).evaluate(), {"broken": False, "text": False, "nan": False, "bool_as_temp": False})

    def test_names_must_be_unique_and_present(self):
        with self.assertRaises(ValueError):
            AuxiliarySupervisor([AuxiliaryCheck("a", lambda: True), AuxiliaryCheck("a", lambda: True)])
        with self.assertRaises(ValueError):
            AuxiliarySupervisor([AuxiliaryCheck("", lambda: True)])

    def test_job_is_allowed_when_auxiliaries_are_satisfied(self):
        self.assertTrue(ask(bridge_with(Sim(True), Sim(22.0)), job_payload())["allowed"])

    def test_job_is_refused_when_extraction_is_off(self):
        answer = ask(bridge_with(Sim(False), Sim(22.0)), job_payload())
        self.assertFalse(answer["allowed"])
        self.assertIn("extraction", answer["reason"])

    def test_job_is_refused_when_the_tube_is_hot_and_names_it(self):
        answer = ask(bridge_with(Sim(True), Sim(41.5)), job_payload())
        self.assertFalse(answer["allowed"])
        self.assertIn("tube_temperature", answer["reason"])

    def test_abort_still_passes_the_gate_with_a_failed_auxiliary(self):
        self.assertTrue(ask(bridge_with(Sim(False), Sim(99.0)), job_payload(JobPhase.ABORT))["allowed"])

    def test_state_reports_the_auxiliaries(self):
        state = json.loads(bridge_with(Sim(True), Sim(50.0)).state_publish().payload)
        self.assertEqual(state["auxiliary"], {"extraction": True, "tube_temperature": False})

    def test_without_auxiliaries_the_state_is_unchanged(self):
        bridge = LaserMqttBridge(GpioSafetyLines(Sim(True), Sim(True), Sim(True)), lambda: "IDLE", lambda: CellState.READY)
        self.assertNotIn("auxiliary", json.loads(bridge.state_publish().payload))


if __name__ == "__main__":
    unittest.main()
