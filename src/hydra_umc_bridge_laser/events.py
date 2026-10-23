# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Safety event stream (interlock-open and safeguard log)
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Turn changes of the three safeguards into timestamped events.

Two topics come out of the same observation:

  hydra/bridges/laser/event/safety          one record per safeguard that changed (the log a data lake keeps for audit and OEE)
  hydra/bridges/laser/event/interlock_open  once, when the cell goes from safe to unsafe (the orchestrator decides to abort the arms)

Both are published with QoS 1 and never retained: an event is something that
happened, not a state, and a late subscriber must not replay it as if it were
new. This module only reports; it cannot stop, arm or fire a laser.
"""

from __future__ import annotations

import json
import threading
from typing import Callable

from hydra_umc_sdk.bridge_transport import MqttPublish

from .cell import LaserSafetySnapshot

EVENT_PREFIX = "hydra/bridges/laser/event/"
SAFETY_EVENT_TOPIC = f"{EVENT_PREFIX}safety"
INTERLOCK_OPEN_TOPIC = f"{EVENT_PREFIX}interlock_open"

SAFEGUARDS = ("key_enabled", "enclosure_closed", "interlock_healthy")


class EventPublish(MqttPublish):
    """An `MqttPublish` that also carries its QoS (events use 1)."""

    __slots__ = ("qos",)

    def __init__(self, topic: str, payload: str, retain: bool = False, qos: int = 1) -> None:
        super().__init__(topic, payload, retain)
        self.qos = qos


def _is_safe(snapshot: LaserSafetySnapshot) -> bool:
    return all(getattr(snapshot, name) is True for name in SAFEGUARDS)


class SafetyEventTracker:
    """Remembers the last snapshot seen and reports what changed since.

    The first observation only sets the baseline: nothing is known to have
    changed. `sequence` grows by one per event so a consumer can tell a gap.
    """

    def __init__(self, *, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._previous: LaserSafetySnapshot | None = None
        self._sequence = 0

    def observe(self, snapshot: LaserSafetySnapshot, *, reason: str | None = None) -> list[MqttPublish]:
        at_ms = int(self._clock() * 1000)
        with self._lock:
            previous, self._previous = self._previous, snapshot
            if previous is None:
                return []
            events: list[MqttPublish] = []
            for name in SAFEGUARDS:
                before, after = getattr(previous, name) is True, getattr(snapshot, name) is True
                if before != after:
                    self._sequence += 1
                    record = {
                        "event": "safeguard_change",
                        "safeguard": name,
                        "from": before,
                        "to": after,
                        "at_ms": at_ms,
                        "sequence": self._sequence,
                        "machine_state": snapshot.machine_state().value,
                    }
                    if reason is not None:
                        record["reason"] = reason
                    events.append(EventPublish(SAFETY_EVENT_TOPIC, json.dumps(record)))
            if _is_safe(previous) and not _is_safe(snapshot):
                self._sequence += 1
                opened = {
                    "event": "interlock_open",
                    "reasons": [name for name in SAFEGUARDS if getattr(snapshot, name) is not True],
                    "at_ms": at_ms,
                    "sequence": self._sequence,
                    "machine_state": snapshot.machine_state().value,
                    "advice": "stop the arms of the cell; this bridge cannot stop a laser",
                }
                if reason is not None:
                    opened["reason"] = reason
                events.append(EventPublish(INTERLOCK_OPEN_TOPIC, json.dumps(opened)))
            return events
