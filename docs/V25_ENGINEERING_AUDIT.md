# Minecraft Mod Studio V2.5 — 工程验收审查

审查日期：2026-11-20  
审查基线：GitHub `main` 的 V2.5 源码快照，提交 `f4070b207cc916df7e138c6c6009778df85e8049`  
审查对象：`Minecraft_Mod_Studio_V19.html`（页面标题 V2.5）

## 1. 结论摘要

当前主程序比原 README 和 `docs/V25_TEST_REPORT.md` 所描述的范围更广。源码已经包含生物骨骼、动画、UV/材质、行为树和状态机扩展，并且能够从浏览器导出一个包含 Fabric Gradle 构建文件的源码 ZIP。

本轮复测确认：

- 20 个内嵌 JavaScript 脚本均通过 Node.js 语法检查。
- Playwright 能加载页面并执行核心工作区交互，没有捕获到页面级 JavaScript 异常。
- 默认示例项目校验为 0 errors、1 warning。
- 生物工作区的新增骨骼操作成功：7 根骨骼增加到 8 根。
- 默认示例项目成功导出 63 个 ZIP 条目；生成清单记录 62 个文件。
- Build Doctor 的源码完整性检查为 PASS。
- 独立的生物 Rig Java 类可由当前 JDK 21 编译。
- 完整 Fabric Gradle 构建和 Minecraft 客户端运行仍未执行。

因此，当前阶段应定为：**编辑器和源码导出具备可复测证据；完整构建与游戏运行仍待验收。**

## 2. 当前源码实际包含的功能

| 子系统 | 源码/界面证据 | 当前判断 |
|---|---|---|
| 物品编辑器 | 纹理、配方、模型预览、行为图、节点调试 | 已有实现，部分行为仍需游戏验证 |
| 方块工作区 | 方块属性、纹理预览、掉落和矿石生成参数 | 已有实现，真实注册/生成待验证 |
| 生物骨骼编辑器 | 父子骨骼、枢轴、立方体、层级校验 | 已有实现 |
| 关键帧动画 | 动画片段、时间轴、关键帧和插值 | 已有实现 |
| UV/材质 | UV 图集、像素绘制、面材质、透明度和发光数据 | 已有实现 |
| 生物客户端渲染生成 | EntityModel、ModelLayer、Renderer 和动画驱动源码 | 可生成源码，未通过真实游戏验收 |
| 生物 AI | 行为树、Fabric Goal、AI/动画状态机 | 可生成部分源码，API 兼容性未通过真实构建验收 |
| 资源库 | JAR/ZIP 静态导入、来源追踪、资源补丁 | 已有实现；正常站点 IndexedDB 跨重启持久化尚未在本轮复测 |
| 跨模组适配 | 共享标签配方分析、关联资源迁移和命名空间映射 | 有限格式和白名单范围内实现 |
| 任务/效果/GUI | 编辑工作区与项目关联 | 当前仍为草稿，未接入完整 Fabric 运行时生成 |

**文档差异：** 当前 HTML 含有标记为 V0.7–V1.4 的生物骨骼、客户端渲染、UV/材质、动画和 AI 扩展代码；而原 V2.5 测试报告仍把骨骼及动画列为未实现。报告只覆盖了静态立方体模型工作台，不能代表当前主程序的全部功能。README 已明确这一差异。

## 3. 本轮复测记录

| 检查项 | 结果 | 证据边界 |
|---|---|---|
| 20 个内嵌 JS 脚本语法 | PASS 20/20 | 仅语法检查 |
| 浏览器页面加载 | PASS | Playwright `set_content` |
| 页面级 JS 异常 | 0 | 不代表所有交互均无缺陷 |
| 默认项目数据校验 | 0 errors、1 warning | 只校验默认示例项目 |
| 生物骨骼编辑 | 7 → 8 | 验证新增骨骼交互 |
| 方块工作区 | PASS | 界面可渲染，不代表游戏注册成功 |
| Fabric 源码 ZIP 导出 | PASS，63 个条目 | 不是 JAR |
| 源码清单完整性 | PASS | Build Doctor `source_check` |
| Rig Java 类独立编译 | PASS，JDK 21 | 不包含 Minecraft/Fabric API 类 |
| Fabric Gradle 编译 | BLOCKED | 当前执行环境只有 JDK 21，没有 Gradle 9.5.1 |
| Minecraft runClient / 游戏内渲染 | NOT RUN | 没有游戏运行证据 |
| IndexedDB 跨重启持久化 | NOT RUN | 隔离页面禁止 IndexedDB；本轮使用内存 localStorage 适配器 |

复测环境：Node.js 22.16.0、Python 3.13.5、Chromium、Playwright、OpenJDK 21.0.12.1；未发现 Gradle 可执行文件。

Build Doctor 返回 `source=PASS`、`status=ENVIRONMENT_BLOCKED`，原因是目标工程要求 JDK 25 和 Gradle 9.5.1。不能将环境阻塞描述成编译失败，也不能描述成构建通过。

## 4. 导出内容与功能边界

默认示例项目导出 63 个 ZIP 条目，报告状态为 `SOURCE_GENERATED_NOT_BUILT`。默认示例导出包含：

- Fabric `build.gradle`、`settings.gradle`、`gradle.properties`
- `studio_build.py` 和 `studio_smoke.py`
- 主端 Java 源码、客户端 Java 源码
- 物品、方块、生物模型与纹理资源
- 导出报告和源码完整性清单

默认示例导出明确省略：

- `quests/storm_hunter`
- `quests/crystal_collector`
- `effects/storm_charge`
- `guis/quest_journal`
- `items/stormshard_sword: effect link`

导出界面要求用户确认部分导出。上述内容仍保留在项目 JSON 中，但不能宣称已生成游戏内功能。

## 5. Fabric 工具链

当前导出工程固定目标为 Minecraft 26.2、JDK 25、Gradle 9.5.1、Loom 1.17.12。Fabric 官方 26.2 说明建议使用 Loom 1.17 和 Gradle 9.5.1；Fabric 文档的开发环境说明要求 JDK 25。

参考：
- [Fabric for Minecraft 26.2](https://www.fabricmc.net/2026/06/15/262.html)
- [Fabric Loom 文档](https://docs.fabricmc.net/develop/loom/)
- [Fabric 开发环境设置](https://docs.fabricmc.net/develop/getting-started/setting-up)

版本配置与官方推荐的大版本方向一致，但 Loader、Fabric API 和具体 Loom patch 仍须通过真实 Gradle 依赖解析及编译验证。当前未获得真实构建结果。

## 6. 仓库完整性

当前 GitHub 主分支已保存主程序和 V1.9–V2.5 测试报告快照，但不是完整的原始研发工程：

- 原始本地 Git 历史和完整 bundle 尚未恢复。
- 历史独立测试脚本没有同步到当前仓库。
- 当前仓库此前没有可直接执行的 CI 验收工作流。
- 本轮新增 `tests/acceptance/test_browser_export.py`，作为新的可复现验收入口；它不替代尚未找回的历史测试套件。

## 7. 下一阶段顺序

1. 在 JDK 25 / Gradle 9.5.1 环境运行自动化构建，按实际错误修复生成器。
2. 生成真实 JAR，验证 JAR 条目、元数据和 class major version。
3. 在隔离的 Minecraft 26.2 开发实例执行 `runClient`，验收生物模型、骨骼动画、透明材质和 AI。
4. 单独验证资源库 IndexedDB 持久化、导入大文件和跨模组资源冲突。
5. 再确定 V2.6：优先补齐已有工作区的运行时实现和验收，不重复开发已经存在的骨骼/动画编辑器。

游戏服务器启动脚本会要求明确的 EULA 接受参数。本审查和 CI 不会自动接受 EULA，也不会触碰用户现有游戏世界。
