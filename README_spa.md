<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laser cell coordination bridge
Copyright (C) JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-BRIDGE-LASER banner" width="100%">
</p>

# 🔆 HYDRA-UMC-BRIDGE-LASER

<p align="center"><a href="README.md">🇺🇸 English</a> | 🇪🇸 <b>Español</b> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a> | <a href="README_por.md">🇵🇹 Português</a></p>

### 🛑 Puente de coordinación seguro por defecto para celdas láser

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python">
  <img src="https://img.shields.io/badge/Safety-Fails%20Closed-red.svg" alt="Safety">
  <img src="https://img.shields.io/badge/Tests-197%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.2.0-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-functional-0F6CBD.svg" alt="Maturity">
</p>

---

> **Comprobación de honestidad - qué funciona realmente hoy:** el snapshot de seguridad de cuatro señales y su puerta (`cell.py` con `LaserSafetySnapshot`/`LaserCellBridge`, que hace pasar cada trabajo por el propio `evaluate_job()` de `HYDRA-UMC-SDK`), el normalizador de evidencia de solo lectura (`observation.py`), el lector real de enclavamiento GPIO (`gpio_safety.py` con `GpioSafetyProbe`, libgpiod v2), y el transporte MQTT de estado/evidencia (`mqtt_transport.py`) son reales y están cubiertos por 197 casos `unittest` que pasan (`python tools/build_test.py`), incluyendo `tests/test_gpio_mqtt_emulator.py`, que ejecuta este bridge contra un emulador GPIO/MQTT fiel al protocolo pero escrito a mano. Nada de esto ha tocado un chip GPIO real, un broker MQTT real, ni un controlador láser real - `test_gpio_safety.py` lee contra un chip falso y `test_mqtt_transport.py` usa un cliente de broker falso. Todavía no existe una integración concreta con software/controlador láser, porque la máquina y su interfaz documentada no están disponibles - ver "Estado actual y próximos pasos" más abajo, que ya lo dice con claridad, y `CHANGELOG.md` para lo que se ha entregado exactamente hasta ahora. El transporte MQTT también se ha ejecutado contra un HYDRA-UMC-MQTT-BROKER real en una máquina de desarrollo (`tests/test_broker_integration.py`, que se omite si no hay ningún broker instalado): publicar y suscribirse con QoS 0, 1 y 2, la disponibilidad retenida y su último testamento, y la vuelta tras caerse y levantarse el broker.

> **Estado de seguridad física y de ciberseguridad:** este ecosistema no es un sistema de seguridad certificado. Todavía no existe una ruta de E-STOP por hardware, ni límites ni enclavamientos aplicados por el firmware, ni un comando de movimiento verificado; las imágenes de firmware se comprueban con CRC-32 y una firma Ed25519, y una compilación de versión rechaza las claves de desarrollo publicadas (los cabezales de herramienta y las placas de expansión detrás del relé siguen con cargadores de URTC, que usan un HMAC-SHA256 de clave compartida en lugar de una firma); TLS y TLS mutuo son opcionales y están desactivados por defecto; aún no se ha poblado ni probado ninguna placa propia. Lee la [línea base de seguridad](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/SECURITY_BASELINE.md) y el [modelo de amenazas](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/THREAT_MODEL.md) antes de fiarte de cualquier afirmación de aquí para la seguridad de una persona.

---

## 📋 De un vistazo

| | |
|---|---|
| Versión | `0.2.0` |
| Madurez | Funcional |
| Tests | 197 (`python tools/build_test.py`) |
| Tecnología | Python / Laser controller / G-code / Safety evidence / GPIO interlock reading |
| Destino | La Raspberry Pi CM5 de una celda HYDRA-UMC |
| En hardware real | Solo simulado: probado con emuladores, dobles de prueba o simuladores; no consta ninguna ejecución en hardware real para esta versión |

**Ir a:** [Resumen](#-resumen) · [Arquitectura](#-arquitectura) · [Funciones](#-funciones) · [Seguridad y protección](#-seguridad-y-protección) · [Interfaces](#-interfaces) · [Configuración](#-configuración) · [Inicio rápido](#-inicio-rápido) · [Pruebas](#-pruebas) · [Resolución de problemas](#-resolución-de-problemas) · [Estructura del repositorio](#-estructura-del-repositorio) · [Proyectos relacionados](#-proyectos-relacionados)

## 🚦 Estado del proyecto

Cada línea es una parte de este repositorio y la luz dice hasta dónde llega hoy. Se escribe con lo que el repositorio puede demostrar (pruebas, compilaciones, ejecuciones), no con lo previsto.

🟢 Hecho y verificado · 🟡 Funciona, con límites conocidos · 🟠 Hecho a medias o sin verificar · 🔴 Sin hacer o sin funcionar

| Área | Estado | Qué significa aquí |
|---|---|---|
| Software | 🟡 | Funciona para su propósito principal; la comprobación de honestidad de arriba lista lo que aún falta |
| Pruebas | 🟢 | 197 pruebas automáticas, ejecutadas en cada cambio |
| Hardware real | 🟠 | Solo simulado: probado con emuladores, dobles de prueba o simuladores; no consta ninguna ejecución en hardware real para esta versión |
| Documentación | 🟢 | README en ocho idiomas, comprobado contra el manifiesto en cada cambio |

## 🎯 Resumen

**HYDRA-UMC-BRIDGE-LASER** es el puente de alto nivel para celdas láser y auxiliares robóticos HYDRA-UMC. Puede coordinar tareas periféricas seguras como el traspaso de material, pero **nunca** puede armar, disparar o anular un controlador láser: esas condiciones son observaciones que lee, no autoridades que posee.

Pertenece a la familia **External Automation Bridges**: un conjunto de repositorios hermanos (CNC, LASER, OPENPNP, PRINTER3D, ROS2) que hablan el mismo contrato de seguridad compartido de `HYDRA-UMC-SDK`, de modo que ningún puente puede inventar su propia definición de "seguro para trabajar".

## 🧩 Papel en HYDRA-UMC

**HYDRA-UMC-BRIDGE-LASER** deja que una celda de robots trabaje alrededor de una cortadora o grabadora láser sin poder armarla ni dispararla jamás. Lee tres salvaguardas independientes (llave, cerramiento, enclavamiento) por GPIO y el estado de un controlador láser GRBL, y solo una celda en la que todas las salvaguardas indican seguro recibe trabajo.

Todos los bridges hablan el contrato de seguridad compartido de `HYDRA-UMC-SDK`: un trabajo solo se acepta cuando la puerta compartida `evaluate_job()` lo permite, y esa puerta falla cerrada. El proyecto padre es `HYDRA-UMC-SERVER`; este bridge no lo llama, responde por MQTT, a través de `HYDRA-UMC-MQTT-BROKER`, a quien manda en la celda.

## 🏛️ Arquitectura

<p align="center">
  <img src="images/architecture.svg" alt="HYDRA-UMC-BRIDGE-LASER architecture" width="100%">
</p>

<details>
<summary>Versión en texto del diagrama (Mermaid)</summary>

```mermaid
flowchart LR
    LASER["Controlador láser<br/>(estado, llave, carcasa, enclavamiento)"] --> BRIDGE["BRIDGE-LASER<br/>LaserSafetySnapshot.machine_state()"]
    BRIDGE -- "BridgeJob + MachineState observado" --> SDK["HYDRA-UMC-SDK<br/>evaluate_job()"]
    SDK -- GateDecision --> RESULT["MQTT: cmd/job/result"]
```

</details>

**Por qué está hecho así**

* **Por qué tres protecciones independientes en lugar de un solo booleano.** `LaserSafetySnapshot.machine_state()` comprueba `key_enabled`, `enclosure_closed` e `interlock_healthy` como tres condiciones separadas: la seguridad láser real necesita que cada resguardo físico sea independientemente verdadero; reducirlas a un solo indicador ocultaría cuál de ellas falló en realidad.
* **Por qué el puente documenta que nunca puede armar ni disparar un láser.** El propio docstring de `LaserCellBridge` afirma que "coordina solo auxiliares externos; no puede armar ni disparar un láser" — esas condiciones son observaciones de los propios enclavamientos certificados del controlador, nunca un sustituto de ellos.
* **Por qué el mapeo del estado del controlador es deliberadamente conservador.** Solo la cadena literal `IDLE` se mapea a `MachineState.IDLE`. Cualquier valor no reconocido cae en `OFFLINE`, nunca en algo que permitiría trabajo auxiliar.
* **Por qué el puente construye un nuevo `BridgeJob` y delega en el `evaluate_job()` compartido en lugar de escribir su propia lógica de aceptación/rechazo.** Los cinco External Automation Bridges (CNC, LASER, OPENPNP, PRINTER3D, ROS2) reutilizan exactamente el mismo `bridge_contract` de `HYDRA-UMC-SDK`, de modo que "qué cuenta como seguro para iniciar un trabajo" no puede divergir silenciosamente entre ellos.
* **Por qué la elección del software/controlador láser real se aplaza deliberadamente.** Comprometerse con la interfaz de un fabricante concreto antes de que la máquina y su reporte de enclavamiento documentado estén disponibles significaría afirmar una garantía de seguridad real que este núcleo local no puede verificar.
* **Cómo encaja en el resto del ecosistema.** BRIDGE-LASER se sitúa entre el controlador láser y `HYDRA-UMC-SDK` → `HYDRA-UMC-MQTT-BROKER` → seguridad independiente: coordina trabajo robótico auxiliar alrededor de la celda láser, no reemplaza ni anula la seguridad láser certificada.

El asistente de observación es un normalizador de evidencia, no un adaptador de controlador láser: no abre ningún enlace de red o serie, no altera ajustes, no sube trabajos, no arma ni dispara. [Laser Controller Evidence Boundary](docs/CONTROLLER_EVIDENCE_BOUNDARY.md) define la validación necesaria antes de una integración real.

**Funcionamiento como servicio.** `python -m hydra_umc_bridge_laser --config /etc/hydra-umc/bridge-laser.toml` arranca el bridge desde un único fichero TOML: el chip GPIO y las tres líneas de salvaguarda (línea, `active_low`, sesgo, antirrebote), el puerto serie del controlador GRBL, el broker MQTT, el origen del estado de la celda y las salvaguardas auxiliares opcionales. Una clave que no conoce se rechaza, la polaridad de una línea no tiene valor por defecto y todo falla cerrado: sin controlador lee OFFLINE y un fichero de estado de la celda ausente, desconocido o caducado es `SAFE_STOP`. `--check` valida el fichero; `deploy/` contiene la unidad systemd (`Restart=on-failure`) y un fichero de ejemplo. Se ha ejecutado contra GPIO y un controlador simulados, no en una celda real.

## ✨ Funciones

* ✅ **Instantánea de seguridad de cuatro señales (lógica de software, probada sin láser):** `cell.py` — `LaserSafetySnapshot.machine_state()` exige que la llave esté habilitada, la carcasa cerrada **y** el enclavamiento en buen estado simultáneamente; si falta cualquiera de ellas, resuelve en `SAFE_STOP` incluso antes de leer `controller_state`. *(implementado, probado en `tests/test_cell.py`)*
* ✅ **Puerta de seguridad compartida, real:** cada trabajo observado se reevalúa mediante `evaluate_job()` de `bridge_contract` en `HYDRA-UMC-SDK`, la misma puerta que usan todos los puentes hermanos. *(implementado)*
* ✅ **Mapeo de estado conservador:** solo `IDLE` se trata como reposo; `RUN`/`RUNNING`/`PAUSED` se mapean a `RUNNING`, `FAULT`/`ALARM`/`ERROR` a `FAULT`, y cualquier valor no reconocido cae en `OFFLINE`. *(implementado)*
* ✅ **Evidencia de seguridad de solo lectura:** `observation.py` solo acepta señales booleanas genuinas de llave, carcasa e enclavamiento; los valores faltantes, numéricos o de tipo texto fallan de forma segura. No puede armar ni disparar un láser. *(implementado, probado en `tests/test_observation.py`)*
* ✅ **Lectura de enclavamiento GPIO independiente del controlador (probada solo contra un chip simulado):** `GpioSafetyProbe` de `gpio_safety.py` lee las mismas 3 protecciones independientes desde líneas GPIO (libgpiod v2; las pruebas usan un chip simulado) en vez de un mapeo guardado — deliberadamente agnóstico del controlador, ya que una llave/sensor de puerta/relé de enclavamiento es universal en cortadoras láser sin importar la marca. Un fallo de lectura GPIO hace fallar de forma segura las 3 protecciones. *(implementado, probado en `tests/test_gpio_safety.py`)*
* ✅ **Vigilancia de enclavamientos por flancos (probada solo contra un chip simulado):** `open_gpio_safety()` abre las líneas de llave, carcasa y enclavamiento UNA sola vez (`INPUT`, `Edge.BOTH`) y atiende con esa única petición tanto a los lectores de nivel como al vigilante de flancos — el kernel rechaza una segunda petición de las mismas líneas. `watch_for_interlock_edges()` se bloquea en las notificaciones de eventos de flanco del propio kernel (libgpiod v2) en lugar de releer niveles solo cuando un mensaje MQTT ajeno lo pide, y `run_forever(edge_watcher=...)` lanza un hilo demonio que publica un `state` retenido actualizado en el instante en que una línea cambia; si el vigilante falla, publica un `state` que falla cerrado (`SAFE_STOP`, con el motivo) y sigue intentándolo. El cableado de cada línea se declara (`GpioLineSettings`: `active_low`, `bias` — el valor por defecto hace que un cable cortado se lea como inseguro — y `debounce_ms`); véase `docs/WIRING_GUIDE.md`. Aún no validado en un chip GPIO real. *(implementado, probado en `tests/test_gpio_safety.py` y, con un `gpiod` simulado, en `tests/test_hardening.py`)*
* ✅ **Flujo de eventos de seguridad (probado con líneas simuladas y un vigilante de flancos simulado):** `events.py` convierte cada cambio de llave, cerramiento e interlock en un registro con marca de tiempo en `hydra/bridges/laser/event/safety` (el registro que un data lake guarda para auditoría y OEE) y, una sola vez, cuando la celda pasa de segura a insegura, un evento `hydra/bridges/laser/event/interlock_open` con las protecciones que se abrieron, para que el orquestador pare los brazos de la celda al instante. Ambos son QoS 1 y nunca retenidos; llevan `at_ms` y un `sequence` creciente; la primera lectura es solo una referencia; un vigilante de flancos que falla comunica la pérdida también como interlock abierto. El bridge solo informa: no puede parar un láser. *(implementado, probado en `tests/test_events.py`)*
* ✅ **Protecciones auxiliares opcionales (probadas con entradas simuladas):** `auxiliary.py` permite a la celda declarar condiciones extra - extracción de humos en marcha, aire de asistencia activo, temperatura del tubo CO2 como máximo un límite - como `AuxiliaryCheck` pasados a `LaserMqttBridge(auxiliary=...)`. Un trabajo que no sea ABORT se rechaza, nombrando la comprobación que falla, mientras alguna no se cumpla; una lectura ilegible, no numérica o no finita cuenta como no cumplida; `state` lleva un mapa `auxiliary`. Sin ninguna declarada no cambia nada. Solo lectura: no conmuta nada. *(implementado, probado en `tests/test_auxiliary.py`)*
* ✅ **Compilación/prueba no mutante:** `build-test.bat`/`.sh` compilan el código y ejecutan la batería de pruebas de la puerta de seguridad sin tocar archivos de versión ni el CHANGELOG. *(implementado, ver Compilación y publicación más abajo)*
* ✅ **Lector de estado de láser GRBL (probado solo contra una placa simulada):** el `GrblLaserState` de `grbl_state.py` es el `controller_state` real para un controlador láser de la familia GRBL en un puerto serie (las placas que manejan LaserGRBL y LightBurn): envía la consulta de estado de GRBL `?` y devuelve la palabra de estado del informe. Es de solo lectura a propósito - el único byte que escribe es `?`, no hay retención, reinicio, reanudación ni G-code - y falla cerrado (sin respuesta es un estado vacío, nunca reposo). El puerto, la conexión que se reabre y el analizador son el enlace serie compartido del SDK que usa también el bridge CNC. La potencia del láser y el avance del informe van en `state` como información (`laser_power`, `feed_rate`), nunca como salvaguarda. Una placa GRBL tiene un solo puerto serie: mientras LightBurn o LaserGRBL lo tienen, este lector no puede usarlo. *(implementado, no probado en una placa real)*
* 🔜 **Integración concreta con controlador/software láser** — deliberadamente aplazada hasta que la máquina y su interfaz documentada estén disponibles. *(planeado)*
* ✅ **Claves de idempotencia repetidas:** `LaserMqttBridge` acepta un `IdempotencyStore`: una clave de trabajo repetida recibe la respuesta dada la primera vez en lugar de evaluarse de nuevo. *(implementado, probado en `tests/test_idempotency.py`)*
* ✅ **Bucle MQTT blindado y lecturas que fallan cerradas:** una carga demasiado grande (más de 16 KiB) o ilegible, un JSON profundamente anidado y cualquier fallo inesperado reciben una negativa en el topic de resultado y nunca terminan el bucle; las respuestas de `cmd/job` indican `"mode": "gate-only"` y un ABORT por ahí dice que no se detuvo nada (el E-STOP físico detiene el láser); el estado lleva `observed_at` y el bridge se anuncia en un topic `availability` con Last Will; cualquier excepción al leer las líneas GPIO — no solo `OSError` — hace fallar las tres protecciones, y los tres niveles se leen en una sola operación bajo un cerrojo; se entienden estados de controlador de estilo GRBL como `Hold:0`, `Alarm:1`, `Door:1`, `Jog` y `Home`. *(implementado, probado en `tests/test_hardening.py`)*
* ✅ **Trabajos por la admisión compartida:** la comprobación de un trabajo mal formado y de una `idempotency_key` repetida es el `JobIntake` del SDK en lugar de código de este puente (las claves ya no llevan el prefijo `job:`).
* ✅ **Respuestas publicadas con QoS 1:** las respuestas a las órdenes se publican con QoS 1 (el despachador compartido respeta el QoS que un puente da a una respuesta), de modo que un resultado no se pierde en un enlace inestable.
* ✅ **Sigue la parada global (apagado por defecto):** con `HYDRA_UMC_LASER_GLOBAL_STOP=1` el bridge lee el anuncio retenido del servidor en `hydra/swarm/safety/estop`; mientras diga `SAFE_STOP`, o no se pueda leer, rechaza con un motivo: un trabajo (un aborto pasa). Las paradas y las peticiones de solo lectura siguen funcionando y solo `READY` termina el rechazo. *(implementado, probado contra un broker real; nunca ejecutado con un servidor real)*

## 🔒 Seguridad y protección

| Amenaza | Defensa | Dónde |
|---|---|---|
| Un trabajo para una celda o máquina que no está en estado seguro | Todo trabajo pasa por la puerta compartida `evaluate_job()` del SDK, que falla cerrada; el bridge no tiene lógica propia de aceptar o rechazar | SDK `bridge_contract` |
| Datos de trabajo desmesurados | Como máximo 32 parámetros, claves de hasta 64 caracteres, valores de hasta 1024, identificadores de hasta 128 (`MAX_PARAMETERS`, `MAX_PARAMETER_KEY_CHARS`, `MAX_PARAMETER_VALUE_CHARS`, `MAX_IDENTIFIER_CHARS`) | SDK `bridge_contract` |
| Una orden repetida o reenviada | Un `IdempotencyStore` recuerda cada clave 24 horas y como máximo 10 000 entradas; una repetición recibe la primera respuesta en vez de evaluarse otra vez | SDK `job_intake` |
| Una carga MQTT enorme u hostil | Una carga de más de 16 KiB, un JSON ilegible o muy anidado y cualquier fallo inesperado se responden con un rechazo en el topic de resultado y nunca terminan el bucle | `mqtt_transport.py` |
| Un láser armado por error | Las tres salvaguardas independientes (`key_enabled`, `enclosure_closed`, `interlock_healthy`) deben indicar seguro; solo el estado exacto `IDLE` del controlador cuenta como reposo, cualquier otro es `OFFLINE` | `cell.py`, `events.py` |
| Un cable de enclavamiento cortado | El sesgo por defecto hace que un cable cortado se lea como inseguro (pull-up para señal activa en bajo, pull-down para activa en alto), el rebote se ignora 10 ms por defecto y las tres líneas son distintas | `gpio_safety.py` |
| Una lectura de GPIO que falla | El `state` retenido pasa a fallar cerrado con el motivo (todas las salvaguardas sin cumplir, `SAFE_STOP`) para que nadie siga leyendo un buen estado viejo | `mqtt_transport.py` |
| Una orden retenida que se reejecuta al reconectar | Un mensaje `cmd/` retenido se ignora al reconectar | `mqtt_transport.py` |

**Lo que nunca hace:** solo coordina auxiliares externos: no puede armar ni disparar un láser y al controlador GRBL no le envía más que la consulta de estado.

## 🔌 Interfaces

Topics bajo `hydra/bridges/laser/`; no hay verbo de parada (`STOP_VERBS` está vacío).

| Topic o ruta | Qué lleva |
|---|---|
| `cmd/status` | carga vacía: relee las tres líneas GPIO y publica el estado |
| `cmd/job` → `cmd/job/result` | un `BridgeJob` en JSON; solo planifica: la respuesta es una `GateDecision` |
| `state`, `availability` | la instantánea retenida con su marca de tiempo, y `online`/`offline` |
| `event/safety`, `event/interlock_open` | eventos QoS 1, no retenidos, cuando cambia una salvaguarda |

La biblioteca: `LaserCellBridge`, `LaserSafetySnapshot`, `LaserMqttBridge`, `GpioSafetyProbe`, `open_gpio_safety()`, `GrblLaserState`, `open_grbl_laser_state()` y `AuxiliarySupervisor` (extracción de humos, aire de asistencia, temperatura del tubo de CO2).

## ⚙️ Configuración

| Variable | Por defecto | Qué fija |
|---|---|---|
| `GpioLineSettings.active_low` | obligatorio | `True` cuando la señal es segura en nivel 0 (un contacto normalmente cerrado a masa) |
| `GpioLineSettings.bias` | a prueba de fallos | `pull-up`, `pull-down`, `disabled` o `as-is`; sin definir elige el que hace que un cable cortado se lea inseguro |
| `GpioLineSettings.debounce_ms` | `10.0` | rebote ignorado durante este tiempo; `0` lo desactiva, un valor negativo se rechaza |
| `HYDRA_UMC_LASER_GLOBAL_STOP` | desactivado | `1` sigue la parada global del servidor: mientras el último anuncio del tema retenido `hydra/swarm/safety/estop` diga `SAFE_STOP` (o no se pueda leer), el bridge rechaza con un motivo: un trabajo (un aborto pasa); solo `READY` lo termina. `HYDRA_UMC_LASER_GLOBAL_STOP_TOPIC` cambia el tema y `HYDRA_UMC_LASER_GLOBAL_STOP_STRICT=1` rechaza también hasta que llegue el primer anuncio |
| `HYDRA_MQTT_USERNAME` | ninguno | El usuario MQTT; el broker lo liga a un prefijo de ID de cliente |
| `HYDRA_MQTT_PASSWORD` | ninguno | La contraseña; solo vale junto con el usuario |
| `HYDRA_MQTT_PASSWORD_FILE` | ninguno | La contraseña leída de un fichero (secreto de Docker o systemd); se ignora si hay `HYDRA_MQTT_PASSWORD` |
| `HYDRA_MQTT_TLS_CA` | ninguno | El fichero de la CA que firmó el certificado del broker: la conexión es TLS y se verifica el certificado |
| `HYDRA_MQTT_TLS` | desactivado | `1` activa TLS, verificado con las CA de confianza del sistema |
| `HYDRA_MQTT_TLS_CERT` / `HYDRA_MQTT_TLS_KEY` | ninguno | El certificado de cliente y su clave para un broker que exige TLS mutuo; hacen falta los dos |

Los desplazamientos de las tres líneas GPIO y el chip son argumentos de `open_gpio_safety()`; el dispositivo serie del controlador GRBL es el argumento de `open_grbl_laser_state()` (115200 baudios, 1 segundo de espera por defecto).

## 🚀 Inicio rápido

Requiere Python 3.11 o superior. Las pruebas y los scripts de compilación esperan `HYDRA-UMC-SDK` clonado junto a este repositorio (`../HYDRA-UMC-SDK`) o indicado con `HYDRA_UMC_SDK_ROOT`.

Pruébalo sin hardware (esto comprueba todo el bridge contra sus emuladores y dobles de prueba):

```bash
py -3 tools/build_test.py          # Windows
python3 tools/build_test.py         # Linux, macOS
```

Arranca el servicio (no hay un script de consola: el servicio es el `run_forever()` del transporte MQTT, que llamas desde tu propio código de arranque):

```python
from hydra_umc_bridge_laser.gpio_safety import GpioLineSettings, open_gpio_safety
from hydra_umc_bridge_laser.grbl_state import open_grbl_laser_state
from hydra_umc_bridge_laser.mqtt_transport import LaserMqttBridge, run_forever
wiring = GpioLineSettings(active_low=True)                       # normally-closed contacts to ground
safety = open_gpio_safety("/dev/gpiochip0", 17, 27, 22, key=wiring, enclosure=wiring, interlock=wiring)
bridge = LaserMqttBridge(safety.lines, controller_state=open_grbl_laser_state("/dev/ttyUSB0"), cell_state=lambda: cell_state)
run_forever(bridge, host="192.168.0.180", edge_watcher=safety.watcher)   # serves cmd/# and publishes the events
```

El usuario, la contraseña y los ficheros TLS salen de las variables `HYDRA_MQTT_*` (ver Configuración); el código de arriba no necesita credenciales propias.

## 🧪 Pruebas

197 casos automáticos de `unittest` se ejecutan con `python tools/build_test.py` (que también compila cada módulo). Las pruebas no necesitan hardware, red ni paquetes opcionales: las que necesitarían `paho-mqtt`, `pyserial` o una biblioteca del fabricante usan un sustituto o se saltan si falta el paquete.

| Fichero de pruebas | Pruebas | Qué cubre |
|---|---|---|
| `test_global_stop.py`, `test_global_stop_broker.py` | - | la guardia de la parada global y sus rechazos con el motivo, y lo mismo contra un broker real en un puerto local libre (el anuncio en QoS 0, 1 y 2, una parada retenida obedecida al conectar, una ilegible que falla cerrada) |
| `test_broker_integration.py`, `broker_harness.py` | - | el cliente MQTT contra un HYDRA-UMC-MQTT-BROKER real en un puerto local libre: una orden a través del cliente, el estado retenido y la última voluntad, y la vuelta tras caer y volver el broker; se omite si faltan Node.js, `paho-mqtt` o el broker instalado (`HYDRA_UMC_TEST_BROKER_DIR`, por defecto la carpeta contigua) |
| `test_cell.py`, `test_observation.py`, `test_events.py`, `test_auxiliary.py` | - | salvaguardas, evidencia, eventos y comprobaciones auxiliares |
| `test_gpio_safety.py`, `test_gpio_mqtt_emulator.py`, `gpio_mqtt_emulator.py` | - | el lector GPIO contra líneas simuladas; el bridge real contra montajes de GPIO y MQTT |
| `test_grbl_state.py` | - | el lector GRBL contra un controlador en memoria que habla como GRBL (banner, `ok`, respuestas viejas) |
| `test_mqtt_transport.py`, `test_mqtt_environment.py`, `test_hardening.py`, `test_edge_cases.py`, `test_idempotency.py` | - | despacho de topics, las credenciales del entorno, clientes hostiles, lecturas raras y claves repetidas |

El CI ejecuta `HYDRA_UMC_CI=1 python tools/ci_validate.py`, que comprueba el manifiesto, los documentos, los ocho README y las imágenes, y ejecuta las pruebas con una copia del SDK.

## 🏗️ Compilación y publicación

Requiere Python 3.11+. `tools/build_test.py` espera que `HYDRA-UMC-SDK` esté clonado como directorio hermano (`../HYDRA-UMC-SDK`) o indicado mediante la variable de entorno `HYDRA_UMC_SDK_ROOT`.

```bash
# Windows
build-test.bat      # solo valida — sin cambio de versión/CHANGELOG
build.bat            # Valida y compila (compilar nunca cambia la versión)

# Linux/macOS
bash build-test.sh
bash build.sh
```

`build-test` compila cada módulo bajo `src/` y `tools/` con `py_compile` y ejecuta la batería completa de `unittest` descubierta en `tests/` (`test_cell.py`, `test_observation.py`, `test_gpio_safety.py`, `test_mqtt_transport.py`, `test_gpio_mqtt_emulator.py`, `test_hardening.py`, `test_idempotency.py`, `test_mqtt_environment.py` - 197 tests), demostrando la admisión en reposo seguro, el rechazo por carcasa y el reenvío de aborto entre todo lo demás cubierto — nunca modifica el repositorio. `build` ejecuta primero esa misma validación y, solo si tiene éxito, llama a `tools/bump_version.py` para sincronizar la versión en `pyproject.toml`, `hydra-umc.project.json` y `CHANGELOG.md`. Todavía no existe un comando `run` real de láser — eso requiere una integración de controlador validada y segura.

## 🩺 Resolución de problemas

| Ves | Porque | Haz |
|---|---|---|
| `ModuleNotFoundError: hydra_umc_sdk` | El SDK no está instalado ni junto a este repositorio | Clona `HYDRA-UMC-SDK` junto a este repositorio o define `HYDRA_UMC_SDK_ROOT` |
| `paho-mqtt is not installed` | El cliente MQTT es un extra opcional | `pip install ".[mqtt]"` (necesita `paho-mqtt` 2.1 o superior, menor que 3) |
| `password was given without a username` | Las credenciales MQTT necesitan las dos partes | Define `HYDRA_MQTT_USERNAME` además de la contraseña |
| `could not reach the MQTT broker after N attempts` | El broker está caído, la dirección es errónea o el puerto está cerrado | Arranca `HYDRA-UMC-MQTT-BROKER` y revisa el host y el puerto dados al transporte (lo intenta 5 veces, con 2 segundos de pausa); un fallo del handshake TLS no se reintenta |
| `the MQTT broker refused the connection` | El broker rechazó la credencial (o no respondió dentro del plazo) | Revisa `HYDRA_MQTT_USERNAME` y la contraseña; el ID de cliente debe empezar por el prefijo que el broker ligó a la credencial |
| `state` with every safeguard unsatisfied and `SAFE_STOP` | Falló una lectura GPIO (chip ausente, permisos, petición liberada) o se detuvo el vigilante de flancos | Lee el motivo en el `state` retenido; revisa la ruta del chip, los desplazamientos de línea y los permisos del usuario del servicio |
| `"allowed": false` + `reason` | La puerta compartida o una guarda rechazó la orden | Lee `reason` y arregla la causa; no reintentes a ciegas |

## 📂 Estructura del repositorio

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of HYDRA-UMC-BRIDGE-LASER" width="100%">
</p>

<details>
<summary>Versión en texto del árbol</summary>

```text
HYDRA-UMC-BRIDGE-LASER/
├── src/hydra_umc_bridge_laser/
│   ├── cell.py                    rechaza el trabajo salvo que las salvaguardas indiquen reposo seguro
│   ├── gpio_safety.py             lee las tres líneas de salvaguarda por GPIO (libgpiod)
│   ├── grbl_state.py              estado del controlador GRBL; solo la consulta de estado
│   ├── observation.py             evidencia local de seguridad, nunca una orden al láser
│   ├── events.py                  eventos con marca de tiempo cuando cambia una salvaguarda
│   ├── auxiliary.py               comprobaciones de extracción de humos, aire de asistencia y temperatura del tubo
│   └── mqtt_transport.py          transporte MQTT de órdenes, estado y eventos
├── tests/                         149 pruebas, con un emulador de GPIO y MQTT
├── deploy/                        unidad systemd y configuración de ejemplo
├── docs/                          guía del bridge, límite de la evidencia, guía de cableado
├── tools/                         ejecutor de compilación y pruebas, subida de versión, validador de CI, generadores y comprobaciones de README e imágenes
├── images/                        banner y las imágenes del README
├── .github/                       flujo de CI y plantillas de incidencias
├── pyproject.toml                 metadatos del paquete y dependencias
├── hydra-umc.project.json         manifiesto: versión, madurez, familia
├── CHANGELOG.md                   qué cambió en cada versión
├── build.sh build.bat             scripts de compilación (nunca cambian la versión)
├── build-test.sh build-test.bat   scripts de compilación (nunca cambian la versión)
├── test.sh test.bat               ejecutan las pruebas
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE LICENSE.md
```

</details>

## 🗺️ Hoja de ruta y límites conocidos

**Límites conocidos hoy**

**Real hoy:** versión `0.2.0`, un núcleo de planificación seguro por defecto probado en local (`LaserSafetySnapshot` + `LaserCellBridge`) apoyado en la puerta de trabajo compartida de `HYDRA-UMC-SDK`, normalización estricta de evidencia de seguridad en solo lectura que distingue un trabajo realmente en pausa (`HOLDING`) de uno realmente disparando (`RUNNING`), una lectura real de enclavamiento GPIO independiente del controlador (`GpioSafetyProbe`) para las 3 protecciones independientes de llave/carcasa/enclavamiento, un transporte MQTT real de estado/evidencia (`mqtt_transport.py`), una batería `unittest` determinista de 197 pruebas, y scripts de build-test no mutantes conectados a CI con clonado del SDK.

**Frontera de integración:** la carcasa, la llave y el enclavamiento certificados del propio controlador láser nunca se eluden; este puente solo controla trabajo robótico *auxiliar* a su alrededor, y únicamente leyendo su estado reportado.

**Todavía pendiente:** el puente no se ha conectado ni usado para operar un sistema láser real — elegir y validar una interfaz concreta de controlador/software se aplaza hasta disponer de la máquina y su interfaz documentada.

## 🌍 Idiomas

Este README y los documentos del repositorio existen en ocho idiomas: inglés, español, alemán, francés, italiano, japonés, chino y portugués (Portugal). Se escriben a la vez y el CI comprueba que los ocho ficheros tengan las mismas secciones y los mismos enlaces. Este repositorio no tiene pantalla ni catálogo de mensajes propios, así que no hay cadenas de interfaz que traducir.

## 🔗 Proyectos relacionados

Este proyecto es parte del ecosistema de robótica HYDRA-UMC del mismo autor (JuanenRac / Electro Hobby 3D). Vale la pena conocerlo, ya que una petición podría en realidad ser sobre alguno de estos en vez de sobre este repositorio.

**Proyecto Padre**
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — el backend headless real (REST/WebSocket) con el que habla de verdad cada cliente de control; este bridge no lo llama: responde por MQTT, a través de HYDRA-UMC-MQTT-BROKER, a quien manda en la celda.

**Proyectos Hermanos** — también hablan con la propia API de HYDRA-UMC-SERVER, cada uno como su propio cliente
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — panel de control web con visualización 3D multi-robot en tiempo real.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — centro de mando de enjambre de escritorio (PySide6) para varios servidores a la vez, empaquetado como ejecutable independiente.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — app nativa de control para Android con inicio de sesión biométrico y un compañero Wear OS emparejado.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — app de control para iOS/iPadOS (Flutter) con sincronización en tiempo real por WebSocket.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — interfaz táctil nativa para la pantalla táctil DSI de 7" a bordo, embebida en el propio CM5.
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — barrera de coordinación para flotas AGV/AMR mediante un publicador MQTT VDA 5050 (probado solo contra una flota emulada).
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — coordinador de alto nivel para celdas CNC con acceso a estado/bytes de control GRBL (probado solo contra un emulador).
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — barrera de coordinación para droides con patas/humanoides, con un emisor de comandos para Boston Dynamics Spot (probado solo contra un emulador).
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — coordinador de alto nivel seguro para el flujo de placas de pick-and-place OpenPnP.
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — barrera de coordinación segura para impresoras 3D Moonraker/Klipper, con comandos de trabajo reales y controlados.
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — coordinador con un transporte ROS 2 rclpy importado de forma perezosa (todavía no ejecutado contra una instalación de ROS 2).
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — barrera de coordinación para UAV equipados con cámara, con un emisor de comandos MAVLink (probado solo contra un emulador).

**Directamente Relacionados**
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — el contrato JSON-Schema compartido y la barrera de software de puerta de trabajos contra la que cada bridge valida sus comandos (no es una función de seguridad certificada).
- **[HYDRA-UMC-CONNECTOR-HUB](https://github.com/JuanenRac/HYDRA-UMC-CONNECTOR-HUB)** — registro declarativo y validador de manifiestos de adaptador para conectores de máquinas externas; extiende la propia idea de contrato del SDK a máquinas externas sin sustituir a los proyectos de pasarela industrial.
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — el transporte real de `mqtt_transport.py` para los propios tópicos `hydra/bridges/laser/...` de este bridge — solo estado de las salvaguardas, ya que aquí no existe ningún comando real de accionamiento (este bridge no puede armar ni disparar un láser en ningún caso); ver el propio `docs/BRIDGE_TOPICS.md` de ese repositorio.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — futura evidencia de seguridad de zona de celda para este bridge.

**También Forma Parte del Ecosistema**

*Hardware y Plataforma Base*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — el diseño de la placa madre del brazo robótico: host CM5 + coprocesador STM32H745 de doble núcleo, pensado para coordinar hasta 8 brazos herramienta por CAN-OTA/SPI-OTA (firmware en fase temprana; todavía no hay ninguna placa poblada).
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — capa de producto reproducible sobre Raspberry Pi OS para el CM5: agente de solo lectura, config/perfiles validados, aprovisionamiento WiFi de primer contacto.

*Backend Central y Clientes*
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — creador/editor gráfico de URDF de escritorio que envía los modelos terminados al propio catálogo de STUDIO.
- **[HYDRA-UMC-EDITOR-STL](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-STL)** — editor de escritorio de modelos STL, que transforma/reemplaza/quita/añade piezas reales en el mismo catálogo de modelos que también edita HYDRA-UMC-EDITOR-URDF.

*Plataforma de Herramientas URTC*
- **[URTC](https://github.com/JuanenRac/URTC)** — firmware para la placa física del Universal Robot Tool Controller, más de 25 perfiles de herramienta por bus CAN.
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — herramienta de escritorio con GUI para flashear placas URTC, CAN-OTA más SWD/JTAG de chip completo.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — herramienta de escritorio de diagnóstico CAN-bus en vivo para placas URTC, un panel por perfil de herramienta.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — alternativa basada en navegador a URTC-TESTER mediante la Web Serial API, sin instalación local.
- **[URTC-GATEWAY](https://github.com/JuanenRac/URTC-GATEWAY)** — pasarela delante del bus CAN de URTC: lista de identificadores permitidos, límite de tasa y clave de sesión; software probado en ordenador, aún no en un bus real.

*Nodo IA de Visión (Hailo-8)*
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — nodo de integración para el pipeline de visión Hailo-8, con una comprobación real de disponibilidad de hardware por etapa.
- **[HYDRA-UMC-DETECTION-HEF](https://github.com/JuanenRac/HYDRA-UMC-DETECTION-HEF)** — registro real de modelos compilados con verificación de carga segura por arquitectura Hailo/checksum.
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — generador real de pipeline GStreamer + config MediaMTX, con una frontera de integración HailoRT real.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — ley de corrección Position-Based Visual Servoing con autorización condicionada al estado de zona; todavía sin estimación de pose por cámara.

*Nodo IA Cognitivo (Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — nodo de integración para el pipeline cognitivo Hailo-10 (orquestación de LLM/VLA/voz).
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — codificación/decodificación real de tokens de acción y generación de trayectoria para un modelo Vision-Language-Action.
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — front-end de voz real (VAD + analizador de intención) con un relé a Watch acotado y con confirmación.
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — descomposición real de tareas basada en reglas y recuperación semántica de errores sobre códigos de error del MCU.
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — búsqueda real de documentos TF-IDF (solo librería estándar) sobre los propios documentos Markdown de este ecosistema.
- **[HYDRA-UMC-LOCAL-TECHNICIAN](https://github.com/JuanenRac/HYDRA-UMC-LOCAL-TECHNICIAN)** — técnico de mantenimiento con IA local y con puertas de política para el propio ecosistema - observa, diagnostica y propone arreglos; los dos niveles de riesgo más altos están deliberadamente sin implementar todavía.

*Orquestación y Enjambre*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — nodo de integración con un contrato real de informe de salud gRPC/Protobuf y una máquina de estados de misión.
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — cola de trabajos real basada en prioridad con deduplicación, sobre una API HTTP real.
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — watchdog de salud de flota real basado en gRPC, con reintento/backoff y detección de discrepancia de identidad.
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — planificador de rutas 3D real basado en RRT, con validación real de colisión de obstáculos/espacio de trabajo.
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — sincronización de estado real mediante CRDT LWW-Element-Map, con pruebas de propiedades para convergencia multi-celda.

*Gemelo Digital y Simulación*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — nodo de integración para el motor de gemelo digital, con un contrato real de sincronización por compatibilidad de versión.
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — enrutador hardware-in-the-loop con un enclavamiento de software por colisión entre simulación y hardware real (probado sin hardware real).
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — cinemática directa real y validación de límites articulares sobre un subconjunto real de URDF.
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — generador real de escenas 2D procedurales con exportación de anotaciones YOLO/COCO.

*Datos y Analítica*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — almacén de series temporales real respaldado por sqlite3, con una API HTTP real de ingesta/consulta.
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — detector de anomalías real basado en FFT + línea base estadística, con monitorización de deriva.
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — cálculo real de OEE/disponibilidad sobre el histórico de DATALAKE, con exportación CSV reproducible.
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — pipeline real de ingesta CAN/WebSocket hacia DATALAKE, con deduplicación por secuencia.

*Pasarela Industrial*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — nodo de integración que retransmite a protocolos industriales, con una capa real de lista blanca de comandos/contrapresión.
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — espacio de direcciones OPC-UA real, verificado con una sesión de cliente real del protocolo binario.
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — endpoints XML reales `/probe` y `/current` de MTConnect, con salida en modo degradado.

*Herramientas Complementarias y Operaciones del Ecosistema*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — paneles de Resúmenes Inteligentes y Resaltado de Anomalías sobre DATALAKE/ANOMALY-DETECTOR, con un respaldo estadístico honesto.
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — CLI de flota con un contrato real y estable de códigos de salida, cliente real y en vivo de la propia API de HYDRA-UMC-SERVER.
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — app compañera de WearOS con patrones de alerta háptica y un relé de voz al teléfono emparejado (todavía no ejecutada en un reloj físico).
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — firmware para un rack de montaje de placas con decodificación real de ID de herramienta y lógica de precalentamiento Smart Idle.
- **[URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)** — firmware más un compañero de visión real en Python para un cabezal de inspección térmica/RGB.
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — herramienta administrativa de escritorio que descubre, clona y actualiza cada repositorio de este ecosistema.
- **[HYDRA-UMC-OS-REBUILDER](https://github.com/JuanenRac/HYDRA-UMC-OS-REBUILDER)** — herramienta de escritorio Windows/Linux que construye una imagen de la CM5 lista para grabar, precargada con las versiones más actuales del ecosistema, con configuración de primer arranque de Wi-Fi/usuario/SSH al estilo de Raspberry Pi Imager.
- **[HYDRA-UMC-OPS-AGENT](https://github.com/JuanenRac/HYDRA-UMC-OPS-AGENT)** — coordinador de incidencias de mantenimiento: un rol edge de bajo privilegio recopila un snapshot de inventario/salud saneado, un rol control-plane lo renderiza de solo lectura y pide a un proveedor de IA que sugiera un diagnóstico - nunca aplica un parche ni despliega nada.
- **[HYDRA-UMC-DEV-SERVER](https://github.com/JuanenRac/HYDRA-UMC-DEV-SERVER)** — host de desarrollo reproducible (Raspberry Pi 5 / CM5) que almacena el código del ecosistema y ejecuta tareas acotadas de compilación/pruebas bajo una cola duradera; un rol de desarrollo dedicado, explícitamente distinto de un CM5 operativo.

## 📚 Documentación

Dónde leer más:

* [docs/BRIDGE_GUIDE.md](docs/BRIDGE_GUIDE.md) - alcance, ajustes de cableado GPIO, el lector GRBL, scripts
* [docs/WIRING_GUIDE.md](docs/WIRING_GUIDE.md) - cómo se cablean las tres señales de salvaguarda
* [docs/CONTROLLER_EVIDENCE_BOUNDARY.md](docs/CONTROLLER_EVIDENCE_BOUNDARY.md) - qué cuenta como evidencia real de seguridad
* [Base de seguridad del ecosistema](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/SECURITY_BASELINE.md)
* [Modelo de amenazas del ecosistema](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/THREAT_MODEL.md)
* [Historial de cambios de este repositorio](CHANGELOG.md)
* [Licencia de este repositorio](LICENSE.md)

## 🤝 Contribuir y comunidad

* Antes de un pull request ejecuta `HYDRA_UMC_CI=1 py -3 tools/ci_validate.py` (o `HYDRA_UMC_CI=1 python3 tools/ci_validate.py`): debe imprimir `CI_VALIDATION=PASS`. No ejecutes `build.sh` ni `build.bat` para esta comprobación; compilar no es comprobar.
* Los ocho README se escriben desde una sola fuente en HYDRA-UMC-DOCS; no los edites a mano. Cambia la fuente y vuelve a escribirlos con `tools/make_readmes.py`.
* No afirmes en un README lo que no se ha ejecutado: di «simulado» o «sin probar en hardware» cuando esa sea la verdad.
* Mira [CONTRIBUTING.md](CONTRIBUTING.md), el [código de conducta](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md) y [SUPPORT.md](SUPPORT.md).

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - [LICENSE](LICENSE).
