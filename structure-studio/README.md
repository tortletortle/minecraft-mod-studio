# Structure Studio v0.1 — 建筑制作核心
独立功能分支，基于工程验收提交 1d98eed578f87b65b0fa14c1aa666b327880671e。未修改主程序或 main。目标 Minecraft Java 26.2 / Fabric。

## 使用
需要 Node.js 22+，无 npm 依赖。在仓库根目录执行：
```sh
node structure-studio/core.test.mjs
node structure-studio/export.mjs house 42 out/house.nbt
node structure-studio/export.mjs tower 42 out/tower.nbt
node structure-studio/export.mjs factory 42 out/factory.nbt 27,8,17
```
输出文件已存在时拒绝覆盖。尺寸顺序为 X,Y,Z，每轴最多 48。种子范围 0..4294967295。CLI 默认输出 26.2 DataVersion 4903、传统 Name/Properties 键。后续格式须显式选择并验收，不能仅修改版本号。建议本地对照实际游戏 jar 中 version.json。

## 实现
- 无 DOM 的 ES module：createBuilder、generate、validate、paletteFor、walkability、encodeNBT。
- 显式方块坐标、状态属性、有界体素、去重、稳定排序、可选墙/地/顶材料。
- 平顶房屋、带梯子塔楼、中心通道与四个侧室工厂，种子控制装饰而非任意布局。
- 原生 Java 结构 NBT 序列化及 Node gzip 导出。方块 ID 和属性只做语法验证，不查游戏注册表；仅支持普通方块状态，未附加实体与方块实体数据。
- 地面层 BFS 近似检查双格高通道和房间中心；不验证楼梯/梯子、多层通行、实际物理或 NPC 寻路。空气会覆盖已有方块，须在一次性测试世界操作。
- 结构生成包含实体空气单元，支持清空内部空间；手动 builder 可省略不希望覆盖的坐标。

## 实机验收方法（尚未执行）
在测试存档的数据包 data/<namespace>/structure/ 放置生成的 NBT，使用与 26.2 匹配的有效 pack.mcmeta；启用数据包，重载后在空旷测试区尝试 /place template <namespace>:<name>。按实际版本命令提示核对。确认旋转、墙体、窗口、梯子支撑、房间通行和空气清除行为。使用备份测试世界，禁止在生产存档直接覆盖。后续才可接入 Fabric 工程 ZIP 和游戏测试工具。

## 当前证据
- 首次执行核心生成检查 90 项断言通过。
- 重新从 GitHub 读取 core.mjs（blob d410b767428deeb265de5d0d6347958e936f8a40），执行同一测试逻辑和独立的 NBT 解析器：45 组预设/尺寸/种子组合，465 项断言通过。包含边界、重复坐标、非法输入、完整 NBT 字段及调色板一致性。
- Node gzip 和命令行 IO 测试交给新增 CI；截至撰写此文尚未取得实际运行结果。
- 未执行 Minecraft、Fabric 构建或原生游戏解析器，所以不标记为实机通过。
- 默认预设 seed=42 的体素总数（含空气）：房屋 1001（13×7×11），塔楼 1815（11×15×11），工厂 3672（27×8×17）；工厂入口和四个地面房间通过 BFS。

## 后续路线
1. 先验收 gzip/CLI 和真实游戏放置，修复兼容性及塔楼多层连通。
2. 界面设计与效果图确认后，接入 Studio 项目模型、3D 体素编辑、撤销与预览。
3. 接入 Fabric ZIP 输出；再完成结构注册和世界自然生成，控制生物群系、间距和概率。
4. 实现 NBT/Schematic 导入、战利品、实体、Jigsaw 建筑群，并完成 AI 自然语言转参数和安全验证。不得把目前的程序化预设称为 AI 生成。

## 格式参考
- https://minecraft.wiki/w/Structure_file
- https://minecraft.wiki/w/NBT_format
- https://minecraft.wiki/w/Data_version
- https://gofedako.com/mc/java/versions/

## V0.2 — 数据包与自然生成候选配置
从库根目录执行：
```sh
node structure-studio/pack.test.mjs
node structure-studio/export-pack.mjs structure-studio/example-pack.json mms-test-pack
```
输出为独立目录，不是 ZIP；父目录必须已存在，目标目录必须不存在。可将整个目录复制到一次性测试存档的 datapacks 目录，测试前备份。示例包含三种建筑，仅 factory 显式开启自然生成。可将配置中的 worldgen 移除，以仅测试手动放置。库入口 createPack(options) 返回 Map（文本 JSON 与未压缩 NBT）和报告；CLI 将 NBT gzip 压缩后写入目标目录。后续 Fabric 集成复用 data/ 资源，不等同于当前已集成 Fabric。
- 26.2 DataVersion 4903，数据包 min/max 均为 [107,1]，传统 Name/Properties 调色板。来源：https://www.minecraft.net/en-us/article/minecraft-java-edition-26-2 、https://www.nurshia.com/minecraft/versions 、https://minecraft.wiki/w/Structure_file 。
- 可选单模板 Jigsaw 生成定义、template_pool、structure_set、biome tag；默认关闭。spacing、separation 为区块单位而非精确生成概率，salt 在本数据包内唯一。地形适配仅为候选配置，不保证平坦或不悬空。无多片拼接或地下生成。
- 塔楼修复：之前楼层落脚点下方被清空；现在保留相邻地板、移除靠近屋顶的无效楼层。
- 已直接读取更新后的 core.mjs 和 pack.mjs，执行现有核心 465 项断言及新增 1037 项断言（含 40 种塔楼高度、4 组种子、资源引用、非法路径及去重），全部通过。未执行 Node gzip/文件 IO、Minecraft 或 Fabric 构建；独立工作流增加相关检查，尚未读取结果。

### 游戏验收
使用与版本对应的测试世界，启用数据包，优先通过 /datapack list 核实加载状态。使用空旷地带的命令（可破坏已有方块）：
```mcfunction
/place template mms_structure:house ~ ~ ~
/place template mms_structure:tower ~ ~ ~
/place template mms_structure:factory ~ ~ ~
/place structure mms_structure:factory ~ ~ ~
/locate structure mms_structure:factory
```
每条放置命令分别在不相交位置执行。自然生成需新建启用数据包的世界或生成新地块；记录种子、坐标、区块及日志。检查模板加载、实际梯子通行、自然生成位置、地形交界和生成冲突。仅 command 放置成功不证明自然生成成功。

## V0.3 — 独立可视化建筑编辑器
从仓库根目录执行：
```sh
python -m http.server 8765 --bind 127.0.0.1
```
浏览器打开 http://127.0.0.1:8765/structure-studio/editor.html 。使用本地 HTTP 而非直接双击 HTML（ES modules 有 file:// 安全限制）。无需 npm 包。建议现代 Chromium 浏览器。
- 独立三栏工作台：模板、方块材料、Canvas 等轴测视口、属性及地面静态检查。设计基于本轮 AI 生成界面效果图；实现为简化的纯色立方体，不包含图中材质纹理、复杂工厂道具或自由透视摄像机。
- 90° 相机旋转、Y 层切片、全视图预览、当前层点击放置/擦除/保留。Shift+点击选坐标；全视图只读。可输入 X/Z 坐标，按“应用工具”完成确定位置编辑。
- 擦除写入 minecraft:air，保留删除坐标记录（模板放置时不覆盖该位置）。原始模板含显式空气。
- 独立事务编辑模型：原子修改、重复坐标合并、空操作过滤、80 步 undo/redo、重做分支清除。重新生成或导入会重置历史；离开页面不自动保存。
- JSON 导入/导出及 NBT gzip 导出（CompressionStream）；自定义 ID 仅验证语法，特殊方块属性的可视化配置未实现。NBT 导出尚未实机验证；本轮不接入主制作器或 V0.2 数据包自定义建筑入口。
- 已从 GitHub 读取提交源码，执行 765 项编辑与投影断言，覆盖 4 旋转、4 尺寸、2 视口、双高度、原子修改和历史边界。UI JS 语法解析通过，30 个静态 DOM ID 匹配。浏览器脚本及 CI 已写入，尚无运行结果。效果图不是实机截图。
- 后续：Playwright 验收、真实 Minecraft NBT 放置、编辑器与数据包/主制作器集成、材质与批量操作。

## V0.4 — 程序化地牢生成
- \`generateDungeon\` 使用确定性随机数、网格房间布局、随机 Kruskal 最小生成树和可选环路，生成 4–16 个房间（受尺寸容量约束）。
- 房间类型包括入口、图书室、宝藏室、守卫室、仪式室、储藏室、Boss 房和隐藏房；stone / crypt / bunker 三种材料风格。
- 走廊宽度 1–3 格；隐藏房通过窄支路连接。当前“隐藏”是拓扑与房间标记，尚无可交互隐藏门或伪装墙。宝藏房没有战利品表，未生成带数据的方块实体。
- 编辑器增加“地牢迷宫”模板；NBT CLI 与数据包规划器支持 dungeon。编辑器加载/保存时保留房间类型、隐藏标记、连接图和入口元数据。
- 默认 31×7×25、8 房间、1 隐藏房、stone 风格。平面尺寸每轴限制 16–48，高度 6–16；房间数受每个 6×6 单元容量限制，过小输入会拒绝。
- 已完成 972 组尺寸/房间数/种子边界组合，无生成错误；新增 2319 项地牢断言。尚未执行 Minecraft 实机放置或自然生成验证。
