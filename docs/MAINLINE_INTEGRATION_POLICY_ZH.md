# Main 主线集成与分支收敛规则

> 生效原则：所有正式功能最终都以 `main` 为目标分支；不再建立长期的功能 PR 堆叠链。
> 本文件是分支整理和合并操作的统一规则。项目总验收仍以 Issue #30 为准。

## 1. 唯一集成方向

- 所有正式功能 PR 的目标分支必须是 `main`。
- 新功能分支从创建时记录的最新 `main` SHA 派生。
- 禁止把 `feature/A` 长期设置为 `feature/B` 的 PR Base。
- 功能存在依赖时，按依赖拓扑顺序先合入依赖，再将后续功能重新整理到更新后的 `main`。
- 如果两个功能必须原子交付，可以在一个以 `main` 为基线的集成分支中组合，但 PR 必须明确列出各功能提交和验收范围。
- 不允许仅通过 GitHub 的 Edit PR / Change base 把堆叠 PR 的 Base 改成 `main`，并将其误认为已完成分支重基。

## 2. 原分支保护与集成分支

- 原始研发分支是审计记录，不直接重写、不强制推送、不删除。
- 每次集成创建新的 `integration/<feature>-to-main` 分支。
- 集成分支完成整理后，PR 目标为 `main`。
- 每次合并后重新 fetch `main`；下一项集成必须以新的 main HEAD 为基础。
- 已关闭、已合并、Draft、实验和测试证据分支分别标记，不因分支存在就认定为可合并产品功能。

## 3. 分支整理前必须完成的 Git 历史审计

每个功能分支都必须记录：

1. 当前 `main` SHA。
2. 原始功能分支 HEAD SHA。
3. PR 的 base/head 分支及对应 SHA。
4. `git merge-base origin/main origin/<feature>` 的真实分叉点。
5. `git log --graph --oneline --decorate` 所显示的提交拓扑。
6. 功能分支独有提交、父功能已包含的提交、合并提交和重复补丁。
7. 与已合并功能的文件重叠、接口依赖和测试依赖。

不得只根据 PR 页面上的 Base Branch 判断真实历史关系；不得把不同 commit 的测试结果合并成同一个版本的结论。

## 4. 线性分支的标准整理流程

以下操作只针对新的集成副本，不改写原始研发分支：

```bash
git fetch origin --prune

# 记录原始分支和当前 main 的精确 SHA
git rev-parse origin/main
git rev-parse origin/<feature>
git merge-base origin/main origin/<feature>
git log --graph --oneline --decorate origin/main...origin/<feature>

# 从原始功能分支建立集成副本
git switch --detach origin/<feature>
git switch -c integration/<feature>-to-main

# 仅适用于已确认是线性历史、且 OLD_BASE 是该功能真实分叉点的情况
git rebase --onto origin/main <OLD_BASE_SHA>

# 检查整理结果
git log --graph --oneline --decorate origin/main..HEAD
git diff --check
git diff --stat origin/main...HEAD
git diff --name-status origin/main...HEAD

# 推送集成分支并创建目标为 main 的 PR
git push -u origin integration/<feature>-to-main
```

注意：

- `OLD_BASE_SHA` 必须是该功能开始独立开发时的真实父提交，不能随便填当前父分支 HEAD。
- 对堆叠子分支，只有当父功能已经进入 main 后，才能把子分支独有提交重放到最新 main。
- 如果父功能尚未进入 main，必须先集成父功能，或将不可分割的父子功能整理成一个 main-based 集成 PR。
- 如果历史含有 merge commit、多个父分支、反复同步 main 或 cherry-pick，禁止盲目执行普通 rebase；先识别提交图，再决定使用 `--rebase-merges`、选择性 cherry-pick 或按文件/补丁重建集成分支。
- 整理后必须检查重复提交、重复代码、冲突解决是否改变语义，以及测试是否覆盖合并后的组合状态。

## 5. 文件重叠和依赖处理

- 同时修改同一个维护源码、工作流、Schema、公共 API 或测试夹具的 PR 必须串行集成。
- 每合并一个 PR，后续集成分支都要以最新 main 重整并重跑相关测试。
- 不允许用“自动解决冲突”替代接口和行为审查。
- 合并前确认父功能已经在 main，或把所需依赖一起纳入当前 PR。
- 当前产品维护源码遵循项目源码映射：`Minecraft_Mod_Studio_V19.html` 是唯一维护入口；V23/V25 快照不得覆盖 V19。

## 6. PR 与合并策略

- 正式 PR 一律 `integration/* → main`。
- 小型、独立、可审计的功能默认可使用 Squash and Merge。
- 需要保留多阶段工程历史、测试和审查链的基础集成可使用 Merge Commit。
- 不使用长期堆叠 PR 作为正式集成机制。
- 不允许因 PR 数量、分支已存在、GitHub 显示 mergeable 或 CI 记录显示 failure 就推断功能已验收。
- PR 合并必须使用预期 HEAD SHA，避免在审查后分支变化造成竞态。
- 合并后记录 merge commit SHA，并在 main 上运行必要回归。

## 7. CI 与证据口径

必须区分：

- **PASS**：精确提交 SHA 上有真实 runner、实际 steps、可读取日志和成功结果。
- **CODE-FAIL**：runner 正常执行了测试，测试命令或断言失败。
- **INFRA-UNEXECUTED**：runner 未分配、steps 缺失、日志不可用或工作流未真正开始。
- **SKIPPED**：工作流或步骤按配置跳过。
- **EQUIVALENT-EVIDENCE**：当前 SHA 与已有 PASS SHA 的相关源码、测试和工作流文件完全相同，差异仅在经审查的文档/元数据；必须列出两个 SHA、完整差异文件清单及旧 SHA 的真实成功日志。它不是“当前 SHA 的 CI PASS”。

遇到 `INFRA-UNEXECUTED` 时：

1. 不要把它标成代码失败。
2. 不要盲目重复消耗相同 runner 资源。
3. 用最小 runner smoke（不 checkout、不安装依赖、只打印 runner/OS/基础版本）区分平台分配问题与项目测试问题。
4. 如果 smoke 也在第一步前失败，交由仓库管理员检查 Actions 开关、组织/仓库 Actions policy、runner group、并发/额度和平台状态；必要时使用已配置的 self-hosted runner。
5. 不得把无 steps、无日志的失败当成 PASS。

### CI 无法执行时的有限证据等价例外

仅在以下条件全部满足时，项目负责人可以提出一次有记录的合并例外：

- 有同一功能、同一测试配置的旧 SHA，三个相关工作流均有真实 steps、可读日志并成功；
- 当前 HEAD 与旧 PASS SHA 的完整 compare 显示，除文档/元数据外，产品源码、测试、工作流和依赖配置没有任何变化；
- 当前 SHA 的失败属于 `INFRA-UNEXECUTED`，并有最小 runner smoke 的独立证据；
- 当前 PR 无未解决冲突，审查和安全检查完成，且没有其他失败的必需检查；
- Issue #30 和 PR 中明确记录“EQUIVALENT-EVIDENCE；当前 SHA 未取得 CI PASS”，列出证据 SHA、差异文件、运行 ID 和风险；
- 如果 GitHub branch protection / ruleset 要求当前 SHA 的检查通过，不得绕过；应由仓库管理员恢复 runner 或按组织政策处理。

该例外只解决“代码与测试未变化、CI 平台未执行”的特定情形，不得推广为跳过功能测试的通用规则。合并后必须在 runner 恢复时对 main 的合并 SHA 补跑全量回归。

## 8. 每个集成 PR 的验收清单

- [ ] 原始分支、PR、main SHA、head SHA 和真实 merge-base 已记录。
- [ ] 已确认功能独有提交，不包含未合并父功能的隐式依赖。
- [ ] 集成分支从最新 main 整理，原始分支未被改写。
- [ ] 变更文件、重叠文件、公共接口和 Schema 已审查。
- [ ] 冲突解决经过语义审查，不只是文本合并。
- [ ] 单元测试、集成测试、构建和必要的 Fabric 实机测试有精确 SHA 证据。
- [ ] CI 状态明确区分 PASS、CODE-FAIL、INFRA-UNEXECUTED、SKIPPED 和 EQUIVALENT-EVIDENCE。
- [ ] PR Base 为 main，描述中包含依赖、风险、测试命令和证据链接。
- [ ] 合并后记录 main merge SHA，并更新项目看板和 Issue #30。

## 9. 第一项主线集成结果：PR #1 已合并

核对与合并记录（2026-11-25）：

- 合并前 main：`867e1bd37df2f039a395779493efb8cb20093287`。
- PR #1 HEAD：`4a36d0a50e7b5942acacfe851648849f4b62837d`；目标分支为 main；合并前 compare ahead 48、behind 0；GitHub 返回 `mergeable=true`。
- 旧验证 SHA：`6b8cbec13476045a5f1fd63ba6ed212564b8231d`。三个工作流均为 success，且有完整实际 steps：Engineering Acceptance run `44901675881`、Material Fixture run `44901675929`、Resource Library Acceptance run `44901675911`。
- 旧验证 SHA 到 PR #1 当前 HEAD 的差异仅涉及 `README.md`、`docs/MULTI_AGENT_DEVELOPMENT_PLAN_ZH.md`、`docs/PROJECT_STATUS_DASHBOARD_ZH.md`；V19 源码、测试脚本和三个工作流没有变化。
- 当前 PR #1 HEAD 的三个工作流均失败，但 job steps 为空、日志下载返回 `BlobNotFound`。PR #32 的最小 runner smoke（commit `6eae04b00d7f979eeebf02d694394ac6dc6f1a18`）同样在第一步前失败且无日志。
- 按上述完整差异与旧 SHA 真实成功证据，将当前失败归类为 `INFRA-UNEXECUTED`，并以 `EQUIVALENT-EVIDENCE` 记录，不声称当前 HEAD 的 CI 通过。
- PR #1 已通过 GitHub Merge API 成功合并，方式为 Merge Commit。Merge Commit：`1806488728306274cb16eab973fe9e8444fb60ab`。
- 合并后 compare 已确认 `main` 与该 Merge Commit identical（ahead 0 / behind 0），因此该 SHA 已成为 main HEAD。
- 合并后 main SHA 的新一轮 Actions 执行结果尚未取得；当前 combined status 未返回状态项。必须继续检查 main push workflows，并在 runner 恢复后补跑三项回归。

结论：PR #1 的代码已经进入 main；**产品代码合并完成，合并后回归验收仍待完成**。不得把这两个状态合并成“全部验收完成”。
