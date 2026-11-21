# Minecraft Mod Studio 全系统工程审计（第一轮）

- 审计日期：2026-11-21
- 审计范围：仓库主线、V2.5 工程验收、AI Debug Lab、Structure Studio、Extension Engine、Horizon 预研，以及相关 CI / PR 集成状态。
- 审计基线：
  - `main`: `8e8703875131c60b3bf2440c2dd8f44ae8c616a9`
  - `v2.5-engineering-acceptance`: `1d98eed578f87b65b0fa14c1aa666b327880671e`
  - `ai-debug-lab-v0.1`: `092f5656c51ea66016ee313630ec1807c49e2255`
  - `feature/ai-debug-cache-lifecycle-v0.12.4`: `7c655e3082ac626948c64982398cd529ae1e64ab`
  - `feature/ai-debug-startup-phase-timings-v0.12.5`: `b8b59afa68eb8369505128526f0fc282f27b2ddb`
  - `feature/structure-studio-v0.1`: `3448969fe5874a6a73304c21e2e581960d7fa980`
  - `research/extension-engine`: `d0e633fd54ec9f3962447ac9177f21ad2a4df5f8`
  - `research/horizon-adapter`: `1917f28e7957ca2dc4b1a6bb368411731f60edc1`

## 1. 审计结论

系统已经具备若干可信的工程基础：V2.5 可以生成并编译 Fabric 工程；资源导入有路径、类型、大小和 CRC 等限制；AI Debug Lab 能在 Windows/Linux CI 中启动真实的隔离 Fabric 测试服务端；Structure Studio 有确定性生成、NBT/数据包导出和浏览器验收；扩展引擎已设计内容寻址、事务与回滚。

但当前仓库仍是**多个成熟度不同的研发分支集合**，不能视为一个已集成、可对任意整合包安全测试的完整产品。当前最重要的两个门槛：

1. **安全门槛：** 在允许 AI Debug Lab 执行用户或第三方模组之前，必须增加操作系统级隔离。临时世界、回环网络和 RCON 密码并不构成进程沙箱。
2. **产品验证门槛：** 源码生成、JAR 编译、结构 NBT/数据包生成、模拟测试和真实 Minecraft 游戏行为必须分别验收。现有报告明确保留了多项尚未完成的真实游戏验证。

本报告是第一轮工程审计，不是完整的渗透测试，也不是对所有源文件逐行形式化验证。未检查的部分在相应条目中标记为待审计，不推定安全或正确。

## 2. 当前系统分区与证据

| 子系统 | 当前可确认状态 | 尚未证明的能力 |
|---|---|---|
| V2.5 主制作器 | 单文件 HTML/JS；Playwright、源码导出和真实 Fabric Gradle 构建验收已建立；CI 报告 Build Doctor 检查 46 个预期 JAR 条目 | Minecraft 客户端启动、渲染和游戏内行为 |
| 资源库与跨模组适配 | JAR/ZIP 静态解析、来源记录、资源暂存、迁移/兼容分析；有独立浏览器和构建验收 | 第三方许可真实性、所有复杂资源格式及所有模组依赖语义 |
| AI Debug Lab | MCP/stdio 接口；只读诊断与受限写操作；临时 Fabric 服务端；缓存、校验和清理逻辑 | 任意整合包、任意模组组合、客户端/多人/GUI/世界生成的通用测试 |
| Structure Studio | 生成结构 NBT 和 Java 26.2 数据包；Playwright 与大量确定性断言通过 | 红石陷阱、交互实体、钥匙门、自然生成等真实游戏行为 |
| Extension Engine | V0.6 数据型扩展包管理、权限声明、依赖、内容寻址、事务、回滚和恢复逻辑 | 真实 IndexedDB 浏览器事务、跨标签竞争、UI 集成、签名与发布者信任 |
| Horizon Adapter | H0 研究、上游接口调查、实验规范和合成追踪工具 | SDK 实际运行、目标游戏加载、行为等价性；当前不是生产适配器 |

关键文档：
- [V2.5 工程验收说明](https://github.com/tortletortle/minecraft-mod-studio/blob/1d98eed578f87b65b0fa14c1aa666b327880671e/docs/V25_ENGINEERING_AUDIT.md)
- [V2.5 客户端验收边界](https://github.com/tortletortle/minecraft-mod-studio/blob/1d98eed578f87b65b0fa14c1aa666b327880671e/docs/V25_CLIENT_ACCEPTANCE.md)
- [AI Debug Lab 运行与安全边界](https://github.com/tortletortle/minecraft-mod-studio/blob/7c655e3082ac626948c64982398cd529ae1e64ab/ai-debug-lab/AI_PLAYTEST.md)
- [AI Debug Lab 缓存边界](https://github.com/tortletortle/minecraft-mod-studio/blob/7c655e3082ac626948c64982398cd529ae1e64ab/ai-debug-lab/RUNTIME_CACHE.md)
- [Structure Studio 验收与未完成事项](https://github.com/tortletortle/minecraft-mod-studio/blob/3448969fe5874a6a73304c21e2e581960d7fa980/structure-studio/README.md)
- [Extension Engine V0.6 报告](https://github.com/tortletortle/minecraft-mod-studio/blob/d0e633fd54ec9f3962447ac9177f21ad2a4df5f8/research/extension-engine/V06_REPORT.md)
- [Horizon H0 研究章程](https://github.com/tortletortle/minecraft-mod-studio/blob/1917f28e7957ca2dc4b1a6bb368411731f60edc1/docs/research/RD-001-horizon-adapter.md)

## 3. 主要审计发现

### F-01 — P0（面向不可信模组测试的发布阻断）：Java 模组执行尚无 OS 级沙箱

**观察事实**
- AI Debug Lab 通过子进程启动 Java/Fabric 服务端，并在临时目录创建测试世界。
- 服务端绑定回环地址，RCON 凭据由测试运行生成；MCP 工具的写操作范围受限。
- 当前真实 MCP CI 使用的是项目自己的测试模组与固定测试资产。
- 当前实现没有证据表明 Java 进程运行在 Windows Sandbox、独立 VM、受限容器或低权限隔离账户中。

**风险判断**
Minecraft 模组 JAR 是可执行 Java 代码。若将任意用户/第三方模组装入当前测试进程，它们原则上会继承启动该 Java 进程的操作系统用户权限。临时世界只隔离游戏数据，不隔离文件系统、网络、凭据和其他本机资源。

**要求**
在支持不可信/来源不明整合包前，必须采用 OS 级隔离：一次性 VM 或等价隔离环境、非特权账户、仅挂载测试副本、无宿主凭据、明确网络策略、CPU/内存/磁盘/时间限制、进程树清理和快照回滚。增加逃逸/越权验证。完成前只允许可信测试夹具，不得将“临时世界”描述为安全沙箱。

### F-02 — P1：AI Debug Lab 还不是通用整合包自动测试系统

**观察事实**
- 已验证的实际运行环境是 Minecraft 26.2、Fabric Loader 0.20.1、Java 25 的专用服务端。
- 当前 MCP 工具以模组清单、定向原生快照、配方证据、日志尾部、受限方块写入和 tick 实验为主。
- 真实 MCP 验收使用固定测试模组/探针；测试通过证明该测试路径可运行，不证明任意用户整合包可测试。
- 尚无 Forge/NeoForge/Quilt、多版本矩阵、完整客户端渲染、多人同步、GUI、世界生成、长时间运行及存档迁移的统一验收矩阵。

**要求**
建立按 Loader × Minecraft 版本 × Server/Client × 功能类别的能力矩阵；将“可发现、可加载、可观察、可修改、可验证行为”分开标记。先定义一组真实整合包样本和失败案例，再扩展测试工具。不得将当前固定 Fabric fixture 的通过率外推为通用兼容率。

### F-03 — P1：主线集成和版本源头仍未收敛

**观察事实**
- 当前 `main` 仍是 V2.5 单文件源码与报告快照；README 指向 `Minecraft_Mod_Studio_V19.html`。
- V2.5 工程验收分支包含测试脚本和 CI，PR #1 仍开放、可合并，但尚未进入 main。
- `main` 与 V2.5 分支有分叉：main 额外包含 V2.3/V2.5 命名的 HTML 快照；V19 与 V25 当前内容相同（仅尾部换行不同），容易形成双源。
- AI Debug Lab 的 PR #2 仍为草稿；V0.12.2 → V0.12.5 采用堆叠 PR #6/#8/#9/#10，第四轮验收证据另在 PR #7。
- Structure Studio、Extension Engine、Horizon Adapter 是独立分支，尚未集成到主产品。

**要求**
先冻结唯一正式主程序路径和版本标签；合并前对 PR 基线、测试结果、数据文件和迁移记录做一次完整对账。按依赖顺序合并，不要把测试报告 PR、产品代码 PR 和研究分支混为一个版本。研究分支继续保持隔离。

### F-04 — P1：Structure Studio CI 缺少 pull_request 触发器

**观察事实**
- Structure Studio 最新工作流仅对指定分支的 push 和手动 workflow_dispatch 运行，没有 pull_request 事件。
- 当前提交 `3448969f` 的 push CI 已通过；最新 README 记录 15,332 项代码断言/检查及 Playwright 浏览器验收。
- 这轮曾发现浏览器验收把所有含 `Items` 的方块实体都当作钥匙箱；新增发射器箭矢库存后，测试选择器与产品语义不一致。当前测试已修正为只匹配带钥匙物品的箱子，CI 通过。

**要求**
给 Structure Studio 工作流增加针对其目标分支的 pull_request 触发器，并将相同验收设为合并必需检查。避免未来出现“分支 push 通过、PR 合并路径未运行 CI”的情况。

### F-05 — P1：真实 Minecraft 游戏行为验收尚未覆盖所有子系统

**观察事实**
- V2.5 已有真实 Fabric Gradle 编译和 JAR 完整性验证，但文档明确客户端启动与游戏内行为仍未验收。
- Structure Studio 已通过 NBT/数据包生成、结构断言和浏览器验收；README 明确红石陷阱触发、发射器朝向、箭矢碰撞、钥匙门、交互实体和自然生成仍需 Java 26.2 实机验证。
- Extension Engine 没有 Minecraft 游戏内测试。
- Horizon 分支处于 H0；未运行 SDK 或目标游戏。

**要求**
为每个功能维护独立阶段状态：静态检查、源码生成、编译、JAR 检查、游戏加载、行为验证、存档/重载。任何阶段不得替代下一阶段。Structure Studio 优先建立一次性 Java 26.2 世界的实机验收脚本；V2.5 优先完成客户端启动与核心生成模组的真实行为验证。

### F-06 — P1/P2：Extension Engine 的持久化测试与浏览器实际行为仍有缺口

**观察事实**
- V0.6 报告称 209 项分支回归通过；持久化存储 31 项测试使用 MemoryKVBackend。
- 报告明确指出 IndexedDB 浏览器执行、跨标签竞争、真实事务中止、配额错误、重载/重开后的恢复尚未验证。
- 当前扩展为数据型贡献，不执行任意插件代码；尚未接入主 Studio UI。
- 无发布者签名、信任根和撤销机制。

**要求**
在真实浏览器中验证 IndexedDB：并发 prepare/commit、双标签、事务 abort、配额耗尽、关闭/重开和恢复。先完成权限审查 UI 与可见的恢复状态，再考虑远程市场。若未来引入可执行插件，必须另做代码签名、信任和沙箱设计；不能沿用当前数据包安全假设。

### F-07 — P2：资源来源记录不等于授权核验

资源库能记录来源、许可信息和修改副本，但许可字段依赖用户/导入方提供，系统无法证明用户拥有再分发权。应保留来源哈希、许可原文/链接、修改记录和导出清单；对授权不明资源默认不打包、不上传、不随测试报告分发。

### F-08 — P2：单文件主程序的维护成本随功能增长

V2.5 主程序约 580 KB，包含大量内联 HTML/CSS/JS。单文件离线交付是合理的产品选择，但直接在同一文件持续叠加资源库、动画、AI 和扩展逻辑，会提高回归定位与模块隔离成本。

建议内部拆成可测试模块，通过固定构建流程生成单文件发布物；保持离线打开能力，不为了模块化引入不必要的运行时依赖。此项是维护性风险，不是当前已证实的功能故障。

### F-09 — P2：资源归档解析已有防护，但安全测试矩阵仍可扩大

**已有防护/测试**
- 资源导入对归档、单文件、总解压体积和条目数量设置上限，并限制资源路径与类型。
- 已有 ZIP/JAR 负例覆盖路径穿越、绝对路径、反斜杠、重复路径、符号链接、CRC 错误、超大文件和不支持压缩方式。

**尚缺证据**
当前负例集不等于完整 ZIP 解析器安全证明。建议增加截断/伪造中央目录、本地头与中央目录不一致、重叠数据区、异常压缩比、ZIP64/多磁盘、编码边界、超深 JSON、重复大小写路径和随机模糊测试，并检查失败时是否留下半成品或改变现有资源库。

### F-10 — P2：测试证据需要分层归档

第三轮/第四轮 Windows 验收报告包含大量原始日志、MCP transcript 和环境证据。当前报告对用户目录做了归一化，且明确不提交 server.properties/RCON 密码/个人存档；这有利于复核。但把所有大体积运行日志长期并入源代码 PR，会增加仓库体积和审查噪声。

建议仓库保留：测试报告、运行环境、提交 SHA、资产 SHA-256、汇总指标、失败摘要和证据清单；完整原始日志优先放 GitHub Actions artifact 或专用私有证据存储，并设置保留期。敏感字段在上传前做自动扫描和脱敏。

## 4. 已验证的正向工程能力

- **V2.5：** PR #1 对应分支有 Playwright 浏览器验收和真实 Fabric Gradle 构建；报告明确将 SOURCE_GENERATED、BUILD_VERIFIED 与游戏行为分开。
- **AI Debug Lab V0.12.5：** 提交 `b8b59afa` 的 Linux/Windows 单元测试与真实 MCP/Fabric CI 检查均通过；日志记录 89 项单元测试，以及真实服务端 MISS→STORED、HIT→NOT_NEEDED 两次运行。计时值是轮询观测，不是精确内部阶段时间。
- **Structure Studio：** 提交 `3448969f` 的最新 CI 成功；包含 15,332 项代码断言/检查、Playwright 浏览器验收和 Java 26.2 测试数据包 artifact。游戏内行为仍未验证。
- **Extension Engine：** V0.6 对依赖、权限、事务、升级/卸载、回滚、内容寻址和内存后端恢复有系统化测试；当前保持数据型、无任意代码执行的边界。
- **Horizon：** 研究明确区分官方上游能力、推断和 NOT_RUN；已复用方向和对照基线，不把合成 trace 测试冒充真实游戏兼容。

## 5. 建议执行顺序

1. **先设安全红线：** 在 OS 级沙箱验收完成前，不对来源不明模组执行真实 Java 运行。
2. **收敛主线：** 确定 V2.5 唯一源文件、版本标签和 PR #1 的集成方案；同步完整测试/构建入口。
3. **补齐 CI 治理：** 给 Structure Studio 增加 PR 触发器；明确各分支的必需检查和合并顺序。
4. **完成真实游戏验收：** V2.5 生成模组、Structure Studio 数据包分别在隔离的 Java 26.2 世界中验证。
5. **再扩展 AI 测试面：** 从固定 Fabric fixture 扩展到经过许可的真实整合包样本、负例和多环境矩阵。
6. **Extension Engine 浏览器验收：** 真 IndexedDB、跨标签、崩溃恢复、配额错误和权限 UI。
7. **Horizon 保持 H0/H1 门禁：** Java 主线实机验收完成、SDK/游戏 commit 锁定后再启动最小内容包验证。

## 6. 审计限制与下一轮

本轮未完成：对所有 580 KB HTML 内联代码逐函数审查；生成 Java 全量源码的安全审计；Windows 本机手工复现；恶意模组沙箱逃逸测试；完整 ZIP fuzzing；所有数据包在 Minecraft 客户端内加载；真实 IndexedDB 多标签压力测试；Horizon SDK 安装和游戏运行。

因此本报告的结论是“已识别当前系统边界、工程风险和验收缺口”，不是“整个系统已证明安全/无缺陷”。下一轮应按 F-01、F-03、F-04、F-05 顺序做针对性验证和修复。
