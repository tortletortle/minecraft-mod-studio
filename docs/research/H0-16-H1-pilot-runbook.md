# H0.16 · H1 admission and first content-port runbook
2026-11-21 | H0 only | all actual SDK/game steps NOT_RUN.
Main baseline: f4070b207cc916df7e138c6c6009778df85e8049; V2.5 README still reports no real Fabric compile/game/render acceptance. Do not start H1, modify main, merge or add production dependencies until the agreed Java gate is met.

## 1. Crucial correction: upstream and fork are distinct targets
Public docs checked 2026-11-21:
- https://playhorizon.dev/docs/make-a-mod describes upstream content/native/Wasm workflows and installation from horizon-rust/horizon.
- https://arismoko.github.io/horizon/how-to/publish.html explicitly limits its fork-specific code API to fork builds, advises against submitting those code mods to the upstream registry, and limits portable content to features shared with upstream.
- https://arismoko.github.io/horizon/reference/sdk/05-commands.html describes code SDK pins; a content project has no code SDK.
- https://arismoko.github.io/horizon/start/first-content-mod.html documents the fork's initial block example.
- https://arismoko.github.io/horizon/how-to/content-mods.html documents fork API 0.2 content registries, components, manifest sides and namespace rules.
- https://arismoko.github.io/horizon/start/installing.html documents install/enable and restart.
These are active docs and may not correspond to the same shipped build. The official site broadly describes code mods, while the fork expressly warns its API is not yet portable. Treat this as a release compatibility risk, not evidence that the APIs are identical or that upstream supports no code mods. Pin independently; later check the published upstream release and its matching API before claiming support. Prefer upstream as the first product target; fork is an optional independent research profile. No registry publication planned.

## 2. Admission and profile locking
Before running H1 require actual evidence of the Java core build and installed-JAR gameplay, plus user-authorized isolated game environment. Record source repo+commit, JAR SHA256, Java game version and loader, Java acceptance evidence, target repository URL, full game/build commit, launcher build, tool repository+full revision, tool binary SHA256, content API/package format, OS/architecture and exact command output. For code only, additionally record SDK index+surface hashes, SDK/mixins revisions and dependency lock. Content tooling need not fetch a code SDK. All actual target identifiers are UNSET now; do not fabricate them.
A profile is target-specific; failure on a fork or upstream release cannot be generalized to all Horizon. Do not use floating main/HEAD for a reproducibility claim. Do not redistribute Minecraft assets or unlicensed third-party content.

## 3. P0 control — run vendor's own content sample without Studio
After admission, select a released upstream game and matching upstream CLI from the upstream documentation. For the optional fork repeat independently using fork CLI and fork launcher. Commands below are templates, unexecuted; fill the 40-hex revision and validate exact command syntax against the chosen checkout. Install into separate tool roots and separate CARGO_HOME/instance directories; do not replace an existing user's setup.

    cargo install --locked --git <selected-tool-repository> --rev <confirmed-tool-commit> --root <isolated-tool-root> cargo-horizon-mod
    cargo horizon-mod new rd001-control
    cd rd001-control
    cargo horizon-mod build
    cargo horizon-mod check target/horizon-mod/rd001_control.hmod

Verify PATH resolves the isolated tool; record rustc/cargo versions and tool hash. Use scaffold manifest id for actual output filename (do not assume the illustrative name). Use the selected game's documented installation flow: content package into horizon-mods in a disposable instance, enable the exact id, restart and verify the Mods page AND actual registry/world effects. Test template recipe, placement, break/drop, save/reload. Preserve source/output hashes, config, logs and screenshot or independent game observations. A boot alone is not success. If the unchanged vendor sample fails, classify environment/SDK mismatch or upstream failure first; do not attribute to Studio. Reproduce and retain failed evidence. Scope all observations to the selected version.

## 4. P1 pilot — original Research Coil
Use existing research/horizon/materialize.py and fixtures/static-content-v1.json in scratch areas; these generate resource ZIP inputs, not mods. The experimental negative archives stay separate. After P0 passes, scaffold a fresh content mod with namespace rd001, adapt only the self-authored resources from the base fixture, keep upstream manifest format; candidate item declaration path data/rd001/horizon/item/coil.json, vanilla inert template minecraft:copper_ingot with explicit stack count 64 if supported (check exact schema on pinned target). Do not copy the example block unintentionally or assume item-specific behavior from a template. Set both-side registration if required by target manifest; verify on the exact build. Recipe and tag schemas must be checked for Java 26.2 to 26.3 changes separately. The content files must include the previously missing actual item registration, not merely texture+recipe.
Build/check via vendor CLI; inspect archive file list and hash. On isolated game instances check:
- registry contains rd001:coil, stack size 64, custom model/texture and displayed name;
- three copper ingots in the specified recipe pattern produce exactly one coil; wrong material does not produce this recipe output;
- after save/reload, the obtained item retains its registry identity and count;
- missing texture and namespace collision diagnostic-only tests never silently overwrite the valid fixture or mutate the baseline instance;
- if test cannot observe a required result, mark NOT_RUN or UNKNOWN, not PASS.
C02/C03/C04 only; block-specific C01 stays as P0 control and requires a separate self-authored pilot later. Compare with the same-version Java reference (including separate 26.2 vs 26.3 baseline). No invented equivalence if source item not registered/tested in actual Java. First manually establish that the target can load a correct package before automating the translation. Where official port-pack applies to the same authorized input, use it as an independent baseline; if it requires a different input type, record NOT_APPLICABLE until a proper JAR fixture exists. Do not score a mismatch in input as a product advantage.

## 5. Required records
One directory per target/version/run with input hash, environment, exact CLI command and exit code, original package hash, complete logs, registry and gameplay observations, failures and notes. Distinguish TOOL_INSTALL, SCAFFOLD, PACKAGE, CHECK, LOAD, GAMEPLAY, PERSISTENCE, JAVA_REFERENCE, PARITY; each independently NOT_RUN/PASS/FAIL/UNKNOWN/NOT_APPLICABLE with evidence. Do not elevate synthetic experiment reports to actual game results. No performance claim or compatibility percentage from this pilot. Abort if Java gate absent; H0 remains complete enough and does not need additional synthetic infrastructure.
