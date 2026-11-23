# Minecraft Mod Studio 项目进度看板

> **最后核对：2026-11-24**  
> 仓库：[tortletortle/minecraft-mod-studio](https://github.com/tortletortle/minecraft-mod-studio) · 默认分支：main  
> Wave 0 主分支 HEAD：867e1bd37df2f039a395779493efb8cb20093287

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

V2.5 源码快照为 8e8703875131c60b3bf2440c2dd8f44ae8c616a9，其后的四个 main 提交更新了 README 和两份项目管理文档。主分支当前包含 V19、V23、V25 三份 HTML 文件、V19–V25 测试报告快照和基础文档。

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
| V2.5 工程验收 / Fabric 构建 | PR #1 增加源文件映射、PR 检查、Fabric 构建、材质夹具和资源库验收工作流。该 PR 的旧 head 上三项检查均已执行并通过，包括资源库检查。 | **分支 CI 有通过证据，PR 未合并**。需要以最新工作流状态复核，并处理后续 Windows 验收发现的问题。 |
| AI Debug Lab | PR #2–#10、#12–#13。独立试玩服务、MCP 诊断工具、Fabric runtime 缓存、启动阶段计时、缓存生命周期和游戏内聊天中继均有实现或测试。 | **部分能力已有真实服务端实测**。PR #12 仍记录资源归档路径检查失败、动画姿态差异、预算耗尽错误提示不清晰，以及默认关闭宽限下测试世界清理问题。 |
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

## Wave 0 盘点与 Wave 1 执行记录

- 2026-11-24 上海时间，盘点基准为 [`867e1bd`](https://github.com/tortletortle/minecraft-mod-studio/commit/867e1bd37df2f039a395779493efb8cb20093287)。分支与 PR 计数取自开始本轮写入前：32 条分支、26 个开放 PR、16 个 Draft。#11 合入目标为扩展引擎研究分支。
- GitHub 比较显示 #1 与 main 分叉 46/4。三个版本的 README 复现单个冲突，候选分支 `agent/integration/w1-baseline-sync` 的 [`4a6541f`](https://github.com/tortletortle/minecraft-mod-studio/commit/4a6541f2e3505afcc88ec6d3dcdf6f85a4855cf6) 同时保留工程与项目管理入口。历史 #1 的三条 CI 已执行并通过。
- #14 包含 #1 的旧 head，新增 70 个提交、18 个净变更文件。#21 和 #22 均缺少当前 #19 的 68 个提交，且同时修改 MCP 服务和测试。V19 写入由 Agent 04 集中；#24 只在 V25 验证。
- 本轮 Linux 重跑 20 个内联脚本语法检查和 26 项工作流策略断言均通过。浏览器导出尝试在 Chromium 启动阶段被环境限制拦截，归档浏览器脚本也缺少 Playwright 随附的 Chromium。旧分支 CI 证据仍按其原 SHA 记录。#12 的 Windows 归档夹具修复已在 Draft PR #28 提交，模拟 Windows 分隔符验证通过，真实 Windows 浏览器复验仍待执行。
- 关闭的 #11 及独立分支 `research/extension-engine`、`feature/structure-studio-v0.1`、`research/horizon-adapter`、`research/ai-project-operator-bridge-v0.1`、`audit/system-audit-2026-11-21` 见上文及分支列表。上述范围维持 Java/Fabric 优先。

| Task ID / PR | 任务 | 负责席位 | 分支 @ head | 优先级 | 状态 | 依赖 | 测试状态 / 证据 | 验收等级 | 阻塞 / 下一步 |
|---|---|---|---|---|---|---|---|---|---|
| MMS-01 [#1](https://github.com/tortletortle/minecraft-mod-studio/pull/1) | Minecraft Mod Studio: Fabric build, animation runtime fixes and resource-library acceptance | 12 | `v2.5-engineering-acceptance` @ `4a6541f2` | P0 | VERIFY | `main` | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44901675929)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44901675881)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44901675911) | L4（旧 head） | GitHub 报告无合并冲突。候选已通过独立源码复核；新 head 三项 CI 首次及重试均失败，无测试步骤 |
| MMS-02 [#2](https://github.com/tortletortle/minecraft-mod-studio/pull/2) | AI Debug Lab V0.1: read-only runtime diagnostics and reproducible evidence | 05 | `ai-debug-lab-v0.1` @ `092f5656` | P0 | VERIFY | #1 | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44766223641) | L2 | 复核 #1 新基线上的只读诊断 |
| MMS-03 [#3](https://github.com/tortletortle/minecraft-mod-studio/pull/3) | test: Windows 实机 AI/MCP 验收报告（4d5e01d） | 10 | `test/local-ai-playtest-20261120` @ `a84d920d` | P1 | VERIFY | #2 | 未检索到 PR CI | L5（报告场景） | 核对 Windows 记录与测试 SHA |
| MMS-04 [#4](https://github.com/tortletortle/minecraft-mod-studio/pull/4) | test: add Windows AI playtest round two report | 10 | `test/local-ai-playtest-round2-20261120` @ `e3163831` | P1 | VERIFY | #2 | 未检索到 PR CI | L5（报告场景） | 复核第二轮 Windows 日志 |
| MMS-05 [#5](https://github.com/tortletortle/minecraft-mod-studio/pull/5) | test: AI Debug Lab cold-start and stability round 3 | 10 | `test/ai-debug-coldstart-round3-20261121` @ `61e7d685` | P1 | VERIFY | #2 | 未检索到 PR CI | L5（报告场景） | 复核冷启动基准与环境 |
| MMS-06 [#6](https://github.com/tortletortle/minecraft-mod-studio/pull/6) | feat(ai-debug-lab): V0.12.2 shared Fabric runtime cache | 05 | `feature/ai-debug-runtime-cache-v0.12.2` @ `3d265d53` | P0 | VERIFY | #2 | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44867907498)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44867907566)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44867907546) | L5（#7 指定场景） | 复核缓存生命周期和两秒清理失败 |
| MMS-07 [#7](https://github.com/tortletortle/minecraft-mod-studio/pull/7) | test: V0.12.2 第四轮 Windows 实机验收 | 10 | `test/ai-debug-runtime-cache-round4-20261121` @ `59600733` | P1 | VERIFY | #6 | 未检索到 PR CI | L5（报告场景） | 核对第四轮 Windows 条件 |
| MMS-08 [#8](https://github.com/tortletortle/minecraft-mod-studio/pull/8) | fix(ai-debug-lab): V0.12.3 startup and cache timing observability | 05 | `feature/ai-debug-startup-observability-v0.12.3` @ `0623a813` | P1 | VERIFY | #6 | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44877801311)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44877801372)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44877801291) | L2 | 检查计时与缓存事件一致性 |
| MMS-09 [#9](https://github.com/tortletortle/minecraft-mod-studio/pull/9) | feat(ai-debug-lab): V0.12.4 bounded Fabric cache lifecycle | 05 | `feature/ai-debug-cache-lifecycle-v0.12.4` @ `63883dc2` | P1 | VERIFY | #8 | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44890052591)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44890052650)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44890052666) | L2 | 固化缓存回收和并发回归 |
| MMS-10 [#10](https://github.com/tortletortle/minecraft-mod-studio/pull/10) | feat(ai-debug-lab): V0.12.5 startup phase timing evidence | 05 | `feature/ai-debug-startup-phase-timings-v0.12.5` @ `b8b59afa` | P1 | ACTIVE | #9 | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44886166939)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44886166921)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44886166912) | L2 | 复核 #9 新增 7 提交的生命周期行为 |
| MMS-12 [#12](https://github.com/tortletortle/minecraft-mod-studio/pull/12) | test: Windows 全功能实机验收 Mod Studio V2.5 与 AI Debug Lab | 10 | `test/windows-full-feature-acceptance-20261121` @ `5864e37f` | P0 | ACTIVE | #6 | 未检索到 PR CI | L5（指定通过场景） | 复测归档夹具、动画、预算反馈和清理 |
| MMS-13 [#13](https://github.com/tortletortle/minecraft-mod-studio/pull/13) | AI Debug Lab: connect Minecraft chat to desktop MCP | 05 | `feature/ai-debug-in-game-chat-v0.1` @ `163cdd75` | P1 | VERIFY | #10 | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44908241747)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44908241785) | L2 | 核对真实聊天往返与权限 |
| MMS-14 [#14](https://github.com/tortletortle/minecraft-mod-studio/pull/14) | V2.6: Live Game Debugger runtime companion and acceptance tooling | 05 | `v2.6-live-game-debugger` @ `13a0e8de` | P1 | VERIFY | `main` | [成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916573072)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916573070)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916573138)、[成功](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916573078) | L4 | GitHub 报告冲突。基于 #1 比较 18 个净变更文件，补真实客户端 |
| MMS-15 [#15](https://github.com/tortletortle/minecraft-mod-studio/pull/15) | V2.6.4: expose Live Game Debugger as typed MCP tools | 05 | `feature/live-debugger-mcp-v0.1` @ `83f4a34d` | P1 | VERIFY | #14 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45040748148) | 待复核 | 补执行记录，验证 11 项工具 |
| MMS-16 [#16](https://github.com/tortletortle/minecraft-mod-studio/pull/16) | V2.6.5: reduce Cursor friction in Live Game Debugger | 05 | `feature/live-debugger-agent-experience-v2.6.5` @ `dd6ea7dc` | P1 | VERIFY | #15 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45048508804) | 待复核 | 验证真实客户端截图、移动、短时授权和退出 |
| MMS-17 [#17](https://github.com/tortletortle/minecraft-mod-studio/pull/17) | [Draft] Schema Engine experiment: CodecUI integration for Minecraft 26.2 | 03 | `experiment/schema-engine-codecui-26.2` @ `42e67860` | P2 | VERIFY | `main` | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45112656399) | L0 | 执行实验夹具和真实 Fabric 构建 |
| MMS-18 [#18](https://github.com/tortletortle/minecraft-mod-studio/pull/18) | V2.7.0: AI God Mode command intelligence (read-only prototype) | 06 | `feature/ai-god-mode-command-intelligence-v2.7.0` @ `5515f58b` | P1 | VERIFY | #16 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45056466687) | L0 | 真实会话验证只读命令发现 |
| MMS-19 [#19](https://github.com/tortletortle/minecraft-mod-studio/pull/19) | V2.7.1: Mod command manifests and search enrichment (read-only) | 06 | `feature/ai-god-mode-command-manifests-v2.7.1` @ `7526c618` | P1 | VERIFY | #18 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45172725181) | L0 | 锁定当前命令清单契约，复跑 CI |
| MMS-20 [#20](https://github.com/tortletortle/minecraft-mod-studio/pull/20) | [WIP] Add UMPD static mod protocol scanner 0.1.0 | 03 | `research/umpd-static-scanner` @ `9f4a3142` | P2 | VERIFY | `main` | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45154210509) | L2（本地报告） | 审核授权语料、命中和漏报 |
| MMS-21 [#21](https://github.com/tortletortle/minecraft-mod-studio/pull/21) | [Draft] feat(ai): add capability-aware AI Template Library v0.2 | 08 | `feature/ai-template-library-v0.1` @ `39fb3ce1` | P2 | ACTIVE | #19 | 未检索到 PR CI | L1（分支记录） | GitHub 报告冲突。同步 #19，解决共享 MCP 路径，运行测试 |
| MMS-22 [#22](https://github.com/tortletortle/minecraft-mod-studio/pull/22) | V2.7.2: AI command retrieval, task planning and risk preview | 06 | `feature/ai-god-mode-operation-planner-v2.7.2` @ `bcdf3355` | P1 | ACTIVE | #19 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45134588492) | 待复核 | GitHub 报告冲突。同步 #19，复核计划预览、解决共享 MCP 路径 |
| MMS-23 [#23](https://github.com/tortletortle/minecraft-mod-studio/pull/23) | V2.7.3: typed block patch preview, apply and rollback | 06 | `feature/ai-god-mode-typed-world-patches-v2.7.3` @ `ee644299` | P1 | ACTIVE | #22 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45146912163) | 待复核 | 校验显式授权、异常补偿与一次性世界往返 |
| MMS-24 [#24](https://github.com/tortletortle/minecraft-mod-studio/pull/24) | feat: add reusable Minecraft mod template library | 08 | `feature/mod-template-library-v0.1` @ `bb213eb6` | P2 | VERIFY | `main` | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45149968719) | L2（V25） | 由编辑器负责人将接入层移植到 V19 |
| MMS-25 [#25](https://github.com/tortletortle/minecraft-mod-studio/pull/25) | [Draft] UI Workbench v0.1: contextual editor modes and fewer cards | 04 | `feature/ui-workbench-redesign-v0.1` @ `106fb393` | P1 | VERIFY | `main` | 未检索到 PR CI | L1 | 进行真实浏览器、键盘和双语验收 |
| MMS-26 [#26](https://github.com/tortletortle/minecraft-mod-studio/pull/26) | [Draft] V0.2: read-only AI Project Operator bridge | 07 | `feature/ai-project-operator-readonly-bridge-v0.2` @ `066148ef` | P1 | VERIFY | `research/ai-project-operator-bridge-v0.1` | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45151346360) | 待复核 | 使用真实 Windows 浏览器验收只读桥 |
| MMS-27 [#27](https://github.com/tortletortle/minecraft-mod-studio/pull/27) | [Draft] V0.3: read-only compatibility and resource migration analysis | 07 | `feature/ai-project-operator-analysis-v0.3` @ `542e6ca9` | P1 | VERIFY | #26 | [失败，无步骤](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45152858111) | 待复核 | 保持只读，校对权限文档，复测真实 JAR |
| MMS-28 [#28](https://github.com/tortletortle/minecraft-mod-studio/pull/28) | Windows ZIP 路径测试夹具 | 05 | `agent/fabric/w1-windows-archive-fixture` @ `c4feea9a` | P0 | VERIFY | #1、#12 | Python 语法和模拟 Windows 分隔符下的 ZIP 字节验证通过 | L2（夹具字节级） | 独立 QA 使用 V19 实际 ZIP 解析器，模拟 Windows 分隔符时旧夹具 9/10、新夹具 10/10；Windows Chromium 待复跑 |

本轮 PR #1 新提交重新触发了 [工程验收](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45229722438)、[材质](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45229722495) 和 [资源库](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45229722433)。三个作业均无步骤和日志，不能据此判断代码测试结果。三项均已重跑一次。重试仍无步骤和日志。当前执行环境为 JDK 21，缺 Gradle，未在本地执行 Fabric 26.2 构建或 Minecraft 实机。


### 2026-11-23 运行时复核（Wave 0 / P0，未新增产品完成声明）

- 重新读取 `main`、Issue #30、开放 PR 搜索、36 条分支（搜索首批返回 36 条且有后续游标）、近期提交及工程看板。此前 PR 数量/HEAD 记录是历史快照，不可作为实时状态。
- PR #1 最新 head `4a36d0a50e7b5942acacfe851648849f4b62837d`；三项最新运行 [资源库 45231061996](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45231061996)、[工程 45231062056](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45231062056)、[材质 45231062000](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45231062000) 均显示 failure，但查询 jobs 未返回 runner/steps 字段，判定为 **未获得可用执行证据**，不能判为产品代码失败或测试通过；历史成功只对历史 SHA 有效。
- PR #25 最新 head `1eac9032f842feb0677e5b896182084e564b3174`，Chromium 工作流 [45236264611](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45236264611) 同样没有可用 runner/steps 证据，浏览器验收 **未证实**。
- PR #31 最新 head `a1e4f5500fa18e81f57c63f7d8d0d629577d6b88`，单测工作流 [45232956914](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45232956914) 未返回 steps；Windows/真实 MCP 也显示 failure，不能作为功能结论。
- 本轮选定的最小 P0 任务是 **核实 PR #1 当前 head 的真实测试门禁与基础设施证据**；此项仍处于 Blocked/Verify，未重试已记录重试失败的 runner。PR #28 ZIP 夹具修复仍独立待 Windows Chromium 复核，未擅自合并。
- 验收等级：本轮仅证据审计 L0；未新增 L2/L3/L4/L5 通过证据。未执行 Fabric 构建、游戏实机或合并。下一步：获得可用 runner 或隔离环境后在精确 head 重跑三项工作流；独立审查并配置 branch protection / required checks。
