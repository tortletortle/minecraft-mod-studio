# Minecraft Mod Studio V0.12.2 · 第四轮 Windows 实机验收

- 验收日期：2026-11-21（Asia/Shanghai）。产品候选分支：feature/ai-debug-runtime-cache-v0.12.2。受测提交：3d265d533a412b453cc0b835b66a05c6f10126ad（[产品 PR #6](https://github.com/tortletortle/minecraft-mod-studio/pull/6)）。
- 本报告、测试脚本和脱敏证据属于独立验收分支。所有测试实际运行候选提交原有的 playtest.py serve，未修改产品源码。

## 验收结论

**V0.12.2 通过本轮 Windows 实机验收。** 10 次均启动真实 Minecraft 服务端、到达 MCP ready 并完成原生探针配方查询。三组冷／热缓存状态符合预期；故意损坏的缓存被拒绝、清理并重建；两个并发实例共用缓存时只发布了一份有效条目。[原始驱动摘要](evidence/summary.json) 对损坏恢复标为 false 并退出 1，原因是测试脚本额外要求重建 JAR 与原件逐字节一致；[独立复核](evidence/corrupt-recovery-postcheck.json) 证实该断言只被新生成的 ZIP 时间戳触发。原始结论保留，产品判定依据见损坏恢复章节。

## 环境与测量方法

同一台 Windows 11（10.0.26200，AMD64）主机，使用第三轮原有 Temurin 25.0.5+8、Python 3.12.10、MCP SDK 2.3.0，Minecraft 26.2、Fabric Loader 0.20.1、Fabric Installer 1.1.2。四个 JAR 的 SHA-256 与第三轮相同，并在本轮启动前重新计算验证；详见 [environment.json](evidence/environment.json)。JVM 子进程继续使用 -XX:ActiveProcessorCount=4，每次单独设置 TEMP/TMP/TMPDIR 并由产品生成新的平坦世界。没有清空 OS/DNS 缓存，网络未阻断，也没有固定网络负载。psutil 7.2.2 仅用于本机测试子进程和套接字的观察。

三组主实验依次运行，每组新建一个空的测试缓存根目录，冷启动与热启动在同组复用这个目录；组间不共享缓存。每次新建独立 MCP stdio 子进程，经官方 Python SDK 初始化和发现工具，每约一秒调用 playtest_status，收到 ready 后调用 game_recipe_status 读取原生探针配方实验。Minecraft 原始日志的 Done 与 MCP 探针返回共同确认服务器启动成功。每次都由 MCP 关闭输入触发产品关服和世界清理。

| 计时 | 起点 → 终点 | 用途 |
| --- | --- | --- |
| 请求 → ready | 驱动请求启动 MCP 子进程 → 收到首次 ready 响应 | 主指标。包含 MCP 启动、缓存校验与复制、JVM、探针轮询；MISS 时还包含 ready 响应前同步写缓存 |
| 产品 ready | Playtest 构造开始 → ready 状态锁存 | startup.json 的 ready_elapsed_s；含实例准备与缓存恢复，**不含**随后同步发布缓存 |
| JVM → ready 文件 | Windows 观察的 java.exe 创建时间 → 首次已就绪 startup.json 的文件写入时间 | 辅助对照，接近第三轮 JVM 启动至探针 ready 的界限；使用 Windows 文件时钟，两者不是完全相同的计时实现 |

分阶段数据取自 startup.json 的轮询观察点；Fabric 加载是首次观察到 Loading Minecraft，探针等待是首次观察到 RCON 已应答、快照尚未就绪。它们不是每次下载或类加载的独立内部计时。网络核对使用原始服务端日志和约两秒采样一次的公网 TCP 连接状态，只记录端口和状态。日志出现 Mojang 环境 URL 并不证明存在对应请求，连接采样也不能证明具体 URL、请求耗时或全程离线。

## 三组冷／热启动

时间单位为秒。各阶段列记录从产品计时起点到首次观察该状态的累计时间。每次服务端日志均有 Done，且 game_recipe_status 返回 minecraft:emerald。下面的结果链接可进入对应运行目录，查看 cache.json、startup.json 和完整服务端日志。

| 运行 | 缓存恢复 → 发布 | 请求 → ready | JVM → ready 文件 | Fabric 加载 | 等待探针 | 产品 ready | Fabric 超时日志 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| [1 冷](evidence/pair-1-cold/result.json) | MISS → STORED | 197.046 | 187.709 | 161.703 | 182.750 | 187.969 | Timed out after reading 4674 bytes |
| [1 热](evidence/pair-1-hot/result.json) | HIT → NOT_NEEDED | 32.484 | 29.970 | 6.031 | 25.547 | 30.766 | 未见 |
| [2 冷](evidence/pair-2-cold/result.json) | MISS → STORED | 359.282 | 349.413 | 329.703 | 344.437 | 349.687 | Read timed out |
| [2 热](evidence/pair-2-hot/result.json) | HIT → NOT_NEEDED | 27.750 | 25.090 | 7.219 | 21.234 | 26.437 | 未见 |
| [3 冷](evidence/pair-3-cold/result.json) | MISS → STORED | 74.563 | 65.408 | 48.265 | 60.468 | 65.656 | 未见 |
| [3 热](evidence/pair-3-hot/result.json) | HIT → NOT_NEEDED | 25.031 | 22.772 | 6.156 | 18.531 | 23.750 | 未见 |

| 中位数口径 | 冷启动 | 热启动 |
| --- | ---: | ---: |
| 第四轮：请求 → MCP ready | **197.046** | **27.750** |
| 第四轮：产品 ready | 187.969 | 26.437 |
| 第四轮：JVM → ready 文件 | 187.709 | 25.090 |
| [第三轮](https://github.com/tortletortle/minecraft-mod-studio/pull/5)：JVM 启动前 → 探针 ready | 115.375 | 25.672 |

同轮主指标下热启动中位数缩短 169.296 秒（85.9%）。第三轮预置缓存的操作不在历史热启动计时内，因此以 JVM → ready 文件作近似同口径对照：本轮热启动 25.090 秒，与第三轮 25.672 秒接近；冷启动 187.709 秒，高于第三轮的 115.375 秒。比较使用同一台主机、同版本运行环境、相同测试资产和 JVM 配额；候选提交、缓存的准备方式、计时点和网络负载有所不同。该跨轮差值不能单独证明性能回归。主实验的冷启动是产品运行库缓存冷启动：不等同于 Windows 重启后首次启动。

## 缓存损坏恢复

1. 从第一组复制测试缓存，在独立副本中，将 622 字节的 Fabric 生成启动 JAR 的第 311 个零基字节翻转一位。文件长度不变，SHA-256 由 bd904e26… 变为 aa5a40ea…，见 [损坏记录](evidence/corrupt-edit.json)。
2. [恢复启动](evidence/corrupt-recovery/result.json) 返回 MISS（invalid_cache_removed / file_inventory_or_hash_mismatch）。[目录采样](evidence/corrupt-recovery/cache-observations.jsonl) 观察到无效条目消失、锁保留，然后新临时条目升级为正式条目。该 JVM 有已建立的[公网 TCP/443 连接](evidence/corrupt-recovery/network.jsonl)，日志出现 40 条运行库解包记录。真实服务端启动并通过 MCP 探针，74.562 秒 ready，发布状态为 STORED。
3. [独立审计](evidence/corrupt-recovery-cache-audit.json) 重算全部 87 文件的 SHA-256 和大小，均与新清单一致；没有半成品条目或残留暂存文件。新建实例[再次启动](evidence/corrupt-verified-hit/result.json) 用时 23.641 秒，得到 HIT → NOT_NEEDED，真实服务端和探针均正常。
4. 原始脚本的附加断言要求恢复后 JAR 哈希与恢复前相同。新 JAR 哈希为 133aeb16…；两个归档的内部文件内容 SHA-256 相同，逐字节比对发现差异只在四处 ZIP 头部的 DOS 时间字段（[内容复核](evidence/corrupt-recovery-postcheck.json)、[字节比对](evidence/corrupt-jar-byte-comparison.json)）。独立冷启动生成的缓存清单也显示同一个 JAR 的哈希随重新生成而变化，其余 86 个运行库文件哈希一致。保留原始断言与退出码，后续验收应以新清单完整性、确实弃用损坏文件及再次命中为验收条件。

## 并发与隔离

两个独立 Python MCP 进程同时使用同一个全新测试缓存根目录。两 JVM 的生命周期重叠，且驱动保留两实例直至两边都完成原生探针查询。

| 实例 | 请求 → ready（秒） | 缓存恢复 → 发布 | 服务端与探针 |
| --- | ---: | --- | --- |
| [并发 A](evidence/concurrent-a/result.json) | 86.828 | MISS → STORED | Done；minecraft:emerald |
| [并发 B](evidence/concurrent-b/result.json) | 93.609 | MISS → ALREADY_VALID | Done；minecraft:emerald |

[并发目录采样](evidence/concurrent-a/cache-observations.jsonl) 可见一个临时目录先写入、再以正式条目出现；正式条目首次被观察到时已有清单。[最终审计](evidence/concurrent-cache-audit.json) 显示只有一个有效条目，87 个文件完整，未见发布冲突、半成品或暂存文件残留。本轮并发验证覆盖一次双实例冷启动，不外推到更多进程、高频长跑或写入中断电。

缓存**条目内**顶层只有 .fabric、libraries、versions、cache-manifest.json；缓存**根目录**另有正常的同级 .lock 文件。全部八次独立缓存审计均通过，条目内未发现 mods、个人文件、世界、EULA、server.properties、RCON 凭据或重解析链接。默认缓存[运行中及运行后均不存在](evidence/default-cache-observation.json)；未使用个人存档，未修改防火墙。

[实例隔离结果](evidence/isolation.json)：10 次使用不同的世界目录、配置路径、会话及 RCON 密码；配置绑定回环地址，并发实例的游戏/RCON 端口共四个，互不重复。断开 MCP 后，10 个临时世界均被删除，10 个自建 JVM 和 MCP 进程均退出。另在每次测试的[私有 TEMP](evidence/private-temp-observation.json) 中观察到一个 JNA DLL 和一个零字节标记文件。这些文件不在世界或共享缓存中；未测试长期积累或默认 TEMP 的清理策略。

## 事实、推断和未确定问题

- **事实：** 每次冷启动都有 40 条运行库解包记录，热启动均为 0；两次慢冷启动都在 Fabric Maven 的 experimental_versions.json 请求中遇到读取超时，第三次未观察到读取超时。六次运行从 RCON 可用且等待探针到 ready 的观察间隔约 5.2 秒。三次热启动仍采到 JVM 的公网 TCP/443 已建立连接。
- **推断：** 本轮冷、热差距主要发生在首次看到 Loading Minecraft 之前。耗时分布及日志支持 Fabric 启动准备（联网取件、重试与解包）是主要影响因素；没有逐请求耗时，无法把延迟定量归到某一次请求或区分网络和本地 I/O 的贡献。
- **已复现的观测缺口：** 第一组冷启动日志有 Timed out after reading 4674 bytes，但 startup.json 的 network_warning_observed 为 false；第二组 Read timed out 被识别为 true。建议在后续变更覆盖两种消息，并补充请求起止、重试、缓存验证/复制、写缓存和探针阶段的时间戳。产品 ready 与主指标中间约 9 秒（冷）包含缓存发布及启动/轮询开销，不能反推为单独的写入耗时。
- **未确定：** 未阻断网络，不能承诺离线启动；未测异常断电、多进程长期压力与 Windows TEMP 残留随时间的变化。热启动收益的幅度取决于运行环境与网络。本轮未修改产品源码。

## 复核证据与复现

- 每次运行的原始产品文件位于 evidence/<运行名>/playtest-*/：server.log、startup.json、cache.json、session.json。相邻目录记录 MCP 原始响应、测试端计时、网络采样、缓存条目可见性、stderr 和运行结论。
- 缓存审计清单、独立重新计算的校验结果、损坏注入哈希、实例隔离和验收摘要均位于 [evidence](evidence/)。未上传 JAR、缓存本体、存档、server.properties 或密码；配置隔离只提供不同路径、端口及密码唯一性的布尔值。
- 本机保留未经修改的原始证据。仓库中的副本经过脱敏；[evidence-sha256.json](evidence-sha256.json) 分别记录本机原始字节和发布副本的 SHA-256。
- 用 Python 3.12 运行 python reports/ai-debug-lab-round4-20261121/verify_evidence.py 核对发布副本的完整性和隐私检查。它不会重新运行 Minecraft。
- 本机对现有输出复核损坏恢复，运行 python -B reports/ai-debug-lab-round4-20261121/scripts/compare_rebuilt_jar.py <实机输出目录>。该脚本只读；无需重启游戏。原始实机驱动的严格字节一致断言仍保留，以便重现原始判定。
- 在 Windows 准备相同版本的 JDK、Python 和匹配 SHA-256 的四个测试 JAR，安装仓库锁定的 MCP SDK 与 psutil 7.2.2，然后运行以下命令。--out 必须是新建前不存在的路径；该目录下 cache、tmp、evidence 均与用户默认缓存隔离。复跑新启动会有新的计时，不会覆盖本轮记录。仅在已经接受 Minecraft EULA 的测试环境使用。

    python -B <验收检出>/reports/ai-debug-lab-round4-20261121/scripts/windows_acceptance.py --repo <受测提交检出> --assets <已有测试资产目录> --jdk <JDK目录> --out <不存在的测试输出目录>
