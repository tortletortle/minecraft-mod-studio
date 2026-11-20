"""Evidence-linked recipe hypotheses, not an autonomous LLM or recipe executor."""
from datetime import datetime
from mod_knowledge import identifier

MAX_MATCHES=32
MAX_REFS=512

def _inventory(reg,key):
    values=reg.get(key)
    total=reg.get(key+"_total")
    if not isinstance(values,list) or len(values)>20000 or type(total) is not int or total<len(values):
        raise ValueError("invalid registry inventory")
    if any(not isinstance(v,str) or identifier(v)!=v for v in values) or len(set(values))!=len(values):
        raise ValueError("invalid registry identifiers")
    return set(values),total==len(values)

def diagnose_recipe(knowledge,snapshot,recipe):
    """Join static declarations to one probe receipt; no writes or causal claims."""
    if not isinstance(recipe,str) or identifier(recipe)!=recipe:
        raise ValueError("canonical namespaced recipe id required")
    if not isinstance(knowledge,dict) or knowledge.get("schema")!=1 or not isinstance(snapshot,dict) or snapshot.get("schema")!=1:
        raise ValueError("unsupported evidence schema")
    reg=snapshot.get("registrations")
    if not isinstance(reg,dict):raise ValueError("registrations unavailable")
    items,complete=_inventory(reg,"items")
    at=snapshot.get("at")
    if not isinstance(at,str) or datetime.fromisoformat(at.replace("Z","+00:00")).tzinfo is None:
        raise ValueError("invalid probe timestamp")
    mods=reg.get("mods")
    if not isinstance(mods,list) or len(mods)>20000 or any(not isinstance(m,dict) or not isinstance(m.get("id"),str) or not isinstance(m.get("version"),str) for m in mods):
        raise ValueError("invalid runtime mod list")
    mod_total=reg.get("mods_total")
    if type(mod_total) is not int or mod_total<len(mods):
        raise ValueError("invalid runtime mod count")
    loaded={}
    for m in mods:
        if m["id"] in loaded:raise ValueError("duplicate runtime mod id")
        loaded[m["id"]]=m["version"]
    resources=knowledge["resources"]
    matches=[(i,row) for i,row in enumerate(resources) if row["kind"]=="recipe" and row["id"]==recipe]
    if len(matches)>MAX_MATCHES:raise ValueError("too many recipe declarations")
    by_source={i:[] for i,_ in matches}
    for e in knowledge["edges"]:
        if e["source"] in by_source:
            if len(by_source[e["source"]])>=MAX_REFS:raise ValueError("too many recipe references")
            by_source[e["source"]].append(e)
    archives={a["jar"]:a for a in knowledge["archives"]}
    declarations=[];hypotheses=[]
    def suggest(kind,source,observation,verification):
        hypotheses.append({"kind":kind,"source":source,"status":"unverified","observation":observation,"verification":verification})
    for i,row in matches:
        a=archives[row["jar"]]
        mid=a.get("mod_id")
        version=a.get("version")
        if not mid or not isinstance(version,str):alignment="unknown"
        elif mid in loaded:alignment="id_version_match" if loaded[mid]==version else "version_mismatch"
        else:alignment="id_not_listed" if mod_total==len(mods) else "unknown_truncated_mod_list"
        src={"jar":row["jar"],"path":row["path"],"sha256":a.get("sha256"),"mod_id":mid,"version":version,
             "runtime_alignment":alignment}
        references=[]
        if alignment in ("version_mismatch","id_not_listed"):
            suggest("workspace_runtime_mismatch",src,alignment,
                    ["compare_active_instance_manifest","verify_loaded_jar_hashes"])
        if not row.get("recognized"):
            suggest("unsupported_serializer",src,row.get("serializer"),["inspect_recipe_serializer","query_active_recipe"])
        for e in by_source[i]:
            ref={"relation":e["relation"],"kind":e["target_kind"],"id":e["target"]}
            if e["target_kind"]=="item":
                status="present" if e["target"] in items else "absent_from_complete_snapshot" if complete else "unknown_truncated_registry"
                ref["status"]=status
                if status=="absent_from_complete_snapshot":
                    suggest("unregistered_item_reference",src,ref,
                            ["verify_loaded_jar_hashes","query_active_recipe","test_recipe_in_disposable_instance"])
            else:
                ref["status"]="runtime_tag_membership_unknown"
                suggest("tag_resolution_unknown",src,ref,["query_active_tag_members","test_recipe_in_disposable_instance"])
            references.append(ref)
        declarations.append({"source":src,"serializer":row.get("serializer"),"recognized":bool(row.get("recognized")),"references":references})
    if len(matches)>1:
        suggest("multiple_recipe_declarations",None,{"count":len(matches)},["inspect_datapack_order","query_active_recipe"])
    if not matches:
        suggest("no_indexed_declaration",None,{"recipe":recipe},["inspect_active_datapacks","query_active_recipe"])
    return {"schema":1,"recipe":recipe,"session":snapshot.get("session"),"snapshot_at":at,
            "registry_complete":complete,"declarations":declarations,"hypotheses":hypotheses,
            "status":"hypotheses_only",
            "plan":{"implemented_read_only":[{"tool":"game.native_snapshot","arguments":{"session":snapshot.get("session")}}],
                    "required_capabilities_not_implemented":["verify_loaded_jar_hashes","query_active_recipe","query_active_tag_members","inspect_datapack_order","test_recipe_in_disposable_instance"],
                    "approval_required_for_world_mutation":True},
            "limitations":["ID/version alignment is not proof the scanned JAR is loaded; its hash is static evidence only.",
                           "Snapshot may be stale; registry completeness refers to listed items, not recipes or tags.",
                           "Recipe references may be alternatives; absent items do not establish an invalid recipe.",
                           "Conditional loading, overrides, custom serializers and runtime recipe execution are not resolved.",
                           "Hypotheses are rule-generated, unranked and unverified; no automatic execution."]}
