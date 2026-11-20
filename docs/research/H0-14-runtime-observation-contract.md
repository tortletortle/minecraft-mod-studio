# H0.14 · 真实运行时观测接口与证据契约
日期：2026-11-21；阶段：H0 静态研究。NOT_RUN：未启动 Fabric、Horizon、SDK 或采集器。
基线：Java main f4070b207cc916df7e138c6c6009778df85e8049；源码 blob a0e47c2b137679475e5a3325314c2acc42c8fa6f。
源码：https://github.com/tortletortle/minecraft-mod-studio/blob/f4070b207cc916df7e138c6c6009778df85e8049/Minecraft_Mod_Studio_V19.html
本轮仅写研究契约，不改主线、生产代码、依赖、工作流，不启动 H1。

## A. Java 已存在的观测能力（实际读取源代码）
- L1930–1985 V1.5 运行时追踪：StudioRuntimeTrace.java 生成器及 StudioTraceV15 解析/过滤。开关 STUDIO_TRACE=1 或 studio.trace 属性；默认关闭。
- 日志标记 STUDIO_TRACE_V1；记录 v、session、mod、seq、dropped、entity、mob、tick、kind、data；data 均为字符串。UUID 与 seq 是进程相关身份；tick 是实体年龄而非全局世界时钟。
- snapshot 每20实体 tick 记录生命值、最大生命、xyz、目标存活状态、动画；bt_node 每10次评估采样，返回状态为后序；animation_start、state_transition、marker_attempt 事件存在。marker_attempt 只证明尝试，state_transition 记录在赋值之前，动画广播不证明客户端渲染成功。
- 全进程/模组每单调时钟秒窗口最多200条；sequence 在限流前递增；dropped 是自上条成功输出后累计丢弃数；尾部损失可能永远不被记录。解析器会统计损坏、重复、序号缺口、乱序、截断和 dropped；首条序号不一定为1。不能把 gap 与 dropped 加总当作唯一损失数（可能描述同一批丢失）。
- 现有生成器仅在报告列出的生物上注入追踪，未见 LightningItem/GraphItem 的专用完整事件流。无 case.begin/end、实验输入、产物 hash、完整性证明；现有日志只可辅助诊断，不可直接转换成完整比较记录。
- L290–357：LightningItem.use 先检查冷却，客户端预测 SUCCESS 后返回；服务端目标是玩家脚下 BlockPos 沿水平朝向移动 distance，然后取 Vec3.atBottomCenterOf。addFreshEntity 返回 false 时 FAIL，不设置冷却。成功才设置大于0的 cooldownTicks，返回 SUCCESS。此物品不扣数量、不减耐久（该方法无相应操作）。GraphItem 有 use/useOn 分流、有限程序、lightning/heal/message 操作；程序成功才设置冷却，不能假设程序失败具有事务回滚。均为生成模板静态语义，待真实 Java oracle 核验。

## B. Horizon 文档核对（2026-11-21，公开活动文档；未固定 SDK SHA）
- https://arismoko.github.io/horizon/start/writing-hooks.html : Hooks、Part、HostSide；有取消能力的 hook 可接收取消事件；priority 后按依赖顺序执行。观察者不得改变取消标志、优先级或返回值导致测试对象行为变化。
- https://arismoko.github.io/horizon/reference/hook-notes.html : right_click_item 在 ItemPart::use_item / 模板之前、两侧执行，且仅在目标交互 fallthrough；use_on 与 use_item_on_block 各有独立阶段；不能直接把两侧日志合并为一次权威操作。
- 同上：player_item_cooldown 在服务器冷却生效之前，可取消；lightning_strike 描述天气、引雷三叉戟和 /summon 路径的生成前事件，可取消；entity_struck_by_lightning 是命中前。实体加入 hook 也可能拒绝。任何 pre 事件只代表尝试。
- 同上：native_summon(dimension,kind,pos,nbt) 描述 /summon 型生成接口，可能因维度/未加载区块/取消等返回 None，事务中 id 可能失效。存在候选 API 不代表 Java addFreshEntity 语义或 lightning 类型一定覆盖；不得把控制台命令作为无声替代。level_tick_post 可作状态读取时机；暂停或出错时不能假定 post 一定出现。实体查询、added_to_level 等有覆盖及可见性限制，须锁定版本核验闪电实体是否可查询。
- https://arismoko.github.io/horizon/reference/api.html 和 https://arismoko.github.io/horizon/api/mod_api/ ：API 参考，Not on wasm 表示 Wasm 不可用。可在固定 checkout 生成 cargo doc；本轮个别 rustdoc trait 直链访问失败，catalog 文档链接返回 404，未能验证实际签名、SDK 构建或可调用接口集合。
- https://arismoko.github.io/horizon/concepts/hooks-and-the-host.html ：Hooks 可重入、同一模组对象可能服务多个线程/侧；读操作要注意 host/level 作用域，不应为日志调用 RNG 或改变世界。
- https://arismoko.github.io/horizon/concepts/testing.html ：FakeHost 可模拟受支持服务，仍非真正游戏证据。

## C. 拟定最小观测契约（未实现）
未来在两端独立测试实例中创建实验 harness，不默认修改产品模组。现有行为 trace 可作为辅助输入；完整观测要求自有、可审计、不会丢失关键事件的测试采集器及外部观测。先确定真实 API 和可控制场景，再实现专用采集。
| 中立事件 | Java 采集点候选 | Horizon 候选 | 目前证据 |
| --- | --- | --- | --- |
| case.begin/end | 测试 harness 明确开始、结束与 flush | 同 | 两端未接入 |
| item.use.request | 权威服务端进入 use/useOn，记录 hand/item等 | right_click_item / ItemPart 入口；按 phase 区分 | 候选 |
| spawn.attempt | 调用 addFreshEntity 前 | 适配器调用生成方法前 | 候选 |
| spawn.committed | 成功返回与世界内独立观察 | 返回有效值后独立读取世界/核对实体是否已加入 | API 可用性、闪电可见性待查 |
| cooldown.attempt | addCooldown 前 | player_item_cooldown pre | 不当成 commit |
| cooldown.observed | 实际剩余 tick/下一次交互受阻 | 目标 API 读取或独立时间边界实测 | 尚未确认直接读取接口 |
| inventory.observed | 服务端手中物品 count/durability 前后 | 服务端 stack 读取，明确 hand | 候选 |
| interaction.result | 服务端返回值 | 对应消费/回退语义，不能仅比较枚举名 | 候选 |
记录 observable ID 使用 registry ID、测试内稳定角色名或逻辑实体 ID；UUID 不作跨运行时直接比较；保留原始 UUID→逻辑角色映射的本地证据。未知映射不猜测。客户端预测另立通道；同一事件不得重复计数。tick 基于明确的统一实验起点和同一维度的权威 tick；实体年龄不可直接当作绝对时钟。
关键事件使用严格有序记录，不允许容差或忽略；只有预先声明且实证独立的遥测通道允许受限容差。

## D. 可比较性与完整性门禁
1. 固定游戏版本、源产物与目标产物 SHA256、SDK SHA、mod 列表、世界初态及明确的 seed/重复编号；Java 26.2→26.3 单列。
2. 保持原始日志，登记原始文件字节哈希、采集配置、会话、权威执行侧、是否截断与采集器版本；实验边界来自可信的独立 harness，不由截取日志推定。
3. 测试专用序列需要首尾、数量、drop 状态及 flush；发现序号缺口、重复或乱序等，按实际协议保留证据，关键记录不完整则 INVALID/NOT_COMPARABLE，而非 DIFFERENT。无边界或尾部确认的旧日志只能标 DIAGNOSTIC_ONLY。禁止把缺记录当作事件未发生。
4. 预先定义观测窗口、结束条件与负例。断言真实世界状态以独立观测支持，区分请求/尝试/提交/效果；测试本身不得改变随机序列或权限。
5. 现有 trace_compare、trace_policy、experiment_pipeline 只接受 SYNTHETIC；不得改标签伪装实际运行。H1 后才另行设计真正的证据入口、验证及回归，明确现有统计聚合非因果推断。

## E. 首个实机实验的候选验收（未运行）
在隔离、合法、本地专用世界中，原版天气关闭、无其他干扰模组，固定朝向和位置。使用自有 LightningItem。先冻结真实 Java 结果，不预设未确认的状态。静态预期：
- 正常右键：服务端一次实体添加；目标格中心正确；冷却仅成功后设置；物品数量不变。
- 冷却内再次右键：不产生新的服务端闪电；手中数量不变；允许客户端预测记录与权威事件不同。
- 在具备合法且可控的生成失败注入手段时：拒绝生成，无新冷却；若无法模拟失败，标 NOT_RUN。
- 冷却边界与双手、空中/方块目标、未加载区块、取消、同种子复跑分别记录，不假定跨游戏版本机制相同。
- 仅验证实体生成及状态的用例不自动验证雷击伤害、火、声音、客户端效果；这些分别收集。
H0 已形成足够具体的实机观测方案，下一关键阻塞不是增加合成工具，而是 Java 核心验收、目标 SDK 固定和实际测试环境。未满足前保持研究分支隔离，不开展生产后端。
