# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Read-only GRBL laser state tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The GRBL reader against an in-memory laser controller that talks the way GRBL does (banner, ok, stale answers)."""

import json
import unittest

from hydra_umc_sdk.bridge_contract import BridgeJob, CellState, JobPhase, MachineState, job_to_dict
from hydra_umc_bridge_laser import GpioSafetyLines, GrblLaserState, LaserMqttBridge, open_grbl_laser_state
from hydra_umc_bridge_laser.mqtt_transport import TOPIC_PREFIX
from hydra_umc_sdk.serial_link import ReconnectingSerialConnection


class FakeGrblLaser:
    """A GRBL laser board over the SerialLike seam: it answers only what it is asked and talks unasked, like the real one."""

    def __init__(self, state="Idle", power=0, feed=0):
        self.state, self.power, self.feed = state, power, feed
        self.written: list[bytes] = []
        self.pending: list[bytes] = [b"Grbl 1.1h ['$' for help]\r\n", b"[MSG:'$H'|'$X' to unlock]\r\n"]
        self.fail = False
        self.silent = False

    def write(self, data: bytes) -> int:
        if self.fail:
            raise OSError("unplugged")
        self.written.append(data)
        if data == b"?" and not self.silent:
            self.pending.append(f"<{self.state}|MPos:0.000,0.000,0.000|FS:{self.feed},{self.power}>\r\n".encode())
        return len(data)

    def readline(self) -> bytes:
        return self.pending.pop(0) if self.pending else b""

    def reset_input_buffer(self) -> None:
        # what was waiting before the question is gone
        self.pending.clear()

    @property
    def in_waiting(self) -> int:
        return sum(len(line) for line in self.pending)

    def close(self) -> None:
        pass


class Line:
    def __init__(self, value=True):
        self.value = value

    def read(self):
        return self.value


def laser_bridge(reader, key=True, enclosure=True, interlock=True):
    return LaserMqttBridge(GpioSafetyLines(Line(key), Line(enclosure), Line(interlock)), reader, lambda: CellState.READY)


def job(phase=JobPhase.LOAD):
    return BridgeJob("j-1", "k-1", "orchestrator", phase, MachineState.IDLE, {})


class GrblLaserStateTests(unittest.TestCase):
    def test_the_state_word_is_the_one_of_the_status_report(self):
        for word in ("Idle", "Run", "Hold:0", "Alarm:1", "Door:1", "Jog"):
            with self.subTest(word=word):
                self.assertEqual(GrblLaserState(FakeGrblLaser(word))(), word)

    def test_the_only_byte_ever_written_is_the_status_query(self):
        laser = FakeGrblLaser()
        reader = GrblLaserState(laser)
        reader()
        reader()
        self.assertEqual(laser.written, [b"?", b"?"])

    def test_the_banner_and_messages_the_board_sends_unasked_are_not_the_answer(self):
        laser = FakeGrblLaser("Run")
        self.assertEqual(GrblLaserState(laser)(), "Run")

    def test_a_board_that_does_not_answer_is_an_empty_state_never_idle(self):
        laser = FakeGrblLaser()
        laser.silent = True
        self.assertEqual(GrblLaserState(laser)(), "")
        self.assertIsNone(GrblLaserState(laser).last_report())

    def test_a_dead_link_is_an_empty_state(self):
        laser = FakeGrblLaser()
        laser.fail = True
        reader = GrblLaserState(laser)
        self.assertEqual(reader(), "")
        self.assertIsNone(reader.last_report())

    def test_the_report_keeps_the_laser_power_and_the_feed(self):
        reader = GrblLaserState(FakeGrblLaser("Run", power=800, feed=1200))
        reader()
        report = reader.last_report()
        self.assertEqual((report.spindle_speed, report.feed_rate), (800.0, 1200.0))

    def test_a_failed_query_forgets_the_last_report(self):
        laser = FakeGrblLaser("Run", power=800, feed=1200)
        reader = GrblLaserState(laser)
        reader()
        laser.fail = True
        reader()
        self.assertIsNone(reader.last_report())

    def test_it_survives_a_replug_through_the_reconnecting_connection(self):
        first = FakeGrblLaser()
        first.fail = True
        second = FakeGrblLaser("Hold:0")
        connections = [first, second]
        reader = GrblLaserState(ReconnectingSerialConnection(lambda: connections.pop(0)))
        self.assertEqual(reader(), "Hold:0")

    def test_open_without_pyserial_is_a_clear_error_on_first_use(self):
        try:
            import serial  # noqa: F401

            self.skipTest("pyserial is installed in this environment")
        except ImportError:
            pass
        reader = open_grbl_laser_state("COM9")
        self.assertEqual(reader(), "")  # the link failure is a state that is not known, not an exception


class BridgeWithAGrblReaderTests(unittest.TestCase):
    def status(self, bridge):
        return json.loads(bridge.handle_message(f"{TOPIC_PREFIX}cmd/status", b"")[0].payload)

    def test_the_machine_state_comes_from_the_controller(self):
        payload = self.status(laser_bridge(GrblLaserState(FakeGrblLaser("Idle"))))
        self.assertEqual(payload["controller_state"], "Idle")
        self.assertEqual(payload["machine_state"], "IDLE")

    def test_an_alarm_is_a_fault_and_a_hold_is_holding(self):
        self.assertEqual(self.status(laser_bridge(GrblLaserState(FakeGrblLaser("Alarm:1"))))["machine_state"], "FAULT")
        self.assertEqual(self.status(laser_bridge(GrblLaserState(FakeGrblLaser("Hold:0"))))["machine_state"], "HOLDING")

    def test_the_laser_power_is_information_in_the_state(self):
        payload = self.status(laser_bridge(GrblLaserState(FakeGrblLaser("Run", power=500, feed=300))))
        self.assertEqual(payload["laser_power"], 500.0)
        self.assertEqual(payload["feed_rate"], 300.0)

    def test_a_plain_callable_adds_nothing_to_the_state(self):
        payload = self.status(laser_bridge(lambda: "Idle"))
        self.assertNotIn("laser_power", payload)

    def test_a_silent_controller_never_lets_a_job_through(self):
        laser = FakeGrblLaser()
        laser.silent = True
        bridge = laser_bridge(GrblLaserState(laser))
        answer = json.loads(bridge.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode())[0].payload)
        self.assertFalse(answer["allowed"])

    def test_a_running_laser_keeps_the_arm_out_and_an_idle_one_lets_it_in(self):
        running = laser_bridge(GrblLaserState(FakeGrblLaser("Run")))
        answer = json.loads(running.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode())[0].payload)
        self.assertFalse(answer["allowed"])
        idle = laser_bridge(GrblLaserState(FakeGrblLaser("Idle")))
        answer = json.loads(idle.handle_message(f"{TOPIC_PREFIX}cmd/job", json.dumps(job_to_dict(job())).encode())[0].payload)
        self.assertTrue(answer["allowed"])

    def test_the_gpio_safeguards_still_decide_whatever_the_controller_says(self):
        payload = self.status(laser_bridge(GrblLaserState(FakeGrblLaser("Idle")), enclosure=False))
        self.assertEqual(payload["machine_state"], "SAFE_STOP")

    def test_a_reader_that_raises_in_last_report_does_not_stop_the_state(self):
        class Broken:
            def __call__(self):
                return "Idle"

            def last_report(self):
                raise RuntimeError("broken")

        self.assertEqual(self.status(laser_bridge(Broken()))["machine_state"], "IDLE")


if __name__ == "__main__":
    unittest.main()
