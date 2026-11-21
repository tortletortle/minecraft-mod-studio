# MMS Extension Engine V0.5 — deterministic .mmse writer and content-addressed asset index

Date: 2026-11-21  
Branch: research/extension-engine

## Delivered

### 1. Deterministic .mmse writer
- Emits a ZIP container using the stored method (method 0); no compressor dependency.
- Fixed DOS timestamp (1980-01-01), sorted canonical file paths, fixed metadata, no comments, extras, data descriptors or directory entries.
- Writes ZIP local headers, central directory and EOCD; calculates CRC-32 for every entry.
- Requires strict SDK manifest validation; allows optional README and static files only beneath assets/.
- Uses the V0.4 reader as a post-generation validation gate before returning bytes.
- Enforces existing .mmse caps: 8 MiB archive, 64 entries, 1 MiB per file, 4 MiB total uncompressed, and restricted path/type allowlist.

### 2. Full-archive SHA-256 lockfile
- Added a byte-only SHA-256 API; it rejects non-Uint8Array inputs.
- Lockfile schema 2 identifies format mmse-1 and records package id, version and SHA-256 of the complete archive bytes.
- Lockfile generation validates every archive, rejects duplicate package IDs and sorts entries deterministically.
- Verification re-parses the archive and recomputes its full-byte digest. Changing a static asset while leaving manifest unchanged changes the lock hash.
- Hashes provide integrity relative to a trusted lockfile; they do not establish publisher identity.

### 3. Content-addressed asset index
- Computes SHA-256 for each extracted static asset.
- Returns a path-to-content-hash map plus byte blobs.
- Deduplicates identical assets by hash and checks byte equality if a hash key already exists.
- Does not write to disk; this is a staging/index contract for the later persistent store.

## Verification evidence

Committed source and tests were re-read from GitHub and executed in the V8 harness:

| Suite | Passed |
|---|---:|
| V0.1 registry | 24/24 |
| V0.2 host transaction | 33/33 |
| V0.3 package manager + raw-byte SHA-256 | 47/47 |
| V0.4 archive reader | 39/39 |
| V0.5 writer, lockfile and asset index | 35/35 |
| **Total** | **178/178** |

Independent ZIP interoperability: generated a 549-byte .mmse sample from the committed writer and opened it with Python's standard-library `zipfile`. `ZipFile.testzip()` returned `None`; the independent reader enumerated README.md, assets/sounds/demo.ogg and manifest.json, parsed manifest id `interop-demo`, and decoded README text. SHA-256 of that fixture: `82be998664c6b90f77409a90db176ecf11af1a2227d9186bea422d3bca5e6aa1`.

## Limits / not claimed
- Writer currently emits stored entries only; it does not compress.
- Browser DecompressionStream('deflate-raw') has not been exercised in a real browser. V0.8 reader's Deflate path remains unverified against external archives.
- Python zipfile interoperability was checked for one writer-generated stored archive; broad ZIP tool compatibility and malformed-archive differential fuzzing are still pending.
- No Node CLI run, persistent catalog, crash-safe disk transaction, filesystem extraction, remote package source, signature verification, executable extension runtime, Studio UI integration or Minecraft in-game test.
- Main branch was not changed. The V2.5 editor HTML blob is identical between main and this research branch.

## Next acceptance gates
1. V0.6: content-addressed persistent asset store, catalog schema, atomic journal and crash recovery tests.
2. V0.7: publisher signing, trust roots, key rotation and revocation semantics.
3. Browser integration behind a feature flag, with actual browser Deflate tests and editor regression fixtures.
4. Only consider main merge after a clean branch build, UI regression, project import/export and Minecraft game validation.
