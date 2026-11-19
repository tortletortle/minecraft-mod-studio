# Minecraft Mod Studio V1.9 — Test report

## Scope
Portable JSON function packs for explicit copying between item graphs and projects. Canonicalized typed AST, atomic merge, identical-definition deduplication, conflicting-ID rejection, dependency and recursion validation, 256 KiB input cap, 16-function limit. No live global linkage. Imports remain draft-only until Apply.

- New portable-pack logic: 50 assertions passed.
- New Chromium pack interactions: 9 assertions passed (download, merge, conflicts, cancellation, apply, execution).
- V1.8 editor unit checks: 153 passed; Chromium regression: 21 passed.
- Source export: 47 assertions, 18 inline scripts, 64 files.
- Function engine: 378 assertions; 92 generated Java programs executed and compared with JS.
- Earlier logic engine: 283 assertions; 87 generated Java programs compared with JS.
- Build Doctor: 14 tests passed.
- Runtime trace parser: 8 tests passed; Java trace harness and 2 controller stub classes compiled.
- Source preflight: PASS; full build: ENVIRONMENT_BLOCKED (JDK 21 present, required JDK 25 and Gradle 9.5.1 unavailable). Real Fabric build and Minecraft runtime NOT RUN. Chromium uses set_content; actual origin-specific browser persistence unverified.

## Reproduce
From the package directory, run `node tests/test_v18.js` to generate fixture, then `node tests/test_editor_v18.js`, `node tests/test_functions_v17.js`, `node tests/test_logic_v16.js`, `python tests/test_build_doctor.py`, `bash tests/test_trace_java.sh`, `node tests/test_trace.js` and `bash tests/compile_controller_stubs.sh`. Browser checks require Python Playwright and Chromium at `/usr/bin/chromium` (`python tests/test_logic_browser.py`). Additionally run `node tests/test_pack_v19.js` and `python tests/test_pack_browser.py`.
