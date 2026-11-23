# V0.12.1 — Windows AI acceptance follow-up
Source: PR #3, test/local-ai-playtest-20261120, tested 4d5e01d; evidence remains unchanged.
- Join exact configured recipe and tag evidence, capture memory check separately. Never treat an unrelated target or truncated tag as complete. No general runtime query or player crafting claim.
- Stable MCP step-budget error before mutation; regression test. Serialize status polls with actions.
- Windows nonprivileged symlink setup error becomes explicit skip (not pass); actual symlink boundary still exercised on Linux. Windows junction rejection and Windows-specific fixture added; run on Windows before claiming coverage.
- Explicit flat layers; live playtest asserts absence of prior layers error, not all terrain correctness.
- Startup observations, actual elapsed time, network warning and explicit 600 s deadline. No latency improvement claimed; the previous 229 s is one sample. Measure repeat fresh starts and use stage evidence before implementing/cache trusting downloaded runtime files.
- Scripted CI and independent external AI retest are separate. No UI/third-party pack claim.
