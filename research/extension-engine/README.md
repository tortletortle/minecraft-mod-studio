# MMS Extension Engine — V0.1 research

Base: main f4070b207cc916df7e138c6c6009778df85e8049. The editor is intentionally untouched.

## Scope
L1 JSON-only manifest and contribution registry, in memory. No ZIP loader, no executable extension, no DOM changes, no project edits, no browser sandbox, no persisted grants. Tested JavaScript class and test function directly in a V8 isolate before committing their source via toString; to repeat in Node 18+ run `node research/extension-engine/registry.test.mjs`. Node/browser execution and Studio regression were not performed. Payload content schemas (templates, recipes and blueprint semantics) are not validated yet; never treat their contents as HTML or executable code.

## Contract
Packages are strict JSON with id, version, sdkVersion (exact 0.1.0), permissions, dependencies (package ID -> exact version), contributes [{type,id,data}]. The supported types are template, recipe, blueprint. Contribution keys are namespaced by owner and type. The host provides explicit grants at each activation. The host must be trusted; this registry is not a security sandbox. Dependencies must already be active; no automatic graph solver, cycles cannot be activated. Disable refuses active dependents. Data snapshots are copied. No upgrade, persistence, hash verification or project rollback yet.

## Test results
24/24 scenarios passed in V8 on 2026-11-21. No measurements or claims of editor integration.

- PASS: install does not activate
- PASS: independent template activation
- PASS: disable restores registry
- PASS: uninstall removes inactive package
- PASS: active uninstall refused
- PASS: SDK mismatch
- PASS: permission denial atomic
- PASS: undeclared permission refused
- PASS: unknown permission refused
- PASS: missing dependency refusal
- PASS: dependency exact version
- PASS: dependency chain activation
- PASS: active dependent prevents removal
- PASS: cycle cannot activate
- PASS: duplicate package refusal
- PASS: duplicate contribution refusal
- PASS: namespace isolation
- PASS: snapshot mutation isolated
- PASS: prototype key refused
- PASS: invalid JSON
- PASS: size limit
- PASS: executable entry rejected
- PASS: multiple contribution types
- PASS: revocation and reauthorization

## Next
1. Model a real structure template schema and validate its semantics. Establish canonical path and resource limits.
2. Add a host adapter for V2.5 project snapshots and staged changes with revision checks and validation; never give plugins direct access to the global project. Test rollback on failure with actual editor project fixtures.
3. Compare iframe/Worker/local service for L2/L3; separate origin, CSP, message channel bindings, permissions and timeouts. Do not expose executable third-party loading before browser security testing.
4. ZIP import: reject traversal, symlink, duplicate paths, decompression bombs and unsupported files; validate before activation. Add hash-pinned lockfile and compatibility/dependency solver later.
5. Keep branch separate until old editor regressions and one real extension end-to-end pass.

References: https://code.visualstudio.com/api/get-started/extension-anatomy ; https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe ; https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage
