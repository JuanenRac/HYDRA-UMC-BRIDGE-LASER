# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - tests/test_two_channel_safeguards.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""A safeguard wired with two contacts (normally-closed plus normally-open) is satisfied only when both agree.

Evidence: simulator (a fake libgpiod and fake lines; no contact was wired).
"""

import json
import sys
import types
import unittest
from unittest import mock

from hydra_umc_bridge_laser import GpioLineSettings, GpioSafetyLines, GpioSafetyProbe, open_gpio_safety
from hydra_umc_bridge_laser.gpio_safety import with_complements
from hydra_umc_bridge_laser.service import ConfigError, build_bridge, parse_config

LOGGER = "hydra_umc_bridge_laser.gpio_safety"


class Line:
    def __init__(self, value=True):
        self.value = value

    def read(self):
        return self.value


class FakeSettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeRequest:
    def __init__(self, config, levels):
        self.config = config
        self.levels = levels
        self.fd = 9
        self.calls = []

    def get_values(self, offsets):
        self.calls.append(list(offsets))
        return ["ACTIVE" if self.levels[offset] else "INACTIVE" for offset in offsets]

    def read_edge_events(self):
        return []

    def release(self):
        return None


def fake_gpiod(levels):
    requests = []
    gpiod = types.ModuleType("gpiod")
    gpiod.LineSettings = FakeSettings

    def request_lines(chip_path, consumer, config):
        request = FakeRequest(config, levels)
        requests.append(request)
        return request

    gpiod.request_lines = request_lines
    line = types.ModuleType("gpiod.line")
    line.Bias = types.SimpleNamespace(PULL_UP="PULL_UP", PULL_DOWN="PULL_DOWN", DISABLED="DISABLED", AS_IS="AS_IS")
    line.Direction = types.SimpleNamespace(INPUT="INPUT")
    line.Edge = types.SimpleNamespace(BOTH="BOTH")
    line.Value = types.SimpleNamespace(ACTIVE="ACTIVE", INACTIVE="INACTIVE")
    return {"gpiod": gpiod, "gpiod.line": line}, requests


class WrapperTests(unittest.TestCase):
    def lines(self):
        return GpioSafetyLines(Line(True), Line(True), Line(True))

    def test_both_contacts_saying_safe_is_safe(self):
        lines = with_complements(self.lines(), {"enclosure": Line(True)})
        self.assertTrue(lines.enclosure_closed.read())
        self.assertEqual(lines.read_all(), (True, True, True))

    def test_the_two_contacts_disagreeing_is_not_safe_and_is_reported(self):
        for main_says, other_says in ((True, False), (False, True)):
            seen = []
            base = GpioSafetyLines(Line(True), Line(main_says), Line(True))
            lines = with_complements(base, {"enclosure": Line(other_says)}, (lambda *args, sink=seen: sink.append(args)))
            self.assertFalse(lines.enclosure_closed.read())
            self.assertEqual(lines.read_all(), (True, False, True))
            self.assertEqual(seen[0], ("enclosure", main_says, other_says))

    def test_both_contacts_saying_unsafe_is_unsafe_without_a_fault(self):
        seen = []
        base = GpioSafetyLines(Line(False), Line(True), Line(True))
        lines = with_complements(base, {"key": Line(False)}, lambda *args: seen.append(args))
        self.assertFalse(lines.key_enabled.read())
        self.assertEqual(seen, [])

    def test_a_safeguard_without_a_second_contact_reads_as_before(self):
        base = GpioSafetyLines(Line(True), Line(False), Line(True))
        lines = with_complements(base, {"key": Line(True)})
        self.assertFalse(lines.enclosure_closed.read())
        self.assertTrue(lines.interlock_healthy.read())

    def test_the_combined_lines_use_the_single_read_of_the_base_when_it_has_one(self):
        calls = []
        base = GpioSafetyLines(Line(), Line(), Line(), read_all=lambda: calls.append(1) or (True, True, False))
        lines = with_complements(base, {"interlock": Line(False)})
        self.assertEqual(lines.read_all(), (True, True, False))
        self.assertEqual(calls, [1])

    def test_a_failing_second_contact_makes_the_probe_fail_closed(self):
        class Broken:
            def read(self):
                raise OSError("expander gone")

        lines = with_complements(self.lines(), {"key": Broken()})
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", lines)
        self.assertEqual((snapshot.key_enabled, snapshot.enclosure_closed, snapshot.interlock_healthy), (False, False, False))

    def test_only_the_three_safeguards_can_have_a_second_contact(self):
        with self.assertRaises(ValueError):
            with_complements(self.lines(), {"laser": Line()})


class OpenTests(unittest.TestCase):
    def open(self, levels, complements):
        modules, requests = fake_gpiod(levels)
        wiring = GpioLineSettings(active_low=True)
        with mock.patch.dict(sys.modules, modules):
            safety = open_gpio_safety("/dev/gpiochip0", 4, 5, 6, key=wiring, enclosure=wiring, interlock=wiring, complements=complements)
        return safety, requests

    def test_all_the_lines_are_one_request_and_one_read(self):
        levels = {4: True, 5: True, 6: True, 14: True}
        safety, requests = self.open(levels, {"key": (14, GpioLineSettings(active_low=False))})
        self.assertEqual(len(requests), 1)
        self.assertEqual(set(requests[0].config), {4, 5, 6, 14})
        self.assertEqual(requests[0].config[14].active_low, False)
        snapshot = GpioSafetyProbe().read_snapshot("IDLE", safety.lines)
        self.assertTrue(snapshot.key_enabled)
        self.assertEqual(requests[0].calls, [[4, 5, 6, 14]])

    def test_a_disagreement_reads_unsafe_is_logged_once_and_clears(self):
        levels = {4: True, 5: True, 6: True, 14: False}
        safety, _ = self.open(levels, {"key": (14, GpioLineSettings(active_low=False))})
        with self.assertLogs(LOGGER, level="WARNING") as logged:
            self.assertEqual(safety.lines.read_all(), (False, True, True))
            self.assertEqual(safety.lines.read_all(), (False, True, True))
        self.assertEqual(len(logged.records), 1, "one warning per episode, not one per reading")
        levels[14] = True
        self.assertEqual(safety.lines.read_all(), (True, True, True))
        levels[14] = False
        with self.assertLogs(LOGGER, level="WARNING"):
            safety.lines.read_all()

    def test_without_complements_the_request_is_the_same_as_before(self):
        levels = {4: True, 5: False, 6: True}
        safety, requests = self.open(levels, None)
        self.assertEqual(set(requests[0].config), {4, 5, 6})
        self.assertEqual(safety.lines.read_all(), (True, False, True))
        self.assertEqual(requests[0].calls, [[4, 5, 6]])

    def test_repeated_or_unknown_lines_are_refused(self):
        modules, _ = fake_gpiod({})
        wiring = GpioLineSettings(active_low=True)
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(ValueError):
                open_gpio_safety("/dev/gpiochip0", 4, 5, 6, key=wiring, enclosure=wiring, interlock=wiring, complements={"key": (5, wiring)})
            with self.assertRaises(ValueError):
                open_gpio_safety("/dev/gpiochip0", 4, 5, 6, key=wiring, enclosure=wiring, interlock=wiring, complements={"door": (9, wiring)})


MINIMAL = {
    "gpio": {
        "chip": "/dev/gpiochip0",
        "key": {"line": 17, "active_low": True},
        "enclosure": {"line": 27, "active_low": True, "complement_line": 28, "complement_active_low": False},
        "interlock": {"line": 22, "active_low": True},
    }
}


class ConfigTests(unittest.TestCase):
    def data(self):
        return json.loads(json.dumps(MINIMAL))

    def test_the_second_contact_is_parsed_with_its_own_polarity(self):
        config = parse_config(self.data())
        self.assertIsNone(config.gpio.key.complement)
        line, settings = config.gpio.enclosure.complement
        self.assertEqual((line, settings.active_low), (28, False))
        self.assertEqual(settings.debounce_ms, config.gpio.enclosure.settings.debounce_ms)

    def test_the_line_and_its_polarity_come_together(self):
        for drop in ("complement_line", "complement_active_low"):
            data = self.data()
            del data["gpio"]["enclosure"][drop]
            with self.assertRaises(ConfigError):
                parse_config(data)

    def test_a_negative_or_repeated_line_is_refused(self):
        data = self.data()
        data["gpio"]["enclosure"]["complement_line"] = -1
        with self.assertRaises(ConfigError):
            parse_config(data)
        data["gpio"]["enclosure"]["complement_line"] = 17
        with self.assertRaisesRegex(ConfigError, "different line"):
            parse_config(data)

    def test_build_bridge_hands_the_second_contacts_to_the_opener_only_when_declared(self):
        class Watcher:
            fd = 0

            def read_edge_events(self):
                return []

            def close(self):
                return None

        for data, expected in ((self.data(), True), ({"gpio": {k: v for k, v in MINIMAL["gpio"].items()}}, False)):
            if not expected:
                data["gpio"] = {"chip": "/dev/gpiochip0", "key": {"line": 1, "active_low": True}, "enclosure": {"line": 2, "active_low": True}, "interlock": {"line": 3, "active_low": True}}
            seen = {}

            def open_gpio(*args, sink=seen, **kwargs):
                sink.update(kwargs)
                from hydra_umc_bridge_laser.gpio_safety import GpioSafety

                return GpioSafety(GpioSafetyLines(Line(), Line(), Line()), Watcher())

            build_bridge(parse_config(data), open_gpio=open_gpio)
            self.assertEqual("complements" in seen, expected)
            if expected:
                self.assertEqual(list(seen["complements"]), ["enclosure"])


if __name__ == "__main__":
    unittest.main()
