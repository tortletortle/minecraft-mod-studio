#!/usr/bin/env python3
"""Real Chromium acceptance for the contextual UI Workbench and custom values."""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Minecraft_Mod_Studio_V19.html"
ARTIFACTS = ROOT / "artifacts" / "ui-workbench"

STORAGE_SHIM = r"""<script>
(() => {
  const values = new Map();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: key => values.has(key) ? values.get(key) : null,
      setItem: (key, value) => values.set(key, String(value)),
      removeItem: key => values.delete(key),
      clear: () => values.clear(),
      key: index => Array.from(values.keys())[index] ?? null,
      get length() { return values.size; }
    }
  });
})();
</script>"""


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"Maintained editor source not found: {SOURCE}")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    html = SOURCE.read_text(encoding="utf-8-sig")
    html = html.replace("<script>", STORAGE_SHIM + "<script>", 1)
    errors: list[str] = []
    results: dict[str, object] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1440, "height": 960},
            accept_downloads=True,
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append("console: " + message.text)
            if message.type == "error"
            else None,
        )
        page.set_content(html, wait_until="load")
        page.wait_for_timeout(250)

        assert page.title() == "Minecraft Mod Studio V2.5"
        assert page.locator("#studioNav").count() == 1
        assert page.locator(".inspector").count() == 1

        # Each editing mode must expose exactly one primary editor panel.
        for mode in ("texture", "model", "recipe", "behavior"):
            tab = page.locator(f"#tab-{mode}")
            tab.click()
            page.wait_for_timeout(60)
            assert tab.get_attribute("aria-selected") == "true", mode
            assert page.locator(".workspace").get_attribute("data-focus") == mode
            assert page.locator(".workspace .editor-panel:not([hidden])").count() == 1, mode
            assert page.locator(f"#{mode}Panel").is_visible(), mode
        page.locator("#tab-model").click()
        assert not page.locator(".workspace .showcase").is_visible(), "Model mode must reclaim the preview column"
        page.screenshot(path=str(ARTIFACTS / "workbench-model-desktop.png"), full_page=True)

        # Tabs must be keyboard operable and announce their selected state.
        page.locator("#tab-texture").focus()
        page.keyboard.press("ArrowRight")
        assert page.locator("#tab-model").get_attribute("aria-selected") == "true"
        results["keyboard_tab_navigation"] = "PASS"

        # HEX entry must update the actual native color control, not only the DOM text.
        page.locator("#tab-texture").click()
        color_hex = page.locator(".color-value-control:has(#color) .color-hex")
        assert color_hex.count() == 1, "Texture color HEX field missing"
        color_hex.fill("#ff00aa")
        color_hex.press("Tab")
        assert page.locator("#color").input_value().lower() == "#ff00aa"
        results["texture_custom_hex"] = page.locator("#color").input_value()

        # A malformed HEX value must be rejected and restored to the stored color.
        color_hex.fill("#gggggg")
        color_hex.press("Tab")
        assert page.locator("#color").input_value().lower() == "#ff00aa"
        results["invalid_hex_rejected"] = True

        # Recipe identifiers are not limited to the sample dropdown options.
        page.locator("#tab-recipe").click()
        page.locator("#ingredientCustom").fill("othermod:crystal")
        page.locator("#useCustomIngredient").click()
        assert page.locator("#ingredient").input_value() == "othermod:crystal"
        page.locator("#craftGrid button").first.click()
        assert page.locator("#craftGrid button").first.get_attribute("title") == "othermod:crystal"
        generated_recipe = page.evaluate("StudioCompiler.recipe(project, project.items[0])")
        assert "othermod:crystal" in list(generated_recipe["key"].values()), generated_recipe
        results["custom_recipe_id"] = {
            "selected": page.locator("#ingredient").input_value(),
            "generated_key_values": list(generated_recipe["key"].values()),
            "runtime_registry_verified": False,
        }

        # Invalid namespace syntax must not enter the recipe selector.
        page.locator("#ingredientCustom").fill("Other Mod:bad id")
        page.locator("#useCustomIngredient").click()
        assert "Invalid ID" in page.locator("#toast").inner_text()
        assert page.locator("#ingredient").input_value() == "othermod:crystal"
        results["invalid_resource_id_rejected"] = True

        # The shared inspector must also expose HEX controls for dynamic resource colors.
        page.locator('#studioNav button[data-open="blocks"]').click()
        page.wait_for_timeout(150)
        assert page.locator("#studioFields input[type=color]").count() >= 1
        assert page.locator("#studioFields .color-value-control .color-hex").count() >= 1
        assert page.locator(".inspector").count() == 1
        results["dynamic_inspector_hex"] = "PASS"
        page.screenshot(path=str(ARTIFACTS / "workbench-block-inspector.png"), full_page=True)

        # Capture a narrow viewport for review; no desktop-only assertion is substituted for visual review.
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(150)
        page.screenshot(path=str(ARTIFACTS / "workbench-mobile.png"), full_page=True)
        assert page.locator("#studioNav").is_visible()
        results["mobile_capture"] = "CAPTURED_REQUIRES_VISUAL_REVIEW"

        browser.close()

    assert not errors, "Browser errors: " + " | ".join(errors)
    results["browser_errors"] = errors
    results["screenshots"] = [
        "workbench-model-desktop.png",
        "workbench-block-inspector.png",
        "workbench-mobile.png",
    ]
    (ARTIFACTS / "result.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
