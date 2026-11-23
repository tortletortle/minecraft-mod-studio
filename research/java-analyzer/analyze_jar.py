#!/usr/bin/env python3
"""Read-only static analyzer for Minecraft Java mod JARs. Never loads or executes classes."""
from __future__ import annotations
import argparse, hashlib, json, re, stat, struct, sys, zipfile
from collections import Counter
from pathlib import Path
from typing import Any
try:
    import tomllib
except ImportError:
    tomllib = None

VERSION = "0.2.0"
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_ENTRY = 16 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_ENTRIES = 20_000
MAX_RATIO = 250
MAX_CLASSES = 12_000
MAX_JSON = 2 * 1024 * 1024
MAX_SAMPLES = 500
MAGIC = 0xCAFEBABE

class AnalysisError(Exception):
    pass

class Reader:
    def __init__(self, data: bytes):
        self.data, self.pos = data, 0
    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise AnalysisError("truncated class-file structure")
        out = self.data[self.pos:self.pos+n]
        self.pos += n
        return out
    def u1(self): return self.take(1)[0]
    def u2(self): return struct.unpack(">H", self.take(2))[0]
    def u4(self): return struct.unpack(">I", self.take(4))[0]

def mutf8(raw: bytes) -> str:
    """Decode JVM modified UTF-8, including its two-byte NUL and UTF-16 surrogate encoding."""
    units, i = bytearray(), 0
    while i < len(raw):
        b = raw[i]
        if 1 <= b <= 0x7f:
            v, n = b, 1
        elif 0xc0 <= b <= 0xdf:
            if i + 1 >= len(raw):
                raise AnalysisError("truncated modified UTF-8 sequence")
            b1 = raw[i + 1]
            if b1 & 0xc0 != 0x80:
                raise AnalysisError("invalid modified UTF-8 continuation byte")
            v = ((b & 0x1f) << 6) | (b1 & 0x3f)
            if v == 0:
                if b != 0xc0 or b1 != 0x80:
                    raise AnalysisError("invalid modified UTF-8 NUL encoding")
            elif v < 0x80:
                raise AnalysisError("overlong modified UTF-8 sequence")
            n = 2
        elif 0xe0 <= b <= 0xef:
            if i + 2 >= len(raw):
                raise AnalysisError("truncated modified UTF-8 sequence")
            b1, b2 = raw[i + 1], raw[i + 2]
            if b1 & 0xc0 != 0x80 or b2 & 0xc0 != 0x80:
                raise AnalysisError("invalid modified UTF-8 continuation byte")
            v = ((b & 0x0f) << 12) | ((b1 & 0x3f) << 6) | (b2 & 0x3f)
            if v < 0x800:
                raise AnalysisError("overlong modified UTF-8 sequence")
            n = 3
        else:
            raise AnalysisError("invalid modified UTF-8 lead byte")
        units.extend(struct.pack(">H", v))
        i += n
    try:
        return units.decode("utf-16-be")
    except UnicodeDecodeError as exc:
        raise AnalysisError("invalid modified UTF-8 surrogate sequence") from exc

def utf8(cp, i):
    if not 0 < i < len(cp) or not cp[i] or cp[i][0] != 1:
        raise AnalysisError(f"invalid CONSTANT_Utf8 index {i}")
    return cp[i][1]

def class_name(cp, i):
    if not 0 < i < len(cp) or not cp[i] or cp[i][0] != 7:
        raise AnalysisError(f"invalid CONSTANT_Class index {i}")
    return utf8(cp, cp[i][1])

def member_ref(cp, i):
    if not 0 < i < len(cp) or not cp[i] or cp[i][0] not in (9, 10, 11):
        return None
    e = cp[i]
    if not 0 < e[2] < len(cp) or not cp[e[2]] or cp[e[2]][0] != 12:
        return None
    nt = cp[e[2]]
    return {"owner": class_name(cp, e[1]), "name": utf8(cp, nt[1]),
            "descriptor": utf8(cp, nt[2]),
            "kind": {9:"field",10:"method",11:"interface_method"}[e[0]]}

def instruction_size(code: bytes, pc: int) -> int:
    if pc < 0 or pc >= len(code):
        raise AnalysisError("instruction offset outside Code array")
    op = code[pc]
    if op == 0xaa:
        a = (pc + 4) & ~3
        if a + 12 > len(code):
            raise AnalysisError("truncated tableswitch")
        low, high = struct.unpack_from(">ii", code, a + 4)
        if high < low:
            raise AnalysisError("invalid tableswitch bounds")
        count = high - low + 1
        if count > 1_000_000:
            raise AnalysisError("tableswitch exceeds entry limit")
        size = a - pc + 12 + count * 4
    elif op == 0xab:
        a = (pc + 4) & ~3
        if a + 8 > len(code):
            raise AnalysisError("truncated lookupswitch")
        count = struct.unpack_from(">i", code, a + 4)[0]
        if count < 0 or count > 1_000_000:
            raise AnalysisError("invalid lookupswitch count")
        size = a - pc + 8 + count * 8
    elif op == 0xc4:
        if pc + 1 >= len(code):
            raise AnalysisError("truncated wide")
        modified = code[pc + 1]
        if modified not in set(range(0x15, 0x1a)) | set(range(0x36, 0x3b)) | {0xa9, 0x84}:
            raise AnalysisError("invalid opcode following wide")
        size = 6 if modified == 0x84 else 4
    else:
        one = {0x10,0x12,0x15,0x16,0x17,0x18,0x19,0x36,0x37,0x38,0x39,0x3a,0xa9,0xbc}
        two = {0x11,0x13,0x14,0x84,0xc6,0xc7,0xbb,0xbd,0xc0,0xc1}
        two.update(range(0x99,0xa9))
        two.update(range(0xb2,0xb9))
        four = {0xb9,0xba,0xc8,0xc9}
        three = {0xc5}
        if op > 0xc9:
            raise AnalysisError(f"reserved opcode 0x{op:02x}")
        size = 1 + (1 if op in one else 2 if op in two else 4 if op in four else 3 if op in three else 0)
    if pc + size > len(code):
        raise AnalysisError("bytecode instruction exceeds Code attribute")
    return size

def scan_code(code: bytes, cp):
    refs, dynamic, pc = [], 0, 0
    while pc < len(code):
        size = instruction_size(code, pc)
        op = code[pc]
        if op in (0xb6,0xb7,0xb8,0xb9):
            index = struct.unpack_from(">H", code, pc + 1)[0]
            allowed = (10,) if op == 0xb6 else ((11,) if op == 0xb9 else (10, 11))
            if not 0 < index < len(cp) or not cp[index] or cp[index][0] not in allowed:
                raise AnalysisError("invalid method reference for invocation opcode")
            ref = member_ref(cp, index)
            if ref is None:
                raise AnalysisError("malformed method reference")
            if op == 0xb9 and (code[pc + 3] == 0 or code[pc + 4] != 0):
                raise AnalysisError("invalid invokeinterface operands")
            ref["opcode"] = {
                0xb6:"invokevirtual",0xb7:"invokespecial",
                0xb8:"invokestatic",0xb9:"invokeinterface"
            }[op]
            refs.append(ref)
        elif op == 0xba:
            index = struct.unpack_from(">H", code, pc + 1)[0]
            if not 0 < index < len(cp) or not cp[index] or cp[index][0] != 18:
                raise AnalysisError("invalid CONSTANT_InvokeDynamic reference")
            if code[pc + 3] != 0 or code[pc + 4] != 0:
                raise AnalysisError("invalid invokedynamic reserved operands")
            dynamic += 1
        elif op == 0xbc and code[pc + 1] not in range(4, 12):
            raise AnalysisError("invalid newarray atype")
        elif op == 0xc5 and code[pc + 3] == 0:
            raise AnalysisError("invalid multianewarray dimensions")
        pc += size
    return refs, dynamic

def parse_code(data: bytes, cp):
    r = Reader(data)
    r.u2()  # max_stack
    r.u2()  # max_locals
    code_length = r.u4()
    if not 0 < code_length < 65536:
        raise AnalysisError("Code attribute length must be between 1 and 65535")
    code = r.take(code_length)
    for _ in range(r.u2()):
        start_pc, end_pc, handler_pc, catch_type = r.u2(), r.u2(), r.u2(), r.u2()
        if not (start_pc < end_pc <= code_length and handler_pc < code_length):
            raise AnalysisError("invalid Code exception-table range")
        if catch_type:
            class_name(cp, catch_type)
    for _ in range(r.u2()):
        utf8(cp, r.u2())
        r.take(r.u4())
    if r.pos != len(data):
        raise AnalysisError("trailing Code attribute bytes")
    return scan_code(code, cp)

def parse_class(data: bytes):
    if len(data) > MAX_ENTRY: raise AnalysisError("class file exceeds size limit")
    r = Reader(data)
    if r.u4() != MAGIC: raise AnalysisError("invalid class-file magic")
    minor, major, count = r.u2(), r.u2(), r.u2()
    if count < 1:
        raise AnalysisError("constant_pool_count must be at least one")
    cp = [None] * count; i = 1
    while i < count:
        tag = r.u1()
        if tag == 1: cp[i] = (tag, mutf8(r.take(r.u2())))
        elif tag in (3,4): cp[i] = (tag, r.take(4))
        elif tag in (5,6):
            if i + 1 >= count:
                raise AnalysisError("long/double constant is missing its reserved constant-pool slot")
            cp[i] = (tag, r.take(8))
            i += 1
        elif tag in (7,8,16,19,20): cp[i] = (tag, r.u2())
        elif tag in (9,10,11,12,17,18): cp[i] = (tag, r.u2(), r.u2())
        elif tag == 15: cp[i] = (tag, r.u1(), r.u2())
        else: raise AnalysisError(f"unsupported constant-pool tag {tag}")
        i += 1
    access, this_idx, super_idx = r.u2(), r.u2(), r.u2()
    name = class_name(cp, this_idx)
    superclass = class_name(cp, super_idx) if super_idx else None
    interfaces = [class_name(cp, r.u2()) for _ in range(r.u2())]
    field_count = r.u2()
    for _ in range(field_count):
        r.u2(); r.u2(); r.u2()
        for _ in range(r.u2()): r.u2(); r.take(r.u4())
    methods, invocations, native_methods, sensitive_calls, dynamic = [], [], [], [], 0
    for _ in range(r.u2()):
        flags, ni, di, ac = r.u2(), r.u2(), r.u2(), r.u2()
        mn, desc = utf8(cp, ni), utf8(cp, di)
        refs_here = 0
        if flags & 0x0100: native_methods.append(f"{name}.{mn}{desc}")
        for _ in range(ac):
            an = utf8(cp, r.u2()); payload = r.take(r.u4())
            if an == "Code":
                refs, dyn = parse_code(payload, cp)
                refs_here += len(refs); dynamic += dyn
                for ref in refs:
                    record = {"callerClass":name,"callerMethod":mn,"callerDescriptor":desc,**ref}
                    if len(invocations) < MAX_SAMPLES:
                        invocations.append(record)
                    if ((ref["owner"] == "java/lang/Class" and ref["name"] in
                         ("forName","getDeclaredMethod","getDeclaredField","getDeclaredConstructor")) or
                        (ref["owner"] in ("java/lang/ClassLoader","java/net/URLClassLoader") and
                         ref["name"] in ("loadClass","defineClass")) or
                        (ref["owner"] in ("java/lang/System","java/lang/Runtime") and
                         ref["name"] in ("load","loadLibrary"))):
                        sensitive_calls.append(f'{ref["owner"]}.{ref["name"]}{ref["descriptor"]}')
        methods.append({"name":mn,"descriptor":desc,"access":flags,"native":bool(flags&0x0100),
                        "abstract":bool(flags&0x0400),"invocationCount":refs_here})
    attrs = []
    for _ in range(r.u2()):
        attrs.append(utf8(cp, r.u2())); r.take(r.u4())
    if r.pos != len(data): raise AnalysisError("trailing class-file bytes")
    refs = {class_name(cp, n) for n,e in enumerate(cp) if e and e[0] == 7}
    member_count = sum(1 for e in cp if e and e[0] in (9,10,11))
    return {"name":name,"majorVersion":major,"minorVersion":minor,"access":access,
            "superclass":superclass,"interfaces":interfaces,"fieldCount":field_count,
            "methods":methods,"methodCount":len(methods),"nativeMethods":native_methods,
            "classReferences":sorted(refs),"memberReferenceCount":member_count,
            "invocations":invocations,"sensitiveCalls":sensitive_calls,
            "invocationCount":sum(m["invocationCount"] for m in methods),
            "invocationsTruncated":sum(m["invocationCount"] for m in methods)>len(invocations),
            "invokedynamicCount":dynamic,"attributes":attrs}

def class_java_version(major):
    if major == 45: return "Java 1.1"
    if 46 <= major <= 48: return f"Java {major-44}"
    if 49 <= major <= 69: return f"Java {major-44}"
    return "unknown"

def safe_path(name):
    if not name or len(name)>1024 or "\x00" in name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:",name): return False
    return all(x not in ("",".","..") for x in name.rstrip("/").split("/"))

def unfold_manifest(raw):
    lines = raw.replace("\r\n","\n").replace("\r","\n").split("\n")
    out=[]
    for line in lines:
        if line.startswith(" ") and out: out[-1]+=line[1:]
        else: out.append(line)
    result={}
    for line in out:
        if not line: break
        if ":" in line:
            k,v=line.split(":",1); result[k.strip().lower()]=v.strip()
    return result

def read_json_member(zf, name, diagnostics):
    """Read a bounded UTF-8 JSON member without extracting it to disk."""
    try:
        info=zf.getinfo(name)
        if info.file_size > MAX_JSON:
            diagnostics.append({"code":"JSON_TOO_LARGE","path":name,
                                "message":f"JSON member exceeds {MAX_JSON} byte limit"})
            return None
        raw=zf.read(info)
        if len(raw) > MAX_JSON:
            diagnostics.append({"code":"JSON_TOO_LARGE","path":name,
                                "message":f"JSON member expands beyond {MAX_JSON} byte limit"})
            return None
        return json.loads(raw.decode("utf-8"))
    except KeyError:
        diagnostics.append({"code":"MISSING_JSON_MEMBER","path":name,
                            "message":"JSON member disappeared while reading archive"})
    except (UnicodeDecodeError,json.JSONDecodeError,zipfile.BadZipFile,RuntimeError,RecursionError) as exc:
        diagnostics.append({"code":"INVALID_JSON","path":name,"message":str(exc)[:240]})
    return None

def parse_entrypoints(loader, entrypoints, diagnostics, source):
    parsed=[]
    if not isinstance(entrypoints,dict):
        diagnostics.append({"code":"INVALID_ENTRYPOINTS","path":source,
                            "message":"Entrypoints must be an object"})
        return parsed
    for key,raw_values in entrypoints.items():
        values=raw_values if isinstance(raw_values,list) else [raw_values]
        for item in values:
            if isinstance(item,str):
                adapter,value="default",item
            elif isinstance(item,dict) and isinstance(item.get("value"),str):
                adapter=item.get("adapter","default")
                value=item["value"]
                if not isinstance(adapter,str) or not adapter:
                    diagnostics.append({"code":"INVALID_ENTRYPOINT_ADAPTER","path":source,
                                        "message":f"Invalid adapter for entrypoint {key}"})
                    continue
            else:
                diagnostics.append({"code":"INVALID_ENTRYPOINT_DECLARATION","path":source,
                                    "message":f"Unsupported entrypoint declaration for {key}"})
                continue
            parsed.append({"loader":loader,"key":str(key),"adapter":adapter,
                           "value":value,"source":source})
    return parsed

def parse_metadata(zf, names, diagnostics):
    meta={"loaderCandidates":[],"descriptors":[],"mods":[],"dependencies":[],
          "entrypoints":[],"declaredMixins":[],"mixinConfigDeclarations":[],
          "nestedJars":[],"provides":[],"conflicts":[],"languageAdapters":{},
          "manifest":{}}
    if "META-INF/MANIFEST.MF" in names:
        meta["manifest"]=unfold_manifest(zf.read("META-INF/MANIFEST.MF").decode("utf-8","replace"))
    if "fabric.mod.json" in names:
        meta["descriptors"].append("fabric.mod.json"); meta["loaderCandidates"].append("fabric")
        data=read_json_member(zf,"fabric.mod.json",diagnostics)
        if isinstance(data,dict):
            meta["mods"].append({"loader":"fabric","id":data.get("id"),"version":data.get("version"),
                                 "name":data.get("name"),"environment":data.get("environment","*")})
            for key,kind in (("depends","required"),("recommends","recommended"),("suggests","suggested"),("breaks","breaks")):
                values=data.get(key,{})
                if isinstance(values,dict):
                    for dep,constraint in values.items():
                        meta["dependencies"].append({"id":dep,"constraint":constraint,"kind":kind,"source":"fabric.mod.json"})
            conflicts=data.get("conflicts",{})
            if isinstance(conflicts,dict):
                for dep,constraint in conflicts.items():
                    item={"id":dep,"constraint":constraint,"kind":"conflict","source":"fabric.mod.json"}
                    meta["conflicts"].append(item); meta["dependencies"].append(item)
            elif isinstance(conflicts,list):
                for dep in conflicts:
                    if isinstance(dep,str):
                        item={"id":dep,"constraint":None,"kind":"conflict","source":"fabric.mod.json"}
                        meta["conflicts"].append(item); meta["dependencies"].append(item)
            meta["entrypoints"].extend(parse_entrypoints("fabric",data.get("entrypoints",{}),diagnostics,"fabric.mod.json"))
            for item in data.get("mixins",[]) if isinstance(data.get("mixins",[]),list) else []:
                if isinstance(item,str):
                    declaration={"path":item,"environment":data.get("environment","*"),"source":"fabric.mod.json"}
                elif isinstance(item,dict) and isinstance(item.get("config"),str):
                    declaration={"path":item["config"],"environment":item.get("environment",data.get("environment","*")),
                                 "source":"fabric.mod.json"}
                else:
                    diagnostics.append({"code":"INVALID_MIXIN_DECLARATION","path":"fabric.mod.json",
                                        "message":"Mixin declaration must be a path or an object with config"})
                    continue
                meta["mixinConfigDeclarations"].append(declaration)
                meta["declaredMixins"].append(declaration["path"])
            jars=data.get("jars",[])
            if isinstance(jars,list):
                for item in jars:
                    if isinstance(item,dict) and isinstance(item.get("file"),str):
                        meta["nestedJars"].append({"path":item["file"],"source":"fabric.mod.json"})
                    else:
                        diagnostics.append({"code":"INVALID_NESTED_JAR_DECLARATION","path":"fabric.mod.json",
                                            "message":"Nested JAR declaration must contain a file path"})
            provides=data.get("provides",[])
            if isinstance(provides,list):
                meta["provides"]=[x for x in provides if isinstance(x,str)]
            adapters=data.get("languageAdapters",{})
            if isinstance(adapters,dict):
                meta["languageAdapters"]={k:v for k,v in adapters.items() if isinstance(k,str) and isinstance(v,str)}
            if isinstance(data.get("accessWidener"),str): meta["accessWidener"]=data["accessWidener"]
    if "quilt.mod.json" in names:
        meta["descriptors"].append("quilt.mod.json"); meta["loaderCandidates"].append("quilt")
        data=read_json_member(zf,"quilt.mod.json",diagnostics)
        if isinstance(data,dict):
            ql=data.get("quilt_loader",{}) if isinstance(data.get("quilt_loader"),dict) else {}
            md=ql.get("metadata",{}) if isinstance(ql.get("metadata"),dict) else {}
            meta["mods"].append({"loader":"quilt","id":ql.get("id"),"version":ql.get("version"),
                                 "name":md.get("name"),"environment":ql.get("environment","*")})
            deps=ql.get("depends",[])
            if isinstance(deps,list):
                for dep in deps:
                    if isinstance(dep,dict):
                        meta["dependencies"].append({"id":dep.get("id"),"constraint":dep.get("versions"),
                                                     "kind":"required","source":"quilt.mod.json"})
            meta["entrypoints"].extend(parse_entrypoints("quilt",ql.get("entrypoints",{}),diagnostics,"quilt.mod.json"))
    for toml_name in ("META-INF/neoforge.mods.toml","META-INF/mods.toml"):
        if toml_name not in names: continue
        loader="neoforge" if "neoforge" in toml_name else "forge"
        meta["descriptors"].append(toml_name); meta["loaderCandidates"].append(loader)
        if tomllib is None:
            diagnostics.append({"code":"TOML_UNAVAILABLE","path":toml_name,"message":"Python 3.11+ required"})
            continue
        try:
            data=tomllib.loads(zf.read(toml_name).decode("utf-8"))
            for mod in data.get("mods",[]):
                if isinstance(mod,dict):
                    meta["mods"].append({"loader":loader,"id":mod.get("modId"),"version":mod.get("version"),
                                         "name":mod.get("displayName"),"environment":"*"})
            deps=data.get("dependencies",{})
            if isinstance(deps,dict):
                for owner,items in deps.items():
                    for dep in items if isinstance(items,list) else []:
                        if isinstance(dep,dict):
                            meta["dependencies"].append({"id":dep.get("modId"),"constraint":dep.get("versionRange"),
                                "kind":"required" if dep.get("mandatory",True) else "optional",
                                "source":toml_name,"declaredFor":owner})
        except (UnicodeDecodeError,ValueError) as exc:
            diagnostics.append({"code":"INVALID_TOML","path":toml_name,"message":str(exc)[:240]})
    return meta

def parse_mixins(zf,names,declarations,diagnostics):
    declaration_by_path={item["path"]:item for item in declarations}
    paths=set(declaration_by_path)
    paths.update(n for n in names if re.search(r"\.mixins?\.json$",n,re.I))
    result=[]
    for path in sorted(paths):
        declaration=declaration_by_path.get(path,{})
        if path not in names:
            diagnostics.append({"code":"MISSING_MIXIN_CONFIG","path":path,"message":"Declared config missing"})
            continue
        data=read_json_member(zf,path,diagnostics)
        if not isinstance(data,dict): continue
        package=data.get("package","")
        if not isinstance(package,str):
            diagnostics.append({"code":"INVALID_MIXIN_PACKAGE","path":path,
                                "message":"Mixin package must be a string"})
            package=""
        environment=declaration.get("environment","*")
        if not isinstance(environment,str):
            diagnostics.append({"code":"INVALID_MIXIN_ENVIRONMENT","path":path,
                                "message":"Mixin environment must be a string"})
            environment="*"
        mixin_classes=[]
        for key in ("mixins","client","server"):
            values=data.get(key,[])
            if isinstance(values,list):
                mixin_classes.extend((package+"." if package else "")+v for v in values if isinstance(v,str))
        result.append({"path":path,"package":package,"environment":environment,
                       "mixinClasses":sorted(set(mixin_classes)),"targetClasses":[],
                       "targetDiscoveryStatus":"NOT_ANALYZED",
                       "plugin":data.get("plugin"),"refmap":data.get("refmap"),
                       "compatibilityLevel":data.get("compatibilityLevel"),"required":data.get("required")})
    return result

def make_signals(class_refs,invocations,metadata,native_methods,sensitive_calls):
    refs=set(class_refs); refs.update(x["owner"] for x in invocations)
    signals=[]; flags=[]
    def sig(code,desc,ev):
        if ev: signals.append({"id":code,"description":desc,"evidence":sorted(ev)[:30],
                               "mappingStatus":"unknown","verification":"NOT_RUN"})
    def flag(code,sev,desc,ev):
        if ev: flags.append({"id":code,"severity":sev,"description":desc,"evidence":sorted(set(ev))[:30]})
    sig("minecraft-api-reference","Minecraft classes appear in bytecode symbols; behavior is not inferred.",
        [x for x in refs if x.startswith("net/minecraft/")])
    sig("fabric-api-reference","Fabric API or loader symbols appear in bytecode.",
        [x for x in refs if x.startswith("net/fabricmc/")])
    sig("quilt-api-reference","Quilt symbols appear in bytecode.",[x for x in refs if x.startswith("org/quiltmc/")])
    sig("forge-api-reference","Forge or NeoForge symbols appear in bytecode.",
        [x for x in refs if x.startswith(("net/minecraftforge/","net/neoforged/"))])
    sig("rendering-reference","Likely rendering/GUI namespaces appear in bytecode.",
        [x for x in refs if any(k in x for k in ("net/minecraft/client/render","net/minecraft/client/renderer",
           "net/minecraft/client/gui","net/fabricmc/fabric/api/client/rendering"))])
    sig("networking-reference","Likely networking namespaces appear in bytecode.",
        [x for x in refs if any(k in x for k in ("net/minecraft/network","net/fabricmc/fabric/api/networking",
           "net/neoforged/neoforge/network"))])
    sig("entity-world-reference","Entity/world namespaces appear in bytecode.",
        [x for x in refs if any(k in x for k in ("net/minecraft/world/entity","net/minecraft/entity",
           "net/minecraft/world/level","net/minecraft/world/World"))])
    mixin_refs=[x for x in refs if "org/spongepowered/asm/mixin" in x]
    if metadata.get("declaredMixins") or mixin_refs:
        flag("MIXIN","high","Mixin config or API references detected; injection points need review.",
             mixin_refs+metadata.get("declaredMixins",[]))
    plugin_configs=metadata.get("mixinPlugins",[])
    if plugin_configs:
        flag("MIXIN_CONFIG_PLUGIN_DYNAMIC","high",
             "Mixin config plugin can change the applied mixin set at runtime; plugin was not executed.",
             plugin_configs)
    reflection=[x for x in refs if x.startswith(("java/lang/reflect/","java/lang/invoke/"))]
    reflection += [x for x in sensitive_calls if ".forName" in x or ".getDeclared" in x]
    if reflection: flag("REFLECTION_OR_METHOD_HANDLES","high","Reflection or method-handle symbols detected.",reflection)
    dynamic=[x for x in refs if x in ("java/lang/ClassLoader","java/net/URLClassLoader","java/lang/instrument/Instrumentation")]
    dynamic += [x for x in sensitive_calls if ".loadClass" in x or ".defineClass" in x or ".loadLibrary" in x or ".load(" in x]
    if dynamic: flag("DYNAMIC_LOADING_OR_INSTRUMENTATION","high","Dynamic loading/instrumentation/native loading symbols detected.",dynamic)
    if native_methods: flag("NATIVE_METHODS","high","Native method declarations need platform-specific handling.",native_methods)
    return signals,flags

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def analyze_jar(path):
    path=Path(path)
    if not path.is_file(): raise AnalysisError("input is not a regular file")
    size=path.stat().st_size
    if size>MAX_ARCHIVE: raise AnalysisError("archive exceeds 128 MiB compressed-size limit")
    digest=sha256_file(path)
    diagnostics=[]; classes=[]; class_refs=set(); invocations=[]; native_methods=[]; sensitive_calls=[]
    totals=Counter(); majors=Counter(); resources=Counter(); resource_inventory=[]
    native_libs=[]; providers=[]; access_files=[]; licenses=[]; names=set()
    try:
        with zipfile.ZipFile(path,"r") as zf:
            infos=zf.infolist()
            if len(infos)>MAX_ENTRIES: raise AnalysisError("more than 20,000 archive entries")
            seen=set(); total=0
            for info in infos:
                name=info.filename
                if not safe_path(name): raise AnalysisError("unsafe archive path: "+name[:160])
                if info.is_dir(): continue
                key=name.casefold()
                if key in seen: raise AnalysisError("duplicate archive path: "+name)
                seen.add(key)
                mode=(info.external_attr>>16)&0xffff
                if stat.S_ISLNK(mode): raise AnalysisError("symbolic link rejected: "+name)
                if info.flag_bits&1: raise AnalysisError("encrypted entry rejected: "+name)
                if info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
                    raise AnalysisError("unsupported compression method: "+name)
                if info.file_size>MAX_ENTRY: raise AnalysisError("entry exceeds 16 MiB: "+name)
                total+=info.file_size
                if total>MAX_TOTAL: raise AnalysisError("archive exceeds 256 MiB uncompressed")
                if info.file_size>1024 and info.file_size/max(info.compress_size,1)>MAX_RATIO:
                    raise AnalysisError("excessive compression ratio: "+name)
                names.add(name); lower=name.lower()
                if lower.endswith(".class"):
                    totals["classEntries"]+=1
                    if totals["classEntries"]>MAX_CLASSES: raise AnalysisError("more than 12,000 class entries")
                    try:
                        item=parse_class(zf.read(info)); item["path"]=name
                        m=re.match(r"META-INF/versions/(\d+)/(.+\.class)$",name)
                        item["multiReleaseVersion"]=int(m.group(1)) if m else None
                        classes.append(item); class_refs.update(item["classReferences"])
                        totals["methods"]+=item["methodCount"]
                        totals["invocations"]+=item["invocationCount"]
                        totals["invokedynamic"]+=item["invokedynamicCount"]
                        majors[item["majorVersion"]]+=1; native_methods.extend(item["nativeMethods"])
                        sensitive_calls.extend(item["sensitiveCalls"])
                        for ref in item["invocations"]:
                            if len(invocations)<MAX_SAMPLES: invocations.append(ref)
                    except (AnalysisError,zipfile.BadZipFile) as exc:
                        diagnostics.append({"code":"CLASS_PARSE_FAILED","path":name,"message":str(exc)[:240]})
                elif name.startswith("META-INF/services/"):
                    try:
                        txt=zf.read(info).decode("utf-8","replace")
                        for line in txt.splitlines():
                            value=line.split("#",1)[0].strip()
                            if value: providers.append({"service":name[len("META-INF/services/"):],"provider":value})
                    except (zipfile.BadZipFile,RuntimeError) as exc:
                        diagnostics.append({"code":"SERVICE_READ_FAILED","path":name,"message":str(exc)[:240]})
                elif lower.endswith((".dll",".so",".dylib")) or re.search(r"\.so\.\d",lower): native_libs.append(name)
                elif "accesswidener" in lower or "accesstransformer" in lower or lower.endswith(".at"):
                    access_files.append(name)
                elif re.search(r"(^|/)(license|licence|copying|notice)(\.[^/]*)?$",lower): licenses.append(name)
                elif lower.endswith((".png",".ogg",".json",".mcmeta",".properties",".lang",".obj")):
                    resources[Path(name).suffix.lower() or "(none)"]+=1
                    category = "other"
                    if "/textures/" in lower: category = "texture"
                    elif "/models/" in lower: category = "model"
                    elif "/recipes/" in lower or "/recipe/" in lower: category = "recipe"
                    elif "/tags/" in lower: category = "tag"
                    elif "/loot_tables/" in lower or "/loot_table/" in lower: category = "loot_table"
                    elif lower.endswith((".ogg",)): category = "sound"
                    elif lower.endswith((".properties",".lang")): category = "localization"
                    resource_inventory.append({"path":name,"category":category})
            metadata=parse_metadata(zf,names,diagnostics)
            mixins=parse_mixins(zf,names,metadata["mixinConfigDeclarations"],diagnostics)
            metadata["mixinPlugins"]=[item["path"] for item in mixins if item.get("plugin")]
            if mixins:
                metadata["declaredMixins"] = sorted(set(metadata["declaredMixins"]) | {item["path"] for item in mixins})
            if metadata.get("accessWidener"): access_files.append(metadata["accessWidener"])
    except zipfile.BadZipFile as exc:
        raise AnalysisError("invalid ZIP/JAR: "+str(exc)) from exc
    except (OSError,RuntimeError) as exc:
        raise AnalysisError("cannot read archive: "+str(exc)) from exc

    signals,flags=make_signals(class_refs,invocations,metadata,native_methods,sensitive_calls)
    if native_libs: flags.append({"id":"NATIVE_LIBRARIES","severity":"high",
        "description":"Native libraries are bundled; platform loading and ABI need review.","evidence":sorted(native_libs)[:30]})
    if totals["invokedynamic"]: flags.append({"id":"INVOKEDYNAMIC","severity":"medium",
        "description":"invokedynamic instructions observed; bootstrap semantics are not resolved.",
        "evidence":[f'{totals["invokedynamic"]} instruction(s)']})
    if any(x.startswith("META-INF/versions/") for x in names):
        flags.append({"id":"MULTI_RELEASE_JAR","severity":"medium",
            "description":"Multi-release class variants found; all variants are listed without selecting a JVM view.",
            "evidence":["META-INF/versions/"]})
    if access_files: flags.append({"id":"ACCESS_TRANSFORMERS","severity":"medium",
        "description":"Access widener/transformer files found; target access rules need mapping.",
        "evidence":sorted(set(access_files))[:30]})
    parse_failures=[x["path"] for x in diagnostics if x["code"]=="CLASS_PARSE_FAILED"]
    if parse_failures: flags.append({"id":"PARTIAL_BYTECODE_ANALYSIS","severity":"high",
        "description":"Some class files could not be parsed; reference inventory is incomplete.",
        "evidence":parse_failures[:30]})
    if not metadata["descriptors"]: flags.append({"id":"NO_RECOGNIZED_MOD_DESCRIPTOR","severity":"medium",
        "description":"No Fabric/Quilt/Forge/NeoForge descriptor found; may be a library or legacy package.","evidence":[]})
    loaders=sorted(set(metadata["loaderCandidates"]))
    if len(loaders)>1: diagnostics.append({"code":"MULTIPLE_LOADER_DESCRIPTORS","path":"",
        "message":"Multiple loader descriptors found; multi-loader packaging needs manual review."})
    report={
      "schemaVersion":"0.2",
      "analyzer":{"name":"Mod Analyzer","version":VERSION,"mode":"read-only-static","executesInputCode":False},
      "input":{"fileName":path.name,"sizeBytes":size,"sha256":digest},
      "metadata":metadata,
      "summary":{"archiveEntries":len(names),"classEntries":totals["classEntries"],
        "uniqueLogicalClasses":len({x["name"] for x in classes}),"methods":totals["methods"],
        "methodInvocationInstructions":totals["invocations"],"invokedynamicInstructions":totals["invokedynamic"],
        "nativeMethods":len(native_methods),"resourceCountsByExtension":dict(sorted(resources.items())),
        "nativeLibraries":len(native_libs),"classMajorVersions":{str(k):v for k,v in sorted(majors.items())}},
      "bytecode":{"classes":[{"path":x["path"],"name":x["name"],"majorVersion":x["majorVersion"],
        "javaVersion":class_java_version(x["majorVersion"]),"superclass":x["superclass"],
        "interfaces":x["interfaces"],"fieldCount":x["fieldCount"],"methodCount":x["methodCount"],
        "nativeMethodCount":len(x["nativeMethods"]),"invocationCount":x["invocationCount"],
        "invokedynamicCount":x["invokedynamicCount"],"multiReleaseVersion":x["multiReleaseVersion"]}
        for x in sorted(classes,key=lambda y:y["path"])],
        "classReferenceInventory":sorted(class_refs)[:MAX_SAMPLES],"classReferenceCount":len(class_refs),
        "methodInvocationSamples":invocations,"methodInvocationSamplesTruncated":totals["invocations"]>len(invocations)},
      "resources":{"count":sum(resources.values()),"inventory":sorted(resource_inventory,key=lambda x:x["path"])[:MAX_SAMPLES],
        "inventoryTruncated":len(resource_inventory)>MAX_SAMPLES},
      "mixins":mixins,"serviceProviders":providers[:MAX_SAMPLES],"nativeLibraries":sorted(native_libs),
      "licenseFiles":sorted(licenses),"signals":signals,
      "riskFlags":sorted(flags,key=lambda x:({"high":0,"medium":1,"low":2}.get(x["severity"],3),x["id"])),
      "diagnostics":diagnostics,
      "migrationAssessment":{"targetProfile":None,"overallStatus":"UNASSESSED","featureMappings":[],
        "note":"Static symbol evidence is not proof of runtime behavior or target API compatibility. No compatibility percentage is calculated."},
      "limitations":[
        "The JAR is never extracted, loaded, or executed.",
        "Reflection, invokedynamic bootstrap behavior, generated code, and runtime-loaded classes may remain unresolved.",
        "Resource presence does not prove registration or runtime use.",
        "Declared dependencies are not proof that dependency JARs are present or compatible.",
        "Signals and risk flags are triage evidence, not semantic-equivalence judgments.",
        "No Horizon SDK, game runtime, or behavior-equivalence test is run."
      ]}
    return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jar",type=Path,help="local Java mod JAR (read-only)")
    parser.add_argument("-o","--output",type=Path,help="JSON report path; stdout by default")
    args=parser.parse_args(argv)
    try: report=analyze_jar(args.jar)
    except (AnalysisError,OSError) as exc:
        print(json.dumps({"status":"REJECTED","error":str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2
    payload=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if args.output: args.output.write_text(payload,encoding="utf-8")
    else: sys.stdout.write(payload)
    return 0

if __name__=="__main__": raise SystemExit(main())
