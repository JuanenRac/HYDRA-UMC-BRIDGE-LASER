# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Public package interface
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Laser-cell coordination that preserves laser controller safety authority."""

from .cell import LaserCellBridge, LaserSafetySnapshot
from .gpio_safety import (
    EdgeEventSource,
    GpioLineReader,
    GpioSafetyLines,
    GpioSafetyProbe,
    open_gpio_edge_watcher,
    open_gpio_safety_lines,
    watch_for_interlock_edges,
)
from .mqtt_transport import (
    build_edge_watch_on_change,
    connect_with_retry,
    LaserMqttBridge,
    MqttPublish,
    run_forever,
    start_edge_watch_thread,
)
from .observation import IndependentObservation, snapshot_from_fresh_mapping, snapshot_from_independently_observed_mapping, snapshot_from_mapping

__all__ = [
    "LaserCellBridge",
    "LaserSafetySnapshot",
    "snapshot_from_mapping",
    "snapshot_from_fresh_mapping",
    "snapshot_from_independently_observed_mapping",
    "IndependentObservation",
    "GpioSafetyProbe",
    "GpioSafetyLines",
    "GpioLineReader",
    "open_gpio_safety_lines",
    "EdgeEventSource",
    "open_gpio_edge_watcher",
    "watch_for_interlock_edges",
    "LaserMqttBridge",
    "MqttPublish",
    "connect_with_retry",
    "run_forever",
    "build_edge_watch_on_change",
    "start_edge_watch_thread",
]
