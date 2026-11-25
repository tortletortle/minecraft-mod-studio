# Windows 单元测试与 MCP 兼容性独立复核

测试日期：2026-11-20（Asia/Shanghai）。被测源码提交：4d5e01d82547ec6fa4f8a6cfcf089ca0396e34ec。

结论：普通单元测试未全套通过；65 项中 64 项通过，1 项因 Windows 符号链接权限导致夹具建立失败。独立 MCP 兼容性测试 3/3 通过。

| 命令 | 返回码 | 结果 | 进程墙钟耗时 | unittest 内部耗时 |
|---|---:|---|---:|---:|
| python -m unittest discover -s ai-debug-lab -p test_*.py -v | 1 | 64 PASS，1 ERROR，0 assertion failures | 1.359 s | 0.766 s |
| python -m unittest discover -s ai-debug-lab -p mcp_checks.py -v | 0 | 3 PASS | 5.938 s | 2.521 s |

## Windows 符号链接失败的精确解释

用例：test_ide_bridge.BridgeTests.test_symlink_denied。

源码 test_ide_bridge.py 第 46 行先移除临时夹具中的 logs/latest.log，第 47 行调用 p.symlink_to(self.root / "missing")，试图建立一个指向同一临时目录内不存在目标的符号链接。Python pathlib.py 第 1386 行转调 os.symlink；Windows 返回 WinError 1314（客户端没有所需的特权）。

因此，夹具尚未建立，第 48 行 self.assertFalse(self.call("logs.tail", {})["ok"]) 未执行。该结果说明本机当前进程无法完成此符号链接测试前置条件，不能证明 Bridge 的符号链接拒绝逻辑通过，也不能据此断言该拒绝逻辑有缺陷。未修改系统权限、未启用开发者模式、未以管理员权限重跑。

脱敏 trace 摘要：

    <REPO>/ai-debug-lab/test_ide_bridge.py:47
        p.symlink_to(self.root/"missing")
    <USER_HOME>/.../Python312/Lib/pathlib.py:1386
        os.symlink(target, self, target_is_directory)
    OSError: [WinError 1314] 客户端没有所需的特权。

## 本机实际核查的工具链

- Windows 11，Python platform 标识 Windows-11-10.0.26200-SP0，amd64。
- Python 3.12.10。
- 官方 Python MCP SDK 2.3.0（读取已安装 distribution 元数据核实）。
- Temurin / Eclipse Adoptium JDK 25.0.5+8-LTS，java -version 已执行核实。
- 本地独立 Gradle 9.5.1，--version 返回 0，Launcher JVM 25.0.5；仅对子进程设置 JAVA_HOME。
- Git 2.55.0.windows.3；GitHub CLI 2.100.0；Node.js v24.19.0。

## 必须保留的验收限制

1. 不能称 65 项普通单元测试全部通过，符号链接边界用例在本机属于环境阻塞，目标断言未执行。
2. 3 项 MCP 兼容性测试包含内存和真实 stdio 子进程通信；这是协议/适配器验收，不是外部 AI 对真实游戏的自主控制验收。真实 Minecraft 运行结果由主测试另行记录。
3. MCP 日志中的 Unknown tool 和 rejected arguments 是测试主动发起的非法调用，预期被拒绝后测试通过，不能把这些诊断行单独误报为失败。
4. 本子任务没有执行 Java 游戏服务器、世界写入、tick 步进或配方运行验证，也没有进行渲染、FPS、模组包兼容性或跨平台验收。
5. 本次仅在该 Windows 主机和该提交上执行；没有通过更改权限绕过失败，也没有把 Linux CI 历史结果计入本次通过数量。

## 证据与上传脱敏

- 普通单测：unit/result.redacted.json、unit/stdout.redacted.log、unit/stderr.redacted.log。
- MCP 单测：unit/mcp-result.redacted.json、unit/mcp-stdout.redacted.log、unit/mcp-stderr.redacted.log。
- 原始未脱敏副本保留在相同本地目录，不建议上传。原始普通单测 stderr 含 2 处本机用户路径匹配，MCP stderr 含 9 处；脱敏副本已替换仓库与用户主目录，复核均不含本机用户名。
- 本轮模式扫描未发现 GitHub token、私钥、凭据赋值或邮箱；此扫描结果不是对任意敏感数据的绝对保证。上传仍应只选择本轮脱敏证据和结论。

未修改仓库源码、依赖或 Git 历史。仅写入工作区 outputs 中的日志、结构化结果与本摘要。
