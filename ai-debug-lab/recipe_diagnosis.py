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
    # Only join evidence from this exact snapshot and configured target.
    probe=snapshot.get("recipe_probe")
    probe=probe if isinstance(probe,dict) else {}
    active=probe.get("recipe")
    active=active if isinstance(active,dict) and active.get("id")==recipe and active.get("status") in ("present","not_found") else None
    tag=probe.get("item_tag")
    tag=tag if isinstance(tag,dict) and isinstance(tag.get("id"),str) and identifier(tag["id"])==tag["id"] and tag.get("status") in ("present","not_found") else None
    if tag and tag["status"]=="present":
        members=tag.get("members");total=tag.get("total")
        if (not isinstance(members,list) or len(members)>4096 or any(not isinstance(x,str) or identifier(x)!=x for x in members)
            or len(set(members))!=len(members) or type(total) is not int or total<len(members)
            or type(tag.get("complete")) is not bool or tag["complete"]!=(total==len(members))):
            tag=None
    exp=active.get("experiment") if active and active["status"]=="present" else None
    if not isinstance(exp,dict) or exp.get("scope")!="in_memory_exact_recipe_only" or exp.get("status") not in ("matched","not_matched","unsupported_implementation"):
        exp=None
    elif (not isinstance(exp.get("inputs"),list) or not 1<=len(exp["inputs"])<=3 or
          any(not isinstance(x,str) or identifier(x)!=x for x in exp["inputs"])):
        exp=None
    elif exp["status"]=="matched" and (not isinstance(exp.get("output"),str) or identifier(exp["output"])!=exp["output"] or type(exp.get("count")) is not int or exp["count"]<1):
        exp=None
    declarations=[];hypotheses=[];needed_tags=set()
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
                needed_tags.add(e["target"])
                if tag is not None and tag["id"]==e["target"]:
                    ref["status"]="runtime_tag_not_found" if tag["status"]=="not_found" else ("runtime_tag_members_available" if tag["complete"] else "runtime_tag_members_truncated")
                    ref["runtime_tag"]=tag
                    if tag["status"]=="not_found":
                        suggest("runtime_tag_not_found",src,ref,["inspect_datapack_order","test_recipe_in_disposable_instance"])
                    elif tag["complete"] and not tag["members"]:
                        suggest("runtime_tag_empty",src,ref,["inspect_datapack_order","test_recipe_in_disposable_instance"])
                else:
                    ref["status"]="runtime_tag_membership_unknown"
                    suggest("tag_resolution_unknown",src,ref,["query_active_tag_members","test_recipe_in_disposable_instance"])
            references.append(ref)
        declarations.append({"source":src,"serializer":row.get("serializer"),"recognized":bool(row.get("recognized")),"references":references})
    if len(matches)>1:
        suggest("multiple_recipe_declarations",None,{"count":len(matches)},["inspect_datapack_order","query_active_recipe"])
    if not matches:
        suggest("no_indexed_declaration",None,{"recipe":recipe},["inspect_active_datapacks","query_active_recipe"])
    if active and active["status"]=="not_found":
        suggest("active_recipe_not_found",None,{"id":recipe},["inspect_datapack_order","inspect_active_datapacks"])
    # Expose actual coverage separately from still-missing general capabilities.
    covered=[]
    if active:covered.append("query_active_recipe")
    if tag and tag["id"] in needed_tags and (tag["status"]=="not_found" or tag.get("complete")):
        if needed_tags=={tag["id"]}:covered.append("query_active_tag_members")
    read_tools=[{"tool":"game.native_snapshot","arguments":{"session":snapshot.get("session")}}]
    if active or tag:read_tools.append({"tool":"game.recipe_status","arguments":{"session":snapshot.get("session")}})
    for h in hypotheses:
        h["verification"]=[v for v in h["verification"] if v not in covered]
    remaining=["verify_loaded_jar_hashes","inspect_datapack_order","test_recipe_in_disposable_instance"]
    remaining.extend(v for v in ("query_active_recipe","query_active_tag_members") if v not in covered)
    return {"schema":1,"recipe":recipe,"session":snapshot.get("session"),"snapshot_at":at,
            "registry_complete":complete,"declarations":declarations,"hypotheses":hypotheses,
            "status":"hypotheses_only",
            "runtime_recipe":active,"runtime_item_tag":tag if tag and tag["id"] in needed_tags else None,
            "in_memory_experiment":exp,
            "plan":{"implemented_read_only":read_tools,"covered_by_configured_snapshot":covered,
                    "required_capabilities_not_implemented":remaining,
                    "in_memory_check_status":exp["status"] if exp else "not_observed",
                    "scope":"only configured recipe/tag and exact memory inputs; no general live lookup or player transaction",
                    "approval_required_for_world_mutation":True},
            "limitations":["ID/version alignment is not proof the scanned JAR is loaded; its hash is static evidence only.",
                           "Snapshot may be stale; registry completeness refers to listed items, not recipes or tags.",
                           "Recipe references may be alternatives; absent items do not establish an invalid recipe.",
                           "Conditional loading, overrides and custom serializers are not resolved; exact in-memory check does not prove player crafting.",
                           "Hypotheses are rule-generated, unranked and unverified; no automatic execution."]}
