# 证据和复现说明

本目录随验收 PR 发布。SHA256SUMS.txt 对应这里的 111 个证据文件。RAW-SHA256SUMS.txt 对应本机各原始文件。上传版本已去除用户名和用户目录，测试结果与原始 Minecraft 原生截图保留。所有目录和账号均为验收用途。证据未包含运行库、个人世界、服务端配置或凭据。

## 浏览器和构建

1. 用两个固定提交各自的 Minecraft_Mod_Studio_V19.html。安装项目验收工作流用到的 Python 3.12、Playwright/Chromium、Temurin 25 和 Gradle 9.5.1。
2. 运行仓库现有 tests/acceptance/test_browser_export.py，并在工程目录中执行 studio_build.py build。Crystal Lab 的编辑器项目在 evidence/build/crystal/function-project.json。运行 evidence/replay/browser_generation.py 可对照编辑操作，脚本末尾注明需要的输出目录和浏览器参数。
3. 用 tests/resources/resource_library_acceptance.py 和 tests/resources/archive_security.py 对候选工作树验收资源导入/迁移及路径边界。用 tests/materials/material_fixture.py 对同一导出项目构造材质夹具，候选和主分支分别运行。用各自的构建产物运行 evidence/replay/check_compiled_animation.py，对照实际 ModelPart 姿态。脚本源自隔离工作区，按各机安装位置调整其中的工作目录和资产路径。

## Windows 游戏与 MCP

1. 使用 AI Debug Lab README 和 AI_PLAYTEST.md 中的资产和启动流程。准备 Minecraft 26.2 客户端、Fabric Loader 0.20.1、Fabric API 0.161.0+26.2、Java 25、MCP SDK 2.3.0，以及从对应提交导出的 Crystal Lab 或材质 JAR。只在新建测试目录配置并接受独立测试服所需 EULA。
2. 用普通 Fabric 客户端加载发布 JAR，到独立创造模式世界，按 evidence/client 下的 datapack 复现场景。Crystal Lab 第一阶段让 load 计划调用 prepare，再把原版 Use 绑定 R，保存使用前后截图。第二阶段将 load 切换为归档的版本并在游戏内 reload，打印健康、掉落和矿石证据后观察 AI。材质夹具在同一相机位置分别于 midnight 和 noon 截图。用 STUDIO_TRACE=1 启用日志，从控制台选取 STUDIO_TRACE_V1 行，导入 Crystal Lab 项目的运行追踪。
3. evidence/replay/worldgen_ore.py 使用固定种子 42、生产 JAR 和 nbtlib 2.0.4。脚本创建独立标准主世界，生成并保存九个区块，在退出后解码区域数据。evidence/ore/console-commands.txt 给出控制台记录。区块证据可用 Python zlib 解压为 NBT。
4. MCP 回归驱动接收新证据目录、AI Debug Lab 路径、预备资产目录、已预热的隔离运行库缓存、JDK 目录、新测试工作目录，另可传 --with-cli。稳定性驱动在同一提交启用受控的测试启动阈值并对照 SDK 宽限。只会对实验启动且验证过的 JVM 注入异常退出。参数以脚本的参数解析和 evidence/mcp/ 中的运行回执为准。
5. 冷热启动严格按 PR #7 的实验方案执行。第三轮参考数据与第四轮原始结果均保留在独立验收记录。
