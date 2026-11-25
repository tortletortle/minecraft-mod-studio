# AI Debug Lab 第三轮 Windows 实机测试报告

测试日期：2026-11-21（Asia/Shanghai）  
仓库：tortletortle/minecraft-mod-studio  
被测分支：ai-debug-lab-v0.1  
被测提交：092f5656c51ea66016ee313630ec1807c49e2255  
测试分支：test/ai-debug-coldstart-round3-20261121

## 结论

本轮在同一 Windows 主机、相同源码和固定资产下完成了 3 次没有实例级 Fabric runtime 缓存的真实启动，另做了 3 次预置完整运行库缓存的真实启动。前者 MCP 报告 ready 的时间为 90.953–149.375 秒（中位数 115.375 秒）；预置缓存后为 24.110–25.797 秒（中位数 25.672 秒）。缓存对照的中位数低约 77.7%。该结果显示每实例重新引导 Fabric 运行库是主要可优化区段；它不是产品已实现缓存后的性能承诺，也不代表离线启动已经验证。

启动日志中的 Fabric Maven 请求超时在 3 次干净启动中出现 2 次，缓存启动中未出现；但没有逐请求耗时，也有一次未记录 Fabric 超时的干净启动仍耗时 115.375 秒。网络等待是重要候选因素，现有证据不足以认定它是唯一瓶颈或量化它的单独贡献。Minecraft 的 Loading Minecraft 到 Done 阶段稳定在约 15.8–17.4 秒，世界/服务器启动、探针就绪所占时间远小于启动前段。

本报告仅记录测试与根因分析，没有改动产品源码。所有运行均使用 Debug Lab 创建的临时服务端世界；没有打开或改写个人存档，没有终止无关进程。共享证据中的本机用户目录已替换为 <USER_HOME>；未经处理的本机源记录仍在测试主机的原始证据目录。

## PR #3 / #4 历史基线

用户要求先读的两份实机报告已核对：

| 来源 | 被测提交 | 真实服务器结果 | 边界 |
| --- | --- | --- | --- |
| [PR #3 报告](https://github.com/tortletortle/minecraft-mod-studio/pull/3) | 4d5e01d82547ec6fa4f8a6cfcf089ca0396e34ec | 1 个临时 Fabric 26.2 世界；9 个 MCP 工具、20 次调用；报告冷启动约 229 秒 | Python 64 PASS、1 个 Windows symlink 权限 ERROR；仅单世界单样本 |
| [PR #4 报告](https://github.com/tortletortle/minecraft-mod-studio/pull/4) | 092f5656c51ea66016ee313630ec1807c49e2255 | 1 个临时 Fabric 26.2 世界；46 次 MCP 调用；报告冷启动 372.828 秒 | 72 项 Python 测试中 71 PASS、1 SKIP；没有实测 600 秒超时分支 |

两份历史启动数字各只有一个样本，不能说明性能趋势。本轮把当前被测提交和环境固定后重复三次，以弥补该缺口；历史报告未提供足以与本轮逐项匹配的下载阶段记录。

## 环境与控制变量

| 项目 | 固定值 / 说明 |
| --- | --- |
| 操作系统 | Windows 11，10.0.26200 |
| Minecraft / Fabric Loader | 26.2 / 0.20.1 |
| Java | Eclipse Temurin 25.0.5+8 |
| Python / MCP SDK | 3.12.10 / 2.3.0 |
| JVM CPU 提示 | -XX:ActiveProcessorCount=4，仅作用于测试子进程 |
| 源码 | ai-debug-lab-v0.1，092f5656c51ea66016ee313630ec1807c49e2255 |
| 固定输入资产 | fabric-server.jar、server.jar、fabric-api.jar、probe.jar；逐次记录的 SHA-256 与测试资产清单一致 |
| 隔离 | 每次新建 Debug Lab 临时世界与私有临时目录；仅测试服务器自己的 127.0.0.1 端口 |

干净运行的 instance runtime_seed 记录为 null，表示该实例开始时没有种入 Fabric 运行库。它不是操作系统级的全盘冷缓存：没有清空系统 DNS、磁盘或网络缓存。缓存对照将一份完整运行库（.fabric、libraries、versions）复制到新实例临时目录，游戏资产、源码、JDK、JVM 选项和测试步骤不变。每组都连续真实启动 3 次；运行之间正常关闭并清理临时世界。

缓存对照是验证运行库缓存价值的实验夹具；产品当前仍为每个调试实例创建独立临时目录，因此本实验不证明产品现在会跨实例复用缓存。所有 6 次启动均由真实 JVM 加载 Fabric、Minecraft 和 Debug Probe，并通过 MCP 状态轮询达到 ready；没有用模拟 server 或静态代码分析代替实测。

## 冷启动与缓存对照

启动时间统一取 MCP status 中首次锁存的 ready_elapsed_s；它包含启动器、Fabric、Minecraft、世界/服务器、探针及轮询观测延迟。不要用 run.json 的 duration_s 代替：该值还包含启动后的操作、关闭和记录过程。下面各阶段时间来自独立的进程日志标记，测量点是观测时间而不是 JVM 内部精确计时。

| 条件 / 样本 | 首次 Fabric 解包日志 | Loading Minecraft | No worlds / server startup | Done | MCP ready | Fabric timeout 日志 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 干净 1 | 124.875 s | 128.515 s | 143.531 / 144.672 s | 145.875 s | 149.375 s | 39.390 s，出现 |
| 干净 2 | 91.578 s | 94.860 s | 109.141 / 110.281 s | 111.141 s | 115.375 s | 未观察到 |
| 干净 3 | 66.735 s | 70.000 s | 84.735 / 85.828 s | 86.688 s | 90.953 s | 29.563 s，出现 |
| 缓存 1 | 无 | 5.219 s | 20.265 / 21.359 s | 22.172 s | 25.672 s | 未观察到 |
| 缓存 2 | 无 | 4.375 s | 18.360 / 19.422 s | 20.219 s | 24.110 s | 未观察到 |
| 缓存 3 | 无 | 5.203 s | 19.938 / 21.328 s | 22.156 s | 25.797 s | 未观察到 |

Loading Minecraft → Done 分别为：干净运行 17.360、16.281、16.688 秒；缓存运行 16.953、15.844、16.953 秒。Loading Minecraft → No worlds 为 14.281–15.016 秒，随后 No worlds → Starting server 约 1.09–1.14 秒。Done 到 MCP ready 为 3.500–4.265 秒；它包含 probe/RCON 健康检查和轮询延迟，当前无法进一步拆出探针纯初始化时间。

三次干净运行的 ready 中位数 115.375 秒、均值 118.568 秒；缓存组中位数 25.672 秒、均值 25.193 秒。样本数较小，且同一主机顺序运行，结果是本环境内的可复现实验观察，不应外推为总体性能分布。

### Fabric、依赖与网络判断

- 3 次干净运行的启动时间主要消耗在 Loading Minecraft 日志出现之前：该标记出现在 run 开始后 70.000–128.515 秒；Fabric 第一次解包日志出现在 66.735–124.875 秒。这个时间段涵盖 Fabric 引导及依赖准备，日志不足以将下载、重试、解包和类加载各自精确计时。
- 干净运行 1、3 在 39.390、29.563 秒左右记录到 Fabric Service 对 maven.fabricmc.net 请求读取超时；2 次都继续启动成功。干净运行 2 未记录此警告，但仍有约 91.6 秒才出现首个解包日志，说明该警告不是长启动的必要条件。
- 6 次启动记录均存在启动进程对外 TCP/443 连接的观察；缓存组虽然 ready 更快，仍有外联。单次网络采样只说明存在连接，不提供 HTTP 请求的完整时间线、内容或因果关系。
- 曾尝试只对测试 JDK 建立 Windows 防火墙阻断规则以验证完全离线启动，但系统拒绝该操作；未改变防火墙。故离线启动结果为“未验证”。当前实验只支持“预置运行库显著降低启动时间”，不支持“可断网运行”。
- 产品每实例使用新临时目录，.fabric/server 和 Fabric 依赖闭包不会由该实例自然复用；顶层 server、Fabric server、API、probe JAR 不能替代完整 Fabric runtime。建议优先测试受版本与哈希约束的共享 runtime cache，并将离线优先作为缓存完整性通过后的策略。
- 代码核查补充：Fabric Installer 默认从运行目录下的 .fabric/server 读取 26.2-server.jar、fabric-loader-server-0.20.1-minecraft-26.2.jar 以及该 loader JAR 的 MANIFEST Class-Path 闭包；顶层复制的 server.jar 默认不是它的缓存命中。Installer 默认主要检查路径和 Manifest 可读性，不自行提供 SHA-256 完整性保证，因此共享缓存必须由产品维护版本键、文件清单和哈希校验。

## 稳定性与失败路径

### 600 秒启动超时及恢复

这是有意构造的超时/恢复机制测试，不是自然网络故障复现：启动真实测试 JVM 后，测试驱动只暂停自己创建的 Java PID 601.34 秒。MCP 在 601.437 秒报告 startup_timeout（阈值 600 秒）；恢复同一个 JVM 后，在总启动时间 775.203 秒报告 ready，恢复后约 125.484 秒。PID 和创建时间匹配，确认恢复的是同一个被测 JVM。

之后测试只终止这次试验创建的 JVM，MCP 观察到 stopped，监听端口消失；最终清理记录确认 Java 与启动器进程都已退出、临时世界不存在。停止回执瞬间 world_present 仍为 true，随后 final_cleanup 才记录 false，因此报告把“关闭后最终删除”作为结论，不把删除说成与停止回执同步完成。

### 异常进程退出、重复启动与临时资源

- 三次干净运行、三次缓存运行以及恢复测试均记录了自有测试进程、监听端口和临时世界的最终清理状态；个人存档路径未作为输入。
- 超时/恢复测试对自有 JVM 强制终止后，启动器完成最终清理；此测试覆盖了进程意外终止后的清理路径，但不等价于 Windows 崩溃、断电或 launcher 自身被强杀的全部故障模式。
- 3 次缓存启动重复执行，没有发现遗留 Java PID、游戏监听端口或临时世界。使用隔离 TEMP 的一组留下了 JNA native DLL 临时目录；这不是世界泄漏。继承系统 TEMP 的复核没有增加 JNA 目录。
- 没有调用按进程名批量终止、taskkill 无筛选或其他可能影响用户程序的命令。

### 操作预算耗尽

首次真实功能流程的 actions.jsonl 记录 3 个有效写动作；随后单独的 budget-actions.jsonl 记录第 1–21 次写入调用成功，与前 3 次合计达到全局 24 次成功写动作。预算实验后续第 22–25 次调用均返回“Error executing tool playtest_set_block”，且没有写入动作成功记录。状态和只读查询仍可用。机制确实阻止了额外修改，但用户无法从错误文本判断原因；建议返回明确、稳定的预算耗尽错误和剩余预算信息。

## 事实、推断与仍未确定的问题

**观察事实：** 3 次无实例运行库缓存的启动为 90.953–149.375 秒；复制完整运行库后的 3 次启动为 24.110–25.797 秒。Fabric Maven 超时日志 3 次中有 2 次，缓存组 0 次；Loading Minecraft → Done 在 6 次中为 15.844–17.360 秒。预置缓存的启动仍观察到外部 443 连接。所有测量和日志都保存在 evidence 目录。

**合理推断：** 启动瓶颈主要在 Fabric bootstrap/runtime 依赖准备阶段；本机完整 runtime cache 是高价值优化方向。缓存组并未明显缩短 Minecraft 自身 Loading Minecraft → Done 阶段，因此该段不是本轮长冷启动差异的主因。Fabric 超时可能增加部分 run 的等待，但并非唯一原因。

**尚不确定：** 每个下载请求的开始/结束/字节数/重试次数，Fabric cache 缺失时到底有多少时间花在网络、校验、解包或类加载；离线可启动所需的最小完整依赖闭包；加载探针的独立纯耗时；更广泛硬件、网络下的性能分布；launcher 自身异常退出后的所有临时文件清理路径。不能从现有样本判断超时警告对启动时间的精确因果效应。

## 优化建议（本轮不改产品代码）

1. 为 Minecraft / Loader / Fabric API / Probe 版本以及输入资产哈希建立共享运行库缓存键；以原子填充、跨进程锁、完整性校验和只读快照避免并发下载和半成品复用。
2. 首次缺缓存时联网准备并验证完整依赖闭包；命中且校验通过时优先离线启动，遇到缺件再明确回退联网。先用无外网对照试验证明该闭包完整，再宣称离线支持。
3. 增加下载级遥测：URL 主机、artifact 标识、字节数、尝试次数、起止时间、状态/异常类型、缓存命中率；按 Bootstrap、Fabric load、world/server ready、Probe ready 展示阶段持续时间。
4. 用同版本同机的随机交替顺序做“空 runtime cache / 预热 runtime cache / 明确禁网缓存启动”对照，并保留每请求 trace；再做一次有可控延迟/拒绝请求的受控故障实验，区分超时与纯解包/CPU耗时。
5. 为工具预算错误返回机器可读的预算类别、已用数量和上限；不执行动作的拒绝仍须可由只读诊断确认。
6. 检查隔离 TEMP 下 JNA native DLL 的清理时机，确保只删除本测试实例拥有的文件。

## 证据索引与复核

- evidence/cold-clean-1 至 cold-clean-3：三次无实例 runtime cache 的启动轮询、完整服务器日志、资产/进程/清理信息。
- evidence/cache-seeded-1 至 cache-seeded-3：三次完整运行库预置对照；第一组额外包含动作与预算记录。
- evidence/cache-inherited-temp：继承 TEMP 的文件清理复核。
- evidence/stability-timeout-recovery：MCP 转录、暂停/恢复/终止事件、服务器日志和最终清理观察。
- manifest.json：被测源码分支/提交、输入资产哈希和运行环境版本；用户主目录已归一化为 <USER_HOME>。
- scripts/round3_coldstart.py、scripts/round3_server_wrapper.py、scripts/round3_stability.py：记录实验驱动与观测逻辑。重新运行需要 Windows 环境、被测源码、匹配资产及 JDK；本分支不上传游戏二进制、构建缓存、EULA 或个人存档。
- evidence-sha256.json：证据文件与实验脚本的 SHA-256 清单；运行 python reports/ai-debug-lab-round3-20261121/verify_evidence.py 复核文件哈希和隐私路径扫描。该检查只审计已捕获证据，不是额外 Minecraft 实机试验。

共享日志只对本机用户目录做字面路径替换，其他日志/响应结构保持不变。原始日志仍保留在本机测试源目录；GitHub 分支包含便于审查的路径归一化副本，不包含 server.properties、RCON 密码、个人存档、游戏 JAR 或构建运行库。
