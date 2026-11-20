#!/usr/bin/env python3
"""Adversarial ZIP/JAR parser tests against the actual browser StudioResources.readZip."""
import base64, json, stat, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/"Minecraft_Mod_Studio_V19.html"

def archive(entries, compression=zipfile.ZIP_DEFLATED):
    from io import BytesIO
    out=BytesIO()
    with zipfile.ZipFile(out,"w",compression=compression) as z:
        z.writestr("fabric.mod.json",json.dumps({"schemaVersion":1,"id":"mod_alpha","version":"1.0.0","license":"MIT"}))
        for entry in entries:
            name,data,*rest=entry
            if rest and isinstance(rest[0],zipfile.ZipInfo):
                z.writestr(rest[0],data)
            else:
                z.writestr(name,data,compress_type=rest[0] if rest else compression)
    return out.getvalue()

def main():
    valid=archive([("assets/mod_alpha/models/item.json",'{"parent":"minecraft:item/generated"}')])
    traversal=archive([("../escape.json","x")])
    absolute=archive([("/tmp/escape.json","x")])
    backslash=archive([(r"assets\mod_alpha\models\evil.json","{}")])
    duplicate=archive([
        ("assets/mod_alpha/models/a.json","{}"),
        ("ASSETS/MOD_ALPHA/MODELS/A.JSON","{}")
    ])
    symlink_info=zipfile.ZipInfo("assets/mod_alpha/models/link.json")
    symlink_info.create_system=3
    symlink_info.external_attr=(stat.S_IFLNK|0o777)<<16
    symlink_info.extra_data=b"target"
    symlink=archive([symlink_info])
    crc=bytearray(archive([("assets/mod_alpha/models/crc.json",b'{"marker":"CRC_SENTINEL"}',zipfile.ZIP_STORED)]))
    pos=crc.find(b"CRC_SENTINEL")
    assert pos>=0
    crc[pos]^=1
    huge=archive([("assets/mod_alpha/models/huge.json",json.dumps({"x":"A"*(8*1024*1024+1)}))])
    unsupported=archive([("assets/mod_alpha/models/bzip.json","{}",zipfile.ZIP_BZIP2)])
    cases={
        "valid_archive":(valid,True),
        "path_traversal":(traversal,False),
        "absolute_path":(absolute,False),
        "backslash_path":(backslash,False),
        "case_insensitive_duplicate":(duplicate,False),
        "symlink_entry":(symlink,False),
        "crc_corruption":(bytes(crc),False),
        "oversized_expanded_file":(huge,False),
        "unsupported_compression":(unsupported,False),
        "invalid_zip":(b"not-a-zip",False),
    }
    errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        page=browser.new_page()
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.set_content(APP.read_text(encoding="utf-8-sig"),wait_until="load")
        results={}
        for name,(blob,should_accept) in cases.items():
            encoded=base64.b64encode(blob).decode()
            outcome=page.evaluate("""async b64=>{
              const raw=atob(b64), bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));
              try { const x=await StudioResources.readZip(bytes,'fixture.jar'); return {accepted:true,entries:x.entries.length}; }
              catch(e) { return {accepted:false,error:String(e.message||e)}; }
            }""",encoded)
            results[name]=outcome
            if outcome["accepted"] is not should_accept:
                raise AssertionError(name+" unexpected parser result: "+str(outcome))
        browser.close()
    if errors: raise AssertionError("Browser errors: "+" | ".join(errors))
    result={"status":"PASS","cases":len(results),"accepted_valid_archive":results["valid_archive"]["accepted"],"rejected_cases":[k for k,v in results.items() if not v["accepted"]],"results":results,"scope":"actual StudioResources.readZip parser in Chromium; no filesystem extraction and no production JAR build"}
    (ROOT/"archive-security-result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
