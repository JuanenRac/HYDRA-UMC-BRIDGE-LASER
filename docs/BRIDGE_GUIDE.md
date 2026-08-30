<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Technical bridge guide
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER Technical Guide

## Scope and operating model

`LaserSafetySnapshot` requires a literal idle state and three independently reported safeguards: key enabled, enclosure closed and interlock healthy. `observation.py` normalizes saved local evidence and treats every missing, numeric or text-like safeguard as unsafe. `snapshot_from_fresh_mapping()` additionally requires an explicit `observed_at_ms` value to be no older than a caller-supplied bound; stale, future or malformed evidence clears the interlock health signal. The bridge can gate external auxiliary work but cannot configure, arm or fire a laser.

`LaserSafetySnapshot.machine_state()`'s `controller_state` vocabulary: `IDLE` -> `IDLE`; `RUN`/`RUNNING` -> `RUNNING`; `PAUSED` -> `HOLDING` (a paused job means the beam is not actively cutting/engraving, a real, distinct condition from actively running); `FAULT`/`ALARM`/`ERROR` -> `FAULT`. Any other token stays `OFFLINE`, the same conservative fail-safe default used for every unrecognized signal in this bridge.

## Compatible software

No live laser application/controller is integrated yet. The bridge is deliberately controller-neutral until a specific machine and documented safety interface are chosen. Future compatibility may target controller software that can expose independently certified state, key, enclosure and interlock observations; a generic G-code sender is not a valid laser safety adapter.

## Scripts and verification

| Script | Purpose | Changes version/CHANGELOG? |
|---|---|---|
| `build-test.bat` / `build-test.sh` | Compile and run local safety tests | No |
| `build.bat` / `build.sh` | Validate, then increment version and CHANGELOG | Yes, after success |
| `tools/inspect_controller_evidence.py` | Normalize a saved JSON capture only | No |

## Adding a new script

Use the standard header, state the non-arming scope, number console steps and add `pause` to `.bat`. Reusable parsing must be tested and compiled by `build-test`. No script may open a laser connection, modify safety configuration, upload a job, arm or fire a source.

## Hardware acceptance gate

Choose the controller and documented interface, validate signals against certified safety hardware, test stale/disconnected behavior, prove independent E-STOP and conduct dry HIL trials without active material. Only then can a separately reviewed controller adapter be considered.
