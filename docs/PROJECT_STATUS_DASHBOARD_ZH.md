# Minecraft Mod Studio 项目进度看板

> **最后核对：2026-11-24**  
> 仓库：[tortletortle/minecraft-mod-studio](https://github.com/tortletortle/minecraft-mod-studio) · 默认分支：main  
> 当前主分支 HEAD：867e1bd37df2f039a395779493efb8cb20093287  
> 全项目研发总控：[Issue #30](https://github.com/tortletortle/minecraft-mod-studio/issues/30) · 当前工程验收分支：`v2.5-engineering-acceptance`

本看板汇总主分支、功能分支、Draft PR、研究分支和可复核测试记录。它描述的是**项目真实工程状态**，不是功能愿望清单。每个工作流都区分代码实现、自动化测试、Fabric 构建、Minecraft 实机验收和主线合并。

## 1. 项目总览

| 指标 | 当前状态 |
|---|---|
| 产品主线 | Minecraft Java Edition / Fabric |
| 主分支基线 | V2.5 源码与测试报告快照 |
| GitHub 分支 | 32 条 |
| 当前开放 PR | 26 个（其中多个是 Draft 或堆叠 PR） |
| 已关闭 PR | #11，仅把 main 同步进 extension-engine 研究分支，没有把扩展引擎合入 main |
| 产品阶段 | 多个功能已形成可运行原型；主线集成、跨模块验收和实机验收尚未完成 |
| Rust/Horizon | 仅 H0 预研；不进入 Java 主线开发 |

**不提供一个看似精确的总完成百分比。** 当前工作分散在不同分支，测试证据等级差异很大；把本地单测、CI、Gradle 构建和游戏实机统一折算成一个百分比会误导判断。

### 本次复核与执行记录（2026-11-24）

- 已建立全项目总控 Issue [#30](https://github.com/tortletortle/minecraft-mod-studio/issues/30)，统一追踪 Wave 0–6 和最终 L6 发布门槛。
- PR [#1](https://github.com/tortletortle/minecraft-mod-studio/pull/1) 当前 head 为 `6b8cbec13476045a5f1fd63ba6ed212564b8231d`；Engineering Acceptance、Material Fixture、Resource Library Acceptance 三个 GitHub Actions 工作流均已完成且结论为 SUCCESS，工作步骤完整执行。
- PR #1 分支的维护源码包含 ZIP 路径反斜杠拒绝逻辑及独立动画覆盖保护；资源库安全测试和材质夹具工作流已通过。PR #12 的 Windows 失败记录来自较早的 main/候选对照，不能直接描述为 PR #1 当前分支仍失败；但仍需在同一最新候选上补做 Windows 复验。
- PR #12 仍有两项未闭环：MCP 写操作预算耗尽的调用方错误信息不明确；启动中断时 SDK 关闭宽限与 JVM/临时世界清理时序不匹配。PR #8–#10 增加了诊断、缓存生命周期和启动计时，但不能据此声称上述清理问题已经修复。
- PR #14 head 的四个工作流已通过。PR #16、#23、#24 的最新工作流曾失败，但对应 job 未提供可读取 steps/logs；已触发失败任务重跑，等待新证据，当前不归类为代码失败或通过。
- GitHub 集成对 main branch protection 查询返回 403（Resource not accessible by integration）。当前不能通过本连接启用 required checks；仓库管理员仍需在 GitHub Settings 中配置保护规则。未绕过此门禁合并 PR #1。

### 状态口径

- **主线已有**：代码或文件已在 main。
- **分支实现**：功能代码存在于独立分支，尚未合入 main。
- **本地验证**：有本地测试记录，但不代表 GitHub Actions 已通过。
- **CI 通过**：有对应提交的成功工作流记录。
- **实机通过**：在目标 Minecraft / Fabric 环境中实际运行并留下证据。
- **待验收**：代码或测试程序已准备，但关键验收尚未完成。
- **研究中**：只有研究、原型或候选方案，不视为产品功能。

## 2. 主分支基线与关键事实

### 当前 main 是什么

当前 main 的 HEAD 为 8e8703875131c60b3bf2440c2dd8f44ae8c616a9，提交信息为 “Add Minecraft Mod Studio V2.5 source snapshot V25”。主分支当前包含 V19、V23、V25 三份 HTML 文件、V19–V25 测试报告快照和基础文档。

- README 的运行入口仍指向 Minecraft_Mod_Studio_V19.html。
- V19 文件名是历史兼容名称，页面版本为 V2.5。
- PR [#1](https://github.com/tortletortle/minecraft-mod-studio/pull/1) 中的 docs/PROJECT_SOURCE_MAP.md 明确把 V19 作为维护入口、V23/V25 作为历史快照；该源码映射目前仍在 PR 分支，尚未合入 main。
- main 中的 V2.5 报告记录 895 项通过断言，**不是 895 个独立测试用例**。报告同时明确：主分支快照没有随仓库同步完整本地测试脚本、构建脚本和 CI；该报告本身也不是本轮重新执行的结果。
- V2.5 报告没有声称真实 Gradle/Fabric 构建和 Minecraft 游戏内运行已经完成。后续 PR 分支有更高等级的构建和实机证据，必须按对应提交查看，不能反向当作 main 已具备的能力。

### 主线集成现状

目前多个重要能力在独立分支或堆叠 PR 中。**PR 已打开不等于已经进入产品；Draft PR 不等于可发布；测试分支也不等于产品分支。**

## 3. 核心功能进度

| 工作流 | 当前实现与证据 | 状态 / 未完成门槛 |
|---|---|---|
| V2.5 可视化编辑器 | 蓝图逻辑、函数、行为编辑、调试器、Fabric 源码导出；V2.5 静态模型工作台支持传统 cuboid 模型预览、元素编辑、撤销和资源来源追踪。主分支报告记录 895 项通过断言。 | **主线已有原型**。V2.5 报告未证明完整 Minecraft 模型规范兼容，也未证明真实 Gradle 构建和游戏内运行。 |
| 资源库与跨模组适配 | V2.2 JAR/ZIP 资源库和来源追踪；V2.3 基于共享标签的配方适配分析；V2.4 关联资源迁移、命名空间重映射和冲突检查；V2.5 模型资源编辑。 | **主线已有基础能力**。复杂资源、第三方 loader、自定义模型和真实模组语料仍需逐项验收。 |
| V2.5 工程验收 / Fabric 构建 | PR #1 head `6b8cbec` 的 Engineering Acceptance、Material Fixture、Resource Library Acceptance 三个工作流均已完成 SUCCESS；包括真实 Fabric Gradle 构建和 ZIP/JAR 安全边界测试。 | **分支 CI 全部通过，PR 未合并**。主线保护仍需管理员配置；Windows 同提交复验及主线合并门禁仍待完成。 |
| AI Debug Lab | PR #2–#10、#12–#13。独立试玩服务、MCP 诊断工具、Fabric runtime 缓存、启动阶段计时、缓存生命周期和游戏内聊天中继均有实现或测试。PR #1 的当前维护源码已包含归档路径与动画覆盖修复，并通过对应 CI。 | **部分能力已有真实服务端实测**。PR #12 的预算错误反馈与启动中断清理问题仍待最新候选复验；PR #8–#10 的诊断增强不能代替清理修复验收。 |
| Live Game Debugger V2.6 | PR #14：Fabric 客户端伴随模组和受限本地桥；PR #15：11 个类型化 MCP 工具；PR #16：场景快照、截图回传、移动后验证、短时授权和 Cursor 安装诊断。 | **代码与构建有分支证据，真实客户端验收未完成**。PR #16 最近一次工作流在 Runner 分配前失败，不能算测试通过。 |
| AI God Mode V2.7 | PR #18–#19、#22–#23：动态发现 Brigadier 命令树、模组命令清单、中文/英文检索、BM25 风格候选排序、批量命令风险预览，以及类型化方块预览/应用/回滚。 | **分支实现，未形成可发布闭环**。命令发现与语法校验不等于命令执行；V2.7.3 方块事务仍是严格受限的实验能力，CI、Fabric 构建和真实世界往返验收尚未取得完整通过证据。 |
| AI 工作流模板库 | PR #21：7 个 AI 任务模板，覆盖陌生模组理解、指令检索、修改规划、世界建造、实体调参、诊断和多步骤编排；提供 5 个只读 MCP 模板工具。 | **分支实现**。模板目录和 Schema 静态检查通过；16 个注册表单测、14 个 MCP 假桥集成测试方法、4 个 Cursor 安装/诊断测试已添加，但 CI 未观察到实际执行成功；尚无浏览器编辑器模板选择器。 |
| 模组资源模板库 | PR #24：21 个声明式模板、37 个资源定义、13 个资源关系、8 个分类；支持中英双语目录、搜索、预览和原子插入。21/21 模板通过项目数据实例化，12/12 个 source_generated 模板通过当前源码生成器导出。 | **分支本地验证通过，尚未完成产品验收**。9 个模板仍为 design_only；没有声称 Gradle/JAR 构建或游戏内测试通过；GitHub Actions 曾在 Runner 分配前失败。 |
| UI Workbench 重构 | PR #25：把纹理/模型/配方/行为改为互斥编辑标签，隐藏非当前面板，减少重复卡片，合并右侧 Inspector。20 个内联 JS 块语法解析通过。 | **首轮 UI 切片已实现**。还没有真实浏览器截图、鼠标/键盘交互验收；完整中英双语、本地化、统一嵌套对象属性编辑、自定义值输入和 HEX 直接编辑仍未完成。 |
| AI Project Operator | PR #26–#27：本地 MCP stdio 服务、浏览器配对与短期会话令牌、受限只读编辑器 API、项目/资源检索；增加兼容性分析和资源迁移计划分析。 | **只读纵向切片已实现，仍为 Draft**。尚未接入 ProjectPatch 写入；Windows 浏览器和真实 Fabric JAR 对照验收仍待完成。 |
| 插件 / Extension Engine | research/extension-engine：V0.1–V0.9，数据型 .mmse 包、依赖解析、安装/卸载、权限授予、持久化、回滚、垃圾回收和发布者签名/信任根研究；V0.8-B 已把管理器集成到独立 V25 HTML。 | **独立研究分支，未合入 main**。V0.8 的真实 Chromium 单标签安装/保存/卸载流程有两次 CI 通过证据；V0.9 的本地 V8 测试通过，但双标签 Chromium、崩溃恢复、配额和多浏览器验收未完成。当前 UI 只接受本地包，首个贡献适配器仅支持配方；不是远程插件市场，也不执行包内任意 JavaScript。 |
| Structure Studio 建筑工具 | feature/structure-studio-v0.1：程序化建筑、NBT/数据包导出、独立体素编辑器、地牢房间图、钥匙门、秘密门、红石陷阱和符文谜题。README 记录 17,224 项代码断言/检查及 Playwright 浏览器验收通过。 | **独立分支原型较完整**。尚未在 Minecraft Java 26.2 实际加载数据包并验证交互、战利品、红石、自然生成和多人状态；尚未集成主编辑器。 |
| 协议 / Schema 能力 | PR #17：独立 CodecUI / Schema Engine 实验，包含 primitive、list、map、record、either 五类 Codec fixture 和有界 Schema-to-JSON 投影。 | **实验分支**。工作流曾在 Runner 分配前失败；Fabric 构建和游戏内验收未验证。 |
| UMPD 模组静态协议扫描器 | PR #20：Java 21 无额外依赖扫描器，识别 Fabric/Forge/NeoForge 元数据、资源清单、字节码类/成员引用和直接调用点；有 42 个 Fabric 项目的候选抽样框及语料审计器。 | **研究分支原型**。本地 JDK 验证 11/11、语料审计器 5/5；真实模组语料尚未下载并人工审计，Windows PowerShell 尚未执行，CI 无 Runner 执行证据；没有接入生产编辑器。 |
| Rust / Horizon 适配 | research/horizon-adapter：H0 接口和资源迁移预研，包含行为对照、实验矩阵和候选兼容边界。 | **仅预研**。没有 Rust 编译后端或真实适配；严格遵守 Java/Fabric 优先，不启动 Rust 正式开发，不影响主线。 |

## 4. 关键分支与 PR 索引

### 主线、工程验收与 AI Debug Lab

| PR | 内容 | 状态 |
|---|---|---|
| [#1](https://github.com/tortletortle/minecraft-mod-studio/pull/1) | V2.5 工程验收、Fabric 构建、材质和资源库检查 | Open；非 Draft；未合并 |
| [#2](https://github.com/tortletortle/minecraft-mod-studio/pull/2) | AI Debug Lab V0.1 只读诊断 | Open；Draft |
| [#3](https://github.com/tortletortle/minecraft-mod-studio/pull/3) / [#4](https://github.com/tortletortle/minecraft-mod-studio/pull/4) / [#5](https://github.com/tortletortle/minecraft-mod-studio/pull/5) | AI Debug Lab 多轮 Windows 实机测试报告 | Open；测试证据 PR |
| [#6](https://github.com/tortletortle/minecraft-mod-studio/pull/6)–[#10](https://github.com/tortletortle/minecraft-mod-studio/pull/10) | Fabric 缓存、启动诊断、生命周期和计时 | Open；多个堆叠分支 |
| [#12](https://github.com/tortletortle/minecraft-mod-studio/pull/12) | V2.5 与 AI Debug Lab Windows 全功能验收 | Open；非 Draft；包含已记录失败项 |
| [#13](https://github.com/tortletortle/minecraft-mod-studio/pull/13) | Minecraft 聊天与桌面 MCP 中继 | Open；Draft |

### Live Game Debugger 与 AI God Mode

| PR | 内容 | 状态 |
|---|---|---|
| [#14](https://github.com/tortletortle/minecraft-mod-studio/pull/14) | V2.6 Live Game Debugger Fabric companion | Open；Draft |
| [#15](https://github.com/tortletortle/minecraft-mod-studio/pull/15) | 11 个类型化 MCP 调试工具 | Open；Draft |
| [#16](https://github.com/tortletortle/minecraft-mod-studio/pull/16) | Cursor 低摩擦操作体验 | Open；Draft；最新 CI 需重跑 |
| [#17](https://github.com/tortletortle/minecraft-mod-studio/pull/17) | CodecUI / Schema Engine 实验 | Open；Draft |
| [#18](https://github.com/tortletortle/minecraft-mod-studio/pull/18) / [#19](https://github.com/tortletortle/minecraft-mod-studio/pull/19) | AI God Mode 命令发现与模组命令清单 | Open；Draft |
| [#22](https://github.com/tortletortle/minecraft-mod-studio/pull/22) | 命令检索、任务规划与风险预览 | Open；Draft |
| [#23](https://github.com/tortletortle/minecraft-mod-studio/pull/23) | 类型化方块 patch 预览、应用与回滚 | Open；Draft；尚无完整构建/实机验收 |

### 模板、UI、项目操作和协议研究

| PR / 分支 | 内容 | 状态 |
|---|---|---|
| [#20](https://github.com/tortletortle/minecraft-mod-studio/pull/20) | UMPD 静态模组协议扫描器 | Open；Draft |
| [#21](https://github.com/tortletortle/minecraft-mod-studio/pull/21) | AI 工作流模板库 | Open；Draft |
| [#24](https://github.com/tortletortle/minecraft-mod-studio/pull/24) | 模组资源模板库 | Open；Draft |
| [#25](https://github.com/tortletortle/minecraft-mod-studio/pull/25) | UI Workbench 减少卡片、上下文编辑 | Open；Draft |
| [#26](https://github.com/tortletortle/minecraft-mod-studio/pull/26) / [#27](https://github.com/tortletortle/minecraft-mod-studio/pull/27) | AI Project Operator 只读桥与兼容性/迁移分析 | Open；Draft |
| [research/extension-engine](https://github.com/tortletortle/minecraft-mod-studio/tree/research/extension-engine) | 插件 / 扩展引擎 V0.9 | 独立研究分支；未合入 main |
| [feature/structure-studio-v0.1](https://github.com/tortletortle/minecraft-mod-studio/tree/feature/structure-studio-v0.1) | Structure Studio 建筑编辑器与数据包生成 | 独立功能分支；尚无对应合并 PR |
| [research/horizon-adapter](https://github.com/tortletortle/minecraft-mod-studio/tree/research/horizon-adapter) | Horizon / Rust 适配预研 | 独立研究分支；不进入 Java 主线 |
| [research/umpd-static-scanner](https://github.com/tortletortle/minecraft-mod-studio/tree/research/umpd-static-scanner) | UMPD 静态扫描器 | 由 PR #20 跟踪 |

PR [#11](https://github.com/tortletortle/minecraft-mod-studio/pull/11) 已关闭，但它只把 main 同步到 research/extension-engine，不是扩展引擎合入主线的证据。

## 5. 目前最重要的阻塞

1. **主分支与实际开发状态不同步。** main 仍是 V2.5 快照；多项新功能存在于分支和 Draft PR。需要先确认唯一维护源码、工程验收门禁和合并顺序。
2. **Windows 全功能验收有明确失败项。** PR #12 记录资源归档路径检查失败、同输入下 ModelPart 动画姿态差异、MCP 预算耗尽错误不够明确，以及测试世界清理对关闭宽限时间敏感。
3. **若干工作流没有真正执行测试。** 多个 GitHub Actions 记录为 runner_id=0、无 runner、无 steps。此类结果只能标为基础设施未执行，既不是代码失败，也不是测试通过。
4. **Live Game Debugger 还缺真实客户端验收。** MCP 假桥测试和 Fabric Gradle 构建不能替代真实客户端的移动、截图、动画、属性同步和关闭清理测试。
5. **AI God Mode 的写操作边界尚未实机验证。** 方块事务的 fake-bridge 测试不能证明真实世界中的预览、确认、应用、读回和回滚正确。
6. **UI 改造还缺真实交互验收。** 目前不能把语法检查通过说成视觉效果、键盘操作和移动端体验通过；完整中英双语和自定义值输入仍未完成。
7. **插件引擎 V0.9 的持久化边界未完全验证。** 双标签冲突、IndexedDB 配额、事务中断、浏览器崩溃恢复和 Firefox/WebKit 尚未完成。
8. **结构工具、模板库和协议扫描器都需要更高等级的外部验收。** 数据结构测试、源码 ZIP 导出和 Playwright 不等于真实 Minecraft 运行；静态协议扫描也不等于未知模组行为已被理解。

## 6. 下一阶段建议顺序

| 优先级 | 工作 | 验收门槛 |
|---|---|---|
| P0 | 固定 V19 维护源码和 main 合并门禁；完成 PR #1 审核 | 源码映射一致、CI 全绿、Fabric 构建可复现、分支差异可解释 |
| P0 | 处理 PR #12 的归档路径和动画差异，并复核关闭清理 | 失败用例可复现、修复前后有对照证据、Windows 实机复测通过 |
| P1 | 完成 V2.6 Live Game Debugger 客户端验收 | 真实 Minecraft 26.2 / Java 25 / Fabric 中验证状态读取、移动、截图、动画、属性读回、授权和清理 |
| P1 | 完成 AI God Mode V2.7.3 真实世界事务验收 | 在一次性世界验证预览、显式确认、应用后读回、失败补偿和回滚；不开放通用命令执行 |
| P1 | 完成 UI Workbench 首轮浏览器验收 | 提供真实截图和交互记录；完成中英双语及 Preset + Custom 输入验收 |
| P2 | 完成 Extension Engine V0.9 浏览器和持久化验收 | 双标签、回滚窗口、配额、事务中断和恢复测试通过，再讨论合入 |
| P2 | 接通 AI 模板库与模组资源模板库 | 保持两个模板体系独立；完成编辑器入口、能力检查和缺失能力降级 |
| P2 | Structure Studio 真实游戏测试 | 在 26.2 一次性世界验证 NBT、交互实体、谜题、陷阱和自然生成 |
| P2 | UMPD 真实模组语料验证 | 下载并锁定授权/公开样本，记录版本与哈希，人工复核扫描命中和漏报 |
| P3 | Horizon/Rust 方向 | 只有 Java 主线核心功能和实机验收成熟后，再单独审批 H1 原型 |

## 7. 更新规则

每次功能更新都应在对应 PR 或报告中补齐：

- **实现位置**：分支名、PR、提交 SHA、维护源码路径。
- **验证类型**：静态检查、本地单测、GitHub Actions、Gradle/Fabric 构建、真实 Minecraft 实机。
- **测试条件**：Minecraft/Fabric/Java 版本、操作系统、测试世界类型、样本和命令。
- **结果**：通过、失败、跳过、未执行必须分开记录；失败用例不得从报告中删除。
- **证据**：工作流链接、日志、测试报告、截图、JAR 哈希或复现步骤。
- **集成状态**：未开始、分支实现、待评审、已合并、已发布分别标记。

只有代码进入 main 且对应验收门槛通过，才能将功能升级为“主线已完成”。研究成果、Draft PR、源码 ZIP 和本地测试都不能替代真实运行证据。

---

**当前判断：** Minecraft Mod Studio 已经不只是一个简单的可视化编辑器；它正在形成编辑器、资源适配、AI 游戏操作、项目级 AI 操作、模板体系、插件扩展和结构生成等多个子系统。但当前最大风险不是缺少新功能，而是**分支过多、主线落后、验收等级不统一**。下一步应优先收敛主线与验收证据，再继续扩大功能面。


## 8. Wave 1 安全修复：拒绝 ZIP 本地记录重叠（2026-11-24）

- **分支**：`agent/security/w1-zip-overlap-guard-20261124`；基线：`v2.5-engineering-acceptance` @ `4a36d0a50e7b5942acacfe851648849f4b62837d`。
- **维护源码**：`Minecraft_Mod_Studio_V19.html`。在 `StudioResources.readZip` 中记录每个已接受条目的本地头与压缩数据区间，排序后拒绝相交区间，避免多个中央目录条目把同一/重叠字节解释成不同资源。
- **自动化回归**：`tests/resources/archive_security.py` 新增恶意 ZIP fixture：第二个有效本地文件记录被嵌入第一个 PNG 的 payload，并让中央目录指向嵌入位置；同时保留并修正 Windows backslash fixture，确保原始反斜杠实际写入本地头和中央目录。
- **提交**：源码修改 `d49423487ef9cde30df74c2faddbab122c9f9686`；测试及 fixture 修正最终提交 `e3b5deed242858539897ea0ce2844ec640dcee22`。
- **已执行验证**：Python 3.13 标准库构造恶意归档，验证两个本地记录区间确实重叠、第二条中央目录偏移指向嵌入的 `PK\\x03\\x04` 本地头，并验证第一条 PNG payload CRC 更新正确；该 fixture 构造检查通过。
- **未执行 / 待执行**：尚未在真实 Chromium 中运行 `python tests/resources/archive_security.py`，也未运行 Windows Playwright、Fabric 构建或 Minecraft 实机测试。不得将当前结果标记为浏览器验收通过。
- **CI 基础设施证据**：Runner Smoke PR #32 run `45345393355`，唯一 job `138279583726` 首次失败且无 steps；按规则重试一次后 job `138279583726` 再次失败且仍无 steps。该证据支持“Runner 未进入步骤执行”的判断，不构成产品代码失败或通过。
- **验收等级**：L1（代码实现 + 恶意 fixture 构造验证）；L2 浏览器回归待 CI/本地 Chromium 环境。
- **下一步**：检查 PR #33 上的 Actions；Runner 恢复后执行 Chromium 资源导入安全套件。Windows 环境仍需独立执行同一套测试。继续保持 PR Draft，等待独立审查。

