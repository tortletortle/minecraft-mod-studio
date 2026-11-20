function makeHostTools(){
  const fail=(s)=>{throw Error(s);};
  const clone=x=>JSON.parse(JSON.stringify(x));
  const exact=(x,keys)=>x&&typeof x==="object"&&!Array.isArray(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.hasOwn(x,k));
  const snapshot=host=>{
    const s=host.read();
    if(!exact(s,["revision","raw"])||typeof s.raw!=="string"||typeof s.revision!=="string"||s.raw.length>3145728)fail("INVALID_SNAPSHOT");
    const p=JSON.parse(s.raw);
    if(![3,4].includes(p.schemaVersion)||p.target?.loader!=="fabric"||p.target?.minecraft!=="26.2"||!Array.isArray(p.items))fail("UNSUPPORTED_PROJECT");
    return {revision:s.revision,raw:s.raw,p};
  };
  const equal=(a,b)=>a.revision===b.revision&&a.raw===b.raw;
  const lookup=(registry,type,key)=>{
    const matches=registry.list(type).filter(x=>x.key===key);
    if(matches.length!==1)fail("CONTRIBUTION_NOT_ACTIVE");
    return clone(matches[0].data);
  };
  const validated=(validate,p)=>{
    // Existing StudioCore validator is injected by the trusted host. It can inspect a disposable clone.
    const result=validate(clone(p));
    if(!result||!Array.isArray(result.errors)||result.errors.length)fail("PROJECT_VALIDATION_FAILED");
  };
  class RecipeTransactions {
    #host;#registry;#validate;#pending=new WeakMap();#receipts=new WeakMap();
    constructor({host,registry,validate}){this.#host=host;this.#registry=registry;this.#validate=validate;}
    preview(key,uid){
      const s=snapshot(this.#host), data=lookup(this.#registry,"recipe",key);
      if(!exact(data,["ingredients"])||!Array.isArray(data.ingredients)||data.ingredients.length!==9||!data.ingredients.some(Boolean)||!data.ingredients.every(x=>typeof x==="string"&&(x===""||(/^minecraft:[a-z0-9_]{1,80}$/.test(x)))))fail("INVALID_RECIPE");
      const matches=s.p.items.filter(i=>i.uid===uid);
      if(matches.length!==1)fail("ITEM_NOT_FOUND");
      const item=matches[0];
      if(!Array.isArray(item.recipe)||item.recipe.length!==9)fail("INVALID_EXISTING_RECIPE");
      const before=clone(item.recipe);
      item.recipe=clone(data.ingredients);
      validated(this.#validate,s.p);
      const next=JSON.stringify(s.p);
      if(next.length>3145728)fail("PROJECT_LIMIT");
      if(JSON.stringify(before)===JSON.stringify(item.recipe))fail("NO_CHANGE");
      const token=Object.freeze({});
      this.#pending.set(token,{revision:s.revision,raw:s.raw,next,key,data});
      return {token,diff:{itemUid:uid,before,after:clone(item.recipe)}};
    }
    commit(token,{approved=false}={}){
      const plan=this.#pending.get(token);
      if(!plan)fail("INVALID_TOKEN");
      if(approved!==true)fail("APPROVAL_REQUIRED");
      const s=snapshot(this.#host);
      if(!equal(s,plan))fail("STALE_PROJECT");
      if(JSON.stringify(lookup(this.#registry,"recipe",plan.key))!==JSON.stringify(plan.data))fail("STALE_CONTRIBUTION");
      validated(this.#validate,JSON.parse(plan.next));
      // Trusted host must update revision AND raw atomically, or throw without mutation.
      const after=this.#host.compareAndSwap({revision:plan.revision,raw:plan.raw},plan.next);
      this.#pending.delete(token);
      const receipt=Object.freeze({});
      this.#receipts.set(receipt,{after:{revision:after.revision,raw:plan.next},before:plan.raw});
      return receipt;
    }
    undo(receipt,{approved=false}={}){
      const rec=this.#receipts.get(receipt);
      if(!rec)fail("INVALID_RECEIPT");
      if(approved!==true)fail("APPROVAL_REQUIRED");
      const s=snapshot(this.#host);
      if(!equal(s,rec.after))fail("STALE_PROJECT");
      validated(this.#validate,JSON.parse(rec.before));
      this.#host.compareAndSwap(rec.after,rec.before);
      this.#receipts.delete(receipt);
    }
  }
  // Plan only: no project mutation or filesystem access. The real structure service owns NBT generation.
  function planStructure(registry,key,project){
    if(project?.target?.loader!=="fabric"||project?.target?.minecraft!=="26.2")fail("UNSUPPORTED_PROJECT");
    const ns=project.modId;
    if(typeof ns!=="string"||!/^[a-z][a-z0-9_-]{1,47}$/.test(ns)||["minecraft","realms"].includes(ns))fail("INVALID_NAMESPACE");
    const d=lookup(registry,"template",key);
    if(!exact(d,["kind","id","preset","seed"])||d.kind!=="structure-preset"||typeof d.id!=="string"||!/^[a-z0-9][a-z0-9_-]{0,47}$/.test(d.id)||!["house","tower","factory"].includes(d.preset)||!Number.isInteger(d.seed)||d.seed<0||d.seed>4294967295)fail("INVALID_STRUCTURE_TEMPLATE");
    return {namespace:ns,buildings:[{id:d.id,preset:d.preset,seed:d.seed}]};
  }
  return {RecipeTransactions,planStructure};
}
export const {RecipeTransactions,planStructure}=makeHostTools();
