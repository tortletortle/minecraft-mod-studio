# Minecraft Mod Studio UI Workbench Design

**Status:** v0.1 implementation branch; not merged into `main`  
**Maintained editor source:** `Minecraft_Mod_Studio_V19.html`  
**Design direction:** VS Code workspace structure + Blender editing modes + Figma contextual properties + Unreal-style object/details relationship.

## 1. Product objective

Turn the editor from a collection of simultaneously visible feature cards into a task-oriented creative workbench. Preserve existing capabilities and the Minecraft visual identity, but reduce persistent UI surfaces, visual noise, and unnecessary context switching.

The central rule is:

> One selected resource, one primary editing surface, one contextual inspector. Presets accelerate work; they must not restrict valid customization.

This is an interaction and information-architecture refactor, not a feature-removal exercise.

## 2. Verified baseline observations

The following observations were made directly against the maintained source on `main` before this branch's change:

- The item editor uses a three-column/two-row `.workspace` grid.
- The same view simultaneously renders the showcase, texture editor, model preview, recipe editor, and behavior editor.
- The four mode buttons call `focusTab()`, but the previous implementation only scrolled the selected panel into view and animated its border. It did not hide the other editors.
- The recipe ingredient selector is populated from three hard-coded vanilla examples plus project items. It does not provide a general free-form namespaced resource-ID entry path.
- The existing color fields already use native `input[type=color]` in several areas. Therefore the design requirement is not to invent a color picker; it is to provide a consistent, explicit custom-value workflow (including direct HEX entry and presets) across the editor.

These facts identify a concrete source of the clutter: the current tabs behave more like scroll shortcuts than mutually exclusive editing modes.

## 3. Target workbench anatomy

### Global shell

1. **Global toolbar:** project identity, global search, AI operation entry, save state, validation/build actions, language switch.
2. **Resource navigation:** project tree and resource categories; collapsible and resizable.
3. **Primary work surface:** one current editing mode, not every mode at once.
4. **Contextual inspector:** one shared property inspector that follows the current selection.
5. **Activity panel:** build output, errors, warnings, runtime trace and AI operation history; collapsed by default and switched by tabs.

### Resource work modes

| Resource | Primary modes | Contextual selection |
|---|---|---|
| Item | Overview, Texture, Model, Recipe, Behavior | Item, texture tool, model part, recipe slot, behavior node |
| Block | Preview, Appearance, Properties, Drops, World generation | Block, material, drop rule, worldgen rule |
| Mob | Model, Rig, Animation, AI, Spawn, Drops | Bone, cube, keyframe, behavior node, spawn rule |
| Quest | Graph, Objective, Reward, Prerequisites | Quest node, objective, reward |
| Effect | Preview, Effect data, Attribute modifier | Effect, modifier |
| GUI | Canvas, Layers, Component properties, Events | Canvas, layer, component, event |

Modes should be exposed as tabs or a compact mode switch only when they are siblings in the same editing context. Avoid adding a new permanent card for every mode.

## 4. Panel and card policy

### Use a panel when

- It represents a distinct work surface (canvas, viewport, resource tree, inspector, activity panel).
- It has an independent visibility, resize, or docking behavior.
- It contains a meaningful, separately navigable object collection.

### Do not use a panel/card when

- It only groups two or three related fields.
- It duplicates the parent panel's title or background.
- It is a secondary status message that can be shown inline.
- It is an inactive editing mode.

Use section headings, spacing, dividers, inline help and progressive disclosure for parameter groups. Cards are for semantically independent objects, not for every property group.

### Visibility and layout rules

- Only one primary editor mode is visible at a time.
- The inspector follows the active object/tool/node.
- Advanced and low-frequency settings are collapsed by default.
- The resource preview is secondary and may be hidden when it duplicates the active viewport.
- The bottom activity panel is collapsed by default.
- All major regions can be resized or hidden on desktop.
- Mobile uses a single primary column and a deliberate panel switcher; do not shrink a desktop three-column layout into unreadable columns.

## 5. Preset + Custom value contract

Presets are convenience shortcuts, never the only way to enter a valid value.

### Color

- Provide a custom color picker.
- Provide a directly editable HEX field; RGB is an optional secondary representation.
- Keep a small preset palette for speed.
- If opacity is supported by the target data type, expose it explicitly.
- Validate the format without silently replacing a user's value.

### Numeric and dimensional values

- Allow direct typing; use sliders only as optional accelerators.
- Display units and valid ranges.
- Do not silently clamp a value while the user is typing.
- Distinguish syntax errors, range violations and target-engine restrictions.

### Resource identifiers and references

- Offer searchable suggestions from current project resources and known built-in examples.
- Permit custom namespaced IDs (for example, `namespace:path`) where the underlying Minecraft schema accepts identifiers.
- Validate namespace/path syntax locally.
- Show separate states: project-resolved, external/unverified, invalid syntax, and runtime registry-confirmed.
- Do not label an unknown external registry ID as valid merely because it matches the syntax.
- Where possible, provide a “search loaded registry” action after a game/runtime connection exists.

### Closed enums and schema-bound choices

Not every dropdown should become arbitrary text. Native closed enums (for example, engine-defined rarity values) must remain type-safe. If a domain is extensible, expose a validated extension/registry mechanism rather than accepting arbitrary strings that later fail code generation.

### Templates and custom authoring

- Texture templates must remain editable and support import/drawing.
- Model templates must be starting points; users can change geometry, bones, pivots, materials and animation.
- Behavior templates must be editable typed node graphs; custom nodes must declare input/output schemas and validation.
- GUI templates must support custom layout values and components.
- Recipe suggestions must not restrict valid project or external registry identifiers.

### Persistence and migration

- Custom values are stored in the project data model, not in transient DOM state.
- New fields require explicit schema versioning and migration.
- Existing projects must retain their values when a control changes from a select to a searchable/custom control.
- Unsupported values must be surfaced as unresolved/unverified, never silently discarded.

## 6. Localization contract

- Supported locales: `zh-CN` and `en-US`.
- Default locale: `zh-CN`.
- One locale dictionary and one translation lookup path; no per-page hand-written partial translations.
- Translate navigation, labels, buttons, placeholders, tooltips, dialogs, validation messages, build output summaries and empty states.
- Keep user-authored resource names, registry IDs, Java symbols, API names and literal code unchanged.
- Update the document language declaration when switching locale.
- Missing translation keys must be detectable in development checks; do not silently fall back to a mixed-language sentence.

## 7. Accessibility and responsive acceptance

- Keyboard-operable tabs with arrow-key navigation and visible focus.
- Correct tab/tab-panel relationships and selected state.
- Text contrast: WCAG 2.2 AA thresholds (4.5:1 for normal text; 3:1 for large text).
- Target size: meet WCAG 2.2 AA minimum target-size requirements or documented spacing exceptions.
- Desktop: resource navigation, main work surface and inspector remain independently usable.
- Tablet/mobile: one primary work surface; secondary regions open as drawers or switched panels.
- Test at narrow widths, browser zoom, keyboard-only navigation and long translated labels.

## 8. Implementation plan

| Phase | Scope | Acceptance |
|---|---|---|
| 0.1 | Item editor tabs become true mutually exclusive modes; reduce simultaneous panels | Only the selected editor is visible; model mode gets the full work surface; keyboard tab navigation works |
| 0.2 | Shared contextual inspector for item/block/mob/quest/effect/GUI | Inspector content follows selection; no duplicate property cards |
| 0.3 | Consolidate resource workspaces and activity panel | One consistent shell, collapsible/resizable regions |
| 0.4 | Unified zh-CN/en-US localization | No mixed-language system-owned UI strings |
| 0.5 | Preset + Custom input components | Custom HEX, numeric, resource-ID and schema-safe enum workflows |
| 0.6 | Visual and interaction regression | Screenshots and task-based tests at desktop/tablet/mobile sizes |

## 9. Current branch implementation

### Implemented in v0.1

- The item editor's four tabs now behave as actual editing modes.
- Secondary resource workspaces now render their repeated `sPanel()` groups as semantic sections rather than independent decorative cards; nested summary cards are flattened into divider-separated rows. This reduces repeated borders without removing the underlying content.
- Inactive texture/model/recipe/behavior panels are hidden rather than left on screen.
- The preview remains as a secondary column for texture/recipe/behavior; model mode receives the full work surface.
- Tab state is exposed through `aria-selected`, `role=tab` and `role=tabpanel`.
- Left/right arrow keys and Home/End move between editing modes.
- Existing project data, save logic, resource schema and code-generation logic were not intentionally changed.

### Not yet implemented

- Shared contextual inspector across all resource types.
- Rework of every secondary workspace card.
- Complete bilingual dictionary and language switch.
- Reusable custom-value components and arbitrary external resource-ID picker.
- Browser screenshot regression and real user task-time comparison.

Do not describe these deferred items as complete. The branch is a first interaction slice, not the final redesign.

## 10. Reference products and standards

- Blender Manual — Workspaces: https://docs.blender.org/manual/en/latest/interface/window_system/workspaces.html
- VS Code — User interface: https://code.visualstudio.com/docs/getstarted/userinterface
- VS Code — Customizing the layout: https://code.visualstudio.com/docs/configure/custom-layout
- Adobe Photoshop — Workspaces: https://helpx.adobe.com/photoshop/using/workspaces.html
- Unreal Engine — Unreal Editor interface: https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-editor-interface
- W3C — WCAG 2.2 Quick Reference: https://www.w3.org/WAI/WCAG22/quickref/
- W3C Internationalization — HTML language declarations: https://www.w3.org/International/questions/qa-html-language-declarations
