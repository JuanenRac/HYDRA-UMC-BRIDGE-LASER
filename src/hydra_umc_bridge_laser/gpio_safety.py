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
from typing import Callable, Protocol, runtime_checkable

from .cell import LaserSafetySnapshot


@runtime_checkable
class GpioLineReader(Protocol):
    """The minimal real interface this module depends on for one GPIO line.

    A real `typing.Protocol`, not a base class with a `NotImplementedError`
    body - the previous form was directly instantiable and looked like a
    usable no-op implementation (it would only fail, at call time, the
    moment `.read()` actually ran). A Protocol has no body to instantiate
    at all: `_RequestedLine` below satisfies it structurally, with no
    inheritance, and a type checker rejects anything that doesn't.
    """

    def read(self) -> bool: ...


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


@runtime_checkable
class EdgeEventSource(Protocol):
    """The minimal real interface this module depends on for a libgpiod v2
    edge-event-capable line request: a real, pollable file descriptor
    (`fd`) plus a blocking read of whatever edge events are currently
    available on it (`read_edge_events()` - libgpiod v2's own real API,
    the same shape `gpiod.LineRequest` exposes)."""

    @property
    def fd(self) -> int: ...
    def read_edge_events(self) -> list[object]: ...
    def close(self) -> object: ...


def open_gpio_edge_watcher(
    chip_path: str,
    key_line_offset: int,
    enclosure_line_offset: int,
    interlock_line_offset: int,
) -> EdgeEventSource:
    """Open the same 3 real GPIO safeguard lines as `open_gpio_safety_lines()`,
    configured for libgpiod v2's real edge-event API (`edge_detection=
    Edge.BOTH`) instead of level-only input.

    This is what actually closes the real latency gap `mqtt_transport.py`'s
    own LASER-01 comment documents: without this, a real enclosure/key/
    interlock change is only ever noticed the next time something else
    happens to ask this bridge to re-read the lines (an inbound
    `cmd/status`/`cmd/job` MQTT message) - there is no ongoing observation
    of the lines in between. A request opened with `edge_detection=
    Edge.BOTH` makes the kernel itself wake this process the instant any of
    the 3 lines transitions (both directions - a real interlock is exactly
    as safety-relevant going healthy->unhealthy as the reverse), which
    `watch_for_interlock_edges()` below turns into an immediate callback
    instead of waiting on the next unrelated message.

    The only place this module imports gpiod for edge watching. Raises
    RuntimeError with a clear message if gpiod isn't installed, matching
    `open_gpio_safety_lines()`'s own lazy-import convention.
    """

    try:
        import gpiod  # type: ignore[import-untyped]
        from gpiod.line import Direction, Edge
    except ImportError as error:
        raise RuntimeError(
            "gpiod is not installed - install it to watch real laser interlock GPIO edge events "
            "(this module's reading/gating logic works and is tested without it)"
        ) from error

    settings = gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.BOTH)
    return gpiod.request_lines(
        chip_path,
        consumer="hydra-umc-bridge-laser-edge-watch",
        config={
            key_line_offset: settings,
            enclosure_line_offset: settings,
            interlock_line_offset: settings,
        },
    )


def watch_for_interlock_edges(
    source: EdgeEventSource,
    on_change: Callable[[], None],
    *,
    poll: Callable[[int, float | None], bool] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    timeout_seconds: float = 1.0,
) -> None:
    """Block on real GPIO edge events - never a fixed poll interval - and
    call `on_change()` the instant any of the 3 interlock lines actually
    transitions.

    `on_change` takes no arguments deliberately: it is expected to re-read
    the current, live values itself (via `GpioSafetyProbe.read_snapshot()`)
    rather than trust the raw edge-event payload as the safety-relevant
    reading, keeping this module's existing "always read the live level,
    never trust a cached/derived value" rule (see `GpioSafetyProbe`'s own
    docstring reasoning) intact for the edge-triggered path too.

    `poll` wraps `select.select()` on the request's real `fd` purely so
    `timeout_seconds` lets this loop notice `should_stop()` promptly
    instead of blocking forever on a chip that (correctly) never sees
    another edge - it is never what actually detects an edge;
    `read_edge_events()` is, and it only ever returns once the kernel has
    a real event queued. Defaults to a real `select.select()`-backed
    implementation, lazily imported so this stays importable on a platform
    without a usable `select.select()` on arbitrary file descriptors.
    Injectable so the whole loop is unit-testable with a fake source and a
    fake poll function - no real GPIO chip, kernel edge event or `select`
    call required.
    """

    if poll is None:
        import select

        def poll(fd: int, timeout: float | None) -> bool:
            readable, _, _ = select.select([fd], [], [], timeout)
            return bool(readable)

    while not should_stop():
        if poll(source.fd, timeout_seconds):
            events = source.read_edge_events()
            if events:
                on_change()


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
