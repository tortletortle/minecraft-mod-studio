# Minecraft Mod Studio V2.0 — Blueprint preview debugger

Baseline: Git commit `939f596` (V1.9). No project or graph schema migration. Debug state and breakpoints are transient and do not alter generated Java or exported graphs.

## Implemented
- One resumable generator-based interpreter serves the original trace preview and the debugger. Node breakpoints pause before execution, including repeated visits. Step into stops at node and function entry/return boundaries; step over advances to the next node. This is not expression-level stepping.
- A highlighted current node and marked breakpoints, variable and loop counter snapshots, pure function arguments/call stack/return values, fault reasons, and simulated effects. A graph/context edit invalidates the running session; reopening resets breakpoints.
- Snapshot copying is deferred until inspecting a paused state; skipped events do not copy the full trace. Preview state is isolated from graph edits and returned snapshots.

## Executed verification
| Check | Result |
|---|---|
| Debugger unit/differential | 679 assertions passed; 160 deterministic generated fixture/context combinations compared with the independently loaded V1.9 interpreter (including full trace/effects/variables and completion) |
| Chromium debugger | 18 browser assertions passed; actual click/step/continue/reset/context invalidation/apply/reopen, no page errors |
| Source export | 47 assertions passed; 18 scripts parsed; 64 source files generated |
| Function engine | 378 assertions passed; 92 generated Java programs executed against JS |
| Logic engine | 283 assertions passed; 87 generated Java programs executed against JS |
| Function subgraph editor | 153 assertions passed |
| Portable function packs | 50 assertions passed |
| Build Doctor, trace, controller stubs | 14 doctor tests, 8 trace tests, Java trace harness and 2 controller stub classes passed before final UI/snapshot-only refinement |

New browser test uses Chromium `set_content`, not a deployed origin. Existing V1.9 browser suites not rerun in this iteration. Actual Fabric/Gradle compilation, game launch, GameTest and world effects: NOT RUN (JDK 21 only; Gradle unavailable). No GitHub repository found by connected repository search; no remote push. Desktop preview only; mobile layout not verified.

## Reproduce
Clone the Git bundle (`git clone minecraft-mod-studio-v2.0.git.bundle studio`), then run `node tests/test_debug_v20.js`, `python tests/test_debug_browser.py` (Python Playwright and /usr/bin/chromium), `node tests/test_v18.js`, `node tests/test_functions_v17.js`, `node tests/test_logic_v16.js`, `node tests/test_editor_v18.js`, `node tests/test_pack_v19.js`. Java tests use JDK 21 for pure generated harnesses, not the Fabric toolchain. For remaining checks: `python tests/test_build_doctor.py`, `bash tests/test_trace_java.sh`, `node tests/test_trace.js`, `bash tests/compile_controller_stubs.sh`.

## Next
Prioritize a reproducible real Fabric build and runtime smoke-test before expanding the set of supported Minecraft world operations. A preview debugger cannot prove that Minecraft runtime effects work.
