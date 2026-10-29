<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laser cell coordination bridge
Copyright (C) JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-BRIDGE-LASER banner" width="100%">
</p>

# 🔆 HYDRA-UMC-BRIDGE-LASER

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | 🇩🇪 <b>Deutsch</b> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a> | <a href="README_por.md">🇵🇹 Português</a></p>

### 🛑 Ausfallsichere Koordinationsbrücke für Laserzellen

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python">
  <img src="https://img.shields.io/badge/Safety-Fails%20Closed-red.svg" alt="Safety">
  <img src="https://img.shields.io/badge/Tests-149%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.1.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-functional-0F6CBD.svg" alt="Maturity">
</p>

---

> **Ehrlichkeitscheck - was heute wirklich läuft:** der Vier-Signal-Sicherheits-Snapshot und sein Gate (`cell.py` mit `LaserSafetySnapshot`/`LaserCellBridge`, das jeden Job durch das echte `evaluate_job()` von `HYDRA-UMC-SDK` leitet), der schreibgeschützte Evidenz-Normalisierer (`observation.py`), der echte GPIO-Verriegelungs-Leser (`gpio_safety.py` mit `GpioSafetyProbe`, libgpiod v2) und der MQTT-Status-/Evidenz-Transport (`mqtt_transport.py`) sind real und durch 149 bestehende `unittest`-Fälle abgedeckt (`python tools/build_test.py`), einschließlich `tests/test_gpio_mqtt_emulator.py`, das diese Bridge gegen einen protokolltreuen, von Hand geschriebenen GPIO/MQTT-Emulator laufen lässt. Nichts davon hat je einen echten GPIO-Chip, einen echten MQTT-Broker oder einen echten Laser-Controller berührt - `test_gpio_safety.py` liest gegen einen simulierten Chip, und `test_mqtt_transport.py` verwendet einen simulierten Broker-Client. Es gibt noch keine konkrete Laser-Controller-/Software-Integration, weil die Maschine und ihre dokumentierte Schnittstelle nicht verfügbar sind - siehe „Aktueller Status und nächste Schritte" weiter unten, das dies bereits klar sagt, sowie `CHANGELOG.md` für das, was bisher genau ausgeliefert wurde.

> **Stand von Sicherheit (Safety) und Security:** Dieses Ökosystem ist kein zertifiziertes Sicherheitssystem. Es gibt noch keinen Hardware-E-STOP-Pfad, keine von der Firmware durchgesetzten Grenzen oder Verriegelungen und keinen verifizierten Bewegungsbefehl; Firmware-Images werden mit CRC-32 und einer Ed25519-Signatur geprüft, und ein Release-Build verweigert die veröffentlichten Entwicklungsschlüssel (die Werkzeugköpfe und Erweiterungsplatinen hinter dem Relais laufen noch mit URTC-Bootloadern, die statt einer Signatur ein HMAC-SHA256 mit gemeinsamem Schlüssel verwenden); TLS und gegenseitiges TLS sind optional und standardmäßig aus; noch keine eigene Platine wurde bestückt oder getestet. Lesen Sie die [Sicherheitsbasis](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/SECURITY_BASELINE.md) und das [Bedrohungsmodell](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/THREAT_MODEL.md), bevor Sie sich für die Sicherheit einer Person auf eine Aussage hier verlassen.

---

## 📋 Auf einen Blick

| | |
|---|---|
| Version | `0.1.8` |
| Reifegrad | Funktionsfähig |
| Tests | 149 (`python tools/build_test.py`) |
| Technik | Python / Laser controller / G-code / Safety evidence / GPIO interlock reading |
| Ziel | Der Raspberry Pi CM5 einer HYDRA-UMC-Zelle |
| Auf echter Hardware | Nur simuliert: gegen Emulatoren, Attrappen oder Simulatoren getestet; für diese Version ist kein Lauf auf echter Hardware vermerkt |

**Springe zu:** [Überblick](#-überblick) · [Architektur](#-architektur) · [Funktionen](#-funktionen) · [Sicherheit und Schutz](#-sicherheit-und-schutz) · [Schnittstellen](#-schnittstellen) · [Konfiguration](#-konfiguration) · [Schnellstart](#-schnellstart) · [Tests](#-tests) · [Fehlerbehebung](#-fehlerbehebung) · [Struktur des Repositorys](#-struktur-des-repositorys) · [Verwandte Projekte](#-verwandte-projekte)

## 🚦 Projektstatus

Jede Zeile ist ein Teil dieses Repositorys, und die Ampel sagt, wie weit er heute ist. Sie beruht auf dem, was das Repository zeigen kann (Tests, Builds, Läufe), nicht auf dem, was geplant ist.

🟢 Fertig und überprüft · 🟡 Funktioniert, mit bekannten Grenzen · 🟠 Teilweise fertig oder noch nicht überprüft · 🔴 Nicht gemacht oder funktioniert nicht

| Bereich | Stand | Was das hier bedeutet |
|---|---|---|
| Software | 🟡 | Funktioniert für seinen Hauptzweck; die Ehrlichkeitsprüfung oben nennt, was noch fehlt |
| Tests | 🟢 | 149 automatische Tests, bei jeder Änderung ausgeführt |
| Echte Hardware | 🟠 | Nur simuliert: gegen Emulatoren, Attrappen oder Simulatoren getestet; für diese Version ist kein Lauf auf echter Hardware vermerkt |
| Dokumentation | 🟢 | README in acht Sprachen, bei jeder Änderung gegen das Manifest geprüft |

## 🎯 Überblick

**HYDRA-UMC-BRIDGE-LASER** ist die High-Level-Brücke für Laserzellen und HYDRA-UMC-Roboterhilfsfunktionen. Sie kann sichere Randaufgaben wie die Materialübergabe koordinieren, kann eine Lasersteuerung jedoch **niemals** scharfschalten, auslösen oder überstimmen — das sind Beobneunungen, die sie liest, keine Befugnisse, die sie besitzt.

Sie gehört zur Familie **External Automation Bridges**: einer Gruppe von Schwester-Repositories (CNC, LASER, OPENPNP, PRINTER3D, ROS2), die alle denselben gemeinsamen Sicherheitsvertrag von `HYDRA-UMC-SDK` sprechen, sodass keine Brücke ihre eigene Definition von "sicher zum Arbeiten" erfinden kann.

## 🧩 Rolle in HYDRA-UMC

**HYDRA-UMC-BRIDGE-LASER** lässt eine Roboterzelle um einen Laserschneider oder -gravierer arbeiten, ohne ihn je scharf schalten oder auslösen zu können. Er liest drei unabhängige Sicherungen (Schlüsselschalter, Gehäuse, Verriegelung) per GPIO und den Zustand einer GRBL-Laser-Steuerung; nur eine Zelle, in der jede Sicherung „sicher“ meldet, bekommt Arbeit.

Jeder Bridge spricht den gemeinsamen Sicherheitsvertrag von `HYDRA-UMC-SDK`: Ein Auftrag wird nur angenommen, wenn das gemeinsame Tor `evaluate_job()` zustimmt, und das Tor schließt im Zweifel. Das Elternprojekt ist `HYDRA-UMC-SERVER`; dieser Bridge ruft es nicht auf, er antwortet über MQTT und `HYDRA-UMC-MQTT-BROKER` dem, der die Zelle steuert.

## 🏛️ Architektur

<p align="center">
  <img src="images/architecture.svg" alt="HYDRA-UMC-BRIDGE-LASER architecture" width="100%">
</p>

<details>
<summary>Textversion des Diagramms (Mermaid)</summary>

```mermaid
flowchart LR
    LASER["Lasersteuerung<br/>(Zustand, Schlüssel, Gehäuse, Verriegelung)"] --> BRIDGE["BRIDGE-LASER<br/>LaserSafetySnapshot.machine_state()"]
    BRIDGE -- "BridgeJob + beobachteter MachineState" --> SDK["HYDRA-UMC-SDK<br/>evaluate_job()"]
    SDK -- GateDecision --> RESULT["MQTT: cmd/job/result"]
```

</details>

**Warum es so gebaut ist**

* **Warum drei unabhängige Sicherungen statt eines einzelnen Booleans.** `LaserSafetySnapshot.machine_state()` prüft `key_enabled`, `enclosure_closed` und `interlock_healthy` als drei getrennte Bedingungen — echte Lasersicherheit erfordert, dass jede physische Schutzmaßnahme unabhängig voneinander wahr ist; sie zu einem einzigen Flag zusammenzufassen würde verschleiern, welche davon tatsächlich fehlgeschlagen ist.
* **Warum die Brücke dokumentiert, dass sie einen Laser niemals scharfschalten oder auslösen kann.** Der eigene Docstring von `LaserCellBridge` besagt, dass sie "nur externe Hilfsfunktionen koordiniert; sie kann einen Laser nicht scharfschalten oder auslösen" — diese Bedingungen sind Beobneunungen der eigenen zertifizierten Verriegelungen der Steuerung, niemals ein Ersatz dafür.
* **Warum die Zustandsabbildung des Controllers bewusst konservativ ist.** Nur die wörtliche Zeichenkette `IDLE` wird auf `MachineState.IDLE` abgebildet. Jeder nicht erkannte Wert fällt auf `OFFLINE` zurück, niemals auf etwas, das Hilfsarbeit erlauben würde.
* **Warum die Brücke einen neuen `BridgeJob` erstellt und an das gemeinsame `evaluate_job()` delegiert, statt eigene Annahme-/Ablehnungslogik zu schreiben.** Alle fünf External Automation Bridges (CNC, LASER, OPENPNP, PRINTER3D, ROS2) verwenden exakt denselben `bridge_contract` von `HYDRA-UMC-SDK` wieder, sodass "was als sicher für den Start eines Auftrags zählt" zwischen ihnen nicht stillschweigend auseinanderdriften kann.
* **Warum die Wahl der echten Laser-Software/-Steuerung bewusst zurückgestellt wird.** Sich auf die Schnittstelle eines bestimmten Herstellers festzulegen, bevor Maschine und ihre dokumentierte Verriegelungsmeldung verfügbar sind, würde bedeuten, eine echte Sicherheitsgarantie zu behaupten, die dieser lokale Kern nicht verifizieren kann.
* **Wie das in den Rest des Ökosystems passt.** BRIDGE-LASER sitzt zwischen der Lasersteuerung und `HYDRA-UMC-SDK` → `HYDRA-UMC-MQTT-BROKER` → unabhängiger Sicherheit: es koordiniert Roboter-Hilfsarbeit rund um die Laserzelle, es ersetzt oder überschreibt nicht die zertifizierte Lasersicherheit.

Der Beobachtungs-Helfer ist ein Evidenz-Normalisierer, kein Laser-Controller-Adapter: er öffnet keine Netzwerk- oder serielle Verbindung, ändert keine Einstellungen, lädt keine Jobs hoch, scharf schaltet oder zündet nicht. [Laser Controller Evidence Boundary](docs/CONTROLLER_EVIDENCE_BOUNDARY.md) definiert die vor einer echten Integration erforderliche Validierung.

## ✨ Funktionen

* ✅ **Vier-Signal-Sicherheits-Snapshot (Software-Logik, ohne Laser getestet):** `cell.py` — `LaserSafetySnapshot.machine_state()` verlangt, dass der Schlüsselschalter aktiviert, das Gehäuse geschlossen **und** die Verriegelung intakt sind — gleichzeitig; fehlt eines davon, wird auf `SAFE_STOP` aufgelöst, noch bevor `controller_state` überhaupt gelesen wird. *(implementiert, getestet in `tests/test_cell.py`)*
* ✅ **Echtes gemeinsames Sicherheitsgatter:** jeder beobachtete Auftrag wird über `evaluate_job()` aus dem `bridge_contract` von `HYDRA-UMC-SDK` neu bewertet — demselben Gatter, das jede Schwesterbrücke verwendet. *(implementiert)*
* ✅ **Konservative Zustandsabbildung:** nur `IDLE` wird als Leerlauf behandelt; `RUN`/`RUNNING`/`PAUSED` werden auf `RUNNING` abgebildet, `FAULT`/`ALARM`/`ERROR` auf `FAULT`, und jeder nicht erkannte Wert fällt auf `OFFLINE` zurück. *(implementiert)*
* ✅ **Schreibgeschützter Sicherheitsnachweis:** `observation.py` akzeptiert nur echte boolesche Signale für Schlüssel, Gehäuse und Verriegelung; fehlende, numerische oder textartige Werte schlagen sicher fehl. Es kann einen Laser weder scharfschalten noch auslösen. *(implementiert, getestet in `tests/test_observation.py`)*
* ✅ **Controller-neutrales GPIO-Verriegelungs-Lesen (nur gegen einen simulierten Chip getestet):** `GpioSafetyProbe` aus `gpio_safety.py` liest dieselben 3 unabhängigen Schutzeinrichtungen von GPIO-Leitungen (libgpiod v2; die Tests nutzen einen simulierten Chip) statt aus einem gespeicherten Mapping - bewusst controller-unabhängig, da ein Schlüsselschalter/Türsensor/Verriegelungsrelais bei Laserschneidern herstellerunabhängig universell ist. Ein GPIO-Lesefehler lässt alle 3 Schutzeinrichtungen sicher fehlschlagen. *(implementiert, getestet in `tests/test_gpio_safety.py`)*
* ✅ **Flankengesteuerte Überwachung der Verriegelungen (nur gegen einen simulierten Chip getestet):** `open_gpio_safety()` öffnet die Leitungen für Schlüssel, Gehäuse und Verriegelung EINMAL (`INPUT`, `Edge.BOTH`) und bedient mit dieser einen Anforderung sowohl die Pegelleser als auch den Flankenwächter — der Kernel lehnt eine zweite Anforderung derselben Leitungen ab. `watch_for_interlock_edges()` blockiert auf den Flanken-Ereignismeldungen des Kernels (libgpiod v2), statt Pegel nur dann neu zu lesen, wenn eine fremde MQTT-Nachricht danach fragt, und `run_forever(edge_watcher=...)` startet einen Daemon-Thread, der in dem Augenblick einen aktualisierten, retained `state` veröffentlicht, in dem eine Leitung wechselt; fällt der Wächter aus, veröffentlicht er einen fail-closed `state` (`SAFE_STOP`, mit Grund) und versucht es weiter. Die Verdrahtung jeder Leitung wird deklariert (`GpioLineSettings`: `active_low`, `bias` — der Standard lässt ein durchtrenntes Kabel als unsicher lesen — und `debounce_ms`); siehe `docs/WIRING_GUIDE.md`. Noch nicht an einem echten GPIO-Chip validiert. *(implementiert, getestet in `tests/test_gpio_safety.py` und, mit einem simulierten `gpiod`, in `tests/test_hardening.py`)*
* ✅ **Sicherheitsereignis-Strom (getestet mit simulierten Leitungen und einem simulierten Flankenwächter):** `events.py` macht aus jeder Änderung von Schlüssel, Gehäuse und Interlock einen Datensatz mit Zeitstempel auf `hydra/bridges/laser/event/safety` (das Protokoll, das ein Data Lake für Audit und OEE aufbewahrt) und, genau einmal, wenn die Zelle von sicher auf unsicher wechselt, ein Ereignis `hydra/bridges/laser/event/interlock_open` mit den geöffneten Schutzeinrichtungen, damit der Orchestrator die Arme der Zelle sofort anhält. Beide sind QoS 1 und nie retained; sie tragen `at_ms` und eine wachsende `sequence`; die erste Messung ist nur eine Basis; fällt der Flankenwächter aus, wird der Verlust ebenfalls als offenes Interlock gemeldet. Die Bridge meldet nur: Sie kann keinen Laser stoppen. *(implementiert, getestet in `tests/test_events.py`)*
* ✅ **Optionale Zusatz-Schutzeinrichtungen (getestet mit simulierten Eingängen):** `auxiliary.py` lässt die Zelle zusätzliche Bedingungen deklarieren - laufende Rauchabsaugung, Hilfsluft an, Temperatur der CO2-Röhre höchstens ein Grenzwert - als `AuxiliaryCheck`, die an `LaserMqttBridge(auxiliary=...)` übergeben werden. Ein Auftrag außer ABORT wird abgelehnt, mit Nennung der fehlgeschlagenen Prüfung, solange eine nicht erfüllt ist; ein nicht lesbarer, nicht numerischer oder nicht endlicher Wert gilt als nicht erfüllt; `state` enthält eine Map `auxiliary`. Ohne Deklaration ändert sich nichts. Nur lesend: Es schaltet nichts. *(implementiert, getestet in `tests/test_auxiliary.py`)*
* ✅ **Nicht-mutierender Build/Test:** `build-test.bat`/`.sh` kompilieren den Quellcode und führen die Sicherheitsgatter-Testsuite aus, ohne Versionsdateien oder das CHANGELOG anzufassen. *(implementiert, siehe Build und Veröffentlichung unten)*
* ✅ **GRBL-Laser-Statusleser (nur gegen eine simulierte Platine getestet):** `GrblLaserState` in `grbl_state.py` ist der echte `controller_state` für eine Laser-Steuerung der GRBL-Familie an einem seriellen Port (die Platinen, die LaserGRBL und LightBurn ansteuern): er sendet die GRBL-Statusabfrage `?` und gibt das Statuswort des Berichts zurück. Er ist absichtlich nur lesend - das einzige Byte, das er schreibt, ist `?`, es gibt weder Halt, Reset, Fortsetzen noch G-Code - und fällt sicher aus (keine Antwort ist ein leerer Zustand, nie Leerlauf). Port, wiederverbindende Verbindung und Parser sind die gemeinsame serielle Anbindung des SDK, die auch die CNC-Bridge nutzt. Laserleistung und Vorschub des Berichts gehen als Information in `state` (`laser_power`, `feed_rate`), nie als Sicherung. Eine GRBL-Platine hat nur einen seriellen Port: solange LightBurn oder LaserGRBL ihn hält, kann dieser Leser ihn nicht nutzen. *(implementiert, nicht an einer echten Platine erprobt)*
* 🔜 **Konkrete Laser-Controller-/Software-Integration** — bewusst zurückgestellt, bis Maschine und dokumentierte Schnittstelle verfügbar sind. *(geplant)*
* ✅ **Wiederholte Idempotenzschlüssel:** `LaserMqttBridge` nimmt einen `IdempotencyStore` an: ein wiederholter Auftragsschlüssel erhält die Antwort vom ersten Mal, statt erneut bewertet zu werden. *(implementiert, getestet in `tests/test_idempotency.py`)*
* ✅ **Gehärtete MQTT-Schleife und fail-closed Lesen:** eine zu große (über 16 KiB) oder unlesbare Nutzlast, tief verschachteltes JSON und jeder unerwartete Fehler werden mit einer Ablehnung auf dem Ergebnis-Topic beantwortet und beenden die Schleife nie; die Antworten von `cmd/job` tragen `"mode": "gate-only"`, und ein ABORT darüber sagt, dass nichts gestoppt wurde (der physische E-STOP stoppt den Laser); der Zustand enthält `observed_at`, und die Bridge meldet sich auf einem `availability`-Topic mit Last Will; jede Ausnahme beim Lesen der GPIO-Leitungen — nicht nur `OSError` — lässt alle drei Sicherungen fehlschlagen, und die drei Pegel werden in einer Operation unter einer Sperre gelesen; Controller-Zustände im GRBL-Stil wie `Hold:0`, `Alarm:1`, `Door:1`, `Jog` und `Home` werden verstanden. *(implementiert, getestet in `tests/test_hardening.py`)*

## 🔒 Sicherheit und Schutz

| Bedrohung | Abwehr | Wo |
|---|---|---|
| Ein Auftrag für eine Zelle oder Maschine, die nicht sicher ist | Jeder Auftrag läuft durch das gemeinsame Tor `evaluate_job()` des SDK, das im Zweifel schließt; der Bridge hat keine eigene Annahmelogik | SDK `bridge_contract` |
| Überlange oder unbegrenzte Auftragsdaten | Höchstens 32 Parameter, Schlüssel bis 64 Zeichen, Werte bis 1024, Bezeichner bis 128 (`MAX_PARAMETERS`, `MAX_PARAMETER_KEY_CHARS`, `MAX_PARAMETER_VALUE_CHARS`, `MAX_IDENTIFIER_CHARS`) | SDK `bridge_contract` |
| Ein wiederholter oder erneut gesendeter Befehl | Ein `IdempotencyStore` merkt sich jeden Schlüssel 24 Stunden und höchstens 10 000 Einträge; eine Wiederholung bekommt die erste Antwort, statt neu bewertet zu werden | SDK `job_intake` |
| Eine riesige oder feindliche MQTT-Nutzlast | Eine Nutzlast über 16 KiB, unlesbares oder tief verschachteltes JSON und jeder unerwartete Fehler werden mit einer Ablehnung auf dem Ergebnis-Topic beantwortet und beenden die Schleife nie | `mqtt_transport.py` |
| Ein versehentlich scharfgeschalteter Laser | Alle drei unabhängigen Sicherungen (`key_enabled`, `enclosure_closed`, `interlock_healthy`) müssen „sicher“ melden; nur der genaue Steuerungszustand `IDLE` gilt als Leerlauf, alles andere ist `OFFLINE` | `cell.py`, `events.py` |
| Ein durchtrenntes Verriegelungskabel | Die Standard-Vorspannung lässt ein durchtrenntes Kabel als unsicher lesen (Pull-up bei Low-aktiv, Pull-down bei High-aktiv), Kontaktprellen wird standardmäßig 10 ms ignoriert und die drei Leitungen sind verschieden | `gpio_safety.py` |
| Ein fehlschlagendes GPIO-Lesen | Der gehaltene `state` wird mit dem Grund geschlossen (jede Sicherung unerfüllt, `SAFE_STOP`), damit niemand einen alten guten Zustand weiterliest | `mqtt_transport.py` |
| Ein gehaltener Befehl, der beim Wiederverbinden erneut läuft | Eine gehaltene `cmd/`-Nachricht wird beim Wiederverbinden ignoriert | `mqtt_transport.py` |

**Was er nie tut:** er koordiniert nur externe Hilfseinrichtungen: Er kann keinen Laser scharf schalten oder auslösen und sendet der GRBL-Steuerung nur die Statusabfrage.

## 🔌 Schnittstellen

Topics unter `hydra/bridges/laser/`; es gibt kein Stopp-Verb (`STOP_VERBS` ist leer).

| Topic oder Route | Was es trägt |
|---|---|
| `cmd/status` | leere Nutzlast: liest die drei GPIO-Leitungen neu und veröffentlicht den Zustand |
| `cmd/job` → `cmd/job/result` | ein `BridgeJob` als JSON; er plant nur: Die Antwort ist eine `GateDecision` |
| `state`, `availability` | der gehaltene Schnappschuss mit Zeitstempel und `online`/`offline` |
| `event/safety`, `event/interlock_open` | QoS-1-Ereignisse, nicht gehalten, wenn sich eine Sicherung ändert |

Die Bibliothek: `LaserCellBridge`, `LaserSafetySnapshot`, `LaserMqttBridge`, `GpioSafetyProbe`, `open_gpio_safety()`, `GrblLaserState`, `open_grbl_laser_state()` und `AuxiliarySupervisor` (Absaugung, Hilfsluft, CO2-Röhrentemperatur).

## ⚙️ Konfiguration

| Variable | Standard | Was sie festlegt |
|---|---|---|
| `GpioLineSettings.active_low` | erforderlich | `True`, wenn das Signal bei Logik 0 sicher ist (ein Öffner nach Masse) |
| `GpioLineSettings.bias` | ausfallsicher | `pull-up`, `pull-down`, `disabled` oder `as-is`; ohne Angabe wird die Variante gewählt, bei der ein durchtrenntes Kabel unsicher gelesen wird |
| `GpioLineSettings.debounce_ms` | `10.0` | Kontaktprellen wird so lange ignoriert; `0` schaltet es ab, ein negativer Wert wird abgelehnt |
| `HYDRA_MQTT_USERNAME` | keiner | Der MQTT-Benutzername; der Broker bindet ihn an ein Client-ID-Präfix |
| `HYDRA_MQTT_PASSWORD` | keiner | Das Passwort; nur zusammen mit dem Benutzernamen gültig |
| `HYDRA_MQTT_PASSWORD_FILE` | keiner | Das Passwort aus einer Datei (Docker- oder systemd-Secret); wird ignoriert, wenn `HYDRA_MQTT_PASSWORD` gesetzt ist |
| `HYDRA_MQTT_TLS_CA` | keiner | Die CA-Datei, die das Zertifikat des Brokers signiert hat: Die Verbindung ist TLS und das Zertifikat wird geprüft |
| `HYDRA_MQTT_TLS` | aus | `1` schaltet TLS ein, geprüft gegen die vertrauenswürdigen CAs des Systems |
| `HYDRA_MQTT_TLS_CERT` / `HYDRA_MQTT_TLS_KEY` | keiner | Das Clientzertifikat und sein Schlüssel für einen Broker mit gegenseitigem TLS; beide sind nötig |

Die Offsets der drei GPIO-Leitungen und der Chip sind Argumente von `open_gpio_safety()`; das serielle Gerät der GRBL-Steuerung ist das Argument von `open_grbl_laser_state()` (standardmäßig 115200 Baud, 1 Sekunde Zeitlimit).

## 🚀 Schnellstart

Benötigt Python 3.11 oder neuer. Die Tests und die Build-Skripte erwarten `HYDRA-UMC-SDK` neben diesem Repository (`../HYDRA-UMC-SDK`) oder über `HYDRA_UMC_SDK_ROOT` angegeben.

Ohne Hardware ausprobieren (das prüft den ganzen Bridge gegen seine Emulatoren und Attrappen):

```bash
py -3 tools/build_test.py          # Windows
python3 tools/build_test.py         # Linux, macOS
```

Den Dienst starten (es gibt kein Konsolenskript: Der Dienst ist das `run_forever()` des MQTT-Transports, das du aus deinem eigenen Startcode aufrufst):

```python
from hydra_umc_bridge_laser.gpio_safety import GpioLineSettings, open_gpio_safety
from hydra_umc_bridge_laser.grbl_state import open_grbl_laser_state
from hydra_umc_bridge_laser.mqtt_transport import LaserMqttBridge, run_forever
wiring = GpioLineSettings(active_low=True)                       # normally-closed contacts to ground
safety = open_gpio_safety("/dev/gpiochip0", 17, 27, 22, key=wiring, enclosure=wiring, interlock=wiring)
bridge = LaserMqttBridge(safety.lines, controller_state=open_grbl_laser_state("/dev/ttyUSB0"), cell_state=lambda: cell_state)
run_forever(bridge, host="192.168.0.180", edge_watcher=safety.watcher)   # serves cmd/# and publishes the events
```

Benutzername, Passwort und TLS-Dateien kommen aus den Variablen `HYDRA_MQTT_*` (siehe Konfiguration); der Code oben braucht keine eigenen Zugangsdaten.

## 🧪 Tests

149 automatische `unittest`-Fälle laufen mit `python tools/build_test.py` (das kompiliert auch jedes Modul). Die Tests brauchen weder Hardware noch Netz noch optionale Pakete: Die, die `paho-mqtt`, `pyserial` oder eine Herstellerbibliothek bräuchten, nutzen einen Ersatz oder werden übersprungen, wenn das Paket fehlt.

| Testdatei | Tests | Was sie abdeckt |
|---|---|---|
| `test_cell.py`, `test_observation.py`, `test_events.py`, `test_auxiliary.py` | - | Sicherungen, Nachweise, Ereignisse und Hilfsprüfungen |
| `test_gpio_safety.py`, `test_gpio_mqtt_emulator.py`, `gpio_mqtt_emulator.py` | - | der GPIO-Leser gegen Scheinleitungen; der echte Bridge gegen GPIO- und MQTT-Fixtures |
| `test_grbl_state.py` | - | der GRBL-Leser gegen eine Speicher-Steuerung, die wie GRBL spricht (Banner, `ok`, alte Antworten) |
| `test_mqtt_transport.py`, `test_mqtt_environment.py`, `test_hardening.py`, `test_edge_cases.py`, `test_idempotency.py` | - | Topic-Verteilung, Zugangsdaten der Umgebung, feindliche Clients, ungewöhnliche Messwerte und wiederholte Schlüssel |

Die CI führt `HYDRA_UMC_CI=1 python tools/ci_validate.py` aus; das prüft das Manifest, die Dokumente, die acht READMEs und die Bilder und führt die Tests mit einem SDK-Checkout aus.

## 🏗️ Build und Veröffentlichung

Erfordert Python 3.11+. `tools/build_test.py` erwartet, dass `HYDRA-UMC-SDK` als Schwesterverzeichnis (`../HYDRA-UMC-SDK`) ausgecheckt oder über die Umgebungsvariable `HYDRA_UMC_SDK_ROOT` angegeben ist.

```bash
# Windows
build-test.bat      # nur Validierung — keine Versions-/CHANGELOG-Änderung
build.bat            # Validiert und baut (Bauen ändert nie die Version)

# Linux/macOS
bash build-test.sh
bash build.sh
```

`build-test` kompiliert jedes Modul unter `src/` und `tools/` mit `py_compile` und führt die vollständige, unter `tests/` entdeckte `unittest`-Suite aus (`test_cell.py`, `test_observation.py`, `test_gpio_safety.py`, `test_mqtt_transport.py`, `test_gpio_mqtt_emulator.py`, `test_hardening.py`, `test_idempotency.py`, `test_mqtt_environment.py` - 149 Tests), was unter anderem die Zulassung im sicheren Leerlauf, die Gehäuse-Ablehnung und die Abbruchweiterleitung belegt — es ändert das Repository nie. `build` führt zuerst dieselbe Validierung aus und ruft nur bei Erfolg `tools/bump_version.py` auf, um die Version in `pyproject.toml`, `hydra-umc.project.json` und `CHANGELOG.md` zu synchronisieren. Es gibt noch keinen echten Laser-`run`-Befehl — dafür ist eine validierte, sichere Controller-Integration erforderlich.

## 🩺 Fehlerbehebung

| Du siehst | Weil | Tu |
|---|---|---|
| `ModuleNotFoundError: hydra_umc_sdk` | Das SDK ist nicht installiert oder liegt nicht neben diesem Repository | `HYDRA-UMC-SDK` neben dieses Repository klonen oder `HYDRA_UMC_SDK_ROOT` setzen |
| `paho-mqtt is not installed` | Der MQTT-Client ist ein optionales Extra | `pip install ".[mqtt]"` (braucht `paho-mqtt` ab 2.1, unter 3) |
| `password was given without a username` | MQTT-Zugangsdaten brauchen beide Teile | Setze auch `HYDRA_MQTT_USERNAME`, nicht nur das Passwort |
| `could not reach the MQTT broker after N attempts` | Der Broker ist aus, die Adresse falsch oder der Port geschlossen | Starte `HYDRA-UMC-MQTT-BROKER` und prüfe Host und Port des Transports (5 Versuche im Abstand von 2 Sekunden); ein TLS-Handshake-Fehler wird nicht wiederholt |
| `the MQTT broker refused the connection` | Der Broker hat die Zugangsdaten abgelehnt (oder nicht rechtzeitig geantwortet) | Prüfe `HYDRA_MQTT_USERNAME` und das Passwort; die Client-ID muss mit dem Präfix beginnen, das der Broker an die Zugangsdaten gebunden hat |
| `state` with every safeguard unsatisfied and `SAFE_STOP` | Ein GPIO-Lesen ist fehlgeschlagen (Chip fehlt, Berechtigung, freigegebene Anforderung) oder der Flankenwächter ist ausgefallen | Lies den Grund im gehaltenen `state`; prüfe Chip-Pfad, Leitungs-Offsets und die Rechte des Dienstbenutzers |
| `"allowed": false` + `reason` | Das gemeinsame Tor oder eine Sperre hat den Befehl abgelehnt | Lies `reason` und behebe die Ursache; nicht blind wiederholen |

## 📂 Struktur des Repositorys

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of HYDRA-UMC-BRIDGE-LASER" width="100%">
</p>

<details>
<summary>Textversion des Baums</summary>

```text
HYDRA-UMC-BRIDGE-LASER/
├── src/hydra_umc_bridge_laser/
│   ├── cell.py                    lehnt Arbeit ab, wenn die Sicherungen keinen sicheren Leerlauf melden
│   ├── gpio_safety.py             liest die drei Sicherungsleitungen per GPIO (libgpiod)
│   ├── grbl_state.py              GRBL-Steuerungszustand; nur die Statusabfrage
│   ├── observation.py             lokale Sicherheitsnachweise, nie ein Laserbefehl
│   ├── events.py                  Ereignisse mit Zeitstempel, wenn sich eine Sicherung ändert
│   ├── auxiliary.py               Prüfung von Absaugung, Hilfsluft und Röhrentemperatur
│   └── mqtt_transport.py          MQTT-Transport für Befehle, Status und Ereignisse
├── tests/                         149 Tests, mit einem GPIO- und MQTT-Emulator
├── docs/                          Bridge-Leitfaden, Grenze der Nachweise, Verdrahtungsanleitung
├── tools/                         Build- und Testläufer, Versionserhöhung, CI-Prüfer, README- und Bildgeneratoren samt Prüfungen
├── images/                        Banner und die Bilder der README
├── .github/                       CI-Workflow und Issue-Vorlagen
├── pyproject.toml                 Paketmetadaten und Abhängigkeiten
├── hydra-umc.project.json         Manifest: Version, Reifegrad, Familie
├── CHANGELOG.md                   was sich in jeder Version geändert hat
├── build.sh build.bat             Build-Skripte (ändern die Version nie)
├── build-test.sh build-test.bat   Build-Skripte (ändern die Version nie)
├── test.sh test.bat               führen die Tests aus
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE LICENSE.md
```

</details>

## 🗺️ Roadmap und bekannte Grenzen

**Bekannte Grenzen heute**

**Heute real:** Version `0.1.8`, ein lokal getesteter ausfallsicherer Planungskern (`LaserSafetySnapshot` + `LaserCellBridge`), gestützt auf das gemeinsame Auftragsgatter von `HYDRA-UMC-SDK`, strenge schreibgeschützte Normalisierung von Sicherheits-Evidenz, die einen echt pausierten Auftrag (`HOLDING`) von einem echt aktiv feuernden (`RUNNING`) unterscheidet, ein echtes, controller-neutrales GPIO-Verriegelungs-Lesen (`GpioSafetyProbe`) für die 3 unabhängigen Schlüssel-/Gehäuse-/Verriegelungs-Schutzeinrichtungen, ein echter MQTT-Status-/Evidenz-Transport (`mqtt_transport.py`), eine deterministische `unittest`-Suite mit 149 Tests sowie nicht-mutierende Build-Test-Skripte, die in CI mit SDK-Checkout eingebunden sind.

**Integrationsgrenze:** das eigene zertifizierte Gehäuse, der Schlüsselschalter und die Verriegelungsautorität der Lasersteuerung werden nie umgangen; diese Brücke steuert ausschließlich *Hilfs*-Roboterarbeit um sie herum, und das nur durch Lesen ihres gemeldeten Zustands.

**Noch offen:** die Brücke wurde noch nicht mit einem realen Lasersystem verbunden oder zu dessen Betrieb genutzt — die Auswahl und Validierung einer konkreten Controller-/Software-Schnittstelle wird zurückgestellt, bis Maschine und ihre dokumentierte Schnittstelle verfügbar sind.

## 🌍 Sprachen

Diese README und die Dokumente des Repositorys gibt es in acht Sprachen: Englisch, Spanisch, Deutsch, Französisch, Italienisch, Japanisch, Chinesisch und Portugiesisch (Portugal). Sie entstehen gemeinsam, und die CI prüft, dass die acht Dateien dieselben Abschnitte und dieselben Links haben. Dieses Repository hat weder eine eigene Oberfläche noch einen eigenen Meldungskatalog, es gibt also keine Oberflächentexte zu übersetzen.

## 🔗 Verwandte Projekte

Dieses Projekt ist Teil des HYDRA-UMC-Robotik-Ökosystems desselben Autors (JuanenRac / Electro Hobby 3D). Gut zu wissen, da eine Anfrage eigentlich eines dieser Projekte betreffen könnte statt dieses Repositorys.

**Übergeordnetes Projekt**
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — das reale Headless-Backend (REST/WebSocket), mit dem jeder Steuerungsclient tatsächlich spricht; diese Bridge ruft es nicht auf: sie antwortet über MQTT, via HYDRA-UMC-MQTT-BROKER, demjenigen, der die Zelle steuert.

**Geschwisterprojekte** — sprechen ebenfalls mit der eigenen API von HYDRA-UMC-SERVER, jeweils als eigener Client
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — Web-Steuerungs-Dashboard mit Echtzeit-3D-Visualisierung mehrerer Roboter.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — Desktop-Schwarmleitstand (PySide6) für mehrere Server gleichzeitig, verpackt als eigenständige ausführbare Datei.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — native Android-Steuerungs-App mit biometrischem Login und einer gekoppelten Wear-OS-Begleit-App.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — iOS/iPadOS-Steuerungs-App (Flutter) mit Echtzeit-WebSocket-Synchronisierung.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — native Touch-UI für das eingebaute 7"-DSI-Touchscreen, direkt auf dem CM5 eingebettet.
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — Koordinationsschranke für AGV-/AMR-Flotten über einen VDA-5050-MQTT-Publisher (nur gegen eine emulierte Flotte getestet).
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — High-Level-Koordinator für CNC-Zellen mit GRBL-Status-/Steuerbyte-Zugriff (nur gegen einen Emulator getestet).
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — Koordinationsschranke für laufende/humanoide Droiden, mit einem Boston-Dynamics-Spot-Befehlssender (nur gegen einen Emulator getestet).
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — sicherer High-Level-Koordinator für den Leiterplattenfluss von OpenPnP Pick-and-Place.
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — sichere Koordinationsschranke für Moonraker/Klipper-3D-Drucker, mit echten gesicherten Job-Befehlen.
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — Koordinator mit einem träge importierten rclpy-ROS-2-Transport (noch nicht gegen eine ROS-2-Installation ausgeführt).
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — Koordinationsschranke für kameraausgestattete UAVs, mit einem MAVLink-Befehlssender (nur gegen einen Emulator getestet).

**Direkt verwandt**
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — der gemeinsame JSON-Schema-Vertrag und die Software-Auftragsschranke, gegen die jede Bridge ihre Befehle validiert (keine zertifizierte Sicherheitsfunktion).
- **[HYDRA-UMC-CONNECTOR-HUB](https://github.com/JuanenRac/HYDRA-UMC-CONNECTOR-HUB)** — deklaratives Adapter-Manifest-Register und Validator für Konnektoren externer Maschinen; erweitert die eigene Vertragsidee des SDK auf externe Maschinen, ohne die Industrie-Gateway-Projekte zu ersetzen.
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — der echte Transport von `mqtt_transport.py` für die eigenen `hydra/bridges/laser/...`-Topics dieser Bridge — nur Sicherungsstatus, da hier kein echter Aktivierungsbefehl existiert (diese Bridge kann einen Laser weder scharfschalten noch auslösen); siehe die eigene `docs/BRIDGE_TOPICS.md` dieses Repositorys.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — zukünftiger Zellzonen-Sicherheitsnachweis für diese Bridge.

**Ebenfalls Teil des Ökosystems**

*Kern-Hardware & Plattform*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — der Entwurf des Motherboards des Roboterarms: CM5-Host + Dual-Core-STM32H745, gedacht zur Koordination von bis zu 8 Werkzeugarmen über CAN-OTA/SPI-OTA (Firmware in einer frühen Phase; noch keine bestückte Platine).
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — reproduzierbare Raspberry-Pi-OS-Produktschicht für den CM5: schreibgeschützter Agent, validierte Konfiguration/Profile, WiFi-Ersteinrichtung.

*Kern-Backend & Clients*
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — grafischer Desktop-URDF-Ersteller/-Editor, der fertige Modelle in STUDIOs eigenen Katalog überträgt.
- **[HYDRA-UMC-EDITOR-STL](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-STL)** — Desktop-STL-Modelleditor, der echte Teile im selben Modellkatalog transformiert/ersetzt/entfernt/hinzufügt, den auch HYDRA-UMC-EDITOR-URDF bearbeitet.

*URTC-Werkzeugplattform*
- **[URTC](https://github.com/JuanenRac/URTC)** — Firmware für die physische Universal-Robot-Tool-Controller-Platine, 25+ Werkzeugprofile über CAN-Bus.
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — Desktop-GUI-Flash-Tool für URTC-Platinen, CAN-OTA plus Full-Chip-SWD/JTAG.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — Desktop-Live-CAN-Bus-Diagnosetool für URTC-Platinen, ein Panel pro Werkzeugprofil.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — browserbasierte Alternative zu URTC-TESTER über die Web-Serial-API, ohne lokale Installation.
- **[URTC-GATEWAY](https://github.com/JuanenRac/URTC-GATEWAY)** — Gateway vor dem CAN-Bus von URTC: Liste erlaubter Kennungen, Ratenbegrenzung und Sitzungsschlüssel; Software auf dem Computer getestet, noch nicht an einem echten Bus.

*Vision-KI-Knoten (Hailo-8)*
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — Integrationsknoten für die Hailo-8-Vision-Pipeline, mit einer echten stufenweisen Hardware-Bereitschaftsprüfung.
- **[HYDRA-UMC-DETECTION-HEF](https://github.com/JuanenRac/HYDRA-UMC-DETECTION-HEF)** — echte Registry für kompilierte Modelle mit Hailo-Architektur-/Prüfsummen-Safe-Load-Verifizierung.
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — echter GStreamer-Pipeline- + MediaMTX-Konfigurationsgenerator mit einer echten HailoRT-Integrationsschranke.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — Position-Based-Visual-Servoing-Korrekturgesetz mit Freigabe abhängig vom Zonenstatus; noch keine Posenschätzung per Kamera.

*Kognitiver KI-Knoten (Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — Integrationsknoten für die Hailo-10-Cognitive-Pipeline (LLM-/VLA-/Sprach-Orchestrierung).
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — echte Aktions-Token-Kodierung/-Dekodierung und Trajektoriengenerierung für ein Vision-Language-Action-Modell.
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — echtes Sprach-Frontend (VAD + Intent-Parser) mit einem begrenzten, bestätigungsgesicherten Watch-Relay.
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — echte regelbasierte Aufgabenzerlegung und semantische Fehlerbehebung über MCU-Fehlercodes.
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — echte, nur auf der Standardbibliothek basierende TF-IDF-Dokumentensuche über die eigenen Markdown-Dokumente dieses Ökosystems.
- **[HYDRA-UMC-LOCAL-TECHNICIAN](https://github.com/JuanenRac/HYDRA-UMC-LOCAL-TECHNICIAN)** — lokaler, richtlinien-gesteuerter KI-Wartungstechniker für das Ökosystem selbst - beobachtet, diagnostiziert und schlägt Korrekturen vor; die zwei höchsten Risikostufen sind absichtlich noch nicht implementiert.

*Orchestrierung & Schwarm*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — Integrationsknoten mit einem echten gRPC/Protobuf-Health-Report-Vertrag und einer Missions-Zustandsmaschine.
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — echte prioritätsbasierte Job-Queue mit Deduplizierung, über eine echte HTTP-API.
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — echter gRPC-basierter Flotten-Health-Watchdog mit Retry/Backoff und Identitäts-Mismatch-Erkennung.
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — echter RRT-basierter 3D-Pfadplaner mit echter Hindernis-/Arbeitsraum-Kollisionsvalidierung.
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — echte CRDT-LWW-Element-Map-Zustandssynchronisation, eigenschaftsgetestet auf Multi-Zellen-Konvergenz.

*Digitaler Zwilling & Simulation*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — Integrationsknoten für die Digital-Twin-Engine, mit einem echten Versionskompatibilitäts-Sync-Vertrag.
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — Hardware-in-the-Loop-Router mit einer Software-Kollisionsverriegelung zwischen Simulation und echter Hardware (ohne echte Hardware getestet).
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — echte Vorwärtskinematik und Gelenkgrenzenvalidierung über eine echte URDF-Teilmenge.
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — echter prozeduraler 2D-Szenengenerator mit YOLO/COCO-Annotationsexport.

*Daten & Analytik*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — echter sqlite3-gestützter Zeitreihenspeicher mit einer echten Ingest-/Abfrage-HTTP-API.
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — echter FFT- + statistischer Basislinien-Anomaliedetektor mit Drift-Überwachung.
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — echte OEE-/Verfügbarkeitsberechnung über den DATALAKE-Verlauf, mit reproduzierbarem CSV-Export.
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — echte CAN/WebSocket-Ingestion-Pipeline in DATALAKE, mit Sequenz-Deduplizierung.

*Industrie-Gateway*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — Integrationsknoten, der zu Industrieprotokollen weiterleitet, mit einer echten Befehls-Allowlist-/Backpressure-Schicht.
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — echter OPC-UA-Adressraum, verifiziert mit einer echten Binärprotokoll-Client-Session.
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — echte MTConnect-`/probe`- und `/current`-XML-Endpunkte mit Degraded-Mode-Ausgabe.

*Ergänzende Tools & Ökosystembetrieb*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — Smart-Summaries- und Anomaly-Highlighting-Panels über DATALAKE/ANOMALY-DETECTOR, mit einem ehrlichen statistischen Fallback.
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — Flotten-CLI mit einem echten, stabilen Exit-Code-Vertrag, ein echter Live-Client der eigenen API von HYDRA-UMC-SERVER.
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — WearOS-Begleit-App mit haptischen Alarmmustern und einem Sprach-Relay zum gekoppelten Telefon (noch nicht auf einer physischen Uhr ausgeführt).
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — Firmware für ein Platinenmontagegestell mit echter Werkzeug-ID-Dekodierung und Smart-Idle-Vorheizlogik.
- **[URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)** — Firmware plus ein echter Python-Vision-Begleiter für einen Thermal-/RGB-Inspektionswerkzeugkopf.
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — administratives Desktop-Tool, das jedes Repository in diesem Ökosystem entdeckt, klont und aktualisiert.
- **[HYDRA-UMC-OS-REBUILDER](https://github.com/JuanenRac/HYDRA-UMC-OS-REBUILDER)** — Windows/Linux-Desktop-Tool, das ein flashbereites CM5-Image baut, vorgeladen mit den aktuellsten Versionen des Ökosystems, mit Ersteinrichtungs-Konfiguration für WLAN/Benutzer/SSH im Stil von Raspberry Pi Imager.
- **[HYDRA-UMC-OPS-AGENT](https://github.com/JuanenRac/HYDRA-UMC-OPS-AGENT)** — Wartungsvorfall-Koordinator: eine Edge-Rolle mit niedrigem Privileg sammelt einen bereinigten Inventar-/Gesundheits-Snapshot, eine Control-Plane-Rolle rendert ihn schreibgeschützt und bittet einen KI-Anbieter um einen Diagnosevorschlag - wendet nie einen Patch an und stellt nie etwas bereit.
- **[HYDRA-UMC-DEV-SERVER](https://github.com/JuanenRac/HYDRA-UMC-DEV-SERVER)** — reproduzierbarer Entwicklungshost (Raspberry Pi 5 / CM5), der den Quellcode des Ökosystems vorhält und begrenzte Build-/Test-Aufgaben über eine dauerhafte Warteschlange ausführt; eine dedizierte Entwicklerrolle, ausdrücklich kein operativer CM5.

## 📚 Dokumentation

Hier steht mehr:

* [docs/BRIDGE_GUIDE.md](docs/BRIDGE_GUIDE.md) - Umfang, GPIO-Verdrahtungseinstellungen, der GRBL-Leser, Skripte
* [docs/WIRING_GUIDE.md](docs/WIRING_GUIDE.md) - wie die drei Sicherungssignale verdrahtet werden
* [docs/CONTROLLER_EVIDENCE_BOUNDARY.md](docs/CONTROLLER_EVIDENCE_BOUNDARY.md) - was als echter Sicherheitsnachweis gilt
* [Sicherheitsgrundlage des Ökosystems](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/SECURITY_BASELINE.md)
* [Bedrohungsmodell des Ökosystems](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/THREAT_MODEL.md)
* [Änderungsprotokoll dieses Repositorys](CHANGELOG.md)
* [Lizenz dieses Repositorys](LICENSE.md)

## 🤝 Mitwirken und Community

* Führe vor einem Pull Request `HYDRA_UMC_CI=1 py -3 tools/ci_validate.py` (oder `HYDRA_UMC_CI=1 python3 tools/ci_validate.py`) aus: Es muss `CI_VALIDATION=PASS` ausgeben. Führe dafür nicht `build.sh` oder `build.bat` aus; Bauen ist keine Prüfung.
* Die acht READMEs entstehen aus einer einzigen Quelle in HYDRA-UMC-DOCS; bearbeite sie nicht von Hand. Ändere die Quelle und schreibe sie mit `tools/make_readmes.py` neu.
* Behaupte in einer README nichts, was nicht gelaufen ist: Schreibe „simuliert“ oder „nicht auf Hardware erprobt“, wo das stimmt.
* Siehe [CONTRIBUTING.md](CONTRIBUTING.md), den [Verhaltenskodex](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md) und [SUPPORT.md](SUPPORT.md).

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LIZENZ

GPL-3.0-or-later - [LICENSE](LICENSE).
