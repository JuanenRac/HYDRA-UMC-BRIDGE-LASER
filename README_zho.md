<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - 激光单元协调桥接
Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

# HYDRA-UMC-BRIDGE-LASER

🇺🇸 [English](README.md) | 🇪🇸 [Español](README_spa.md) | 🇫🇷 [Français](README_fra.md) | 🇮🇹 [Italiano](README_ita.md) | 🇩🇪 [Deutsch](README_deu.md) | 🇨🇳 **简体中文** | 🇯🇵 [日本語](README_jpn.md)

面向激光单元和 HYDRA-UMC 机器人辅助设备的高级桥接。它可协调安全的外围任务，
例如材料交接，但不能武装、发射或绕过激光控制器。

## 架构

```text
激光控制器 <-> BRIDGE-LASER <-> SDK <-> SERVER <-> 独立安全系统
```

除非控制器处于空闲、钥匙已启用、防护罩已关闭且控制器报告联锁健康，否则桥接
默认安全拒绝。这些条件仅是观测，绝不替代经过认证的激光安全系统。

## 构建与测试

Windows 运行 `build-test.bat`，Linux 运行 `bash build-test.sh`。它不更改版本，
并测试安全空闲许可、防护罩拒绝和中止转发。真实激光软件/控制器的选择有意推迟
到机器及其文档化接口可用时。

## 相关项目

| 项目 | 作用 |
| --- | --- |
| [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) | 共享安全契约。 |
| [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) | 已授权的单元边界。 |
| [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES) | 未来的区域证据。 |

## 状态

版本 `0.0.1` 是本地、已测试且默认安全的规划核心。它尚未连接或用于操作激光系统。
