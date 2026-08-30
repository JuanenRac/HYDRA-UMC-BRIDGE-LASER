<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laser controller evidence boundary
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Laser Controller Evidence Boundary

`snapshot_from_mapping()` transforms evidence already collected by another layer into `LaserSafetySnapshot`. It does not open a connection, arm a source, alter a controller configuration, upload a job or fire a laser.

An idle result requires a literal `IDLE` controller state and three genuine Boolean `true` safety signals: `key_enabled`, `enclosure_closed` and `interlock_healthy`. Missing fields, numbers and strings never count as a healthy safeguard and resolve to `SAFE_STOP`.

Any future controller adapter needs an identified documented interface, independent certified safety authority, authenticated access where applicable and bench/HIL validation before it is connected to a laser cell.

For an offline review, run `py tools/inspect_controller_evidence.py evidence.json`. It reads a saved JSON mapping only and emits the canonical SDK machine state; it never opens a serial or network link and has no arm/fire path.
