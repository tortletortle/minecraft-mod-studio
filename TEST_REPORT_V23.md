# Minecraft Mod Studio V2.3 — 跨模组适配引擎

基线：V2.2 (175048e)。在原单文件工程、资源管理与源码生成流程上增量实现，无新第三方运行依赖。

## 研发选择与参考
- Fabric 共享标签：<https://wiki.fabricmc.net/community:common_tags>；配方使用标签以接受多个注册物品，是本轮复用的标准机制。
- Almost Unified：<https://docs.almostreliable.com/almostunified/> 与 <https://github.com/AlmostReliable/almostunified>。已有材料统一和特殊配方适配；公开源码但 All Rights Reserved，不直接复制其实现，且未验证本项目 26.2 目标的版本支持。参考按标签统一输入的公开行为与文档。
- KubeJS：<https://github.com/kube-mods/kubejs>，LGPLv3；可作日后脚本导出后端，尚未引入，未验证目标版本兼容性。不自行实现游戏运行时通用脚本引擎。

## 本轮能力
- 资源库中的“适配分析”入口一次扫描全部导入来源。基于 `data/c/tags/item/<category>/<material>.json` 中直接声明的成员建立跨命名空间材料组，并显示声明来源。仅白名单常见材料类别；不采用字符串名称近似匹配。
- 原版现代有序/无序工作台配方的字符串型输入可转为共享 `#c:` 标签；其他字段及输出不变。逐项选择，左右 JSON 对比，需确认授权；以原配方路径加入资源覆盖，声明所需来源依赖，不修改原 JAR。
- 模型 parent/texture 的显式命名空间引用解析为具体资源路径：已导入、未在库、原版外部、冲突。输出异内容同路径与多个候选标签报告；标签合并语义仍需验证。可导出完整静态分析 JSON。
- 保守拒绝：多版本同 Mod ID、非 Fabric 来源、未知成员命名空间、replace 标签、嵌套/对象型标签成员、多个候选标签、重复配方路径、老式对象型输入、非工作台自定义配方、已有项目覆盖；不覆盖已暂存补丁。批量加入先校验项目限额后一次变更。分析上限 50,000 资源、单 JSON 256 KiB、候选 500 或候选原始 JSON 2 MiB、依赖边 20,000；面板每类诊断最多显示 100 行，报告保留已分析结果。继承 V2.2 库/项目容量上限。

## 实际验证（2026-11-19）
| 命令 | 实测 |
|---|---|
| `python tests/test_compat_v23.py` | PASS, 35 assertions（19 个独立证据/拒绝用例及 UI、导出） |
| `python tests/test_resources_browser.py` | PASS, 41 browser/export assertions |
| `node tests/test_debug_v20.js` | PASS, 679 assertions；160 个历史对照输入 |
| `node tests/test_v18.js` | PASS, 52 assertions；20 个内嵌脚本语法解析；79 个旧导出夹具文件 |
| `studio_build.source_check` on `tests/compat-export-fixture.zip` | PASS，49 个预期 JAR 条目；两项覆盖配方及两个依赖保留 |

使用真实 Chromium 和两个合成 ZIP 格式 JAR（不是可运行第三方模组）。没有执行 Fabric Gradle 编译、游戏加载或实际合成验证。源码完整性检查只验证清单、CRC、资源路径以及声明，不能证明跨模组运行兼容。标签数据来自导入文件，不等同于运行时注册表；未收集的模组与资源包可能改变标签或配方。没有实现标签递归/条件加载、运行时注册表查询、材料输出统一、任意机器配方、批量依赖迁移、跨加载器或 Minecraft 版本自动移植。依赖版本仍使用 `*`，需按真实整合包锁定。模型引用图只处理部分直接引用，缺失不意味实际游戏缺失。许可证为来源声明，需要用户确认。
