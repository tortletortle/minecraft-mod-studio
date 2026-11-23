# Cursor 本地验收任务 · Minecraft Mod Studio Java 版 AI 控制

目标分支 `feature/ai-god-mode-typed-world-patches-v2.7.3`。记录实际测试的 git rev-parse HEAD。在独立检出目录工作，保留用户本地改动。先读同分支 runtime-companion/README.md、docs/V27_3_TYPED_WORLD_PATCH_TRANSACTIONS.md 和 .github/workflows/mms-live-debugger-build.yml。

1. 在独立 Python 3.12 环境，从仓库根目录依次运行以下命令，分别记录退出码、用例数和跳过项。

   ```sh
   python -m pip install -r runtime-companion/requirements-mcp.txt
   python -m unittest discover -s runtime-companion/tests -v
   python -m compileall -q runtime-companion/tools
   ```

2. 使用 JDK 25 和 Gradle 9.5.1，在 runtime-companion 目录运行 `gradle --no-daemon --console=plain clean build`。记录 Java/Gradle 实际版本、可加载的成品 JAR 路径和 SHA-256。若失败，保留首个有诊断价值的错误和复现步骤，继续独立可执行的用例。

3. 在独立的 Minecraft 26.2 Fabric 实例装入本次构建的 JAR，创建一次性单人创造世界。按 companion README 建立本地连接。在 Cursor 中用自然语言提出“找出当前游戏里与设置时间有关的命令，给出用法并预览设为白天的操作”。记录 Cursor 实际调用的工具、检索词、返回的命令与参数、是否需要操作者补充信息。用当前实例的命令树核对结果。保存摘要时隐去令牌和连接文件内容。

4. 先用 mms_preview_block_patch 在近处一个满足约束的空气格预览放置 minecraft:stone。记录维度、坐标和预期前后状态，检查预览后仍为空气。把这批预览展示给操作者，获得对该批应用和恢复的明确确认后，使用同一个 plan_id 调用 mms_apply_block_patch，独立读取方块验证为石头，再用返回的 transaction_id 调用 mms_rollback_block_patch 并复查恢复为空气。未获确认时记录“仅预览”。另测非空气格的预览被拒绝，复查原方块保持原状。

5. 输出中文验收表，每行列出测试项、预期、实际、通过/失败/阻塞/跳过及证据位置。分别给出 Python 测试、Fabric 构建、Cursor 工具调用和游戏内往返的结论。记录遇到的第一个操作障碍，以及复现它所需的最少步骤。保留本地日志和脱敏证据，测试阶段不提交产品改动。