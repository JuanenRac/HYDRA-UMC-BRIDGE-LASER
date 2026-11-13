# Simulation bench

The laser bridge reads three independent safeguards (key, enclosure, interlock) from GPIO lines. The emulator replaces the chip and the broker: lines that flip, lines that raise, wrong wiring, retained messages and wildcard subscriptions.

The simulation bench replaces the hardware with a libgpiod-shaped GPIO chip and a retained-message MQTT bus (`tests/gpio_mqtt_emulator.py`) around the real bridge code. It proves the parsing, the gating, the transports and the failure paths of the bridge; it says nothing about
a real machine, real timing or real safety functions.

## Run it

```
python -m unittest -v <modules>
```

from the `tests` folder, with `src` of this repository and `clients/python/src` of the SDK on `PYTHONPATH` (the same layout `python tools/build_test.py` uses). The
workflow named "Simulation bench" does exactly this on a clean Linux runner on every push and pull request, by hand and once a week, with nothing but Python; a second job adds the kernel GPIO simulator (`gpio-sim`).

The example settings in `deploy/` show the configuration the service reads; the emulator does not need it.

## What it runs

| File | What it exercises |
|------|-------------------|
| `tests/test_gpio_mqtt_emulator.py` | the emulator and the way the bridge behaves against it |
| `tests/test_gpio_safety.py` | the three safeguards read live before every gate |
| `tests/test_auxiliary_inputs.py` | the auxiliary inputs, such as the one-wire temperature reader, read from simulated files and requests |
| `tests/test_auxiliary_sensor_scenarios.py` | a simulated one-wire tree and extraction line through the real readers and the bridge: power-up value, bad CRC, unplugged sensor, heating and cooling, an abort never held back |
| `tests/test_gpio_sim_kernel.py` | the real libgpiod path against a chip of the `gpio-sim` kernel module (levels, active-low wiring, edge events, a second request refused); second job of the workflow, skipped where the module is missing |
| `tests/test_mqtt_transport.py` | the topic dispatch, QoS, idempotency and limits without a broker |
| `tests/test_broker_integration.py` | the same dispatch against a real MQTT broker; skipped unless the broker checkout is present |
| `tests/test_global_stop_broker.py` | the global stop over a real broker; skipped unless the broker checkout is present |
| `tests/test_config_refusals.py` | every rule of the service configuration shown with the exact mistake that breaks it: unknown keys, wrong types, the polarity of the safety lines with no default, line clashes, the off-by-default auxiliary sources and the fields each source needs |

The broker scenarios start a real MQTT broker from a checkout of HYDRA-UMC-MQTT-BROKER (`HYDRA_UMC_TEST_BROKER_DIR`); the simulation job does not install it, so
those cases skip themselves there and run in the normal test run on a machine that has the broker.

## What it cannot show

A real laser, a real key switch, enclosure sensor or interlock loop, the electrical behaviour of the GPIO lines and any real optical safety function. The hardware row of the status table therefore stays at "simulated" until a person has run the bridge on a real setup.
