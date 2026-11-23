# Minecraft Java 模组协议版图与适配策略（26.2）

- 调研日期：2026-11-23
- 目标环境：Minecraft Java 26.2，优先 Fabric；NeoForge 作为第二适配目标
- 目的：为 Minecraft Mod Studio 建立跨模组数据发现、统一 Schema、验证和安全写回能力
- 证据范围：Fabric 26.2 官方文档、NeoForge 配置文档/源码，以及 Sodium、Spectrum、TechReborn、Applied Energistics 2、Fabric Carpet 等公开源码样本

## 0. 结论先行

Minecraft Java 模组没有一个覆盖所有模组、所有数据域的统一序列化协议。一个模组经常同时使用多个协议：

- 配置文件可能是 Gson JSON；
- 数据包/资源包元数据可能是 Mojang Codec；
- 方块实体保存可能是 NBT；
- 物品组件可能同时使用 Codec 和 StreamCodec；
- 客户端/服务端通信可能是 CustomPacketPayload + StreamCodec；
- 某些网络载荷内部又直接装入 NBT。

因此，不能按“一个模组对应一个协议”设计适配器。应按**数据域 + 序列化机制 + 生命周期/作用域**识别，并把不同机制归一到同一个编辑器无关 Schema。

当前样本是目的性抽样，不是随机抽样或全生态统计；本报告不声称“X% 模组使用某协议”。要验证“绝大多数”的覆盖率，必须建立可重复的模组语料库和检测基准。

## 1. 协议/数据域分类

| 数据域 | 常见机制/格式 | 发现信号 | 自动化潜力 | 写回风险 |
|---|---|---|---|---|
| 数据包与资源数据 | JSON + Codec/MapCodec + Registry ID | `Codec`、`MapCodec`、`RecordCodecBuilder`、`DynamicOps`、`data/<namespace>/...` | 高 | 中：受版本、注册表、数据包优先级影响 |
| 模组配置 | JSON、JSON5、TOML；Gson/Jankson/NightConfig/自定义配置类 | `Gson.fromJson`、`Jankson`、`Toml`、`ModConfigSpec`、YACL/AutoConfig | 高（可读配置） | 中：默认值、注释、重载/重启语义必须保留 |
| 方块实体/实体持久化 | NBT；26.2 的 ValueInput/ValueOutput；部分字段通过 Codec 读写 | `saveAdditional`、`loadAdditional`、`ValueInput`、`ValueOutput`、`CompoundTag` | 中 | 高：位置、注册表、世界状态、未知字段和运行时同步 |
| 世界级 Saved Data | NBT + Codec | `SavedData`、`Codec`、`NbtOps` | 中到高 | 高：通常与具体世界绑定 |
| 物品数据组件 | 命名空间组件 ID + persistent Codec + network StreamCodec | `DataComponentType`、`.persistent(...)`、`.networkSynchronized(...)` | 高（组件定义可发现时） | 中到高：默认组件、缺失值、服务端权威 |
| 网络载荷 | CustomPacketPayload + StreamCodec；旧版 PacketByteBuf/自定义通道 | `CustomPacketPayload`、`StreamCodec`、`PayloadTypeRegistry`、payload ID | 结构可发现，编辑能力低 | 极高：方向、时序、权限、状态机和服务端校验 |
| 注册表/动态注册表 | ResourceKey/Registry ID + Codec + 数据包 JSON | `ResourceKey`、`Registry`、`DynamicRegistries`、注册表 Codec | 高 | 中到高：必须有正确 RegistryAccess 和数据包上下文 |
| 资源包资产 | JSON、PNG、Ogg、mcmeta 等固定资源结构 | `assets/<namespace>/...`、`pack.mcmeta`、models/blockstates/lang | 高，但不是通用 Java 对象 Schema | 中：路径、引用和资源优先级 |
| 自定义 Java 对象/二进制格式 | 任意类、字段、函数、手写字节协议 | ASM/字节码、反射、Mixin、私有 API | 低到中 | 极高：没有通用安全写回语义 |

### 1.1 Codec 不是 JSON，也不是 NBT

Fabric 26.2 文档明确区分：

- `Codec<T>` 定义对象如何编码/解码；
- `DynamicOps<T>` 定义承载格式，例如 JSON 或 NBT；
- `MapCodec<T>` 保证对象按键值映射结构表示；
- `DataResult` 承载成功或失败结果。

同一个 Codec 可以配合 JsonOps 或 NbtOps 使用。因此，Mod Studio 应将“对象 Schema”和“物理存储格式”分开建模，而不是把 JSON Schema 当作唯一中间表示。

参考：[Fabric 26.2 Codecs](https://docs.fabricmc.net/26.2/develop/serialization/codecs)。

### 1.2 配置界面库不等于配置存储协议

这是容易误判的地方：

- Cloth Config 的核心定位是配置屏幕，不拥有模组的配置文件格式；其 Auto Config 才提供基于注解类的读写能力，可使用 Gson、Jankson 或 TOML4J。
- YACL 的 GUI builder 可以定义保存回调；其 Config API 可配合 Gson serializer 管理配置类。仅发现 YACL screen，不代表已经发现了底层持久化格式。
- NeoForge 的 ModConfigSpec 基于 NightConfig/TOML，定义 ValueSpec、ConfigValue、层级、验证与配置类型。
- Fabric 没有一个所有模组都必须使用的统一配置文件规范；模组会选用第三方库或自行实现。

参考：[Cloth Config](https://cloth-config.com/)、[Cloth Config Auto Config 说明](https://cloth-config.com/about/)、[YACL Config API](https://docs.isxander.dev/yet-another-config-lib/config-api/basic-usage-of-config-api)、[NeoForge Configuration](https://docs.neoforged.net/docs/misc/config/)。

## 2. 公开模组源码样本

以下样本用于证明“一个模组可能混用多个机制”，不用于推断全生态占比。

| 项目 | 可核验源码事实 | 对适配器的启示 |
|---|---|---|
| Sodium | [SodiumOptions.java](https://github.com/CaffeineMC/sodium/blob/3a99e4ee80d4a13f453f6607a215f3615842c445/common/src/main/java/net/caffeinemc/mods/sodium/client/gui/SodiumOptions.java) 使用 Gson 将配置类读写文件；[SodiumResourcePackMetadata.java](https://github.com/CaffeineMC/sodium/blob/3a99e4ee80d4a13f453f6607a215f3615842c445/common/src/main/java/net/caffeinemc/mods/sodium/client/checks/SodiumResourcePackMetadata.java) 又使用 RecordCodecBuilder Codec 读取资源包元数据。 | 同一模组的配置和资源元数据需要不同适配器。 |
| Spectrum | [MemoryBlockEntity.java](https://github.com/DaFuqs/Spectrum/blob/0391a91c29270e3a3472940a76a1fee30bd33897/src/main/java/de/dafuqs/spectrum/blocks/memory/MemoryBlockEntity.java) 展示了 CompoundTag 手动字段与 `CodecHelper.writeNbt(..., ItemStack.CODEC, ...)` 混合使用的旧式持久化路径。 | NBT 不总是“无结构原始树”；一个 NBT 对象内部可以嵌入 Codec 定义的数据。该样本用于说明模式，不能代替 26.2 ValueInput/ValueOutput API 的版本验收。 |
| TechReborn / RebornCore | [ConfigGroup.java](https://github.com/TechReborn/TechReborn/blob/140bc0fc12adc74f0b1e81892d33db224ae84629/RebornCore/src/main/java/reborncore/common/config/ConfigGroup.java) 暴露 `codec(key, Codec<T>, defaultValue)`；[ConfigValueImpl.java](https://github.com/TechReborn/TechReborn/blob/140bc0fc12adc74f0b1e81892d33db224ae84629/RebornCore/src/main/java/reborncore/common/config/impl/ConfigValueImpl.java) 保存 Codec 并通过 xmap 构造节点 Codec。 | Codec 不只用于 datapack/worldgen，也可直接成为配置系统的数据契约。 |
| Applied Energistics 2 | [AEKeyType.java](https://github.com/AppliedEnergistics/Applied-Energistics-2/blob/e7103ceccb3bcc75e9af6ad66fa83d683f811c4c/src/main/java/appeng/api/stacks/AEKeyType.java) 同时定义 Codec、StreamCodec、MapCodec，并包含 packet 读取接口。 | 适配器不能假设一个类型只对应一种序列化器；同一类型可能有持久化、结构化和网络表示。 |
| Fabric Carpet | [CarpetClient.java](https://github.com/gnembon/fabric-carpet/blob/101b476d25c0c34a6efd15aa9b13c4744f260f5c/src/main/java/carpet/network/CarpetClient.java) 的 CustomPacketPayload 使用 StreamCodec，但载荷本体是 CompoundTag，并通过 NBT 读写。 | 网络协议层与载荷内部格式必须分层；只识别 StreamCodec 仍不足以理解 NBT 内容。 |

## 3. Minecraft 26.2 的关键官方路径

### 3.1 方块实体与世界保存

Fabric 26.2 的 Block Entity 文档采用 `ValueInput` / `ValueOutput`：

- 原始字段可用 `getIntOr`、`putInt` 等读取和写入；
- 结构化字段可用 `read(name, codec)` 与 `store(name, codec, value)`；
- `saveAdditional` / `loadAdditional` 是生命周期入口；
- 磁盘保存与客户端同步是不同问题，还涉及 update tag/packet。

这意味着 NBT 适配器需要同时识别“原始 tag 键”和“通过 Codec 读写的子对象”，不能只靠 NBT 树推断全部字段语义。

参考：[Fabric 26.2 Block Entities](https://docs.fabricmc.net/26.2/develop/blocks/block-entities)。

### 3.2 Saved Data 与 Data Attachments

Fabric Saved Data 以 NBT 落盘，并用 Codec 序列化/反序列化数据。Data Attachments 可挂在 Entity、BlockEntity、Level、Chunk 上；持久化用 Codec，网络同步用 StreamCodec，并有同步目标策略。

Data Attachment 文档还指出附件值应使用不可变类型并通过 API 更新，否则可能无法正确持久化或同步。大型附件修改字段可能触发整个附件值重新同步。

参考：[Fabric 26.2 Saved Data](https://docs.fabricmc.net/26.2/develop/serialization/saved-data)、[Fabric 26.2 Data Attachments](https://docs.fabricmc.net/26.2/develop/serialization/data-attachments)。

### 3.3 Item Data Components

26.2 的 ItemStack 数据组件使用命名空间 ID 注册；持久化 Codec 与网络 StreamCodec 是两个独立定义。官方示例明确展示了一个 Integer 组件分别使用非负整数 Codec 和 VarInt StreamCodec，复合组件则分别定义 RecordCodecBuilder 与 StreamCodec。

所以同一个组件至少有三个身份：

1. Registry 中的组件 ID；
2. 持久化 Codec；
3. 网络 StreamCodec。

参考：[Fabric 26.2 Custom Data Components](https://docs.fabricmc.net/26.2/develop/items/custom-data-components)。

### 3.4 网络协议

Fabric 26.2 的现代自定义包路径是：

1. 定义带命名空间 ID 的 CustomPacketPayload；
2. 定义 StreamCodec；
3. 按 clientbound/serverbound 方向注册 PayloadTypeRegistry；
4. 在正确的网络阶段发送和处理。

StreamCodec 描述字节流的编码/解码顺序，不自动告诉编辑器业务语义、权限、状态机或服务端验证规则。

参考：[Fabric 26.2 Networking](https://docs.fabricmc.net/26.2/develop/networking)。

### 3.5 动态注册表与数据包

动态注册表由 JSON 数据包填充，使用 Codec 解码成运行时对象；注册表可以只在服务端，也可以同步给客户端，并允许使用不同的客户端 Codec。数据还与具体世界的 RegistryAccess 相关。

这要求 Schema IR 记录 Registry ID、当前上下文、客户端/服务端可见性和是否同步，不能把 Registry ID 当成普通字符串下拉框处理。

参考：[Fabric Dynamic Registry](https://docs.fabricmc.net/26.2/develop/registries/dynamic-registry)。

## 4. CodecUI 的能力边界与当前实验缺口

CodecUI 值得作为第一条 DFU Codec 适配路径，但不能当成“任意模组协议通吃”的总适配器。

其公开 Schema 类型包含：

- Bool、Color、IntRange、LongRange、FloatRange、DoubleRange、Str；
- ResourceId、TagId、Enum、Record、ListOf、MapOf；
- DispatchedMapOf、AnyOf、PairOf、OneOf、Ref；
- Opaque、Custom。

它支持显式 companion schema、SchemaHandler 和对常见 Codec 组合的推断；未知 Codec 会退化为 Opaque，而不是保证可编辑。

更重要的是，CodecUI 的 `SchemaCodecs.inferenceMode()` 区分：

- `MIXIN`：构造期 Mixin 捕获元数据，可获得较完整的字段/默认值信息；
- `REFLECTION`：反射回退模式，结构、字段名和数值范围仍可能恢复，但可选字段默认值会丢失。

上游源码还表明，CodecUI 通过 MethodHandles/VarHandle 读取 DFU 内部字段；分派 Codec 的变体枚举可能调用模组提供的 decoder 函数。故“Schema 推断”不是纯静态、零副作用的操作，必须在隔离实例中执行，并对动态枚举设置预算和权限边界。

参考：[CodecUI Schema](https://github.com/MehVahdJukaar/codecui/blob/8b3afabef7510e73b4b76de850a5819e60127691/src/main/java/net/mehvahdjukaar/codecui/Schema.java)、[SchemaResolver](https://github.com/MehVahdJukaar/codecui/blob/8b3afabef7510e73b4b76de850a5819e60127691/src/main/java/net/mehvahdjukaar/codecui/internal/SchemaResolver.java)、[MixinDetection](https://github.com/MehVahdJukaar/codecui/blob/8b3afabef7510e73b4b76de850a5819e60127691/src/main/java/net/mehvahdjukaar/codecui/internal/MixinDetection.java)。

### 对当前实验代码的具体审查

本轮代码审查发现并修正了两个 Schema 投影遗漏：

1. CodecUI 的 Schema 有 `Color(hasAlpha, hexString)`，此前投影器未覆盖，会被误判为 unsupported。
2. ResourceId/TagId 不只表示“是否受注册表约束”，还包含具体 Registry ResourceKey；此前只输出布尔值，会丢失上下文。

另一个边界需要保持明确：

- DispatchedMapOf 的 value schema 依赖 key，必须按键动态解析；本轮投影只保留 key schema 和“需要运行时 handler”的标记，不调用其函数。
- Custom widget 仅保留类型标识，不假设能安全序列化 widget 对象。
- Enum 标签函数不在投影阶段执行，避免调用模组回调。

## 5. Mod Studio 应采用的统一架构

### 5.1 不是单个 Parser，而是协议发现器 + 多适配器

建议建立以下层次：

```text
Installed Mod / Mod JAR / Config / World Copy / Datapack
                         |
                         v
                 Protocol Scanner
        (metadata + resources + bytecode index)
                         |
                         v
                 Adapter Registry
       +---------+---------+----------+----------+
       |         |         |          |          |
     DFU       Config     NBT       Network    Assets
    Codec     APIs/JSON  Storage    Stream     JSON
       |         |         |          |          |
       +---------+---------+----------+----------+
                         |
                         v
                  Unified Schema IR
                         |
              Validation / Provenance
                         |
             Editor / AI command planner
                         |
                 Capability Gate
                         |
        Validate -> Copy -> Apply -> Reload/Test
```

### 5.2 Schema IR 最少字段

每个节点除类型本身外，还应保存：

- `schemaVersion`、`gameVersion`、`loader`、`modId`；
- `dataDomain`：config / datapack / world / item_component / block_entity / network / asset；
- `sourceProtocol`：DFU_CODEC / MOD_CONFIG_SPEC / GSON / TOML / NBT_MANUAL / VALUE_INPUT_OUTPUT / STREAM_CODEC / CUSTOM；
- `storageFormat`：JSON / JSON5 / TOML / NBT / BYTEBUF / RESOURCE；
- `registryContext`、`worldScope`、`logicalSide`、`syncPolicy`；
- `fields`、`optional`、`default`、`range`、`pattern`、`enum`、`union`、`reference`；
- `readCapability`、`validateCapability`、`encodeCapability`、`writeCapability`；
- `provenance`：来自显式 Schema、CodecUI Mixin、反射、配置 spec、静态字节码、样本观察或人工 handler；
- `confidence` 与 `fidelity`，并保留无法理解的原始节点。

### 5.3 发现顺序

1. **静态资源扫描**：读取 fabric.mod.json / neoforge.mods.toml、嵌套依赖、data/、assets/、config 样本、pack.mcmeta。
2. **字节码索引**：用 ASM 扫描类常量池、字段描述符、方法签名、调用点；不为扫描而执行任意模组静态初始化。
3. **显式协议适配**：Codec、ModConfigSpec、AutoConfig/YACL Config API、ValueInput/Output、DataComponentType、StreamCodec。
4. **隔离运行时探测**：在 disposable instance 中收集已注册 Codec/Registry/Packet type 和配置 spec；给动态回调设置数量、时间和线程预算。
5. **人工 handler**：对 opaque/custom codec、私有配置库或特殊二进制协议注册专用适配器。

### 5.4 写回能力必须分级

| 等级 | 能力 | 允许的场景 |
|---|---|---|
| R0 | 识别/索引 | 任何已发现文件或类型 |
| R1 | 只读解析 | 未知协议、网络载荷、世界数据 |
| R2 | 结构化编辑 + 原协议验证 | JSON/TOML/Codec 数据包和配置 |
| R3 | 隔离副本写回 + 重载测试 | 世界副本、NBT、数据组件样本 |
| R4 | 运行时交互 | 仅经显式授权的命令/API handler；不允许通用任意包注入 |

任何未知字段必须原样保留；不能为了“统一 Schema”而丢弃它们。

## 6. 第一阶段实施优先级

### P0：先覆盖高价值、低风险路径

1. JSON / JSON5 / TOML 配置文件解析；
2. Mojang Codec / MapCodec Schema；
3. datapack JSON + Registry context；
4. 26.2 Item Data Components；
5. ValueInput/ValueOutput 的已知字段和 Codec 字段。

这些路径能覆盖大量可见、可编辑的数据对象，而且可以通过原始 serializer/codec 验证。

### P1：补充复杂状态

1. NBT 手写保存逻辑；
2. SavedData；
3. Data Attachments；
4. 动态注册表和按键分派 Codec；
5. 模组自定义配置库 handler。

### P2：只读优先

1. CustomPacketPayload / StreamCodec；
2. 旧式 PacketByteBuf / CustomPayload；
3. 私有二进制协议；
4. 任意运行时对象和反射字段。

网络数据包可以分析和记录，但默认不向服务端发送修改包。服务端权威、方向注册、状态机和校验逻辑不能由“字段看起来可编辑”推断。

## 7. 如何证明覆盖了“绝大多数模组”

不能凭几个成功案例宣布完成。建议构建一个固定、可复现的测试语料库：

- 30–50 个高下载量 Fabric 模组；
- 按性能优化、技术/机器、内容扩展、世界生成、UI/配置、库/API 六类分层；
- 每个模组至少检查配置、数据包/注册表、持久化、网络四类数据域；
- 记录发现协议、解析成功率、字段/默认值准确率、原始数据保留率、验证通过率和写回后重载成功率；
- 同时纳入“没有 Codec”“手写 NBT”“Opaque Codec”“动态 dispatch”“Mixin 未生效”等负样本。

关键指标：

```text
Protocol Detection Recall
= correctly_detected_protocols / audited_protocols

Schema Field Recall
= correctly_recovered_fields / ground_truth_fields

Schema Field Precision
= correctly_recovered_fields / all_reported_fields

Round-trip Preservation
= unknown_and_known_fields_preserved / input_fields

Safe Write Success
= validated_copy_reloads_successfully / write_attempts
```

“可读取”与“可编辑”必须分开统计；“能解析 JSON”不等于“理解了模组对象”。

## 8. 当前结论与下一步

- **已证明（官方规范）**：26.2 的 Codec/DynamicOps、StreamCodec 网络、Data Components、Data Attachments、SavedData、动态注册表和 Block Entity 持久化路径确实存在。
- **已观察（公开源码样本）**：多个代表性模组在同一项目内混用 Gson、Codec、NBT、StreamCodec；配置 UI 库也不一定拥有底层存储。
- **尚未证明**：这些路径在全体 Fabric 模组中的占比；CodecUI 对任意第三方 Codec 的推断成功率；所有未知数据是否可无损编辑。
- **建议**：先把本报告中的 Schema IR 和协议适配器分层落到独立实验分支，再建立 30–50 个模组的自动扫描语料库。不要把网络写入或任意 Java 反射作为第一阶段功能。

本报告是研究结论和实施设计，不代表尚未执行的编译、运行时或第三方模组实机测试已经通过。
