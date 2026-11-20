// MMS L1 data-only extension registry, research prototype. No executable plugins.
export class ExtensionRegistry {
  #installed = new Map();
  #active = new Map();
  #sdk = "0.1.0";
  #types = new Map([["template","template.register"],["blueprint","blueprint.register"],["recipe","recipe.register"]]);
  #id(value) { return typeof value === "string" && /^[a-z][a-z0-9-]{0,47}$/.test(value) && !["constructor","prototype"].includes(value); }
  #version(value) { return typeof value === "string" && /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(value) && value.length <= 32; }
  #fail(code) { throw new Error(code); }
  #keys(obj, allowed) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj) || Object.keys(obj).some(k=>!allowed.includes(k))) this.#fail("INVALID_FIELDS");
  }
  #parse(raw) {
    if (typeof raw !== "string" || raw.length > 128000) this.#fail("PACKAGE_LIMIT");
    let p;
    try { p=JSON.parse(raw); } catch { this.#fail("INVALID_JSON"); }
    this.#keys(p,["id","version","sdkVersion","permissions","dependencies","contributes"]);
    if (!this.#id(p.id) || !this.#version(p.version)) this.#fail("INVALID_ID_VERSION");
    if (p.sdkVersion!==this.#sdk) this.#fail("SDK_MISMATCH");
    if (!Array.isArray(p.permissions) || new Set(p.permissions).size!==p.permissions.length || p.permissions.some(x=>![...this.#types.values()].includes(x))) this.#fail("INVALID_PERMISSION");
    if (!p.dependencies || typeof p.dependencies!=="object" || Array.isArray(p.dependencies)) this.#fail("INVALID_DEPENDENCY");
    for (const [k,v] of Object.entries(p.dependencies)) if (!this.#id(k) || k===p.id || !this.#version(v)) this.#fail("INVALID_DEPENDENCY");
    if (!Array.isArray(p.contributes) || p.contributes.length===0 || p.contributes.length>100) this.#fail("INVALID_CONTRIBUTIONS");
    const seen=new Set();
    for (const c of p.contributes) {
      this.#keys(c,["type","id","data"]);
      if (!this.#types.has(c.type) || !this.#id(c.id) || !c.data || typeof c.data!=="object" || Array.isArray(c.data)) this.#fail("INVALID_CONTRIBUTION");
      const key=c.type+":"+c.id;
      if(seen.has(key)) this.#fail("DUPLICATE_CONTRIBUTION");
      seen.add(key);
      if(!p.permissions.includes(this.#types.get(c.type))) this.#fail("UNDECLARED_PERMISSION");
    }
    // JSON is inert here, but reject prototype-related keys anywhere in payload before handing it off.
    const stack=[p];
    while(stack.length) {
      const x=stack.pop();
      for(const k of Object.keys(x)) {
        if(["__proto__","constructor","prototype"].includes(k)) this.#fail("UNSAFE_KEY");
        if(x[k]!==null && typeof x[k]==="object") stack.push(x[k]);
      }
    }
    return p;
  }
  install(raw) {
    const p=this.#parse(raw);
    if(this.#installed.has(p.id)) this.#fail("ALREADY_INSTALLED");
    this.#installed.set(p.id,p);
    return p.id;
  }
  enable(id, grants=[]) {
    const p=this.#installed.get(id);
    if (!p) this.#fail("NOT_INSTALLED");
    if (this.#active.has(id)) this.#fail("ALREADY_ACTIVE");
    if (!Array.isArray(grants) || p.permissions.some(x=>!grants.includes(x))) this.#fail("PERMISSION_DENIED");
    for (const [d,v] of Object.entries(p.dependencies)) {
      if(!this.#active.has(d) || this.#installed.get(d).version!==v) this.#fail("DEPENDENCY_NOT_READY");
    }
    // No callbacks or side effects; activation publishes the entire validated set in one operation.
    this.#active.set(id,p.contributes);
  }
  disable(id) {
    if(!this.#active.has(id)) this.#fail("NOT_ACTIVE");
    for(const other of this.#active.keys()) {
      if(Object.hasOwn(this.#installed.get(other).dependencies,id)) this.#fail("ACTIVE_DEPENDENT");
    }
    this.#active.delete(id);
  }
  uninstall(id) {
    if(!this.#installed.has(id)) this.#fail("NOT_INSTALLED");
    if(this.#active.has(id)) this.#fail("STILL_ACTIVE");
    this.#installed.delete(id);
  }
  list(type) {
    if(!this.#types.has(type)) this.#fail("UNKNOWN_TYPE");
    return [...this.#active.entries()].flatMap(([id, entries])=>entries.filter(c=>c.type===type).map(c=>({key:id+":"+c.id,data:JSON.parse(JSON.stringify(c.data))})));
  }
  status() {
    return [...this.#installed.values()].map(p=>({id:p.id,version:p.version,active:this.#active.has(p.id)}));
  }
}
