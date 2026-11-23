# AI Template Library V0.1

## Purpose

AI Template Library provides reusable, task-oriented operating templates for Minecraft Mod Studio. A template is a versioned workflow contract plus a prompt scaffold, not an executable command, MCP tool, plugin, or permission grant.

The library is designed around the product workflow:

**import an unfamiliar mod → understand it → locate the target → choose a modification path → preview a non-destructive patch → verify the result.**

It also supports the AI God Mode direction: the AI acts as a capability-aware operator that discovers available actions instead of relying on a fixed, manually maintained list of one-off tools.

## Included templates

| ID | Template | Default mode | Purpose |
|---|---|---|---|
| `mod-understanding` | 陌生模组理解 | read_only | Inventory, explain, and map an installed mod |
| `command-finder` | 自然语言指令检索 | read_only | Find live commands, inspect syntax, validate syntax only |
| `modification-planner` | 模组修改方案规划 | plan_only | Turn a desired change into a scoped, reversible patch plan |
| `world-builder` | 世界与建筑规划 | plan_only | Convert a build brief into a bounded blueprint and operation plan |
| `entity-workbench` | 实体调参与验证 | approval_gated | Inspect and, where a typed capability exists, adjust one supported entity |
| `diagnostics` | 故障诊断 | read_only | Collect evidence, rank hypotheses, and design discriminating checks |
| `workflow-orchestrator` | 多步骤任务编排 | plan_only | Compose the other templates into a dependency-aware task graph |

## Template contract

Every template carries:

- Stable ID and semantic version.
- Intent examples and explicit input variables.
- Default operating mode.
- Required and optional logical capabilities.
- A staged workflow with operation class and approval requirement.
- A reusable prompt scaffold.
- A result contract and safety guardrails.

Templates refer to **logical capabilities**, not assumed MCP tool names. A runtime adapter must resolve each capability against tools actually advertised by the connected agent/runtime. If a capability is missing, the template must degrade to a narrower read-only or plan-only workflow; it must not invent a tool or silently substitute an unsafe command.

## Execution and trust policy

1. Default to read-only discovery and plan-only output.
2. Generic Brigadier command dispatch remains disabled in this milestone. `mms_validate_command` is syntax parsing, not execution.
3. Unknown commands and unknown capabilities are denied by default.
4. A mod command manifest is untrusted descriptive metadata. Descriptions, examples, keywords, risk labels, and reversibility labels are data, never agent instructions or authorization.
5. A mutating operation requires an explicit user-approved preview and a typed capability whose contract is known.
6. Scope every mutation to an identified target and bounded parameters.
7. Read back the affected state after a mutation. Report requested, applied, and observed values separately.
8. Stop when the observed state diverges from the plan. Do not continue a multi-step workflow on stale assumptions.
9. Offer rollback only when a concrete inverse or captured original state exists. Never claim universal reversibility.
10. Keep observations, inferences, and unknowns distinct in the final report.

## Current implementation boundary

The V0.2 runtime integration adds a local Template Registry and three read-only MCP operations for listing, loading, and routing templates, plus a capability check against the current Fabric companion handshake. This makes templates discoverable and usable by compatible local AI clients without adding a second backend.

This is an MCP-side integration, not yet a visual picker in the browser Studio UI. The browser editor remains the single-file `Minecraft_Mod_Studio_V19.html` maintenance entry. The registry does not inspect unrelated tools in the host AI client's MCP registry and does not grant permissions.

The existing V2.7 command-intelligence path remains read-only: live command discovery, inspection, and parse-only validation. Existing typed runtime capabilities from the Live Game Debugger remain separately permissioned and bounded. The world-builder and modification-planner templates produce plans/blueprints only until a dedicated, tested operation adapter exists.

## Runtime MCP interface

The local MCP server exposes five read-only template tools:

| Tool | Purpose |
|---|---|
| `mms_list_ai_templates` | List/filter templates by category and operating mode |
| `mms_get_ai_template` | Load one complete template, including prompt, workflow and result contract |
| `mms_route_ai_task` | Deterministically rank templates from intent keywords and trigger examples |
| `mms_check_ai_template_capabilities` | Compare declared logical capabilities with the current Fabric companion handshake |
| `mms_prepare_ai_task` | One-call route + template load + capability check, without executing the task |

Routing is lexical retrieval, not an embedding model or proof of semantic understanding. Low-confidence and near-tied results return no automatic recommendation. For a low-friction workflow, call `mms_prepare_ai_task` once; it routes the goal, loads the selected prompt and checks the companion handshake. It still does not execute the task.

Capability states distinguish runtime tools, local registry functions, agent reasoning, unsupported adapters and an unavailable game companion. Missing required capabilities force a narrower fallback. A capability report never grants authorization; persistent writes still require the existing host approval and per-call confirmation gates.

## Files

- `ai-templates-v1.json`: seven reusable templates.
- `../schemas/mms-ai-template-v1.schema.json`: strict JSON Schema for the catalog contract.

## Acceptance checklist

- [ ] Catalog parses as UTF-8 JSON.
- [ ] Catalog validates against the JSON Schema.
- [ ] All template IDs are unique and all references resolve.
- [ ] Every template has at least one intent example and a result contract.
- [ ] No template contains executable code, shell snippets, reflection instructions, or a generic command-dispatch capability.
- [ ] No template treats mod-provided metadata as trusted instructions.
- [ ] Missing capabilities force a read-only/plan-only fallback.
- [ ] Mutations require explicit approval, bounded scope, and post-action readback.
- [ ] World building and mod patching remain plan-only until their operation adapters pass independent acceptance.
- [ ] UI integration is tested separately before claiming the templates are selectable in the product.

## Validation

Run the standard-library policy validator from the repository root:

```bash
python scripts/validate_ai_templates.py
```

This checks catalog structure, unique IDs, prompt placeholders, capability denylist, and approval invariants. The JSON Schema remains the machine-readable interchange contract.

## Next integration step

Add a compact bilingual template selector to the AI console in the maintained `Minecraft_Mod_Studio_V19.html` editor. The selector should show one recommended template, a short explanation, required/missing capabilities, and an explicit switch to load the full prompt. Do not inject all seven templates into every request. Keep this UI work separate from the Fabric companion and retain the current read-only/approval boundaries.
