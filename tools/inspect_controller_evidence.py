#!/usr/bin/env python3
# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Offline laser-evidence inspection CLI
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Normalize a saved local laser-safety JSON file without opening any link."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from hydra_umc_bridge_laser.observation import snapshot_from_mapping  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect saved laser evidence; never contacts or arms a controller.")
    parser.add_argument("evidence", type=Path, help="Local JSON safety-evidence mapping")
    arguments = parser.parse_args()
    try:
        payload = json.loads(arguments.evidence.read_text(encoding="utf-8"))
        snapshot = snapshot_from_mapping(payload)
        print(json.dumps({"machine_state": snapshot.machine_state().value}, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"machine_state": "safe_stop", "reason": f"evidence inspection failed safely: {error}"}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
