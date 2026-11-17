# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - tests/test_auxiliary_age_and_channels.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The age limit of an auxiliary safeguard file, and every combination of the two contacts of the three safeguards.

Evidence: simulator (fake line readers; no contact was wired).
"""

import itertools
import os
import tempfile
import tomllib
import unittest

from hydra_umc_bridge_laser import GpioSafetyLines, GpioSafetyProbe
from hydra_umc_bridge_laser.gpio_safety import SAFEGUARDS, with_complements
from hydra_umc_bridge_laser.service import AuxiliaryConfig, ConfigError, auxiliary_supervisor, parse_config

MINIMAL_GPIO = """
[gpio]
chip = "/dev/gpiochip0"
[gpio.key]
line = 4
active_low = false
[gpio.enclosure]
line = 5
active_low = false
[gpio.interlock]
line = 6
active_low = false
"""


class Line:
    def __init__(self, value):
        self.value = value

    def read(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def parse(text: str):
    return parse_config(tomllib.loads(text))


def config_text(extra: str) -> str:
    return MINIMAL_GPIO + extra


class AuxiliaryAgeTests(unittest.TestCase):
    def _supervisor(self, path: str, max_age: float, now: float):
        item = AuxiliaryConfig("extraction", path=path, max_age_seconds=max_age)
        supervisor = auxiliary_supervisor([item], clock=lambda: now)
        assert supervisor is not None
        return supervisor

    def test_a_file_is_satisfied_only_while_it_is_younger_than_its_own_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "extraction")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("1\n")
            written = os.stat(path).st_mtime
            for max_age, now, satisfied in [(30, written + 20, True), (30, written + 40, False), (120, written + 100, True), (5, written + 6, False)]:
                supervisor = self._supervisor(path, max_age, now)
                self.assertEqual(supervisor.evaluate()["extraction"], satisfied, (max_age, now - written))

    def test_the_default_stays_thirty_seconds(self):
        self.assertEqual(AuxiliaryConfig("x", path="p").max_age_seconds, 30.0)
        config = parse(config_text('[[auxiliary]]\nname = "extraction"\npath = "/run/x"\n'))
        self.assertEqual(config.auxiliary[0].max_age_seconds, 30.0)

    def test_the_limit_is_read_from_the_file_and_must_be_a_positive_finite_number(self):
        config = parse(config_text('[[auxiliary]]\nname = "extraction"\npath = "/run/x"\nmax_age_seconds = 90\n'))
        self.assertEqual(config.auxiliary[0].max_age_seconds, 90.0)
        for bad in ("0", "-5", "nan", "inf", '"soon"', "true"):
            with self.assertRaises(ConfigError, msg=bad):
                parse(config_text(f'[[auxiliary]]\nname = "extraction"\npath = "/run/x"\nmax_age_seconds = {bad}\n'))

    def test_nan_or_inf_cannot_switch_off_the_staleness_of_the_cell_state_file(self):
        for bad in ("nan", "inf", "0", "-1"):
            with self.assertRaises(ConfigError, msg=bad):
                parse(config_text(f'[cell_state]\nsource = "file"\npath = "/run/cell"\nmax_age_seconds = {bad}\n'))


class TwoChannelProperty(unittest.TestCase):
    def _lines(self, primary, complement):
        lines = GpioSafetyLines(Line(primary[0]), Line(primary[1]), Line(primary[2]))
        return with_complements(lines, {name: Line(value) for name, value in zip(SAFEGUARDS, complement, strict=True)})

    def test_every_combination_of_the_six_contacts(self):
        probe = GpioSafetyProbe()
        for values in itertools.product([False, True], repeat=6):
            primary, complement = values[:3], values[3:]
            lines = self._lines(primary, complement)
            expected = tuple(p and c for p, c in zip(primary, complement, strict=True))
            snapshot = probe.read_snapshot("IDLE", lines)
            self.assertEqual((snapshot.key_enabled, snapshot.enclosure_closed, snapshot.interlock_healthy), expected, values)
            # the same through the single read of the three lines
            single = GpioSafetyLines(Line(True), Line(True), Line(True), read_all=lambda p=primary: p)
            combined = with_complements(single, {name: Line(value) for name, value in zip(SAFEGUARDS, complement, strict=True)})
            again = probe.read_snapshot("IDLE", combined)
            self.assertEqual((again.key_enabled, again.enclosure_closed, again.interlock_healthy), expected, values)

    def test_a_reader_that_raises_never_leaves_a_safeguard_satisfied(self):
        probe = GpioSafetyProbe()
        for broken in range(6):
            values: list = [True] * 6
            values[broken] = OSError("line released")
            lines = self._lines(values[:3], values[3:])
            snapshot = probe.read_snapshot("IDLE", lines)
            self.assertEqual((snapshot.key_enabled, snapshot.enclosure_closed, snapshot.interlock_healthy), (False, False, False), broken)


if __name__ == "__main__":
    unittest.main()
