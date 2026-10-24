# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Read-only GRBL laser controller state
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Read the state of a GRBL laser controller; never send it anything but the status query.

``LaserMqttBridge`` takes a ``controller_state`` callable. Until now whoever wired the bridge had to provide it; this module
is the real one for the common case, a GRBL-family laser controller (the boards LaserGRBL and LightBurn drive) on a serial
port: it sends GRBL's real-time status query ``?`` and returns the state word of the report (``Idle``, ``Run``, ``Hold:0``,
``Alarm:1``, ``Door:1`` ...), which ``LaserSafetySnapshot.machine_state()`` already understands.

It is read-only on purpose. The bridge "cannot arm or fire a laser", so this reader has no feed hold, no reset, no resume and
no G-code: the only byte it ever writes is ``?``. The status query, the reconnecting connection and the parsing are the shared
``hydra_umc_sdk.serial_link`` that the CNC bridge uses too.

The report also carries the laser power the controller has programmed (``FS:feed,power``): ``last_report()`` returns it, and
the bridge adds ``laser_power`` and ``feed_rate`` to its ``state`` when the reader has one. It is information for the
operator, never a safeguard: the key, the enclosure and the interlock stay the three GPIO signals.

A GRBL controller has ONE serial port. While LightBurn, LaserGRBL or any sender holds it, this reader cannot open it; the
state then has to come from somewhere else. LightBurn's "UDP command bridge" does not give a reliable state, which is why the
controller itself is read.
"""

from __future__ import annotations

import threading
from typing import Callable

from hydra_umc_sdk.serial_link import (
    GrblReport,
    ReconnectingSerialConnection,
    SerialLike,
    open_serial_port,
    open_serial_port_by_id,
    parse_status_report,
    read_status_line,
)

__all__ = ["GrblLaserState", "open_grbl_laser_state"]


class GrblLaserState:
    """A ``controller_state`` callable that asks a GRBL laser controller for its status. Fails closed: no answer is ``""``."""

    def __init__(self, connection: SerialLike) -> None:
        self._connection = connection
        self._lock = threading.Lock()  # one query at a time: two readers would take each other's replies
        self._last: GrblReport | None = None

    def __call__(self) -> str:
        """The state word of the controller now; ``""`` (which the bridge reads as OFFLINE) when it did not answer."""

        report = self.read_report()
        return report.state if report is not None else ""

    def read_report(self) -> GrblReport | None:
        """Query the controller. ``None`` when the link failed or no status report arrived."""

        with self._lock:
            try:
                line = read_status_line(self._connection)
            except Exception:  # noqa: BLE001 - whatever goes wrong on the link, the laser is not known to be fine
                self._last = None
                return None
            report = parse_status_report(line)
            self._last = report if report.state else None
            return self._last

    def last_report(self) -> GrblReport | None:
        """The report of the last query that was answered; ``None`` after one that was not."""

        with self._lock:
            return self._last

    def close(self) -> None:
        close = getattr(self._connection, "close", None)
        if close is not None:
            close()


def open_grbl_laser_state(
    device: str,
    baud: int = 115200,
    timeout_seconds: float = 1.0,
    *,
    list_ports: Callable[[], list] | None = None,
) -> GrblLaserState:
    """Open the serial port of a GRBL laser controller and read its state. ``device`` is a port name or a stable USB id.

    A port name that exists (``COM3``, ``/dev/ttyUSB0``, a ``/dev/serial/by-id/...`` link) is opened as is; any other text is
    the serial number or ``hwid`` of the device and is looked up, so the same physical controller is found again after a
    replug. The connection reopens itself after a cable replug; the port is opened without asserting DTR, so an
    Arduino-based board is not reset.
    """

    def connect() -> SerialLike:
        try:
            return open_serial_port_by_id(device, baud=baud, timeout_seconds=timeout_seconds, list_ports=list_ports)
        except RuntimeError:
            if list_ports is not None:
                raise
            return open_serial_port(device, baud=baud, timeout_seconds=timeout_seconds)

    return GrblLaserState(ReconnectingSerialConnection(connect))
