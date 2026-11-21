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
    page.locator('[data-preset="dungeon"]').click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('建筑已加载')")
    assert "31 × 7 × 25" in page.locator("#counts").inner_text()
    assert "8/8" in page.locator("#checks").inner_text()
    with page.expect_download() as d:
        page.locator("#json").click()
    dungeon_json = Path(tmp) / "dungeon.json"
    d.value.save_as(dungeon_json)
    metadata = json.loads(dungeon_json.read_text())["metadata"]
    assert metadata["generator"] == "room-graph-v1"
    assert len(metadata["rooms"]) == 8 and metadata["hiddenPassages"] == 1
    assert page.locator("#dungeonOptions").is_visible()
    page.locator("#dungeonStyle").select_option("crypt")
    page.locator("#dungeonDifficulty").select_option("hard")
    page.locator("#dungeonShaftDepth").select_option("24")
    page.locator("#dungeonRooms").fill("10")
    page.locator("#hiddenRooms").fill("2")
    page.locator("#corridorWidth").select_option("3")
    page.locator("#loopChance").fill("0.34")
    page.locator("#generate").click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('建筑已加载')")
    assert "10/10" in page.locator("#checks").inner_text()
    assert "钥匙门 1 · 秘密门 2" in page.locator("#checks").inner_text()
    assert "钥匙箱 room-" in page.locator("#checks").inner_text()
    with page.expect_download() as d:
        page.locator("#json").click()
    configured_path = Path(tmp) / "configured-dungeon.json"
    d.value.save_as(configured_path)
    configured_json = json.loads(configured_path.read_text())
    configured = configured_json["metadata"]
    assert configured["style"] == "crypt"
    assert configured["encounterDifficulty"] == "hard"
    assert configured["roomHeight"] == 7 and configured["shaftDepth"] == 24
    assert configured["entranceShaft"]["depth"] == 24
    assert configured["keyChest"]["keyId"].endswith("/bronze_key")
    assert len(configured["interactiveDoors"]) == 3
    assert len(configured_json["entities"]) == 3
    assert sum(1 for door in configured["interactiveDoors"] if door["kind"] == "locked") == 1
    assert sum(1 for door in configured["interactiveDoors"] if door["kind"] == "secret") == 2
    assert configured["roomCount"] == 10 and configured["hiddenPassages"] == 2
    assert configured["corridorWidth"] == 3 and configured["loopChance"] == 0.34
    loot_blocks = [block for block in configured_json["blocks"] if block.get("nbt", {}).get("LootTable")]
    key_blocks = [block for block in configured_json["blocks"] if block.get("nbt", {}).get("Items")]
    assert len(loot_blocks) >= 2
    assert all(block["nbt"]["LootTable"].startswith("minecraft:chests/") for block in loot_blocks)
    assert len(key_blocks) == 1
    assert key_blocks[0]["nbt"]["Items"][0]["id"] == "minecraft:tripwire_hook"
    assert key_blocks[0]["nbt"]["Items"][0]["components"]["minecraft:custom_data"]["mmsd_key"] == configured["keyChest"]["keyId"]
    with page.expect_download() as d:
        page.locator("#nbt").click()
    dungeon_nbt_path = Path(tmp) / "dungeon.nbt"
    d.value.save_as(dungeon_nbt_path)
    dungeon_nbt = gzip.decompress(dungeon_nbt_path.read_bytes())
    assert b"LootTable" in dungeon_nbt and b"minecraft:chests/" in dungeon_nbt
    assert b"minecraft:ladder" in dungeon_nbt
    assert b"minecraft:interaction" in dungeon_nbt
    assert b"minecraft:tripwire_hook" in dungeon_nbt
    assert b"mmsd_key" in dungeon_nbt
    page.locator("#file").set_input_files(str(configured_path))
    page.wait_for_function("document.querySelector('#status').textContent.includes('建筑已加载')")
    assert page.locator('[data-preset="dungeon"]').get_attribute("class").find("active") >= 0
    assert page.locator("#dungeonStyle").input_value() == "crypt"
    assert page.locator("#dungeonDifficulty").input_value() == "hard"
    assert page.locator("#dungeonShaftDepth").input_value() == "24"
    assert page.locator("#dungeonRooms").input_value() == "10"
    assert page.locator("#hiddenRooms").input_value() == "2"
    assert page.locator("#corridorWidth").input_value() == "3"
    assert page.locator("#loopChance").input_value() == "0.34"
    page.locator("#generate").click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('建筑已加载')")
    assert "10/10" in page.locator("#checks").inner_text()
    assert not errors, errors
    page.screenshot(path="structure-editor-acceptance.png")
    browser.close()
print("browser editor interactions and download smoke passed")
