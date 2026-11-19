# Minecraft Mod Studio V2.4 — 关联资源迁移

基线：V2.3（58f9559）。沿用资源库、原始 JAR 读取、项目补丁、许可证来源记录及 Fabric 导出器。未增加第三方运行时依赖。

## 实现
- 从导入的原始物品定义、模型、方块状态或 PNG 选定单个根，递归收集关联模型、父模型、贴图和 PNG.mcmeta。现代物品 definition 支持静态 model、composite、empty 与常量 tint；方块 states 支持 variants / multipart。不猜测自定义渲染格式。
- 区分模型引用、贴图引用和纹理变量；无命名空间引用按 minecraft 处理。原版引用保留并列出，不复制原版游戏文件。已导入原版覆盖视作阻塞。
- 将资源路径与已识别引用映射到本项目命名空间下 `imported/<原命名空间>/...`，不同来源相同短名不会直接碰撞。可选择把根物品 definition 显式覆盖到已有项目物品，其余依赖仍保留独立路径。未绑定的资源并不注册新物品或方块。
- 每个资源保留来源 JAR、源路径、模组 ID、加载器、版本、许可证声明及许可证文本；原始文件不变。UI 显示完整迁移计划、重写 JSON、依赖边和阻塞原因。授权确认后再次规划、验证容量，并执行完整静态源码导出预检，成功后才一次性写入项目。
- 拒绝缺失依赖、重复来源路径（含完全相同的多份）、循环引用、未知模型字段/类型、非法路径、已存在项目补丁。重复迁移共享资源目前也拒绝，需要先清理冲突或手动复用。迁移最多 200 节点、4000 边、64 层，索引 50000 项，单 JSON 256 KiB，项目资源 2 MiB（总项目 3 MB）。

## 规范参考与复用
- Fabric 物品创建与模型文档：<https://docs.fabricmc.net/develop/items/first-item>，<https://docs.fabricmc.net/develop/items/item-models>。
- Minecraft Wiki 物品定义、模型及资源 ID：<https://minecraft.wiki/w/Items_model_definition>，<https://minecraft.wiki/w/Model>，<https://minecraft.wiki/w/Resource_locations>。复用标准 JSON 格式；核心迁移规划为新增代码，未引入第三方编辑器。

## 实测
| 测试 | 结果 |
|---|---|
| `python tests/test_migration_v24.py` | 40/40（17 个独立语义用例 + Chromium 实际操作和 ZIP 内容验证） |
| `python tests/test_compat_v23.py` | 35/35 |
| `python tests/test_resources_browser.py` | 41/41 |
| `node tests/test_debug_v20.js` | 679/679，包含 160 组历史对照输入 |
| `node tests/test_v18.js` | 52/52，20 个内嵌脚本解析，79 个原测试源码文件 |
| `studio_build.source_check` 对迁移 ZIP | PASS，52 个预期 JAR 条目 |

迁移夹具采用两个自行生成的 ZIP 格式 JAR，6 项关联资源：物品定义、两个模型、两张贴图和一个动画元数据。验证原样 PNG 字节、父级引用跨命名空间重映射、纹理变量保留、元数据随纹理迁移、根绑定、许可证记录、项目 JSON 往返、未引入原模组依赖。截图来自 Chromium 实际页面。

## 限制与未验证
- 静态依赖图不是 Minecraft 资源加载器；不验证整个模型 JSON schema、继承纹理变量最终解析、贴图 atlas、资源加载顺序或游戏渲染。原版引用的实际存在性未核验。未提交的单资源编辑不参与迁移。
- 未迁移动画骨骼、生物模型专属格式、声音事件注册、动态模型条件/分派、语言键、配方或 Java 注册/行为代码；V2.3 的配方适配功能仍可使用。方块状态未实现绑定已有方块。
- 未执行真实 Gradle/Fabric 构建或游戏内测试；浏览器使用 opaque origin，未测试 IndexedDB 跨重启持久化。此 ZIP 是静态源码夹具，不是可运行模组。
- 许可证信息仅为导入声明，不等于分发授权。没有上传 GitHub；保留本地 Git 完整历史。
