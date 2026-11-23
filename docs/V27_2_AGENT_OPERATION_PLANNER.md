# V2.7.2 — AI Operation Planner (Read-only)

## Why this milestone exists

V2.7.0 exposed live Brigadier discovery, inspection and syntax-only validation. V2.7.1 added bounded, untrusted descriptions from installed Fabric mods. The remaining usability problem is orchestration overhead: an agent must search, inspect one or more candidates, and then decide what to validate across several MCP calls.

V2.7.2 adds a task-oriented, read-only planner tool that combines candidate retrieval and top-candidate inspection into one agent-facing call. It reduces the number of decisions and tool round-trips the model must coordinate without granting command execution.

This planner applies only to **live in-world Minecraft command discovery**. It does not edit a mod JAR, change project resources, or replace the future ProjectPatch workflow for editing existing mods.

## Tool surface

| Tool | Purpose | Effect |
|---|---|---|
| `mms_plan_command_task(goal, candidate_limit)` | Retrieve and inspect up to three likely live commands for a natural-language task | Read-only |
| `mms_search_commands(query, limit)` | Search command roots when the agent already knows what it is looking for | Read-only |
| `mms_inspect_command(name)` | Inspect one live Brigadier root | Read-only |
| `mms_validate_command(command)` | Parse one complete command string | Syntax parsing only; never executes |
| `mms_plan_command_batch(commands)` | Validate and classify 1–8 complete commands as a single ordered preview plan | Read-only; never executes |

The task planner reads the live catalog, ranks candidates, and inspects their live usage paths. It returns a compact candidate plan with:
- candidate command roots and relative ranking scores;
- query-term coverage and match evidence;
- bounded live Brigadier usage and child-node summaries;
- manifest provenance and explicit untrusted-data labels;
- the remaining steps the agent must perform before any future execution feature could be considered.

The score is a **relative ranking signal, not a probability or safety rating**. A high score does not mean that a command is semantically correct or safe.

After the agent composes complete command strings, `mms_plan_command_batch` parses 1–8 commands against the live Brigadier dispatcher and applies the separate `command_policy.py` classifier. It returns a deterministic plan ID, per-step syntax result, coarse effect category, risk level and decision:
- a narrow explicit read-only allowlist becomes `preview_only`;
- known world/player/entity/server mutations require operator review;
- unknown mod commands and delegated roots such as `execute`, `function` and `trigger` are blocked by default.

This is a conservative root/subcommand policy, not a semantic proof or a world-state simulation. The policy deliberately ignores manifest risk labels. A valid parse only establishes Brigadier syntax; custom mod argument parsers are not sandboxed.


## Command batch policy preview

After the agent has composed complete command strings from the candidate usage, it may call `mms_plan_command_batch` with 1–8 commands. This second-stage tool:

1. Normalizes and bounds each command (maximum 512 characters; control characters are rejected).
2. Calls the live Brigadier parser for each command and verifies that the response is explicitly syntax-only.
3. Applies an independent, deterministic command-root/subcommand policy. It does not trust a mod manifest's advisory risk or reversibility fields.
4. Returns an ordered plan with a stable SHA-256 plan ID, syntax result, effects, risk category, reversibility assumptions and required review decision.

The policy is deliberately conservative:

- A small explicit set of query patterns (for example `time query`, `data get`, `scoreboard players get`, and `team list`) can be labelled read-only.
- Known block, entity, inventory, player and world-state mutations are marked for operator review; this is not execution authorization.
- Generic dispatch/delegation roots such as `execute`, `function` and `trigger`, plus unknown mod command roots, are blocked by default because their complete effects cannot be inferred safely.
- A syntax-valid command is not necessarily safe. A mod command's manifest may improve retrieval but cannot change this policy decision.
- Every plan and every step explicitly reports `execution_enabled=false`; the tool has no command-dispatch path.

The plan is an audit/preview artifact, not a transaction, undo snapshot or promise that a future executor may run these commands. Persistent world changes require a later typed operation adapter with measurable bounds, pre-state capture and post-state verification.

## Retrieval method

The previous implementation used additive substring checks. V2.7.2 replaces that ranking core with a deterministic field-weighted BM25-style scorer (BM25F):

1. **Command root name** receives the strongest field weight.
2. **Validated-but-untrusted manifest keywords** receive a high retrieval weight.
3. **Manifest descriptions** receive a lower weight.
4. **Curated Chinese/English hints** provide a fallback vocabulary for Vanilla commands.
5. **Exact phrase bonuses** preserve strong full-phrase matches.
6. Chinese text is tokenized using full phrases plus overlapping character bigrams. No network call, embedding model, or external tokenizer is required.

Each result exposes matched terms, field-level match basis, and coverage so the model can compare evidence rather than treating the score as opaque confidence.

This is an initial retrieval baseline, not a claim that BM25F is universally better than embeddings or learned rerankers. A future benchmark should compare retrieval approaches against a labelled Chinese/English task set using Recall@k, MRR@k, nDCG@k, latency and token cost before introducing a heavier model.

The composite planner reduces **model-facing MCP tool calls and orchestration decisions**. It still performs bounded internal bridge requests for catalog pagination and top-candidate inspection; this milestone does not claim fewer low-level game-bridge RPCs. Future evaluations should measure both agent-facing call count and underlying bridge request count.

## Operation flow

```text
Natural-language in-world task
          |
          v
mms_plan_command_task
          |
          +--> read paginated live Brigadier catalog
          |
          +--> rank candidates (BM25F + phrase evidence)
          |
          +--> inspect top candidate syntax
          |
          v
Candidate plan (read-only)
          |
          v
Agent reviews goal, target, constraints and effects
          |
          +--> compose a complete command
          |
          +--> mms_plan_command_batch (syntax + policy preview)
          |
          v
Read-only operation plan; mutations require later review
          |
          v
Execution is unavailable in V2.7.2
```

## Trust and safety

- The live Brigadier dispatcher remains the source of truth for whether a command root is currently registered.
- Manifest descriptions, keywords and examples remain untrusted descriptive metadata. They cannot supply agent instructions, register tools, grant permissions or authorize mutations.
- A root-name match does not prove mod ownership or semantic correctness.
- Manifest risk and reversibility labels remain advisory claims. The planner does not use them as authorization.
- The task planner and batch planner never call Brigadier command execution and never emit a generic dispatch request.
- The batch planner has an explicit read-only pattern allowlist; recognized mutations require operator review and unknown/delegating roots are blocked by default.
- Every step in a command plan reports `execution_allowed=false`; plan IDs are deterministic hashes of the policy version and step results.
- Syntax validation is a parser check, not a sandbox: custom mod argument parsers may contain mod-defined logic.
- The command policy is a narrow allowlist/classifier. It is not a complete side-effect analysis, does not simulate command sequences, and does not prove that a command is safe. Unknown commands remain default-deny.
- Unknown command effects remain unknown. There is no inferred "safe" status from a command name or manifest label.
- No command chaining, block edits, entity spawning, inventory changes or world-rule changes are introduced.

## Acceptance criteria

- [x] Retrieval core is deterministic and uses only the Python standard library.
- [x] Chinese bigram and English token retrieval have focused unit coverage.
- [x] Unlabelled manifest content is excluded from retrieval.
- [x] A separate conservative command policy module classifies explicit read-only, known mutation and unknown command roots without using manifest risk labels.
- [ ] Existing MCP command-search regression tests pass.
- [ ] The batch-planner MCP tool returns syntax and policy evidence for 1–8 commands in one call.
- [ ] The planner returns candidate syntax and trust labels in one MCP call.
- [ ] Task-planner tests prove only catalog and inspect bridge operations are sent.
- [ ] Batch-planner tests prove only syntax-validation bridge operations are sent and that read-only, mutation and unknown roots receive distinct decisions.
- [x] Pure policy tests cover read-only patterns, mutation classification, unknown-root default deny, deterministic plan IDs, input bounds and validation-response binding.
- [ ] Python unit suite and compile checks pass in GitHub Actions.
- [ ] Fabric 26.2 / Java 25 companion build passes.
- [ ] Windows Minecraft 26.2 disposable-world test confirms that candidate discovery does not mutate the world.

Do not mark V2.7.2 accepted until all applicable CI and runtime acceptance checks pass.

## Design references

- Anthropic, [Writing effective tools for AI agents](https://www.anthropic.com/research/writing-tools-for-agents), 2025-09-11: tool choice, clear boundaries, meaningful context, token efficiency and agent-based evaluation.
- Anthropic, [Building effective AI agents](https://www.anthropic.com/research/building-effective-agents): use simple composable workflows where appropriate, and use environmental feedback as ground truth during agent execution.
- Model Context Protocol, [Tools specification](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/server/tools.mdx): tool annotations describe behavior but are not a substitute for a trusted authorization policy; user consent and control remain important.

## Next architectural boundary

The command planner is not the final "God Mode". A full Mod Studio operator must route tasks to separate domain capabilities:

- **Project editing:** inspect imported mod resources, build a Project IR snapshot, propose a typed ProjectPatch, preview a semantic diff, validate references/schema/build, then commit a reversible revision.
- **Live game operation:** use the runtime companion and typed, bounded operations against a disposable world.
- **Build and verification:** run deterministic compiler/tests and collect evidence.

These domains must not share an unrestricted execution endpoint. The Patch Transaction Engine remains the only path that creates a new project revision; the runtime companion remains a separate, authenticated game-control boundary.
