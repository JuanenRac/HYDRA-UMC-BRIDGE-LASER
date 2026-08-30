<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Change history
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Changelog

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
