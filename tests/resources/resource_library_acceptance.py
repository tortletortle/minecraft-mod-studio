#!/usr/bin/env python3
"""End-to-end acceptance for JAR import, IndexedDB persistence, resource migration and compatibility staging."""
from __future__ import annotations
import json, re, threading, zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]

def write_archive(path:Path, mod_id:str, entries:dict[str,bytes|str]):
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("fabric.mod.json",json.dumps({"schemaVersion":1,"id":mod_id,"version":"1.0.0","name":mod_id,"license":"MIT","environment":"*"}))
        z.writestr("LICENSE","MIT License\nPermission is hereby granted for this synthetic test fixture only.\n")
        for name,value in entries.items():
            z.writestr(name,value if isinstance(value,bytes) else value.encode())

def main():
    with TemporaryDirectory(prefix="mms-resource-") as td:
        tmp=Path(td)
        png=tmp/"gem.png"
        Image.new("RGBA",(16,16),(64,180,240,255)).save(png)
        texture=png.read_bytes()
        alpha=tmp/"mod_alpha.jar"
        beta=tmp/"mod_beta.jar"
        evil=tmp/"evil.zip"
        write_archive(alpha,"mod_alpha",{
            "data/c/tags/item/gems/rare.json":json.dumps({"replace":False,"values":["mod_alpha:gem"]}),
            "data/mod_alpha/recipe/steel.json":json.dumps({"type":"minecraft:crafting_shapeless","ingredients":["mod_alpha:gem","minecraft:iron_ingot"],"result":{"id":"mod_alpha:steel","count":1}}),
            "assets/mod_alpha/items/gem.json":json.dumps({"model":{"type":"minecraft:model","model":"mod_alpha:item/gem"}}),
            "assets/mod_alpha/models/item/gem.json":json.dumps({"parent":"minecraft:item/generated","textures":{"layer0":"mod_alpha:item/gem"}}),
            "assets/mod_alpha/textures/item/gem.png":texture,
        })
        write_archive(beta,"mod_beta",{
            "data/c/tags/item/gems/rare.json":json.dumps({"replace":False,"values":["mod_beta:gem"]}),
        })
        with zipfile.ZipFile(evil,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("fabric.mod.json",json.dumps({"id":"mod_evil","version":"1.0.0"}))
            z.writestr("../escape.json","must never be extracted")
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(SimpleHTTPRequestHandler,directory=str(ROOT)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        errors=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
                context=browser.new_context(accept_downloads=True,viewport={"width":1600,"height":1100})
                page=context.new_page()
                page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{server.server_port}/Minecraft_Mod_Studio_V19.html",wait_until="load")
                page.wait_for_selector("#openResources")
                page.locator("#openResources").click()
                page.wait_for_selector("#resourceLibrary[open]")
                page.locator("#rl-file").set_input_files([str(alpha),str(beta)])
                page.wait_for_function("document.querySelector('#rl-source').options.length === 3",timeout=15000)
                page.wait_for_function("document.querySelector('#rl-status').textContent.includes('mod_beta.jar')",timeout=15000)
                imported=page.locator("#rl-source option").all_text_contents()
                assert any("mod_alpha" in x for x in imported), imported
                assert any("mod_beta" in x for x in imported), imported

                page.locator("#rl-source").select_option(value="")  # show resources from both imported archives
                page.locator("#rl-search").fill("assets/mod_alpha/items/gem.json")
                page.locator("#rl-list button").filter(has_text="assets/mod_alpha/items/gem.json").first.click()
                page.locator("#rl-migrate").click()
                page.wait_for_selector("#assetMigration[open]")
                migration_summary=page.locator("#am-summary").inner_text()
                assert "迁移 3 项" in migration_summary, migration_summary
                assert not page.locator("#am-errors").inner_text().strip(), page.locator("#am-errors").inner_text()
                assert not page.locator("#am-stage").is_disabled()
                page.locator("#am-rights").check()
                page.locator("#am-stage").click()
                page.wait_for_selector("#assetMigration",state="detached")
                assert page.locator("#rl-staged article").count()==3

                page.locator("#rl-compat").click()
                page.wait_for_selector("#compatAnalysis[open]")
                compat_summary=page.locator("#ca-summary").inner_text()
                assert "材料组 1" in compat_summary and "候选补丁 1" in compat_summary, compat_summary
                assert page.locator("#ca-list .ca-select").count()==1
                page.locator("#ca-list details summary").first.click()
                page.locator("#ca-list .ca-select").check()
                page.locator("#ca-rights").check()
                page.locator("#ca-stage").click()
                page.wait_for_selector("#compatAnalysis",state="detached")
                assert page.locator("#rl-staged article").count()==4
                page.locator("#save").click()
                page.wait_for_function("document.querySelector('#saveStatus').textContent.includes('Saved locally')")

                compiled=page.evaluate("""() => {
                  const out=StudioCompiler.compile(project,{allowPartial:true});
                  const mod=JSON.parse(out.files.get('src/main/resources/fabric.mod.json'));
                  const report=JSON.parse(out.files.get('studio-export-report.json'));
                  return {
                    staged:project.resourceOverrides.length,
                    dependencies:Object.keys(mod.depends||{}).sort(),
                    files:[...out.files.keys()].filter(x=>x.includes('/imported/mod_alpha/')||x.endsWith('/data/mod_alpha/recipe/steel.json')),
                    verification:report.resourceLibrary?.verification,
                    provenance:report.resourceLibrary?.entries?.length
                  };
                }""")
                assert compiled["staged"]==4,compiled
                assert {"mod_alpha","mod_beta"}.issubset(set(compiled["dependencies"])),compiled
                assert compiled["verification"]=="STATIC_ONLY" and compiled["provenance"]==4,compiled
                assert any(x.endswith("/data/mod_alpha/recipe/steel.json") for x in compiled["files"]),compiled
                assert sum("/imported/mod_alpha/" in x for x in compiled["files"])==3,compiled

                page.locator("#rl-file").set_input_files(str(evil))
                page.wait_for_function("document.querySelector('#rl-status').textContent.includes('不安全 ZIP 路径')",timeout=10000)
                assert page.locator("#rl-source option").count()==3

                page.reload(wait_until="load")
                page.locator("#openResources").click()
                page.wait_for_selector("#resourceLibrary[open]")
                page.wait_for_function("document.querySelector('#rl-source').options.length === 3",timeout=15000)
                assert page.locator("#rl-staged article").count()==4, "Project patches did not survive reload"
                persisted=page.locator("#rl-source option").all_text_contents()
                assert any("mod_alpha" in x for x in persisted) and any("mod_beta" in x for x in persisted),persisted
                browser.close()
        finally:
            server.shutdown();server.server_close()
        assert not errors,"Browser errors: "+" | ".join(errors)
        result={
          "status":"PASS",
          "archive_imports":2,
          "indexeddb_sources_after_reload":2,
          "malicious_path_rejected":True,
          "migration_resources":3,
          "shared_material_groups":1,
          "compatibility_recipe_candidates":1,
          "staged_project_patches":4,
          "export_dependencies":["mod_alpha","mod_beta"],
          "resource_verification":"STATIC_ONLY",
          "browser_page_errors":len(errors),
          "scope":"static resource import, local persistence, model/texture dependency migration and shared-tag recipe patch generation; not a claim of in-game compatibility"
        }
        print(json.dumps(result,indent=2,ensure_ascii=False))
        (ROOT/"resource-library-acceptance-result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")

if __name__=="__main__": main()
