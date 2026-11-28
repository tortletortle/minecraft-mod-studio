# Minecraft Mod Studio

> Minecraft Java Edition / Fabric 26.2 · 新架构主线：v0.1/

## 当前维护入口

**当前唯一维护的产品源码工程：v0.1/**。这是版本化项目模型、纯逻辑核心、Blockbench 文件桥接和独立 Fabric 编译器所在目录。新功能必须进入该工程，不再维护旧单文件 HTML。

- [V0.1 工程说明](v0.1/README.md)
- [项目源码映射](docs/PROJECT_SOURCE_MAP.md)
- [项目进度看板](docs/PROJECT_STATUS_DASHBOARD_ZH.md)

## 新架构模块

| 模块 | 职责 |
|---|---|
| v0.1/creature_studio/schema.py | 版本化项目 Schema 校验 |
| v0.1/creature_studio/blockbench.py | Blockbench .bbmodel 导入/导出 |
| v0.1/creature_studio/compiler.py | 纯内存编译：项目数据 + 模型 → 确定性文件映射与构建清单 |
| v0.1/creature_studio/generator.py | 文件系统适配层：将编译结果写入目标工程 |
| v0.1/creature_studio/core/archive.py | 有界 ZIP/JAR 读取与安全校验 |
| v0.1/creature_studio/behavior_graph.py | 类型化行为图校验、模拟与 Java 方法生成 |
| v0.1/creature_studio/state_machine.py | 动画状态机默认值、归一化、校验与确定性转移选择 |

行为图和状态机目前作为独立纯逻辑模块迁入；其编辑器 UI、项目 Schema 接线及完整 Fabric 运行时接线仍按后续验收逐项完成，不将“模块已迁入”描述成“游戏内功能已完成”。

## 当前产品范围

V0.1 当前聚焦一个最小生物创作闭环：

创建版本化项目 → 导入受支持的 Blockbench 模型/贴图 → 校验 → 编译 Fabric 工程 → Gradle 构建 JAR → 在隔离 Minecraft 26.2 环境中验收。

模型支持边界、命令和证据等级见 [V0.1 README](v0.1/README.md)。不支持的模型输入必须明确拒绝，不得静默丢失信息。

## 运行与测试

从仓库根目录执行：

    python -m pip install -r v0.1/requirements.txt
    PYTHONPATH=v0.1 python -m unittest discover -s v0.1/tests -v
    PYTHONPATH=v0.1 python -m creature_studio.cli validate --project v0.1/examples/void_scout/creature.json
    PYTHONPATH=v0.1 python -m creature_studio.cli generate --project v0.1/examples/void_scout/creature.json --out /tmp/void-scout

完整 Fabric JAR 构建另需 JDK 25 和 Gradle 9.5.1：

    cd /tmp/void-scout
    gradle build

真实 Minecraft 游戏运行必须使用隔离实例和明确的手动 EULA 授权流程。普通 PR/Push CI 不得自动接受 EULA。

## 历史资料

Minecraft_Mod_Studio_V19.html、Minecraft_Mod_Studio_V23.html、Minecraft_Mod_Studio_V25.html 均为只读历史资料/行为参考，不再作为产品维护入口。禁止在这些文件上继续追加功能补丁；迁移时只提取经过验证的逻辑语义，并在新架构中重新实现和测试。
