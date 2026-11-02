# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Readers for the auxiliary safeguards (1-Wire temperature, GPIO level, simulation)
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Where the values of the auxiliary safeguards come from when they are not a file written by someone else.

* ``w1``: a 1-Wire temperature sensor (DS18B20 and the like) read from the kernel's ``w1_slave`` file.
* ``gpio``: the level of one GPIO input (fume extraction running, assist air on) read with libgpiod.
* ``simulated``: a fixed value, for a dry run or a test without hardware.

Every reader returns what ``AuxiliaryCheck.read`` expects (a bool, or degrees Celsius) and raises when it cannot read, which the
supervisor counts as NOT satisfied. These readers only read; nothing here switches anything. The ``w1`` and ``gpio`` readers have
been run against files and a fake libgpiod only: they have not been tried on a real sensor or line.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable

W1_ROOT = "/sys/bus/w1/devices"
_W1_ID = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{12}$")
#: a DS18B20 that has just powered up reports 85 C, and one that cannot be read reports -127 C: neither is a measurement
_W1_NOT_A_MEASUREMENT = (85.0, -127.0)
SOURCES = ("file", "w1", "gpio", "simulated")
BIASES = ("pull-up", "pull-down", "disabled", "as-is")


def parse_w1_temperature(text: str) -> float:
    """Degrees Celsius from the two lines of a ``w1_slave`` file; raises ValueError when the CRC is not YES or there is no value."""
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].rstrip().endswith("YES"):
        raise ValueError("the sensor did not give a valid reading (CRC not YES)")
    match = re.search(r"t=(-?\d+)\s*$", lines[1])
    if match is None:
        raise ValueError("the reading has no t= value")
    celsius = int(match.group(1)) / 1000.0
    if celsius in _W1_NOT_A_MEASUREMENT:
        raise ValueError(f"{celsius} C is the value of a sensor that has not measured")
    return celsius


def w1_path(device: str, root: str = W1_ROOT) -> Path:
    """``<root>/<device>/w1_slave`` for a device id such as ``28-0316a2796e36``; any other text is refused (no path from the file)."""
    if not _W1_ID.match(device):
        raise ValueError(f"not a 1-Wire device id: {device!r}")
    return Path(root) / device / "w1_slave"


def w1_reader(device: str, root: str = W1_ROOT) -> Callable[[], float]:
    path = w1_path(device, root)

    def read() -> float:
        return parse_w1_temperature(path.read_text(encoding="ascii", errors="strict"))

    return read


def gpio_level_reader(
    chip: str,
    line: int,
    *,
    active_low: bool,
    bias: str = "as-is",
    request_lines: Callable[..., object] | None = None,
) -> Callable[[], bool]:
    """A reader of one GPIO input line: True while the line is active (after the polarity). ``request_lines`` is for tests and
    returns an object with ``get_values([line])`` that answers True/False; by default libgpiod is imported here, and a missing
    library is an error at start, not a silent pass."""
    if bias not in BIASES:
        raise ValueError(f"bias must be one of {', '.join(BIASES)}")
    lock = threading.Lock()
    if request_lines is not None:
        request = request_lines(chip, line, active_low, bias)

        def read_fake() -> bool:
            with lock:
                return request.get_values([line])[0] is True  # type: ignore[attr-defined]

        return read_fake
    try:
        import gpiod  # type: ignore[import-untyped]
        from gpiod.line import Bias, Direction, Value
    except ImportError as error:
        raise RuntimeError("gpiod is not installed - install it to read a GPIO input") from error
    names = {"pull-up": Bias.PULL_UP, "pull-down": Bias.PULL_DOWN, "disabled": Bias.DISABLED, "as-is": Bias.AS_IS}
    settings = gpiod.LineSettings(direction=Direction.INPUT, bias=names[bias], active_low=active_low)
    real = gpiod.request_lines(chip, consumer="hydra-umc-bridge-laser-aux", config={line: settings})

    def read() -> bool:
        with lock:
            return real.get_values([line])[0] == Value.ACTIVE

    return read


def simulated_reader(value: object) -> Callable[[], object]:
    """A reader that always gives ``value`` (a bool or a number) - for a dry run without hardware."""
    if not isinstance(value, (bool, int, float)):
        raise ValueError("a simulated value is a boolean or a number")
    return lambda: value
