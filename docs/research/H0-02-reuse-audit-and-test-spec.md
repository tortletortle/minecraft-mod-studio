# H0.2 · V2.5 源码复用审计与差分验收规范
日期：2026-11-20；H0 文档预研，禁止修改 main 或引入生产依赖。
基线：https://github.com/tortletortle/minecraft-mod-studio/blob/f4070b207cc916df7e138c6c6009778df85e8049/Minecraft_Mod_Studio_V19.html
仓库读取：HTML blob a0e47c2b137679475e5a3325314c2acc42c8fa6f，2070 行；未执行 JS、未重新运行测试，以下是静态审计而非行为验证。

## 1. 静态源码证据
| 位置（上述固定提交） | 可借鉴 | 不直接复用/风险 |
| --- | --- | --- |
| L31 StudioBehavior；L1988–2002 报告 | 有限图、类型表达式、局部变量、纯函数、步数预算 | Java 代码生成和游戏效果需要独立映射；模拟器不是真实游戏 |
| L185–205 StudioCore | UID、引用边、范围与输入验证 | 结构校验硬编码 Fabric 26.2；内部 UID 不是游戏注册 ID |
| L226，L358–366 StudioCompiler | 生成资源、拒绝未支持项、可重复归档思路 | Gradle、Java 25、fabric.mod.json、Java 注册类均属 Fabric |
| L397，L410–422 StudioResources | ZIP 解析、显式引用、来源、暂存与校验 | apply 操作 Fabric 导出；不能把全部 Java 数据视为兼容；显式引用非完整依赖 |
| L443，L453–477 StudioMigration | 资源依赖闭包、命名空间处理、迁移计划 | 静态规则只覆盖部分模型与资源；注册及行为不在范围内 |
| L481，L491 StudioCompat；L2043 UI | 标签匹配、冲突/缺口诊断 | 原实现仅建议现代 Fabric 原版工作台配方的输入替换；硬编码范围需保留 |
| L2004–2020 smoke | 初始化与 ready 证据的分级思想 | 只验证 Fabric 开发服务器启动；不证明打包 JAR 或游戏逻辑 |
| L2034–2044 资源库 UI | 原件与编辑副本分离、来源追踪、权利确认 | IndexedDB 和单文件 UI 耦合；不在 H0 抽取或修改 |
不能把现有工具称为任意 Java JAR 的跨运行时翻译器。当前主线为 26.2，上游 Horizon 文档为 26.3，版本迁移须单独验证。

## 2. 上游接口证据（2026-11-20 查阅）
- https://arismoko.github.io/horizon/start/first-content-mod.html ：SDK 示例提供 manifest、block registry JSON、模型、配方、loot；cargo horizon-mod build/check；启动后实际合成另行验证。Rust >=1.95。
- https://arismoko.github.io/horizon/how-to/content-mods.html ：API 0.2 内容注册，manifest capability registries；both-side 模组核对身份版本；命名空间所有权限制、加载顺序影响标签，未注册标签项可能被丢弃；模板不能继承任意 item-ID-specific 行为。效果注册不等于 tick 或属性修改，菜单注册不等于完整 UI。外部 JAR 可由 use-jar 记录 id/version/SHA512，仅提供被动资源，不执行 Java。
- https://github.com/horizon-rust/horizon/blob/main/docs/modpacks.md ：已有 port-pack 内容迁移；先对比后决定自研增量。
- https://github.com/horizon-rust/horizon-mods/issues/1214 ：官方 native mods 正在迁移新 SDK。
- https://github.com/horizon-rust/horizon/blob/main/docs/mods.md ：仍描述旧 .hnmod 路线，与当前 SDK 书中 .hmod 路线不同。不得混用版本；H1 先确认所选分支实际提交、工具版本及启动器配套。
文档为上游声明，尚未验证运行；不主张全部功能已成熟。

## 3.候选转换契约（仅设计）
原始 Project JSON（只读）→ 安全验证与 snapshot → 中立语义清单 → 目标版本分析 → 能力矩阵 → 目标包。每个 feature 记录 featureId、sourceUid、sourcePath、expectedBehavior、targetVersion、mappingStatus、reason、evidence。mappingStatus: unknown / candidate / blocked / unsupported；验证结果独立记录 NOT_RUN / PASS / FAIL。PASS 仅限实际完成的对应阶段；不允许用静态检查自动填充真实游戏 PASS。
- 资源：仅授权原件或显式声明外部 JAR。按 namespace/path 记录冲突，保留来源哈希；不打包未经授权的资源。
- 注册：物品/方块 ID 不从 UID 猜测；模板和组件必须有目标证据；保留未知属性的拒绝诊断。
- 配方：替换前解析原版/tag/内部引用；显式材料组不是全部依赖，跨版本字段及计数规则独立验证。
- 行为：首先映射纯计算及条件，世界写入、冷却、权限、客户端/服务器侧和调用顺序单独核验。遇到未知 hook 拒绝或可见地标注部分支持；不能默默丢弃。
- 未来输出 .hmod 仅在 SDK 版本锁定后生成；不编辑 Java project schema 或现有 UI，不增加主线依赖。

## 4. 预注册实验（全部 NOT_RUN）
| ID | 自有样本/条件 | 独立断言 |
| --- | --- | --- |
| C01 | 原版模板派生方块、同 ID 物品、自制纹理 | 注册、放置、破坏、掉落、渲染与清单一致 |
| C02 | 3x3 有序配方 + 标签输入；不匹配材料 | 合成输出 ID、数量、消耗、负例拒绝 |
| C03 | 两个自有命名空间的模型和纹理关联 | 引用全部解析；不覆盖原件、不引入错误依赖 |
| C04 | 同路径不同内容、缺失标签项、未授权资源、非法路径 | 诊断明确；拒绝不安全包、无静默丢失 |
| B01 | 雷电宝石右键，非合法触发/冷却期间 | 实体生成次数、位置/目标、扣耗、冷却与权限；无重复副作用；确切期望由现行 Java oracle 冻结 |
| B02 | 纯函数、边界数值、除零、循环上限 | 逐步骤输出、错误及副作用序列一致；不以模拟通过代替游戏通过 |
| P01 | 保存、退出、重载、相同/缺失模组多人连接 | 状态和注册 ID 稳定，缺失模组行为与声明一致 |
| V01 | Java 26.2 vs Java 26.3 vs 同版本 Horizon | 先测 Java 版本基线；再测同版跨运行时，避免混淆根因 |
阶段分别为 static/package/real-load/gameplay/persistence；负例单列。保存输入 SHA256、代码与游戏 build ID、SDK SHA、命令、退出码、日志、观测状态及失败原件。固定种子重跑确定性；随机功能至少三个预先选定种子（初步设计，不宣称统计充分）。失败先重跑与控制变量，再判定系统性。
官方 port-pack 在相同授权样本上作对照基线；记录覆盖、错误诊断、人工修复步骤，Studio 不能把官方已有功能当创新。所有测试尚未执行。

## 5. 门禁
H0 仅提交研究文档。待 Java 主线真实游戏验收、独立环境和上游版本锁定明确后，才开始 H1。禁止自动合并。当前无 SDK、无合法游戏实例证据、无实测，不给出兼容率或性能指标。