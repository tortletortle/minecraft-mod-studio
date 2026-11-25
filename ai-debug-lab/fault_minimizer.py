"""Dependency-aware, conservative failure minimization. No game mutation here.

A trusted launcher supplies an oracle that creates an isolated trial, verifies
the immutable test predicate and returns a structured observation. This module
never loads mods or executes code provided by an agent.
"""
import re
import uuid

ID=re.compile(r"[a-z][a-z0-9_.-]{0,127}")
MAX_COMPONENTS=300

class BudgetExhausted(Exception): pass

class Model:
    def __init__(self, dependencies, pinned=()):
        if not isinstance(dependencies,dict) or len(dependencies)>MAX_COMPONENTS:
            raise ValueError("invalid dependency graph")
        if any(not isinstance(k,str) or not ID.fullmatch(k) for k in dependencies):
            raise ValueError("invalid component ID")
        self.all=frozenset(dependencies)
        self.deps={}
        for k,ds in dependencies.items():
            if not isinstance(ds,list) or any(not isinstance(d,str) or d not in self.all for d in ds):
                raise ValueError("required dependency missing or invalid: "+k)
            self.deps[k]=frozenset(ds)
        if not isinstance(pinned,(tuple,list)) or any(not isinstance(k,str) or k not in self.all for k in pinned):
            raise ValueError("invalid pinned component")
        self.pinned=self.closure(pinned)
    def closure(self,items):
        result=set(items)
        while True:
            expanded=result|{d for k in result for d in self.deps[k]}
            if expanded==result:return frozenset(result)
            result=expanded
    def remove(self,config,items):
        """Remove requested components AND any remaining reverse dependents."""
        left=set(config)-set(items)
        while True:
            valid={k for k in left if self.deps[k]<=left}
            if valid==left:break
            left=valid
        if not self.pinned<=left:return None
        return frozenset(left)

def minimize(dependencies,pinned,oracle,*,fingerprint,seeds=(42,173,271),repeats=2,budget=300):
    """Search for a dependency-removal-minimal candidate, not global minimum.

    oracle(tuple_of_sorted_ids, seed, repeat_index, trial_id) returns:
      {"trial_id": same, "outcome": "observed"|"absent"|"invalid",
       "fingerprint": exact target string or None, "evidence_id": nonempty str}
    Oracle owns launch/reset, target assertion, and evidence persistence.
    An unrelated observed fingerprint is unresolved, never the target failure.
    """
    model=Model(dependencies,pinned)
    if not isinstance(fingerprint,str) or not fingerprint or len(fingerprint)>512:
        raise ValueError("invalid target fingerprint")
    if not isinstance(seeds,(tuple,list)) or not 2<=len(seeds)<=8 or any(type(s) is not int or not -(2**63)<=s<2**63 for s in seeds) or len(set(seeds))!=len(seeds):
        raise ValueError("require 2-8 distinct signed 64-bit seeds")
    if type(repeats) is not int or not 2<=repeats<=5 or type(budget) is not int or not 1<=budget<=10000:
        raise ValueError("invalid repeat or budget")
    schedule=[(seed,i) for seed in seeds for i in range(repeats)]
    evidence=[]
    assessments=[]
    cache={}
    run_id=uuid.uuid4().hex
    ids=set()
    current=model.all
    status="inconclusive"
    reason="not_started"
    final_checks=[]
    def check(config,phase,*,fresh=False):
        if config is None:return "constraint_blocked"
        if not fresh and config in cache:return cache[config]
        if len(evidence)+len(schedule)>budget:raise BudgetExhausted
        labels=[]
        for seed,repeat in schedule:
            trial_id=run_id+"-"+str(len(evidence)+1)
            request={"trial_id":trial_id,"config":sorted(config),"seed":seed,"repeat":repeat,"phase":phase}
            try:
                row=oracle(tuple(request["config"]),seed,repeat,trial_id)
                if not isinstance(row,dict) or set(row)!={"trial_id","outcome","fingerprint","evidence_id"}:
                    raise ValueError("malformed trial receipt")
                if row["trial_id"]!=trial_id or not isinstance(row["evidence_id"],str) or not row["evidence_id"] or len(row["evidence_id"])>512 or row["evidence_id"] in ids:
                    raise ValueError("stale or duplicate trial receipt")
                outcome=row["outcome"]
                actual=row["fingerprint"]
                if outcome not in ("observed","absent","invalid") or (actual is not None and (not isinstance(actual,str) or len(actual)>512)):
                    raise ValueError("malformed trial outcome")
                ids.add(row["evidence_id"])
                label=("target" if outcome=="observed" and actual==fingerprint else
                       "absent" if outcome=="absent" and actual is None else "unresolved")
                request.update(receipt=row,classification=label)
            except Exception as exc:
                label="unresolved"
                request.update(error_type=type(exc).__name__,classification=label)
            evidence.append(request)
            labels.append(label)
        result=("reproduced" if all(x=="target" for x in labels) else
                "not_observed" if all(x=="absent" for x in labels) else
                "unresolved" if "unresolved" in labels else "intermittent")
        assessments.append({"config":sorted(config),"phase":phase,"result":result,
                            "target":labels.count("target"),"absent":labels.count("absent"),"unresolved":labels.count("unresolved")})
        if not fresh:cache[config]=result
        return result
    try:
        baseline=check(model.all,"baseline")
        if baseline!="reproduced":
            reason="baseline_"+baseline
        elif current==model.pinned:
            reason="no_removable_components"
        elif check(model.pinned,"negative_control")!="not_observed":
            reason="negative_control_not_clean"
        else:
            n=2
            while True:
                items=sorted(current-model.pinned)
                if not items:break
                n=min(n,len(items))
                chunks=[items[i*len(items)//n:(i+1)*len(items)//n] for i in range(n)]
                reduced=False
                for chunk in chunks:
                    candidate=model.remove(current,chunk)
                    if candidate is not None and candidate!=current and check(candidate,"search")=="reproduced":
                        current=candidate
                        n=max(2,n-1)
                        reduced=True
                        break
                if reduced:continue
                if n==len(items):break
                n=min(len(items),2*n)
            # Independent fresh executions: no reuse of cached search results.
            confirm=check(current,"confirm_candidate",fresh=True)
            control=check(model.pinned,"confirm_control",fresh=True)
            if confirm!="reproduced" or control!="not_observed":
                reason="fresh_confirmation_inconclusive"
            else:
                for item in sorted(current-model.pinned):
                    candidate=model.remove(current,[item])
                    if candidate is None:
                        final_checks.append({"remove":item,"result":"constraint_blocked"})
                        continue
                    result=check(candidate,"confirm_removal",fresh=True)
                    final_checks.append({"remove":item,"removed":sorted(current-candidate),"result":result})
                if final_checks and all(x["result"]=="not_observed" for x in final_checks):
                    status="candidate_confirmed"
                    reason="all_admissible_single_removals_not_observed"
                else:
                    reason="removal_confirmation_inconclusive"
    except BudgetExhausted:
        reason="trial_budget_exhausted"
    return {"schema":1,"status":status,"reason":reason,"target_fingerprint":fingerprint,
            "candidate":sorted(current),"pinned":sorted(model.pinned),"seeds":list(seeds),
            "repeats":repeats,"budget":budget,"trials_used":len(evidence),
            "assessments":assessments,"final_checks":final_checks,"trials":evidence,
            "limitations":["Finite repeated samples; no causal proof or statistical significance.",
                           "Minimality is relative to this graph, predicate, environment, seeds and admissible single-removal groups.",
                           "Exact required component graph supplied externally; no loader version resolution, aliases or optional dependencies.",
                           "Oracle must independently provision and verify each experiment; unique receipts alone do not establish independence.",
                           "No globally smallest set or exhaustive search claim."]}
