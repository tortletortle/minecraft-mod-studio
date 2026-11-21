const fail=(code,details)=>{const error=new Error(code);if(details!==undefined)error.details=details;throw error;};
const clone=value=>JSON.parse(JSON.stringify(value));
const record=value=>!!value&&typeof value==="object"&&!Array.isArray(value);

export const createV25HostBridge=({core,getProject,replaceProject,onProjectChanged=()=>{},isEnabled=()=>false}={})=>{
  if(!record(core)||typeof core.migrate!=="function"||typeof core.encode!=="function"||typeof core.validate!=="function")fail("INVALID_V25_CORE");
  if(typeof getProject!=="function"||typeof replaceProject!=="function"||typeof onProjectChanged!=="function"||typeof isEnabled!=="function")fail("INVALID_HOST_CALLBACKS");
  let revision=0;
  const plans=new WeakMap(),receipts=new WeakMap();
  const enabled=()=>{if(isEnabled()!==true)fail("EXTENSION_FEATURE_DISABLED");};
  const snapshot=()=>{
    enabled();
    const live=getProject();if(!record(live))fail("INVALID_LIVE_PROJECT");
    let migrated;try{migrated=core.migrate(clone(live));}catch(e){fail("PROJECT_SNAPSHOT_FAILED",String(e?.message||e));}
    if(!record(migrated))fail("INVALID_PROJECT_SNAPSHOT");
    const raw=core.encode(migrated);if(typeof raw!=="string")fail("INVALID_PROJECT_ENCODING");
    return {project:clone(migrated),raw};
  };
  const validate=project=>{
    let result;try{result=core.validate(project);}catch(e){fail("PROJECT_VALIDATION_FAILED",String(e?.message||e));}
    if(!record(result)||!Array.isArray(result.errors)||!Array.isArray(result.warnings||[]))fail("INVALID_VALIDATION_RESULT");
    if(result.errors.length)fail("PROJECT_VALIDATION_FAILED",result.errors);
    return {warnings:[...(result.warnings||[])]};
  };
  const syncHost=(next,previous)=>{
    try{
      const result=replaceProject(clone(next));
      if(result&&typeof result.then==="function")fail("ASYNC_HOST_CALLBACK_UNSUPPORTED");
      const actual=getProject();
      if(!record(actual)||core.encode(core.migrate(clone(actual)))!==core.encode(next))fail("HOST_REPLACEMENT_MISMATCH");
      const notified=onProjectChanged();
      if(notified&&typeof notified.then==="function")fail("ASYNC_HOST_CALLBACK_UNSUPPORTED");
    }catch(e){
      try{replaceProject(clone(previous));onProjectChanged();}catch{}
      if(e?.message==="ASYNC_HOST_CALLBACK_UNSUPPORTED"||e?.message==="HOST_REPLACEMENT_MISMATCH")throw e;
      fail("HOST_COMMIT_FAILED",String(e?.message||e));
    }
  };
  const getSnapshot=()=>snapshot().project;
  const stageMutation=(mutator,summary={})=>{
    const base=snapshot();
    if(typeof mutator!=="function")fail("HOST_MUTATOR_REQUIRED");
    let candidate;try{candidate=mutator(clone(base.project));}catch(e){fail("MUTATION_STAGE_FAILED",String(e?.message||e));}
    if(candidate===undefined)fail("MUTATION_RETURN_REQUIRED");
    if(!record(candidate))fail("INVALID_MUTATION_RESULT");
    let next;try{next=core.migrate(clone(candidate));}catch(e){fail("MUTATION_MIGRATION_FAILED",String(e?.message||e));}
    if(!record(next))fail("INVALID_MUTATION_RESULT");
    const checked=validate(next),token=Object.freeze({});
    plans.set(token,{revision,baseRaw:base.raw,before:base.project,next:clone(next),nextRaw:core.encode(next),summary:clone(summary),warnings:checked.warnings});
    return {token,summary:clone(summary),warnings:checked.warnings,baseRevision:revision};
  };
  const commit=(token,{approved=false}={})=>{
    enabled();
    if(approved!==true)fail("APPROVAL_REQUIRED");
    const plan=plans.get(token);if(!plan)fail("INVALID_PLAN_TOKEN");
    if(plan.revision!==revision)fail("STALE_PLAN");
    const current=snapshot();if(current.raw!==plan.baseRaw)fail("HOST_PROJECT_CHANGED");
    validate(plan.next);
    syncHost(plan.next,plan.before);
    revision++;plans.delete(token);
    const receipt=Object.freeze({});
    receipts.set(receipt,{revision,before:plan.before,afterRaw:plan.nextRaw,summary:plan.summary});
    return {receipt,revision,summary:clone(plan.summary),warnings:[...plan.warnings]};
  };
  const rollback=(receipt,{approved=false}={})=>{
    enabled();
    if(approved!==true)fail("APPROVAL_REQUIRED");
    const prior=receipts.get(receipt);if(!prior)fail("INVALID_RECEIPT");
    if(prior.revision!==revision)fail("STALE_RECEIPT");
    const current=snapshot();if(current.raw!==prior.afterRaw)fail("HOST_PROJECT_CHANGED");
    validate(prior.before);
    syncHost(prior.before,current.project);
    revision++;receipts.delete(receipt);
    return {revision,state:"rolled_back",summary:clone(prior.summary)};
  };
  return Object.freeze({getSnapshot,stageMutation,commit,rollback,getRevision:()=>revision,isEnabled:()=>isEnabled()===true});
};
