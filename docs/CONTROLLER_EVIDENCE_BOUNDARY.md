<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laser controller evidence boundary
Copyright (C) JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Laser Controller Evidence Boundary

`snapshot_from_mapping()`, `snapshot_from_fresh_mapping()` and `snapshot_from_independently_observed_mapping()` transform evidence already collected by another layer into `LaserSafetySnapshot`. None of them open a connection, arm a source, alter a controller configuration, upload a job or fire a laser.

An idle result requires a literal `IDLE` controller state and three genuine Boolean `true` safety signals: `key_enabled`, `enclosure_closed` and `interlock_healthy`. Missing fields, numbers and strings never count as a healthy safeguard and resolve to `SAFE_STOP`.

`snapshot_from_fresh_mapping()` additionally requires an explicit `observed_at_ms` timestamp that is no older than a caller-supplied `max_age_ms` bound (against the caller's own `now_ms`); a missing, non-integer, future or stale timestamp clears the `interlock_healthy` signal rather than trusting an otherwise-healthy-looking capture.

`snapshot_from_independently_observed_mapping()` closes a further gap a bare timestamp can't: a saved evidence file's own `observed_at_ms` proves nothing about who actually wrote it, so a process faking a safe state could just as easily fabricate a fresh-looking one. On top of the same freshness check, it requires the payload's `origin` field to equal the one observer the caller actually trusts (e.g. the GPIO safety daemon's own identity), and its `generation` field to be a non-negative integer strictly greater than the `min_generation` the caller last accepted - so a replayed capture (the exact same reading with only its timestamp bumped) can never look like a new one. It returns an `IndependentObservation` (`snapshot` plus the accepted `generation`, or `generation=None` when the snapshot itself was rejected) so the caller can remember and pass back the right `min_generation` on its next read.

Any future controller adapter needs an identified documented interface, independent certified safety authority, authenticated access where applicable and bench/HIL validation before it is connected to a laser cell.

For an offline review, run `py tools/inspect_controller_evidence.py evidence.json`. It reads a saved JSON mapping only and emits the canonical SDK machine state; it never opens a serial or network link and has no arm/fire path.
