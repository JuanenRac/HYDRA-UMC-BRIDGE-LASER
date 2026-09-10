# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Realistic GPIO chip + MQTT broker emulator (fixture)
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Two protocol-faithful fixtures for the exact seams this bridge's real
code depends on: a libgpiod-shaped GPIO chip behind the `GpioLineReader`
interface, and a real MQTT broker (retained messages, wildcard
subscriptions, an inbound queue) around `LaserMqttBridge.handle_message()`.

Until now the doubles here were `FakeLine` (a fixed bool, or one that
raises) and a bare `list` of `MqttPublish`. That proves the bridge's own
snapshot/gating in isolation; it never proves the bridge survives real
GPIO wiring polarity, a mid-session physical change, a faulted chip, or
that its RETAINED `state` publish actually reaches a late subscriber.

`GpioChipEmulator`
  * three real independent lines - `key_switch`, `enclosure_door`,
    `interlock_relay` - each a `GpioLineReader` (`read() -> bool`);
  * `active_low` per line: real interlock/E-stop hardware is very often
    wired active-low (contact closed / "safe" = logic 0), so the value on
    the wire is inverted before it becomes the boolean the bridge reads -
    a `FakeLine(True)` never captures that;
  * `fault()` makes every read raise `OSError` (unplugged ribbon, chip
    offline) so a test proves the bridge fails closed, never assumes safe.

`MqttBrokerEmulator`
  * `publish(topic, payload, retain)` with a real retained-message store;
  * `subscribe(filter)` with real `+`/`#` wildcard matching, and a new
    subscription immediately replays the matching retained message
    (`hydra/bridges/laser/state` is published RETAINED for exactly this);
  * `pump(bridge)` routes every queued `cmd/#` message into
    `bridge.handle_message()` and re-publishes what it returns, updating
    the retained store - the real broker round trip, not a direct call.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class _EmulatedLine:
    def __init__(self, wire_value: bool, active_low: bool) -> None:
        self._wire_value = wire_value
        self._active_low = active_low
        self._faulted = False

    def set_wire(self, value: bool) -> None:
        self._wire_value = value

    def fault(self, faulted: bool = True) -> None:
        self._faulted = faulted

    def read(self) -> bool:
        if self._faulted:
            raise OSError("GPIO line read failed: chip offline")
        return (not self._wire_value) if self._active_low else self._wire_value


class GpioChipEmulator:
    """A 3-line libgpiod-shaped chip. `lines` plugs straight into
    `GpioSafetyLines(key_enabled=, enclosure_closed=, interlock_healthy=)`."""

    def __init__(self, *, key_active_low: bool = False, enclosure_active_low: bool = False, interlock_active_low: bool = True) -> None:
        # Sensible real defaults: a key switch reads its own ON as logic 1
        # (active-high), while an interlock relay's feedback contact is
        # classically active-low. All start in the "safe to operate" state.
        self.key_switch = _EmulatedLine(True, key_active_low)
        self.enclosure_door = _EmulatedLine(True, enclosure_active_low)
        self.interlock_relay = _EmulatedLine(False if interlock_active_low else True, interlock_active_low)

    # ---- physical-side drivers ----------------------------------------
    def turn_key(self, on: bool) -> None:
        self.key_switch.set_wire(on)

    def close_enclosure(self) -> None:
        self.enclosure_door.set_wire(True)

    def open_enclosure(self) -> None:
        self.enclosure_door.set_wire(False)

    def set_interlock_healthy(self, healthy: bool) -> None:
        # Store the LOGICAL intent; _EmulatedLine applies the wiring polarity.
        self.interlock_relay.set_wire(not healthy if self.interlock_relay._active_low else healthy)

    def fault_chip(self, faulted: bool = True) -> None:
        for line in (self.key_switch, self.enclosure_door, self.interlock_relay):
            line.fault(faulted)

    def as_safety_lines(self):
        from hydra_umc_bridge_laser.gpio_safety import GpioSafetyLines

        return GpioSafetyLines(
            key_enabled=self.key_switch,
            enclosure_closed=self.enclosure_door,
            interlock_healthy=self.interlock_relay,
        )


@dataclass
class _Subscription:
    topic_filter: str
    received: list[tuple[str, bytes]] = field(default_factory=list)


def _topic_matches(topic_filter: str, topic: str) -> bool:
    f_parts = topic_filter.split("/")
    t_parts = topic.split("/")
    for i, fp in enumerate(f_parts):
        if fp == "#":
            return True
        if i >= len(t_parts):
            return False
        if fp == "+":
            continue
        if fp != t_parts[i]:
            return False
    return len(f_parts) == len(t_parts)


class MqttBrokerEmulator:
    def __init__(self) -> None:
        self._retained: dict[str, bytes] = {}
        self._subs: list[_Subscription] = []
        self._inbound: list[tuple[str, bytes]] = []
        self.published: list[tuple[str, bytes, bool]] = []

    def publish(self, topic: str, payload, retain: bool = False) -> None:
        data = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        self.published.append((topic, data, retain))
        if retain:
            if data:
                self._retained[topic] = data
            else:
                self._retained.pop(topic, None)  # an empty retained payload clears it, per MQTT
        for sub in self._subs:
            if _topic_matches(sub.topic_filter, topic):
                sub.received.append((topic, data))

    def subscribe(self, topic_filter: str) -> _Subscription:
        sub = _Subscription(topic_filter)
        self._subs.append(sub)
        for topic, data in self._retained.items():
            if _topic_matches(topic_filter, topic):
                sub.received.append((topic, data))  # real broker replays retained on subscribe
        return sub

    def enqueue_inbound(self, topic: str, payload) -> None:
        data = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        self._inbound.append((topic, data))

    def pump(self, bridge) -> None:
        """Deliver every queued inbound message to the bridge and publish
        back what it returns - one real broker round trip."""
        queue, self._inbound = self._inbound, []
        for topic, payload in queue:
            for out in bridge.handle_message(topic, payload):
                self.publish(out.topic, out.payload, retain=getattr(out, "retain", False))

    def retained(self, topic: str) -> bytes | None:
        return self._retained.get(topic)
