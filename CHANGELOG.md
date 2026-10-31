# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- **`EventPublish` passes its QoS to the SDK's `MqttPublish`** instead of declaring a slot of its own; the answers and events are still published at QoS 1 and nothing changes on the wire.

- **The bridge can follow the global stop of the server, off by default:** with `HYDRA_UMC_LASER_GLOBAL_STOP=1` and the table `[global_stop]` of the configuration file it subscribes to the retained announcement on `hydra/swarm/safety/estop` (`HYDRA_UMC_LASER_GLOBAL_STOP_TOPIC` changes the topic) and, while the last message says `SAFE_STOP`, says anything but `READY` or cannot be read, `cmd/job` (an abort passes) is refused with the reason in the answer; stops and read-only requests keep working and only `READY` ends it. `HYDRA_UMC_LASER_GLOBAL_STOP_STRICT=1` also refuses until the first announcement has been heard. Without the switch nothing changes. `tests/test_global_stop.py` covers the guard and the refusals, `tests/test_global_stop_broker.py` runs them against a real broker on a free local port (the announcement is delivered at QoS 0, 1 and 2, a retained stop is obeyed at connect, an unreadable one fails closed).

- **The MQTT transport is tested against a real broker:** `tests/test_broker_integration.py` starts a `HYDRA-UMC-MQTT-BROKER` on a free local port and runs the bridge through the shared client: the retained availability, a command answered at QoS 0, 1 and 2, a retained command that is only a replay, messages published at each QoS, the last will after an unclean loss of the link and the way back after the broker went down and up. It skips itself when node, `paho-mqtt` or the installed broker (`HYDRA_UMC_TEST_BROKER_DIR`, default the folder next to this one) are missing.

## [0.1.9] - The bridge runs as a service, jobs through the shared intake, answers at QoS 1 and the universal README

- **The bridge runs as a service.** `python -m hydra_umc_bridge_laser --config <file>` (or the `hydra-umc-bridge-laser` command) starts it from one TOML file: the GPIO chip and the three safeguard lines with their polarity, bias and debounce, the serial port of the GRBL controller, the MQTT broker, where the state of the cell comes from and the optional auxiliary safeguards (fume extraction, assist air, tube temperature, each read from a small file). A key it does not know is refused, the polarity of a line has no default, and everything fails closed: a missing controller reads OFFLINE, and a cell-state file that is missing, unknown or stale is SAFE_STOP. `--check` validates the file. `deploy/hydra-umc-bridge-laser.service` is the systemd unit (`Restart=on-failure`, a closed device policy, memory limits) and `deploy/bridge-laser.example.toml` the example file. Covered by `tests/test_service.py` with simulated GPIO and a simulated controller.

- **Jobs go through the shared intake of the SDK:** the check of a malformed job and of a repeated `idempotency_key` is the SDK's `JobIntake` instead of code of this bridge (the keys are no longer prefixed with `job:`).

- **The answers to the commands are published at QoS 1** (the shared dispatcher keeps the QoS a bridge gives an answer), so a result is not lost on a flaky link; the pin of the shared SDK moves to its newest tag.
- **README in the universal layout:** the README and its seven translations follow the layout that the four families share (22 sections in a fixed order), with an architecture picture and a repository-structure picture drawn from `docs/architecture.json` and `docs/structure.json`; the CI validator checks both pictures and the file tree. Where the repository has a service or an MQTT transport, the README now says how to start it and which environment variables it reads.

- **The layout of the README is checked in the CI:** the validator runs `tools/universal_readme_check.py` and lists, as a warning, what differs from the universal layout of the README.

## [0.1.8] - A real controller state for GRBL laser boards and optional auxiliary safeguards

- **A real controller state for GRBL laser boards.** `GrblLaserState` / `open_grbl_laser_state` read the state word of a GRBL-family laser controller over a serial port and are the `controller_state` of `LaserMqttBridge`. Read-only: the only byte written is the status query `?`. A board that does not answer is an empty state (`OFFLINE`), never idle. The laser power and the feed of the report appear in `state` as `laser_power` and `feed_rate`, as information and never as a safeguard. The port, the reconnecting connection, the status query and the parser are the shared SDK serial link of the CNC bridge. Needs an SDK newer than 0.3.6. Tested against a simulated board.
- **Optional auxiliary safeguards.** A cell can declare fume extraction, assist air and CO2 tube temperature as checks (`AuxiliaryCheck`, `LaserMqttBridge(auxiliary=...)`); a job other than ABORT is refused, naming the failed check, while one is not satisfied, and an unreadable or non-finite reading counts as not satisfied. `state` carries an `auxiliary` map. Read-only. Covered by `tests/test_auxiliary.py`.
- **Safety event stream.** Every change of the key, enclosure or interlock becomes a timestamped record on `hydra/bridges/laser/event/safety` (for audit and OEE in a data lake), and the moment the cell goes from safe to unsafe an `hydra/bridges/laser/event/interlock_open` event names the safeguards that opened, so the orchestrator can stop the arms of the cell at once. Both are QoS 1 and never retained, carry `at_ms` and a growing `sequence`, and a failing edge watcher is reported as an open interlock too. The bridge only reports; it cannot stop a laser. Covered by `tests/test_events.py`.
- Building no longer changes the version; raising it is the explicit `bump` command (`python tools/hydra_project_tool.py bump`). The build scripts only report the version they built, and CI fails if a build script runs a bump.
- **The MQTT transport comes from the SDK.** Connecting with retries, the publish record and the message dispatcher are the shared `hydra_umc_sdk.bridge_transport` of SDK 0.3.6 instead of a copy of their own; what is specific to this bridge (its topics and what it does with a message) stays here, and its tests are unchanged.

- **Pinned to SDK 0.3.6** (dependency and contract checkout in CI). From this version the shared bridge gate fails closed: a productive job is refused when the bridge did not pass the state it read from its machine. The bridge passes what the laser safety input reported.
- The banner follows the animated style of the ecosystem banners, with the name, the kind and the technologies of the project.
- Added `tools/hydra_project_tool.py`: the same `validate`, `test`, `version`, `status` and `bump` commands in every repository. The checks run with `HYDRA_UMC_CI=1` and fail if the version changes; only `bump` changes it.
- The SDK is now fetched at a release tag instead of the main branch, so a change of the SDK cannot break this repository by itself.
- Successful incremental build: synchronized package metadata and `hydra-umc.project.json`.

## [0.1.7]

- Successful incremental build: synchronized package metadata and `hydra-umc.project.json`.
- The licence is written as GPL-3.0-or-later in every header and in the package metadata.

## [0.1.6] - Maturity lowered to functional

- Maturity is functional: the code, tests and documentation are in place, but nothing here has been verified on real hardware yet, so the manifest no longer claims the established level.

## [0.1.5] - One GPIO request for levels and edges, declared wiring, and a watcher that says when it fails

- **The levels and the edge watcher share ONE line request.** The kernel lets a GPIO line belong to one request at a time: opening the same three lines again for the watcher was refused as busy. `open_gpio_safety()` makes a single request (`INPUT`, `Edge.BOTH`) and returns the three level readers and the watcher; it replaces `open_gpio_safety_lines()` and `open_gpio_edge_watcher()`. `run_forever()` takes `edge_watcher=` instead of the chip path and three offsets.
- **The wiring is declared, not guessed.** Each safeguard takes a `GpioLineSettings` with a required `active_low`, a `bias` (the default is the fail-safe one: pull-up for an active-low signal, pull-down for an active-high one, so a cut wire reads as unsafe) and a `debounce_ms` (10 ms by default). The three lines must be three different offsets. A new wiring guide (`docs/WIRING_GUIDE.md`) explains polarity, normally-closed contacts, bias and debounce.
- **One read, one lock.** The three levels are read in one operation (`get_values()`), and the MQTT thread and the watcher read under the same lock, because libgpiod request objects are not thread-safe.
- **Any failure while reading fails closed.** Not only `OSError`: libgpiod v2 raises errors that are not (for example a released request); all three safeguards read as unsatisfied.
- **The watcher no longer dies in silence.** A failure while waiting, reading or publishing publishes a retained, fail-closed `state` (`SAFE_STOP`, every safeguard unsatisfied, with the reason) and the watcher tries again; nobody keeps reading an old "healthy".
- **The loop survives anything a client sends.** Deeply nested JSON, a payload larger than 16 KiB, an unreadable payload and any unexpected failure while handling a message are answered with a refusal on the result topic instead of ending `loop_forever()`. Messages are handled off the network thread, in order.
- **`cmd/job` answers say what they are.** The result carries `"mode": "gate-only"`; an `ABORT` says `"forwarded": false` and that nothing was stopped (this bridge cannot stop a laser; the physical E-STOP does). Idempotency keys are namespaced (`job:<key>`) and a failure leaves an explicit answer for the key.
- **A retained state can be judged.** `state` carries `observed_at` (epoch milliseconds); `availability` is `online` once connected and the broker publishes `offline` (Last Will) when the bridge dies.
- **GRBL-style controller states.** `Hold:0`, `Alarm:1`, `Door:1`, `Jog` and `Home` are understood (the substate is dropped, as the CNC bridge does) instead of falling to `OFFLINE`.
- **paho-mqtt.** The client uses the version 2 callback API, which also starts with paho-mqtt 2.0; the extra now requires `paho-mqtt>=2.1,<3`.
- `tools/inspect_controller_evidence.py` reports the canonical `SAFE_STOP` value on failure; the unused `subprocess` import of `tools/ci_validate.py` is gone; `LICENSE` now carries the complete GPL-3.0-or-later text.
- README (all eight languages) and `docs/` updated: test counts and test file list, the "four-signal" wording (three safeguards plus the controller state), the real-time monitoring now described as one shared request, the HYDRA-UMC-SERVER path that does not exist is no longer drawn, and LightBurn/LaserGRBL are stated as not supported.
- New `tests/test_hardening.py` (hostile payloads, a fake `gpiod` proving the single request and the declared wiring, the failing watcher, controller states, the dispatcher).

## [0.1.4] - Connects to a broker that demands credentials: user, password and TLS from the environment

- The MQTT client now takes its credentials and TLS from the environment of the service (`HYDRA_MQTT_USERNAME`, `HYDRA_MQTT_PASSWORD` or `HYDRA_MQTT_PASSWORD_FILE`, `HYDRA_MQTT_TLS_CA`) through `hydra_umc_sdk.mqtt_connection`, so it can reach a production HYDRA-UMC-MQTT-BROKER, which refuses anonymous clients and evaluates its ACL for the identity of the credential.
- An explicit `username`/`password` argument still wins, and a password without a user name is refused.
- The client ID must start with the `clientIdPrefix` of the bridge's credential.
- New `tests/test_mqtt_environment.py` (a fake paho client, so it runs without paho-mqtt) proves that the environment credentials and the CA reach the client, that the explicit ones win, that nothing set is an anonymous plain connection, and that a lonely password is refused.

## [0.1.3] - A repeated idempotency key is answered once

- **Idempotency keys.** `LaserMqttBridge` accepts an `IdempotencyStore` from HYDRA-UMC-SDK: the first time a job key arrives it is evaluated and its answer kept; a repeat gets the same answer and nothing is evaluated again. docs/BRIDGE_CONTRACT.md asked bridges to do this and none did.
- Three new tests (tests/test_idempotency.py).

## [0.1.2] - Real-time interlock monitoring via libgpiod v2 edge events

- `open_gpio_edge_watcher()`/`watch_for_interlock_edges()` (`gpio_safety.py`)
  open the same 3 real GPIO safeguard lines configured for libgpiod v2's
  real edge-event API (`edge_detection=Edge.BOTH`) and block on the
  kernel's own edge notifications instead of only re-reading level values
  when an unrelated inbound `cmd/status`/`cmd/job` message happens to ask -
  the real gap `mqtt_transport.py`'s own stale-interlock-snapshot fix
  already documented ("went unnoticed until the next unrelated poll
  happened to catch it").
- `run_forever()` gains optional `gpio_chip_path`/`key_line_offset`/
  `enclosure_line_offset`/`interlock_line_offset` keyword arguments; when
  given, a background daemon thread watches for real edge events and
  publishes an updated, retained `state` the instant a key/enclosure/
  interlock line transitions. Omitting them keeps the previous on-demand
  behavior unchanged - no new required dependency or hardware for a
  deployment without the GPIO lines wired up yet.
- 8 new tests. 65/65 `unittest` cases pass (`python tools/build_test.py`,
  up from 57).

## [0.1.1] - configurable MQTT authentication, and a retained command can no longer replay as a live one

- **.** `run_forever` had no way to authenticate against
  HYDRA-UMC-MQTT-BROKER's own real, opt-in `MQTT_AUTH_JSON` username/
  password CONNECT authentication - a broker deployed with credentials
  required was simply unreachable from this bridge. New optional
  `username`/`password` keyword arguments call paho-mqtt's own
  `username_pw_set()`; a `password` given without a `username` is
  rejected outright rather than silently connecting unauthenticated.
- **.** `on_connect`'s `subscribe("cmd/#")` makes the broker replay
  every currently-retained message on that wildcard immediately - on
  *every* reconnect, not just once at startup. A retained `cmd/job` would
  re-run the shared job gate with no new operator intent behind it.
  `handle_message()` now takes a `retained` flag and ignores any retained
  delivery before it reaches a real command; `on_message()` passes the
  real MQTT message's own `.retain` flag through.
- 8 new tests, confirmed to fail against the pre-fix code (7 real
  failures - 1 of the 8 proves an already-ignored case stays ignored, so
  it cannot itself regress against the old code) via a local revert of
  just `mqtt_transport.py`, tests kept. 57/57 `unittest` cases pass
  (`python tools/build_test.py`, up from 49).

## [0.1.0] - Saved safety evidence now proves it came from the expected independent observer

`observation.py`: `snapshot_from_fresh_mapping()`
already failed closed on a stale timestamp, but a saved evidence file's
own `observed_at_ms` proves nothing about who actually wrote it - the
same process that would otherwise fake a safe state could just as easily
fabricate a fresh-looking timestamp. New
`snapshot_from_independently_observed_mapping()` closes that gap with two
further, independent checks: `origin` must equal the one observer this
caller actually trusts (e.g. the GPIO safety daemon's own identity), and
`generation` must be a real integer strictly greater than the generation
this caller last accepted - a capture that doesn't advance the
generation is treated as a replay of an already-seen observation, never
a new one, no matter how fresh its timestamp claims to be.

`GpioLineReader` is a real `typing.Protocol` now, not a base class
with a `NotImplementedError` body - the previous form was directly
instantiable and looked like a usable (if broken) implementation.

16 new tests, 49 total, `ci_validate.py`/`build_test.py` both pass.

## [0.0.9] - A libgpiod-shaped GPIO chip + a real MQTT broker emulator, not FakeLine + a list

Until now the doubles here were `FakeLine` (a fixed bool, or one that
raises) and a bare `list` of `MqttPublish`. New
`tests/gpio_mqtt_emulator.py`:

  * `GpioChipEmulator` - three real independent `GpioLineReader` lines
    (`key_switch`/`enclosure_door`/`interlock_relay`) with an `active_low`
    option per line (real interlock hardware is very often wired
    active-low - "safe" = logic 0 - so the wire value is inverted before
    it becomes the boolean the bridge reads; a `FakeLine(True)` never
    captures that), physical-side drivers
    (`turn_key`/`open_enclosure`/`close_enclosure`/`set_interlock_healthy`),
    and `fault_chip()` making every read raise `OSError` so a test proves
    the bridge fails closed on an unplugged/offline chip.
  * `MqttBrokerEmulator` - a real retained-message store, `+`/`#` wildcard
    subscription matching, a new subscription replaying the matching
    retained message (`hydra/bridges/laser/state` is published RETAINED
    for exactly this), and `pump(bridge)` doing a real broker round trip
    (queued `cmd/#` -> `handle_message()` -> re-publish, retained store
    updated).

New `tests/test_gpio_mqtt_emulator.py` (8 tests): `cmd/status` publishes
a real retained `state` from the live GPIO lines; opening the enclosure
moves the next state to `SAFE_STOP`; a late subscriber still gets the
current retained safety state; a faulted chip fails closed; active-low
interlock wiring reads healthy at logic 0; and a job arriving right
after a key-off is gated against the live snapshot, not a stale one
(the real interlock-refresh fix below) - all through the real message flow. 40 tests total.

## [0.0.8] - Real interlocks are re-read live before every job

- **Fixed a real stale-interlock-snapshot bug (P0):** `cmd/job` reused `self._last_snapshot` - whatever
  key/enclosure/interlock state was last queried, possibly from an
  unrelated `cmd/status` poll seconds or minutes earlier - instead of
  re-reading the real, current 3 GPIO safeguards right before gating a
  new job. Reproduced: enclosure closed at an earlier poll, then it
  opens before a `cmd/job` command arrives - the stale snapshot still
  said safe, so a job could be allowed despite the CURRENT open
  enclosure. Fixed: `refresh_status()` is now called live,
  unconditionally, immediately before the gate decides -
  `self._last_snapshot` itself was removed entirely (it had no other
  reader left) rather than leaving unused cached state a future edit
  could be tempted to read from again. Same real fix already applied to
  the same class of bug in sibling HYDRA-UMC-BRIDGE-CNC. 2 tests updated/added
  (32 total, up from 31) - explicit regressions for both the dangerous
  direction (stale-safe masking a real open enclosure) and the safe
  direction (stale-unsafe no longer blocking a now-genuinely-safe job).
- **Fixed a missing translation section:** the English README's own
  "observation helper is an evidence normalizer" paragraph, linking
  `docs/CONTROLLER_EVIDENCE_BOUNDARY.md`, was missing from all 6
  translations even though the file was already listed in each one's own
  Directory Structure tree. Added the equivalent paragraph + link to all
  6.
- **`tools/bump_version.py`'s own auto-generated CHANGELOG heading
  embedded a literal calendar date** (`date.today().isoformat()`) into
  this public file - every real entry here is otherwise dated only by
  its position, never a literal date. The same bug, copied from the same
  template, found and fixed in the same pass across all 5 sibling
  bridges (BRIDGE-CNC/LASER/OPENPNP/PRINTER3D/ROS2) plus HYDRA-UMC-SDK
  and HYDRA-UMC-OS. Removed before it could ever actually land one (no
  prior real build in this repo's own history shows the script running
  mechanically without a hand-written entry replacing the stub first).
  Repo-hygiene fix, no runtime code changed, no version bump.
- **`run_forever()`'s initial MQTT connect now retries with backoff**
  (`connect_with_retry()`, new) - this bridge's process used to die
  outright if it started before HYDRA-UMC-MQTT-BROKER was listening yet,
  a real race between two independent systemd units with no ordering
  guarantee across a reboot. Only `OSError` (what an unreachable broker
  actually raises) is retried; anything else surfaces immediately as a
  real bug. Once connected, paho-mqtt's own `loop_forever()` already
  handles a later mid-session drop on its own - only the first connect
  needed this.

## [0.0.7] - Real MQTT transport over the real broker

- **`mqtt_transport.py`** (new) - reaches this bridge's already-real logic
  (`GpioSafetyProbe.read_snapshot`, `LaserCellBridge.plan`) over
  `HYDRA-UMC-MQTT-BROKER`, per the ecosystem's own "MQTT via the real
  broker, real commands included" decision. Unlike the sibling CNC/
  PRINTER3D bridges this exposes no real actuation command - this bridge
  cannot arm or fire a laser either way - so `LaserMqttBridge` only routes
  `hydra/bridges/laser/cmd/{status,job}`, publishing `hydra/bridges/laser/
  state` (retained) and `.../cmd/job/result`. `handle_message()` is a
  pure(ish) topic dispatcher over 3 real `GpioLineReader`s - fully
  testable with the same in-memory fake `test_gpio_safety.py` already
  uses, no real broker or GPIO chip required. `run_forever()` is the thin
  real-I/O glue, lazily importing the new optional `paho-mqtt` dependency
  the same way `open_gpio_safety_lines()` already lazily imports `gpiod`.
  13 new tests.

## [0.0.6] - Real, controller-neutral GPIO interlock reading (pre-real: connected, not simulated)

- **`gpio_safety.py`** (new) - this bridge's first real transport:
  `GpioSafetyProbe.read_snapshot()` reads the 3 real, independent safeguard
  signals (`key_enabled`/`enclosure_closed`/`interlock_healthy`) over real
  GPIO lines rather than a saved/simulated mapping. Deliberately does NOT
  assume any specific laser controller brand or G-code dialect - this
  bridge stays controller-neutral by design (see README/BRIDGE_GUIDE):
  what's universal across laser cutters is that these 3 safeguards are
  typically wired as simple, independently-certified digital signals (key
  switch, door sensor, interlock relay feedback), so reading them directly
  over GPIO is exactly the kind of independent evidence this bridge's own
  design already calls for, without inventing a protocol decision that
  isn't this bridge's to make. Uses libgpiod v2 (`gpiod`, new optional
  `[gpio]` extra) - the same real library already chosen for the
  `HYDRA_DATA_READY` line in the HYDRA-UMC CM5<->STM32H745 SPI link. A GPIO
  read failure fails all 3 safeguards closed, never assumed True.
  `open_gpio_safety_lines()` is the one place `gpiod` is imported, lazily,
  degrading to a clear `RuntimeError` instead of a bare `ImportError` when
  it isn't installed.
- 4 new regression tests (against an in-memory fake `GpioLineReader` - no
  real GPIO chip needed) - 16/16 tests passing.

## [0.0.5] - Real paused-vs-running distinction

- Added pure offline freshness validation for saved interlock evidence. A
  missing, stale, future or malformed timestamp fails closed; it cannot turn a
  previously safe snapshot into authority to arm or fire a laser.
- **`cell.py`** - `LaserSafetySnapshot.machine_state()`'s `PAUSED` controller
  state now maps to `HOLDING` instead of `RUNNING`. A paused job means the
  beam is not actively cutting/engraving - a real, distinct condition, not
  just a naming nuance, matching the same real "paused is not running" fix
  already made in the sibling PRINTER3D (Moonraker `print_stats.state=
  paused`) and CNC (GRBL `Hold`) bridges. Does not change any dispatch
  decision - `evaluate_job()` only permits productive work on `IDLE` either
  way - only the accuracy of the reported state.
- 2 new regression tests - 12/12 tests passing.

## [0.0.4]

- Added `docs/BRIDGE_GUIDE.md`, defining controller-neutral safety scope,
  script conventions and the laser hardware acceptance gate.
- Removed the duplicated terminal BUILD & RUN section from all seven README files.
- Added an offline CLI for inspecting saved laser-safety evidence JSON with no
  controller connection, arm, configuration, upload or fire path.
- Added CLI contract coverage; the full suite now has nine tests.
- Synchronized package metadata, ecosystem manifest and all seven README files.

## [0.0.3]

- Added read-only normalization of external laser-safety evidence without a
  controller connection, upload, arming or firing path.
- Made missing, numeric or text-like key, enclosure and interlock values fail
  closed instead of being mistaken for healthy safeguards.
- Added four deterministic evidence-boundary tests; the suite now has eight
  tests. Package metadata, manifest and all seven README files are synchronized.

## [0.0.2]

- Made an unexpected non-text controller state fail safe as `OFFLINE` instead
  of raising while evaluating the laser cell boundary.
- Synchronized the English README and all six translated README files with
  the current version.
- Successful incremental build: synchronized package metadata and
  `hydra-umc.project.json`.

## [0.0.1]

- Added fail-safe laser interlock snapshot and SDK safety-gate tests.
- Added non-mutating build-test scripts and CI SDK checkout.
- Standardized README (all 7 languages) and project banner to match the
  rest of the ecosystem's established-project structure.
- Promoted to `established`: manifest, docs, build-test/CI, real local
  verification and no private-doc references all confirmed - no
  functional gap found in this bridge's own small, SDK-delegated core.
