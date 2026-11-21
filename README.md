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

在保留 V2.5 编辑器和既有蓝图预览调试器的前提下，新增独立的 Fabric 客户端伴随模组原型：

- [Live Game Debugger 设计与验收边界](docs/V26_LIVE_GAME_DEBUGGER.md)
- [运行时伴随模组、协议和本地 Agent 客户端](runtime-companion/README.md)
- [V2.6 开发分支](https://github.com/tortletortle/minecraft-mod-studio/tree/v2.6-live-game-debugger)

当前首期实现范围：本机回环地址认证通信、单人世界玩家状态读取、有限时长移动/视角控制、实体与方块只读检查。**该功能仍处于开发验收阶段；在 Fabric 构建和真实游戏内控制测试通过前，不将 JAR 视为可安装发布版本。** 暂不支持生物属性写入、动画触发、方块修改或多人服务器控制。
