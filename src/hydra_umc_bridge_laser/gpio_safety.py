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

import threading
import time
from dataclasses import dataclass
from datetime import timedelta
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
    """Three already-opened GPIO line readers - one per independent safeguard.

    `read_all`, when given, reads the three lines in one operation (one ioctl
    on a real chip), so that the snapshot cannot mix instants; the individual
    readers are the fallback."""

    key_enabled: GpioLineReader
    enclosure_closed: GpioLineReader
    interlock_healthy: GpioLineReader
    read_all: Callable[[], tuple[bool, bool, bool]] | None = None


@dataclass(frozen=True)
class GpioLineSettings:
    """How one safeguard is wired - it must be declared, because the safe level depends on the wiring and not on the code.

    `active_low`: True when the signal is "safe/healthy" at logic 0 (the usual
    normally-closed contact to ground). `read()` then reports True for a safe
    line, whatever the electrical level.

    `bias`: "pull-up", "pull-down", "disabled" or "as-is". None picks the
    fail-safe one: the bias that makes a CUT WIRE read as UNSAFE (pull-up for an
    active-low signal, pull-down for an active-high one).

    `debounce_ms`: contact bounce is ignored for this long (0 turns it off)."""

    active_low: bool
    bias: str | None = None
    debounce_ms: float = 10.0

    def resolved_bias(self) -> str:
        bias = self.bias if self.bias is not None else ("pull-up" if self.active_low else "pull-down")
        if bias not in {"pull-up", "pull-down", "disabled", "as-is"}:
            raise ValueError(f"bias must be pull-up, pull-down, disabled or as-is, not {bias!r}")
        if self.debounce_ms < 0:
            raise ValueError("debounce_ms must not be negative")
        return bias


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


@dataclass(frozen=True)
class GpioSafety:
    """What `open_gpio_safety()` hands back: the three level readers and the edge watcher, both served by ONE line request."""

    lines: GpioSafetyLines
    watcher: EdgeEventSource


def open_gpio_safety(
    chip_path: str,
    key_line_offset: int,
    enclosure_line_offset: int,
    interlock_line_offset: int,
    *,
    key: GpioLineSettings,
    enclosure: GpioLineSettings,
    interlock: GpioLineSettings,
) -> GpioSafety:
    """Open the 3 real GPIO safeguard lines ONCE, for both the level readers and the edge-event watcher.

    A GPIO line can belong to only one request at a time (libgpiod v2 / the
    kernel's character device): asking for the same lines twice - once to read
    levels and once to watch edges - fails the second time with "Device or
    resource busy". So there is a single request here (`direction=INPUT`,
    `edge_detection=BOTH`), the readers use `get_values()` on it and the watcher
    uses `read_edge_events()` on it, serialised by a lock because libgpiod's
    request objects are not thread-safe.

    Each line's polarity, bias and debounce are declared by the caller (see
    `GpioLineSettings`): the code never guesses what "safe" looks like on a wire.

    The only place this module imports gpiod. Raises RuntimeError with a clear
    message if gpiod isn't installed, rather than letting an ImportError surface
    from deep inside this module.
    """

    try:
        import gpiod  # type: ignore[import-untyped]
        from gpiod.line import Bias, Direction, Edge, Value
    except ImportError as error:
        raise RuntimeError(
            "gpiod is not installed - install it to read real laser interlock GPIO lines "
            "(this module's reading/gating logic works and is tested without it)"
        ) from error

    biases = {"pull-up": Bias.PULL_UP, "pull-down": Bias.PULL_DOWN, "disabled": Bias.DISABLED, "as-is": Bias.AS_IS}
    offsets = (key_line_offset, enclosure_line_offset, interlock_line_offset)
    if len(set(offsets)) != 3:
        raise ValueError("the key, enclosure and interlock lines must be three different GPIO lines")

    def settings_of(wiring: GpioLineSettings):  # noqa: ANN202
        return gpiod.LineSettings(
            direction=Direction.INPUT,
            edge_detection=Edge.BOTH,
            bias=biases[wiring.resolved_bias()],
            active_low=wiring.active_low,
            debounce_period=timedelta(milliseconds=wiring.debounce_ms),
        )

    request = gpiod.request_lines(
        chip_path,
        consumer="hydra-umc-bridge-laser",
        config={
            key_line_offset: settings_of(key),
            enclosure_line_offset: settings_of(enclosure),
            interlock_line_offset: settings_of(interlock),
        },
    )
    lock = threading.Lock()

    def read_all() -> tuple[bool, bool, bool]:
        with lock:
            values = request.get_values(list(offsets))
        return tuple(value == Value.ACTIVE for value in values)  # type: ignore[return-value]

    class _RequestedLine:
        def __init__(self, index: int):
            self._index = index

        def read(self) -> bool:
            return read_all()[self._index]

    class _LockedWatcher:
        @property
        def fd(self) -> int:
            return request.fd

        def read_edge_events(self) -> list[object]:
            with lock:
                return request.read_edge_events()

        def close(self) -> object:
            return request.release()

    return GpioSafety(
        GpioSafetyLines(_RequestedLine(0), _RequestedLine(1), _RequestedLine(2), read_all),
        _LockedWatcher(),
    )


def watch_for_interlock_edges(
    source: EdgeEventSource,
    on_change: Callable[[], None],
    *,
    poll: Callable[[int, float | None], bool] | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    timeout_seconds: float = 1.0,
    on_failure: Callable[[Exception], None] | None = None,
    retry_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Block on real GPIO edge events - never a fixed poll interval - and
    call `on_change()` the instant any of the 3 interlock lines actually
    transitions.

    Any failure of the wait, of the read or of `on_change()` itself is passed to
    `on_failure(error)` (the bridge uses it to publish a fail-closed state, so the
    retained value is never an old "healthy") and the loop tries again after
    `retry_seconds`: the watcher never ends in silence.

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
        try:
            if poll(source.fd, timeout_seconds):
                events = source.read_edge_events()
                if events:
                    on_change()
        except Exception as error:  # noqa: BLE001 - a failing watcher must say so and keep trying, never die silently
            if on_failure is not None:
                try:
                    on_failure(error)
                except Exception:  # noqa: BLE001
                    pass
            sleep(retry_seconds)


class GpioSafetyProbe:
    """Build a LaserSafetySnapshot from 3 real, independently-read GPIO lines."""

    def read_snapshot(self, controller_state: str, lines: GpioSafetyLines) -> LaserSafetySnapshot:
        # A failure while reading (unavailable chip, unplugged GPIO
        # expander, permission error, a request that was released) must fail
        # the same safe way every other failure mode in this bridge does -
        # all three safeguards read as unsatisfied, never silently assumed
        # True - whatever the exception type: libgpiod v2 raises errors that
        # are not OSError.
        try:
            if lines.read_all is not None:
                # one operation for the three lines: the snapshot cannot mix instants
                key_enabled, enclosure_closed, interlock_healthy = lines.read_all()
            else:
                key_enabled = lines.key_enabled.read()
                enclosure_closed = lines.enclosure_closed.read()
                interlock_healthy = lines.interlock_healthy.read()
        except Exception:  # noqa: BLE001
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
