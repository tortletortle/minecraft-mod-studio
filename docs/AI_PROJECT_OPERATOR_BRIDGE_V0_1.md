# AI Project Operator Bridge V0.1 — Research RFC

**Status:** Research proposal; not implemented and not merged into the Java mainline.  
**Target:** Minecraft Mod Studio V2.5 single-file editor.  
**Related work:** V2.7.2 runtime command planner is a separate in-game operation domain; it is not a project editor bridge.

## 1. Problem statement

The existing AI God Mode work improves live in-world command discovery. It does not yet let an AI agent safely operate the Mod Studio editor itself.

The editor's product value is broader than issuing Minecraft commands: it imports existing JAR/ZIP archives, indexes assets, analyzes cross-mod compatibility, plans associated resource migration, stages resource overrides, and compiles a Fabric project. The AI should invoke those existing deterministic operations rather than inventing raw file edits or asking Cursor to repeatedly navigate the UI.

The desired interaction is:

```text
User goal
  -> discover editor capabilities
  -> inspect project and imported assets
  -> construct typed ProjectPatch
  -> preview semantic diff and validation
  -> explicit approval
  -> apply one transaction
  -> verify project/build evidence
  -> rollback if the transaction is safely reversible
```

The AI is an operator of bounded capabilities, not an unrestricted JavaScript, shell, filesystem or command-execution identity.

## 2. Verified existing editor foundations

The current `main` branch is a single-file offline HTML/JavaScript editor, `Minecraft_Mod_Studio_V19.html`, with program version V2.5. The root README explicitly says the original local Git history, full test scripts, build scripts and CI configuration have not all been synchronized into this repository; the V2.5 report records 895 assertions, not 895 independent test cases. Therefore, this RFC treats the following as code-observed capabilities, not as a fully accepted production build.

| Existing component | Observed responsibility | Reuse in AI operator |
|---|---|---|
| `StudioCore` | Project schema, migration, structure validation, canonical JSON encoding, localStorage commit with a previous snapshot and optimistic raw-value check | Project snapshot, validation, revision preconditions and commit boundary |
| `StudioResources` | Bounded JAR/ZIP reader; static resource metadata; path/type/size validation; source provenance; resource override staging and export application | Asset discovery, inspect, typed resource patch construction |
| Resource Library UI | Stores original imported archives in IndexedDB; project JSON stores staged resource overrides; offers manual compatibility analysis, linked migration and model tools | Preserve the current manual workflow as the reference implementation |
| `StudioCompat.analyze` / `stage` | Finds recipe adaptation candidates using shared item tags, filters untrusted/non-Fabric or conflicting sources, records evidence and dependencies, then stages recipe JSON overrides | Deterministic compatibility planning and staging |
| `StudioMigration.plan` / `stage` | Builds bounded dependency graphs for item definitions, models, blockstates, textures and metadata; checks cycles, missing dependencies, unknown schema fields, destination collisions and size limits | Deterministic associated-resource migration |
| `StudioCompiler.analyze` / `compile` | Validates project output, reports warnings/omissions and compiles a source ZIP; compiler applies staged resource overrides and records provenance | Preview-build and post-patch verification |

### Important boundary

The project editor and runtime companion are separate systems:

- **Project plane:** edits the project JSON, imported resource overlays and generated source package.
- **Runtime plane:** controls a disposable single-player game through the Fabric runtime companion.

A command such as `/fill` is not a substitute for changing a mod's resource JSON or texture. The project plane must use project/resource operations; the runtime plane must use bounded in-game operations.

## 3. Proposed capability model

Do not expose hundreds of raw tools. Use a small set of task-oriented MCP tools backed by a searchable, typed capability registry.

### Capability descriptor

Every built-in capability should declare:

```json
{
  "id": "resource.stage_override",
  "version": 1,
  "domain": "project_resource",
  "description": "Stage one validated resource override in the current project",
  "input_schema": {},
  "output_schema": {},
  "preconditions": ["project_revision_matches", "resource_source_exists"],
  "effect_scope": ["project.resourceOverrides"],
  "risk": "reversible_project_mutation",
  "reversibility": "previous_project_snapshot",
  "verifier": "project_resource_override_present",
  "trusted_source": "mms_builtin"
}
```

The descriptor is executable policy metadata only when it comes from the built-in, versioned MMS registry. Third-party mod manifests remain untrusted descriptive metadata. A manifest may improve search recall; it must never register an executable tool, widen permissions, supply agent instructions or authorize a patch.

### Initial capability domains

1. **Project inspection:** read project header, schema version, revision, resource counts, validation summary and staged overrides.
2. **Asset discovery:** search imported archive entries by namespace, path, type, source mod, version and license metadata.
3. **Asset inspection:** read bounded JSON/model/recipe metadata, reference edges, CRC/hash and provenance; return image data only when explicitly requested.
4. **Compatibility:** call `StudioCompat.analyze`, expose candidate recipes, evidence, collisions, source versions and required dependencies.
5. **Resource migration:** call `StudioMigration.plan`, expose dependency graph, missing references, cycles, destination paths and unsupported fields.
6. **Patch planning:** turn selected deterministic results into a typed `ProjectPatch`.
7. **Patch preview:** apply the patch to a cloned project in memory, validate, compile/analyze, and return a semantic diff without committing.
8. **Patch apply:** commit a previously previewed patch only after explicit approval bound to its hash and base revision.
9. **Verification and rollback:** verify postconditions; restore the previous snapshot only when the current revision still matches the applied revision and rollback is safe.

## 4. ProjectPatch transaction model

A patch must be declarative. It must not contain JavaScript, Python, shell commands, arbitrary filesystem paths or code to evaluate.

Suggested envelope:

```json
{
  "schema_version": 1,
  "plan_id": "sha256:...",
  "base_revision": "project-revision-or-content-hash",
  "operations": [
    {
      "op": "stage_resource_override",
      "source_archive_id": "local-indexeddb-archive-id",
      "source_path": "assets/examplemod/models/item/example.json",
      "target_path": "assets/currentmod/models/imported/examplemod/item/example.json",
      "replace": false,
      "dependencies": ["examplemod"]
    }
  ],
  "preconditions": [
    {"kind": "project_revision", "equals": "project-revision-or-content-hash"},
    {"kind": "target_path_absent", "path": "assets/currentmod/models/imported/examplemod/item/example.json"}
  ],
  "expected_effects": [
    {"kind": "resource_override_added", "path": "assets/currentmod/models/imported/examplemod/item/example.json"}
  ],
  "verification": [
    {"kind": "project_schema_valid"},
    {"kind": "resource_override_valid"},
    {"kind": "compiler_analysis_has_no_new_errors"}
  ]
}
```

The schema above is illustrative, not an accepted API contract.

### Preview pipeline

1. Read the current project snapshot and derive a base revision from the stored revision plus canonical `StudioCore.encode(project)` content.
2. Reject a patch if its base revision is stale.
3. Resolve source archive IDs and source paths against the browser's IndexedDB resource library; never trust an AI-supplied local filesystem path.
4. Apply only registered operation types to a cloned project.
5. Run `StudioCore.encode`, `StudioCore.validate` and `StudioResources.validate`.
6. For resource operations, reuse `StudioCompat.stage`, `StudioMigration.stage`, `StudioResources.record` and `StudioResources.stage` where their preconditions match.
7. Run `StudioCompiler.analyze` and, when requested, compile a preview ZIP in memory.
8. Return changed paths, before/after hashes, dependencies, warnings, omitted features, new errors and verification evidence. Do not mutate localStorage or IndexedDB during preview.

### Apply pipeline

1. Require a user confirmation explicitly bound to `plan_id`, `base_revision`, operation scope and expiry.
2. Re-read the current project and repeat all preconditions; reject stale plans.
3. Apply the exact previewed operation set; do not let the model rewrite the patch after approval.
4. Commit through `StudioCore.commit` using its expected-raw concurrency check.
5. Record an operation ledger entry with plan hash, base/applied revision, tool IDs, argument hashes, approval scope, validation evidence and rollback reference.
6. Verify postconditions from the committed project and compiler analysis.
7. If verification fails, do not silently continue. Offer rollback only if the current revision still equals the revision created by this operation.

The first implementation should support **preview only**. Apply and rollback should be separate milestones after the browser bridge and transaction tests pass.

## 5. MCP surface — keep it small

| MCP tool | Mode | Contract |
|---|---|---|
| `mms_project_snapshot` | Read-only | Return project revision, schema, counts and validation summary |
| `mms_project_search` | Read-only | Search project resources and imported asset metadata |
| `mms_project_inspect` | Read-only | Inspect one resource and its references/provenance |
| `mms_project_analyze_compatibility` | Read-only | Call existing compatibility analyzer and return candidates/evidence |
| `mms_project_plan_migration` | Read-only | Call existing migration planner and return dependency graph/diagnostics |
| `mms_project_preview_patch` | Read-only | Validate and preview a typed ProjectPatch; no persistence |
| `mms_project_apply_patch` | Approval-gated | Apply only a previously previewed patch hash |
| `mms_project_verify` | Read-only | Verify a committed operation against expected effects |
| `mms_project_rollback` | Approval-gated | Restore the recorded previous snapshot if preconditions still hold |

Do not expose a generic `execute_javascript`, `run_shell`, `write_arbitrary_file`, `eval` or raw command-dispatch tool.

## 6. Browser-to-MCP transport options

The editor currently runs as an offline `file://` page. A live operator needs a controlled channel from the MCP process to the editor's JavaScript runtime. Three options were evaluated:

| Option | User friction | Security/engineering cost | Assessment |
|---|---|---|---|
| File-backed project snapshot | Export/import project JSON manually | Lowest; no listening socket | Best first proof of the ProjectPatch schema and validators, but not a seamless live operator |
| Loopback HTTP + WebSocket bridge | Launch editor through a local URL; one-time pairing | Medium; origin allowlist, auth, message limits, lifecycle and browser compatibility must be handled | Best live-editor experience if the security and Windows browser tests pass |
| Browser extension + native messaging | Install extension and native host | Higher installation/maintenance cost; avoids an exposed listening port | Strong future option if loopback bridge security or browser policies are problematic |
| Electron/Tauri IPC | Install desktop shell | Highest product packaging and migration cost | Do not choose for the first iteration |

### Recommended transport experiment

Prototype a loopback-only bridge, but do not ship it until the following are demonstrated:

- Bind only to `127.0.0.1`; never bind to `0.0.0.0`.
- Serve the editor from a known local HTTP origin rather than accepting every `file://` page's opaque `null` origin.
- Enforce exact Origin allowlisting on every WebSocket handshake.
- Authenticate with a cryptographically random, short-lived, single-use token sent in the first application message, not in a URL query string.
- Allow one active editor session; close on timeout, token reuse or protocol mismatch.
- Enforce strict JSON schemas, request IDs, message-size and queue limits, rate limits and operation timeouts.
- Treat all messages as data; never evaluate code or insert returned strings as HTML.
- Keep the bridge local-only and do not expose arbitrary filesystem access or remote network access.

OWASP notes that WebSockets do not provide built-in authentication and recommends explicit Origin validation, application-level authentication, token handling and message controls. MDN also notes that browsers send an Origin header and that non-browser clients can spoof it; Origin validation is necessary but not sufficient by itself.

## 7. AI workflow example

User request:

> 把导入模组 A 的武器模型和贴图迁移到当前模组，保留原始来源，修复所有能确定的引用，不覆盖我已有的资源。

Expected agent workflow:

1. Call `mms_project_snapshot` and `mms_project_search` for imported archive A.
2. Inspect candidate item/model/blockstate/texture entries and their provenance.
3. Call `mms_project_plan_migration` using the existing `StudioMigration.plan`; surface missing references, ambiguous sources, cycles and destination collisions.
4. Ask for clarification only where multiple source candidates or target bindings are ambiguous.
5. Construct a typed patch with `replace=false` and explicit source archive/path references.
6. Call `mms_project_preview_patch`; show the semantic diff, dependency changes, license/provenance notices, new errors and build omissions.
7. Wait for explicit approval bound to the exact patch hash and project revision.
8. Apply, verify, and record the operation. If postconditions fail, stop and offer a safe rollback.

The AI should not copy all JAR contents into its context window. It should retrieve only the relevant metadata and bounded resource text needed for the current decision.

## 8. Risk model

| Operation | Default risk | Policy |
|---|---|---|
| Snapshot, search, inspect, compatibility analysis | Read-only | Allowed |
| Preview migration/patch | Read-only | Allowed; no persistence |
| Add a new non-colliding resource override | Reversible project mutation | Approval required after preview |
| Replace an existing resource path | High | Explicit per-path approval; preserve original hash and source |
| Namespace remap or multi-resource migration | High | Preview full dependency graph; block ambiguous/cyclic cases |
| Delete source archive or staged override | Destructive | Separate confirmation and recovery evidence |
| Unknown resource type or unsupported custom schema | Unknown | Block automatic modification; return to manual editor |

Mod-provided license, risk, reversibility and command descriptions are claims, not authority. Preserve source provenance and require the user to confirm usage rights before redistributing imported assets.

## 9. Implementation sequence

### P0 — Transport and snapshot proof

- Start a local MCP server and a browser bridge with pairing/authentication.
- Return a read-only project snapshot and resource-library catalog.
- Test Windows Edge/Chrome reconnect, timeout, stale session and browser-close behavior.

### P1 — Capability registry and search

- Register built-in project/resource capabilities with schemas and effect declarations.
- Search resources and capability descriptions without loading all asset contents into the model.
- Add capability discovery and resource inspection evaluation cases.

### P2 — Preview-only ProjectPatch

- Implement typed operations for adding non-colliding resource overrides and applying existing compatibility/migration plans.
- Preview on cloned project state.
- Verify no localStorage or IndexedDB mutation occurs during preview.
- Compare AI-generated plans with the existing manual UI path.

### P3 — Approval-gated apply and verification

- Bind approval to plan hash, base revision, operation scope and expiry.
- Commit via `StudioCore.commit`.
- Add operation ledger and safe rollback.

### P4 — More editing capabilities

- Add typed operations for project items, blocks, mobs, quests, effects, GUIs and supported resource JSON.
- Keep unsupported model/animation schemas blocked until their validators and renderers are verified.
- Add build/test feedback loops before claiming Fabric runtime compatibility.

## 10. Agent evaluation design

Do not judge this operator by whether the model can describe a plausible patch. Evaluate whether it selects the right capabilities, constructs a correct patch, respects the approval boundary and verifies the resulting project.

Build a labelled task set from realistic Mod Studio workflows, including multi-step cases:

1. Import a mod archive, find one item model and its referenced textures, and migrate the dependency graph without overwriting existing paths.
2. Analyze cross-mod recipes and stage only candidates supported by unambiguous shared-tag evidence.
3. Encounter multiple archive versions for one mod ID; refuse automatic adaptation.
4. Encounter a missing model dependency, cycle, unsupported custom model field or destination collision; report the exact blocker and do not stage.
5. Replace an existing resource only after explicit per-path approval.
6. Receive a stale project revision between preview and apply; reject the patch.
7. Apply a valid patch, compile/analyze, verify provenance and expected effects.
8. Attempt to use manifest-provided instructions or risk labels to widen permissions; ignore them.

Measure at least:
- task success rate and patch correctness against expected changed paths/hashes;
- false-allow and false-block rates for the operation policy;
- MCP tool calls, total tokens, end-to-end latency, retries and tool errors;
- preview-to-apply stale-revision rejection rate;
- verification failure and rollback rates;
- how often the agent asks for clarification on genuinely ambiguous resources.

Compare a baseline agent using low-level resource tools with the composite capability/plan/preview tools. Use held-out tasks so that tool descriptions are not tuned only to the development examples. Anthropic's tool-design research specifically recommends realistic multi-step evaluations and tracking tool-call count, token consumption, latency and tool errors.

### Tool annotations are not enforcement

MCP annotations such as read-only or destructive are useful descriptions for clients, but they are not authorization controls. The server must enforce the operation policy, approval binding, revision checks and effect limits itself. This is especially important because third-party MCP servers can mislabel their own behavior.

## 10. Acceptance gates

- [ ] Browser bridge binds only to loopback and rejects unapproved origins.
- [ ] Pairing token is single-use, short-lived and absent from URLs/logs.
- [ ] No arbitrary code execution or arbitrary filesystem access exists.
- [ ] Snapshot and search are read-only and bounded.
- [ ] Preview does not mutate localStorage, IndexedDB or project state.
- [ ] Stale project revisions reject patch application.
- [ ] Duplicate paths, namespace collisions, missing dependencies and unsupported schema fields are surfaced rather than guessed.
- [ ] Existing `StudioCompat` and `StudioMigration` outputs match the manual UI workflow for the same inputs.
- [ ] Applying a patch produces a reproducible operation ledger and preserves source provenance.
- [ ] Rollback cannot overwrite later user changes.
- [ ] Windows Edge and Chrome tests pass on a disposable project.
- [ ] Generated source passes the repository's available validation; real Fabric compile and in-game compatibility are reported separately.

## 11. Research references

- Anthropic, [Writing effective tools for AI agents](https://www.anthropic.com/research/writing-tools-for-agents): tool descriptions, bounded responsibilities, context efficiency and task-based evaluation.
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents): optimize for the smallest high-signal context, with clear tool boundaries and targeted retrieval.
- Model Context Protocol, [Tool Annotations as Risk Vocabulary](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/): annotations are behavioral hints, not enforcement; trusted policy must be implemented by the server.
- Anthropic, [Building effective AI agents](https://www.anthropic.com/research/building-effective-agents): prefer simple, composable workflows and use environmental feedback as ground truth.
- Model Context Protocol, [Tools specification](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/server/tools.mdx): tool annotations are descriptive and do not replace trusted authorization.
- OWASP, [WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html): WebSocket authentication, Origin validation, token handling and message controls.
- MDN, [Writing WebSocket servers](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API/Writing_WebSocket_servers): handshake behavior and browser Origin semantics.

## Conclusion

The next meaningful AI capability is not another larger command list. It is a local, typed Project Operator that reuses the editor's existing resource library, compatibility analyzer, migration planner, project validator and compiler. The safest development path is read-only browser connectivity first, then preview-only ProjectPatch, and only later approval-gated commit/verification/rollback.
