#!/usr/bin/env python3
"""End-to-end acceptance for JAR import, IndexedDB persistence, resource migration and compatibility staging."""
from __future__ import annotations
import base64, json, re, threading, zipfile, subprocess, sys, hashlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
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
                page.locator("#ca-list .ca-select").evaluate("(el)=>{el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}))}")
                page.wait_for_function("document.querySelector('#ca-list .ca-select')?.checked === true")
                page.locator("#ca-rights").check()
                page.locator("#ca-stage").click()
                page.wait_for_selector("#compatAnalysis",state="detached")
                assert page.locator("#rl-staged article").count()==4
                page.locator("#rl-close").click()
                page.wait_for_function("!document.querySelector('#resourceLibrary')?.open")
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
                    exportFiles:[...out.files.entries()].map(([path,value])=>{const bytes=typeof value==='string'?new TextEncoder().encode(value):value;let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));return {path,base64:btoa(binary)}}),
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
        assert compiled.get("exportFiles"), "Compiler did not return export files"
        build_dir=tmp/"generated-fabric-project"
        build_dir.mkdir()
        for row in compiled["exportFiles"]:
            rel=PurePosixPath(row["path"])
            if rel.is_absolute() or ".." in rel.parts or "\\" in row["path"]:
                raise AssertionError("Unsafe compiler output path: "+row["path"])
            target=build_dir.joinpath(*rel.parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(base64.b64decode(row["base64"],validate=True))
        build=subprocess.run([sys.executable,str(build_dir/"studio_build.py"),"build"],cwd=build_dir,capture_output=True,text=True,timeout=900)
        if build.returncode:
            raise AssertionError("Imported-resource Fabric build failed:\n"+build.stdout[-6000:]+"\n"+build.stderr[-6000:])
        receipt=json.loads((build_dir/"studio-build-result.json").read_text())
        assert receipt.get("status")=="BUILD_VERIFIED",receipt
        meta=json.loads((build_dir/"src/main/resources/fabric.mod.json").read_text())
        assert {"mod_alpha","mod_beta"}.issubset(set(meta.get("depends",{}))),meta
        jars=list((build_dir/"build/libs").glob("*.jar"))
        jars=[x for x in jars if not x.name.endswith("-sources.jar")]
        assert len(jars)==1,[x.name for x in jars]
        jar=jars[0]
        with zipfile.ZipFile(jar) as zf:
            assert zf.testzip() is None,"Generated JAR CRC failure"
            names=set(zf.namelist())
            required={"fabric.mod.json","assets/stormshard_mod/items/imported/mod_alpha/gem.json","assets/stormshard_mod/models/imported/mod_alpha/item/gem.json","assets/stormshard_mod/textures/imported/mod_alpha/item/gem.png","data/mod_alpha/recipe/steel.json","META-INF/studio-resource-notices.json"}
            assert required.issubset(names),sorted(required-names)
            jar_meta=json.loads(zf.read("fabric.mod.json"))
            assert {"mod_alpha","mod_beta"}.issubset(set(jar_meta.get("depends",{}))),jar_meta
        fabric_build={"status":"BUILD_VERIFIED","jar":jar.name,"bytes":jar.stat().st_size,"sha256":hashlib.sha256(jar.read_bytes()).hexdigest(),"required_resource_entries":6,"dependencies":["mod_alpha","mod_beta"]}
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
          "fabric_build":fabric_build,
          "browser_page_errors":len(errors),
          "scope":"static resource import, local persistence, model/texture dependency migration and shared-tag recipe patch generation; not a claim of in-game compatibility"
        }
        print(json.dumps(result,indent=2,ensure_ascii=False))
        (ROOT/"resource-library-acceptance-result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")

if __name__=="__main__": main()
