<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laser-cell coordination bridge
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 **English** | 🇪🇸 [Español](README_spa.md) | 🇫🇷 [Français](README_fra.md) | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

High-level bridge for laser cells and HYDRA-UMC robot auxiliaries. It can
coordinate safe peripheral tasks such as material hand-off, but it cannot arm,
fire or override a laser controller.

## Architecture

```text
Laser controller <-> BRIDGE-LASER <-> SDK <-> SERVER <-> independent safety
```

The bridge fails closed unless the controller is idle, the key is enabled, the
enclosure is closed and the controller reports a healthy interlock. Those
conditions are observations, never substitutes for certified laser safety.

## Build & Test

Run `build-test.bat` on Windows or `bash build-test.sh` on Linux. It performs
no version change and tests safe-idle admission, enclosure rejection and abort
forwarding. The choice of real laser software/controller is intentionally
deferred until the machine and its documented interface are available.

## Related Projects

| Project | Role |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | Shared safety contract. |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | Authorised cell boundary. |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | Future zone evidence. |

## Status

Version `0.0.1` is a local, tested fail-safe planning core. It has not been
connected to or used to operate a laser system.

## ⚙️ Versioned Build

`build-test.bat` / `build-test.sh` validate without modifying the repository.
`build.bat` / `build.sh` run that validation first and, only on success,
synchronize the native package version, manifest and `CHANGELOG.md`. There is
no live laser `run` command until a safe controller integration is validated.
