# V2.5 客户端运行时验收

基线：Stormshard Mod 默认示例；真实 Fabric 26.2 构建已连续通过两次（Actions #1、#2）。本轮不修改产品 HTML 或发布 JAR，新增隔离客户端测试入口。

## 现有覆盖缺口（源码快照和导出报告的实际观察）

- 默认生物有 8 根骨骼（包含验收时新增的 bone_8）、2 个动画，12 个关键帧。idle 与 walk 都指向 walk，故不能证明不同待机/行走动画之间的混合效果。
- 4 项默认材质均为 opaque、opacity=1、emissive=false；无透明或发光路径覆盖，ORM 地图仅导出，不能宣称原版 PBR 已生效。
- 默认 AI 有目标获取、追击、近战、游荡和状态转换代码，但目标获取目前只排除死亡玩家与旁观者，近战节点没有显式视线条件；是否采用该设计由用户配置决定。实际伤害、冷却、寻路、客户端事件和动画标记均需要游戏世界测试。
- 方块、配方、掉落和矿石生成的数据文件存在，构建成功不意味着动态注册表加载及世界生成成功。

## 本轮：开发客户端启动探针

复用 Fabric 官方 ScreenEvents 与 ClientTickEvents、真实 Minecraft ModelPart/EntityModel；使用 Xvfb + Mesa 软件渲染在 GitHub Actions 中测试。验证：

1. 原始源码清单及已构建 JAR 的哈希完整性；
2. 复制原始导出至独立目录，仅叠加测试用 client entrypoint；
3. 真实 Minecraft 客户端初始注册后，TitleScreen 画面提取回调达到至少 10 次；
4. 五个物品、一个方块、一个实体类型已进入运行时注册表；
5. 实体贴图可以由客户端资源管理器查找；
6. Minecraft 实际 ModelPart 层级构造与四个确定动画姿势（walk 0/10、attack 2/8）；
7. 记录明确的 PASS 标记、正常退出、日志和尽可能截取主菜单截图。

探针验证的是带临时测试入口的开发客户端，而非原始发布 JAR 的独立生产加载。标题画面提取不等价于生物像素渲染。它不启动单人世界、远程或专用服务端，不自动接受 EULA。未完成结果必须保持 NOT RUN / FAILED，而不是标记为通过。

## 第二阶段：真实世界 GameTest（需进一步授权）

优先使用 Fabric 官方 GameTest / Client GameTest，而不自行制作服务器控制框架。官方配置文档明确说明 eula=true 表示同意 EULA；不得在未经明确确认的情况下写入。后续测试世界应隔离并按夹具验证：

| 编号 | 验收内容 | 最低通过条件 |
|---|---|---|
| W01 | 单人世界载入与动态注册表 | 无相关资源解析错误，矿石 placed/configured feature 存在 |
| W02 | 物品、方块、配方 | 注册 ID、合成、放置、挖掘掉落断言 |
| W03 | 生物模型 | 实体真实生成；截图含已知模型，贴图无缺失 |
| W04 | 动画同步 | 不同姿势下实际截图/骨骼值；客户端攻击事件同步 |
| W05 | 透明/发光 | 独立非 opaque 夹具、覆盖不同相机方位、已知 alpha/emissive 像素 |
| W06 | AI | 可控目标距离与障碍；寻路、攻击间隔、伤害和事件次数 |
| W07 | 矿石生成 | 固定种子、新区块、实际生成存在性；更广泛分布另测 |
| W08 | 打包 JAR | 在独立 production run 加载未经探针修改的发布 JAR |

参考：[Fabric Automated Testing](https://docs.fabricmc.net/develop/automatic-testing)、[Fabric ScreenEvents 源码](https://github.com/FabricMC/fabric-api/blob/26.2/fabric-screen-api-v1/src/client/java/net/fabricmc/fabric/api/client/screen/v1/ScreenEvents.java)。
