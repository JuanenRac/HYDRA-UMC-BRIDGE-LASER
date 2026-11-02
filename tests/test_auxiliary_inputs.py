# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Tests for the readers of the auxiliary safeguards
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
#
# Run against files and a fake libgpiod: nothing here has touched a real sensor or line.
# =============================================================================
import tempfile
import unittest
from pathlib import Path

from hydra_umc_bridge_laser.auxiliary import AuxiliaryCheck, AuxiliarySupervisor
from hydra_umc_bridge_laser.auxiliary_inputs import gpio_level_reader, parse_w1_temperature, simulated_reader, w1_path, w1_reader
from hydra_umc_bridge_laser.service import ConfigError, auxiliary_supervisor, parse_config

from test_service import MINIMAL, with_  # noqa: E402

GOOD = "72 01 4b 46 7f ff 0e 10 57 : crc=57 YES\n72 01 4b 46 7f ff 0e 10 57 t=23125\n"
DEVICE = "28-0316a2796e36"


class W1Tests(unittest.TestCase):
    def test_a_valid_reading_is_degrees_celsius(self):
        self.assertAlmostEqual(parse_w1_temperature(GOOD), 23.125)
        self.assertAlmostEqual(parse_w1_temperature(GOOD.replace("t=23125", "t=-5062")), -5.062)

    def test_a_bad_crc_or_a_missing_value_or_a_power_on_value_is_refused(self):
        for text in (GOOD.replace("YES", "NO"), "72 01 YES\n", GOOD.replace("t=23125", "t=85000"), GOOD.replace("t=23125", "t=-127000"), ""):
            with self.assertRaises(ValueError):
                parse_w1_temperature(text)

    def test_the_device_is_an_id_and_never_a_path(self):
        self.assertTrue(str(w1_path(DEVICE, "/x")).endswith(f"{DEVICE}/w1_slave") or str(w1_path(DEVICE, "/x")).endswith(f"{DEVICE}\w1_slave"))
        for bad in ("../etc", "28-0316a2796e3", "28-0316A2796E36", "/sys/x", ""):
            with self.assertRaises(ValueError):
                w1_path(bad)

    def test_the_reader_reads_the_file_each_time(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / DEVICE).mkdir()
            file = Path(root) / DEVICE / "w1_slave"
            read = w1_reader(DEVICE, root)
            with self.assertRaises(OSError):
                read()
            file.write_text(GOOD, encoding="ascii")
            self.assertAlmostEqual(read(), 23.125)
            file.write_text(GOOD.replace("t=23125", "t=41000"), encoding="ascii")
            supervisor = AuxiliarySupervisor([AuxiliaryCheck("tube", read, max_celsius=30.0)])
            self.assertEqual(supervisor.evaluate(), {"tube": False})
            file.write_text("", encoding="ascii")
            self.assertEqual(supervisor.evaluate(), {"tube": False})  # unreadable: not satisfied


class FakeRequest:
    def __init__(self, value):
        self.value = value
        self.asked = []

    def get_values(self, lines):
        self.asked.append(list(lines))
        if isinstance(self.value, Exception):
            raise self.value
        return [self.value]


class GpioTests(unittest.TestCase):
    def test_the_level_of_the_line_is_read_each_time(self):
        request = FakeRequest(True)
        read = gpio_level_reader("/dev/gpiochip0", 17, active_low=False, request_lines=lambda *args: request)
        self.assertTrue(read())
        request.value = False
        self.assertFalse(read())
        self.assertEqual(request.asked, [[17], [17]])

    def test_a_line_that_cannot_be_read_is_not_satisfied(self):
        request = FakeRequest(OSError("gone"))
        supervisor = AuxiliarySupervisor([AuxiliaryCheck("extraction", gpio_level_reader("c", 1, active_low=True, request_lines=lambda *a: request))])
        self.assertEqual(supervisor.evaluate(), {"extraction": False})

    def test_a_wrong_bias_is_refused(self):
        with self.assertRaises(ValueError):
            gpio_level_reader("c", 1, active_low=False, bias="sideways", request_lines=lambda *a: FakeRequest(True))


class ConfigTests(unittest.TestCase):
    def test_the_other_sources_are_off_until_the_switch_is_on(self):
        table = {"name": "tube", "source": "w1", "device": DEVICE, "max_celsius": 30}
        with self.assertRaisesRegex(ConfigError, "enabled = true"):
            parse_config(with_(auxiliary=[table]))
        config = parse_config(with_(auxiliary=[table], auxiliary_readers={"enabled": True}))
        self.assertTrue(config.auxiliary_readers_enabled)
        self.assertEqual(config.auxiliary[0].source, "w1")
        self.assertFalse(parse_config(MINIMAL).auxiliary_readers_enabled)

    def test_each_source_needs_its_own_fields(self):
        on = {"auxiliary_readers": {"enabled": True}}
        bad = [
            {"name": "a", "source": "w1", "device": DEVICE},  # no max_celsius
            {"name": "a", "source": "w1", "device": "../x", "max_celsius": 30},
            {"name": "a", "source": "gpio", "chip": "c", "line": 3},  # no polarity
            {"name": "a", "source": "gpio", "chip": "c", "line": 3, "active_low": True, "max_celsius": 3},
            {"name": "a", "source": "gpio", "chip": "c", "line": 3, "active_low": True, "bias": "x"},
            {"name": "a", "source": "simulated"},
            {"name": "a", "source": "simulated", "value": 20.0},  # a number needs max_celsius
            {"name": "a", "source": "file"},  # no path
            {"name": "a", "source": "radio", "path": "x"},
        ]
        for table in bad:
            with self.assertRaises(ConfigError, msg=str(table)):
                parse_config(with_(auxiliary=[table], **on))

    def test_simulated_and_w1_sources_build_a_supervisor(self):
        config = parse_config(
            with_(
                auxiliary=[
                    {"name": "extraction", "source": "simulated", "value": True},
                    {"name": "air", "source": "simulated", "value": False},
                    {"name": "tube", "source": "simulated", "value": 25.0, "max_celsius": 30},
                ],
                auxiliary_readers={"enabled": True},
            )
        )
        self.assertEqual(auxiliary_supervisor(config.auxiliary).evaluate(), {"extraction": True, "air": False, "tube": True})
        with self.assertRaises(ValueError):
            simulated_reader("yes")


if __name__ == "__main__":
    unittest.main()
