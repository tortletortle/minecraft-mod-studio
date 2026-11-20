# Minecraft Mod Studio V2.5

> Private 开发仓 · Minecraft Java / Fabric · 当前主程序为单文件 HTML

## 项目目标
构建面向 Minecraft Java 版的可视化模组制作工作室，支持原创内容制作、资源二创和跨模组适配。

## 当前实现
主程序位于 [Minecraft_Mod_Studio_V19.html](Minecraft_Mod_Studio_V19.html)。文件名沿用旧版名称以兼容原工程，页面标题和导出报告标识当前主程序为 V2.5。

当前源码包含：
- 物品：纹理、模型预览、配方、行为图与蓝图调试器。
- 方块：属性、纹理、掉落和矿石生成配置。
- 生物：骨骼层级、立方体、关键帧动画、UV/材质编辑、行为树和 AI/动画状态机。
- 资源库：JAR/ZIP 静态资源导入、来源记录、资源编辑、跨模组适配分析和关联资源迁移。
- Fabric 导出：当前生成器可为支持的物品、方块和生物输出 Gradle 源码工程。

## 验收状态

**已通过真实 Fabric Gradle 编译和 JAR 完整性验证；Minecraft 客户端启动与游戏内行为仍未验收。**

GitHub Actions 验收运行 #1 已通过：JDK 25.0.5、Gradle 9.5.1；浏览器/源码导出测试通过；Gradle 构建成功，Build Doctor 返回 `BUILD_VERIFIED`，检查 46 个预期 JAR 条目。详见 [V2.5 工程验收审查](docs/V25_ENGINEERING_AUDIT.md) 和 [GitHub Actions 运行记录](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44672678223)。

任务、状态效果、GUI 及部分跨模块关联目前仍是项目草稿，不会全部生成可运行的 Fabric 代码。源码生成成功不等于游戏内运行成功；Gradle 编译成功也不等于客户端渲染或游戏行为正确。

## 运行

在现代桌面浏览器中打开主程序 HTML。建议定期使用 Export JSON 保存项目副本。资源库的原始素材和修改补丁应独立备份；仅在具备相应使用权时复用第三方资源。

## 可复现验收

需要 Node.js 22+、Python 3.9+、Playwright 和 Chromium：

```bash
python -m pip install playwright
python -m playwright install chromium
python tests/acceptance/test_browser_export.py --export-dir /tmp/mms-export
```

脚本检查内嵌 JavaScript 语法、关键编辑器交互、源码 ZIP 导出和 Build Doctor 源码完整性。它使用隔离页面和内存存储适配器，不验证 IndexedDB 跨重启持久化。

完整 Fabric 构建另需 JDK 25 和 Gradle 9.5.1：

```bash
python /tmp/mms-export/studio_build.py build
```

仓库提供 [V2.5 验收工作流](.github/workflows/v25-acceptance.yml)，用于自动执行浏览器验收和真实 Gradle 编译。该工作流不会自动接受 Minecraft EULA，也不会擅自启动游戏客户端或服务器。

## 文档说明

历史 [V2.5 测试报告](TEST_REPORT_V25.md)记录的是静态立方体模型工作台测试范围；它没有覆盖当前 HTML 中全部骨骼、动画、材质和生物 AI 扩展。不要把该报告误读为当前源码全部功能的完整测试记录。当前源码状态以工程验收审查和自动化工作流结果为准。

## Git 同步范围

当前仓库保存 V2.5 主程序及阶段性测试报告快照。原始本地 Git 完整历史、早期独立测试套件和所有历史构建材料尚未完整恢复；本轮新增的验收脚本是当前可复现测试入口，不代表旧测试套件已经找回。

## 工程约定

1. 一个独立项目对应一个 GitHub 仓库，开发阶段默认 Private。
2. 保留本地 Git 完整提交历史和版本标签；不要用空骨架覆盖已有历史。
3. 每个版本保留测试报告、实验数据和变更记录。
4. 未验收功能不得标记为已完成。
