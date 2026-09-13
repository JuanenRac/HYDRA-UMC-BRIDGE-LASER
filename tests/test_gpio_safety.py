# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Real GPIO safeguard reading tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Tests the real GPIO safeguard reader against fake line readers.

No real GPIO chip or gpiod install is needed: GpioSafetyProbe is written
against the small GpioLineReader interface, so a plain fake proves the
reading/gating logic is correct independent of gpiod - only
open_gpio_safety_lines() itself needs gpiod, and it isn't exercised here
(see its own docstring).
"""

import unittest

from hydra_umc_sdk.bridge_contract import MachineState
from hydra_umc_bridge_laser import GpioLineReader, GpioSafetyLines, GpioSafetyProbe


class FakeLine:
    def __init__(self, value: bool = True):
        self.value = value
        self.raise_on_read: OSError | None = None

    def read(self) -> bool:
        if self.raise_on_read:
            raise self.raise_on_read
        return self.value


class GpioSafetyProbeTests(unittest.TestCase):
    def test_all_three_safeguards_true_reports_the_controller_state_through(self):
        lines = GpioSafetyLines(FakeLine(True), FakeLine(True), FakeLine(True))
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", lines)
        self.assertTrue(snapshot.key_enabled)
        self.assertTrue(snapshot.enclosure_closed)
        self.assertTrue(snapshot.interlock_healthy)
        self.assertEqual(snapshot.machine_state(), MachineState.IDLE)

    def test_a_single_false_safeguard_forces_safe_stop_regardless_of_controller_state(self):
        lines = GpioSafetyLines(FakeLine(True), FakeLine(False), FakeLine(True))
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", lines)
        self.assertFalse(snapshot.enclosure_closed)
        self.assertEqual(snapshot.machine_state(), MachineState.SAFE_STOP)

    def test_a_gpio_read_failure_fails_closed_on_all_three_safeguards(self):
        key = FakeLine(True)
        enclosure = FakeLine(True)
        interlock = FakeLine(True)
        interlock.raise_on_read = OSError("gpio chip unavailable")
        lines = GpioSafetyLines(key, enclosure, interlock)
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", lines)
        self.assertFalse(snapshot.key_enabled)
        self.assertFalse(snapshot.enclosure_closed)
        self.assertFalse(snapshot.interlock_healthy)
        self.assertEqual(snapshot.machine_state(), MachineState.SAFE_STOP)


class GpioLineReaderProtocolTests(unittest.TestCase):
    def test_a_real_line_reader_satisfies_the_protocol_structurally(self):
        # H004: GpioLineReader is a real typing.Protocol now, not a base
        # class with a NotImplementedError body - FakeLine never inherits
        # from it, so this isinstance() check only passes because the
        # Protocol is genuinely structural (and @runtime_checkable).
        self.assertIsInstance(FakeLine(True), GpioLineReader)

    def test_the_protocol_itself_cannot_be_instantiated(self):
        # The old base-class form COULD be instantiated directly and would
        # look like a usable (if broken) implementation. A real Protocol
        # has no body to instantiate at all - this is the actual defect
        # H004 asked to close.
        with self.assertRaises(TypeError):
            GpioLineReader()

    def test_an_object_missing_read_does_not_satisfy_the_protocol(self):
        class NotALine:
            pass

        self.assertNotIsInstance(NotALine(), GpioLineReader)


class OpenGpioSafetyLinesTests(unittest.TestCase):
    def test_missing_gpiod_raises_a_clear_runtime_error_not_an_import_error(self):
        from hydra_umc_bridge_laser import open_gpio_safety_lines

        try:
            import gpiod  # noqa: F401

            self.skipTest("gpiod is installed in this environment - nothing to prove here")
        except ImportError:
            pass
        with self.assertRaises(RuntimeError) as context:
            open_gpio_safety_lines("/dev/gpiochip0", 0, 1, 2)
        self.assertIn("gpiod is not installed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
