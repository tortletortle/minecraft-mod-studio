# MMS Extension Engine V0.7 — publisher trust and signed package installation

Date: 2026-11-21  
Branch: research/extension-engine

## Delivered

### 1. Ed25519 publisher trust API
- Added `publisher-trust.mjs`, using the Web Crypto Ed25519 API.
- Publisher key IDs are SHA-256 hashes of 32-byte raw Ed25519 public keys.
- Host-pinned trust roots issue publisher key certificates with explicit package scopes and validity windows.
- Package signatures bind a domain-separated canonical message to package ID, semantic version, signer key ID and SHA-256 of the complete .mmse archive.
- Certificates, signatures and revocation statements are detached metadata; the .mmse v1 ZIP layout remains unchanged.
- Unknown roots, altered keys, malformed metadata, out-of-scope packages, expired/not-yet-valid certificates and invalid signatures fail closed.

### 2. Revocation and key rotation
- Trust roots can sign revocation statements with a constrained reason-code allowlist.
- A matching publisher key is rejected when its revocation time is effective.
- Publisher key rotation is supported by issuing a new root-signed certificate; the old key can then be revoked.
- Root-key rotation is intentionally out-of-band: the host must update its pinned trust-root configuration. A new root cannot bootstrap its own trust.

### 3. Install-path enforcement and provenance
- `PersistentExtensionStore` accepts a host-provided publisher trust service.
- With `requireSignatures: true`, every package in a batch must have a matching detached signature and certificate.
- Verification occurs before asset indexing, staging or journal creation. A failed verification leaves no staged state.
- `prepareInstall` accepts package-ID keyed `signatures` and `certificates`, plus a revocation list and optional verification time.
- Verified signer ID, issuer ID, verification time, certificate and signature are persisted with the installed package record.
- The default remains backward-compatible (`requireSignatures: false`); production/marketplace integration must explicitly turn the mandatory policy on.

## Verification evidence

| Suite | Result | Qualification |
|---|---:|---|
| Registry | 24/24 | V8 harness |
| Host transaction | 33/33 | V8 harness |
| Package manager | 47/47 | V8 harness |
| Archive reader | 39/39 | V8 harness |
| Archive writer / lockfile / asset index | 35/35 | V8 harness |
| Persistent store after signature integration | 41/41 | V8 harness; in-memory backend |
| Publisher trust behavior | 30/30 | Node 22.16.0 native WebCrypto Ed25519 |
| **Existing branch suites total** | **219/219** | V8 harness; does not include publisher trust suite |

The publisher trust suite was run against the committed `publisher-trust.mjs` source (its local copy matched the Git blob SHA) and the committed `publisher-trust.test.mjs` test file (its local copy matched the Git blob SHA). Node 22.16.0 native WebCrypto generated Ed25519 key pairs and exercised certificate issuance, package signing, signature verification, tamper rejection, certificate scope and expiry, revocation, and key rotation. The SHA-256 adapter used the same pure-JavaScript SHA-256 implementation logic already covered by the package-manager suite.

The 30 publisher-trust assertions also passed in the V8 harness with a deterministic fake crypto adapter. That secondary run checks API control flow only and is not counted as cryptographic evidence.

## Branch compatibility finding

At the time of this report, `research/extension-engine` is 50 commits ahead and 2 commits behind `main`, with merge base `f4070b207cc916df7e138c6c6009778df85e8049`. The latest main branch adds `Minecraft_Mod_Studio_V25.html` (blob `cb10de80d28bdef5e2da7fa73065624a93466d73`), which is not present on this research branch. The older V19 editor file is byte-identical on both refs, but that does not prove V25 compatibility. The branch remains isolated and was not merged into main.

## Security limits / not claimed
- No publisher key generation, private-key custody, HSM integration, signing CLI or secure key backup/rotation workflow.
- No signed revocation-feed format, monotonic feed sequence, anti-rollback storage or automated revocation distribution. The host must supply current revocation statements; omission means the verifier cannot know about a revocation it has not received.
- Trust roots are host-pinned and require an out-of-band update for root rotation.
- Mandatory signature enforcement is opt-in and not yet enabled by the actual Studio UI or remote marketplace.
- A valid signature proves archive provenance/integrity relative to a trusted key; it does not prove benign behavior.
- Packages remain data-only. No arbitrary executable extension runtime is introduced.
- Real-browser IndexedDB behavior, multi-tab concurrency, crash recovery, browser Deflate, V25 editor integration and Minecraft in-game tests remain outstanding.

## Next acceptance gates
1. Add a signed, versioned revocation bundle with anti-rollback.
2. Add publisher key provisioning and secure signing workflow.
3. Synchronize this research branch with the V25 mainline and test editor compatibility.
4. Add Studio UI for publisher identity, signature status, permission review and trust errors; require signatures for remote packages.
5. Run V2.5/V25 editor regression, project import/export fixtures and Minecraft in-game validation before any main-branch merge.
