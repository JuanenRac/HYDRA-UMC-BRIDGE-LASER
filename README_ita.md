<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Ponte di coordinamento cella laser
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 [Français](README_fra.md) | 🇮🇹 **Italiano** | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 [Français](README_fra.md) | 🇮🇹 **Italiano** | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

Ponte ad alto livello per celle laser e ausiliari robotici HYDRA-UMC. Può
coordinare compiti periferici sicuri, come il passaggio di materiale, ma non
può armare, sparare o aggirare un controllore laser.

## Architettura

```text
Controllore laser <-> BRIDGE-LASER <-> SDK <-> SERVER <-> sicurezza indipendente
```

Il ponte fallisce in modo sicuro a meno che il controllore sia inattivo, la
chiave sia abilitata, l'involucro chiuso e il controllore riporti un
interblocco sano. Queste condizioni sono osservazioni, mai sostituti della
sicurezza laser certificata.

## Build e test

Eseguire `build-test.bat` su Windows o `bash build-test.sh` su Linux. Non
cambia la versione e verifica l'ammissione a riposo sicuro, il rifiuto
dell'involucro e l'inoltro dell'interruzione. La scelta del software/
controllore laser reale è intenzionalmente rinviata finché non siano disponibili
la macchina e la relativa interfaccia documentata.

## Progetti correlati

| Progetto | Ruolo |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | Contratto di sicurezza condiviso. |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | Confine di cella autorizzato. |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | Futura evidenza di zona. |

## Stato

La versione `0.0.1` è un nucleo di pianificazione locale, testato e sicuro per
impostazione predefinita. Non è stato collegato né usato per azionare un sistema
laser.
