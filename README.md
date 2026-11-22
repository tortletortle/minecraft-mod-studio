# Minecraft Mod Studio V2.5

> Private 开发仓 · Minecraft Java / Fabric · 当前维护版本 V2.5

## 项目目标

构建面向 Minecraft Java 版的可视化模组制作工作室，支持原创内容制作、资源二创和跨模组适配。

## 当前实现

**唯一维护中的编辑器源码：** [Minecraft_Mod_Studio_V19.html](Minecraft_Mod_Studio_V19.html)。文件名沿用旧版以兼容原工程；页面标题和导出报告标识当前程序版本为 V2.5。V23、V25 同名版本文件是历史快照，不是并行维护入口。具体映射见 [源码与版本映射](docs/PROJECT_SOURCE_MAP.md)。

当前源码包含：
- 物品：纹理、模型预览、配方、行为图与蓝图调试器。
- 方块：属性、纹理、掉落和矿石生成配置。
- 生物：骨骼层级、立方体、关键帧动画、UV/材质编辑、行为树和 AI/动画状态机。
- 资源库：JAR/ZIP 静态资源导入、来源记录、资源编辑、跨模组适配分析和关联资源迁移。
- Fabric 导出：当前生成器可为支持的物品、方块和生物输出 Gradle 源码工程。

## 验收状态

**已验证：** 浏览器编辑器关键交互、源码导出、真实 Fabric Gradle 编译、JAR 完整性、专项材质夹具，以及隔离测试源集中的选定服务端/客户端 GameTests。

现有证据：
- [工程验收](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44684912065)：浏览器/源码导出和真实 Fabric 构建通过。
- [材质夹具](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44683048831)：材质像素、源码接线和 Rig 断言通过；随后真实 Fabric 构建通过。
- [隔离世界测试](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44684912005)：选定服务端 GameTests、客户端动画同步/混合断言及截图差异检查通过。
- [资源库验收](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44687320192)：合成 JAR 导入、IndexedDB 重载持久化、关联资源迁移、配方补丁、真实 Fabric JAR 构建和 10 项归档安全测试通过。

**证据边界：** 世界测试运行于一次性测试源集，不是将未经修改的生产 JAR 放入独立 mods 目录进行完整发布验收。截图差异证明渲染姿势不同，不等于所有动画和材质表现均已达标。资源兼容性仍是静态及合成夹具证据，不代表已兼容任意第三方模组。任务、状态效果和 GUI 运行时生成仍不完整。

## CI 与 EULA 边界

普通 Pull Request 会自动运行浏览器/Fabric 构建、材质夹具和资源库验收工作流；这些检查不启动 Minecraft 世界。

[V2.5 隔离世界 GameTest](.github/workflows/v25-world-test.yml) **仅允许手动触发**。运行者必须在 GitHub Actions 的手动运行界面明确勾选 EULA 确认；Push、Pull Request 和普通 CI 不会自动写入 `eula=true`。测试只使用一次性隔离目录，不触碰用户现有游戏世界。

注意：自动触发 CI 不等于 GitHub 已强制执行分支保护。当前仓库的 main 分支保护仍需在 GitHub 仓库设置中单独启用，并将上述 PR 检查设为必需状态检查。

## 运行

在现代桌面浏览器中打开主程序 HTML。建议定期使用 Export JSON 保存项目副本。资源库原始素材和修改补丁应独立备份；仅在拥有相应使用权时复用第三方资源。

## 可复现验收

需要 Node.js 22+、Python 3.9+、Playwright 和 Chromium：

```bash
python -m pip install playwright
python -m playwright install chromium
python tests/acceptance/test_browser_export.py --export-dir /tmp/mms-export
```

完整 Fabric 构建另需 JDK 25 和 Gradle 9.5.1：

```bash
python /tmp/mms-export/studio_build.py build
```

## 工程约定

1. 一个独立项目对应一个 GitHub 仓库，开发阶段默认 Private。
2. 保留原始 Git 历史和版本标签；不要用空骨架覆盖已有历史。
3. 每个版本保留测试报告、实验数据和变更记录。
4. 未验收功能不得标记为已完成。
5. 只在 [源码映射文档](docs/PROJECT_SOURCE_MAP.md) 指定的维护入口开发；历史快照只读保留。


## V2.6 实时游戏调试（实验分支）

在保留 V2.5 编辑器、既有蓝图预览调试器和 V2.5 维护源码的前提下，新增独立 Fabric 客户端伴随模组：

- [Live Game Debugger 总体设计与验收边界](docs/V26_LIVE_GAME_DEBUGGER.md)
- [V2.6.1 生物属性调试与动画控制协议](docs/V26_1_RUNTIME_CONTROLS.md)
- [V2.6.2 生成默认属性恢复](docs/V26_2_RUNTIME_TUNING.md)
- [真实游戏运行时验收步骤](docs/V26_RUNTIME_ACCEPTANCE.md)
- [运行时伴随模组、协议和本地 Agent 客户端](runtime-companion/README.md)
- [V2.6.4 typed MCP Agent 接口](docs/V26_4_MCP_AGENT.md)
- [V2.6.5 Cursor Agent 控制体验重构](docs/V26_5_AGENT_EXPERIENCE.md)
- [V2.7.0 AI 上帝模式与指令智能库（只读原型）](docs/V27_AI_GOD_MODE_COMMAND_INTELLIGENCE.md)
- [V2.6 开发分支](https://github.com/tortletortle/minecraft-mod-studio/tree/v2.6-live-game-debugger)
- [Draft Pull Request #14](https://github.com/tortletortle/minecraft-mod-studio/pull/14)
- [Draft Pull Request #15 — typed MCP Agent tools](https://github.com/tortletortle/minecraft-mod-studio/pull/15)
- [Draft Pull Request #16 — Cursor Agent experience V2.6.5](https://github.com/tortletortle/minecraft-mod-studio/pull/16)
- [Draft Pull Request #18 — AI God Mode Command Intelligence V2.7.0](https://github.com/tortletortle/minecraft-mod-studio/pull/18)
- [V2.6.5 Cursor Agent 体验与实机验收要求](docs/V26_5_AGENT_EXPERIENCE.md)
- [Live Game Debugger 0.3.0 CI artifact](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916284480/artifacts/14712390413)

V2.6.0 的 0.1.0 基线已通过 Python 协议测试和 Fabric 26.2 / JDK 25 构建。V2.6.1 的 0.2.0 扩展加入服务器权威的生物属性读写和生成动画触发，六项协议客户端测试、Fabric 构建及 JAR 内容检查均已通过。V2.6.2 的 0.3.0 扩展继续加入显式确认的生成默认属性恢复命令，七项协议客户端测试、Fabric 26.2 构建和 JAR 内容检查均已通过。JAR SHA-256：`12c129000fb9bf7ef4fab76226b0935dad533e764cf3d80795699682072765d1`。 V2.6.3 增加真实游戏运行时验收脚本及报告验证测试，15 项 Python 测试、工具语法检查和 Fabric 构建均已通过；实际客户端验收仍待完成。 V2.6.4 在 PR #15 中增加 typed stdio MCP Agent 接口；V2.6.5 在 PR #16 中增加 Cursor 场景快照、截图返回、移动闭环验证、短时授权和安装诊断。V2.6.5 仍为 Draft。当前 GitHub Actions 尝试在 runner 分配前失败（runner_id=0、steps=[]），尚无测试/构建结果；Windows 实机验收也未完成。 V2.7.0 在独立堆叠分支上增加只读 Brigadier 命令发现、检索、检查与语法验证；未开放通用命令执行。 PR #18 的 CI 当前因 GitHub Runner 无法分配（runner_id=0、steps=[]）未执行测试或构建，不能视为通过。

**尚未完成真实游戏内验收。** 编译通过不代表玩家移动、属性同步和动画播放已在实际 26.2 客户端验证；在一次性单人测试世界完成手动验收前，不将该伴随模组标记为正式发布版本。属性写入可能随世界保存，必须使用 disposable test world。
