# Minecraft Mod Studio V2.5

> Private 开发仓 · 批次 1 · 资源优先级：20%

## 项目进度看板

查看 [中文项目进度总览](docs/PROJECT_STATUS_DASHBOARD_ZH.md)，包含 Java/Fabric 主线、AI God Mode、Live Game Debugger、插件体系、模板库、UI 重构、协议研究、Structure Studio、Rust/Horizon 预研，以及所有主要 PR 的状态和验收门槛。

## 目标
构建面向 Minecraft Java 版的可视化模组开发工作室，支持原创制作、资源二创与跨模组适配。

## 架构
- 离线单文件 HTML/JavaScript 编辑器：蓝图逻辑、函数、调试器、Fabric 源码生成。
- JAR/ZIP 静态资源库与来源追踪；基于共享标签的配方适配；关联资源迁移与命名空间重映射。
- 受限的 Canvas 静态立方体模型预览与编辑。

## 运行方式
下载仓库内的 [Minecraft_Mod_Studio_V19.html](Minecraft_Mod_Studio_V19.html)，在现代桌面浏览器中打开。内部文件名沿用 V1.9 以兼容原工程测试，实际程序版本为 V2.5。资源库中可导入 JAR/ZIP，选择资源后使用适配分析、关联迁移或 3D 模型工具。仅在拥有相应使用权时复用第三方素材。项目 JSON 与资源备份宜独立保存。

## 当前完成度
V2.5 本地测试报告记录了 895 项通过的断言（含旧功能回归），不是 895 个独立测试用例。参见 [V2.5 测试报告](TEST_REPORT_V25.md) 和 V1.9–V2.4 测试报告。真实 Fabric 编译、游戏内运行与完整渲染尚未验收；本仓库没有重新运行原测试。

## 同步范围
本次提交为经 Git blob 哈希校验的 V2.5 单文件源码与七份测试报告快照，不是完整原本地 Git 历史。原始 V2.5 本地提交为 `ce84a646bb338f64a98ca284ceac0932364eb2e1`。完整 bundle、测试脚本、构建脚本及 CI 配置仍待同步，不能声称已迁入全部工程或已部署。

## 工程约定
1. 一个独立项目对应一个 GitHub 仓库，开发阶段默认 Private。
2. 保留本地完整 Git 提交历史和版本标签；不要用空骨架覆盖已有历史。
3. 每个版本保留测试报告、实验数据和变更记录。
4. 未经验收功能不得标记为已完成。
