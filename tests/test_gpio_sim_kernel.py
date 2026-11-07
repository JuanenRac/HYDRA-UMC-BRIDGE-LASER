# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Safeguard lines against the kernel GPIO simulator
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The three safeguard lines read through libgpiod from a chip made by the `gpio-sim` kernel module.

This is the closest a machine without the laser can get to the real path: `open_gpio_safety` asks the
kernel for a real character-device request, the test moves the level of each line through the simulator
and the bridge reads the new level and gets the edge events. It needs root, the `gpio-sim` module,
configfs and the `gpiod` Python library (libgpiod v2); when any of them is missing every case SKIPS and
says why, so the test is safe to run anywhere. It is run in the "Simulation bench" workflow on a
Linux runner and proves nothing about a real laser, a real key switch or real wiring.
"""

import os
import select
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from hydra_umc_sdk.bridge_contract import MachineState
from hydra_umc_bridge_laser import GpioSafetyProbe
from hydra_umc_bridge_laser.gpio_safety import GpioLineSettings, open_gpio_safety

CONFIGFS = Path("/sys/kernel/config")
SIM = CONFIGFS / "gpio-sim"


def _why_not() -> str | None:
    """None when the simulator can be used, else the reason it cannot."""

    if not sys.platform.startswith("linux"):
        return "not a Linux host"
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return "needs root to create the simulated chip"
    try:
        import gpiod  # noqa: F401
        from gpiod.line import Bias, Direction, Edge, Value  # noqa: F401
    except ImportError:
        return "the gpiod library (libgpiod v2) is not installed"
    if not SIM.is_dir():
        if shutil.which("modprobe"):
            subprocess.run(["modprobe", "gpio-sim"], capture_output=True, check=False)
        if not CONFIGFS.is_dir() or not any(CONFIGFS.iterdir()):
            subprocess.run(["mount", "-t", "configfs", "none", str(CONFIGFS)], capture_output=True, check=False)
    if not SIM.is_dir():
        return "the gpio-sim kernel module is not available on this kernel"
    return None


class SimulatedChip:
    """One chip of `gpio-sim` with a few lines; the level of a line is set through its pull."""

    def __init__(self, lines: int = 4):
        self.name = "hydra-" + uuid.uuid4().hex[:8]
        self.dir = SIM / self.name
        self.dir.mkdir()
        bank = self.dir / "bank0"
        bank.mkdir()
        (bank / "num_lines").write_text(str(lines))
        (self.dir / "live").write_text("1")
        self.chip_name = (bank / "chip_name").read_text().strip()
        self.device = (self.dir / "dev_name").read_text().strip()
        self.path = "/dev/" + self.chip_name

    def pull(self, offset: int, level: bool) -> None:
        line = Path("/sys/devices/platform") / self.device / self.chip_name / f"sim_gpio{offset}" / "pull"
        line.write_text("pull-up" if level else "pull-down")

    def close(self) -> None:
        try:
            (self.dir / "live").write_text("0")
        except OSError:
            pass
        for path in (self.dir / "bank0", self.dir):
            try:
                path.rmdir()
            except OSError:
                pass


_REASON = _why_not()


@unittest.skipIf(_REASON is not None, _REASON or "")
class KernelGpioSimTests(unittest.TestCase):
    def setUp(self):
        self.chip = SimulatedChip()
        self.addCleanup(self.chip.close)
        self.opened = []

    def _open(self, **wiring):
        settings = GpioLineSettings(active_low=wiring.get("active_low", False), bias="as-is", debounce_ms=0)
        safety = open_gpio_safety(self.chip.path, 0, 1, 2, key=settings, enclosure=settings, interlock=settings)
        self.addCleanup(safety.watcher.close)
        return safety

    def test_each_line_follows_the_level_set_in_the_simulator(self):
        for offset in range(3):
            self.chip.pull(offset, True)
        safety = self._open()
        self.assertEqual(safety.lines.read_all(), (True, True, True))
        self.chip.pull(1, False)
        self.assertEqual(safety.lines.read_all(), (True, False, True))
        self.chip.pull(1, True)
        self.chip.pull(2, False)
        self.assertEqual(safety.lines.read_all(), (True, True, False))

    def test_an_active_low_wiring_reads_a_low_level_as_safe(self):
        for offset in range(3):
            self.chip.pull(offset, False)
        safety = self._open(active_low=True)
        self.assertEqual(safety.lines.read_all(), (True, True, True))
        self.chip.pull(0, True)
        self.assertEqual(safety.lines.read_all(), (False, True, True))

    def test_the_probe_gates_on_the_simulated_levels(self):
        for offset in range(3):
            self.chip.pull(offset, True)
        safety = self._open()
        probe = GpioSafetyProbe()
        snapshot = probe.read_snapshot("IDLE", safety.lines)
        self.assertEqual(snapshot.machine_state(), MachineState.IDLE)
        self.chip.pull(2, False)
        snapshot = probe.read_snapshot("IDLE", safety.lines)
        self.assertFalse(snapshot.interlock_healthy)
        self.assertNotEqual(snapshot.machine_state(), MachineState.IDLE)

    def test_an_edge_wakes_the_watcher_and_a_steady_line_does_not(self):
        for offset in range(3):
            self.chip.pull(offset, True)
        safety = self._open()
        readable, _, _ = select.select([safety.watcher.fd], [], [], 0.2)
        self.assertFalse(readable)
        self.chip.pull(0, False)
        readable, _, _ = select.select([safety.watcher.fd], [], [], 2.0)
        self.assertTrue(readable)
        self.assertTrue(safety.watcher.read_edge_events())

    def test_the_same_lines_cannot_be_requested_twice(self):
        for offset in range(3):
            self.chip.pull(offset, True)
        self._open()
        with self.assertRaises((OSError, RuntimeError)):
            self._open()


class SimulatorAvailabilityTests(unittest.TestCase):
    """Runs everywhere: the guard that decides whether the kernel cases run gives a reason or nothing."""

    def test_the_reason_is_text_or_none(self):
        self.assertTrue(_REASON is None or (isinstance(_REASON, str) and _REASON))


if __name__ == "__main__":
    unittest.main()
