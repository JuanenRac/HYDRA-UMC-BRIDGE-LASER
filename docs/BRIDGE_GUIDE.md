<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Technical bridge guide
Copyright (C) JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER Technical Guide

## Scope and operating model

`LaserSafetySnapshot` requires a literal idle state and three independently reported safeguards: key enabled, enclosure closed and interlock healthy. `observation.py` normalizes saved local evidence and treats every missing, numeric or text-like safeguard as unsafe. `snapshot_from_fresh_mapping()` additionally requires an explicit `observed_at_ms` value to be no older than a caller-supplied bound; stale, future or malformed evidence clears the interlock health signal. The bridge can gate external auxiliary work but cannot configure, arm or fire a laser.

`LaserSafetySnapshot.machine_state()`'s `controller_state` vocabulary: `IDLE` -> `IDLE`; `RUN`/`RUNNING`/`JOG`/`HOME` -> `RUNNING`; `PAUSED`/`HOLD` -> `HOLDING` (a paused job means the beam is not actively cutting/engraving, a real, distinct condition from actively running); `FAULT`/`ALARM`/`ERROR` -> `FAULT`; `DOOR` -> `SAFE_STOP`. GRBL-style tokens carry a numeric substate (`Hold:0`, `Alarm:1`, `Door:1`): it is dropped before matching, the way the CNC bridge does. Any other token stays `OFFLINE`, the same conservative fail-safe default used for every unrecognized signal in this bridge.

`gpio_safety.py`'s `GpioSafetyProbe.read_snapshot()` is this bridge's first real transport: it reads the same 3 independent safeguards (key/enclosure/interlock) from real GPIO lines via libgpiod v2 (`gpiod`, optional `[gpio]` extra, imported lazily inside `open_gpio_safety()`) instead of a saved mapping. It is deliberately controller-neutral - a key switch, door sensor or interlock relay's own feedback contact is universal wiring across laser cutters regardless of brand, so reading it directly over GPIO needs no controller-specific protocol decision. Any failure while reading - an `OSError`, but also the errors libgpiod v2 raises that are not one, such as a released request - fails all 3 safeguards closed, mirroring `observation.py`'s own "missing/invalid means unsafe" rule; the three levels are read in one operation and every reader shares a lock, because libgpiod request objects are not thread-safe. The reading logic is written against a small `GpioLineReader` interface so it is unit-testable with an in-memory fake, with no real GPIO chip required. `open_gpio_safety()` opens the three lines once (`INPUT`, `Edge.BOTH`): the kernel lets a GPIO line belong to one request at a time, so the level readers and the edge watcher are served by that single request. Each line's wiring is declared with a `GpioLineSettings` (`active_low` is required; `bias` defaults to the one that makes a cut wire read as unsafe; `debounce_ms` defaults to 10) - see [WIRING_GUIDE.md](WIRING_GUIDE.md). `watch_for_interlock_edges()` adds real-time monitoring on top of that same on-demand read path - it blocks on libgpiod v2's own kernel edge-event notifications instead of only re-reading levels when an unrelated inbound message happens to ask, and when it fails it reports the failure (the bridge then publishes a fail-closed `state`) and tries again. None of this has run on a real GPIO chip yet; the tests use a fake `gpiod`.

`mqtt_transport.py` reaches this same real logic over `HYDRA-UMC-MQTT-BROKER`, this bridge's second real transport. Unlike the sibling CNC/PRINTER3D bridges it exposes no real actuation command here either - `LaserCellBridge` cannot arm or fire a laser, so `LaserMqttBridge.handle_message()` only routes `hydra/bridges/laser/cmd/{status,job}`: `status` re-reads the 3 GPIO safeguards and publishes `hydra/bridges/laser/state` (retained); `job` accepts a `BridgeJob` in the shared SDK's `job_to_dict()` wire shape and answers with a `GateDecision` on `.../cmd/job/result`, marked `"mode": "gate-only"`: it never acts, so an `ABORT` through it is answered with `"forwarded": false` and the reason says that nothing was stopped - the laser is stopped by its own physical E-STOP and interlocks. Idempotency keys are namespaced (`job:<key>`). Every message is handled without ever raising: a payload over 16 KiB, deeply nested or unreadable JSON and any unexpected failure get a refusal on the result topic. `state` carries `observed_at` (epoch milliseconds), and the bridge publishes `hydra/bridges/laser/availability` (`online` when connected; the broker publishes `offline`, the MQTT Last Will, when the connection is lost). Dispatch is pure enough to unit-test with the same in-memory fake GPIO lines, no real broker or GPIO chip required - `paho-mqtt` (optional `[mqtt]` extra) is only imported, lazily, inside `run_forever()`. `run_forever(edge_watcher=...)` takes the `watcher` of `open_gpio_safety()` and starts a background daemon thread on it, publishing an updated, retained `state` the instant a safeguard line transitions instead of only on the next unrelated `cmd/status`/`cmd/job` poll; omitting it keeps the on-demand-only behavior. The client uses paho-mqtt's version 2 callback API (`paho-mqtt>=2.1,<3`).

## Reading a GRBL laser controller

`grbl_state.py` gives `LaserMqttBridge` a real `controller_state` instead of a callable the integrator has to write: `GrblLaserState(connection)` sends GRBL's real-time status query `?` over an open serial connection and returns the state word of the report (`Idle`, `Run`, `Hold:0`, `Alarm:1`, `Door:1`...), which `LaserSafetySnapshot.machine_state()` already understands; `open_grbl_laser_state(port_or_usb_id)` opens the port (without asserting DTR, so an Arduino-based board is not reset), finds the same physical device again after a replug and reopens itself. It is read-only on purpose: the only byte it writes is `?` (no feed hold, no reset, no resume, no G-code), because this bridge cannot arm or fire a laser. Like the CNC bridge it uses the shared SDK serial link, which discards what the board sent unasked (banner, `ok`, `[MSG:...]`), reads until the report that answers its own query and treats a board that does not answer as an empty state, which is `OFFLINE` and never lets a job through. When the reader keeps its last report, `state` also carries `laser_power` and `feed_rate` (`FS:` of the report) as information for the operator; they are never a safeguard, which stay the key, the enclosure and the interlock read from GPIO. A GRBL board has one serial port: while LightBurn or LaserGRBL holds it, this reader cannot open it, and LightBurn's UDP command bridge does not give a reliable state, which is why the controller itself is read.

## Compatible software

LightBurn and LaserGRBL are NOT supported: nothing here talks to either of them (the controller state is an input the caller supplies, for example the state token of a GRBL-style controller), and the laser is never driven.

No live laser application/controller command path is integrated yet - the bridge is deliberately controller-neutral until a specific machine and documented safety interface are chosen for that. Real GPIO-level interlock reading (above) doesn't need that choice, since it targets the universal safety wiring, not a controller's own protocol. Future command-path compatibility may target controller software that can expose independently certified state, key, enclosure and interlock observations; a generic G-code sender is not a valid laser safety adapter.

## Scripts and verification

| Script | Purpose | Changes version/CHANGELOG? |
|---|---|---|
| `build-test.bat` / `build-test.sh` | Compile and run local safety tests | No |
| `build.bat` / `build.sh` | Validate, then build (never changes the version or the CHANGELOG) | No |
| `tools/inspect_controller_evidence.py` | Normalize a saved JSON capture only | No |

## Adding a new script

Use the standard header, state the non-arming scope, number console steps and add `pause` to `.bat`. Reusable parsing must be tested and compiled by `build-test`. No script may open a laser connection, modify safety configuration, upload a job, arm or fire a source.

## Hardware acceptance gate

Choose the controller and documented interface, validate signals against certified safety hardware, test stale/disconnected behavior, prove independent E-STOP and conduct dry HIL trials without active material. Only then can a separately reviewed controller adapter be considered.

## Safety events

`events.py` publishes what the edge watcher sees, never retained and with QoS 1:

- `hydra/bridges/laser/event/safety`: one JSON record per safeguard that changed (`safeguard`, `from`, `to`, `at_ms`, `sequence`, `machine_state`), the log a data lake keeps for audit and OEE.
- `hydra/bridges/laser/event/interlock_open`: once, when the cell goes from safe to unsafe (`reasons`, `at_ms`, `sequence`). The orchestrator decides what to stop; this bridge cannot stop a laser.

The first reading only sets the baseline. A watcher that fails is reported as the loss of every safeguard.

## Auxiliary safeguards

`auxiliary.py` reads optional extra conditions (fume extraction, assist air, CO2 tube temperature with a `max_celsius` limit). Pass `AuxiliarySupervisor([AuxiliaryCheck(...)])` as `LaserMqttBridge(auxiliary=...)`: `cmd/job` refuses any job except ABORT while a check is not satisfied and names it, and `state` carries an `auxiliary` map. A reading that fails, is not a real number or is not a bool where a level is expected counts as not satisfied.
