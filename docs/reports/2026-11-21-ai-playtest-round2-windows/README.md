# Windows 本机外部 AI / MCP / Minecraft 第二轮验收报告

日期：2026-11-20 至 2026-11-21（Asia/Shanghai）。被测提交 **092f5656c51ea66016ee313630ec1807c49e2255**，来自 ai-debug-lab-v0.1，包含上一轮问题修复。

2026-11-21 00:22 +08:00 fetch 确认 GitHub 功能分支 tip 仍为该提交；报告分支从此版本派生。默认分支 main 未因此更新或合并。

结论：**第一轮发现的配方证据关联、步数边界错误和启动遥测修复，在真实临时 Minecraft 服务器上通过；空气方块和 24 次写动作预算也通过。冷启动仍然很慢，本轮没有声称性能改善。**

## 执行范围

- 外部 AI 逐次查看 MCP 返回结果并选择下一步，使用官方 Python MCP SDK stdio Client；交互 host 只转发请求，没有预编排游戏动作或断言。
- 真实发现 9 个工具，本轮实际调用其中 8 个（未重复 trials_summarize，因为只有一个临时世界）。共 **46 次 MCP 调用**，其中 5 次预期拒绝：步数 101、总计 201、步数 0、布尔步数及第 25 个写动作。
- 运行 1 个新的临时 Fabric 26.2 专用服务器；seed 42 是启动器配置值，没有查询个人世界或实际世界 seed。
- 游戏读写全部经 MCP；shell 只用于构建、检查日志/进程/清理及整理报告。

## 第二轮修复验证

### 配方证据关联

调用 007 确认 minecraft:planks 标签完整列出 12 项；stone + oak_planks 的服务端内存 matches/assemble 实验 matched，输出 emerald ×1。

调用 009 的 mods_diagnose_recipe 正确关联同一快照：runtime_recipe.status=present；runtime_item_tag.status=present 且 complete=true；标签引用状态 runtime_tag_members_available；in_memory_experiment.status=matched，输出 minecraft:emerald ×1；hypotheses 为空。plan.covered_by_configured_snapshot 包含 query_active_recipe 和 query_active_tag_members，仍保留 verify_loaded_jar_hashes、inspect_datapack_order、test_recipe_in_disposable_instance。内存实验不等于玩家工作台交易。

对未配置配方 mms_playtest:not_configured（010）检查：runtime_recipe、runtime_item_tag、in_memory_experiment 全部为空，覆盖列表为空，仅报告 no_indexed_declaration，没有串用 gem 证据。

### 启动遥测

首次状态 001 为 starting；337.093 秒时 005 进入 waiting_for_probe；372.828 秒时 006 ready，并返回真实 session 56e6a48f-f631-42d0-9888-9f3066d4370e。响应包含 timeout_s=600、锁存的 ready_elapsed_s=372.828、network_warning_observed=true 及实际观测到的 waiting_for_probe → ready 阶段转换。字段明确表示阶段为轮询观测，不是逐下载计时。Fabric Maven 日志仍有 Read timed out，最终仍成功启动。

约 373 秒是本次一次冷启动观测，不能据此声称性能回归或改善；600 秒 timeout 分支没有被人为等待到。ready 后仍在运行时 elapsed_s 会继续增长，启动时长应读取 ready_elapsed_s。

### 方块与 tick 控制

- 008 初始固定坐标为 chunk_not_loaded，没有误判为空气。
- 011→012 经 MCP 设置 chest，原生快照观察到 minecraft:chest 及其 block_entity_type。
- 013→014 经 MCP 设置 air，原生快照观察到 minecraft:air，没有残留方块实体字段。
- 019 的冻结负对照保持 7031→7031；精确步进 [3,9] 分别得到 7031→7034（delta 3）和 7034→7043（delta 9）。实验 status=passed、cleanup=verified_running。
- 020 恢复后两次观察均为 running normally，gametime 7048→7053。

### 参数拒绝与动作预算

015、016、017 对 [101]、[100,100,1] 和 [0] 都返回稳定文本：Step budget exceeded: 1–10 entries, each integer 1–100, total at most 200. 拒绝发生在动作前。018 对 [true] 由 StrictInt 拒绝，没有把 bool 当作整数 1。

有效写动作共 **24/24**：最初 chest、air、tick experiment 三个动作，加上 21 次交替 air/chest 写入。042 是第 25 个写动作，返回 isError=true；之后 043 状态仍 ready，044 原生快照可读，045 tick 观察仍显示 running。动作账本没有增加第 25 条成功动作。

预算耗尽后只读诊断仍可用；但第 25 个写动作的 MCP 文本仍是笼统的 Error executing tool playtest_set_block，这是剩余的低优先级错误提示问题。

## 构建与测试

| 验证 | 结果 |
| --- | --- |
| Python test_*.py | 72 项：71 PASS、1 显式 SKIP、0 ERROR、0 FAIL，exit 0 |
| Windows symlink 边界 | WinError 1314 时显式 SKIP；该断言未执行，未计为通过 |
| Windows junction 边界 | 实际创建 junction，执行拒绝检查并通过 |
| MCP 兼容性 | 4/4 PASS，含真实 stdio 子进程；预算参数测试使用 Fake，不代替本次真实服务器预算实测 |
| 探针构建 | 15.141 秒成功；JAR 12,052 bytes，SHA256 f64b35f34739a65737d107989489b0beefcc69c19d2a3e2da1206f091c57298c |
| Java 测试 | compileTestJava、test 均 NO-SOURCE；没有 Java 测试用例执行 |
| GitHub CI | 被测提交 092f565 上相关 Windows、MCP、native 和 playtest 工作流显示 success；与本次外部 AI 实测分开记录 |
| 清理 | MCP context closed；测试 Java、host、MCP 进程已退出；临时世界删除；服务器保存各维度并关闭 RCON |

## 剩余边界

- 本轮只有一个独立世界；46 次 MCP 调用不代表 46 次独立试验。
- 未验收客户端渲染、玩家移动、多人、第三方整合包、跨操作系统、崩溃恢复或真实工作台交易。
- 24 次写预算拒绝有效，但第 25 次错误文本仍可改善。
- 配方诊断明确不验证通用已加载 JAR 哈希、datapack 顺序或玩家交易；这些是保留的范围边界。
- 启动仍受 Fabric runtime 引导和网络影响。本轮观察到 372.828 秒 ready；没有实施缓存优化或建立统计基线。
- 首轮冷启动观测为 229 秒，本轮为 372.828 秒；每个版本都只有一个环境样本，不能据此归因版本造成性能变化。

## 证据

- [脱敏 MCP 转录](evidence/mcp-transcript.jsonl)
- 调用索引及动作账本：[call-index.json](evidence/call-index.json)、[actions.jsonl](evidence/actions.jsonl)
- 启动遥测与服务器日志：[startup.json](evidence/startup.json)、[server.log](evidence/server.log)
- 单测摘要与脱敏日志：[unit-summary.md](evidence/unit-summary.md)、[unit evidence](evidence/unit/)
- 构建记录：[probe-build.json](evidence/probe-build.json)、[probe-build.log](evidence/probe-build.log)
- [SHA256 清单](evidence-sha256.json)
- [离线复核脚本](verify_evidence.py)；其输出 [verification.json](verification.json)

仅上传经过选择和脱敏的文本证据；未包含 server.properties、RCON 密码、个人存档、游戏 JAR、构建缓存或未脱敏单测日志。离线复核用于检查本次捕获证据一致性，不是第二次游戏试验。
