# MMS Extension Engine V0.4 — strict .mmse ZIP reader

Reference: PKWARE APPNOTE.TXT ZIP File Format Specification 6.3.10, revised 2022-11-01. The reader follows the local-header/central-directory/EOCD layout and per-entry CRC-32 model. It intentionally supports a strict subset, not arbitrary ZIP interoperability.

## .mmse profile
- Root manifest.json is mandatory and validated by the existing strict SDK manifest parser.
- Optional README.md; static files only under assets/ with png, ogg, json, mcmeta, jem, jpm, bbmodel extensions.
- ASCII canonical relative paths only; reject traversal, backslashes, absolute paths, duplicate case-folded paths and unsupported files.
- ZIP methods 0 (stored) and 8 (Deflate) only. No encryption, data descriptors, ZIP64, multi-disk, comments, extra fields, directories, symlinks, preambles or trailing local-layout gaps.
- Validate local and central headers against each other, enforce non-overlapping contiguous local records, bounds, CRC32 and decompressed sizes.
- Caps: 8 MiB archive, 64 entries, 1 MiB/file, 4 MiB aggregate uncompressed, 100:1 compression ratio, 200-byte path. Product limits, not ZIP format limits.
- Deflate uses browser DecompressionStream('deflate-raw') by default; tests inject a deterministic decompressor. Actual browser decompression has not been exercised.

## Evidence
35/35 archive tests passed in the V8 harness on 2026-11-21. Tests cover stored/Deflate adapter flow, traversal, unsupported executable files, duplicates, encryption, data descriptors, methods, ZIP64, multi-disk, comments, extras, local/central mismatches, duplicate offsets, symlinks, CRC corruption, size/ratio/file-count limits, malformed assets and manifest schema. Deflate test injects a placeholder inflater; it does not establish real raw-Deflate compatibility. No Node CLI, browser, real ZIP tool interoperability, persistence or editor integration test yet.

## Limits and next gates
This parser returns validated manifest and inert asset byte arrays. It does not persist assets, install into the editor, create a .mmse writer, authenticate publisher identity or execute extension code. ASCII paths are a deliberate profile restriction. Next: test real Deflate archives from common ZIP tools; add asset references and content-addressed extraction; add publisher signatures and trust roots; integrate only behind a feature flag after real Studio project and browser regression tests.
