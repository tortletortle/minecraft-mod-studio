# H0.8 fixture materialization — actual local evidence
Scope: standalone research utility; no main changes, no adapter/SDK/game execution.
Input fixture Git blob: e891f9e1bfe1a877ca98ec827c45ef3442f0128d (local reconstruction matched remote bytes).
Script Git blob: e9b875cd04346a3b21dea3c7967ee74523ad1302 (remote matches tested local script).
Environment: Linux container, Python 3.13.5, zlib 1.3.1. Pillow used only for independent PNG decoding in the one-off checks; the generator itself uses standard library only.

From repository root:
    python research/horizon/materialize.py --out /tmp/rd001-run1
    python research/horizon/materialize.py --out /tmp/rd001-run2
Use fresh paths; existing output directories are deliberately rejected. Compare directories byte-for-byte.
Outputs (SHA-256, same in both runs):
- rd001-base.zip: ada4e8d544921e7610acc15a9eea22ae077dcb2332a313871e88c5105e87991c
- rd001-conflict.zip: de248bf224444d786314e5f52061323af6d66f596f1b8fd8943fe838ac210018
- rd001-missing.zip: 2f00039c60de009ff6def58242be9b9ba69b34e6300b2eeb20a9d6560e3bb9c1
- manifest.json: 4f1318f3e21d63af0678a140597940d696b6bf6995e07d976b7385a2afdc6d30

15 one-off local checks passed:
1. Both runs' outputs byte-identical.
2–4. Each of three ZIPs matched archive and entry hashes in manifest; zipfile.testzip returned None.
5. Pillow independently decoded PNG: 16×16 RGBA, every pixel (180,100,45,255).
6. Missing variant removed only the texture; other bytes unchanged.
7. Conflict variant contained only same-path differing localization.
8. Unsafe mutation not emitted into any ZIP.
9–13. Traversal, absolute path, case-folded duplicate, Windows device and oversized texture mutations were each rejected before output directory creation.
14. Existing output directory and sentinel unchanged after rejected build.
15. Manifest gameVerification remained NOT_RUN.

Limits: checks were executed via a one-off local Python harness, not a committed automated suite. No general security audit; generator is for trusted research fixtures in disposable directories. Byte equality verified on this environment, not across operating systems or zlib versions. Rights and unsafe-path cases remain metadata; no adapter policy or malicious extraction tested. The source ZIPs are resource samples, not registered mods, .hmod or JAR; no game or SDK ran. Generated outputs are intentionally not committed. H1 remains gated on Java real-game acceptance and target SDK pin.
