# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - tests/test_config_refusals.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The configuration of the laser bridge refuses what is unknown or wrong at start, never on the first reading: each rule is shown with the exact mistake that
breaks it, starting from one valid configuration. The polarity of the safety lines has no default on purpose, and the sources of the auxiliary safeguards other
than a file are off unless the operator switches them on. No hardware: only the parsed configuration."""

import copy
import tempfile
import unittest
from pathlib import Path

from hydra_umc_bridge_laser.service import ConfigError, load_config, parse_config

VALID = {
    "mqtt": {"host": "broker.local", "port": 1883},
    "gpio": {
        "chip": "/dev/gpiochip0",
        "key": {"line": 5, "active_low": True},
        "enclosure": {"line": 6, "active_low": True},
        "interlock": {"line": 13, "active_low": False},
    },
}


def mutated(**changes):
    data = copy.deepcopy(VALID)
    for dotted, value in changes.items():
        parts = dotted.split("__")
        target = data
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        if value is ...:
            target.pop(parts[-1], None)
        else:
            target[parts[-1]] = value
    return data


class Basics(unittest.TestCase):
    def test_the_valid_configuration_and_its_defaults(self):
        config = parse_config(copy.deepcopy(VALID))
        self.assertEqual((config.mqtt.host, config.mqtt.port), ("broker.local", 1883))
        self.assertEqual((config.gpio.key.line, config.gpio.interlock.line), (5, 13))
        self.assertTrue(config.gpio.edge_watch)
        self.assertIsNone(config.controller)
        self.assertEqual(config.auxiliary, ())
        self.assertFalse(config.auxiliary_readers_enabled)
        self.assertIsNone(config.hardening)
        self.assertFalse(config.global_stop.enabled)

    def refuses(self, data, text):
        with self.assertRaisesRegex(ConfigError, text):
            parse_config(data)

    def test_unknown_keys_are_refused_everywhere(self):
        self.refuses(mutated(surprise={}), "unknown key in the file: surprise")
        self.refuses(mutated(mqtt__surprise=1), "unknown key in mqtt")
        self.refuses(mutated(gpio__surprise=1), "unknown key in gpio")
        self.refuses(mutated(gpio__key__surprise=1), "unknown key in gpio.key")

    def test_tables_must_be_tables(self):
        self.refuses(mutated(mqtt=5), r"\[mqtt\] must be a table")
        self.refuses(mutated(gpio=...), r"\[gpio\] is required")
        self.refuses(mutated(gpio__key=...), r"\[key\] is required")
        self.refuses(mutated(gpio__enclosure="x"), r"\[enclosure\] must be a table")

    def test_wrong_types_are_refused_and_a_boolean_is_not_a_number(self):
        self.refuses(mutated(mqtt__host=5), "mqtt.host must be a str")
        self.refuses(mutated(mqtt__port="1883"), "mqtt.port must be a int")
        self.refuses(mutated(mqtt__port=True), "mqtt.port must be a int")
        self.refuses(mutated(mqtt__connect_retry_delay_seconds=True), "must be a float")
        self.refuses(mutated(gpio__edge_watch=1), "gpio.edge_watch must be a bool")
        self.assertEqual(parse_config(mutated(mqtt__connect_retry_delay_seconds=2)).mqtt.connect_retry_delay_seconds, 2.0)

    def test_the_port_range(self):
        for port in (0, -1, 65536, 100000):
            self.refuses(mutated(mqtt__port=port), "1 to 65535")
        for port in (1, 65535):
            self.assertEqual(parse_config(mutated(mqtt__port=port)).mqtt.port, port)


class SafetyLines(unittest.TestCase):
    def refuses(self, data, text):
        with self.assertRaisesRegex(ConfigError, text):
            parse_config(data)

    def test_the_polarity_has_no_default(self):
        for line in ("key", "enclosure", "interlock"):
            self.refuses(mutated(**{f"gpio__{line}__active_low": ...}), f"gpio.{line}.active_low is required")

    def test_the_line_number_is_required_and_not_negative(self):
        self.refuses(mutated(gpio__key__line=...), "gpio.key.line is required")
        self.refuses(mutated(gpio__key__line=-1), "must not be negative")
        self.refuses(mutated(gpio__key__line="5"), "must be a int")

    def test_the_three_lines_must_be_different(self):
        self.refuses(mutated(gpio__key__line=6), "three different lines")
        self.refuses(mutated(gpio__interlock__line=5), "three different lines")
        self.refuses(mutated(gpio__enclosure__line=13), "three different lines")

    def test_the_chip_is_required(self):
        self.refuses(mutated(gpio__chip=...), "gpio.chip is required")

    def test_a_wrong_bias_or_debounce_stops_the_start(self):
        with self.assertRaises(ValueError):
            parse_config(mutated(gpio__key__bias="sideways"))
        with self.assertRaises(ValueError):
            parse_config(mutated(gpio__key__debounce_ms=-5))


class Optional(unittest.TestCase):
    def refuses(self, data, text):
        with self.assertRaisesRegex(ConfigError, text):
            parse_config(data)

    def test_controller(self):
        config = parse_config(mutated(controller={"device": "/dev/ttyUSB0"}))
        self.assertEqual((config.controller.device, config.controller.baud), ("/dev/ttyUSB0", 115200))
        self.refuses(mutated(controller={}), "controller.device is required")
        self.refuses(mutated(controller={"device": "x", "parity": "even"}), "unknown key in controller")
        self.refuses(mutated(controller={"device": "x", "baud": "fast"}), "controller.baud must be a int")

    def test_cell_state(self):
        self.assertEqual(parse_config(mutated(cell_state={"source": "file", "path": "/run/cell", "max_age_seconds": 5})).cell_state.max_age_seconds, 5.0)
        self.refuses(mutated(cell_state={"source": "magic"}), "must be fixed or file")
        self.refuses(mutated(cell_state={"source": "file"}), "path is required")
        self.refuses(mutated(cell_state={"value": "exploding"}), "must be one of")
        self.refuses(mutated(cell_state={"max_age_seconds": 0}), "must be positive")
        self.refuses(mutated(cell_state={"max_age_seconds": -3}), "must be positive")
        self.refuses(mutated(cell_state={"color": "red"}), "unknown key in cell_state")

    def test_the_default_cell_state_is_the_conservative_one(self):
        self.assertEqual(parse_config(copy.deepcopy(VALID)).cell_state.value.value.lower(), "inhibited")

    def test_global_stop_and_hardening_tables(self):
        self.assertTrue(parse_config(mutated(global_stop={"enabled": True})).global_stop.enabled)
        self.refuses(mutated(global_stop={"enabled": "yes"}), "global_stop.enabled must be a bool")
        self.refuses(mutated(global_stop={"colour": 1}), "unknown key in global_stop")
        self.refuses(mutated(global_stop={"topic": "bad topic with # wildcard"}), "global_stop.topic")
        self.refuses(mutated(hardening={"turbo": True}), "unknown key in hardening")
        self.refuses(mutated(idempotency={"file": "x"}), "unknown key in idempotency")
        self.refuses(mutated(auxiliary_readers={"on": True}), "unknown key in auxiliary_readers")


class Auxiliary(unittest.TestCase):
    def refuses(self, items, text, readers=False):
        data = mutated(auxiliary=items)
        if readers:
            data["auxiliary_readers"] = {"enabled": True}
        with self.assertRaisesRegex(ConfigError, text):
            parse_config(data)

    def test_a_file_source_needs_a_path_and_a_name(self):
        config = parse_config(mutated(auxiliary=[{"name": "door", "path": "/run/door"}, {"name": "tube", "path": "/run/temp", "max_celsius": 40}]))
        self.assertEqual([item.name for item in config.auxiliary], ["door", "tube"])
        self.refuses([{"name": "door"}], "path is required for a file source")
        self.refuses([{"path": "/run/door"}], r"auxiliary\[0\].name is required")
        self.refuses([{"name": "d", "path": "x", "colour": 1}], "unknown key in auxiliary")

    def test_the_list_must_be_a_list_of_tables(self):
        self.refuses({"name": "x"}, "must be an array of tables")
        self.refuses(["x"], "must be an array of tables")

    def test_other_sources_are_off_unless_the_operator_switches_them_on(self):
        self.refuses([{"name": "t", "source": "simulated", "value": True}], "needs .auxiliary_readers. enabled = true")
        self.refuses([{"name": "t", "source": "teleport"}], "must be one of")

    def test_each_source_needs_its_own_fields(self):
        self.refuses([{"name": "t", "source": "w1", "device": "28-0123456789ab"}], "needs device and max_celsius", readers=True)
        self.refuses([{"name": "t", "source": "w1", "max_celsius": 40}], "needs device and max_celsius", readers=True)
        self.refuses([{"name": "t", "source": "w1", "device": "../etc", "max_celsius": 40}], "auxiliary.0..device", readers=True)
        self.refuses([{"name": "g", "source": "gpio", "chip": "/dev/gpiochip0", "line": 4}], "polarity has no default", readers=True)
        self.refuses([{"name": "g", "source": "gpio", "chip": "/dev/gpiochip0", "line": -2, "active_low": True}], "not negative", readers=True)
        self.refuses([{"name": "g", "source": "gpio", "chip": "/dev/gpiochip0", "line": 4, "active_low": True, "max_celsius": 3}], "not negative", readers=True)
        self.refuses([{"name": "g", "source": "gpio", "chip": "/dev/gpiochip0", "line": 4, "active_low": True, "bias": "weird"}], "bias must be one of", readers=True)

    def test_a_simulated_value_is_a_boolean_or_a_number_with_a_limit(self):
        self.refuses([{"name": "s", "source": "simulated"}], "needs a value", readers=True)
        self.refuses([{"name": "s", "source": "simulated", "value": "hot"}], "needs a value", readers=True)
        self.refuses([{"name": "s", "source": "simulated", "value": 30.0}], "boolean, or a number together", readers=True)
        self.refuses([{"name": "s", "source": "simulated", "value": True, "max_celsius": 40}], "boolean, or a number together", readers=True)
        ok = parse_config(
            {
                **mutated(),
                "auxiliary_readers": {"enabled": True},
                "auxiliary": [{"name": "s1", "source": "simulated", "value": True}, {"name": "s2", "source": "simulated", "value": 30.0, "max_celsius": 40}],
            }
        )
        self.assertTrue(ok.auxiliary_readers_enabled)
        self.assertEqual(len(ok.auxiliary), 2)


class Files(unittest.TestCase):
    def test_load_config_reads_toml_and_refuses_what_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            good = Path(folder) / "bridge.toml"
            good.write_text('[mqtt]\nhost = "x"\n[gpio]\nchip = "c"\n[gpio.key]\nline = 1\nactive_low = true\n[gpio.enclosure]\nline = 2\nactive_low = true\n[gpio.interlock]\nline = 3\nactive_low = false\n', encoding="utf-8")
            self.assertEqual(load_config(good).mqtt.host, "x")
            broken = Path(folder) / "broken.toml"
            broken.write_text("[mqtt\nhost =", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(broken)
            with self.assertRaisesRegex(ConfigError, "cannot read"):
                load_config(Path(folder) / "missing.toml")


if __name__ == "__main__":
    unittest.main()
