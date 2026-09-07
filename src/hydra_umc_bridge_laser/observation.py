# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Read-only controller safety normalization
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Normalize local safety evidence without connecting to, arming or firing a laser."""

from __future__ import annotations

from collections.abc import Mapping

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
