# MMS Extension Engine V0.3 — package manager and dependency transactions

Current main is b249e564cbb3b482bd7668817fe337e665b43c72 (archive of original V2.3 HTML). The V2.5 editor HTML blob a0e47c2b137679475e5a3325314c2acc42c8fa6f is identical on main and this research branch. Extension work remains isolated; no editor HTML, main or Java/structure branch changes.

## Implemented
- Strict V0.1-compatible manifest parser (SDK 0.1.0; template/blueprint/recipe contributions only).
- Exact-version dependency resolution from the submitted batch plus the local installed catalog. Topological order, missing pins and cycle rejection. No remote fetching or semver ranges.
- Atomic batch install/uninstall plans with explicit approval, generation-based stale-plan rejection, and one-use rollback receipts.
- New packages remain disabled until explicit permission grants. Dependency closure activation asks for grants for every newly enabled package and is atomic.
- Upgrades require an explicit flag and strictly increasing SemVer triplets. Same-version content changes and downgrades are rejected. Dependents pinned to the previous version must be upgraded in the same batch.
- Active upgrades retain activation only if the existing grants cover every requested permission. New permissions require disabling and reauthorization.
- SHA-256 over exact UTF-8 manifest bytes and deterministic lockfile generation/verification. This detects content mismatch relative to a trusted lockfile; it does not authenticate the publisher.

## Limits
No ZIP/.mmse container reader/writer, persistent catalog, remote package fetch, semver ranges, digital signatures/trust roots, executable plugins or L2/L3 runtime. Inputs remain strict JSON manifest strings. Resolution is local only. Package catalog cap 256; submitted install/uninstall batch cap 32; lockfile cap 64; each manifest cap 128 KB.

## Tests
44/44 passed in the V8 harness on 2026-11-21. Post-commit verification re-read the committed module and test files from GitHub and executed their exact source in the V8 harness. Combined regression: 101/101 (24 V0.1 registry + 33 V0.2 host + 44 V0.3 package manager). A post-commit check found and fixed a module factory binding issue before this final verification. The committed module and tests were re-read from GitHub and executed in the V8 harness; run under Node 18+ with node research/extension-engine/package-manager.test.mjs for an additional local CLI check (not yet run here).

- PASS SHA-256 abc vector
- PASS SHA-256 UTF-8 vector
- PASS lockfile sorted deterministically
- PASS lockfile verifies exact bytes
- PASS lockfile catches changed bytes
- PASS lockfile catches missing package
- PASS plan does not mutate before commit
- PASS install single package
- PASS dependency topological order ignores input order
- PASS batch commit is atomic
- PASS missing dependency rejects batch
- PASS dependency version pin exact
- PASS dependency cycle rejected
- PASS duplicate package in batch rejected
- PASS new packages stay disabled
- PASS dependency closure activates in order
- PASS closure grants failure leaves all disabled
- PASS unexpected grant entry rejected
- PASS active dependent blocks dependency disable
- PASS approval required
- PASS plan token one-use
- PASS stale plan blocked after competing commit
- PASS rollback restores exact previous state
- PASS rollback requires approval
- PASS rollback cannot overwrite later changes
- PASS rollback receipt one-use
- PASS upgrade requires explicit flag
- PASS downgrade refused
- PASS same version cannot change content
- PASS dependent pin blocks partial dependency upgrade
- PASS dependent and dependency upgrade atomically
- PASS active upgrade preserves activation if grants suffice
- PASS active upgrade cannot add ungranted permission
- PASS disable then upgrade then regrant
- PASS cannot remove dependency while dependent remains
- PASS dependency tree can be uninstalled atomically
- PASS unknown uninstall target rejected
- PASS wrong SDK rejected
- PASS unknown manifest field rejected
- PASS unknown permission rejected
- PASS missing contribution permission rejected
- PASS nested prototype key rejected
- PASS self dependency rejected
- PASS payload depth limit enforced

## Next acceptance gates
1. Implement a ZIP/.mmse parser with canonical path rules, local/central header consistency, CRC, count/size caps and rejection of encryption, symlinks, ZIP64 and traversal; build a malformed archive corpus.
2. Add persistent lockfile/catalog with crash-safe writes and recovery journal.
3. Add publisher signatures with explicit trust roots; keep integrity and authenticity distinct.
4. Integrate only after real StudioCore project fixtures, editor regression and browser compatibility tests.
