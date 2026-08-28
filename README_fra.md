<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Pont de coordination de cellule laser
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 **Français** | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 **Français** | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

Pont de haut niveau pour les cellules laser et auxiliaires robotiques
HYDRA-UMC. Il peut coordonner des tâches périphériques sûres, comme le
transfert de matière, mais ne peut ni armer, ni tirer, ni outrepasser un
contrôleur laser.

## Architecture

```text
Contrôleur laser <-> BRIDGE-LASER <-> SDK <-> SERVER <-> sécurité indépendante
```

Le pont échoue en position sûre sauf si le contrôleur est au repos, la clé est
activée, l'enceinte fermée et l'interverrouillage sain selon le contrôleur.
Ces conditions sont des observations, jamais des substituts à une sécurité
laser certifiée.

## Compilation et test

Exécutez `build-test.bat` sous Windows ou `bash build-test.sh` sous Linux. Il
ne change pas la version et teste l'admission au repos sûr, le rejet de
l'enceinte et le transfert de l'annulation. Le choix du logiciel/contrôleur
laser réel est volontairement reporté jusqu'à disponibilité de la machine et
de son interface documentée.

## Projets associés

| Projet | Rôle |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | Contrat de sécurité partagé. |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | Limite de cellule autorisée. |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | Future preuve de zone. |

## État

La version `0.0.1` est un noyau local de planification sûr par défaut et
testé. Il n'a été ni connecté à un système laser ni utilisé pour le piloter.
