# R&D-001 · Horizon / Rust 跨运行时适配
日期：2026-11-20
状态：独立研发分支已立项；当前只启动预研，不启动生产适配后端。
分支：research/horizon-adapter
基线：main @ f4070b207cc916df7e138c6c6009778df85e8049

## 优先级与隔离
Java/Fabric 主线优先。预研只使用本分支的独立文档、样本、实验和（经后续评审批准后）独立工具链。不改 main，不改变主线发布、构建依赖、UI、CI 或资源分配；不自动合并或创建合并请求。将来可按需单向同步 main。任何共享代码变更须有独立评审、Java 回归证据与明确批准。主线开发不能被本方向的失败阻塞。此提交仅新增文档。

## 基线证据
main README 标记 V2.5，说明现有离线 HTML/JS 编辑器包括蓝图逻辑、函数、调试器、Fabric 源码生成、JAR/ZIP 静态资源库与来源追踪、共享标签配方适配、关联资源迁移和命名空间重映射。README 明确这是源码和报告快照，不代表完整开发历史或真实游戏验收。本次仅核实远程基线和 README，未审计全部实现或运行测试。后续 PR 中的验收材料须独立核对，不能以 README 推定所有现有功能。

## 研究对象与目标
优先考察 Horizon 的模组生态，而非把所有 Rust Minecraft 实现视为同一平台。
A. Studio 原生项目直接向目标平台导出：利用结构化设计语义，不先生成 Java 再逆向。
B. 经授权的既有 Java 模组跨运行时迁移：优先复用资源及数据转换工具；行为代码做有限语义映射与诊断，不保证任意 JAR 的自动转换。
验证核心是功能行为是否保持，而不是能否打包。

## 上游线索（来自 2026-11-19 预研；尚未运行 SDK，本次未重新核验）
- Horizon: https://github.com/horizon-rust/horizon
- 模组 API: https://github.com/horizon-rust/horizon/blob/main/docs/api/README.md
- 模组开发分支文档: https://arismoko.github.io/horizon/introduction.html
- SDK 命令: https://arismoko.github.io/horizon/reference/sdk/05-commands.html
- Manifest: https://arismoko.github.io/horizon/reference/manifest.html
- 资源迁移与模组包工具线索: https://github.com/horizon-rust/horizon/blob/main/docs/modpacks.md
- SDK 示例: https://github.com/arismoko/horizon-machine-sample
- Java bridge 实验: https://github.com/iaxivers/horizon-java-bridge
启动原型前核实链接、真实支持的 API、提交版本、许可证、工具可运行性；不得将实验性功能视为正式兼容。优先复用现有 port-pack / SDK 工具（能否复用取决于重新验证），不重复实现已有能力。

## 预估兼容范围
| 功能 | 候选路径 | 风险 |
| --- | --- | --- |
| PNG、语言、基础模型 | 资源复用 | 版本和资源路径差异 |
| 物品、方块、配方、战利品 | 内容 schema 转换 | 属性及注册规则差异 |
| 简单节点事件 | typed hooks / host API | 时序、取消语义 |
| 生物、动画、机器、GUI | 显式行为重实现 | 渲染、网络、存档、生命周期 |
| Mixin、任意 Java 字节码、Forge 私有 API | 人工迁移或拒绝 | 缺失类及注入点 |
所有条目目前为预估，未通过实测。Java 游戏版本迁移和跨运行时迁移必须分别控制。

## 候选架构（不是已存在的实现）
Studio 项目 / 授权 Java 源码或 JAR → 内容提取与语义分析 → 结构化 IR → 目标能力矩阵 → Fabric 或 Horizon 后端 → 构建、实际加载、行为等价性测试 → 报告。
建议 IR 表达注册对象、资源引用、事件序列、行为图、作用域、依赖、预期输出。遇到无法映射的功能应明确标注未支持或需人工补完，不允许静默删掉行为。

## 研发阶段与门禁
- H0（当前）：接口与工具可行性调查，形成证据表；仅预研文件。
- H1（Java 核心功能成熟并独立批准后）：固定目标版本，最小内容模组，对官方打包、校验及真实游戏加载作验证。
- H2：雷电宝石等自有样例行为，控制同版本、随机种子、事件、配置，验证正负用例、边界与可观察状态。
- H3：少量授权 Java 模组，逐功能兼容报告，记录拒绝和失败样本。
- H4：评估 Rust 原生/Wasm、复杂 GUI/实体、网络与存档；单独回归。
正式原型前须确认 Java 主线核心功能、生产 JAR 实际运行和适配回归证据，重新检查 Horizon SDK 稳定性、许可证、成本及需求。任何主线集成须单独批准。
实验报告区分编译、加载、行为等价性；失败要通过复现、控制变量及多样本判断是否系统性缺陷，不以偶发失败直接提出全局重构。

## 本次交付
独立分支研发章程和预研路线；无 Rust 后端、无游戏运行测试、无主线改动。