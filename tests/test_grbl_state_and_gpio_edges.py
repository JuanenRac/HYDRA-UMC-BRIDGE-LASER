# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - the edges of the GRBL state reader and of the GPIO input reader
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The GRBL reader fails closed (no answer is an empty state) and only ever writes the status query; the GPIO reader opens the real library
only through gpiod, which here is a small fake, and a missing library is an error at start."""

import sys
import types
import unittest
from unittest import mock

from hydra_umc_bridge_laser import grbl_state
from hydra_umc_bridge_laser.auxiliary_inputs import gpio_level_reader
from hydra_umc_bridge_laser.grbl_state import GrblLaserState, open_grbl_laser_state


class Port:
    """A serial port that answers GRBL's status query with the lines it was given."""

    def __init__(self, lines=(), fail=None):
        self.lines, self.fail, self.written, self.closed = list(lines), fail, [], False

    def write(self, data):
        if self.fail:
            raise self.fail
        self.written.append(bytes(data))
        return len(data)

    def readline(self):
        if self.fail:
            raise self.fail
        return self.lines.pop(0) if self.lines else b""

    def reset_input_buffer(self):
        pass

    def close(self):
        self.closed = True


class GrblStateTests(unittest.TestCase):
    def test_an_answered_query_gives_the_state_word_and_keeps_the_report(self):
        reader = GrblLaserState(Port([b"<Idle|MPos:0.000,0.000,0.000|FS:0,0>\r\n"]))
        self.assertEqual(reader(), "Idle")
        self.assertIsNotNone(reader.last_report())
        self.assertEqual(reader.last_report().state, "Idle")

    def test_a_link_that_fails_gives_an_empty_state_and_forgets_the_last_report(self):
        port = Port([b"<Run|FS:500,80>\r\n"])
        reader = GrblLaserState(port)
        self.assertEqual(reader(), "Run")
        port.fail = OSError("cable pulled")
        self.assertEqual(reader(), "")
        self.assertIsNone(reader.read_report())
        self.assertIsNone(reader.last_report())

    def test_a_silent_controller_gives_an_empty_state(self):
        reader = GrblLaserState(Port([]))
        self.assertEqual(reader(), "")
        self.assertIsNone(reader.last_report())

    def test_the_only_byte_written_is_the_status_query(self):
        port = Port([b"<Idle|FS:0,0>\r\n", b"<Alarm:1|FS:0,0>\r\n"])
        reader = GrblLaserState(port)
        reader()
        reader()
        self.assertTrue(port.written)
        self.assertEqual({chunk.strip() for chunk in port.written}, {b"?"})

    def test_closing_closes_the_connection_and_a_connection_without_close_is_fine(self):
        port = Port()
        GrblLaserState(port).close()
        self.assertTrue(port.closed)
        GrblLaserState(object()).close()  # nothing to close, nothing raised


class OpenStateTests(unittest.TestCase):
    def _open(self, device, **kwargs):
        calls = []

        def by_id(*args, **options):
            calls.append(("by_id", args, options))
            return Port()

        def by_name(*args, **options):
            calls.append(("by_name", args, options))
            return Port()

        with mock.patch.object(grbl_state, "open_serial_port_by_id", by_id), mock.patch.object(grbl_state, "open_serial_port", by_name):
            reader = open_grbl_laser_state(device, **kwargs)
            reader.read_report()
        return calls

    def test_a_device_id_is_looked_up_first(self):
        calls = self._open("ABC123", baud=57600, timeout_seconds=0.5)
        self.assertEqual(calls[0][0], "by_id")
        self.assertEqual(calls[0][1], ("ABC123",))
        self.assertEqual((calls[0][2]["baud"], calls[0][2]["timeout_seconds"]), (57600, 0.5))

    def test_a_name_that_is_not_an_id_falls_back_to_the_port_name(self):
        def refuse_by_id(*args, **options):
            raise RuntimeError("no such device id")

        opened = []
        with mock.patch.object(grbl_state, "open_serial_port_by_id", refuse_by_id), mock.patch.object(
            grbl_state, "open_serial_port", lambda *a, **k: opened.append((a, k)) or Port()
        ):
            open_grbl_laser_state("COM7").read_report()
        self.assertEqual(opened[0][0], ("COM7",))

    def test_with_a_port_list_given_the_failure_is_not_hidden_by_the_fallback(self):
        def refuse_by_id(*args, **options):
            raise RuntimeError("no such device id")

        with mock.patch.object(grbl_state, "open_serial_port_by_id", refuse_by_id), mock.patch.object(grbl_state, "open_serial_port", side_effect=AssertionError("fallback used")):
            reader = open_grbl_laser_state("X", list_ports=lambda: [])
            # the reconnecting connection reports the failure as an unreadable state, never as a crash
            self.assertEqual(reader(), "")


class FakeGpiod:
    """Just enough of libgpiod 2 for the reader: line settings, a request and the values."""

    ACTIVE = "active"

    def __init__(self, levels):
        self.levels, self.requests = levels, []

    def modules(self):
        gpiod = types.ModuleType("gpiod")
        line = types.ModuleType("gpiod.line")
        line.Bias = types.SimpleNamespace(PULL_UP="up", PULL_DOWN="down", DISABLED="off", AS_IS="as-is")
        line.Direction = types.SimpleNamespace(INPUT="input")
        line.Value = types.SimpleNamespace(ACTIVE=self.ACTIVE, INACTIVE="inactive")
        gpiod.line = line
        gpiod.LineSettings = lambda **settings: types.SimpleNamespace(**settings)

        def request_lines(chip, consumer, config):
            self.requests.append((chip, consumer, config))
            return types.SimpleNamespace(get_values=lambda lines: [self.levels.pop(0)])

        gpiod.request_lines = request_lines
        return {"gpiod": gpiod, "gpiod.line": line}


class GpioReaderTests(unittest.TestCase):
    def test_the_real_library_is_asked_for_an_input_line_with_the_bias_and_polarity(self):
        fake = FakeGpiod([FakeGpiod.ACTIVE, "inactive"])
        with mock.patch.dict(sys.modules, fake.modules()):
            read = gpio_level_reader("/dev/gpiochip0", 17, active_low=True, bias="pull-up")
        chip, consumer, config = fake.requests[0]
        self.assertEqual((chip, consumer), ("/dev/gpiochip0", "hydra-umc-bridge-laser-aux"))
        settings = config[17]
        self.assertEqual((settings.direction, settings.bias, settings.active_low), ("input", "up", True))
        self.assertTrue(read())
        self.assertFalse(read())

    def test_every_bias_is_mapped_to_the_library_constant(self):
        for name, constant in (("pull-up", "up"), ("pull-down", "down"), ("disabled", "off"), ("as-is", "as-is")):
            fake = FakeGpiod([FakeGpiod.ACTIVE])
            with mock.patch.dict(sys.modules, fake.modules()):
                gpio_level_reader("chip", 3, active_low=False, bias=name)
            self.assertEqual(fake.requests[0][2][3].bias, constant)

    def test_a_missing_library_is_an_error_at_start_and_not_a_silent_pass(self):
        with mock.patch.dict(sys.modules, {"gpiod": None, "gpiod.line": None}):
            with self.assertRaises(RuntimeError) as caught:
                gpio_level_reader("chip", 1, active_low=False)
        self.assertIn("gpiod is not installed", str(caught.exception))

    def test_an_unknown_bias_is_refused_before_anything_is_opened(self):
        with self.assertRaises(ValueError):
            gpio_level_reader("chip", 1, active_low=False, bias="floating")


if __name__ == "__main__":
    unittest.main()
