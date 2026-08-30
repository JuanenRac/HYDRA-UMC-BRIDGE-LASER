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
