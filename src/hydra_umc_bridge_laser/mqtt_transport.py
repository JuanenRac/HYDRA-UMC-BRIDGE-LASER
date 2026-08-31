# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Real MQTT transport over HYDRA-UMC-MQTT-BROKER
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Reach this bridge's already-real logic over the real MQTT broker.

Unlike the sibling CNC/PRINTER3D bridges, this one has no real actuation
command to expose here: `LaserCellBridge` "coordinates only external
auxiliaries; it cannot arm or fire a laser" (its own docstring) - this
bridge is deliberately controller-neutral, no laser controller brand or
G-code dialect has been chosen yet (see `gpio_safety.py`'s own module
docstring). So this module's real command surface is exactly what the
bridge itself already offers: reading the 3 real independent GPIO
safeguards and evaluating the shared SDK job gate - a new transport
(MQTT), not new physical authority the rest of this bridge doesn't have
either.

`LaserMqttBridge.handle_message()` is the one real place topic routing
happens, and it is a pure(ish) dispatcher over 3 real `GpioLineReader`s
and a `controller_state` callable - fully testable with the exact same
kind of fake `test_gpio_safety.py` already uses, no real MQTT broker or
GPIO chip required. `run_forever()` is the thin real-I/O glue that lazily
imports `paho-mqtt` and is not itself unit-tested beyond import-time
behavior, same convention as `open_gpio_safety_lines()` elsewhere in this
bridge.

Topic scheme (see HYDRA-UMC-MQTT-BROKER's own `hydra/bridges/<name>/...`
convention, `docs/BRIDGE_TOPICS.md`):
  hydra/bridges/laser/state           <- published, RETAINED (LaserSafetySnapshot + derived machine_state)
  hydra/bridges/laser/cmd/status      -> (empty) re-read the 3 GPIO safeguards + publish state
  hydra/bridges/laser/cmd/job         -> BridgeJob JSON (job_to_dict shape) - the shared bridge-contract gate
  hydra/bridges/laser/cmd/job/result  <- published, GateDecision JSON
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Callable

from hydra_umc_sdk.bridge_contract import BridgeError, CellState, decision_to_dict, job_from_dict

from .cell import LaserCellBridge, LaserSafetySnapshot
from .gpio_safety import GpioSafetyLines, GpioSafetyProbe

TOPIC_PREFIX = "hydra/bridges/laser/"


class MqttPublish:
    """One real outbound MQTT publish this module decided to make."""

    __slots__ = ("topic", "payload", "retain")

    def __init__(self, topic: str, payload: str, retain: bool = False) -> None:
        self.topic = topic
        self.payload = payload
        self.retain = retain

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, MqttPublish)
            and (self.topic, self.payload, self.retain) == (other.topic, other.payload, other.retain)
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"MqttPublish(topic={self.topic!r}, payload={self.payload!r}, retain={self.retain!r})"


def _snapshot_payload(snapshot: LaserSafetySnapshot) -> str:
    payload = asdict(snapshot)
    payload["machine_state"] = snapshot.machine_state().value
    return json.dumps(payload)


class LaserMqttBridge:
    """Real telemetry/job-gate dispatch for this bridge's MQTT topics.

    `controller_state` is a callable, not a fixed value - matching
    `CncMqttBridge`'s own reasoning: whatever future controller-state
    evidence this bridge reads must always be the current reading, never
    one captured at construction time. There is no real command to gate
    beyond the shared job contract - see this module's own docstring.
    """

    def __init__(self, lines: GpioSafetyLines, controller_state: Callable[[], str], cell_state: Callable[[], CellState]) -> None:
        self._lines = lines
        self._controller_state = controller_state
        self._cell_state = cell_state
        self._probe = GpioSafetyProbe()
        self._gate = LaserCellBridge()
        self._last_snapshot: LaserSafetySnapshot | None = None

    def refresh_status(self) -> LaserSafetySnapshot:
        """Re-read the 3 real GPIO safeguards now and remember the result for `cmd/job`."""

        snapshot = self._probe.read_snapshot(self._controller_state(), self._lines)
        self._last_snapshot = snapshot
        return snapshot

    def handle_message(self, topic: str, payload: bytes) -> list[MqttPublish]:
        """Route one real inbound MQTT message. An unrecognised `cmd/`
        sub-topic (this bridge subscribes to `cmd/#`, a wildcard) is
        silently ignored, never an error - a future sibling topic this
        version does not know about yet must never crash the message loop."""

        if not topic.startswith(TOPIC_PREFIX):
            return []
        suffix = topic[len(TOPIC_PREFIX) :]

        if suffix == "cmd/status":
            return [MqttPublish(f"{TOPIC_PREFIX}state", _snapshot_payload(self.refresh_status()), retain=True)]
        if suffix == "cmd/job":
            return [self._handle_job(payload)]
        return []

    def _handle_job(self, payload: bytes) -> MqttPublish:
        try:
            job = job_from_dict(json.loads(payload))
        except (json.JSONDecodeError, BridgeError, UnicodeDecodeError) as error:
            decision = {"allowed": False, "reason": f"malformed job payload: {error}"}
            return MqttPublish(f"{TOPIC_PREFIX}cmd/job/result", json.dumps(decision))
        snapshot = self._last_snapshot or self.refresh_status()
        decision = self._gate.plan(job, self._cell_state(), snapshot)
        return MqttPublish(f"{TOPIC_PREFIX}cmd/job/result", json.dumps(decision_to_dict(decision)))


def run_forever(
    bridge: LaserMqttBridge,
    host: str,
    port: int = 1883,
    client_id: str = "hydra-umc-bridge-laser",
) -> None:
    """Connect to a real HYDRA-UMC-MQTT-BROKER and dispatch forever.

    The only place this module imports paho-mqtt - lazily, so the rest of
    this module (and every test) works on a host without it installed.
    """

    try:
        import paho.mqtt.client as mqtt  # type: ignore[import-untyped]
    except ImportError as error:
        raise RuntimeError(
            "paho-mqtt is not installed - install it to connect to a real HYDRA-UMC-MQTT-BROKER "
            "(this module's topic-dispatch/gating logic works and is tested without it)"
        ) from error

    def on_connect(client: object, userdata: object, flags: object, reason_code: object, properties: object = None) -> None:
        client.subscribe(f"{TOPIC_PREFIX}cmd/#")  # type: ignore[attr-defined]

    def on_message(client: object, userdata: object, message: object) -> None:
        for publish in bridge.handle_message(message.topic, message.payload):  # type: ignore[attr-defined]
            client.publish(publish.topic, publish.payload, retain=publish.retain)  # type: ignore[attr-defined]

    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port)
    client.loop_forever()
