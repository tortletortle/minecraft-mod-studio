# Example recipe extension

This is a minimal, local, data-only MMS extension package for the V25 editor.

## Build

From the repository root, using Node.js 22+:

```sh
node research/extension-engine/examples/recipe-pack/build.mjs
```

The script creates `mms-demo-recipes.mmse` in this folder. Import that file from V25 → **扩展** → **导入 .mmse**.

## Package contract

- Package ID: `mms-demo-recipes`
- SDK: `0.1.0`
- Permission: `recipe.register`
- Contributions: two declarative 3×3 recipe templates.
- No executable code and no external network requests.

After import, enable the global extension feature flag, then explicitly enable the package and approve its declared permission. The templates appear in the active recipe list. Applying one updates the selected item's recipe in the project draft; it does not save automatically.

The package is unsigned. Treat it as a local development example, not a trusted marketplace artifact.


## Project-local item references

A recipe may reference an existing item in the current V25 project by using `@item:<uid>` in an ingredient slot. The UID must exist in the target project when the template is applied. These references are project-specific and should not be assumed to resolve in another project; use namespaced Minecraft/mod resource IDs for portable templates.
