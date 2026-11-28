# 模组模板库 V0.1 验证报告

## 目录规模

- 模板：21
- 模板资源定义：37
- 显式资源关系：13
- 分类：8（物品、方块、生物、任务、状态效果、GUI、配方组合、世界生成）
- 能力标记：12 个 `source_generated`，9 个 `design_only`

## 已完成的运行时验证

使用编辑器中的实际 `StudioCore`、模板 `instantiate` 函数和 `StudioCompiler` 函数执行隔离测试。为脱离浏览器 DOM，测试环境对 UID 生成、16×16 像素纹理和生物默认模型提供了确定性桩函数；项目迁移、项目校验、模板实例化、源码生成和 ZIP 打包逻辑使用实际实现。

| 检查项 | 结果 |
|---|---:|
| 模板实例化并通过 `StudioCore.validate` | 21 / 21 |
| `source_generated` 模板通过 `StudioCompiler.compile` | 12 / 12 |
| 源码报告中的未支持功能 | 0 |
| JSON 目录与 HTML 内嵌目录一致 | 是 |
| HTML 内联脚本语法解析 | 21 / 21 |
| 模板实例化是否修改原始项目对象 | 否 |
| 注册 ID 冲突是否自动避让 | 是（冲突时追加序号） |
| 矿石掉落物关系、内部配方材料关系 | 已验证 |
| 物品—状态效果、物品—GUI 关联记录 | 已验证 |

## 源码生成验证明细

下表中的文件数是 `StudioCompiler.compile` 返回的源码文件数量，不是 JAR 内文件数。

| 模板 | 源码文件数 | 生成模式 |
|---|---:|---|
| basic-item | 18 | items-only-complete |
| weapon-item | 18 | items-only-complete |
| gem-material | 18 | items-only-complete |
| ingot-material | 18 | items-only-complete |
| basic-block | 22 | items-blocks-complete |
| ore-vein | 27 | items-blocks-complete |
| decorative-block | 22 | items-blocks-complete |
| ore-progression-pack | 31 | items-blocks-complete |
| lightning-sword | 19 | items-only-complete |
| crafted-crystal-blade | 22 | items-only-complete |
| dual-ore-set | 37 | items-blocks-complete |
| building-material-set | 33 | items-blocks-complete |

## 修复记录

源码生成器检查发现三个普通武器模板设置了非零 `cooldown`，但没有特殊行为。当前生成器将这种组合视为未支持特性。已将这些无技能武器的冷却值归零；雷击武器保留冷却，因为它具有对应的行为定义。

实例化测试还发现物品关联记录必须同时包含 `effect` 和 `gui` 字段。已修复 `item_effect_link` 与 `item_gui_link` 的初始化，避免出现不完整关联对象。

## 尚未验证

- 没有执行 Gradle 构建，因此不能声称源码 ZIP 已成功编译成 JAR。
- 没有启动 Minecraft 客户端或服务端进行游戏内验收。
- 9 个 `design_only` 模板只验证了项目数据实例化，不代表其生物 AI、任务、状态效果或 GUI 已有完整运行时代码。
- 没有完成真实浏览器中的鼠标、键盘、移动端布局和无障碍交互验收。
- Python 标准库验证器和仓库中的 Node 回归脚本已加入自动化工作流，但 GitHub Actions 当前失败在 Runner 分配之前：任务 `runner_id=0`、无步骤、无可读取日志。因此，不能将 CI 标记为通过。

## 结论

当前可以确认：21 个内置模板都能实例化并通过项目数据校验；其中 12 个受支持模板都能通过当前源码生成器导出完整源码 ZIP，且生成报告没有未支持功能。

这仍然是模板库 V0.1 的工程验证，不等于 12 个模板都已完成 Gradle 构建和 Minecraft 游戏内验收。
