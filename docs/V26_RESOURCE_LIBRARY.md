# V2.6 Resource Library acceptance

The existing resource library is reused, not rewritten. This test uses two synthetic Fabric JARs with explicit test-only MIT notices. It verifies:

1. JAR import and source metadata extraction.
2. IndexedDB source persistence after a full page reload.
3. ZIP path traversal rejection.
4. Recursive static migration of an item definition, its model and texture into the project namespace.
5. Cross-mod shared material tag evidence (c:gems/rare).
6. Conservative recipe ingredient adaptation to the shared tag.
7. Explicit rights acknowledgement before staging.
8. Fabric source export includes migrated resources, recipe, provenance, and declared dependencies.

The acceptance report deliberately labels resource-library verification STATIC_ONLY. It does not claim the two synthetic third-party mods exist in a game instance, nor that external recipes, models or textures resolve at runtime. The fixtures are synthetic and their licenses are test fixtures, not actual third-party resources.
