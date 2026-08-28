<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Puente de coordinación de celda láser
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 [English](README.md) | 🇪🇸 **Español** | 🇫🇷 [Français](README_fra.md) | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

🇺🇸 [English](README.md) | 🇪🇸 **Español** | 🇫🇷 [Français](README_fra.md) | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 [简体中文](README_zho.md) | 🇯🇵 [日本語](README_jpn.md)

Puente de alto nivel para celdas láser y auxiliares robóticos HYDRA-UMC.
Puede coordinar tareas periféricas seguras, como entrega de material, pero no
puede armar, disparar ni anular un controlador láser.

## Arquitectura

```text
Controlador láser <-> BRIDGE-LASER <-> SDK <-> SERVER <-> seguridad independiente
```

El puente falla de forma segura salvo que el controlador esté en reposo, la
llave esté habilitada, el recinto cerrado y el controlador informe de un
enclavamiento correcto. Estas condiciones son observaciones, nunca sustitutos
de una seguridad láser certificada.

## Compilación y prueba

Ejecuta `build-test.bat` en Windows o `bash build-test.sh` en Linux. No cambia
la versión y prueba la admisión en reposo seguro, el rechazo por recinto y el
reenvío de aborto. La elección del software/controlador láser real se aplaza
intencionadamente hasta disponer de la máquina y su interfaz documentada.

## Proyectos relacionados

| Proyecto | Función |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | Contrato de seguridad compartido. |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | Límite de celda autorizado. |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | Evidencia futura de zonas. |

## Estado

La versión `0.0.1` es un núcleo local de planificación segura por defecto y
probado. No se ha conectado ni utilizado para operar un sistema láser.

## ⚙️ Compilación con versión

`build-test.bat` / `build-test.sh` validan sin modificar el repositorio.
`build.bat` / `build.sh` ejecutan primero esa validación y, solo si es
correcta, sincronizan la versión nativa, el manifiesto y `CHANGELOG.md`. No
existe un comando `run` láser hasta validar una integración segura de control.
