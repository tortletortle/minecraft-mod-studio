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
