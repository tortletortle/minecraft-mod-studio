# Minecraft Mod Studio — 源码与版本映射

最后核对：2026-11-28  
仓库：tortletortle/minecraft-mod-studio

## 唯一维护入口

| 路径 | 状态 | 用途 |
|---|---|---|
| v0.1/ | **当前唯一维护源码工程** | 版本化项目模型、纯逻辑核心、Blockbench 桥接、Fabric 编译器与生成器 |
| Minecraft_Mod_Studio_V19.html | 只读历史资料 | V2.5 逻辑/行为参考；禁止继续追加功能 |
| Minecraft_Mod_Studio_V23.html | 只读历史快照 | V2.3 历史状态 |
| Minecraft_Mod_Studio_V25.html | 只读历史快照 | V2.5 历史状态；仅用于核对旧行为语义和回归边界 |

## 新架构模块映射

| 旧 V2.5 逻辑 | 新架构位置 | 迁移状态 |
|---|---|---|
| StudioResources.readZip | v0.1/creature_studio/core/archive.py | 首轮迁移；安全回归测试已加入，需继续扩充恶意归档夹具并做逐项语义对照 |
| StudioBehavior | v0.1/creature_studio/behavior_graph.py + function_library.py + function_editor.py | 校验、模拟、步进调试、函数库打包/导入、表达式编辑辅助和 Java 方法生成已迁入；仍需完整差异验收 |
| StudioStateMachineV12 | v0.1/creature_studio/state_machine.py | 默认值、归一化、校验、条件计算和确定性转移选择已迁入；动画运行时接线未完成 |
| StudioCompiler | v0.1/creature_studio/compiler.py + generator.py | 编译逻辑与文件写入适配分离；纯内存编译输出和 SHA-256 构建清单已建立；完整 V2.5 功能语义尚未宣称等价 |

## 维护规则

1. 新产品代码、测试和文档只在 v0.1/ 新架构中维护。
2. V19/V23/V25 HTML 均只读；禁止反向复制覆盖或继续堆叠猴子补丁。
3. 迁移以旧版已验证行为为参考，不以旧版文件结构作为新架构约束。
4. 每项迁移必须有新架构单元测试；涉及生成代码时必须增加生成快照/结构测试；涉及运行时行为时必须增加对应 Fabric/GameTest 验收。
5. 区分纯逻辑模块迁入、Schema 接线、代码生成、Gradle 构建和真实 Minecraft 运行，不能相互替代。
6. 修改新架构目录、命令或构建入口时同步更新根 README、本文件和对应 CI。

## 历史快照说明

历史 HTML 仅作为审计、差异分析和行为回归的输入。不要再将其称为“当前维护源码”，也不要因迁移未完成而恢复双轨维护。
