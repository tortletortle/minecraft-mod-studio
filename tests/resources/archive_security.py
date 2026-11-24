#!/usr/bin/env python3
"""Adversarial ZIP/JAR parser tests against the actual browser StudioResources.readZip."""
import base64, json, stat, zipfile, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
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

def overlapping_local_records():
    """Build a structurally valid ZIP whose second local record is embedded in the first PNG payload."""
    import struct, zlib
    from io import BytesIO
    def png(padding):
        ihdr=struct.pack(">IIBBBBB",1,1,8,2,0,0,0)
        return b"\x89PNG\r\n\x1a\n"+struct.pack(">I",13)+b"IHDR"+ihdr+b"\0"*4+b"\0"*padding
    out=BytesIO()
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_STORED) as z:
        z.writestr("fabric.mod.json",json.dumps({"schemaVersion":1,"id":"mod_alpha","version":"1.0.0","license":"MIT"}))
        z.writestr("assets/mod_alpha/models/a.png",png(2048))
        z.writestr("assets/mod_alpha/models/b.png",png(16))
    data=bytearray(out.getvalue())
    eocd=data.rfind(b"PK\x05\x06")
    cd_start=struct.unpack_from("<I",data,eocd+16)[0]
    count=struct.unpack_from("<H",data,eocd+10)[0]
    entries={}
    pos=cd_start
    for _ in range(count):
        if data[pos:pos+4]!=b"PK\x01\x02": raise AssertionError("invalid fixture central directory")
        nl,xl,cl=struct.unpack_from("<HHH",data,pos+28)
        name=bytes(data[pos+46:pos+46+nl]).decode("utf-8")
        offset=struct.unpack_from("<I",data,pos+42)[0]
        entries[name]=(pos,offset)
        pos+=46+nl+xl+cl
    a_cd,a_off=entries["assets/mod_alpha/models/a.png"]
    b_cd,b_off=entries["assets/mod_alpha/models/b.png"]
    a_nl,a_xl=struct.unpack_from("<HH",data,a_off+26)
    a_data=a_off+30+a_nl+a_xl
    a_size=struct.unpack_from("<I",data,a_off+22)[0]
    b_nl,b_xl=struct.unpack_from("<HH",data,b_off+26)
    b_packed=struct.unpack_from("<I",data,b_off+18)[0]
    b_record_end=b_off+30+b_nl+b_xl+b_packed
    b_record=bytes(data[b_off:b_record_end])
    embedded_offset=a_data+64
    if embedded_offset+len(b_record)>a_data+a_size:
        raise AssertionError("first entry payload is too small for overlap fixture")
    data[embedded_offset:embedded_offset+len(b_record)]=b_record
    first_crc=zlib.crc32(data[a_data:a_data+a_size])&0xffffffff
    struct.pack_into("<I",data,a_off+14,first_crc)
    struct.pack_into("<I",data,a_cd+16,first_crc)
    struct.pack_into("<I",data,b_cd+42,embedded_offset)
    return bytes(data)


def main():
    valid=archive([("assets/mod_alpha/models/item.json",'{"parent":"minecraft:item/generated"}')])
    traversal=archive([("../escape.json","x")])
    absolute=archive([("/tmp/escape.json","x")])
    backslash_name=r"assets\mod_alpha\models\evil.json"
    backslash_info=zipfile.ZipInfo(backslash_name)
    # Preserve raw backslashes: ZipInfo normalizes Windows separators on construction.
    backslash_info.filename=backslash_name
    backslash=archive([(backslash_name,"{}",backslash_info)])
    if backslash.count(backslash_name.encode("ascii"))!=2:
        raise AssertionError("Backslash fixture must preserve the raw name in both ZIP headers")
    overlap=overlapping_local_records()
    duplicate=archive([
        ("assets/mod_alpha/models/a.json","{}"),
        ("ASSETS/MOD_ALPHA/MODELS/A.JSON","{}")
    ])
    symlink_info=zipfile.ZipInfo("assets/mod_alpha/models/link.json")
    symlink_info.create_system=3
    symlink_info.external_attr=(stat.S_IFLNK|0o777)<<16
    symlink=archive([("assets/mod_alpha/models/link.json","target",symlink_info)])
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
        "overlapping_local_records":(overlap,False),
        "case_insensitive_duplicate":(duplicate,False),
        "symlink_entry":(symlink,False),
        "crc_corruption":(bytes(crc),False),
        "oversized_expanded_file":(huge,False),
        "unsupported_compression":(unsupported,False),
        "invalid_zip":(b"not-a-zip",False),
    }
    errors=[]
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(SimpleHTTPRequestHandler,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
            page=browser.new_page()
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/Minecraft_Mod_Studio_V19.html",wait_until="load")
            page.wait_for_function("typeof StudioResources !== 'undefined'")
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
    finally:
        server.shutdown();server.server_close()
    if errors: raise AssertionError("Browser errors: "+" | ".join(errors))
    result={"status":"PASS","cases":len(results),"accepted_valid_archive":results["valid_archive"]["accepted"],"rejected_cases":[k for k,v in results.items() if not v["accepted"]],"results":results,"scope":"actual StudioResources.readZip parser in Chromium; no filesystem extraction and no production JAR build"}
    (ROOT/"archive-security-result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__": main()
