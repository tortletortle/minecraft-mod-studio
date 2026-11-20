# H0 上游证据与方案比较（2026-11-20）
范围：只读公开资料，未运行 Horizon、SDK、迁移工具或兼容桥；不影响 Java main。此报告修正 R&D-001 中未核验的推断。

## 已查证的公开文档声明
1. https://arismoko.github.io/horizon/introduction.html ：.hmod 是带 horizon-mod.toml 的 ZIP，内容包放 assets/data，原生包带 Rust 源码，Wasm 包带 mod.wasm。同一 mod API 的两种代码构建目标；不能据此推断所有 hooks 都可用。
2. https://arismoko.github.io/horizon/start/installing.html ：内容/Wasm 放 horizon-mods，原生包放 horizon-native-mods；需启用；新注册对象或世界生成通常须重启。普通 Horizon 不直接加载 Fabric/NeoForge JAR。多人服务器的数据所有权有约束。
3. https://github.com/horizon-rust/horizon/blob/main/docs/modpacks.md ：上游迁移器已有 import/inventory/fetch/carry/report/port、覆盖分类、依赖及许可证登记、计划中的 Java oracle 与差分 harness；并非空白市场。官方文档示例 ATM10（1.21.1）的 496 个条目有 42 partial、333 not yet、121 not needed（其文档末尾整合包导入场景，非通用兼容率），必须复现后才能引用为实测，不能把加载成功当作行为完整。
4. https://github.com/horizon-rust/horizon-mods/issues/1214 ：官方模组仍在迁移到新 SDK，11 月 20 日讨论中有缺失 hooks；说明平台接口不稳定。确切 SDK 版本待锁定。
5. https://github.com/iaxivers/horizon-java-bridge ：独立可选 beta，嵌入 JVM 执行 Fabric 26.3 模组，非 Rust 代码转换。作者自报 60 个热门模组中 39 可运行，16 有缺口，4 个渲染器替换不纳入，1 个阻止运行。未独立复核；要求合法 Minecraft 26.3 安装和登录。macOS 未测。桥接可作为对照，不直接承诺集成。
6. https://github.com/horizon-rust/horizon/blob/main/CONTRIBUTING.md ：模组 API 相关改动提交到 arismoko/horizon；引擎扩展点及游戏机制仍归上游主仓。需要跟踪两个基线。
资料可能随 main 变化；进入 H1 时记录具体 upstream SHA 与 SDK/游戏版本，再实际运行。

## 三条路线，按需选择
| 路线 | 用途 | 优先级/限制 |
|---|---|---|
| 内容迁移 | 授权 JAR 数据、纹理、基础注册对象、配方 | 复用官方 port-pack；不重做其已有能力 |
| Studio 原生项目直接生成 .hmod | 用户已有结构化设计语义 | Java 主线完成后首选；先内容后行为 |
| 保留 Java 代码的兼容桥 | 原有 Fabric 模组运行 | 仅观察或独立对照；不是纯 Rust；可能替代部分自研需求 |
避免任意字节码翻译，也不以 Java bridge 的支持范围推断 Rust 原生 API 能力。

## 后续最小验证方案（尚未执行）
固定同一 Minecraft 版本、目标 SDK/commit 和独立游戏实例。自造且授权的 fixture：A 基础方块+物品+配方+掉落，B 交互事件/冷却/状态，C 缺失 API/未知依赖/非法路径（负例），D 保存重载和多模组命名空间冲突。比较官方迁移器、Studio 未来导出、可选 bridge（仅当环境和版本允许）。分别记录打包、加载、行为、持久化；验证注册 ID、合成输出与数量、状态及事件顺序、重复运行确定性，明确 unsupported 或 partial，禁止 silent loss。样本按自有用例事先定义，避免取样偏差；随机行为用固定种子及多种子检验。所有断言必须由真实游戏状态/日志输出支持。
上游官方工具已可生成报告，因此产品增量待验证：结构化蓝图直接跨平台导出、迁移前可编辑预览、可定位到节点的兼容性诊断、与 Java 主线既有适配工作流整合。没有基线对照证明增量前不投入生产后端。
授权不清的第三方代码和游戏资源不入仓；遵守其许可证及上游政策，不假设可商用或可再发布。

## 决策
当前只保留 H0 研究分支。Java 生产 JAR 和适配主线验收是 H1 前置门禁。任何功能代码、依赖、CI、合并均暂缓。下一步可在分支继续整理接口清单与实验样本规范，只读、不引入生产依赖。