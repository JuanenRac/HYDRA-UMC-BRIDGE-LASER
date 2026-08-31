<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Change history
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Changelog

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

## [0.0.4] - 2026-08-30

- Added `docs/BRIDGE_GUIDE.md`, defining controller-neutral safety scope,
  script conventions and the laser hardware acceptance gate.
- Removed the duplicated terminal BUILD & RUN section from all seven README files.
- Added an offline CLI for inspecting saved laser-safety evidence JSON with no
  controller connection, arm, configuration, upload or fire path.
- Added CLI contract coverage; the full suite now has nine tests.
- Synchronized package metadata, ecosystem manifest and all seven README files.

## [0.0.3] - 2026-08-30

- Added read-only normalization of external laser-safety evidence without a
  controller connection, upload, arming or firing path.
- Made missing, numeric or text-like key, enclosure and interlock values fail
  closed instead of being mistaken for healthy safeguards.
- Added four deterministic evidence-boundary tests; the suite now has eight
  tests. Package metadata, manifest and all seven README files are synchronized.

## [0.0.2] - 2026-08-30

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
