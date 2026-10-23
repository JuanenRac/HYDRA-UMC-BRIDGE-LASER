# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Optional auxiliary safeguards (extraction, assist air, tube temperature)
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Extra conditions a real laser cell needs before work: fume extraction running, assist air on, CO2 tube cool.

Each check is declared by the caller and is optional: with none declared the
bridge behaves as before. A check that cannot be read, or that reads
anything but a clear pass, counts as NOT satisfied - the same fail-closed rule
as the three main safeguards. Nothing here switches anything: it only reads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AuxiliaryCheck:
    """One auxiliary safeguard.

    `read` returns a bool for a digital input (True = satisfied) or a number for
    a temperature in degrees Celsius (satisfied while it is at most `max_celsius`).
    """

    name: str
    read: Callable[[], object]
    max_celsius: float | None = None


class AuxiliarySupervisor:
    def __init__(self, checks: list[AuxiliaryCheck] | tuple[AuxiliaryCheck, ...]) -> None:
        names = [check.name for check in checks]
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("every auxiliary check needs a name")
        if len(set(names)) != len(names):
            raise ValueError("auxiliary check names must be unique")
        for check in checks:
            if check.max_celsius is not None and not (isinstance(check.max_celsius, (int, float)) and math.isfinite(check.max_celsius)):
                raise ValueError("max_celsius must be a finite number")
        self._checks = tuple(checks)

    def evaluate(self) -> dict[str, bool]:
        """Read every check now; a failure to read is an unsatisfied check, never an exception."""
        result: dict[str, bool] = {}
        for check in self._checks:
            try:
                value = check.read()
            except Exception:  # noqa: BLE001
                result[check.name] = False
                continue
            if check.max_celsius is None:
                result[check.name] = value is True
            else:
                result[check.name] = (
                    isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value <= check.max_celsius
                )
        return result

    @staticmethod
    def unsatisfied(evaluation: dict[str, bool]) -> list[str]:
        return [name for name, ok in evaluation.items() if not ok]
