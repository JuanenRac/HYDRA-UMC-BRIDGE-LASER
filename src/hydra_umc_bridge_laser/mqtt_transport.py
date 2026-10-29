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
imports `paho-mqtt`.

Topic scheme (see HYDRA-UMC-MQTT-BROKER's own `hydra/bridges/<name>/...`
convention, `docs/BRIDGE_TOPICS.md`):
  hydra/bridges/laser/state           <- published, RETAINED (LaserSafetySnapshot + derived machine_state + observed_at, epoch milliseconds)
  hydra/bridges/laser/availability    <- "online" / "offline", RETAINED (the broker publishes "offline" if this bridge dies)
  hydra/bridges/laser/cmd/status      -> (empty) re-read the 3 GPIO safeguards + publish state
  hydra/bridges/laser/cmd/job         -> BridgeJob JSON (job_to_dict shape) - the shared bridge-contract gate (plan only: it never acts)
  hydra/bridges/laser/cmd/job/result  <- published, GateDecision JSON
  (state also carries "auxiliary": {name: bool} when extraction/assist-air/temperature checks are declared, and "laser_power" / "feed_rate" when the controller state comes from a GRBL reader that keeps its last report)
  hydra/bridges/laser/event/safety          <- published, QoS 1, not retained: one record per safeguard that changed (see events.py)
  hydra/bridges/laser/event/interlock_open  <- published, QoS 1, not retained: the cell went from safe to unsafe

A payload larger than 16 KiB, a payload that cannot be read and any unexpected failure while handling a message are
answered with a refusal on the result topic; they never end the loop.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict
from typing import Callable

from hydra_umc_sdk.bridge_contract import CellState, JobPhase, decision_to_dict
from hydra_umc_sdk.job_intake import IdempotencyStore, JobIntake
from hydra_umc_sdk.serial_link import GrblReport
from hydra_umc_sdk.bridge_transport import MessageDispatcher as SharedMessageDispatcher
from hydra_umc_sdk.bridge_transport import MqttPublish, connect_with_retry, open_bridge_client

from .cell import LaserCellBridge, LaserSafetySnapshot
from .auxiliary import AuxiliarySupervisor
from .events import EventPublish, SafetyEventTracker
from .gpio_safety import EdgeEventSource, GpioSafetyLines, GpioSafetyProbe, watch_for_interlock_edges

TOPIC_PREFIX = "hydra/bridges/laser/"
AVAILABILITY_TOPIC = f"{TOPIC_PREFIX}availability"

# A command is a few hundred bytes; anything larger is not a command, and parsing it is how a hostile payload costs the bridge its memory or its stack.
MAX_PAYLOAD_BYTES = 16 * 1024

# This bridge has no stop command of its own: the laser is stopped by its own physical E-STOP and enclosure interlocks.
STOP_VERBS: frozenset[str] = frozenset()

_LOG = logging.getLogger(__name__)


def _snapshot_payload(snapshot: LaserSafetySnapshot, observed_at_ms: int, reason: str | None = None) -> str:
    payload = asdict(snapshot)
    payload["machine_state"] = snapshot.machine_state().value
    # when this reading was taken: a retained state without it cannot be told from one that is hours old
    payload["observed_at"] = observed_at_ms
    if reason is not None:
        payload["reason"] = reason
    return json.dumps(payload)


def _refusal(suffix: str, reason: str) -> list[MqttPublish]:
    """The answer to a command that could not be handled; nothing for a topic that is not a `cmd/<verb>`."""
    parts = suffix.split("/")
    if len(parts) != 2 or parts[0] != "cmd":
        return []
    return [EventPublish(f"{TOPIC_PREFIX}{suffix}/result", json.dumps({"allowed": False, "executed": False, "reason": reason}))]


class LaserMqttBridge:
    """Real telemetry/job-gate dispatch for this bridge's MQTT topics.

    `controller_state` is a callable, not a fixed value - matching
    `CncMqttBridge`'s own reasoning: whatever future controller-state
    evidence this bridge reads must always be the current reading, never
    one captured at construction time. There is no real command to gate
    beyond the shared job contract - see this module's own docstring.
    """

    def __init__(
        self,
        lines: GpioSafetyLines,
        controller_state: Callable[[], str],
        cell_state: Callable[[], CellState],
        idempotency: IdempotencyStore | None = None,
        *,
        clock: Callable[[], float] = time.time,
        auxiliary: AuxiliarySupervisor | None = None,
    ) -> None:
        # docs/BRIDGE_CONTRACT.md: the idempotency key of a job is handled once; a repeat gets the answer that was given, nothing is evaluated again
        self._idempotency = idempotency
        # what arrives as a job goes through the shared intake: a malformed one is refused and a repeated key is answered from the store
        self._intake = JobIntake(idempotency)
        self._lines = lines
        self._controller_state = controller_state
        self._cell_state = cell_state
        self._clock = clock
        # the MQTT thread and the edge watcher both read the lines and the controller state; libgpiod objects are not thread-safe
        self._read_lock = threading.Lock()
        self._probe = GpioSafetyProbe()
        self._gate = LaserCellBridge()
        self._events = SafetyEventTracker(clock=clock)
        # optional extra conditions (extraction, assist air, tube temperature); with none declared nothing changes
        self._auxiliary = auxiliary

    def refresh_status(self) -> LaserSafetySnapshot:
        """Re-read the 3 real GPIO safeguards now.

        (same real gap as sibling HYDRA-UMC-BRIDGE-CNC's own
        ): this
        used to cache its result in `self._last_snapshot` for `cmd/job` to
        reuse instead of reading the 3 real GPIO lines again - a real
        enclosure/key/interlock change between two messages went unnoticed
        until the next unrelated `cmd/status` poll happened to catch it.
        Deliberately no caching at all anymore: `cmd/job` calls this
        fresh, immediately before gating, every time - removed the field
        entirely rather than leaving unused dead state a future edit
        could be tempted to read from again.
        """

        with self._read_lock:
            return self._probe.read_snapshot(self._controller_state(), self._lines)

    def state_publish(self) -> MqttPublish:
        """The retained `state` message for a reading taken right now."""
        return MqttPublish(f"{TOPIC_PREFIX}state", self._state_payload(self.refresh_status()), retain=True)

    def _state_payload(self, snapshot: LaserSafetySnapshot) -> str:
        payload = _snapshot_payload(snapshot, int(self._clock() * 1000))
        report = self._controller_report()
        if self._auxiliary is None and report is None:
            return payload
        decoded = json.loads(payload)
        if self._auxiliary is not None:
            decoded["auxiliary"] = self._auxiliary.evaluate()
        if report is not None:
            # what a GRBL laser controller reported besides its state: information for the operator, never a safeguard
            decoded["laser_power"] = report.spindle_speed
            decoded["feed_rate"] = report.feed_rate
        return json.dumps(decoded)

    def _controller_report(self) -> "GrblReport | None":
        """The last report of the controller, when `controller_state` is a reader that keeps one (see `grbl_state.GrblLaserState`)."""
        reader = getattr(self._controller_state, "last_report", None)
        if not callable(reader):
            return None
        try:
            report = reader()
        except Exception:  # noqa: BLE001 - extra information must never keep the state from being published
            return None
        return report if report is not None and getattr(report, "state", "") else None

    def state_and_events(self) -> list[MqttPublish]:
        """The retained `state` for a reading taken now, followed by the events (if any) that this reading shows since the last one."""
        snapshot = self.refresh_status()
        state = MqttPublish(f"{TOPIC_PREFIX}state", self._state_payload(snapshot), retain=True)
        return [state, *self._events.observe(snapshot)]

    def failed_state_and_events(self, reason: str) -> list[MqttPublish]:
        """The fail-closed `state` plus the events that losing sight of the safeguards means."""
        failed = LaserSafetySnapshot("", False, False, False)
        return [self.failed_state_publish(reason), *self._events.observe(failed, reason=reason)]

    def failed_state_publish(self, reason: str) -> MqttPublish:
        """The retained `state` message for a bridge that can no longer see its safeguards: every one of them unsatisfied."""
        failed = LaserSafetySnapshot("", False, False, False)
        return MqttPublish(f"{TOPIC_PREFIX}state", _snapshot_payload(failed, int(self._clock() * 1000), reason), retain=True)

    def handle_message(self, topic: str, payload: bytes, *, retained: bool = False) -> list[MqttPublish]:
        """Route one real inbound MQTT message. An unrecognised `cmd/`
        sub-topic (this bridge subscribes to `cmd/#`, a wildcard) is
        silently ignored, never an error - a future sibling topic this
        version does not know about yet must never crash the message loop.

        `retained` is True when the broker delivered this message
        because of the MQTT retain flag, not because a client just
        published it live. `on_connect()`'s own `subscribe("cmd/#")`
        replays every currently-retained message on that wildcard the
        instant it (re)subscribes - which happens on every reconnect, not
        just once at startup - so a retained `cmd/job` would otherwise
        re-run the shared job gate with no new operator intent behind it
        at all, every single time this bridge reconnects. A retained
        delivery is always ignored here, before it ever reaches a real
        command.

        This never raises: an oversized payload and any failure while handling
        the message come back as a refusal on the verb's result topic.
        """

        if retained:
            return []
        if not topic.startswith(TOPIC_PREFIX):
            return []
        suffix = topic[len(TOPIC_PREFIX) :]
        if len(payload) > MAX_PAYLOAD_BYTES:
            return _refusal(suffix, f"payload is larger than {MAX_PAYLOAD_BYTES} bytes")
        try:
            if suffix == "cmd/status":
                return [self.state_publish()]
            if suffix == "cmd/job":
                return [self._handle_job(payload)]
        except Exception as error:  # noqa: BLE001 - nothing a message does may end the loop
            _LOG.exception("could not handle %s", topic)
            return _refusal(suffix, f"the command could not be handled: {type(error).__name__}")
        return []

    def _handle_job(self, payload: bytes) -> MqttPublish:
        result_topic = f"{TOPIC_PREFIX}cmd/job/result"
        try:
            raw = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            decision = {"allowed": False, "reason": f"malformed job payload: {error}"}
            return EventPublish(result_topic, json.dumps(decision))
        intake = self._intake.accept(raw if isinstance(raw, dict) else {})
        if intake.job is None:
            reason = intake.reason.removeprefix("malformed job: ")
            return EventPublish(result_topic, json.dumps({"allowed": False, "reason": f"malformed job payload: {reason}"}))
        job = intake.job
        key = job.idempotency_key
        if intake.duplicate:
            stored = self._idempotency.recall(key) if self._idempotency is not None else None
            fallback = {"allowed": False, "reason": "this idempotency_key was already handled"}
            return EventPublish(result_topic, stored if stored is not None else json.dumps(fallback))
        try:
            # - always re-read live, right before the gate decides.
            snapshot = self.refresh_status()
            decision = self._gate.plan(job, self._cell_state(), snapshot)
            result = decision_to_dict(decision)
            result["mode"] = "gate-only"
            if self._auxiliary is not None and job.phase is not JobPhase.ABORT:
                missing = AuxiliarySupervisor.unsatisfied(self._auxiliary.evaluate())
                if missing:
                    result["allowed"] = False
                    result["reason"] = "auxiliary safeguard not satisfied: " + ", ".join(missing)
            if job.phase is JobPhase.ABORT:
                # the shared gate always lets an abort through, but this bridge has nothing to abort with: the laser is stopped by its own E-STOP and interlocks
                result["forwarded"] = False
                result["reason"] = "abort acknowledged by the gate only - nothing was stopped; this bridge cannot stop a laser, use its physical E-STOP"
            return self._answer(key, EventPublish(result_topic, json.dumps(result)))
        except Exception as error:  # noqa: BLE001
            _LOG.exception("cmd/job failed")
            failure = {"allowed": False, "reason": f"the job could not be handled: {type(error).__name__}"}
            return self._answer(key, EventPublish(result_topic, json.dumps(failure)))

    def _answer(self, key: str, publish: MqttPublish) -> MqttPublish:
        if self._idempotency is not None:
            self._idempotency.remember(key, publish.payload)
        return publish


class MessageDispatcher(SharedMessageDispatcher):
    """Takes the messages off the network thread, one at a time and in order; `stop_verbs` (none for this bridge) would get a lane of their own."""

    def __init__(self, bridge: object, stop_verbs: frozenset[str] = STOP_VERBS) -> None:
        super().__init__(bridge, TOPIC_PREFIX, stop_verbs)  # type: ignore[arg-type]


def build_edge_watch_on_change(bridge: LaserMqttBridge, publish: Callable[[MqttPublish], None]) -> Callable[[], None]:
    """Build the real `on_change` callback `watch_for_interlock_edges()`
    calls: re-read the 3 GPIO lines live (never trust the raw edge-event
    payload itself, same "always read the live level" rule the rest of
    this bridge already follows) and publish the resulting state the same
    way a `cmd/status` message would, retained, so any subscriber sees the
    real interlock change immediately instead of only on the next message
    this bridge happens to receive. Kept as its own pure function (returns
    a callable, does not start any thread itself) so the wiring is
    unit-testable without a real GPIO chip, edge event or MQTT client."""

    def on_change() -> None:
        for message in bridge.state_and_events():
            publish(message)

    return on_change


def build_edge_watch_on_failure(bridge: LaserMqttBridge, publish: Callable[[MqttPublish], None]) -> Callable[[Exception], None]:
    """Build the callback `watch_for_interlock_edges()` calls when watching fails: the retained `state` becomes a fail-closed one (every safeguard unsatisfied, SAFE_STOP) saying why, so that nobody keeps reading an old "healthy"."""

    def on_failure(error: Exception) -> None:
        for message in bridge.failed_state_and_events(f"edge watcher failed: {type(error).__name__}"):
            publish(message)

    return on_failure


def start_edge_watch_thread(
    bridge: LaserMqttBridge,
    publish: Callable[[MqttPublish], None],
    watcher: EdgeEventSource,
    *,
    watch: Callable[..., None] = watch_for_interlock_edges,
) -> "threading.Thread":
    """Start the real background edge-watch loop as a daemon thread - the
    real latency win over the pre-existing "only re-read on the next
    unrelated MQTT message" behavior (see above): a real
    enclosure/key/interlock transition now publishes an updated `state`
    the instant the kernel reports it, independent of any inbound command.

    `watcher` is the edge-event half of `open_gpio_safety()`: the SAME line
    request the bridge reads its levels from (a second request for the same
    lines would be refused as busy).

    A daemon thread so it never blocks process shutdown; `watch_for_interlock_edges()`
    itself has no natural exit condition here (this loop is meant to run
    for the whole process lifetime, matching `client.loop_forever()`
    below), so this is deliberately fire-and-forget rather than joined. A
    failure inside the loop is published as a fail-closed state and retried.
    """

    thread = threading.Thread(
        target=watch,
        args=(watcher, build_edge_watch_on_change(bridge, publish)),
        kwargs={"should_stop": lambda: False, "on_failure": build_edge_watch_on_failure(bridge, publish)},
        name="hydra-umc-bridge-laser-edge-watch",
        daemon=True,
    )
    thread.start()
    return thread


def run_forever(
    bridge: LaserMqttBridge,
    host: str,
    port: int = 1883,
    client_id: str = "hydra-umc-bridge-laser",
    *,
    max_connect_attempts: int = 5,
    connect_retry_delay_seconds: float = 2.0,
    username: str | None = None,
    password: str | None = None,
    edge_watcher: EdgeEventSource | None = None,
) -> None:
    """Connect to a real HYDRA-UMC-MQTT-BROKER and dispatch forever.

    The only place this module imports paho-mqtt - lazily, so the rest of
    this module (and every test) works on a host without it installed.

    `username`/`password` are optional (matching
    HYDRA-UMC-MQTT-BROKER's own `MQTT_AUTH_JSON` authentication, which is
    itself opt-in) - a broker deployed with authentication required had no
    way to be reached from here at all before this. `password` is only
    meaningful together with `username`; a caller supplying `password`
    alone almost certainly meant to set both, so that combination is
    rejected rather than silently connecting unauthenticated.

    `edge_watcher` is optional and off by default: the `watcher` of
    `open_gpio_safety()` (the same line request the bridge reads from) starts
    the real libgpiod v2 edge-event watcher (see `start_edge_watch_thread()`) as a
    background thread publishing state the instant a real interlock line
    transitions, on top of (never instead of) the existing `cmd/status`/`cmd/job`
    on-demand reads. Omitting it leaves this bridge on-demand only.

    The bridge announces itself on `availability`: "online" once connected, and
    the broker publishes "offline" (the Last Will) if the connection is lost.
    """

    if password is not None and username is None:
        raise ValueError("password was given without a username - MQTT credentials need both")

    dispatcher = MessageDispatcher(bridge)
    try:
        client = open_bridge_client(
            host,
            port,
            client_id=client_id,
            topic_prefix=TOPIC_PREFIX,
            dispatcher=dispatcher,
            username=username,
            password=password,
            max_connect_attempts=max_connect_attempts,
            connect_retry_delay_seconds=connect_retry_delay_seconds,
        )
        if edge_watcher is not None:
            start_edge_watch_thread(
                bridge,
                lambda publish: client.publish(publish.topic, publish.payload, qos=getattr(publish, "qos", 0), retain=publish.retain),  # type: ignore[attr-defined]
                edge_watcher,
            )

        client.loop_forever()
    finally:
        dispatcher.close(wait=False)
