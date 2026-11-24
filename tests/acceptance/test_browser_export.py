#!/usr/bin/env python3
"""Browser-to-Fabric-source acceptance test for Minecraft Mod Studio.

The app is loaded with Playwright set_content because some sandboxed CI/browser
policies block file:// and localhost navigation. A small in-memory localStorage
shim allows the app's project editor to initialize; IndexedDB persistence is not
covered by this test.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "Minecraft_Mod_Studio_V19.html"

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


def check_inline_javascript(html: str) -> int:
    scripts = re.findall(r"<script\b([^>]*)>([\s\S]*?)</script\s*>", html, re.I)
    checked = 0
    with tempfile.TemporaryDirectory(prefix="mms-js-") as temp:
        temp_path = Path(temp)
        for index, (attrs, body) in enumerate(scripts, 1):
            if re.search(r"\bsrc\s*=", attrs, re.I) or not body.strip():
                continue
            script = temp_path / f"inline-{index:02d}.js"
            script.write_text(body, encoding="utf-8")
            subprocess.run(["node", "--check", str(script)], check=True, capture_output=True, text=True)
            checked += 1
    return checked


def safe_extract(archive: Path, destination: Path) -> int:
    with zipfile.ZipFile(archive) as zf:
        for item in zf.infolist():
            name = item.filename
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise AssertionError(f"Unsafe path in generated ZIP: {name}")
            target = (destination / Path(*path.parts)).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise AssertionError(f"ZIP path escaped destination: {name}")
        zf.extractall(destination)
        return len(zf.infolist())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=Path, help="Keep the generated Gradle project at this path")
    parser.add_argument("--chromium", default=os.environ.get("CHROMIUM"), help="Optional Chromium executable")
    args = parser.parse_args()

    if not SOURCE.is_file():
        raise SystemExit(f"Source HTML not found: {SOURCE}")
    html = SOURCE.read_text(encoding="utf-8-sig")
    js_count = check_inline_javascript(html)

    export_dir = args.export_dir.resolve() if args.export_dir else Path(tempfile.mkdtemp(prefix="mms-export-"))
    export_dir.mkdir(parents=True, exist_ok=True)
    if any(export_dir.iterdir()):
        raise SystemExit(f"Export directory must be empty: {export_dir}")

    html = html.replace("<script>", STORAGE_SHIM + "<script>", 1)
    browser_errors: list[str] = []
    downloaded_zip = export_dir.parent / (export_dir.name + "-source.zip")

    with sync_playwright() as playwright:
        launch = {"headless": True, "args": ["--no-sandbox"]}
        if args.chromium:
            launch["executable_path"] = args.chromium
        browser = playwright.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1600, "height": 1100}, accept_downloads=True)
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.on("console", lambda message: browser_errors.append("console: " + message.text) if message.type == "error" else None)

        page.set_content(html, wait_until="load")
        page.wait_for_timeout(250)
        assert page.title() == "Minecraft Mod Studio V2.5", page.title()
        assert page.locator("#studioNav").count() == 1, "Workspace navigation did not initialize"

        page.locator("#test").click()
        page.wait_for_timeout(100)
        validation = page.locator("#validationCard").inner_text()
        assert "Validation passed" in validation, validation
        assert page.locator("#errorCount").inner_text() == "(0)"

        page.locator('#studioNav button[data-open="mobs"]').click()
        page.wait_for_timeout(100)
        assert page.locator("#rigBoneSelect").count() == 1, "Skeleton editor missing"
        assert page.locator("#rigAnimSelect").count() == 1, "Animation timeline missing"
        assert page.locator("#v09UvCanvas").count() == 1, "UV/material editor missing"
        bones_before = page.locator("#rigBoneSelect option").count()
        page.locator('[data-rig="add-bone"]').click()
        page.wait_for_timeout(100)
        bones_after = page.locator("#rigBoneSelect option").count()
        assert bones_after == bones_before + 1, f"Add-bone action failed: {bones_before} -> {bones_after}"

        page.locator('#studioNav button[data-open="blocks"]').click()
        page.wait_for_timeout(100)
        assert page.locator("#blockTexturePreview").count() == 1, "Block workspace did not render"

        page.locator("#build").click()
        page.wait_for_timeout(100)
        assert page.locator("#dialog").is_visible(), "Fabric export confirmation did not open"
        assert page.locator("#exportFabricSource").count() == 1, "Fabric source export action missing"
        consent = page.locator('#dialog input[type="checkbox"]')
        if consent.count():
            consent.check()
        assert not page.locator("#exportFabricSource").is_disabled(), "Export remains disabled after explicit partial-export consent"

        with page.expect_download(timeout=30_000) as pending:
            page.locator("#exportFabricSource").click()
        download = pending.value
        download.save_as(str(downloaded_zip))
        browser.close()

    assert not browser_errors, "Browser errors: " + " | ".join(browser_errors)
    assert downloaded_zip.is_file() and downloaded_zip.stat().st_size > 0
    file_count = safe_extract(downloaded_zip, export_dir)

    for required in (
        "build.gradle", "settings.gradle", "gradle.properties", "studio_build.py",
        "studio_smoke.py", "studio-export-report.json", "studio-build-manifest.json",
        "studio-project.json", "src/main/resources/fabric.mod.json",
    ):
        assert (export_dir / required).is_file(), f"Generated project missing {required}"

    report = json.loads((export_dir / "studio-export-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((export_dir / "studio-build-manifest.json").read_text(encoding="utf-8"))
    assert report.get("status") == "SOURCE_GENERATED_NOT_BUILT", report.get("status")
    assert report.get("gameRuntimeVerification", {}).get("status") == "NOT_RUN"
    assert report.get("clientRendering", {}).get("gameRuntimeVerified") is False
    assert len(manifest.get("files", {})) >= 50, "Unexpectedly small source manifest"

    subprocess.run(
        [sys.executable, str(export_dir / "studio_build.py"), "preflight"],
        cwd=export_dir, capture_output=True, text=True, timeout=90,
    )
    receipt_path = export_dir / "studio-build-result.json"
    assert receipt_path.is_file(), "Build Doctor did not write a preflight receipt"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt.get("source") == "PASS", json.dumps(receipt, ensure_ascii=False)
    assert receipt.get("status") in ("PREFLIGHT_PASS", "ENVIRONMENT_BLOCKED"), json.dumps(receipt, ensure_ascii=False)

    rig_sources = list((export_dir / "src/main/java").rglob("*Rig.java"))
    javac = shutil.which("javac")
    javac_status = "SKIPPED_NO_JAVAC"
    if rig_sources and javac:
        classes = export_dir / ".acceptance-classes"
        classes.mkdir(exist_ok=True)
        compile_result = subprocess.run(
            [javac, "-d", str(classes), *map(str, rig_sources)],
            capture_output=True, text=True, timeout=90,
        )
        assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
        javac_status = "PASS"

    summary = {
        "inline_scripts_syntax_checked": js_count,
        "browser_page_errors": len(browser_errors),
        "validation": validation,
        "skeleton_bones_before_after": [bones_before, bones_after],
        "generated_zip_entries": file_count,
        "manifest_files": len(manifest["files"]),
        "source_preflight": receipt.get("status"),
        "source_integrity": receipt.get("source"),
        "environment": receipt.get("environment"),
        "rig_javac": javac_status,
        "runtime_verification": report.get("gameRuntimeVerification", {}).get("status"),
        "export_dir": str(export_dir),
        "zip": str(downloaded_zip),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
