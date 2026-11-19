# Minecraft 模组制作器

> 状态：Private 开发仓 · 批次 1 · 资源优先级：20%

## 当前完成度

- 记录进度：V1.8–V2.4 开发迭代（版本号来自开发记录，未宣称已发布）
- **未经验收功能不得标记为已完成。**

## 目标 / 架构 / 运行方式

（待迁入真实源码与文档后补全。）

## 工程约定

1. 一个独立项目对应一个 GitHub 仓库。
2. 开发阶段默认 Private。
3. 保留本地 Git 完整提交历史和版本标签。
4. 每个版本保留测试报告、实验数据和变更记录（建议放 docs/）。
5. README 保持目标、架构、运行方式、当前完成度四段信息。

## 迁移说明

本仓库先由工作区登记建仓。若你本地另有完整 Git 历史，请用：

```bash
cd <你的本地项目目录>
git remote add origin https://github.com/tortletortle/minecraft-mod-studio.git
git push -u origin --all
git push origin --tags
```

不要用空骨架覆盖已有历史。
