# Minecraft Mod Studio V2.1 — Fabric build and development-server acceptance

Baseline: V2.0 Git commit `5b6bb9a`. Retained project schema, compiler version 1.9.0, Minecraft 26.2 export backend and V2.0 debugger. No Rust backend work.

## Implemented
- The export now contains `studio_smoke.py`, an opt-in Linux development-server boot observer. It checks the unchanged export snapshot, verified build receipt and JAR hash, pinned toolchain, and a fresh run directory before starting `gradle runServer`. It requires both a generated `STUDIO_INIT_V1 <modId>` marker after main mod initialization and a server-ready message. It requires explicit EULA acceptance and binds a disposable development server to loopback with an ephemeral port. It attempts to terminate the POSIX process group on success or failure. It does not assert gameplay, graceful shutdown, packaged JAR runtime or client rendering.
- A manually dispatched GitHub Actions workflow installs JDK 25 / Gradle 9.5.1, generates the expanded regression export, runs the real build and optionally the development-server boot observer, and retains JAR/log/receipt artifacts even when checks fail. The workflow YAML was parsed locally but has not been dispatched remotely.
- Expanded regression export covers graph and legacy lightning items, custom recipe, ore/block, three mobs with varied AI/animation controllers. Output includes 79 files (including build scripts/metadata).

## Executed checks
| Check | Observed result |
|---|---|
| Source export | 52 assertions passed, 18 inline scripts parsed, 79 export files |
| Build Doctor | 14/14 unit tests passed (synthetic JAR and subprocess checks) |
| V2.1 boot observer | 10/10 unit/integration tests passed (fake Gradle processes, synthetic JAR; not Minecraft) |
| V2.0 debugger | 679 assertions passed, 160 historical differential cases |
| Function pack | 50 assertions passed |
| Chromium debugger | 18 real browser assertions passed |
| Java controller syntax/API stubs | 2 classes compiled with JDK 21 against stubs |
| Real Fabric build attempt | ENVIRONMENT_BLOCKED; export source PASS; actual Gradle not run; report in tests/v21-real-build-attempt.json |
| Real Minecraft server/client | NOT_RUN |

Environment: JDK 21.0.12.1, no Gradle binary, DNS resolution failures for maven.fabricmc.net and services.gradle.org. Official Fabric 26.2 guidance confirms JDK 25 / Loom 1.17 / Gradle 9.5.1 generation: https://fabricmc.net/2026/06/15/262.html and https://docs.fabricmc.net/develop/getting-started/setting-up. Exact pinned dependency patch versions in existing backend not resolved from this sandbox. No GitHub push or workflow execution. No mod JAR produced.

## Reproduce
In repository: `node tests/test_v18.js`, `python3 tests/test_build_doctor.py`, `python3 tests/test_smoke_v21.py`, `node tests/test_debug_v20.js`, `node tests/test_pack_v19.js`, `python3 tests/test_debug_browser.py`, `bash tests/compile_controller_stubs.sh`. The boot tests use fake processes and need Linux; the historical debugger comparison needs Git history. To attempt real validation, use the Fabric export verification workflow on GitHub or extract `tests/generated-fixture.zip` into a new directory and run `python3 studio_build.py build` with JDK 25 and Gradle 9.5.1. Read the EULA (https://aka.ms/MinecraftEULA); if accepted and on a disposable Linux environment run `python3 studio_smoke.py --accept-eula`. Do not run untrusted exports or reuse a real world. Logs record success/failure separately.
