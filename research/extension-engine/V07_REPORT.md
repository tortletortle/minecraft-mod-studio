# MMS Extension Engine V0.7 — publisher trust and signed package installation

Date: 2026-11-21  
Branch: research/extension-engine

## Delivered

### 1. Ed25519 publisher trust API
- Added `publisher-trust.mjs`, using the Web Crypto Ed25519 API.
- Publisher key IDs are SHA-256 hashes of 32-byte raw public keys.
- Host-pinned trust roots issue publisher key certificates with explicit package scopes and validity windows.
- Package signatures bind a domain-separated canonical message to the package ID, semantic version, signer key ID and SHA-256 of the complete .mmse archive.
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
| Publisher trust control-flow | 30/30 | V8 harness with deterministic fake crypto adapter |
| **Existing branch suites total** | **219/219** | Does not include publisher trust fake-adapter checks |

The fake crypto adapter exercises API orchestration and signature-message binding, not Ed25519 cryptographic strength. A separate `publisher-trust.test.mjs` uses Node's native WebCrypto Ed25519 key generation, signing and verification. That native suite is committed but has not yet been executed in this environment; real Ed25519 acceptance is therefore still pending.

## Security limits / not claimed
- No publisher key generation, private-key custody, HSM integration, signing CLI or secure key backup/rotation workflow.
- No signed revocation-feed format, monotonic feed sequence, anti-rollback storage or automated revocation distribution. The host must supply current revocation statements; omission means the verifier cannot know about a revocation it has not received.
- Trust roots are host-pinned and require an out-of-band update for root rotation.
- Mandatory signature enforcement is opt-in and not yet enabled by the actual Studio UI or remote marketplace.
- A valid signature proves archive provenance/integrity relative to a trusted key; it does not prove benign behavior or code safety.
- Packages remain data-only. No arbitrary executable extension runtime is introduced.
- Native Node WebCrypto suite, real-browser IndexedDB behavior, multi-tab concurrency, crash recovery, browser Deflate, editor integration and Minecraft in-game tests remain outstanding.

## Next acceptance gates
1. Run the native Node WebCrypto Ed25519 test suite.
2. Define signed, versioned revocation bundles with anti-rollback.
3. Exercise IndexedDB and signature enforcement in a real browser.
4. Add Studio UI for publisher identity, signature status, permission review and trust errors; require signatures for remote packages.
5. Complete editor and in-game regression before any main-branch merge.
