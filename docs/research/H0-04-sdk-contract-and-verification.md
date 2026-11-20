# H0.4–H0.5 · Horizon SDK 兼容性契约与分级验证
日期：2026-11-20；状态：预研规范（NOT_RUN），非生产实现。
范围：research/horizon-adapter；Java main 不修改。基线 f4070b207cc916df7e138c6c6009778df85e8049。
依据：下列公开文档本轮重新查阅；尚未下载及运行 SDK，未锁定实际可执行 build。

## 1. 上游能力与明确限制
- https://arismoko.github.io/horizon/reference/sdk/01-release.html ：SDK index 包含 build.commit/game、schema、package_format、Rust、content_api、surface.hash、mixins.rev/patch 和各资产 sha256。官方提供签名、哈希与安全解包校验；不要另写下载信任体系。
- https://arismoko.github.io/horizon/reference/sdk/05-commands.html ：new、build、check --uses、hooks、sdk diff、fits、update。优先封装这些命令并保存原始输出及退出状态；update 会改 pin，不自动用于任何既有工程。
- https://arismoko.github.io/horizon/reference/sdk/04-fit.html ：uses.json 表示代码使用的 API 表面及指纹；API-only native 模组可能跨 build 编译。使用内部 API、native 源码注入等特定机制或没有可读 uses 记录时只适合原 pin。兼容性还依赖依赖库、编译；声明不变并不证明实际行为不变。
- https://arismoko.github.io/horizon/reference/manifest.html ：内容 API 精确匹配，未知字段拒绝；原生 pin 含 game、horizon/mixins 完整 SHA。Wasm 与原生路由互斥；依赖版本、安装侧与事件执行侧不同。必需依赖缺失、不兼容版本、dispatch 循环会阻止加载；逻辑依赖覆盖不能消除二进制链接要求。原始 Java JAR 作为被动资源层不会执行其字节码。
- https://arismoko.github.io/horizon/concepts/testing.html ：官方 testing::FakeHost + with_mods 可模拟服务与 dispatch；无客户端后端，不支持的方法明确失败，不能替代真实游戏。
- https://arismoko.github.io/horizon/concepts/hooks-and-the-host.html 与 https://arismoko.github.io/horizon/reference/api.html ：全局 Hook 和绑定对象的 Part 语义不同；监听顺序、取消、执行侧以及 Not on wasm 均是映射约束。
所有链接为活动文档，进入 H1 须重新核对并记录上游 SHA；本报告没有捏造 build id 或运行日志。

## 2. 候选路由判定（Studio 自身策略）
按 feature 选择最低满足要求的运行方式；合并至完整包时需检查各 feature 能否共同部署，而不是简单混装。
| 候选 | 允许条件 | 不满足条件时 |
| --- | --- | --- |
| content | 完全可表达为目标版本的资源及注册数据 | 检查缺失行为，转候选 code 或停止 |
| wasm | 所需 Hook/Part/Host 全部在目标 Wasm API，权限、跨侧与资源语义明确 | 不静默降级；评估 native |
| native-public | Wasm 不可用，所需公开 Rust API 具备 | 固定目标并测试；否则阻塞 |
| native-exact | 需要 internals、定点源码变换等 | 默认不自动选；独立审计并明确批准 |
| bridge/manual | 保留原 Java 语义更合适或没有可证映射 | 独立可选桥对照或人工；不得宣告已迁移 |
未知依赖、授权不足、版本不明分别标为 blocked；无映射证据标 unknown；经过固定版本审计确定没有接口才标 unsupported。整个包的完整性取决于必需 feature，而不是平均分。

## 3. 待锁定环境记录（规范示例，非真实环境）
记录 sourceCommit、sourceGameVersion、targetGameVersion、targetHorizonCommit、targetMixinsCommit、sdkIndexSHA256、surfaceSHA256、contentApi、packageFormat、rustToolchain、sdkToolCommit、launcherVersion、osArch、installationSide、executionSide、lockfileSHA256、dependencies 和 fixtureSHA256。
缺失任何对应路线必需字段时不得报告可复现。内容模组不强行要求 code SDK / uses.json；精确 build 仍记录以便实验复现。SDK 资产校验由上游执行。

## 4. SDK 证据分级
官方 fits 退出码 0：目标范围的 API fit 检查成功；1：存在不兼容；2：未知、不可读或不适用；分别记录 PASS / FAIL / UNKNOWN 或 NOT_APPLICABLE（按输出区分）。工具未运行则 NOT_RUN。不得把 2 当作兼容或全部失败。
| 条件 | 静态映射 | 编译/打包 | 游戏行为 |
| --- | --- | --- | --- |
| fits=0；未运行游戏 | 可保持 candidate | 单独验证 | NOT_RUN |
| fits=1；接口变化 | 相关 feature blocked | NOT_RUN 或实际状态 | NOT_RUN |
| fits=2；网络失败 | UNKNOWN；保留原日志 | 不推定 | NOT_RUN |
| fits=2；内容模组 | NOT_APPLICABLE | 走内容 check/build | 独立验证 |
| FakeHost PASS；真实服务异常 | 可记录模拟 PASS | 独立验证 | FAIL 或 NOT_RUN |
任何实际失败记录精确命令、退出码、stderr、输入哈希、目标环境；重试失败需分类网络/SDK/源代码/环境，不将一次网络失败误判为系统性 API 缺口。

## 5. 实验设计：B01 雷电宝石的可移植性
从真实 Java oracle 固定触发条件、输入手、冷却、目标、世界侧及副作用次序。不得用文档中 LightningStrikeEvent 的名称推定其能主动生成闪电；查目标 SDK 的 ItemPart、Host 与实体生成能力。先验证右键调用与事件取消，再验证实际实体生成、物品状态。若缺失生成 API 标 blocked，不自动切换为命令或绕过权限。
分层对照：
1. 纯 IR 运算：同输入比较有序输出与错误行为。
2. 官方 FakeHost：只对支持的服务记录调用、状态及副作用；不可模拟的客户端渲染、多玩家/存档不计入通过。
3. 真实运行：合法、隔离的 Java 和 Horizon 实例，同游戏版本（Java 26.2→26.3 单列），记录日志及真实状态。固定输入、冷却边界、双手、取消、重复点击、客户端预测/服务器提交；选择多种子验证涉及随机性的行为。对应前一份规范 B01/B02/P01/V01。
4. 官方迁移工具作为资源迁移对照；桥接仅在可访问且合法的环境作额外对照。
验收必须按层记录独立状态，禁止用 mock 或编译代替游戏验证。

## 6. 依赖冲突最小负例（未执行）
- 缺失必需依赖；缺失可选依赖；同版本不满足范围；循环 order；client-only 标记却请求 server 权威逻辑；两个资源同 ID；外部 Java JAR hash 不一致；没有 uses.json 的 native 请求不同 build。
- 每个负例保留预期诊断类别及原始上游拒绝/警告。只做候选建议，禁止在用户不知情时丢弃依赖、修改安装侧或接受注入变化。
- 证据不足的用例（例如目标 SDK 变化）保持 UNKNOWN，不虚构通过率。

## 7. 分支后续门禁
当前 H0 研究成果已足够形成第一份可执行实验计划。停止重复扩展文档，待 Java 主线真实游戏验收与明确 H1 环境后，在独立分支开展最小内容包、官方工具 baseline、真实加载。H1 前不创建生产后端、修改 UI 或引入主线 CI。此次仅新增研究文档，没有实际 SDK 或游戏测试。