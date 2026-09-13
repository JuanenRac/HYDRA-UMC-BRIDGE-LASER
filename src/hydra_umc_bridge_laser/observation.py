# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Read-only controller safety normalization
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Normalize local safety evidence without connecting to, arming or firing a laser."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .cell import LaserSafetySnapshot


def _strict_bool(value: object) -> bool:
    """Only a genuine true signal counts as a live laser safeguard."""

    return value is True


def snapshot_from_mapping(payload: object) -> LaserSafetySnapshot:
    """Build a conservative snapshot from already-collected controller evidence."""

    if not isinstance(payload, Mapping):
        return LaserSafetySnapshot("", False, False, False)
    state = payload.get("controller_state", payload.get("state", ""))
    return LaserSafetySnapshot(
        state if isinstance(state, str) else "",
        _strict_bool(payload.get("key_enabled")),
        _strict_bool(payload.get("enclosure_closed")),
        _strict_bool(payload.get("interlock_healthy")),
    )


def snapshot_from_fresh_mapping(payload: object, *, now_ms: int, max_age_ms: int) -> LaserSafetySnapshot:
    """Accept saved laser evidence only while its explicit timestamp is fresh.

    This is deliberately a pure, offline boundary: callers supply both the
    captured mapping and their clock.  It cannot query, arm or fire a laser.
    Invalid clocks, absent timestamps and future/stale captures fail closed by
    clearing the interlock-health signal.
    """

    snapshot = snapshot_from_mapping(payload)
    observed_at = payload.get("observed_at_ms") if isinstance(payload, Mapping) else None
    valid_clock = (
        isinstance(now_ms, int)
        and not isinstance(now_ms, bool)
        and isinstance(max_age_ms, int)
        and not isinstance(max_age_ms, bool)
        and max_age_ms >= 0
        and isinstance(observed_at, int)
        and not isinstance(observed_at, bool)
        and observed_at <= now_ms
        and now_ms - observed_at <= max_age_ms
    )
    if valid_clock:
        return snapshot
    return LaserSafetySnapshot(snapshot.controller_state, snapshot.key_enabled, snapshot.enclosure_closed, False)


@dataclass(frozen=True)
class IndependentObservation:
    """A snapshot plus the generation it was actually accepted at.

    A caller remembers ``generation`` and passes it back as
    ``min_generation`` on its next read, so a replayed capture (the exact
    same observation, just with its timestamp bumped) can never look like
    a brand new one. ``generation`` is ``None`` whenever ``snapshot``
    itself was rejected - there is nothing genuine to remember from a
    capture that was already unhealthy, stale, or not from the expected
    observer.
    """

    snapshot: LaserSafetySnapshot
    generation: int | None


def snapshot_from_independently_observed_mapping(
    payload: object,
    *,
    now_ms: int,
    max_age_ms: int,
    expected_origin: str,
    min_generation: int | None,
) -> IndependentObservation:
    """Accept saved laser evidence only when it is BOTH fresh (see
    ``snapshot_from_fresh_mapping``) AND genuinely produced, for the first
    time, by the one independent observer this caller actually trusts.

    A saved evidence file's own ``observed_at_ms`` proves nothing about
    who wrote it - the same process that would otherwise fake a safe
    state could just as easily fabricate a fresh-looking timestamp. Two
    further, independent checks close that gap:

    - ``origin`` must be a non-empty string equal to ``expected_origin``
      (e.g. the GPIO safety daemon's own identity) - evidence claiming any
      other origin, or none, fails closed the same way a stale timestamp
      already does.
    - ``generation`` must be a real, non-negative integer strictly greater
      than ``min_generation`` (the generation this caller last accepted,
      or ``None`` on its very first read) - a capture that does not
      advance the generation is treated as a replay of an
      already-observed reading, never a new one, no matter how fresh its
      timestamp claims to be.
    """

    base = snapshot_from_fresh_mapping(payload, now_ms=now_ms, max_age_ms=max_age_ms)
    if not base.interlock_healthy:
        return IndependentObservation(base, None)

    origin = payload.get("origin") if isinstance(payload, Mapping) else None
    generation = payload.get("generation") if isinstance(payload, Mapping) else None
    valid_origin = isinstance(origin, str) and origin != "" and origin == expected_origin
    valid_generation = (
        isinstance(generation, int)
        and not isinstance(generation, bool)
        and generation >= 0
        and (min_generation is None or generation > min_generation)
    )
    if not (valid_origin and valid_generation):
        rejected = LaserSafetySnapshot(base.controller_state, base.key_enabled, base.enclosure_closed, False)
        return IndependentObservation(rejected, None)
    return IndependentObservation(base, generation)
