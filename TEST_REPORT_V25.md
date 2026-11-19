# Minecraft Mod Studio V2.5 — 静态 3D 模型工作台

基线：V2.4，提交 fbc41a2。沿用既有单 HTML 架构、资源库、迁移与 Fabric 源码导出。新增 StudioModelPreview 核心与资源库工作台。

## 已实现
- 导入模型或选择已入项目的迁移模型，在独立对话框内预览标准 Java cuboid 元素。父模型递归、子模型纹理变量覆盖、纹理变量间接引用、路径校验；内置 cube/cube_all/cube_column 的几何模板，缺失其他父模型时明确拒绝。原始导入和项目补丁使用不同查找视图，后者以已提交补丁优先；模糊多来源路径不猜测。
- Canvas 2D 正交投影：拖动视角、滚轮缩放、线框、元素选中高亮，仿射 PNG 贴图映射、标准默认 UV、显式 UV、面 UV 旋转及传统单轴元素旋转（含 rescale）。缺失/不可用贴图为占位色并列出原因。
- 通过 `from`/`to` 编辑尺寸位置、新增/复制/删除元素、30 步撤销；继承几何需显式复制为本地元素。其他 JSON 字段保持。写回 JSON 草稿前验证，不直接修改原始 JAR 或项目；随后需权限确认并加入项目。跨模组建议先关联迁移，保留各文件来源/许可证。
- 限制：128 个模型元素，32 层父链，50000 资源索引项，256 KiB 草稿和父模型，64 次贴图读取，单贴图 2048²，贴图合计 8388608 像素。沿用项目资源容量及导出检查。

## 开源调研与实现决策
- bridge-core/model-viewer（MIT，https://github.com/bridge-core/model-viewer）支持 Three.js 场景/canvas 渲染；block-model-renderer（https://github.com/ewanhowell5195/block-model-renderer）是更完整的 JS 渲染方案。当前未安装 Three.js，保持单文件离线运行，本轮没有集成上述项目；无复制其代码，也未验证完整兼容性。后续完整渲染优先评估复用。
- 参考 Minecraft Wiki 模型规范：https://minecraft.wiki/w/Model 。本轮有意限制在传统立方体模型，不宣称覆盖 26.2 全量模型规范。

## 实测
| 测试命令 | 通过 |
|---|---:|
| python tests/test_model_v25.py | 48/48 |
| python tests/test_migration_v24.py | 40/40 |
| python tests/test_compat_v23.py | 35/35 |
| python tests/test_resources_browser.py | 41/41 |
| node tests/test_debug_v20.js | 679/679 |
| node tests/test_v18.js | 52/52 |

48 项中含 16 个独立语义检查，其余为真实 Chromium 交互、像素与导出字节断言。使用两个自行构建的压缩 JAR：子模型依赖另一模组父模型、父模型含传统单轴旋转、贴图变量两级引用。验证真实贴图像素、视角和线框像素变化、继承锁定、非法坐标拒绝、编辑/撤销、原始文件不可变、迁移后三项资源继续编辑、项目 JSON 往返、来源记录、已编辑 JSON 与未改动父模型和 PNG 的 ZIP 字节。截图来自实际 Chromium。

## 限制 / 未验证
- 正交画家排序无深度缓冲，交叉几何、半透明层及复杂遮挡可能显示不准确。未做游戏渲染像素对照；不模拟 display transforms、游戏光照、染色、动画纹理帧（整张纹理静态展示）、atlas 或 cullface 邻接。隐式 UV 可能超出纹理区域；只支持传统单轴旋转，不支持现代多轴。仅显式 cuboid；生成式物品挤出、动态物品模型、blockstate 场景组合、自定义 loader、骨骼及动画均未实现。
- 未进行视觉 UV/旋转的全量规范对照，测试中校验了基本纹理像素、默认 UV、旋转几何计算和字段保留，不能据此称渲染与 Minecraft 完全一致。编辑器不是完整 Blockbench 替代品。
- 仍未执行真实 Gradle/Fabric 编译或游戏内验证；测试使用 opaque origin，未验证 IndexedDB 跨重启持久化。示例为源码 ZIP，不是可运行 JAR；迁移独立模型不自动注册物品/方块。未上传 GitHub。
