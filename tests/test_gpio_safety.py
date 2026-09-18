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
from hydra_umc_bridge_laser.gpio_safety import watch_for_interlock_edges


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


class OpenGpioEdgeWatcherTests(unittest.TestCase):
    def test_missing_gpiod_raises_a_clear_runtime_error_not_an_import_error(self):
        from hydra_umc_bridge_laser import open_gpio_edge_watcher

        try:
            import gpiod  # noqa: F401

            self.skipTest("gpiod is installed in this environment - nothing to prove here")
        except ImportError:
            pass
        with self.assertRaises(RuntimeError) as context:
            open_gpio_edge_watcher("/dev/gpiochip0", 0, 1, 2)
        self.assertIn("gpiod is not installed", str(context.exception))


class FakeEdgeSource:
    """A minimal, deterministic stand-in for a real libgpiod v2 LineRequest
    opened for edge events - only the fd/read_edge_events() shape
    `watch_for_interlock_edges()` actually depends on."""

    def __init__(self, event_batches: list[list[object]]):
        # Each call to read_edge_events() pops the next batch - an empty
        # list is a real, legal (if unusual) libgpiod return: the fd woke
        # up readable but nothing new was actually queued by the time it
        # was read.
        self._event_batches = list(event_batches)
        self.fd = 7
        self.closed = False

    def read_edge_events(self) -> list[object]:
        return self._event_batches.pop(0) if self._event_batches else []

    def close(self) -> object:
        self.closed = True


class WatchForInterlockEdgesTests(unittest.TestCase):
    def test_a_real_edge_event_batch_triggers_on_change_exactly_once_per_batch(self):
        source = FakeEdgeSource([["edge-1"], ["edge-2", "edge-3"]])
        calls = []
        # poll() reports "readable" for exactly the 2 real batches, then
        # tells the loop to stop - proving on_change() fires once per
        # real batch of kernel-reported events, not once per event.
        polls = iter([True, True, False])

        def fake_poll(fd: int, timeout):
            self.assertEqual(fd, source.fd)
            return next(polls)

        should_stop_calls = {"n": 0}

        def should_stop() -> bool:
            should_stop_calls["n"] += 1
            return should_stop_calls["n"] > 3

        watch_for_interlock_edges(
            source, lambda: calls.append(1), poll=fake_poll, should_stop=should_stop, timeout_seconds=0.01
        )
        self.assertEqual(len(calls), 2)

    def test_a_poll_timeout_with_no_event_never_calls_on_change(self):
        source = FakeEdgeSource([])
        calls = []
        polls = iter([False, False, False])

        def fake_poll(fd: int, timeout):
            return next(polls, None)

        should_stop_calls = {"n": 0}

        def should_stop() -> bool:
            should_stop_calls["n"] += 1
            return should_stop_calls["n"] > 3

        watch_for_interlock_edges(source, lambda: calls.append(1), poll=fake_poll, should_stop=should_stop)
        self.assertEqual(calls, [])

    def test_an_empty_event_batch_on_a_readable_fd_does_not_call_on_change(self):
        # A real, if unusual, libgpiod outcome: the fd was readable but
        # read_edge_events() returned nothing new to report.
        source = FakeEdgeSource([[]])
        calls = []
        polls = iter([True, False])

        def fake_poll(fd: int, timeout):
            return next(polls)

        should_stop_calls = {"n": 0}

        def should_stop() -> bool:
            should_stop_calls["n"] += 1
            return should_stop_calls["n"] > 2

        watch_for_interlock_edges(source, lambda: calls.append(1), poll=fake_poll, should_stop=should_stop)
        self.assertEqual(calls, [])

    def test_should_stop_true_from_the_start_never_polls_at_all(self):
        source = FakeEdgeSource([["edge"]])
        calls = []
        watch_for_interlock_edges(
            source, lambda: calls.append(1), poll=lambda fd, timeout: True, should_stop=lambda: True
        )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
