# Windows 本机外部 AI / MCP / Minecraft 实际验收报告

日期：2026-11-20（Asia/Shanghai）。结论：**受控临时专用服务器的核心 AI 调试闭环通过本次实测；仍有环境限制和诊断体验问题，不能据此宣布通用游戏控制或全平台验收完成。**

## 被测版本与执行方式

- 仓库：`tortletortle/minecraft-mod-studio`（私有）。
- 被测分支：`ai-debug-lab-v0.1`。
- 被测提交：`4d5e01d82547ec6fa4f8a6cfcf089ca0396e34ec`，2026-11-20 22:48:58 +08:00。
- 上传前于 2026-11-20 23:33 +08:00 通过 `git ls-remote` 复核，远端功能分支仍指向上述提交。默认分支为 `main`；本报告不表示功能已经合入 main。
- 报告分支：`test/local-ai-playtest-20261120`。本次仅新增报告、脱敏证据和验收辅助程序，未修改产品源码。
- 外部 AI 代理阅读真实工具发现结果，逐次决定并发起下一次调用；[交互转发器](interactive_mcp_host.py)通过官方 Python MCP SDK 的 stdio Client 连接产品 `playtest.py serve`。它只转发请求，没有预编排游戏动作或游戏断言。
- **未使用 `playtest_check.py` 冒充外部 AI 验收。** 游戏读取和写入全部经 MCP 工具；shell 仅用于构建、启动、读取日志、检查清理及整理报告，没有直接执行游戏/RCON 控制命令。

真实发现并调用了全部 **9 个工具**，共 **20 次调用**。其中 **3 次故意非法调用返回 isError**，其余 17 次正常响应；最初 3 个状态响应仍为 starting，不计作启动通过。只运行了 **1 个独立临时世界，启动器配置 seed 42**；未额外查询实际世界 seed。

## 测试环境与资源控制

| 项目 | 实测值 |
| --- | --- |
| OS | Windows 11，10.0.26200 |
| Python / MCP SDK | 3.12.10 / 2.3.0 |
| Java | Eclipse Temurin 25.0.5+8 |
| Gradle / Fabric Loom | 9.5.1 / 1.17.12 |
| Minecraft / Fabric Loader | 26.2 / 0.20.1 |
| Fabric API / 调试探针 | 0.161.0+26.2 / 0.3.0 |
| 测试服务器堆 | `-Xms512M -Xmx2G` |
| 子进程 CPU 上限提示 | `JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=4` |
| 构建资源 | `--max-workers=1`，JVM `-Xmx768m -XX:MaxMetaspaceSize=384m` |
| 实例隔离 | 新建临时世界，游戏/RCON 只监听 127.0.0.1，随机端口和随机密码 |

Java/PATH 只对测试子进程指定，未修改全局环境变量，未终止用户原有程序、未使用个人存档。这里的资源约束是减少本次测试干扰，不是经过基线对照验证的性能优化结论。

`prepare` 下载官方资源，Mojang server 下载路径执行 size/SHA1 检查；四个顶层资产保存 SHA256，serve 在复制前后核对。实际探针由本地 Gradle 构建，SHA256 为 `f64b35f34739a65737d107989489b0beefcc69c19d2a3e2da1206f091c57298c`。完整清单见 [asset-hashes.json](evidence/asset-hashes.json)。

## 实际操作与结果

完整原始结构的脱敏请求/响应见 [mcp-transcript.jsonl](evidence/mcp-transcript.jsonl)，简明时序见 [call-index.json](evidence/call-index.json)。请求编号可直接检索 JSONL 的 `id` 字段。

| 请求 | 操作 / 预期 | 实际结果 |
| --- | --- | --- |
| 001、003、004 → 005 | 等待服务器和探针就绪，使用实际返回的 session | starting 后变为 ready；session 为 `7d360a6c-9c8d-409d-ab46-42427ae25392` |
| 002 | 读取测试 mods 静态清单 | 发现 Fabric API、`mms_playtest` 1.0.0、`mms_debug_probe` 0.3.0；无重复声明 ID |
| 006 | 验证 `mms_playtest:gem`、planks tag 及精确配方实验 | 配方 present；tag 完整列出 12 项且包含 oak_planks；stone＋oak_planks 匹配并输出 emerald ×1 |
| 007 | 记录初始原生快照 | tick_callbacks=2100，目标 chunk_not_loaded；没有把未知状态当成 air |
| 008 → 009 | 经 MCP 设置 chest，再回读原生快照 | 动作 verified；快照 tick=2800，方块 chest，block_entity_type=chest |
| 010 → 011 | 经 MCP 替换为 stone，再回读 | 动作 verified；快照 tick=3300，方块 stone，旧 block_entity_type 字段消失 |
| 012 | 冻结负对照，再精确推进 `[2,7]`，最后恢复 | 冻结时 3493→3493；step 2 为 3493→3495；step 7 为 3495→3502；status=passed，cleanup=verified_running |
| 013 | 独立于动作返回值，再观察 ticks/gametime 两次 | 两次 running normally；gametime 3713→3719，确认继续推进 |
| 014 | 尝试非白名单 `minecraft:tnt` | SDK literal 校验拒绝，isError=true |
| 015 | 尝试布尔步数 `[true]` | StrictInt 校验拒绝，isError=true，没有被当作整数 1 |
| 016 | 尝试超限步数 `[101]` | 运行时步数预算拒绝，isError=true；返回错误过于笼统，见问题清单 |
| 017 | 非法调用后回读世界 | tick=4900，仍为 stone，无箱子实体；世界继续运行 |
| 018 | 读取配方诊断，核对其可信边界 | 成功返回 hypotheses_only；未把 tag 未知假设当作配方失效，但暴露能力元数据陈旧问题 |
| 019 | 仅用本轮一个 seed 的实际实验记录做汇总 | observed=1，valid=1，label=insufficient；未虚构多次独立试验或统计显著性 |
| 020 | 结束前再次查询状态 | 仍 ready，随后正常关闭 MCP 上下文 |

探针每 100 tick 发布一次快照，所以以快照时间、tick 和方块状态确认读取的是动作后的数据。本轮快照时间依次推进：15:18:53Z → 15:19:28Z → 15:19:53Z → 15:21:13Z。真实运行时注册表报告 44 个 mod 条目（包含 Fabric 子模块）、1537 items、1196 blocks、158 entity types、49 block entity types；这与静态顶层 3 个 JAR 的统计口径不同。

有效写动作共 **3/24**：chest、stone、tick experiment。三次非法输入后，[actions.jsonl](evidence/actions.jsonl) 仍只有 sequence 1、2、3；没有额外占用写预算。

## 构建、单元测试与清理

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| 探针实际 Gradle build | PASS，1m 3s，4 tasks executed | [probe-build.log](evidence/probe-build.log) |
| Python `test_*.py` | **64 PASS / 1 ERROR / 0 assertion failures，进程 exit 1** | [结果](evidence/unit/result.redacted.json)、[stderr](evidence/unit/stderr.redacted.log) |
| 官方 MCP SDK 兼容性检查 | 3/3 PASS，包含实际 stdio 子进程 | [结果](evidence/unit/mcp-result.redacted.json)、[stderr](evidence/unit/mcp-stderr.redacted.log) |
| 真实 AI / MCP / Minecraft 核心流程 | 本文逐项通过；单世界、单 seed 的 smoke 验收 | [完整调用记录](evidence/mcp-transcript.jsonl) |
| 正常关闭 | MCP context closed，日志正常 stop/save，测试 Java、host、MCP 进程均已退出，临时世界不存在 | [清理检查](evidence/cleanup-check.json)、[关闭记录](evidence/host-closed.json)、[服务器日志](evidence/server.log) |

Gradle 日志中的 compileTestJava/test 均为 NO-SOURCE；构建成功不代表运行过 Java 单元测试。Python 单测、MCP 协议检查与本次真实服务端验收是不同层次的证据。

唯一单测 ERROR 为 `test_ide_bridge.BridgeTests.test_symlink_denied`：`test_ide_bridge.py:47` 创建符号链接时发生 WinError 1314，尚未执行第 48 行被测拒绝逻辑。这是**未覆盖的 Windows 权限边界**，不能说全套单测通过，也不能直接说产品断言失败。未通过提权或修改开发者模式绕过。详见 [unit-summary.md](evidence/unit-summary.md)。

服务器在本地时间 23:22:01 收到正常停止，23:22:02 保存各维度并关闭 RCON；23:22:18 复查确认测试进程和临时世界均已清理。没有运行进程名批量结束或关闭用户程序的操作。

## 发现的问题与建议优先级

1. **中：冷启动慢且依赖网络。** Java 23:13:18 创建，23:16:54 才出现 Fabric Loader 日志，23:17:07 Done，总计约 229 秒。日志出现主 Fabric Maven 的 experimental_versions.json Read timed out、备用地址 DIRECT failed，随后仍成功启动。它不是启动失败，但接近现有 300 秒状态等待窗口。`prepare` 只保存四个顶层 JAR，新的临时目录仍需 Fabric runtime 引导；建议单独缓存并校验官方 libraries 或预热，并把下载/引导阶段暴露为明确状态。缺少逐下载时间戳，不能把全部 229 秒归因于单个域名。
2. **中：配方诊断的能力计划落后于新增探针。** 请求 018 仍给出 tag_resolution_unknown，并把 query_active_recipe/query_active_tag_members/test_recipe_in_disposable_instance 列为未实现；同一会话的 006 已有真实 recipe/tag/内存实验结果。诊断保守但缺乏关联，建议将已有目标探针证据接入计划，精确标注“仅配置目标/内存实验”的支持范围，避免误导 AI 重复规划。
3. **低：运行时步数越界错误不够明确。** `[101]` 被保护逻辑拒绝，世界未改变，但 MCP 仅返回 Error executing tool playtest_tick_steps；host stderr 显示 ValueError: step budget exceeded 被包装为 unexpected exception。建议转成稳定、可理解的 ToolError，说明每步 1–100、总计 ≤200，而不暴露堆栈。
4. **低：超平坦生成配置日志有 ERROR。** 首次建世界出现 No key layers in MapLike[{}]；服务端和本轮固定坐标测试仍成功。未验证地形层是否符合产品期望，不应据此宣称地形正确。建议显式提供 generator-settings.layers 或调整测试世界定义。
5. **环境缺口：Windows symlink 测试没有执行到目标逻辑。** 后续可在具备符号链接权限的受控 runner 补验，或在无权限时将 fixture 建立失败明确标为 skip 并由另一项环境补足。单纯跳过不能当作该边界通过。

本次报告不顺带修改上述产品逻辑，保留被测提交与证据的一致性。

## 能力边界

- 这是本机临时**专用服务器**的受控调试验收，不是桌面客户端/渲染/FPS、玩家移动、真实工作台交易或个人整合包兼容性验收。
- 写能力仅包括固定 Overworld 坐标 `(0,80,0)` 的 chest/stone/air 与有预算 tick 步进。本轮实测 chest、stone；**air 分支和 24 次预算耗尽没有实际触发**。
- RecipeProbe 的 matches/assemble 在真实服务端内存执行，不修改玩家背包；不能表述成玩家已在工作台成功合成。
- 没有多 seed、多次独立世界、长时间 soak、多人、客户端、崩溃恢复或跨 OS 复验；本轮取样的 tick 原始数值不能作为性能基准。
- 工具诊断输出是证据和假设，不是指令或自动修复结果。本轮未验证自动改代码、重新构建、通用模组故障定位能力。
- 普通测试和 MCP 检查日志里的负面请求是有意测试；不应把它们计作未说明的产品失败。

## 复核方式与证据处理

在本报告目录运行 `python verify_evidence.py --output verification.json`，可复核捕获日志之间的一致性和证据哈希。**这是离线审计，不是第二次游戏试验。** 结果见 [verification.json](verification.json)。

重新实际试验需按被测版本的 `ai-debug-lab/AI_PLAYTEST.md` 准备探针与资产。可使用本目录交互转发器：`python interactive_mcp_host.py --repo <repo> --assets <prepared-assets> --out <new-evidence-dir>`，等待 host-ready.json，逐次写入 requests/001.json 等请求，再检查 responses/001.json；每个请求的内容为 name 与 arguments。结束时创建 shutdown.request，让 MCP 上下文正常退出。必须使用新的输出目录，避免复用已处理请求。启动器涉及的 Minecraft EULA 应在重新运行前审阅。

只上传经过选择和脱敏的文本证据：个人 home 路径替换为 `<USER_HOME>`；RCON 密码、server.properties、个人存档、游戏 JAR、构建缓存均未纳入。server.log 的启动器早期文本使用平台编码，上传副本以 UTF-8 replacement 解码，保留其余英文警告及时间线；原始字节仅留本机。MCP 响应保留 content 与 structuredContent 的原有重复表示，便于完整审计。

各证据文件 SHA256 见 [evidence-sha256.json](evidence-sha256.json)。哈希用于检查这份快照的文件完整性，不是外部签名或独立可信证明。
