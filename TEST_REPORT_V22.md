# Minecraft Mod Studio V2.2 — 资源管理库验证记录

基线：V2.1 (`8c7a7e4d68495abfae0a84dd389425d35cac2ad1`)；保留浏览器单文件和既有 Git 历史。

## 已实现

- 浏览器本地导入 Java 版模组 JAR/ZIP 的 assets/data 资源（ZIP stored/deflate）。不执行 Java class、嵌套 JAR、脚本或入口点；不修改输入文件。
- 按模组、命名空间、资源类别、路径搜索；同路径多来源提示。Fabric 元数据解析及 Forge/NeoForge TOML 首个 modId 等字段的有限提取（不是完整 TOML 解析，不支持所有多模组包/变量）。
- PNG 预览、像素画笔、整体换色、水平翻转；JSON/模型/配方/标签等文本编辑、格式化、显式命名空间引用检查与手动重映射；OGG 播放控件（未实测真实 OGG 解码）。
- 原始素材和修改副本隔离。IndexedDB 按来源保存，失败时明确降级到会话；可下载原始资源备份 ZIP 并重新导入。项目仅存已加入的补丁，随项目 JSON 保存；来源、许可证声明和原许可证文本作为未验证的元数据保留。
- 可保留原路径或设置自己项目的命名空间，可选当前物品导出贴图路径；生成资源路径冲突必须明确允许覆盖。跨模组必需依赖由用户填写，使用 `*`（不表示版本兼容）。Fabric 源码 ZIP 包含资源、依赖和来源报告，许可证信息也放入 JAR 预期条目。未自动迁移注册 ID 或跨版本 JSON 格式。
- 安全边界：每个压缩档 64 MiB，已选资源解压合计 64 MiB，每个文件 8 MiB，ZIP 中央目录最多 12,000 条；拒绝路径穿越、重复路径、加密、ZIP64、多卷与 CRC 不一致；库最多 24 个来源/128 MiB，项目补丁最多 500 项/2 MiB 原始字节，整个项目原有 3 MB JSON 限制仍生效。大体积模组需先选择性提取或未来实现按需索引。

## 本轮真实执行

| 检查 | 结果 |
| --- | --- |
| `python tests/test_resources_browser.py` | PASS, 41 assertions |
| `node tests/test_v18.js` | PASS, 52 assertions, 20 scripts parsed, 79-file legacy fixture |
| `node tests/test_debug_v20.js` | PASS, 679 assertions, 160 historical parity cases |
| `node tests/test_pack_v19.js` | PASS, 50 assertions |
| `node tests/test_functions_v17.js` | PASS, 378 assertions, 92 generated Java programs |
| `node tests/test_logic_v16.js` | PASS, 283 assertions, 87 generated Java programs |
| `python tests/test_debug_browser.py` | PASS, 18 actual Chromium assertions |
| `studio_build.source_check` on resource-export-fixture.zip | PASS, 50 expected JAR entries |

41 项资源库测试使用真实 Chromium、合成的 deflate JAR/NeoForge 来源和 stored 备份 ZIP。检查包括导入、跳过代码、路径穿越拒绝、CRC 损坏拒绝、来源识别、同路径提示、搜索、许可确认、模型重映射、图片实际像素、双模组依赖、冲突拒绝/显式覆盖、项目 JSON 往返、原始 PNG 字节不变、备份往返及导出 ZIP 与许可证条目。测试模组是合成夹具，不是正式第三方模组。

## 尚未验证 / 限制

- Chromium 环境禁止页面导航，测试使用 set_content 的 opaque origin；IndexedDB 明确降级到会话。未实测正常站点 origin 的 IndexedDB 跨重启持久化；项目 JSON 和来源备份的独立往返验证已通过。
- JDK 21/无 Gradle，因此没有真实 Fabric 26.2 编译、JAR 或游戏内验证；未验证覆盖优先级、配方/标签语义、依赖真实存在或实际运行时兼容。
- Forge/NeoForge 来源仅供获授权的静态资源编辑，并不意味着 Forge/NeoForge 代码能够在 Fabric 运行。
- 不包含 3D 模型可视化编辑、全自动跨模组 ID/资源引用迁移、独立资源包/数据包生成、对原 JAR 注入补丁。当前项目仍使用既有至少一个物品的项目结构。
- 许可证信息为来源声明，仅用于溯源；不构成版权许可判断。请遵守具体授权条款。
