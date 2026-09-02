<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Ponte di coordinamento cella laser
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="Banner HYDRA-UMC-BRIDGE-LASER" width="100%">
</p>

# 🔦 HYDRA-UMC-BRIDGE-LASER

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | 🇮🇹 <b>Italiano</b> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 🛑 Ponte di coordinamento fail-safe per celle laser

<p align="left">
  <img src="https://img.shields.io/badge/Licenza-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Safety-Fails%20Closed-red.svg" alt="Fail-safe">
</p>

---

## 1. 🛠️ PANORAMICA TECNICA

**HYDRA-UMC-BRIDGE-LASER** è il ponte di alto livello per celle laser e ausiliari robotici HYDRA-UMC. Può coordinare attività periferiche sicure come il trasferimento di materiale, ma non può **mai** armare, attivare o scavalcare un controllore laser — quelle condizioni sono osservazioni che legge, non autorità che detiene.

Appartiene alla famiglia **External Automation Bridges**: un insieme di repository fratelli (CNC, LASER, OPENPNP, PRINTER3D, ROS2) che condividono lo stesso contratto di sicurezza di `HYDRA-UMC-SDK`, così nessun ponte può inventare una propria definizione di "sicuro per lavorare".

### Caratteristiche principali:
* ✅ **Snapshot di sicurezza a quattro segnali, reale:** `cell.py` — `LaserSafetySnapshot.machine_state()` richiede che la chiave sia abilitata, l'involucro chiuso **e** l'interblocco sano contemporaneamente; se anche solo uno manca, si risolve in `SAFE_STOP` ancor prima di leggere `controller_state`. *(implementato, testato in `tests/test_cell.py`)*
* ✅ **Porta di sicurezza condivisa, reale:** ogni lavoro osservato viene rivalutato tramite `evaluate_job()` del `bridge_contract` di `HYDRA-UMC-SDK`, la stessa porta usata da tutti i ponti fratelli e da HYDRA-UMC-SERVER. *(implementato)*
* ✅ **Mappatura di stato conservativa:** solo `IDLE` è trattato come riposo; `RUN`/`RUNNING`/`PAUSED` vengono mappati su `RUNNING`, `FAULT`/`ALARM`/`ERROR` su `FAULT`, e qualsiasi valore non riconosciuto ricade su `OFFLINE`. *(implementato)*
* ✅ **Evidenza di sicurezza in sola lettura:** `observation.py` accetta solo segnali booleani genuini per chiave, involucro e interblocco; valori mancanti, numerici o di tipo testo falliscono in modo sicuro. Non può armare né azionare un laser. *(implementato, testato in `tests/test_observation.py`)*
* ✅ **Lettura GPIO reale e neutrale rispetto al controllore:** `GpioSafetyProbe` di `gpio_safety.py` legge le stesse 3 protezioni indipendenti da vere linee GPIO (libgpiod v2) invece che da una mappatura salvata - deliberatamente agnostico rispetto al controllore, poiché un interruttore a chiave/sensore porta/relè di interblocco è universale sulle taglierine laser indipendentemente dalla marca. Un fallimento di lettura GPIO fa fallire in modo sicuro tutte e 3 le protezioni. *(implementato, testato in `tests/test_gpio_safety.py`)*
* ✅ **Build/test non mutante:** `build-test.bat`/`.sh` compilano il codice sorgente ed eseguono la suite di test della porta di sicurezza senza toccare i file di versione o il CHANGELOG. *(implementato, vedi COMPILAZIONE ED ESECUZIONE più sotto)*
* 🔜 **Integrazione concreta con controllore/software laser** — deliberatamente rimandata fino a quando la macchina e la sua interfaccia documentata non saranno disponibili. *(pianificato)*

---

## 2. 🔄 FLUSSO DI COORDINAMENTO DELLA CELLA

```mermaid
flowchart LR
    LASER["Controllore laser<br/>(stato, chiave, involucro, interblocco)"] --> BRIDGE["BRIDGE-LASER<br/>LaserSafetySnapshot.machine_state()"]
    BRIDGE -- "BridgeJob + MachineState osservato" --> SDK["HYDRA-UMC-SDK<br/>evaluate_job()"]
    SDK -- GateDecision --> SERVER["HYDRA-UMC-SERVER"]
    SERVER -- "lavoro / abort" --> SAFETY["Sicurezza laser indipendente"]
```

---

## 3. 🧱 ARCHITETTURA E DECISIONI DI PROGETTAZIONE

* **Perché quattro osservazioni di sicurezza indipendenti invece di un solo booleano.** `LaserSafetySnapshot.machine_state()` verifica `key_enabled`, `enclosure_closed` e `interlock_healthy` come tre condizioni separate — la sicurezza laser reale richiede che ogni protezione fisica sia indipendentemente vera; ridurle a un solo flag nasconderebbe quale di esse è effettivamente fallita.
* **Perché il ponte documenta che non può mai armare né attivare un laser.** Il docstring stesso di `LaserCellBridge` afferma che "coordina solo ausiliari esterni; non può armare né attivare un laser" — quelle condizioni sono osservazioni degli stessi interblocchi certificati del controllore, mai un loro sostituto.
* **Perché la mappatura dello stato del controllore è deliberatamente conservativa.** Solo la stringa letterale `IDLE` viene mappata su `MachineState.IDLE`. Qualsiasi valore non riconosciuto ricade su `OFFLINE`, mai su qualcosa che permetterebbe lavoro ausiliario.
* **Perché il ponte costruisce un nuovo `BridgeJob` e delega al `evaluate_job()` condiviso invece di scrivere una propria logica di accettazione/rifiuto.** Tutti e cinque gli External Automation Bridges (CNC, LASER, OPENPNP, PRINTER3D, ROS2) riutilizzano esattamente lo stesso `bridge_contract` di `HYDRA-UMC-SDK`, così "cosa conta come sicuro per avviare un lavoro" non può divergere silenziosamente tra loro.
* **Perché la scelta del software/controllore laser reale è deliberatamente rimandata.** Vincolarsi all'interfaccia di un fornitore specifico prima che la macchina e la sua segnalazione documentata degli interblocchi siano disponibili significherebbe affermare una garanzia di sicurezza reale che questo nucleo locale non può verificare.
* **Come si inserisce nel resto dell'ecosistema.** BRIDGE-LASER si trova tra il controllore laser e `HYDRA-UMC-SDK` → `HYDRA-UMC-SERVER` → sicurezza indipendente: coordina il lavoro robotico ausiliario attorno alla cella laser, non sostituisce né annulla la sicurezza laser certificata.

---

## 📂 STRUTTURA DELLE DIRECTORY

```text
HYDRA-UMC-BRIDGE-LASER/
├── src/
│   └── hydra_umc_bridge_laser/
│       ├── __init__.py
│       ├── cell.py              # Porta di sicurezza LaserSafetySnapshot + LaserCellBridge
│       ├── observation.py       # Normalizzazione in sola lettura dell'evidenza di sicurezza
│       ├── gpio_safety.py       # Legge i 3 segnali di sicurezza reali e indipendenti via GPIO - mai un comando laser
│       └── mqtt_transport.py    # Trasporto MQTT reale - solo stato/evidenza, questo bridge non può armare né sparare un laser
├── tests/
│   ├── test_cell.py             # Ammissione in riposo sicuro, rifiuto involucro, inoltro abort
│   ├── test_observation.py      # L'evidenza di sicurezza mancante fallisce fail-closed
│   ├── test_gpio_safety.py      # Letture GPIO di sicurezza reali contro un chip fittizio, incl. percorsi fail-closed
│   └── test_mqtt_transport.py   # Test di forma stato/evidenza MQTT contro un client broker fittizio
├── tools/
│   ├── build_test.py            # Compilatore + esecutore di test non mutante (build-test.bat/.sh)
│   └── bump_version.py          # Sincronizza pyproject.toml, manifesto e CHANGELOG.md
├── docs/
│   ├── BRIDGE_GUIDE.md                    # Ambito, piattaforme compatibili, script, porta di accettazione hardware
│   └── CONTROLLER_EVIDENCE_BOUNDARY.md    # Cosa conta come evidenza di sicurezza reale e cosa questo bridge rifiuta di dedurre
├── images/
│   └── HYDRA_UMC_BANNER.svg     # Banner del README
├── build-test.bat / build-test.sh  # Solo valida, non modifica mai il repository
├── build.bat / build.sh            # Valida e, solo in caso di successo, aggiorna versione + CHANGELOG
├── pyproject.toml               # Metadati del pacchetto; dipende da HYDRA-UMC-SDK (git)
├── hydra-umc.project.json       # Manifesto dell'ecosistema (versione, maturità, famiglia)
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md / CONTRIBUTING.md / SECURITY.md / SUPPORT.md
├── LICENSE / LICENSE.md
└── README.md / README_*.md      # Questo file e le sue 6 traduzioni
```

---

## 4. ⚙️ COMPILAZIONE ED ESECUZIONE

Richiede Python 3.11+. `tools/build_test.py` si aspetta che `HYDRA-UMC-SDK` sia clonato come directory fratella (`../HYDRA-UMC-SDK`) o indicato tramite la variabile d'ambiente `HYDRA_UMC_SDK_ROOT`.

```bash
# Windows
build-test.bat      # solo validazione — nessun cambio di versione/CHANGELOG
build.bat            # valida e, se ha successo, aggiorna versione + CHANGELOG

# Linux/macOS
bash build-test.sh
bash build.sh
```

`build-test` compila ogni modulo sotto `src/` con `py_compile` ed esegue l'intera suite `unittest` (`tests/test_cell.py`), dimostrando l'ammissione in riposo sicuro, il rifiuto involucro e l'inoltro dell'abort — non modifica mai il repository. `build` esegue prima quella stessa validazione e, solo in caso di successo, chiama `tools/bump_version.py` per sincronizzare la versione in `pyproject.toml`, `hydra-umc.project.json` e `CHANGELOG.md`. Non esiste ancora un comando `run` laser reale — serve un'integrazione del controllore validata e sicura.

---

## ✅ STATO ATTUALE E PROSSIMI PASSI

**Reale oggi:** versione `0.0.7`, un nucleo di pianificazione fail-safe testato in locale (`LaserSafetySnapshot` + `LaserCellBridge`) appoggiato sulla porta di lavoro condivisa di `HYDRA-UMC-SDK`, normalizzazione rigorosa e in sola lettura dell'evidenza di sicurezza che distingue un lavoro realmente in pausa (`HOLDING`) da uno realmente in taglio (`RUNNING`), una lettura GPIO reale e neutrale rispetto al controllore (`GpioSafetyProbe`) per le 3 protezioni indipendenti chiave/involucro/interblocco, una suite `unittest` deterministica di ventisette test, e script build-test non mutanti collegati alla CI con checkout dell'SDK.

**Confine di integrazione:** l'involucro, la chiave e l'interblocco certificati del controllore laser stesso non vengono mai aggirati; questo ponte regola solo il lavoro robotico *ausiliario* attorno ad esso, e solo leggendo il suo stato riportato.

**Ancora da fare:** il ponte non è stato collegato né usato per far funzionare un sistema laser reale — scegliere e validare un'interfaccia concreta di controllore/software è rimandato fino alla disponibilità della macchina e della sua interfaccia documentata.

---

## 🔗 PROGETTI CORRELATI

Questo progetto fa parte di un ecosistema robotico più ampio dello stesso autore (JuanenRac / Electro Hobby 3D), che copre firmware, software di controllo, nodi IA e strumenti di flotta. Vale la pena saperlo, perché una richiesta potrebbe in realtà riguardare uno di questi progetti anziché questo repository.

### Direttamente correlati

- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — la porta di lavoro condivisa `bridge_contract` attraverso cui questo ponte (e tutti gli altri) valuta i propri lavori.
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — il confine di cella autorizzato a cui questo ponte riporta.
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — il trasporto reale di `mqtt_transport.py` per i topic `hydra/bridges/laser/...` propri di questo ponte (stato delle protezioni + la porta di lavoro condivisa - qui non esiste alcun comando di attuazione reale, anche questo ponte non può armare né azionare un laser) - vedi il `docs/BRIDGE_TOPICS.md` di quel repository.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — futura evidenza di sicurezza della zona di cella.

### Resto dell'ecosistema

**Piattaforma HYDRA-UMC** — la micro-fabbrica multi-robot per cui questo ponte coordina gli ausiliari
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — la scheda madre CM5 + STM32H745 che orchestra fino a 8 bracci robotici.
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — il backend Express/WebSocket con cui parlano tutti i client di controllo e i ponti.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — dashboard di controllo web, visualizzazione 3D multi-robot.

**External Automation Bridges** — repository fratelli che condividono questa stessa porta di lavoro `HYDRA-UMC-SDK`
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — ponte di coordinamento cella CNC.
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — ponte di flusso schede per OpenPnP.
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — ponte di coordinamento per software di stampa 3D open.
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — confine di coordinamento bidirezionale con ROS 2.

**Evidenze di sicurezza e integrazione**
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — evidenze di sicurezza delle zone di cella usate in tutta la famiglia di ponti.
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — evidenze di test hardware-in-the-loop.

## 👤 AUTORE
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com
📺 [youtube.com/@electrohobby3d](https://youtube.com/@electrohobby3d)

## 📜 LICENZA
GPL-3.0 - Vedi LICENSE per i dettagli.
