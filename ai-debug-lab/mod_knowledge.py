"""Bounded static Minecraft resource evidence; never loads a JAR's Java code."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

RID=re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")
RESOURCE=re.compile(r"data/([a-z0-9_.-]+)/(recipe|recipes|tags/item|tags/items)/([a-z0-9_./-]+)\.json")
MAX_JARS=300
MAX_ARCHIVE=512*1024*1024
MAX_ENTRIES=100000
MAX_JSON=256*1024
MAX_RESOURCES=30000
MAX_EDGES=100000

def identifier(value):
    if not isinstance(value,str) or len(value)>256:return None
    value=value if ":" in value else "minecraft:"+value
    return value if RID.fullmatch(value) and not any(x in ("",".","..") for x in value.split(":",1)[1].split("/")) else None

def read_json(z,info):
    if info.file_size>MAX_JSON:raise ValueError("oversized JSON")
    with z.open(info) as f:
        raw=f.read(MAX_JSON+1)
    if len(raw)>MAX_JSON:raise ValueError("oversized JSON")
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError("duplicate JSON key")
            out[k]=v
        return out
    result=json.loads(raw,object_pairs_hook=pairs)
    if not isinstance(result,dict):raise ValueError("expected object")
    return result

def ingredients(value):
    """Recognize vanilla common ingredient forms; no recursive arbitrary JSON."""
    if isinstance(value,list):
        if len(value)>256:raise ValueError("ingredient alternatives limit")
        for v in value:
            if not isinstance(v,list):yield from ingredients(v)
    elif isinstance(value,str):
        rid=identifier(value[1:] if value.startswith("#") else value)
        if rid:yield ("tag" if value.startswith("#") else "item",rid)
    elif isinstance(value,dict):
        for k in ("item","tag"):
            if k in value:
                rid=identifier(value[k])
                if rid:yield k,rid

def recipe_refs(data):
    typ=identifier(data.get("type"))
    supported={"minecraft:crafting_shaped","minecraft:crafting_shapeless","minecraft:smelting",
               "minecraft:blasting","minecraft:smoking","minecraft:campfire_cooking",
               "minecraft:stonecutting","minecraft:smithing_transform"}
    if typ not in supported:return typ,[],False
    refs=[]
    for key in ("ingredient","ingredients","template","base","addition"):
        if key in data:
            refs.extend(("requires",kind,rid) for kind,rid in ingredients(data[key]))
    keys=data.get("key")
    if isinstance(keys,dict):
        if len(keys)>256:raise ValueError("recipe key limit")
        for v in keys.values():refs.extend(("requires",kind,rid) for kind,rid in ingredients(v))
    result=data.get("result")
    if isinstance(result,dict):result=result.get("id",result.get("item"))
    rid=identifier(result)
    if rid:refs.append(("produces","item",rid))
    return typ,sorted(set(refs)),bool(rid)

def index(workspace):
    folder=Path(workspace)
    if not folder.is_dir() or folder.is_symlink():raise ValueError("expected regular mods directory")
    jars=sorted(folder.glob("*.jar"))
    if len(jars)>MAX_JARS:raise ValueError("JAR count budget exceeded")
    archives=[];resources=[];edges=[];issues=[];seen={}
    def issue(file,kind,path=None):
        if len(issues)<10000:issues.append({"jar":file,"kind":kind,"path":path})
    for path in jars:
        row={"jar":path.name,"status":"unreadable"}
        archives.append(row)
        staged=[]
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_ARCHIVE:
                raise ValueError("unsupported JAR")
            with path.open("rb") as f:row["sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
            with zipfile.ZipFile(path) as z:
                infos=z.infolist()
                if len(infos)>MAX_ENTRIES:raise ValueError("entry count exceeded")
                matches={}
                for info in infos:
                    name=info.filename
                    if name=="fabric.mod.json" or RESOURCE.fullmatch(name):
                        matches.setdefault(name,[]).append(info)
                if "fabric.mod.json" in matches:
                    if len(matches["fabric.mod.json"])!=1:raise ValueError("duplicate manifest")
                    meta=read_json(z,matches["fabric.mod.json"][0])
                    mid=meta.get("id")
                    if not isinstance(mid,str) or len(mid)>128:raise ValueError("invalid mod id")
                    row.update(mod_id=mid,version=meta.get("version"),depends=meta.get("depends",{}))
                row["status"]="indexed"
                for name,group in sorted(matches.items()):
                    m=RESOURCE.fullmatch(name)
                    if not m:continue
                    if len(resources)+len(staged)>=MAX_RESOURCES:
                        raise ValueError("resource budget exceeded")
                    namespace,category,tail=m.groups()
                    rid=identifier(namespace+":"+tail)
                    if not rid or len(group)!=1:
                        issue(path.name,"invalid_or_duplicate_path",name);continue
                    try:
                        data=read_json(z,group[0])
                        kind="tag" if category.startswith("tags/") else "recipe"
                        record={"jar":path.name,"mod_id":row.get("mod_id"),"path":name,"kind":kind,"id":rid}
                        refs=[]
                        if kind=="recipe":
                            typ,refs,recognized=recipe_refs(data)
                            record.update(serializer=typ,recognized=recognized)
                        else:
                            values=data.get("values")
                            if not isinstance(values,list) or len(values)>4096:raise ValueError("invalid tag values")
                            for v in values:
                                value=v.get("id") if isinstance(v,dict) else v
                                if not isinstance(value,str):continue
                                ident=identifier(value[1:] if value.startswith("#") else value)
                                if ident:refs.append(("declares_member","tag" if value.startswith("#") else "item",ident))
                            record["replace"]=data.get("replace",False) is True
                        staged.append((record,sorted(set(refs))))
                    except (ValueError,RuntimeError,RecursionError,zipfile.BadZipFile,NotImplementedError):
                        issue(path.name,"resource_unreadable",name)
            count=sum(len(refs) for _,refs in staged)
            if len(edges)+count>MAX_EDGES:raise ValueError("edge budget exceeded")
            for record,refs in staged:
                node=len(resources);resources.append(record)
                seen.setdefault((record["kind"],record["id"]),[]).append(node)
                for relation,target_kind,target in refs:
                    edges.append({"source":node,"relation":relation,"target_kind":target_kind,"target":target})
        except (OSError,ValueError,RuntimeError,RecursionError,zipfile.BadZipFile,NotImplementedError):
            row["status"]="unreadable"
            issue(path.name,"archive_unreadable_or_budget")
    collisions=[{"kind":k,"id":rid,"sources":nodes,
                 "interpretation":"multiple declarations; tags may intentionally merge; load precedence unknown"}
                for (k,rid),nodes in sorted(seen.items()) if len(nodes)>1]
    # Shared references are candidate interaction surfaces, not proof of a connection or conflict.
    shared={}
    for e in edges:
        key=(e["target_kind"],e["target"])
        shared.setdefault(key,set()).add(resources[e["source"]]["jar"])
    surfaces=[{"kind":k,"id":rid,"jars":sorted(sources)} for (k,rid),sources in sorted(shared.items()) if len(sources)>1]
    return {"schema":1,"archives":archives,"resources":resources,"edges":edges,"multiple_declarations":collisions,
            "shared_references":surfaces,"issues":issues,
            "limitations":["Static declarations, not actual loaded resource precedence or registry resolution.",
                           "Recognized vanilla recipe forms and item tags only; custom serializers and executable behavior unknown.",
                           "Nested JARs, Forge metadata, datapack overrides, optional tag semantics and dependency resolution not evaluated.",
                           "Shared references and duplicate paths do not prove conflict.",
                           "Resource and issue budgets may omit data; inspect archive status."]}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("mods",type=Path)
    a=p.parse_args();print(json.dumps(index(a.mods),ensure_ascii=True,indent=2))
if __name__=="__main__":main()
