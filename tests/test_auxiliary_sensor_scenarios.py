# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Tube temperature and extraction scenarios on a simulated sensor tree
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A simulated 1-Wire tree and a simulated GPIO line feed the real bridge through the real readers (evidence: simulator).

`Ds18b20Tree` writes the `w1_slave` file the kernel would write, with the profiles of the real part: the 85 C it reports right
after power-up, a failed CRC, a sensor that vanishes from the bus and a tube that heats up. The readers, the supervisor, the
gate and the retained state of the bridge are the real ones; only the files and the line are simulated, so nothing here
says anything about a real sensor.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_bridge_laser import LaserMqttBridge
from hydra_umc_bridge_laser.auxiliary import AuxiliaryCheck, AuxiliarySupervisor
from hydra_umc_bridge_laser.auxiliary_inputs import gpio_level_reader, w1_reader
from hydra_umc_bridge_laser.mqtt_transport import TOPIC_PREFIX

from gpio_mqtt_emulator import GpioChipEmulator, MqttBrokerEmulator

DEVICE = "28-0316a2796e36"
RESULT_TOPIC = f"{TOPIC_PREFIX}cmd/job/result"
STATE_TOPIC = f"{TOPIC_PREFIX}state"
JOB_TOPIC = f"{TOPIC_PREFIX}cmd/job"
STATUS_TOPIC = f"{TOPIC_PREFIX}cmd/status"


class Ds18b20Tree:
    """The `/sys/bus/w1/devices` folder of a kernel with one sensor, written the way the driver writes it."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.folder = root / DEVICE
        self.folder.mkdir()
        self.file = self.folder / "w1_slave"

    def _write(self, crc_ok: bool, milli: int) -> None:
        self.file.write_text(f"72 01 4b 46 7f ff 0e 10 57 : crc=57 {'YES' if crc_ok else 'NO'}\n72 01 4b 46 7f ff 0e 10 57 t={milli}\n", encoding="ascii")

    def celsius(self, value: float) -> None:
        self._write(True, round(value * 1000))

    def just_powered_up(self) -> None:
        self._write(True, 85000)

    def bad_crc(self) -> None:
        self._write(False, 22000)

    def unplug(self) -> None:
        if self.file.exists():
            self.file.unlink()


class FanLine:
    """A libgpiod-shaped request for the line of the extraction fan: it can flap, fail to read or stay stuck."""

    def __init__(self, running: bool) -> None:
        self.running, self.broken = running, False

    def get_values(self, lines):
        if self.broken:
            raise OSError("the line cannot be read")
        return [self.running]


def job_bytes(key: str, phase: JobPhase = JobPhase.LOAD) -> bytes:
    return json.dumps(job_to_dict(BridgeJob(f"j-{key}", key, "cell-a", phase, MachineState.IDLE, {}))).encode("utf-8")


class SensorScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.tree = Ds18b20Tree(Path(self._dir.name))
        self.tree.celsius(24.0)
        self.fan = FanLine(True)
        self.chip = GpioChipEmulator()
        self.broker = MqttBrokerEmulator()
        supervisor = AuxiliarySupervisor(
            [
                AuxiliaryCheck("tube", w1_reader(DEVICE, self._dir.name), max_celsius=30.0),
                AuxiliaryCheck("extraction", gpio_level_reader("c", 4, active_low=False, request_lines=lambda *a: self.fan)),
            ]
        )
        self.bridge = LaserMqttBridge(self.chip.as_safety_lines(), controller_state=lambda: "IDLE", cell_state=lambda: CellState.READY, auxiliary=supervisor)
        self._keys = 0

    def run_job(self, phase: JobPhase = JobPhase.LOAD) -> dict:
        self._keys += 1
        self.broker.published.clear()
        self.broker.enqueue_inbound(JOB_TOPIC, job_bytes(f"k{self._keys}", phase))
        self.broker.pump(self.bridge)
        return json.loads(next(p for t, p, _ in self.broker.published if t == RESULT_TOPIC))

    def auxiliary_state(self) -> dict:
        self.broker.enqueue_inbound(STATUS_TOPIC, b"")
        self.broker.pump(self.bridge)
        return json.loads(self.broker.retained(STATE_TOPIC))["auxiliary"]

    def test_with_a_cool_tube_and_the_fan_running_the_job_is_allowed(self) -> None:
        result = self.run_job()
        self.assertTrue(result["allowed"], result.get("reason"))
        self.assertEqual(self.auxiliary_state(), {"tube": True, "extraction": True})

    def test_the_tube_heating_up_blocks_the_next_job_at_the_limit_and_cooling_lets_it_back(self) -> None:
        for celsius, allowed in ((24.0, True), (29.9, True), (30.0, True), (30.1, False), (45.0, False), (28.0, True)):
            self.tree.celsius(celsius)
            self.assertEqual(self.run_job()["allowed"], allowed, celsius)

    def test_the_power_up_value_is_not_a_measurement_and_blocks(self) -> None:
        self.tree.just_powered_up()
        result = self.run_job()
        self.assertFalse(result["allowed"])
        self.assertIn("tube", result["reason"])

    def test_a_failed_crc_and_an_unplugged_sensor_block_and_a_good_reading_recovers(self) -> None:
        self.tree.bad_crc()
        self.assertFalse(self.run_job()["allowed"])
        self.tree.unplug()
        self.assertFalse(self.run_job()["allowed"])
        self.assertEqual(self.auxiliary_state()["tube"], False)
        self.tree.celsius(25.0)
        self.assertTrue(self.run_job()["allowed"])

    def test_a_fan_that_stops_or_a_line_that_cannot_be_read_blocks_the_job(self) -> None:
        self.fan.running = False
        self.assertIn("extraction", self.run_job()["reason"])
        self.fan.running, self.fan.broken = True, True
        self.assertFalse(self.run_job()["allowed"])
        self.fan.broken = False
        self.assertTrue(self.run_job()["allowed"])

    def test_both_failing_at_once_names_both(self) -> None:
        self.tree.celsius(50.0)
        self.fan.running = False
        reason = self.run_job()["reason"]
        self.assertIn("tube", reason)
        self.assertIn("extraction", reason)

    def test_an_abort_is_never_held_back_by_an_auxiliary_safeguard(self) -> None:
        self.tree.celsius(80.0)
        self.fan.running = False
        result = self.run_job(JobPhase.ABORT)
        self.assertNotIn("auxiliary safeguard", result.get("reason", ""))

    def test_an_open_enclosure_wins_over_good_auxiliaries(self) -> None:
        self.chip.open_enclosure()
        result = self.run_job()
        self.assertFalse(result["allowed"])
        self.assertEqual(self.auxiliary_state(), {"tube": True, "extraction": True})


if __name__ == "__main__":
    unittest.main()
