# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - The service: one entry point, one configuration file
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""Run the bridge as a service: ``python -m hydra_umc_bridge_laser --config /etc/hydra-umc/bridge-laser.toml``.

Everything that depends on the machine lives in the configuration file and nothing in the code: the GPIO chip and the three
lines, their polarity, bias and debounce, the serial port of the GRBL controller, the MQTT broker, where the state of the
cell comes from and the optional auxiliary safeguards. The file is TOML; a key the service does not know is refused, so a
typo cannot silently leave a safeguard unconfigured.

Credentials do not go in the file: the MQTT user, password and TLS come from the service environment (``HYDRA_MQTT_*``),
which systemd reads from a file only root can read.

Fail-closed rules of the service:

* without a ``[controller]`` section the controller state is ``""`` (the bridge reads it as OFFLINE);
* the state of the cell comes from the ``[cell_state]`` section; a file that is missing, unreadable, unknown or older than
  ``max_age_seconds`` is ``SAFE_STOP``, and the default source is a fixed ``INHIBITED``;
* the three safeguard lines have no defaults: the safe level depends on the wiring, so the file has to say it.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from hydra_umc_sdk.bridge_contract import CellState

from .auxiliary import AuxiliaryCheck, AuxiliarySupervisor
from .global_stop import DEFAULT_TOPIC, GlobalStopSettings
from .gpio_safety import GpioLineSettings

CONFIG_ENVIRONMENT = "HYDRA_UMC_BRIDGE_LASER_CONFIG"
DEFAULT_CONFIG_PATH = "/etc/hydra-umc/bridge-laser.toml"

_LOG = logging.getLogger(__name__)


class ConfigError(ValueError):
    """The configuration file is wrong; the message names the key."""


@dataclass(frozen=True)
class MqttSettings:
    host: str = "127.0.0.1"
    port: int = 1883
    client_id: str = "hydra-umc-bridge-laser"
    max_connect_attempts: int = 5
    connect_retry_delay_seconds: float = 2.0


@dataclass(frozen=True)
class LineConfig:
    line: int
    settings: GpioLineSettings


@dataclass(frozen=True)
class GpioConfig:
    chip: str
    key: LineConfig
    enclosure: LineConfig
    interlock: LineConfig
    edge_watch: bool = True


@dataclass(frozen=True)
class ControllerConfig:
    device: str
    baud: int = 115200
    timeout_seconds: float = 1.0


@dataclass(frozen=True)
class CellStateConfig:
    """``fixed``: always ``value``. ``file``: the first word of ``path``, refused when older than ``max_age_seconds``."""

    source: str = "fixed"
    value: CellState = CellState.INHIBITED
    path: str | None = None
    max_age_seconds: float = 30.0


@dataclass(frozen=True)
class AuxiliaryConfig:
    """One auxiliary safeguard read from a file (``1``/``0``) or, with ``max_celsius``, a temperature in a file."""

    name: str
    path: str
    max_celsius: float | None = None


@dataclass(frozen=True)
class ServiceConfig:
    gpio: GpioConfig
    mqtt: MqttSettings = field(default_factory=MqttSettings)
    controller: ControllerConfig | None = None
    cell_state: CellStateConfig = field(default_factory=CellStateConfig)
    auxiliary: tuple[AuxiliaryConfig, ...] = ()
    idempotency_path: str | None = None
    global_stop: GlobalStopSettings = field(default_factory=GlobalStopSettings)


def _table(parent: dict, key: str, *, required: bool = False) -> dict:
    value = parent.get(key)
    if value is None:
        if required:
            raise ConfigError(f"[{key}] is required")
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"[{key}] must be a table")
    return value


def _only(table: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"unknown key in {where}: {', '.join(unknown)}")


def _kind(table: dict, key: str, kind: type, where: str, default: object = None, *, required: bool = False):
    if key not in table:
        if required:
            raise ConfigError(f"{where}.{key} is required")
        return default
    value = table[key]
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) if kind is float else isinstance(value, kind) and (kind is not int or not isinstance(value, bool))
    if not ok:
        raise ConfigError(f"{where}.{key} must be a {kind.__name__}")
    return float(value) if kind is float else value


def _line(parent: dict, name: str) -> LineConfig:
    table = _table(parent, name, required=True)
    where = f"gpio.{name}"
    _only(table, {"line", "active_low", "bias", "debounce_ms"}, where)
    line = _kind(table, "line", int, where, required=True)
    if line < 0:
        raise ConfigError(f"{where}.line must not be negative")
    # the safe level depends on the wiring and not on the code: the polarity has no default
    active_low = _kind(table, "active_low", bool, where, required=True)
    settings = GpioLineSettings(active_low, _kind(table, "bias", str, where), _kind(table, "debounce_ms", float, where, 10.0))
    settings.resolved_bias()  # refuses a wrong bias or a negative debounce here, at start, and not on the first reading
    return LineConfig(line, settings)


def parse_config(data: dict) -> ServiceConfig:
    """Turn the parsed TOML into the configuration, refusing what is unknown or wrong."""

    _only(data, {"mqtt", "gpio", "controller", "cell_state", "auxiliary", "idempotency", "global_stop"}, "the file")
    mqtt_table = _table(data, "mqtt")
    _only(mqtt_table, {"host", "port", "client_id", "max_connect_attempts", "connect_retry_delay_seconds"}, "mqtt")
    defaults = MqttSettings()
    mqtt = MqttSettings(
        _kind(mqtt_table, "host", str, "mqtt", defaults.host),
        _kind(mqtt_table, "port", int, "mqtt", defaults.port),
        _kind(mqtt_table, "client_id", str, "mqtt", defaults.client_id),
        _kind(mqtt_table, "max_connect_attempts", int, "mqtt", defaults.max_connect_attempts),
        _kind(mqtt_table, "connect_retry_delay_seconds", float, "mqtt", defaults.connect_retry_delay_seconds),
    )
    if not 0 < mqtt.port <= 65535:
        raise ConfigError("mqtt.port must be 1 to 65535")

    gpio_table = _table(data, "gpio", required=True)
    _only(gpio_table, {"chip", "edge_watch", "key", "enclosure", "interlock"}, "gpio")
    key, enclosure, interlock = _line(gpio_table, "key"), _line(gpio_table, "enclosure"), _line(gpio_table, "interlock")
    if len({key.line, enclosure.line, interlock.line}) != 3:
        raise ConfigError("gpio: the key, enclosure and interlock lines must be three different lines")
    gpio = GpioConfig(_kind(gpio_table, "chip", str, "gpio", required=True), key, enclosure, interlock, _kind(gpio_table, "edge_watch", bool, "gpio", True))

    controller = None
    if "controller" in data:
        table = _table(data, "controller")
        _only(table, {"device", "baud", "timeout_seconds"}, "controller")
        controller = ControllerConfig(
            _kind(table, "device", str, "controller", required=True),
            _kind(table, "baud", int, "controller", 115200),
            _kind(table, "timeout_seconds", float, "controller", 1.0),
        )

    cell_table = _table(data, "cell_state")
    _only(cell_table, {"source", "value", "path", "max_age_seconds"}, "cell_state")
    source = _kind(cell_table, "source", str, "cell_state", "fixed")
    if source not in {"fixed", "file"}:
        raise ConfigError("cell_state.source must be fixed or file")
    try:
        value = CellState(_kind(cell_table, "value", str, "cell_state", CellState.INHIBITED.value))
    except ValueError as error:
        raise ConfigError(f"cell_state.value must be one of {', '.join(item.value for item in CellState)}") from error
    path = _kind(cell_table, "path", str, "cell_state")
    max_age = _kind(cell_table, "max_age_seconds", float, "cell_state", 30.0)
    if source == "file" and not path:
        raise ConfigError("cell_state.path is required when the source is file")
    if max_age <= 0:
        raise ConfigError("cell_state.max_age_seconds must be positive")
    cell_state = CellStateConfig(source, value, path, max_age)

    checks = data.get("auxiliary", [])
    if not isinstance(checks, list):
        raise ConfigError("[[auxiliary]] must be an array of tables")
    auxiliary = []
    for index, table in enumerate(checks):
        if not isinstance(table, dict):
            raise ConfigError("[[auxiliary]] must be an array of tables")
        where = f"auxiliary[{index}]"
        _only(table, {"name", "path", "max_celsius"}, where)
        auxiliary.append(AuxiliaryConfig(_kind(table, "name", str, where, required=True), _kind(table, "path", str, where, required=True), _kind(table, "max_celsius", float, where)))
    AuxiliarySupervisor([AuxiliaryCheck(item.name, lambda: None, item.max_celsius) for item in auxiliary])  # names and limits are checked now

    idem = _table(data, "idempotency")
    _only(idem, {"path"}, "idempotency")
    stop_table = _table(data, "global_stop")
    _only(stop_table, {"enabled", "topic", "strict"}, "global_stop")
    try:
        global_stop = GlobalStopSettings(
            _kind(stop_table, "enabled", bool, "global_stop", False),
            _kind(stop_table, "topic", str, "global_stop", DEFAULT_TOPIC),
            _kind(stop_table, "strict", bool, "global_stop", False),
        )
    except ValueError as error:
        raise ConfigError(f"global_stop.topic: {error}") from error
    return ServiceConfig(gpio, mqtt, controller, cell_state, tuple(auxiliary), _kind(idem, "path", str, "idempotency"), global_stop)


def load_config(path: str | os.PathLike[str]) -> ServiceConfig:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror or error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from error
    return parse_config(data)


def _fresh_text(path: str, max_age_seconds: float, clock: Callable[[], float]) -> str | None:
    """The first word of a small file written by someone else; ``None`` when it is missing, unreadable, empty or stale."""

    try:
        age = clock() - os.stat(path).st_mtime
        if age > max_age_seconds or age < -max_age_seconds:
            return None
        with open(path, encoding="utf-8") as handle:
            words = handle.read(256).split()
    except (OSError, UnicodeDecodeError):
        return None
    return words[0] if words else None


def cell_state_reader(config: CellStateConfig, *, clock: Callable[[], float] = time.time) -> Callable[[], CellState]:
    """The ``cell_state`` callable of the bridge: always the current reading, and ``SAFE_STOP`` whenever it cannot be trusted."""

    if config.source == "fixed":
        value = config.value
        return lambda: value
    path, max_age = config.path or "", config.max_age_seconds

    def read() -> CellState:
        word = _fresh_text(path, max_age, clock)
        try:
            return CellState(word) if word is not None else CellState.SAFE_STOP
        except ValueError:
            return CellState.SAFE_STOP

    return read


def auxiliary_supervisor(items: Sequence[AuxiliaryConfig], *, clock: Callable[[], float] = time.time) -> AuxiliarySupervisor | None:
    """The optional extra safeguards; ``None`` when none is declared. A file read as ``1`` is satisfied, a temperature file is a number in degrees Celsius."""

    if not items:
        return None

    def reader(item: AuxiliaryConfig) -> Callable[[], object]:
        def read() -> object:
            word = _fresh_text(item.path, 30.0, clock)
            if word is None:
                return None
            if item.max_celsius is not None:
                return float(word)
            return word == "1"

        return read

    return AuxiliarySupervisor([AuxiliaryCheck(item.name, reader(item), item.max_celsius) for item in items])


def build_bridge(config: ServiceConfig, *, open_gpio=None, open_controller=None, clock: Callable[[], float] = time.time):
    """The bridge and what it has to close or start; ``open_gpio``/``open_controller`` are for tests."""

    from hydra_umc_sdk.job_intake import IdempotencyStore

    from .gpio_safety import open_gpio_safety
    from .grbl_state import open_grbl_laser_state
    from .mqtt_transport import LaserMqttBridge

    gpio = (open_gpio or open_gpio_safety)(
        config.gpio.chip,
        config.gpio.key.line,
        config.gpio.enclosure.line,
        config.gpio.interlock.line,
        key=config.gpio.key.settings,
        enclosure=config.gpio.enclosure.settings,
        interlock=config.gpio.interlock.settings,
    )
    if config.controller is not None:
        controller_state = (open_controller or open_grbl_laser_state)(config.controller.device, config.controller.baud, config.controller.timeout_seconds)
    else:
        controller_state = lambda: ""  # noqa: E731 - no controller declared: the bridge reads OFFLINE
    idempotency = IdempotencyStore(config.idempotency_path) if config.idempotency_path else IdempotencyStore()
    bridge = LaserMqttBridge(
        gpio.lines,
        controller_state,
        cell_state_reader(config.cell_state, clock=clock),
        idempotency,
        clock=clock,
        auxiliary=auxiliary_supervisor(config.auxiliary, clock=clock),
        global_stop=config.global_stop,
    )
    return bridge, gpio


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hydra_umc_bridge_laser", description="HYDRA-UMC laser cell bridge service")
    parser.add_argument("--config", default=os.environ.get(CONFIG_ENVIRONMENT, DEFAULT_CONFIG_PATH), help=f"configuration file (default: ${CONFIG_ENVIRONMENT} or {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--check", action="store_true", help="read and validate the configuration, then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"hydra-umc-bridge-laser: configuration error: {error}", file=sys.stderr)
        return 2
    if args.check:
        print(f"CONFIG=PASS {args.config}")
        return 0

    from .mqtt_transport import run_forever

    try:
        bridge, gpio = build_bridge(config)
    except RuntimeError as error:  # gpiod or pyserial missing
        print(f"hydra-umc-bridge-laser: {error}", file=sys.stderr)
        return 3
    mqtt = config.mqtt
    # Restart=on-failure: a non-zero exit when the loop ends brings the service back
    try:
        run_forever(
            bridge,
            mqtt.host,
            mqtt.port,
            mqtt.client_id,
            max_connect_attempts=mqtt.max_connect_attempts,
            connect_retry_delay_seconds=mqtt.connect_retry_delay_seconds,
            edge_watcher=gpio.watcher if config.gpio.edge_watch else None,
        )
    except Exception:  # noqa: BLE001
        _LOG.exception("the bridge stopped")
        return 1
    return 1
