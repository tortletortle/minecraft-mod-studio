# GitHub Actions Hosted Runner 故障调查报告

> 调查日期：2026-11-24  
> 仓库：tortletortle/minecraft-mod-studio  
> 影响范围：私有仓库的 GitHub-hosted runners；产品代码尚未执行  
> 状态：根因待账户所有者确认（Billing / Budget 为当前首要假设）

## 1. 执行摘要

已确认当前故障发生在 GitHub-hosted Runner 分配/启动阶段，而不是 workflow step、checkout、依赖安装、Gradle、Playwright 或 Minecraft 代码执行阶段。

**尚未确认具体根因。** 现有证据最支持优先检查私有仓库的 Actions included compute、Actions 预算硬停止和付款状态。若这些都正常，再升级为 GitHub 私有 Hosted Runner 调度/账户级限制调查。

当前不合并 PR #1 或 PR #32，不修改 main，不公开仓库，不增加付费预算，不盲目重复重跑。

## 2. 直接证据

### 2.1 私有仓库最后成功与首次故障

| 时间（UTC） | Run | 结果 | Runner / steps | 含义 |
|---|---|---|---|---|
| 2026-11-22 07:02:37 | [44996410762](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44996410762) | success | runner_id=1000001398；15 steps | 私有仓库 Hosted Runner 曾正常工作 |
| 2026-11-22 15:53:11 | [45040748148](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45040748148) | failure | runner_id=0；0 steps；约3秒 | 首次确认分配前故障 |
| 2026-11-22 16:55:48 | [45046542136](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45046542136) | failure | runner_id=0；0 steps | 相同故障继续 |
| 2026-11-24 07:06–07:08 | [45345393355](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45345393355) | failure，attempt 1/2 | runner_id=0；0 steps；日志 BlobNotFound | 最小 Smoke 也无法启动 |

### 2.2 800 条最新运行记录

查询 GitHub Actions API 时，仓库返回 `total_count=1518`。按 API 分页统计最近 800 条：

- 789 条 failure
- 11 条 cancelled
- 0 条 success

这 800 条记录不是 800 次产品测试失败。抽样检查多个 workflow 的 job 发现它们都没有分配 Runner，不能用作产品代码失败结论。

### 2.3 跨 workflow、跨操作系统

| 工作流 | Run | runs-on 标签 | runner_id | steps |
|---|---|---|---:|---:|
| V2.5 Engineering Acceptance | [45231062056](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45231062056) | ubuntu-latest | 0 | 0 |
| V2.6 Resource Library Acceptance | [45231061996](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45231061996) | ubuntu-24.04 | 0 | 0 |
| V2.5 Material Fixture | [45231062000](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45231062000) | ubuntu-24.04 | 0 | 0 |
| UI Workbench Acceptance | [45236264611](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45236264611) | ubuntu-24.04 | 0 | 0 |
| AI God Mode Build | [45172725181](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45172725181) | ubuntu-24.04 | 0 | 0 |
| AI Debug Lab Windows | [45232956948](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45232956948) | windows-latest | 0 | 0 |
| CI Runner Smoke | [45345393355](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45345393355) | ubuntu-24.04 | 0 | 0 |

因此不是单一业务 workflow、单一分支或单一 Ubuntu runner 标签导致的。

### 2.4 最小诊断实验

[PR #32](https://github.com/tortletortle/minecraft-mod-studio/pull/32) 只新增 `.github/workflows/ci-runner-smoke.yml`。工作流没有 checkout、第三方 `uses`、依赖安装、secrets 或产品代码，只打印 runner 身份、系统版本并输出 `SMOKE_PASS`。

[Run #45345393355](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45345393355) 的 attempt 1 和 attempt 2 均出现：
- runner_id=0
- runner_name=""
- runner_group_id=0
- steps=[]
- Job 约3秒内结束
- 下载日志返回 HTTP 404 `BlobNotFound`

这说明执行环境没有成功接管 job；不是 smoke 命令执行失败。

## 3. 交叉控制与边界

- minecraft-mod-studio 是个人命名空间下的私有仓库。
- 同一 owner 的 supercap-ups 是公开仓库；[Run #45310723927](https://github.com/tortletortle/supercap-ups/actions/runs/45310723927) 于 2026-11-24 02:12:58 UTC 成功，runner_id=1000003414，13 steps。
- 公开仓库标准 Hosted Runner 免费，因此该对照只能说明同账户不是完全无法使用 Actions，不能排除私有仓库 billing gate。
- 该公开仓库成功时间比私有 Smoke 失败早约5小时，非同时段实验。
- main branch API 返回 `protected=false`、`protection.enabled=false`。这不是 runner 分配故障的根因，但 main 缺少 required checks 是独立发布风险。
- GitHub Status 在 2026-11-22 至 2026-11-24 没有公开 Actions 事故，当前组件显示 Operational。公开状态正常不能证明账户级服务完全正常。

## 4. 根因假设与判别

| 优先级 | 假设 | 当前支持证据 | 判别方法 |
|---|---|---|---|
| P0 | Included compute 用尽，且无有效付款方式 | 私有仓库；大量 workflow；官方说明用尽后会阻止用量；社区存在完全相同签名案例 | Billing → Usage 检查 Actions included compute 是否达到上限、是否 Usage blocked；看 job Annotation |
| P0 | Actions 预算启用 Stop usage 且达到上限 | 官方说明任一适用硬预算达到上限可阻止 Hosted Runner | Billing → Budgets and alerts 检查 account/repo/Product/SKU 预算和硬停止状态 |
| P1 | 付款方式/账户计费状态异常 | 社区相同故障讨论报告该错误 | 检查 payment method、Billing banner 和 job Annotation |
| P1 | 私有仓库或账户级 Actions 执行限制 | 公共仓库能跑、私有仓库不能跑；当前私有 repo run/job 已创建 | 检查 Actions General、组织策略（若有）、账户限制；无 billing 证据时交 GitHub Support |
| P2 | GitHub 私有 Hosted Runner dispatch / provisioning 故障 | 0 runner、0 steps、无日志；公开状态页没有当天事故 | Billing 与策略排除后，凭 run/job ID 要求 GitHub Support 查后台调度遥测 |

### 关键 Annotation

GitHub Community 中有同症状案例指出，Job 页顶部 Annotation 可能显示：

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings

如果本仓库 job 页也显示此文案，则可以将其归类为计费/支出限制拒绝，而不是 runner VM provisioning。

该判断来源于社区用户案例，不应在未查看本仓库 Annotation 前当作既定事实。

## 5. 官方计费规则

GitHub 官方文档：

1. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
   - 私有/内部仓库标准 GitHub-hosted runner 使用量从账户 monthly included compute usage 扣除。
   - 公开仓库标准 GitHub-hosted runner 和 self-hosted runner 不消耗该 included compute usage。
   - GitHub Free 的 included compute 为 $12/月，GitHub Pro 为 $18/月；是金额池，不是固定分钟数。
   - 标准 Linux 2-core 费率 $0.006/min，Windows 2-core $0.010/min。

2. [Setting up budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets)
   - 任何适用预算启用了 `Stop usage when budget limit is reached` 并耗尽后，额外用量会被阻止。
   - Actions 产品级硬预算达到上限时，可阻止全部 GitHub-hosted runners，直到新账期或预算调整。

3. [Viewing metered usage](https://docs.github.com/en/billing/how-tos/products/view-productlicense-use)
   - 个人账户可在 https://github.com/settings/billing 查看 Usage。
   - 通过 Usage/Metered usage 页面按时间、SKU 和仓库查看消费。

## 6. 仓库所有者需要完成的人工检查

### A. 查看 Job Annotation

打开最新 job：
https://github.com/tortletortle/minecraft-mod-studio/actions/runs/45345393355/job/138279583726

查看顶部 Annotations：
- 如果出现 payment / spending limit / billing 错误，按计费路径处理。
- 如果没有 annotation 或内容是 runner provisioning/internal error，保留截图交 GitHub Support。

### B. 查看 Billing Usage

打开 https://github.com/settings/billing：

1. Usage → Actions：included compute、metered spend、当前账期、Usage blocked。
2. Budgets and alerts：Actions product-level、SKU-level、repository-level budget。
3. 查看每个适用预算是否启用 `Stop usage when budget limit is reached`。
4. 查看付款方式是否有效。

**先只读核查，不要未经所有者明确决定就添加付款方式、提高预算或启用付费。**

## 7. 修复决策树

### 分支 A：确认计费/预算拒绝

- 若 included usage 已用尽且不想付费：等待下个账期重置。
- 若有硬预算：所有者先明确支出上限，再决定是否调整预算；不要盲目放大。
- 若不希望继续使用 GitHub-hosted minutes，可评估可信隔离机器上的 self-hosted runner。官方 self-hosted runner 不扣 included compute usage。
- 不建议把私有仓库改为公开来规避计费；这会暴露代码、实验和未来配置。

### 分支 B：Billing 正常，无计费 Annotation

向 GitHub Support 提交：
- Repository：`tortletortle/minecraft-mod-studio`
- Last known good run：`44996410762`
- First failed run：`45040748148`
- Latest minimal smoke：`45345393355`
- Latest smoke job：`138279583726`
- Windows control：`45232956948`
- Workflow file：`.github/workflows/ci-runner-smoke.yml`
- Exact timestamps and observed fields: runner_id=0, runner_name empty, runner_group_id=0, steps=[], log download 404 BlobNotFound.
- Ask Support to check private hosted-runner eligibility, billing refusal reason and dispatch/provisioning telemetry for these run/job IDs.

### 分支 C：Self-hosted 临时方案

只有在确认是 GitHub-hosted billing gate 且不想启用付费时，再考虑：
- 独立 Linux VM 或专用机器。
- 只允许可信分支/受信任 PR。
- 不运行来自 fork 或不可信贡献者的代码。
- 不向 runner 放置生产密钥。
- 保留 runner 日志、环境信息和构建产物。
- 将它作为临时/受控执行通道，不把它误标为 GitHub-hosted CI 已恢复。

## 8. CI 成本与触发治理

当前项目在短时间内产生了 1,518 条 workflow run 记录。多分支、多工作流、连续 push 和 Windows 矩阵容易造成成本放大。

本轮检查到的触发配置例子：
- `feature/ai-debug-safe-shutdown-budget-v0.12.6/.github/workflows/ai-debug-lab.yml`：`push` 未限定 branches，只用路径过滤；相关路径每次提交都可能触发。
- `ai-debug-lab-windows.yml`：多个 branch 的 push / pull_request 都会触发 Windows runner。
- `ai-debug-lab-mcp.yml`：Ubuntu + Windows matrix，一次触发创建两个 job。
- `ai-debug-lab-live.yml`：两个 seed matrix，受 EULA 授权条件控制。
- UMPD Scanner 和 UI Workbench 也各有独立 push / pull_request 工作流。

建议在 runner 恢复后另开 CI cost-governance PR：
1. PR 快速门禁：静态检查、单测，Linux，控制在数分钟。
2. Integration PR：Fabric Gradle build、资源/浏览器验收。
3. Windows / 真正游戏内测试：手动或 nightly，只有集成候选触发。
4. 给所有 push 工作流加明确 branches + paths 过滤。
5. 每个 workflow/PR/branch 设置正确 concurrency group，cancel-in-progress。
6. 减少重复工作流；一次性推送相关提交，避免每个中间提交都触发矩阵。
7. 重型工作流提供 workflow_dispatch 输入，显式授权。
8. 不对 runner_id=0 / steps=[] 的失败做自动无限重试。
9. 恢复 main branch ruleset/required checks，确保只合并有可复核证据的提交。

## 9. 当前执行边界

- PR #1 不合并。
- [PR #32](https://github.com/tortletortle/minecraft-mod-studio/pull/32) 保持开放，仅作为 runner 诊断。
- 看板由 Draft PR #29 的 `agent/pm/w0-w1-dashboard` 分支维护。
- main `867e1bd37df2f039a395779493efb8cb20093287` 未修改。
- 当前没有新增 Fabric、Chromium 或 Minecraft 实机通过证据。
- 在所有者提供 Annotation 与 Billing Usage 证据之前，根因状态保持 **待确认**。

## 10. 参考案例（非官方根因确认）

- [GitHub Community #213180](https://github.com/orgs/community/discussions/213180)：报告 Free 私有仓库 $12/$12 included usage、$0 budget、Usage blocked、无付款方式，并出现 runner_id=0 / steps=[] / BlobNotFound。
- [GitHub Community #211596](https://github.com/orgs/community/discussions/211596)：相同故障特征；回复建议读取 job 页面顶部 Annotation。
- [GitHub Status](https://www.githubstatus.com/)：2026-11-22 至 2026-11-24 未列出公开 Actions 事故，当前显示 Operational。
