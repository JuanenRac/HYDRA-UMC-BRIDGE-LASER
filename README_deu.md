<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laserzellenkoordinierungsbruecke
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 [Français](README_fra.md) | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 **Deutsch** | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

Brücke auf hoher Ebene für Laserzellen und robotische HYDRA-UMC-
Hilfseinrichtungen. Sie kann sichere periphere Aufgaben wie Materialübergabe
koordinieren, jedoch keinen Laserregler scharf schalten, auslösen oder
übersteuern.

## Architektur

```text
Lasersteuerung <-> BRIDGE-LASER <-> SDK <-> SERVER <-> unabhängige Sicherheit
```

Die Brücke sperrt sicher, außer wenn die Steuerung im Leerlauf ist, der
Schlüssel aktiviert, die Einhausung geschlossen und der Interlock laut
Steuerung intakt ist. Diese Bedingungen sind Beobachtungen und niemals Ersatz
für zertifizierte Lasersicherheit.

## Build & Test

Unter Windows `build-test.bat` oder unter Linux `bash build-test.sh` ausführen.
Es ändert keine Version und testet sichere Leerlaufzulassung,
Einhausungsablehnung und Abbruchweiterleitung. Die Wahl realer Laser-Software/
Steuerung wird bewusst aufgeschoben, bis Maschine und dokumentierte Schnittstelle
verfügbar sind.

## Verwandte Projekte

| Projekt | Rolle |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | Gemeinsamer Sicherheitsvertrag. |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | Autorisierte Zellgrenze. |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | Zukünftiger Zonennachweis. |

## Status

Version `0.0.1` ist ein lokal getesteter ausfallsicherer Planungskern. Sie wurde
nicht mit einem Lasersystem verbunden oder zum Betrieb eines solchen verwendet.
