"""Run against python -m http.server 8765 from repo root."""
import gzip
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto("http://127.0.0.1:8765/structure-studio/editor.html", wait_until="networkidle")
    page.wait_for_function("document.querySelector('#counts').textContent.includes('3672')")
    page.locator("#layer").evaluate("(el) => { el.value = 1; el.dispatchEvent(new Event(\'input\', {bubbles:true})); }")
    page.locator("#x").fill("13")
    page.locator("#z").fill("1")
    page.locator("#apply").click()
    assert "stone_bricks" in page.locator("#selected").inner_text()
    assert "受阻" in page.locator("#checks").inner_text()
    page.locator("#undo").click()
    assert "minecraft:air" in page.locator("#selected").inner_text()
    assert "有效" in page.locator("#checks").inner_text()
    page.locator("#redo").click()
    assert "stone_bricks" in page.locator("#selected").inner_text()
    page.locator('[data-mode="preserve"]').click()
    page.locator("#apply").click()
    assert "未写入" in page.locator("#selected").inner_text()
    page.locator('[data-mode="erase"]').click()
    page.locator("#apply").click()
    assert "minecraft:air" in page.locator("#selected").inner_text()
    # Exercise pointer mapping after camera rotation using the actual canvas bounds.
    page.locator("#rotateRight").click()
    page.wait_for_timeout(150)
    point = page.evaluate("""async () => {
      const {projection}=await import('/structure-studio/projection.mjs');
      const r=document.querySelector('#view').getBoundingClientRect();
      const p=projection([27,8,17],1,1,[r.width,r.height]).point(3.5,2,3.5);
      return [r.left+p[0],r.top+p[1]];
    }""")
    page.locator('[data-mode="place"]').click()
    page.mouse.click(*point)
    assert "(3, 1, 3)" in page.locator("#selected").inner_text()
    assert "stone_bricks" in page.locator("#selected").inner_text()
    page.locator("#all").click()
    assert page.locator("#apply").is_disabled()
    page.locator("#all").click()
    assert page.locator("#apply").is_enabled()
    with page.expect_download() as d:
        page.locator("#json").click()
    jsonpath = Path(tmp) / "structure.json"
    d.value.save_as(jsonpath)
    s = json.loads(jsonpath.read_text())
    assert s["size"] == [27,8,17]
    assert any(c["pos"] == [3,1,3] and c["block"]["name"] == "minecraft:stone_bricks" for c in s["blocks"])
    with page.expect_download() as d:
        page.locator("#nbt").click()
    nbtpath = Path(tmp) / "structure.nbt"
    d.value.save_as(nbtpath)
    data = gzip.decompress(nbtpath.read_bytes())
    assert data[:3] == bytes([10,0,0]) and b"DataVersion" in data
    page.locator("#file").set_input_files(str(jsonpath))
    page.wait_for_function("document.querySelector('#status').textContent.includes('建筑已加载')")
    assert not errors, errors
    page.screenshot(path="structure-editor-acceptance.png")
    browser.close()
print("browser editor interactions and download smoke passed")
