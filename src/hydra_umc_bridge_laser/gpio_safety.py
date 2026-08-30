# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Real, controller-neutral GPIO safeguard reading
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Read the 3 real independent safeguard signals over GPIO - never a laser command.

This bridge is deliberately controller-neutral (see README/BRIDGE_GUIDE) -
no specific laser controller brand or G-code dialect has been chosen yet, so
this module does not assume one. What IS universal across laser cutters is
that `key_enabled`/`enclosure_closed`/`interlock_healthy` are typically wired
as simple, independently-certified digital signals (a key switch, a door
sensor, an interlock relay's own feedback contact) - reading those directly
over the CM5's own GPIO, rather than through any specific controller's own
(possibly less trustworthy) status report, is exactly the kind of
independent safeguard this bridge's own design already calls for.

Uses libgpiod v2's real Linux GPIO character-device API (`gpiod`), the same
library already chosen for the HYDRA_DATA_READY line in the HYDRA-UMC
CM5<->STM32H745 SPI link - lazily imported so this module (and its tests)
work on any host without it installed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .cell import LaserSafetySnapshot


class GpioLineReader:
    """The minimal real interface this module depends on for one GPIO line."""

    def read(self) -> bool:  # pragma: no cover - Protocol-style stub
        raise NotImplementedError


@dataclass(frozen=True)
class GpioSafetyLines:
    """Three already-opened GPIO line readers - one per independent safeguard."""

    key_enabled: GpioLineReader
    enclosure_closed: GpioLineReader
    interlock_healthy: GpioLineReader


def open_gpio_safety_lines(
    chip_path: str,
    key_line_offset: int,
    enclosure_line_offset: int,
    interlock_line_offset: int,
) -> GpioSafetyLines:
    """Open 3 real GPIO input lines. The only place this module imports gpiod.

    Raises RuntimeError with a clear message if gpiod isn't installed, rather
    than letting an ImportError surface from deep inside this module.
    """

    try:
        import gpiod  # type: ignore[import-untyped]
        from gpiod.line import Direction, Value
    except ImportError as error:
        raise RuntimeError(
            "gpiod is not installed - install it to read real laser interlock GPIO lines "
            "(this module's reading/gating logic works and is tested without it)"
        ) from error

    request = gpiod.request_lines(
        chip_path,
        consumer="hydra-umc-bridge-laser",
        config={
            key_line_offset: gpiod.LineSettings(direction=Direction.INPUT),
            enclosure_line_offset: gpiod.LineSettings(direction=Direction.INPUT),
            interlock_line_offset: gpiod.LineSettings(direction=Direction.INPUT),
        },
    )

    class _RequestedLine:
        def __init__(self, offset: int):
            self._offset = offset

        def read(self) -> bool:
            return request.get_value(self._offset) == Value.ACTIVE

    return GpioSafetyLines(
        _RequestedLine(key_line_offset),
        _RequestedLine(enclosure_line_offset),
        _RequestedLine(interlock_line_offset),
    )


class GpioSafetyProbe:
    """Build a LaserSafetySnapshot from 3 real, independently-read GPIO lines."""

    def read_snapshot(self, controller_state: str, lines: GpioSafetyLines) -> LaserSafetySnapshot:
        # A transport-level failure (unavailable chip, unplugged GPIO
        # expander, permission error) must fail the same safe way every
        # other failure mode in this bridge does - all three safeguards
        # read as unsatisfied, never silently assumed True.
        try:
            key_enabled = lines.key_enabled.read()
            enclosure_closed = lines.enclosure_closed.read()
            interlock_healthy = lines.interlock_healthy.read()
        except OSError:
            return LaserSafetySnapshot(controller_state, False, False, False)
        # _strict_bool()'s own rule elsewhere in this bridge is "only a
        # genuine True signal counts" - a non-bool GPIO read is never
        # possible here (the reader always returns bool), but the
        # constructor call is written the same explicit way regardless.
        return LaserSafetySnapshot(
            controller_state,
            key_enabled is True,
            enclosure_closed is True,
            interlock_healthy is True,
        )
