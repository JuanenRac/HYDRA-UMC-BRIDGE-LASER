<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Wiring guide for the three safeguards
Copyright (C) JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# Wiring the three safeguards

The bridge reads three independent signals - key switch, enclosure (door) and interlock - and treats a cell as safe only when all three are healthy at the same time. What "healthy" looks like on the wire is a property of the wiring, not of the software, so it is declared per line (`GpioLineSettings`) and never guessed.

This bridge is an extra, independent reader. The laser's own certified interlocks and E-STOP stay in charge of the beam; nothing here arms, fires or stops a laser.

## Polarity: `active_low`

`GpioLineSettings(active_low=...)` says at which electrical level the signal is healthy.

| Wiring | Healthy level | `active_low` |
|---|---|---|
| Normally-closed contact to GND, input pulled up | low (contact closed) | `True` |
| Contact or relay output that drives the line high when healthy | high | `False` |

With `active_low=True` the bridge reports a safeguard as healthy when the line is at logic 0. There is no default: a polarity that was never declared would be a guess about a safety signal.

## Bias: a cut wire must read as unsafe

An input with nothing driving it floats. The bias decides what it reads when the wire is cut or the connector is out.

- Healthy at logic 0 (`active_low=True`): use a **pull-up**. A cut wire reads high, which is the unsafe level.
- Healthy at logic 1 (`active_low=False`): use a **pull-down**. A cut wire reads low, which is the unsafe level.

When `bias` is not given, this is exactly what the bridge picks. Give `bias="disabled"` or `"as-is"` only when the board already has an external pull resistor that does the same.

## Normally closed versus normally open

Wire the safe condition as a CLOSED circuit (a normally-closed contact held closed by the door, the key, the interlock relay's energised contact): a broken wire, a loose terminal or a lost supply then looks like "unsafe" and not like "safe". Do not use a normally-open contact whose closing means "safe" unless a pull-down turns a cut wire into the unsafe reading.

For a stronger check, read two channels per safeguard (one normally-closed, one normally-open) and require that they are complementary; a wire shorted or cut on one of them then shows as a disagreement. The bridge reads one line per safeguard today.

## Debounce

Mechanical contacts bounce. `debounce_ms` (10 ms by default) makes the kernel ignore transitions shorter than that, so a door that rattles does not produce a burst of states. Use 0 only for a signal that is already conditioned.

## One request for all three lines

A GPIO line can belong to one request at a time. `open_gpio_safety()` therefore opens the three lines once, for both reading the levels and watching for edges, and returns them together:

```python
from hydra_umc_bridge_laser import GpioLineSettings, LaserMqttBridge, open_gpio_safety, run_forever

gpio = open_gpio_safety(
    "/dev/gpiochip0", 17, 27, 22,          # key, enclosure, interlock offsets
    key=GpioLineSettings(active_low=False),
    enclosure=GpioLineSettings(active_low=True),
    interlock=GpioLineSettings(active_low=True),
)
bridge = LaserMqttBridge(gpio.lines, controller_state, cell_state)
run_forever(bridge, "127.0.0.1", edge_watcher=gpio.watcher)
```

The three offsets must be three different lines. If another process (for example the HYDRA-UMC CM5 link to the STM32) already requests a line, the kernel refuses with "Device or resource busy": give each process its own lines.

## Before trusting it

Nothing here has run on a real GPIO chip yet. Before relying on it: with the door closed, open it and see the state change to `SAFE_STOP`; pull each connector in turn and see the same; check the behaviour when the key is turned; and repeat each of these with the cell powered down and powered up.
