# Minecraft Mod Studio — AI Project Operator V0.2

**Status:** Read-only vertical slice; feature branch only.  
**Branch:** `feature/ai-project-operator-readonly-bridge-v0.2`  
**Scope:** Connect a local MCP agent to the active V2.5 browser editor and inspect the project and imported resource library. No project writes are exposed.

## What this adds

The editor's existing project state and IndexedDB resource library remain the source of truth. The bridge exposes a narrow read-only API from inside the resource-library UI closure:

- project snapshot, schema, counts, current revision hash, validation and compiler analysis;
- search across project items/blocks/mobs/quests/effects/GUIs;
- search across imported JAR/ZIP resource paths and bounded metadata;
- inspect one imported resource or staged project override;
- inspect one project object.

The Python process exposes those operations as MCP tools. It serves the existing HTML file from a loopback-only HTTP server at the stable origin `http://127.0.0.1:8765` and injects two local JavaScript modules. The editor remains usable as before.

## Start

Requirements: Python 3.12+ and an MCP-compatible client.

Install the pinned MCP SDK:

```powershell
python -m pip install -r project-operator/requirements-mcp.txt
```

Register this stdio server in Cursor's MCP configuration (replace the path with the local repository path):

```json
{
  "mcpServers": {
    "minecraft-project-operator": {
      "command": "python",
      "args": [
        "-B",
        "C:\\path\\to\\minecraft-mod-studio\\project-operator\\mms_project_operator.py"
      ]
    }
  }
}
```

The server uses fixed port `8765` so browser storage stays on the same origin across restarts. If that port is occupied, add `--port` and choose another fixed port in the MCP args.

**Important: origin migration.** Browser `localStorage` and IndexedDB are origin-scoped. If you previously used the editor by opening the HTML as `file://`, its saved project and imported JAR archive library will not automatically appear at `http://127.0.0.1:8765`. Before switching, export the project JSON from the old page. Open the bridge-served editor, import that project JSON, then re-import the original JAR/ZIP files into its Resource Library. After this one-time migration, data persists across restarts as long as you keep the same port and browser profile.

Restart the MCP client. Then:

1. Call `mms_project_open_editor`.
2. In the opened local editor, click **连接 AI 操作员** in the small panel at the bottom-right.
3. Call `mms_project_connection_status` to confirm the session.
4. Call `mms_project_snapshot` before searching or inspecting.
5. Import JAR/ZIP files using the existing Resource Library UI, then use `mms_project_search` and the inspect tools.

If the editor page is reloaded or the session is disconnected, reload the page and click the connection button again. Only one editor tab may be paired at a time.

## MCP tools

| Tool | Purpose | Effect |
|---|---|---|
| `mms_project_capabilities` | List built-in capability descriptors and effect boundaries | Read-only |
| `mms_project_open_editor` | Open the local editor in the default browser | Browser navigation |
| `mms_project_connection_status` | Check pairing and pending requests | Read-only |
| `mms_project_snapshot` | Read project summary, validation, build analysis and archive metadata | Read-only |
| `mms_project_search` | Search project definitions and imported resource metadata | Read-only |
| `mms_project_inspect_resource` | Inspect a resource by archive ID and path; binary bytes are omitted | Read-only |
| `mms_project_inspect_object` | Inspect one item, block, mob, quest, effect or GUI | Read-only |

The search tool accepts `scope=all|project|resources`, optional archive ID and resource kind, and returns at most 50 results. Resource scanning is capped at 50,000 entries per call and reports truncation. Text resource inspection is capped at 16 KiB; project object inspection is capped at 48 KiB. The snapshot revision is SHA-256 over `StudioCore.encode(project)`; if project encoding fails, the revision is explicitly unavailable.

## Security boundary

- HTTP binds only to `127.0.0.1:8765` by default; the host and exact Origin are checked on every POST. A stable port preserves the editor's browser storage origin across server restarts.
- A fresh 256-bit, ten-minute, single-use pairing token is embedded in the served page and sent in the first pairing POST body. It is never placed in the URL or returned to the MCP model.
- The browser receives a separate random session token in memory and sends it in an HTTP header. It is not stored in localStorage.
- One active editor session, 30-minute idle expiry, 120 requests/minute, 8 pending MCP requests, bounded body size and bounded response content.
- Only four browser operations are accepted: `snapshot`, `search`, `inspectResource`, and `inspectProjectObject`. No operation name is evaluated as code.
- The API exposes no write, patch, arbitrary file, shell, JavaScript-evaluation or command-execution operation.
- Imported archive metadata, license declarations and resource text are untrusted claims/data. They cannot register capabilities or authorize actions.
- Reloading the editor rotates the pairing token and invalidates the old session.

This is a local development bridge, not a hardened multi-user service. Keep the editor and MCP server on the same trusted machine. Do not expose the port through a tunnel or LAN binding.

## Tests

```powershell
python -m pip install -r project-operator/requirements-mcp.txt
python -m py_compile project-operator/mms_project_operator.py
python -m unittest discover -s project-operator/tests -p "test_*.py" -v
node --check project-operator/mms_project_operator_api.js
node --check project-operator/mms_project_operator_client.js
node --test project-operator/tests/project_api.test.js
```

GitHub Actions runs the same Python and Node checks for this feature branch and its pull request.

## Not implemented yet

- No `ProjectPatch` creation, preview, apply or rollback.
- No automatic compatibility staging or resource migration.
- No imported binary/image transfer into the model context.
- No write permission or approval UI.

Next milestone: expose the existing `StudioCompat.analyze` and `StudioMigration.plan` as read-only task-level tools, with dependency evidence, collision diagnostics and explicit untrusted-source provenance. Only after those outputs match the existing manual UI should a typed preview-only `ProjectPatch` be implemented.
