# Bench tests

Every test below is **not executed**: the bridge has run against a simulated GPIO chip, files that stand for a 1-Wire sensor and a simulated GRBL board, never against a real cell. Fill the result column only after a person ran the step.

## What the software already covers (no cell needed)

- The unit tests, the GPIO and MQTT emulator (`tests/gpio_mqtt_emulator.py`) and the broker integration test run with `python tools/hydra_project_tool.py test`.
- The readers of the auxiliary safeguards (`w1`, `gpio`, simulated) are tested with files and a fake libgpiod, and a reader that cannot read counts as not satisfied.
- `hydra-umc-bridge-laser --check` validates the configuration file without starting anything.

## Setup

- A computer with a GPIO chip (a single-board computer) and the three safeguard lines (key, enclosure, interlock) wired as in `WIRING_GUIDE.md`. The laser has **no power on the tube or the source**: no step of this bench needs the laser to fire.
- Optionally a DS18B20 on the 1-Wire bus and a second input line for the auxiliary readers (`[auxiliary_readers] enabled = true`).
- A GRBL board on a serial port, for the state reader.

## Steps

| # | Step | Expected result | Result |
|---|------|-----------------|--------|
| 1 | Run `--check` with the real configuration file. | The file is accepted; a wrong key or two equal lines are refused. | not executed |
| 2 | With the three safeguards in the safe position, ask `cmd/status`. | The three read as satisfied. | not executed |
| 3 | Open the enclosure contact. | Within the debounce time a retained `state` shows the enclosure as not satisfied. | not executed |
| 4 | Cut each safeguard wire in turn. | Each one reads as not satisfied (the bias makes a cut wire unsafe). | not executed |
| 5 | Send a job with the enclosure open. | Answered with a refusal; `ABORT` is answered with `"forwarded": false`. | not executed |
| 6 | Read a DS18B20 at room temperature, then warm it above `max_celsius`. | Satisfied below the limit, not satisfied above it; a reading of 85 or -127 is not taken as a measure. | not executed |
| 7 | Unplug the sensor. | The check counts as not satisfied. | not executed |
| 8 | Query the GRBL state with the board idle, then with its door pin active. | `Idle`, then `Door:1`; the bridge writes only `?`. | not executed |
| 9 | Stop the service and read the availability topic. | `offline` is published by the broker. | not executed |

## What this bench cannot show

A real laser command path does not exist. The bridge never arms or fires a laser, and the physical e-stop and interlocks remain the only safety of the machine.
