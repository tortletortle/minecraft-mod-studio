() => {
  const fail = code => { throw new Error(code); };
  const exact = (v, keys) => v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === keys.length && keys.every(k=>Object.hasOwn(v,k));
  const idOk = v => typeof v === "string" && /^[a-z][a-z0-9-]{0,47}$/.test(v) && !["constructor","prototype"].includes(v);
  const versionOk = v => { if(typeof v!=="string"||v.length>32)return false;const m=/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.exec(v);return !!m&&m.slice(1).every(x=>Number.isSafeInteger(Number(x))); };
  const compareVersion = (a,b) => {a=a.split(".").map(Number);b=b.split(".").map(Number);for(let i=0;i<3;i++)if(a[i]!==b[i])return a[i]<b[i]?-1:1;return 0;};
  const permissionByType = new Map([["template","template.register"],["blueprint","blueprint.register"],["recipe","recipe.register"]]);
  const parseManifest = raw => {
    if(typeof raw!=="string"||raw.length>128000)fail("PACKAGE_LIMIT");
    let m;try{m=JSON.parse(raw)}catch{fail("INVALID_JSON")}
    if(!exact(m,["id","version","sdkVersion","permissions","dependencies","contributes"]))fail("INVALID_FIELDS");
    if(!idOk(m.id)||!versionOk(m.version))fail("INVALID_ID_VERSION");
    if(m.sdkVersion!=="0.1.0")fail("SDK_MISMATCH");
    if(!Array.isArray(m.permissions)||new Set(m.permissions).size!==m.permissions.length||m.permissions.some(p=>![...permissionByType.values()].includes(p)))fail("INVALID_PERMISSION");
    if(!m.dependencies||typeof m.dependencies!=="object"||Array.isArray(m.dependencies))fail("INVALID_DEPENDENCY");
    for(const [d,v] of Object.entries(m.dependencies))if(!idOk(d)||d===m.id||!versionOk(v))fail("INVALID_DEPENDENCY");
    if(!Array.isArray(m.contributes)||m.contributes.length<1||m.contributes.length>100)fail("INVALID_CONTRIBUTIONS");
    const seen=new Set();
    for(const c of m.contributes){
      if(!exact(c,["type","id","data"])||!permissionByType.has(c.type)||!idOk(c.id)||!c.data||typeof c.data!=="object"||Array.isArray(c.data))fail("INVALID_CONTRIBUTION");
      const k=c.type+":"+c.id;if(seen.has(k))fail("DUPLICATE_CONTRIBUTION");seen.add(k);
      if(!m.permissions.includes(permissionByType.get(c.type)))fail("UNDECLARED_PERMISSION");
    }
    const stack=[[m,0]];let nodes=0;
    while(stack.length){const [v,d]=stack.pop();if(++nodes>10000||d>32)fail("PAYLOAD_COMPLEXITY_LIMIT");for(const k of Object.keys(v)){if(["__proto__","constructor","prototype"].includes(k))fail("UNSAFE_KEY");if(v[k]!==null&&typeof v[k]==="object")stack.push([v[k],d+1]);}}
    return m;
  };
  const utf8 = s => {let e;try{e=encodeURIComponent(s)}catch{fail("INVALID_UNICODE")}const b=[];for(let i=0;i<e.length;){if(e[i]==="%"){b.push(parseInt(e.slice(i+1,i+3),16));i+=3}else{b.push(e.charCodeAt(i));i++}}return b;};
  const sha256 = value => {
    const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    const bytes=utf8(value),bits=bytes.length*8;bytes.push(0x80);while(bytes.length%64!==56)bytes.push(0);
    const hi=Math.floor(bits/0x100000000),lo=bits>>>0;for(let n=24;n>=0;n-=8)bytes.push((hi>>>n)&255);for(let n=24;n>=0;n-=8)bytes.push((lo>>>n)&255);
    const H=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],rotr=(x,n)=>(x>>>n)|(x<<(32-n));
    for(let off=0;off<bytes.length;off+=64){
      const w=new Array(64);
      for(let i=0;i<16;i++){const j=off+i*4;w[i]=((bytes[j]<<24)|(bytes[j+1]<<16)|(bytes[j+2]<<8)|bytes[j+3])>>>0;}
      for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2],s0=rotr(x,7)^rotr(x,18)^(x>>>3),s1=rotr(y,17)^rotr(y,19)^(y>>>10);w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;}
      let [a,b,c,d,e,f,g,h]=H;
      for(let i=0;i<64;i++){const s1=rotr(e,6)^rotr(e,11)^rotr(e,25),ch=(e&f)^(~e&g),t1=(h+s1+ch+K[i]+w[i])>>>0,s0=rotr(a,2)^rotr(a,13)^rotr(a,22),maj=(a&b)^(a&c)^(b&c),t2=(s0+maj)>>>0;h=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
      H[0]=(H[0]+a)>>>0;H[1]=(H[1]+b)>>>0;H[2]=(H[2]+c)>>>0;H[3]=(H[3]+d)>>>0;H[4]=(H[4]+e)>>>0;H[5]=(H[5]+f)>>>0;H[6]=(H[6]+g)>>>0;H[7]=(H[7]+h)>>>0;
    }
    return H.map(x=>x.toString(16).padStart(8,"0")).join("");
  };
  const createLockfile = raws => {
    if(!Array.isArray(raws)||raws.length<1||raws.length>64)fail("LOCKFILE_PACKAGE_LIMIT");
    const seen=new Set(),packages=raws.map(raw=>{const m=parseManifest(raw);if(seen.has(m.id))fail("DUPLICATE_PACKAGE");seen.add(m.id);return {id:m.id,version:m.version,sha256:sha256(raw)}}).sort((a,b)=>a.id.localeCompare(b.id));
    return {schema:1,sdkVersion:"0.1.0",packages};
  };
  const verifyLockfile = (lock,raws) => {if(!exact(lock,["schema","sdkVersion","packages"])||lock.schema!==1||lock.sdkVersion!=="0.1.0"||!Array.isArray(lock.packages)||!Array.isArray(raws)||lock.packages.length!==raws.length)fail("INVALID_LOCKFILE");if(JSON.stringify(lock)!==JSON.stringify(createLockfile(raws)))fail("LOCKFILE_MISMATCH");return true;};
  class PackageManager {
    #installed=new Map();#active=new Set();#grants=new Map();#generation=0;#plans=new WeakMap();#receipts=new WeakMap();
    #topological(installed){if(installed.size>256)fail("INSTALLED_PACKAGE_LIMIT");const state=new Map(),order=[];const visit=id=>{const s=state.get(id)||0;if(s===1)fail("DEPENDENCY_CYCLE");if(s===2)return;const e=installed.get(id);if(!e)fail("PACKAGE_NOT_FOUND");state.set(id,1);for(const d of Object.keys(e.manifest.dependencies).sort()){const t=installed.get(d);if(!t||t.manifest.version!==e.manifest.dependencies[d])fail("DEPENDENCY_UNSATISFIED");visit(d);}state.set(id,2);order.push(id);};for(const id of [...installed.keys()].sort())visit(id);return order;}
    #validateState(installed,active,grants){const order=this.#topological(installed);for(const id of active){const e=installed.get(id);if(!e)fail("ACTIVE_PACKAGE_MISSING");const allowed=grants.get(id)||new Set();if(e.manifest.permissions.some(p=>!allowed.has(p)))fail("PERMISSION_NOT_GRANTED");for(const d of Object.keys(e.manifest.dependencies))if(!active.has(d))fail("ACTIVE_DEPENDENCY_NOT_ACTIVE");}for(const id of grants.keys())if(!active.has(id))fail("ORPHANED_GRANT");return order;}
    #makePlan(kind,installed,active,grants,summary){const order=this.#validateState(installed,active,grants),token=Object.freeze({});this.#plans.set(token,{generation:this.#generation,kind,installed,active,grants,summary,order});return {token,kind,summary:JSON.parse(JSON.stringify(summary)),activationOrder:order};}
    planInstall(raws,options={}){if(!options||typeof options!=="object"||Array.isArray(options)||Object.keys(options).some(k=>k!=="upgrade"))fail("INVALID_INSTALL_OPTIONS");const upgrade=options.upgrade??false;if(!Array.isArray(raws)||raws.length<1||raws.length>32||typeof upgrade!=="boolean")fail("INSTALL_BATCH_LIMIT");const candidates=new Map();for(const raw of raws){const m=parseManifest(raw);if(candidates.has(m.id))fail("DUPLICATE_PACKAGE");candidates.set(m.id,{manifest:m,raw});}const installed=new Map(this.#installed),active=new Set(this.#active),grants=new Map([...this.#grants].map(([id,s])=>[id,new Set(s)])),summary={installed:[],unchanged:[],upgraded:[]};for(const [id,c] of candidates){const old=installed.get(id);if(old){const cmp=compareVersion(c.manifest.version,old.manifest.version);if(cmp===0){if(c.raw!==old.raw)fail("VERSION_CONTENT_REUSE");summary.unchanged.push(id);continue;}if(cmp<0)fail("DOWNGRADE_REFUSED");if(!upgrade)fail("UPGRADE_REQUIRES_FLAG");if(active.has(id)&&c.manifest.permissions.some(p=>!(grants.get(id)||new Set()).has(p)))fail("NEW_PERMISSION_REQUIRES_CONSENT");summary.upgraded.push({id,from:old.manifest.version,to:c.manifest.version});}else summary.installed.push(id);installed.set(id,c);}if(!summary.installed.length&&!summary.upgraded.length)fail("NO_CHANGES");const order=this.#validateState(installed,active,grants);return this.#makePlan("install",installed,active,grants,{...summary,activationOrder:order});}
    planUninstall(ids){if(!Array.isArray(ids)||ids.length<1||ids.length>32||new Set(ids).size!==ids.length)fail("INVALID_UNINSTALL_BATCH");const installed=new Map(this.#installed),active=new Set(this.#active),grants=new Map([...this.#grants].map(([id,s])=>[id,new Set(s)]));for(const id of ids){if(!installed.has(id))fail("PACKAGE_NOT_FOUND");installed.delete(id);active.delete(id);grants.delete(id);}const order=this.#validateState(installed,active,grants);return this.#makePlan("uninstall",installed,active,grants,{removed:[...ids].sort(),activationOrder:order});}
    commit(token,options={}){if(!options||typeof options!=="object"||Array.isArray(options)||Object.keys(options).some(k=>k!=="approved"))fail("INVALID_COMMIT_OPTIONS");const p=this.#plans.get(token);if(!p)fail("INVALID_PLAN_TOKEN");if(options.approved!==true)fail("APPROVAL_REQUIRED");if(p.generation!==this.#generation)fail("STALE_PLAN");this.#validateState(p.installed,p.active,p.grants);const previous={installed:this.#installed,active:this.#active,grants:this.#grants};this.#installed=new Map(p.installed);this.#active=new Set(p.active);this.#grants=new Map([...p.grants].map(([id,s])=>[id,new Set(s)]));this.#generation++;this.#plans.delete(token);const receipt=Object.freeze({});this.#receipts.set(receipt,{generation:this.#generation,previous});return {receipt,summary:JSON.parse(JSON.stringify(p.summary)),generation:this.#generation};}
    rollback(receipt,options={}){if(!options||typeof options!=="object"||Array.isArray(options)||Object.keys(options).some(k=>k!=="approved"))fail("INVALID_ROLLBACK_OPTIONS");const r=this.#receipts.get(receipt);if(!r)fail("INVALID_RECEIPT");if(options.approved!==true)fail("APPROVAL_REQUIRED");if(r.generation!==this.#generation)fail("STALE_RECEIPT");this.#installed=new Map(r.previous.installed);this.#active=new Set(r.previous.active);this.#grants=new Map([...r.previous.grants].map(([id,s])=>[id,new Set(s)]));this.#generation++;this.#receipts.delete(receipt);return this.status();}
    enable(id,grants=[]){if(!this.#installed.has(id))fail("PACKAGE_NOT_FOUND");if(this.#active.has(id))fail("ALREADY_ACTIVE");const required=this.#installed.get(id).manifest.permissions;if(!Array.isArray(grants)||new Set(grants).size!==grants.length||grants.some(p=>!required.includes(p))||required.some(p=>!grants.includes(p)))fail("PERMISSION_DENIED");for(const d of Object.keys(this.#installed.get(id).manifest.dependencies))if(!this.#active.has(d))fail("DEPENDENCY_NOT_READY");this.#active.add(id);this.#grants.set(id,new Set(grants));this.#validateState(this.#installed,this.#active,this.#grants);this.#generation++;return this.status();}
    enableClosure(id,grantsById){if(!this.#installed.has(id))fail("PACKAGE_NOT_FOUND");if(!grantsById||typeof grantsById!=="object"||Array.isArray(grantsById))fail("INVALID_GRANT_MAP");const closure=new Set();const collect=current=>{if(closure.has(current))return;closure.add(current);const e=this.#installed.get(current);if(!e)fail("PACKAGE_NOT_FOUND");for(const d of Object.keys(e.manifest.dependencies))collect(d);};collect(id);if(Object.keys(grantsById).some(k=>!closure.has(k)))fail("UNEXPECTED_GRANT_ENTRY");const order=this.#topological(this.#installed).filter(k=>closure.has(k)),active=new Set(this.#active),grants=new Map([...this.#grants].map(([k,s])=>[k,new Set(s)])),enabled=[];for(const k of order){if(active.has(k))continue;const supplied=Object.hasOwn(grantsById,k)?grantsById[k]:undefined,required=this.#installed.get(k).manifest.permissions;if(!Array.isArray(supplied)||new Set(supplied).size!==supplied.length||supplied.some(p=>!required.includes(p))||required.some(p=>!supplied.includes(p)))fail("PERMISSION_DENIED");active.add(k);grants.set(k,new Set(supplied));enabled.push(k);}if(!enabled.length)fail("ALREADY_ACTIVE");this.#validateState(this.#installed,active,grants);this.#active=active;this.#grants=grants;this.#generation++;return {enabled,generation:this.#generation};}
    disable(id){if(!this.#active.has(id))fail("NOT_ACTIVE");for(const other of this.#active)if(Object.hasOwn(this.#installed.get(other).manifest.dependencies,id))fail("ACTIVE_DEPENDENT");this.#active.delete(id);this.#grants.delete(id);this.#generation++;return this.status();}
    status(){return [...this.#installed.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([id,e])=>({id,version:e.manifest.version,active:this.#active.has(id),dependencies:{...e.manifest.dependencies},permissions:[...e.manifest.permissions],grants:[...(this.#grants.get(id)||new Set())].sort()}));}
  }
  return {PackageManager,sha256,createLockfile,verifyLockfile,parseManifest,compareVersion};
}
export const {PackageManager,sha256,createLockfile,verifyLockfile}=makePackageTools();
