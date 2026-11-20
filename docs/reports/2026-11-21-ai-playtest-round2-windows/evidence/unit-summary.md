# Round 2 Python / MCP acceptance

Tested commit: 092f5656c51ea66016ee313630ec1807c49e2255.
Environment: Windows 11 build 26200, Python 3.12.10, MCP SDK 2.3.0.
Only subprocess-local PYTHONDONTWRITEBYTECODE=1 and PYTHONUTF8=1 were set. No elevation, global configuration changes, Minecraft startup, or user-process termination occurred.

| Test command | Total | PASS | SKIP | ERROR | FAIL | Exit | Process wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| python -m unittest discover -s ai-debug-lab -p test_*.py -v | 72 | 71 | 1 | 0 | 0 | 0 | 1.141 s |
| python -m unittest discover -s ai-debug-lab -p mcp_checks.py -v | 4 | 4 | 0 | 0 | 0 | 0 | 2.781 s |

Unittest-reported durations: ordinary 0.771 s; MCP 1.390 s. UTC timestamps and all per-case classifications are retained in the result JSON files.

- test_symlink_denied: explicit SKIP because Windows symlink creation requires privilege (WinError 1314). Its Bridge symlink-rejection assertion did not run and must not be counted as PASS.
- test_windows_junction_denied: executed and PASS. It creates a real Windows directory junction with mklink /J targeting an external temporary directory, confirms is_junction(), verifies logs.tail rejection and the symlink refused message, then removes its own temporary junction.
- All four MCP tests passed, including an actual stdio subprocess. test_playtest_step_budget uses a Fake object for the MCP argument boundary and does not replace real Minecraft action-budget acceptance.
- Unknown tool, rejected arguments, and Step budget exceeded messages are expected negative-test rejections; the final unittest summary is OK.

Original stdout/stderr bytes were retained. Files named *.redacted.* remove local user-home paths, including double-backslash repr paths in asyncio logs. A second scan found no local username/path, GitHub token, private-key header, credential assignment, or email remaining.

Upload-safe files: result.redacted.json, stdout.redacted.log, stderr.redacted.log, mcp-result.redacted.json, mcp-stdout.redacted.log, mcp-stderr.redacted.log, and this summary. Raw result JSON files and raw logs are local-only.
