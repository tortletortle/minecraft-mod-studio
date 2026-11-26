# P0 第一轮审计：新一代 Mod Studio 资产与技术复用基线

> 状态：第一轮静态审计，待后续分支代码与实机复核  
> 审计日期：2026-11-26  
> 仓库基线：`main@e42eb5b826764ff6ab364eb81c8b7b31bd1cdc5c`  
> 对应总任务：Issue #41  
>
> 本文是审计记录，不是新架构最终冻结。凡标记“候选/待验证”的能力，不得当作已完成产品功能。

## 0. 审计原则

1. 新产品目标优先；旧项目只作为可选资产来源，不构成架构约束。
2. 先验证资产是否真实存在、在哪个 commit、有什么证据，再决定复用。
3. 区分主线代码、独立分支实现、自动化测试、Fabric 构建、真实 Minecraft 运行。
4. 不为 V0.1 提前实现通用 Boss 内核、插件市场或完整性能预测。
5. 任何外部依赖都要记录版本、许可证、兼容范围和退出方案。

## 1. 当前仓库事实

- main HEAD：`e42eb5b826764ff6ab364eb81c8b7b31bd1cdc5c`。
- 主线 HTML 编辑器：`Minecraft_Mod_Studio_V19.html`，当前 Blob SHA：`62bc83f4d4ff3a5c0209d508dcb79d6bc05e66e5`，实际约 580,844 字符。
- `Minecraft_Mod_Studio_V23.html` 与 `Minecraft_Mod_Studio_V25.html` 是历史快照；源码映射文档指定 V19 为维护入口。
- 仓库树共 364 项。主线不是一个已拆分的多模块应用工程；主编辑器仍是单 HTML 文件，Fabric 项目主要由编辑器导出生成。
- 根目录没有独立维护的完整 Fabric 生成器 Gradle 多模块工程。现有真实 Fabric 构建是对导出工程/验收夹具执行，不应误读成 Mod Studio 自身已拥有成熟的独立生成后端。
- main 有浏览器导出验收、材质夹具、资源库安全验收、客户端启动探针和隔离世界测试入口；各测试报告对“未运行”和“仅静态验证”有明确边界。

## 2. 旧项目资产审计矩阵（第一轮）

| 资产 | main 上证据 | 复用判断 | V0.1 决策 | 待补核查 |
|---|---|---|---|---|
| 生物编辑器 | V19 HTML 中有 EntityModel、骨骼/立方体、UV/材质、关键帧、行为树和状态机相关实现；README 与 V25 报告有功能描述 | 高，但需拆出稳定数据边界 | 复用交互和编辑流程；不继承单文件架构 | 端到端保存、重开、导出、游戏内模型/属性/AI |
| 物品编辑器 | V19 中有物品、模型预览、配方、行为图相关实现 | 高 | 暂不纳入 V0.1 主流程，保留为后续创作类型 | 实际注册、使用、配方运行时验收 |
| 方块编辑器 | V19 中有属性、纹理、掉落、矿石生成配置 | 高 | 暂不纳入 V0.1 主流程 | 注册、放置、挖掘、掉落、生成验收 |
| 模型/贴图工作台 | V25 报告：传统 Java cuboid 模型预览、编辑、撤销、贴图映射和资源追踪；明确不是完整 Blockbench 替代品 | 中高 | 保留导入/预览/基础编辑；优先支持 Blockbench 文件互操作 | 复杂模型、骨骼、现代模型规范和渲染一致性 |
| 动画 | V19 有动画关键帧；V26 动画修正文档记录了 locomotion overlay 修复和客户端模型测试 | 中高 | V0.1 先支持简单动画路径；GeckoLib 做可选适配候选 | 生产 JAR 加载和真实实体动画全流程 |
| 行为树/状态机 | V19 有相关编辑和生成逻辑 | 中 | V0.1 不承诺完整 AI 编辑；仅保留一个可验证基础行为/默认 AI | 节点语义、运行时行为和异常恢复 |
| Fabric 代码生成 | README 说明可导出物品/方块/生物 Gradle 源码；V25 工程验收有真实 Gradle 构建成功记录 | 高但范围受限 | 复用现有生成路径作为基线，先抽取/封装，不整体重写 | 完整追踪生成文件、不同实体配置覆盖、独立发布 JAR 加载 |
| 构建/测试 | `.github/workflows/v25-*`、`v26-resource-library.yml`；tests 下有 browser/material/resource/world 验收 | 高 | 直接复用验收脚本和安全边界 | 当前 HEAD 重新执行成功记录、Windows 复跑 |
| 资源库/模组导入 | V19 有 JAR/ZIP 静态资源导入、来源追踪、资源编辑、命名空间迁移和冲突检测；V26 文档将资源库验收标为 STATIC_ONLY | 高，但不是任意模组无损适配 | V0.1 只接收模型/贴图文件；完整 JAR 适配留后 | 真实第三方模组语料、运行时依赖和许可流程 |
| AI Debug Lab | 多条分支/PR，当前开放 PR #39 为 integration 汇总；旧看板记录缓存、启动诊断和聊天中继分支成果 | 中，独立研发资产 | 不进入 V0.1 生物生成闭环 | 以当前 PR head 重核 Windows、启动中断清理和运行证据 |
| Live Game Debugger | 分支 `v2.6-live-game-debugger`、`feature/live-debugger-mcp-v0.1`、`feature/live-debugger-agent-experience-v2.6.5`；PR #14–16 | 中，后续 QA 能力 | 不进入 V0.1；可作为后续实机调试工具 | 真实客户端、授权边界和当前 CI |
| AI God Mode | 分支/PR #18、#19、#22、#23，涉及命令发现、清单、规划、类型化 patch | 中低，未形成完整用户闭环 | 暂缓 | 从自然语言到真实执行/回滚的 Fabric 实机证据 |
| AI Project Operator | 分支/PR #26–27，主要是只读桥和迁移分析 | 中 | 暂缓 | 写入事务、回滚、权限和 Windows 验收 |
| 资源模板库 | PR #24，21 个声明式模板等，仍为 Draft | 中高 | 先作为内部测试夹具/示例来源，不阻塞 V0.1 | 当前 head 的 CI、构建和产品 UI 集成 |
| AI 工作流模板库 | PR #21，7 个工作流模板 | 中 | 后续复用 | 注册表测试实际执行、编辑器入口 |
| 插件引擎 | `research/extension-engine` 独立分支，研究数据型包、依赖、权限和回滚；未进入 main | 低至中 | V0.1 仅预留扩展边界，不接入插件系统 | 当前分支完整代码、安全威胁模型、安装/卸载/崩溃恢复 |
| Structure Studio | `feature/structure-studio-v0.1` 独立分支 | 中，独立产品域 | 不进入 V0.1，未来可作为创作类型 | Minecraft 数据包实机与主编辑器集成 |
| UMPD 静态扫描器 | PR #20 / `research/umpd-static-scanner` | 中，适配研究工具 | 不进入 V0.1 | 真实模组语料人工标注、召回率/误报率 |
| Schema Engine | PR #17 / `experiment/schema-engine-codecui-26.2` | 值得研究，但不能直接认定适合产品 Schema | 新 Schema 独立设计，参考其实验 | codec 覆盖、版本迁移、数据往返和兼容性 |
| 性能分析 | main 的 V19 未发现完整性能分析器；测试体系可用于构建基准 | 低（产品能力尚缺） | V0.1 仅静态复杂度计数/警告；真实性能采集后续接 spark/JFR | 运行时指标定义和采样开销 |

### 重要的主线/分支状态

当前开放 PR 不等于主线已集成。2026-11-26 查询到 24 个开放 PR，包含 Draft、堆叠分支、测试 PR 和文档 PR。特别注意：

- PR #39：AI Debug Lab integration 汇总，head `a3054f940642debea4e2457c6101dc8397a9bc27`，base main，Draft。
- PR #24：资源模板库，base main，Draft。
- PR #20：UMPD 扫描器，base main，Draft。
- PR #17：Schema Engine 实验，base main，Draft。
- PR #14：Live Game Debugger 初始 PR，base main，Draft。
- PR #25：UI Workbench，base 为旧工程验收分支，不应直接按 main 已有能力统计。
- PR #18–23、#26–27 等多个 PR 采用堆叠 base；合并前必须先核查依赖和共同基线。
- main 最新提交修复 ZIP/JAR 重叠本地记录检测；此安全修复应保留，但不改变 V0.1 产品架构判断。

## 3. 外部成熟项目复用矩阵（初步）

| 项目 | 能力 | 许可证/兼容证据 | 建议集成方式 | V0.1 |
|---|---|---|---|---|
| Fabric API | Minecraft 原生扩展事件、注册与客户端/服务端 API | Apache-2.0；Fabric API 有 26.2 对应发布版本 | 生成项目的基础依赖，不封装成自有替代 API | 必须 |
| Fabric Loom | Minecraft/Fabric Gradle 开发环境、运行配置和构建 | Fabric 官方 26.2 说明建议 Loom 1.17、Gradle 9.5.1；当前项目已有对应构建记录 | 直接作为生成工程构建工具 | 必须 |
| Blockbench | 模型、贴图、骨骼、动画及多种 Minecraft 格式 | 主程序 GPL-3.0；官方格式文档列出 Java block/item、modded entity、GeckoLib 等格式 | 文件导入/导出与外部启动；不复制源码、不把它嵌入产品 | 模型工作流必须支持互操作；深度集成后置 |
| GeckoLib | 实体/方块/物品/盔甲骨骼动画、关键帧、事件 | MIT；检索到 5.5.8 Fabric 26.2 发布条目 | 可选运行时依赖 + 独立动画适配器；默认简单实体不强制依赖 | 可选，不是首个闭环的硬依赖 |
| spark | Minecraft 客户端/服务端 CPU profiler、heap、GC、TPS/tick health | GPL-3.0；spark API 子模块为 MIT | 开发/用户环境外部工具或导入 profile 报告；不直接嵌入或复制 GPL 实现 | 不进入 |
| Java Flight Recorder | JVM 事件、CPU、分配、GC、线程等诊断数据 | 随 JDK 提供；按所用发行版/JDK 版本确认授权和功能 | 本地开发/测试启动参数采集，解析录制文件 | 后续真实性能分析 |
| MCreator | 可视化元素、Blockly procedures、Gradle workspace、代码生成产品经验 | GPL-3.0（带额外许可条款）；官方说明其 procedure 系统基于 Blockly | 只做产品与工作流对标；除非专项许可证审查通过，不复制代码 | 不进入 |
| Blockly | 可视化程序块编辑器 | 需单独核对当前仓库许可证、版本和自定义块维护成本 | 作为行为逻辑编辑器候选，不因 MCreator 使用它就自动采用 | 暂缓，先用简单行为配置 |

### 外部项目初步结论

1. **直接采用：Fabric API + Fabric Loom。** 它们是目标平台的基础设施，不值得重复开发。
2. **文件互操作优先：Blockbench。** 先支持其模型格式和往返测试，不把完整 3D 编辑器复制进 Mod Studio。
3. **可选动画适配：GeckoLib。** 先做最小 Fabric 26.2 实体动画样例，验证依赖、导出、安装和客户端加载，再决定成为正式适配器。
4. **性能诊断分阶段：JFR 优先作为 JVM 采集基础，spark 用作 Minecraft 语义化诊断/报告导入。** spark GPL-3.0，不应在未审查分发边界前嵌入。
5. **MCreator/Blockly 只做竞品和交互研究。** V0.1 不复制 MCreator，也不急于接入完整 Blockly。

## 4. V0.1 最小产品边界

### 用户流程

创建项目 → 创建生物 → 编辑基础属性 → 导入模型/贴图 → 设置一种基础交互 → 生成 Fabric 工程 → Gradle 构建 JAR → 在隔离 Minecraft 客户端中加载并实际验证。

### 必须支持

- 一个明确锁定的 Minecraft/Fabric/JDK 工具链配置。
- 生物 ID、显示名、最大生命值、移动速度、基础攻击属性。
- 模型与贴图导入；对不支持的模型格式明确拒绝并给出原因。
- 一种明确可验收的基础交互（例如玩家右键交互，返回成功/失败结果）。
- 生成可独立构建的 Fabric 工程和 JAR。
- 生物注册、生成方式（生成蛋或明确的测试命令）、属性、模型/贴图实际加载。
- 项目保存、关闭、重新打开后数据不丢失。
- 基础静态复杂度报告：实体数、动画数、行为/事件数、投射物数、依赖数；不声称 CPU 百分比预测。

### 明确不做

- 多节实体、Boss 分裂、传送门、复杂战斗 AI。
- 完整行为树编辑器和通用机制运行时。
- 任意第三方 JAR 无损适配。
- 插件市场、远程任意代码执行。
- 多 Loader、Rust/Horizon。
- 精确 CPU/内存占用预测。
- V0.1 必须集成 GeckoLib；若原生模型/动画无法满足最小闭环，再将其作为有条件依赖。

### 建议的 V0.1 技术边界

- 项目文件：版本化 JSON Schema，资源文件独立存储并有稳定 ID。
- 生成器：独立的 Fabric project generator，不依赖浏览器 DOM；输入为已验证的项目模型，输出为可构建 Gradle 工程。
- 编辑器：UI 只操作项目模型，不直接拼接 Java 字符串。
- 验证：Schema validation → resource validation → generation snapshot tests → Gradle build → isolated Minecraft client test。
- 兼容：旧项目数据采用只读导入/显式迁移；不要求新内核直接读懂旧 HTML 内部状态。
- 运行时：V0.1 优先生成静态、可独立运行的 Java/Fabric 代码，不在游戏运行时依赖 AI 或 Mod Studio。

## 5. P0 之后的最小任务拆分

| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| P0-A | 完成旧资产分支复核 | 本文初审 | 对 V0.1 相关能力追踪到具体源码/测试/commit |
| P0-B | 建立 GeckoLib 最小兼容样例 | Fabric 26.2 工具链 | 单生物模型/动画在隔离客户端加载，比较原生与 GeckoLib 路径 |
| P0-C | Blockbench 文件往返夹具 | 模型格式范围 | 选定一种实体模型格式，导入/导出关键字段无损或明确列出损失 |
| P0-D | 新项目 Schema 设计 | V0.1 流程 | JSON Schema、版本字段、迁移测试、示例项目 |
| P0-E | 生成器边界原型 | Schema | 从一个最小生物项目生成 Gradle 工程并成功构建 |
| P0-F | V0.1 真实游戏验收夹具 | 生成器 | 独立 Minecraft 26.2 客户端加载生成 JAR，实体生成、属性和交互通过 |
| P0-G | 冻结 P1 实施计划 | P0-A 至 P0-F | 有明确任务、依赖、负责人角色、证据路径和回滚策略 |

## 6. 本轮已知风险与待确认事项

1. 旧编辑器的高密度单 HTML 实现不适合作为新内核边界；可复用交互和算法，但应逐步提取纯数据模型和生成器。
2. 当前主线导出能力和历史测试记录存在价值，但部分 GameTest 使用隔离测试源集/探针；必须单独验收未经探针修改的发布 JAR。
3. Blockbench 与 MCreator 均为 GPL 系列许可证项目；外部工具集成和文件互操作比复制源码风险低，但仍需保留许可证告知。
4. GeckoLib 的 26.2 Fabric 发布存在，但需通过项目自身 JDK/Gradle/Loom 组合实测，不仅凭 Modrinth 版本列表就认定集成无风险。
5. spark GPL-3.0，优先作为外部工具；其 MIT API 子模块需要独立评估，不能把整个 spark 当 MIT。
6. 目前没有足够证据给 V0.1 定一个“开发天数”承诺；先完成最小生成器和真实客户端探针，再估算后续工作量。

## 7. 参考与证据

### 仓库内部
- [main commit e42eb5b](https://github.com/tortletortle/minecraft-mod-studio/commit/e42eb5b826764ff6ab364eb81c8b7b31bd1cdc5c)
- [源码映射](https://github.com/tortletortle/minecraft-mod-studio/blob/main/docs/PROJECT_SOURCE_MAP.md)
- [项目看板](https://github.com/tortletortle/minecraft-mod-studio/blob/main/docs/PROJECT_STATUS_DASHBOARD_ZH.md)
- [V25 工程审计](https://github.com/tortletortle/minecraft-mod-studio/blob/main/docs/V25_ENGINEERING_AUDIT.md)
- [V25 客户端验收边界](https://github.com/tortletortle/minecraft-mod-studio/blob/main/docs/V25_CLIENT_ACCEPTANCE.md)
- [V26 资源库验收](https://github.com/tortletortle/minecraft-mod-studio/blob/main/docs/V26_RESOURCE_LIBRARY.md)
- [V26 动画修正](https://github.com/tortletortle/minecraft-mod-studio/blob/main/docs/V26_RUNTIME_ANIMATION.md)
- [开放 PR 列表](https://github.com/tortletortle/minecraft-mod-studio/pulls)

### 外部项目
- [Fabric 26.2 公告](https://fabricmc.net/2026/06/15/262.html)
- [Fabric Loom 文档](https://docs.fabricmc.net/develop/loom/)
- [Fabric API](https://github.com/FabricMC/fabric-api)
- [Blockbench 官方格式说明](https://blockbench.net/wiki/blockbench/formats/)
- [Blockbench 插件文档](https://blockbench.net/wiki/docs/plugin/)
- [GeckoLib Modrinth 兼容性与许可证](https://modrinth.com/project/geckolib)
- [spark GitHub 与许可证](https://github.com/lucko/spark)
- [Java Flight Recorder / JDK Mission Control 文档](https://docs.oracle.com/en/java/java-components/jdk-mission-control/9/user-guide/jdk-mission-control-users-guide.pdf)
- [MCreator 官方许可证与 Blockly 说明](https://mcreator.net/support/knowledgebase)

---

**审计结论（暂定）：** V0.1 不应重写整个编辑器，也不应把旧 V19 直接当成新产品架构。最稳妥路线是保留其经过验证的创作交互和导出能力，抽取版本化项目数据模型与独立 Fabric 生成器；外部优先复用 Fabric 工具链，模型侧采用 Blockbench 文件互操作，动画按需适配 GeckoLib。复杂机制内核、AI 机制组合和完整性能分析均后置。
