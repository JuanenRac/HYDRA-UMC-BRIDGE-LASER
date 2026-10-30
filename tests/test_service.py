# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Service configuration and wiring tests
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""The configuration file, the cell-state source and the wiring of the service, with simulated GPIO and a simulated controller."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from hydra_umc_sdk.bridge_contract import CellState
from hydra_umc_bridge_laser.gpio_safety import GpioSafety, GpioSafetyLines
from hydra_umc_bridge_laser.mqtt_transport import TOPIC_PREFIX
from hydra_umc_bridge_laser.service import (
    CellStateConfig,
    ConfigError,
    build_bridge,
    cell_state_reader,
    load_config,
    main,
    parse_config,
)

MINIMAL = {
    "gpio": {
        "chip": "/dev/gpiochip0",
        "key": {"line": 17, "active_low": True},
        "enclosure": {"line": 27, "active_low": True},
        "interlock": {"line": 22, "active_low": False, "bias": "pull-down", "debounce_ms": 5},
    }
}
EXAMPLE = Path(__file__).resolve().parents[1] / "deploy" / "bridge-laser.example.toml"


def with_(**changes):
    data = json.loads(json.dumps(MINIMAL))
    data.update(changes)
    return data


class FakeLine:
    def __init__(self, value=True):
        self.value = value

    def read(self):
        return self.value


class FakeWatcher:
    fd = 0

    def read_edge_events(self):
        return []

    def close(self):
        return None


class ParseTests(unittest.TestCase):
    def test_minimal_file_gets_the_safe_defaults(self):
        config = parse_config(MINIMAL)
        self.assertEqual(config.mqtt.host, "127.0.0.1")
        self.assertIsNone(config.controller)
        self.assertEqual(config.cell_state.source, "fixed")
        self.assertEqual(config.cell_state.value, CellState.INHIBITED)
        self.assertEqual(config.gpio.interlock.settings.debounce_ms, 5.0)
        self.assertEqual(config.gpio.key.settings.debounce_ms, 10.0)

    def test_the_example_file_is_valid(self):
        config = load_config(EXAMPLE)
        self.assertEqual(config.controller.device, "/dev/ttyUSB0")
        self.assertEqual(config.cell_state.source, "file")

    def test_polarity_has_no_default(self):
        data = with_()
        del data["gpio"]["key"]["active_low"]
        with self.assertRaisesRegex(ConfigError, "gpio.key.active_low is required"):
            parse_config(data)

    def test_unknown_keys_are_refused(self):
        with self.assertRaisesRegex(ConfigError, "unknown key in the file: gpoi"):
            parse_config(with_(gpoi={}))
        data = with_()
        data["gpio"]["key"]["activelow"] = True
        with self.assertRaisesRegex(ConfigError, "unknown key in gpio.key"):
            parse_config(data)

    def test_three_lines_must_differ(self):
        data = with_()
        data["gpio"]["enclosure"]["line"] = 17
        with self.assertRaisesRegex(ConfigError, "three different"):
            parse_config(data)

    def test_wrong_types_and_values_are_refused(self):
        data = with_()
        data["gpio"]["key"]["line"] = "17"
        with self.assertRaisesRegex(ConfigError, "must be a int"):
            parse_config(data)
        data = with_()
        data["gpio"]["key"]["line"] = True
        with self.assertRaises(ConfigError):
            parse_config(data)
        data = with_()
        data["gpio"]["key"]["bias"] = "sideways"
        with self.assertRaises(ValueError):
            parse_config(data)
        with self.assertRaisesRegex(ConfigError, "cell_state.value"):
            parse_config(with_(cell_state={"value": "GO"}))
        with self.assertRaisesRegex(ConfigError, "cell_state.path is required"):
            parse_config(with_(cell_state={"source": "file"}))
        with self.assertRaisesRegex(ConfigError, "mqtt.port"):
            parse_config(with_(mqtt={"port": 0}))

    def test_gpio_section_is_required(self):
        with self.assertRaisesRegex(ConfigError, r"\[gpio\] is required"):
            parse_config({})

    def test_bad_toml_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.toml"
            bad.write_text("[gpio\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "not valid TOML"):
                load_config(bad)
            with self.assertRaisesRegex(ConfigError, "cannot read"):
                load_config(Path(folder) / "none.toml")

    def test_check_flag_and_exit_codes(self):
        self.assertEqual(main(["--config", str(EXAMPLE), "--check"]), 0)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(main(["--config", str(Path(folder) / "none.toml"), "--check"]), 2)


class CellStateTests(unittest.TestCase):
    def test_fixed_source(self):
        self.assertEqual(cell_state_reader(CellStateConfig())(), CellState.INHIBITED)
        self.assertEqual(cell_state_reader(CellStateConfig("fixed", CellState.READY))(), CellState.READY)

    def test_file_source_follows_the_file_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cell_state"
            read = cell_state_reader(CellStateConfig("file", path=str(path), max_age_seconds=30))
            self.assertEqual(read(), CellState.SAFE_STOP)  # missing
            path.write_text("READY\n", encoding="utf-8")
            self.assertEqual(read(), CellState.READY)
            path.write_text("INHIBITED", encoding="utf-8")
            self.assertEqual(read(), CellState.INHIBITED)  # always the current reading
            path.write_text("GO", encoding="utf-8")
            self.assertEqual(read(), CellState.SAFE_STOP)  # unknown word
            path.write_text("", encoding="utf-8")
            self.assertEqual(read(), CellState.SAFE_STOP)  # empty
            path.write_text("READY", encoding="utf-8")
            old = time.time() - 120
            os.utime(path, (old, old))
            self.assertEqual(read(), CellState.SAFE_STOP)  # a stale READY is not READY


class WiringTests(unittest.TestCase):
    def build(self, config, lines, **kwargs):
        opened = {}

        def open_gpio(chip, key_line, enclosure_line, interlock_line, **settings):
            opened.update(chip=chip, offsets=(key_line, enclosure_line, interlock_line), settings=settings)
            return GpioSafety(GpioSafetyLines(*lines), FakeWatcher())

        bridge, gpio = build_bridge(config, open_gpio=open_gpio, **kwargs)
        return bridge, opened

    def state_of(self, bridge):
        answer = bridge.handle_message(f"{TOPIC_PREFIX}cmd/status", b"")
        return json.loads(answer[0].payload)

    def test_lines_polarity_and_settings_reach_the_gpio_opener(self):
        bridge, opened = self.build(parse_config(MINIMAL), (FakeLine(), FakeLine(), FakeLine()))
        self.assertEqual(opened["chip"], "/dev/gpiochip0")
        self.assertEqual(opened["offsets"], (17, 27, 22))
        self.assertTrue(opened["settings"]["key"].active_low)
        self.assertFalse(opened["settings"]["interlock"].active_low)
        self.assertEqual(opened["settings"]["interlock"].resolved_bias(), "pull-down")

    def test_no_controller_reads_offline_and_closed(self):
        bridge, _ = self.build(parse_config(MINIMAL), (FakeLine(), FakeLine(), FakeLine()))
        state = self.state_of(bridge)
        self.assertEqual(state["machine_state"], "OFFLINE")
        self.assertTrue(state["key_enabled"])

    def test_controller_state_and_a_safeguard_that_opens(self):
        config = parse_config(with_(controller={"device": "/dev/ttyUSB0", "baud": 9600}))
        seen = {}

        def open_controller(device, baud, timeout):
            seen.update(device=device, baud=baud, timeout=timeout)
            return lambda: "Idle"

        door = FakeLine()
        bridge, _ = self.build(config, (FakeLine(), door, FakeLine()), open_controller=open_controller)
        self.assertEqual(seen, {"device": "/dev/ttyUSB0", "baud": 9600, "timeout": 1.0})
        self.assertFalse(self.state_of(bridge)["enclosure_closed"] is False)
        door.value = False
        self.assertFalse(self.state_of(bridge)["enclosure_closed"])

    def test_cell_state_hook_reaches_the_job_gate(self):
        from hydra_umc_sdk.bridge_contract import BridgeJob, JobPhase, MachineState, job_to_dict

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cell_state"
            config = parse_config(with_(controller={"device": "x"}, cell_state={"source": "file", "path": str(path)}))
            bridge, _ = self.build(config, (FakeLine(), FakeLine(), FakeLine()), open_controller=lambda *a: (lambda: "IDLE"))
            job = json.dumps(job_to_dict(BridgeJob("j1", "k1", "orchestrator", JobPhase.LOAD, MachineState.IDLE, {}))).encode()
            path.write_text("SAFE_STOP", encoding="utf-8")
            denied = json.loads(bridge.handle_message(f"{TOPIC_PREFIX}cmd/job", job)[0].payload)
            self.assertFalse(denied["allowed"])
            path.write_text("READY", encoding="utf-8")
            job2 = json.dumps(job_to_dict(BridgeJob("j2", "k2", "orchestrator", JobPhase.LOAD, MachineState.IDLE, {}))).encode()
            allowed = json.loads(bridge.handle_message(f"{TOPIC_PREFIX}cmd/job", job2)[0].payload)
            self.assertTrue(allowed["allowed"], allowed)

    def test_auxiliary_files_gate_the_state(self):
        with tempfile.TemporaryDirectory() as folder:
            fan, tube = Path(folder) / "fan", Path(folder) / "tube"
            config = parse_config(with_(auxiliary=[{"name": "extraction", "path": str(fan)}, {"name": "tube", "path": str(tube), "max_celsius": 30}]))
            bridge, _ = self.build(config, (FakeLine(), FakeLine(), FakeLine()))
            self.assertEqual(self.state_of(bridge)["auxiliary"], {"extraction": False, "tube": False})  # nothing written yet
            fan.write_text("1", encoding="utf-8")
            tube.write_text("24.5", encoding="utf-8")
            self.assertEqual(self.state_of(bridge)["auxiliary"], {"extraction": True, "tube": True})
            tube.write_text("41", encoding="utf-8")
            self.assertFalse(self.state_of(bridge)["auxiliary"]["tube"])
            tube.write_text("hot", encoding="utf-8")
            self.assertFalse(self.state_of(bridge)["auxiliary"]["tube"])


if __name__ == "__main__":
    unittest.main()
