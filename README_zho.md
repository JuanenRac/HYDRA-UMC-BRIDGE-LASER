<!-- =============================================================================
HYDRA-UMC-BRIDGE-LASER - Laser cell coordination bridge
Copyright (C) JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
GPL-3.0-or-later - see LICENSE
============================================================================= -->

<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-BRIDGE-LASER banner" width="100%">
</p>

# 🔆 HYDRA-UMC-BRIDGE-LASER

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | 🇨🇳 <b>简体中文</b> | <a href="README_jpn.md">🇯🇵 日本語</a> | <a href="README_por.md">🇵🇹 Português</a></p>

### 🛑 面向激光单元的故障安全协调桥接

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python">
  <img src="https://img.shields.io/badge/Safety-Fails%20Closed-red.svg" alt="Safety">
  <img src="https://img.shields.io/badge/Tests-197%20passing-2ea44f.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-0.2.0-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-functional-0F6CBD.svg" alt="Maturity">
</p>

---

> **诚实检查——今天真正可运行的部分：** 四信号安全快照及其门控（`cell.py` 中的 `LaserSafetySnapshot`/`LaserCellBridge`，每个任务都会经过 `HYDRA-UMC-SDK` 自身真正的 `evaluate_job()`）、只读的证据归一化器（`observation.py`）、真正的 GPIO 联锁读取器（`gpio_safety.py` 中的 `GpioSafetyProbe`，libgpiod v2），以及 MQTT 状态/证据传输（`mqtt_transport.py`）都是真实的，并由 197 个通过的 `unittest` 用例覆盖（`python tools/build_test.py`），其中包括让该桥接对抗一个协议忠实但纯手写的 GPIO/MQTT 模拟器的 `tests/test_gpio_mqtt_emulator.py`。以上这些都从未接触过真实的 GPIO 芯片、真实的 MQTT broker 或真实的激光控制器——`test_gpio_safety.py` 读取的是一个伪造芯片，`test_mqtt_transport.py` 使用的是一个伪造的 broker 客户端。目前还没有具体的激光控制器/软件集成，因为相应的机器及其文档化接口尚不可用——详见下文的"当前状态与后续步骤"（已经如实说明了这一点），以及 `CHANGELOG.md` 中目前具体已交付的内容。 MQTT 传输层也已在开发机器上针对真实的 HYDRA-UMC-MQTT-BROKER 运行过(`tests/test_broker_integration.py`,未安装 broker 时会跳过):QoS 0、1、2 的发布与订阅、保留的可用性及其遗嘱消息,以及 broker 停止后重新启动时的恢复。

> **安全与安防现状:**本生态系统不是经认证的安全系统。目前尚无硬件 E-STOP 通路,没有由固件强制执行的限位或联锁,也没有经过验证的运动指令;固件映像使用 CRC-32 和 Ed25519 签名校验,发布构建会拒绝已公开的开发密钥(中继之后的工具头和扩展板仍运行 URTC 的引导程序,它们使用共享密钥的 HMAC-SHA256 而不是签名);TLS 与双向 TLS 均为可选项,默认关闭;自制电路板尚未组装或测试。在依赖此处任何说法来保障人身安全之前,请先阅读[安全基线](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/SECURITY_BASELINE.md)和[威胁模型](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/THREAT_MODEL.md)。

---

## 📋 速览

| | |
|---|---|
| 版本 | `0.2.0` |
| 成熟度 | 可用 |
| 测试 | 197 (`python tools/build_test.py`) |
| 技术栈 | Python / Laser controller / G-code / Safety evidence / GPIO interlock reading |
| 目标 | HYDRA-UMC 工作单元的 Raspberry Pi CM5 |
| 真实硬件 | 仅模拟：使用模拟器、替身或仿真测试；此版本没有在真实硬件上运行的记录 |

**跳转：** [概述](#-概述) · [架构](#-架构) · [功能](#-功能) · [安全与防护](#-安全与防护) · [接口](#-接口) · [配置](#-配置) · [快速开始](#-快速开始) · [测试](#-测试) · [故障排除](#-故障排除) · [仓库结构](#-仓库结构) · [相关项目](#-相关项目)

## 🚦 项目状态

每一行是本仓库的一个部分，灯号表示它今天做到了哪一步。内容依据仓库能够展示的证据（测试、构建、运行），而不是计划。

🟢 已完成并验证 · 🟡 可用，有已知限制 · 🟠 部分完成或尚未验证 · 🔴 未完成或不可用

| 领域 | 状态 | 在这里的含义 |
|---|---|---|
| 软件 | 🟡 | 主要用途可用；上面的诚实性检查列出了仍然缺少的内容 |
| 测试 | 🟢 | 197 项自动测试，每次变更都会运行 |
| 真实硬件 | 🟠 | 仅模拟：使用模拟器、替身或仿真测试；此版本没有在真实硬件上运行的记录 |
| 文档 | 🟢 | 八种语言的 README，每次变更都会与清单核对 |

## 🎯 概述

**HYDRA-UMC-BRIDGE-LASER** 是激光单元与 HYDRA-UMC 机器人辅助设备之间的高层桥接。它可以协调诸如物料交接之类的安全外围任务,但**绝不能**为激光控制器解锁、触发或越权操作——那些是它读取的观测量,而不是它拥有的权限。

它属于 **External Automation Bridges** 家族:一组共享 `HYDRA-UMC-SDK` 相同安全契约的兄弟仓库(CNC、LASER、OPENPNP、PRINTER3D、ROS2),因此任何一个桥接都不能自行发明"可以安全工作"的定义。

## 🧩 在 HYDRA-UMC 中的角色

**HYDRA-UMC-BRIDGE-LASER** 让机器人单元在激光切割机或雕刻机周围作业，却永远无法使激光待发或发射。它通过 GPIO 读取三个独立的安全装置（钥匙开关、机罩、联锁）以及 GRBL 激光控制器的状态，只有每个安全装置都显示安全的单元才会得到作业。

所有桥接都遵循 `HYDRA-UMC-SDK` 的共同安全契约：只有共用的 `evaluate_job()` 关口放行，任务才会被接受，而该关口在失败时保持关闭。父项目是 `HYDRA-UMC-SERVER`；本桥接不调用它，而是通过 `HYDRA-UMC-MQTT-BROKER` 以 MQTT 回应指挥该单元的一方。

## 🏛️ 架构

<p align="center">
  <img src="images/architecture.svg" alt="HYDRA-UMC-BRIDGE-LASER architecture" width="100%">
</p>

<details>
<summary>图表的文本版本（Mermaid）</summary>

```mermaid
flowchart LR
    LASER["激光控制器<br/>(状态、钥匙、防护罩、联锁)"] --> BRIDGE["BRIDGE-LASER<br/>LaserSafetySnapshot.machine_state()"]
    BRIDGE -- "BridgeJob + 观测到的 MachineState" --> SDK["HYDRA-UMC-SDK<br/>evaluate_job()"]
    SDK -- GateDecision --> RESULT["MQTT: cmd/job/result"]
```

</details>

**为什么这样构建**

* **为什么用三个独立的安全防护,而不是一个布尔值。** `LaserSafetySnapshot.machine_state()` 将 `key_enabled`、`enclosure_closed` 和 `interlock_healthy` 作为三个独立条件分别检查——真实的激光安全要求每一项物理防护都独立成立;把它们压缩成一个标志会掩盖到底是哪一项失效了。
* **为什么桥接会明确声明它绝不能为激光解锁或触发。** `LaserCellBridge` 自身的文档字符串写明它"只协调外部辅助设备;不能为激光解锁或触发"——这些条件是对控制器自身已认证联锁装置的观测,绝不是它们的替代品。
* **为什么控制器状态的映射被刻意设计得保守。** 只有字面字符串 `IDLE` 会被映射为 `MachineState.IDLE`。任何无法识别的值都会回落到 `OFFLINE`,绝不会回落到允许辅助工作的状态。
* **为什么桥接会构造一个新的 `BridgeJob` 并委托给共享的 `evaluate_job()`,而不是自己编写接受/拒绝逻辑。** 全部五个 External Automation Bridges(CNC、LASER、OPENPNP、PRINTER3D、ROS2)都复用 `HYDRA-UMC-SDK` 中完全相同的 `bridge_contract`,因此"什么才算安全到可以启动任务"不会在它们之间悄悄产生分歧。
* **为什么真实激光软件/控制器的选型被刻意推迟。** 在设备及其文档化的联锁上报机制就绪之前就绑定某个特定厂商的接口,等于宣称一个这个本地核心无法验证的真实安全保证。
* **它如何融入整个生态系统。** BRIDGE-LASER 位于激光控制器与 `HYDRA-UMC-SDK` → `HYDRA-UMC-MQTT-BROKER` → 独立安全系统之间:它协调围绕激光单元的辅助机器人工作,而不会取代或凌驾于已认证的激光安全系统之上。

这个观测辅助工具是证据规范化器,而不是激光控制器适配器:它不会打开任何网络或串口连接,不会更改设置、上传任务、进行武装或触发出光。[Laser Controller Evidence Boundary](docs/CONTROLLER_EVIDENCE_BOUNDARY.md) 定义了进行真实集成之前所需的验证。

**作为服务运行。** `python -m hydra_umc_bridge_laser --config /etc/hydra-umc/bridge-laser.toml` 从一个 TOML 文件启动桥接：GPIO 芯片和三条安全线路（线路、`active_low`、偏置、消抖）、GRBL 控制器的串口、MQTT 代理、单元状态的来源以及可选的辅助安全装置。未知的键会被拒绝，线路的极性没有默认值，所有情况都失败即关闭：没有控制器时读为 OFFLINE，单元状态文件缺失、未知或过期时为 `SAFE_STOP`。`--check` 校验该文件；`deploy/` 中有 systemd 单元（`Restart=on-failure`）和示例文件。它已针对模拟的 GPIO 和模拟的控制器运行，尚未在真实单元上运行。

## ✨ 功能

* ✅ **四信号安全快照(软件逻辑,未接激光器即完成测试):** `cell.py` 中的 `LaserSafetySnapshot.machine_state()` 要求钥匙开关启用、防护罩关闭**且**联锁状态健康这三者同时成立;只要缺少任何一项,甚至在读取 `controller_state` 之前就会解析为 `SAFE_STOP`。*(已实现,并在 `tests/test_cell.py` 中测试)*
* ✅ **真实的共享安全门控:** 每个被观察到的任务都会通过 `HYDRA-UMC-SDK` 的 `bridge_contract` 中的 `evaluate_job()` 重新评估,这与所有兄弟桥接使用的是同一个门控。*(已实现)*
* ✅ **保守的状态映射:** 只有 `IDLE` 被视为空闲;`RUN`/`RUNNING`/`PAUSED` 映射为 `RUNNING`,`FAULT`/`ALARM`/`ERROR` 映射为 `FAULT`,任何无法识别的值都会回落到 `OFFLINE`。*(已实现)*
* ✅ **只读安全证据:** `observation.py` 只接受钥匙、防护罩和联锁的真实布尔信号;缺失、数值型或文本型的值都会安全失效关闭。它既不能使激光武装,也不能触发激光。*(已实现,在 `tests/test_observation.py` 中测试)*
* ✅ **与控制器无关的 GPIO 联锁读取(仅针对模拟芯片测试):** `gpio_safety.py` 的 `GpioSafetyProbe` 从 GPIO 线路(libgpiod v2;测试使用模拟芯片)读取这 3 项独立防护,而不是依赖保存的映射——刻意做到与控制器无关,因为钥匙开关/门传感器/联锁继电器在各品牌激光切割机上都是通用的。GPIO 读取失败会使这 3 项防护全部安全失效关闭。*(已实现,在 `tests/test_gpio_safety.py` 中测试)*
* ✅ **边沿触发的联锁监控(仅针对模拟芯片测试):** `open_gpio_safety()` 只打开一次钥匙、防护罩和联锁这几条线(`INPUT`、`Edge.BOTH`),并用这唯一的请求同时服务电平读取器和边沿监视器——内核会拒绝对同一批线路的第二次请求。`watch_for_interlock_edges()` 阻塞等待内核自身的边沿事件通知(libgpiod v2),而不是仅在无关的 MQTT 消息提出请求时才重新读取电平;`run_forever(edge_watcher=...)` 会启动一个守护线程,在线路发生跳变的瞬间发布更新后的保留 `state`;若监视器失败,它会发布一个故障安全的 `state`(`SAFE_STOP`,附带原因)并继续重试。每条线的接线都需要声明(`GpioLineSettings`:`active_low`、`bias`——默认值会让断线被读为不安全——以及 `debounce_ms`);参见 `docs/WIRING_GUIDE.md`。尚未在真实 GPIO 芯片上验证。*(已实现,在 `tests/test_gpio_safety.py` 以及使用模拟 `gpiod` 的 `tests/test_hardening.py` 中测试)*
* ✅ **安全事件流(使用模拟线路和模拟边沿监视器测试):** `events.py` 把钥匙、机箱和互锁的每一次变化转成带时间戳的记录,发布到 `hydra/bridges/laser/event/safety`(数据湖用于审计和 OEE 的日志);当单元由安全变为不安全时,仅一次发布 `hydra/bridges/laser/event/interlock_open` 事件,列出已打开的保护,以便编排器立即停止单元的机械臂。两者均为 QoS 1 且从不保留;都带有 `at_ms` 和递增的 `sequence`;第一次读取只作为基准;边沿监视器失败时,该丢失同样作为互锁打开上报。该 bridge 只做上报:它无法停止激光器。*(已实现,在 `tests/test_events.py` 中测试)*
* ✅ **可选的辅助保护(使用模拟输入测试):** `auxiliary.py` 允许单元声明额外条件 —— 排烟运行中、辅助气开启、CO2 激光管温度不超过某一限值 —— 以 `AuxiliaryCheck` 传给 `LaserMqttBridge(auxiliary=...)`。只要有一项未满足,除 ABORT 之外的作业都会被拒绝,并指明失败的检查;无法读取、非数值或非有限的读数视为未满足;`state` 带有 `auxiliary` 映射。未声明时一切不变。只读:不切换任何东西。*(已实现,在 `tests/test_auxiliary.py` 中测试)*
* ✅ **非变更式构建/测试:** `build-test.bat`/`.sh` 编译源码并运行安全门控测试套件,不会触碰版本文件或 CHANGELOG。*(已实现,见下方"构建与发布")*
* ✅ **GRBL 激光状态读取器(仅针对模拟板卡测试):** `grbl_state.py` 的 `GrblLaserState` 是串口上 GRBL 系列激光控制器(LaserGRBL 和 LightBurn 驱动的那类板卡)的真实 `controller_state`:它发送 GRBL 的状态查询 `?`,并返回报告中的状态词。它刻意只读——唯一写出的字节是 `?`,没有暂停、复位、恢复或 G 代码——并且失效即关闭(没有应答就是空状态,绝不是空闲)。串口、可重连的连接和解析器是 CNC 桥接也使用的 SDK 共享串口连接。报告中的激光功率和进给作为信息放入 `state`(`laser_power`、`feed_rate`),绝不作为安全保护。GRBL 板卡只有一个串口:LightBurn 或 LaserGRBL 占用它时,此读取器无法使用。*(已实现,尚未在真实板卡上试过)*
* 🔜 **具体的激光控制器/软件集成** —— 刻意推迟,直到设备及其文档化接口就绪。*(计划中)*
* ✅ **重复的幂等键：** `LaserMqttBridge` 接受 `IdempotencyStore`：重复的作业键会得到第一次给出的答复，而不是被重新评估。*（已实现，已在 `tests/test_idempotency.py` 中测试）*
* ✅ **加固的 MQTT 循环与故障安全读取:** 过大(超过 16 KiB)或无法读取的负载、深度嵌套的 JSON 以及任何意外故障,都会在结果主题上得到拒绝回复,绝不会终止循环;`cmd/job` 的回复带有 `"mode": "gate-only"`,通过它发出的 ABORT 会说明没有停止任何东西(停止激光的是物理急停);状态带有 `observed_at`,桥接在带遗嘱(Last Will)的 `availability` 主题上宣告自己;读取 GPIO 线路时的任何异常——不只是 `OSError`——都会使三个保护装置全部判为失败,三个电平在锁的保护下一次操作读出;能理解 `Hold:0`、`Alarm:1`、`Door:1`、`Jog`、`Home` 等 GRBL 风格的控制器状态。*(已实现,在 `tests/test_hardening.py` 中测试)*
* ✅ **作业经由共享的受理环节:** 对格式错误的作业和重复的 `idempotency_key` 的检查，由 SDK 的 `JobIntake` 完成，而不是此桥接自己的代码(键不再带 `job:` 前缀)。
* ✅ **以 QoS 1 发布的响应:** 对命令的响应以 QoS 1 发布(共享调度器会保留桥接给响应指定的 QoS)，因此在不稳定的链路上结果不会丢失。
* ✅ **跟随全局停止（默认关闭）:** 设置 `HYDRA_UMC_LASER_GLOBAL_STOP=1` 后，桥接读取服务器在 `hydra/swarm/safety/estop` 上的保留通知；通知为 `SAFE_STOP` 或无法读取时，它会带原因拒绝：任务（中止放行）。停止命令和只读请求照常工作，只有 `READY` 才能解除拒绝。*（已实现，已对真实代理测试；从未与真实服务器一起运行）*

## 🔒 安全与防护

| 威胁 | 防御 | 位置 |
|---|---|---|
| 对处于不安全状态的单元或机器下达任务 | 每个任务都经过 SDK 共用的 `evaluate_job()` 关口，该关口失败时保持关闭；桥接本身没有接受/拒绝逻辑 | SDK `bridge_contract` |
| 过大的任务数据 | 最多 32 个参数，键最长 64 个字符，值最长 1024，标识符最长 128（`MAX_PARAMETERS`、`MAX_PARAMETER_KEY_CHARS`、`MAX_PARAMETER_VALUE_CHARS`、`MAX_IDENTIFIER_CHARS`） | SDK `bridge_contract` |
| 重复或重放的命令 | `IdempotencyStore` 将每个键记住 24 小时、最多 10 000 条；重复请求得到第一次的答复而不是重新评估 | SDK `job_intake` |
| 巨大或恶意的 MQTT 负载 | 超过 16 KiB 的负载、不可读或嵌套过深的 JSON 以及任何意外故障，都会在结果主题上得到拒绝答复，且不会终止循环 | `mqtt_transport.py` |
| 激光被误置于待发状态 | 三个独立的安全装置（`key_enabled`、`enclosure_closed`、`interlock_healthy`）必须全部显示安全；只有控制器状态恰为 `IDLE` 才算空闲，其他一律为 `OFFLINE` | `cell.py`, `events.py` |
| 被剪断的联锁线 | 默认偏置使断线被读为不安全（低电平有效用上拉，高电平有效用下拉），触点抖动默认忽略 10 ms，三条线互不相同 | `gpio_safety.py` |
| GPIO 读取失败 | 保留的 `state` 会带着原因变为失败即关闭（所有安全装置均未满足，`SAFE_STOP`），避免有人继续读取旧的良好状态 | `mqtt_transport.py` |
| 重连时被重放的保留命令 | 保留的 `cmd/` 消息在重连时被忽略 | `mqtt_transport.py` |

**它绝不做的事：** 它只协调外部辅助设备：不能使激光待发或发射，对 GRBL 控制器也只发送状态查询。

## 🔌 接口

位于 `hydra/bridges/laser/` 下的主题；没有停止动词（`STOP_VERBS` 为空）。

| 主题或路由 | 内容 |
|---|---|
| `cmd/status` | 空负载：重新读取三条 GPIO 线并发布状态 |
| `cmd/job` → `cmd/job/result` | JSON 格式的 `BridgeJob`；只做规划，答复是 `GateDecision` |
| `state`, `availability` | 带时间戳的保留快照，以及 `online`/`offline` |
| `event/safety`, `event/interlock_open` | 安全装置变化时的 QoS 1 事件，不保留 |

库：`LaserCellBridge`、`LaserSafetySnapshot`、`LaserMqttBridge`、`GpioSafetyProbe`、`open_gpio_safety()`、`GrblLaserState`、`open_grbl_laser_state()` 和 `AuxiliarySupervisor`（排烟、辅助气、CO2 管温度）。

## ⚙️ 配置

| 变量 | 默认值 | 设置内容 |
|---|---|---|
| `GpioLineSettings.active_low` | 必填 | 信号在逻辑 0 时为安全则取 `True`（接地的常闭触点） |
| `GpioLineSettings.bias` | 故障安全 | `pull-up`、`pull-down`、`disabled` 或 `as-is`；未设置时选择使断线被读为不安全的那种 |
| `GpioLineSettings.debounce_ms` | `10.0` | 在此时间内忽略触点抖动；`0` 关闭，负值被拒绝 |
| `HYDRA_UMC_LASER_GLOBAL_STOP` | 关闭 | `1` 跟随服务器的全局停止：只要保留主题 `hydra/swarm/safety/estop` 上最新的通知是 `SAFE_STOP`（或无法读取），桥接就会带原因拒绝：任务（中止放行）；只有 `READY` 才能解除。`HYDRA_UMC_LASER_GLOBAL_STOP_TOPIC` 可更改主题，`HYDRA_UMC_LASER_GLOBAL_STOP_STRICT=1` 会在收到第一条通知之前也拒绝 |
| `HYDRA_MQTT_USERNAME` | 无 | MQTT 用户名；代理将其绑定到客户端 ID 前缀 |
| `HYDRA_MQTT_PASSWORD` | 无 | 密码；只能与用户名一起使用 |
| `HYDRA_MQTT_PASSWORD_FILE` | 无 | 从文件读取的密码（Docker 或 systemd 机密）；设置了 `HYDRA_MQTT_PASSWORD` 时忽略 |
| `HYDRA_MQTT_TLS_CA` | 无 | 签署代理证书的 CA 文件：连接使用 TLS 并验证证书 |
| `HYDRA_MQTT_TLS` | 关闭 | `1` 启用 TLS，并用系统信任的 CA 验证 |
| `HYDRA_MQTT_TLS_CERT` / `HYDRA_MQTT_TLS_KEY` | 无 | 用于要求双向 TLS 的代理的客户端证书及其密钥；两者都需要 |

三条 GPIO 线的偏移和芯片是 `open_gpio_safety()` 的参数；GRBL 控制器的串口设备是 `open_grbl_laser_state()` 的参数（默认 115200 波特，超时 1 秒）。

## 🚀 快速开始

需要 Python 3.11 或更高版本。测试和构建脚本期望 `HYDRA-UMC-SDK` 位于本仓库旁边（`../HYDRA-UMC-SDK`），或由 `HYDRA_UMC_SDK_ROOT` 指定。

无需硬件即可试用（用模拟器和替身检查整个桥接）：

```bash
py -3 tools/build_test.py          # Windows
python3 tools/build_test.py         # Linux, macOS
```

启动服务（没有控制台脚本：服务就是 MQTT 传输的 `run_forever()`，由你自己的启动代码调用）：

```python
from hydra_umc_bridge_laser.gpio_safety import GpioLineSettings, open_gpio_safety
from hydra_umc_bridge_laser.grbl_state import open_grbl_laser_state
from hydra_umc_bridge_laser.mqtt_transport import LaserMqttBridge, run_forever
wiring = GpioLineSettings(active_low=True)                       # normally-closed contacts to ground
safety = open_gpio_safety("/dev/gpiochip0", 17, 27, 22, key=wiring, enclosure=wiring, interlock=wiring)
bridge = LaserMqttBridge(safety.lines, controller_state=open_grbl_laser_state("/dev/ttyUSB0"), cell_state=lambda: cell_state)
run_forever(bridge, host="192.168.0.180", edge_watcher=safety.watcher)   # serves cmd/# and publishes the events
```

用户名、密码和 TLS 文件来自 `HYDRA_MQTT_*` 变量（见“配置”）；上面的代码本身不需要凭据。

## 🧪 测试

运行 `python tools/build_test.py` 会执行 197 个自动 `unittest` 用例（同时编译每个模块）。测试不需要硬件、网络或可选软件包：需要 `paho-mqtt`、`pyserial` 或厂商库的用例使用替身，缺少软件包时则跳过。

| 测试文件 | 测试数 | 覆盖内容 |
|---|---|---|
| `test_global_stop.py`, `test_global_stop_broker.py` | - | 全局停止的守卫及其附带原因的拒绝，以及在空闲本地端口上对真实代理的同样测试（QoS 0、1、2 的通告，连接时遵从保留的停止，无法读取的通告按故障关闭处理） |
| `test_broker_integration.py`, `broker_harness.py` | - | 在空闲本地端口上对真实 HYDRA-UMC-MQTT-BROKER 的 MQTT 客户端测试：通过客户端下发的指令、保留状态与遗嘱，以及代理掉线再恢复后的回路；缺少 Node.js、`paho-mqtt` 或已安装的代理（`HYDRA_UMC_TEST_BROKER_DIR`，默认是相邻文件夹）时会自动跳过 |
| `test_cell.py`, `test_observation.py`, `test_events.py`, `test_auxiliary.py` | - | 安全装置、证据、事件和辅助检查 |
| `test_gpio_safety.py`, `test_gpio_mqtt_emulator.py`, `gpio_mqtt_emulator.py` | - | 针对假线路的 GPIO 读取器；真实桥接对 GPIO 与 MQTT 夹具 |
| `test_grbl_state.py` | - | GRBL 读取器对以 GRBL 方式应答的内存控制器（横幅、`ok`、过期答复） |
| `test_mqtt_transport.py`, `test_mqtt_environment.py`, `test_hardening.py`, `test_edge_cases.py`, `test_idempotency.py` | - | 主题分发、环境凭据、恶意客户端、异常读数和重复键 |

CI 运行 `HYDRA_UMC_CI=1 python tools/ci_validate.py`，检查清单、文档、八个 README 和图片，并使用 SDK 副本运行测试。

## 🏗️ 构建与发布

需要 Python 3.11+。`tools/build_test.py` 期望 `HYDRA-UMC-SDK` 作为兄弟目录被检出(`../HYDRA-UMC-SDK`),或通过环境变量 `HYDRA_UMC_SDK_ROOT` 指定。

```bash
# Windows
build-test.bat      # 仅验证 —— 不改变版本/CHANGELOG
build.bat            # 先验证,成功后更新版本 + CHANGELOG

# Linux/macOS
bash build-test.sh
bash build.sh
```

`build-test` 使用 `py_compile` 编译 `src/`和`tools/` 下的每个模块,并运行在 `tests/` 下发现的完整 `unittest` 套件(`test_cell.py`、`test_observation.py`、`test_gpio_safety.py`、`test_mqtt_transport.py`、`test_gpio_mqtt_emulator.py`、`test_hardening.py`、`test_idempotency.py`、`test_mqtt_environment.py`——共 197 个测试),证明安全空闲准入、防护罩拒绝和中止转发等均按预期工作 —— 它绝不会修改仓库。`build` 会先运行同样的验证,只有成功后才调用 `tools/bump_version.py`,在 `pyproject.toml`、`hydra-umc.project.json` 和 `CHANGELOG.md` 之间同步版本号。目前尚无真正的激光 `run` 命令 —— 这需要经过验证且安全的控制器集成。

## 🩺 故障排除

| 你看到 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: hydra_umc_sdk` | 未安装 SDK，且不在本仓库旁边 | 把 `HYDRA-UMC-SDK` 克隆到本仓库旁边，或设置 `HYDRA_UMC_SDK_ROOT` |
| `paho-mqtt is not installed` | MQTT 客户端是可选附加包 | `pip install ".[mqtt]"`（需要 `paho-mqtt` 2.1 或更高，低于 3） |
| `password was given without a username` | MQTT 凭据需要两部分 | 除密码外还要设置 `HYDRA_MQTT_USERNAME` |
| `could not reach the MQTT broker after N attempts` | 代理未运行、地址错误或端口已关闭 | 启动 `HYDRA-UMC-MQTT-BROKER`，检查传给传输层的主机和端口（每隔 2 秒试 5 次；TLS 握手失败不会重试） |
| `the MQTT broker refused the connection` | 代理拒绝了凭据（或未在时限内应答） | 检查 `HYDRA_MQTT_USERNAME` 和密码；客户端 ID 必须以代理绑定到该凭据的前缀开头 |
| `state` with every safeguard unsatisfied and `SAFE_STOP` | GPIO 读取失败（缺芯片、权限、请求已释放）或边沿监视器已停止 | 查看保留的 `state` 中的原因；检查芯片路径、线偏移和运行服务的用户权限 |
| `"allowed": false` + `reason` | 共用关口或某项保护拒绝了命令 | 阅读 `reason` 并排除原因；不要盲目重试 |

## 📂 仓库结构

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of HYDRA-UMC-BRIDGE-LASER" width="100%">
</p>

<details>
<summary>目录树的文本版本</summary>

```text
HYDRA-UMC-BRIDGE-LASER/
├── src/hydra_umc_bridge_laser/
│   ├── cell.py                    除非安全装置报告安全空闲，否则拒绝作业
│   ├── gpio_safety.py             通过 GPIO（libgpiod）读取三条安全线
│   ├── grbl_state.py              GRBL 控制器状态；只做状态查询
│   ├── observation.py             本地安全证据，绝不是激光命令
│   ├── events.py                  安全装置变化时生成带时间戳的事件
│   ├── auxiliary.py               排烟、辅助气和管温检查
│   └── mqtt_transport.py          MQTT 命令、状态与事件传输
├── tests/                         149 项测试（含 GPIO 与 MQTT 模拟器）
├── deploy/                        systemd 单元和示例配置
├── docs/                          桥接指南、证据边界、接线指南
├── tools/                         构建与测试运行器、版本提升、CI 校验、README 与图片的生成和检查
├── images/                        横幅图与 README 的图片
├── .github/                       CI 工作流和 Issue 模板
├── pyproject.toml                 包元数据与依赖
├── hydra-umc.project.json         清单：版本、成熟度、系列
├── CHANGELOG.md                   每个版本的变化
├── build.sh build.bat             构建脚本（从不改变版本）
├── build-test.sh build-test.bat   构建脚本（从不改变版本）
├── test.sh test.bat               运行测试
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE LICENSE.md
```

</details>

## 🗺️ 路线图与已知限制

**当前已知限制**

**目前真实的部分:** 版本 `0.2.0`,一个已在本地测试过的故障安全规划核心(`LaserSafetySnapshot` + `LaserCellBridge`),依托 `HYDRA-UMC-SDK` 的共享任务门控,包含严格的只读安全证据标准化,能区分真正暂停的任务(`HOLDING`)与真正正在切割的任务(`RUNNING`),一个真实的、与控制器无关的 GPIO 联锁读取(`GpioSafetyProbe`),覆盖钥匙/外壳/联锁这 3 项独立防护,一个真实的 MQTT 状态/证据传输(`mqtt_transport.py`),配有确定性的197项 `unittest` 测试套件,以及已接入 CI 并带 SDK 检出的非变更式 build-test 脚本。

**集成边界:** 激光控制器自身已认证的防护罩、钥匙开关和联锁权限从不被绕过;本桥接只负责围绕它门控*辅助*机器人工作,且仅通过读取其上报的状态。

**仍待完成:** 本桥接尚未连接或用于操作真实的激光系统 —— 选择并验证具体的控制器/软件接口被推迟到设备及其文档化接口就绪之后。

## 🌍 语言

本 README 和仓库文档提供八种语言：英语、西班牙语、德语、法语、意大利语、日语、中文和葡萄牙语（葡萄牙）。它们同时编写，并由 CI 检查八个文件拥有相同的章节和相同的链接。 本仓库没有自己的界面或消息目录，因此没有需要翻译的界面文字。

## 🔗 相关项目

本项目是同一作者(JuanenRac / Electro Hobby 3D)打造的 HYDRA-UMC 机器人生态系统的一部分。值得了解,因为某个请求实际上可能是关于这些项目之一,而非本仓库本身。

**父项目**
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — 每个控制客户端真正通信的真实无头后端(REST/WebSocket);本桥接不会调用它,而是通过 HYDRA-UMC-MQTT-BROKER 以 MQTT 回应指挥单元的一方。

**兄弟项目** —— 同样与 HYDRA-UMC-SERVER 自身 API 通信,各自作为独立客户端
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — 具有实时多机器人 3D 可视化的网页控制面板。
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — 面向多台服务器的桌面(PySide6)集群指挥中心，打包为独立可执行文件。
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — 具有生物识别登录和配对 Wear OS 伴侣应用的原生 Android 控制应用。
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — 具有实时 WebSocket 同步的 iOS/iPadOS 控制应用(Flutter)。
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — 面向机载 7 英寸 DSI 触摸屏的原生触控界面，直接嵌入 CM5 本体。
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — 通过 VDA 5050 MQTT 发布者为 AGV/AMR 车队提供的协调边界(仅针对仿真车队测试)。
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — 具备 GRBL 状态/控制字节访问能力的高层 CNC 单元协调器(仅针对模拟器测试)。
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — 面向足式/人形机器人的协调边界,带有 Boston Dynamics Spot 指令发送器(仅针对模拟器测试)。
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — 面向 OpenPnP 贴片机板级流程的安全高层协调器。
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — 面向 Moonraker/Klipper 3D 打印机的安全协调边界，具备真实的受控作业指令。
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — 带有惰性导入 rclpy ROS 2 传输层的协调器(尚未在 ROS 2 环境中运行)。
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — 面向搭载摄像头的无人机的协调边界,带有 MAVLink 指令发送器(仅针对模拟器测试)。

**直接相关**
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — 每个桥接都据此校验自身指令的共享 JSON-Schema 契约与软件作业门限边界(并非经认证的安全功能)。
- **[HYDRA-UMC-CONNECTOR-HUB](https://github.com/JuanenRac/HYDRA-UMC-CONNECTOR-HUB)** — 面向外部机器连接器的声明式适配器清单注册与校验工具；把 SDK 自身的契约理念扩展到外部机器，而不取代工业网关类项目。
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — `mqtt_transport.py` 为本桥接自身 `hydra/bridges/laser/...` 主题提供的真实传输——仅安全防护状态,因为这里不存在任何真实的驱动指令(本桥接无法对激光器进行武装或触发);详见该仓库自身的 `docs/BRIDGE_TOPICS.md`。
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — 面向本桥接的未来单元区域安全验证。

**生态系统中的其他项目**

*核心硬件与平台*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — 机器人手臂主板设计——CM5 主机 + 双核 STM32H745,目标是通过 CAN-OTA/SPI-OTA 协调最多 8 条工具臂(固件处于早期阶段,尚无已组装的电路板)。
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — 面向 CM5 的可复现 Raspberry Pi OS 产品层——只读代理、经过验证的配置/配置文件、WiFi 首次配网。

*核心后端与客户端*
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — 将完成的模型推送到 STUDIO 自身目录的桌面版图形化 URDF 创建/编辑工具。
- **[HYDRA-UMC-EDITOR-STL](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-STL)** — 桌面 STL 模型编辑器，在 HYDRA-UMC-EDITOR-URDF 编辑的同一模型目录中变换/替换/移除/添加真实部件。

*URTC 工具平台*
- **[URTC](https://github.com/JuanenRac/URTC)** — 面向实体 Universal Robot Tool Controller 板卡的固件，通过 CAN 总线支持 25 种以上工具配置。
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — 面向 URTC 板卡的桌面图形烧录工具，支持 CAN-OTA 以及全芯片 SWD/JTAG。
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — 面向 URTC 板卡的桌面实时 CAN 总线诊断工具，每种工具配置对应一个面板。
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — 通过 Web Serial API 实现的浏览器版 URTC-TESTER 替代方案，无需本地安装。
- **[URTC-GATEWAY](https://github.com/JuanenRac/URTC-GATEWAY)** — URTC CAN 总线前的网关：允许的标识符列表、速率限制和会话密钥；软件已在计算机上测试，尚未在真实总线上测试。

*视觉 AI 节点(Hailo-8)*
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — 面向 Hailo-8 视觉流水线的集成中枢，具备逐阶段的真实硬件就绪检测。
- **[HYDRA-UMC-DETECTION-HEF](https://github.com/JuanenRac/HYDRA-UMC-DETECTION-HEF)** — 具备 Hailo 架构/校验和安全加载验证的真实编译模型注册表。
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — 具备真实 HailoRT 集成边界的真实 GStreamer 流水线 + MediaMTX 配置生成器。
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — 以区域状态为授权条件的 Position-Based Visual Servoing 修正律;尚无摄像头位姿估计。

*认知 AI 节点(Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — 面向 Hailo-10 认知流水线(LLM/VLA/语音编排)的集成中枢。
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — 面向 Vision-Language-Action 模型的真实动作 token 编解码与轨迹生成。
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — 具备受限、需确认的 Watch 中继的真实语音前端(VAD + 意图解析)。
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — 基于真实规则的任务分解，以及针对 MCU 错误码的语义化错误恢复。
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — 面向本生态系统自身 Markdown 文档的真实纯标准库 TF-IDF 文档检索。
- **[HYDRA-UMC-LOCAL-TECHNICIAN](https://github.com/JuanenRac/HYDRA-UMC-LOCAL-TECHNICIAN)** — 面向生态系统自身的本地、按策略门控的 AI 维护技师——观察、诊断并提出修复建议;两个最高风险等级目前特意尚未实现。

*编排与集群*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — 具备真实 gRPC/Protobuf 健康报告契约与任务状态机的集成中枢。
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — 基于真实 HTTP API 的真实优先级任务队列，支持去重。
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — 具备重试/退避与身份不匹配检测的真实基于 gRPC 的车队健康看门狗。
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — 具备真实障碍物/工作空间碰撞校验的真实基于 RRT 的三维路径规划器。
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — 经过多单元收敛属性测试的真实 CRDT LWW-Element-Map 状态同步。

*数字孪生与仿真*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — 面向数字孪生引擎的集成中枢，具备真实的版本兼容性同步契约。
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — 在仿真与真实硬件之间带有软件碰撞联锁的硬件在环路由器(未在真实硬件上测试)。
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — 面向真实 URDF 子集的真实正向运动学与关节限位校验。
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — 具备 YOLO/COCO 标注导出功能的真实程序化 2D 场景生成器。

*数据与分析*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — 具备真实数据摄入/查询 HTTP API 的真实 sqlite3 时序数据存储。
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — 具备漂移监测能力的真实 FFT + 统计基线异常检测器。
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — 基于 DATALAKE 历史数据的真实 OEE/可用率计算，支持可复现的 CSV 导出。
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — 面向 DATALAKE 的真实 CAN/WebSocket 数据摄入管道，支持序列去重。

*工业网关*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — 中继至工业协议的集成中枢，具备真实的指令白名单/背压控制层。
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — 经真实二进制协议客户端会话验证的真实 OPC-UA 地址空间。
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — 具备降级模式输出的真实 MTConnect `/probe` 与 `/current` XML 端点。

*辅助工具与生态系统运维*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — 基于 DATALAKE/ANOMALY-DETECTOR 的智能摘要与异常高亮面板，具备诚实的统计回退机制。
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — 具备真实、稳定退出码契约的车队 CLI，是 HYDRA-UMC-SERVER 自身 API 的真实在线客户端。
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — 带有触觉提醒模式与配对手机语音中继的 WearOS 伴侣应用(尚未在实体手表上运行)。
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — 面向板卡安装机架的固件，具备真实的工具 ID 解码与 Smart Idle 预热逻辑。
- **[URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)** — 面向热成像/RGB 检测工具头的固件及真实 Python 视觉伴侣程序。
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — 发现、克隆并更新本生态系统中每个仓库的管理类桌面工具。
- **[HYDRA-UMC-OS-REBUILDER](https://github.com/JuanenRac/HYDRA-UMC-OS-REBUILDER)** —— 构建即刻可烧录、预装生态系统最新版本的 CM5 镜像的 Windows/Linux 桌面工具,具备类似 Raspberry Pi Imager 风格的首次启动 Wi-Fi/用户/SSH 配置。
- **[HYDRA-UMC-OPS-AGENT](https://github.com/JuanenRac/HYDRA-UMC-OPS-AGENT)** — 维护事件协调器：一个低权限的边缘角色采集经过脱敏的库存/健康快照，一个控制面角色以只读方式渲染它，并请求某个 AI 提供方给出诊断建议——从不应用补丁，也从不部署任何内容。
- **[HYDRA-UMC-DEV-SERVER](https://github.com/JuanenRac/HYDRA-UMC-DEV-SERVER)** — 可复现的开发主机（Raspberry Pi 5 / CM5），保存整个生态系统的源代码，并在持久队列下运行有界的构建/测试任务；这是专用的开发角色，明确区别于运行中的 CM5。

## 📚 文档

更多阅读：

* [docs/BRIDGE_GUIDE.md](docs/BRIDGE_GUIDE.md) - 范围、GPIO 接线设置、GRBL 读取器、脚本
* [docs/WIRING_GUIDE.md](docs/WIRING_GUIDE.md) - 三个安全信号如何接线
* [docs/CONTROLLER_EVIDENCE_BOUNDARY.md](docs/CONTROLLER_EVIDENCE_BOUNDARY.md) - 什么算真实的安全证据
* [生态系统的安全基线](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/SECURITY_BASELINE.md)
* [生态系统的威胁模型](https://github.com/JuanenRac/HYDRA-UMC-DOCS/blob/main/docs/THREAT_MODEL.md)
* [本仓库的更新日志](CHANGELOG.md)
* [本仓库的许可证](LICENSE.md)

## 🤝 参与贡献与社区

* 提交 pull request 之前，请运行 `HYDRA_UMC_CI=1 py -3 tools/ci_validate.py`（或 `HYDRA_UMC_CI=1 python3 tools/ci_validate.py`）：它必须输出 `CI_VALIDATION=PASS`。此检查不要运行 `build.sh` 或 `build.bat`；构建不是检查。
* 八个 README 由 HYDRA-UMC-DOCS 中的同一个源生成；请勿手工编辑。修改源文件，再用 `tools/make_readmes.py` 重新生成。
* 不要在 README 中声称尚未运行过的内容：属实时请写“仅模拟”或“尚未在硬件上试过”。
* 请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)、[行为准则](CODE_OF_CONDUCT.md)、[SECURITY.md](SECURITY.md) 和 [SUPPORT.md](SUPPORT.md)。

## 👤 作者

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 许可证

GPL-3.0-or-later - [LICENSE](LICENSE).
