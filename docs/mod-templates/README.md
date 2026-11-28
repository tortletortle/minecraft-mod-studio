# 模组模板库 V0.1

## 目标

模组模板库为 Minecraft Mod Studio 提供可复用的结构化模组资源组合。模板不是未经验证的 Java 代码片段，而是对当前项目数据模型的声明式描述：资源类型、默认属性、资源间引用、兼容目标和生成能力边界。

模板实例化采用“复制当前项目 → 分配新 UID/注册路径 → 解析模板内部引用 → 完整项目校验 → 原子替换”的流程。失败时不修改当前项目。

## 首批内容

当前包含 21 个模板：其中 12 个标记为 `source_generated`，9 个标记为 `design_only`。

| 分类 | 模板 |
|---|---|
| 物品 | 基础物品、近战武器、宝石材料、金属锭材料、雷击武器 |
| 方块 | 基础方块、装饰方块、建筑材料套装 |
| 世界生成 | 矿石与矿脉、双矿脉生成套装、矿石与武器材料包 |
| 配方组合 | 晶体材料合成武器 |
| 生物 | 被动生物、敌对生物、生物掉落物 |
| 任务 | 击败目标任务、收集物品任务 |
| 状态效果 | 状态效果、附带状态效果的武器 |
| GUI | 基础界面布局、关联界面的功能物品 |

## 能力标记

- `source_generated`：模板只包含当前物品/方块源码生成器覆盖的数据类型，包括当前支持的物品行为与配方数据。
- `design_only`：模板可以进入项目并在编辑器中继续修改，但当前版本不承诺完整生成可运行的游戏代码。

不能因为资源可以保存到项目 JSON，就声称它已经完成运行时代码生成。尤其是生物 AI、任务系统、状态效果和 GUI，目前应按设计数据处理。

## 模板关系

关系使用稳定的模板内 key，而不是硬编码 UID：

- `drop_item`：方块/生物 → 掉落物品
- `item_recipe`：物品 → 配方材料（指定 0–8 槽位）
- `item_effect_link` / `item_gui_link`：物品 → 状态效果/界面
- `quest_target` / `quest_reward` / `quest_prerequisite` / `quest_screen`
- `gui_action`：GUI 组件 → 任务或界面

实例化时由引擎生成新的 UID 并解析这些引用，避免不同项目之间发生 UID 冲突。

## 安全和兼容边界

1. 仅支持 Java Edition / Fabric / Minecraft 26.2 / 项目 Schema 3–4。
2. 模板只允许声明式数据，不允许内嵌 Java、JavaScript、命令、Shell 或动态执行逻辑。
3. 所有资源属性由按 kind 的字段白名单约束。
4. 所有资源 ID 在当前项目中自动避让冲突；模板引用按 key 解析。
5. 实例化前对候选项目运行 `StudioCore.validate`；校验失败不写入。
6. 不修改现有资源，不自动保存，不自动构建或安装模组。
7. 第三方模板未来导入时必须先经过相同 schema、白名单和引用验证；模板中的描述文字永远是数据，不是 AI 指令。

## 文件

- `mod-templates-v1.json`：模板目录数据。
- `../schemas/mms-mod-template-v1.schema.json`：JSON Schema。
- `../../scripts/validate_mod_templates.py`：标准库验证器。
- `VALIDATION_REPORT_V0_1.md`：当前已完成的实例化与源码导出验证证据及未验证边界。
- 编辑器内置选择器使用同一份目录内容，当前 V0.1 提供 21 个模板。

## 验证

从仓库根目录运行：

```bash
python scripts/validate_mod_templates.py
python -m unittest tests.test_mod_templates -v
node tests/test_mod_template_runtime.js
```

验证器检查模板 ID、资源 key、属性白名单、数值范围、关系端点、关系类型/资源类型匹配和生成能力声明。

## 当前边界与下一步

V0.1 提供内置目录、筛选/预览和向当前项目添加模板的能力。当前 12 个 `source_generated` 模板均通过 StudioCompiler 源码 ZIP 导出测试；这不等于 Gradle 构建成功或游戏内行为验收。后续再增加用户自定义模板导入导出、社区模板来源/许可证记录、更多 Fabric 资源类型和完整运行时生成器。新增加载器或 Minecraft 版本必须经过独立兼容验证，不在此版本自动外推。
