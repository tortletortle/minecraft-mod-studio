/* Self-contained browser bundle for MMS V25. Generated from the tested research modules. */
(()=>{
"use strict";
const packageApi=(()=>{const makePackageTools = () => {
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
  const utf8 = s => {if(s instanceof Uint8Array)return Array.from(s);let e;try{e=encodeURIComponent(s)}catch{fail("INVALID_UNICODE")}const b=[];for(let i=0;i<e.length;){if(e[i]==="%"){b.push(parseInt(e.slice(i+1,i+3),16));i+=3}else{b.push(e.charCodeAt(i));i++}}return b;};
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
  const sha256Bytes=value=>{if(!(value instanceof Uint8Array))fail("INVALID_BYTES");return sha256(value);};
    return {PackageManager,sha256,sha256Bytes,createLockfile,verifyLockfile,parseManifest,compareVersion};
};
return makePackageTools();
})();
const archiveApi=(()=>{const makeArchiveTools = () => {
  const fail = code => { throw new Error(code); };
  const MAX_ARCHIVE=8*1024*1024,MAX_FILES=64,MAX_FILE=1024*1024,MAX_TOTAL=4*1024*1024;
  const crcTable=new Uint32Array(256);
  for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?(0xedb88320^(c>>>1)):(c>>>1);crcTable[n]=c>>>0;}
  const crc32=bytes=>{if(!(bytes instanceof Uint8Array))fail("INVALID_BYTES");let crc=0xffffffff;for(const b of bytes)crc=crcTable[(crc^b)&255]^(crc>>>8);return (crc^0xffffffff)>>>0;};
  const browserInflateRaw=async(compressed,expected)=>{
    if(typeof DecompressionStream!=="function"||typeof Blob!=="function")fail("DEFLATE_UNAVAILABLE");
    const reader=new Blob([compressed]).stream().pipeThrough(new DecompressionStream("deflate-raw")).getReader(),chunks=[];let total=0;
    try{while(true){const {value,done}=await reader.read();if(done)break;total+=value.length;if(total>expected||total>MAX_FILE){await reader.cancel();fail("DECOMPRESSED_SIZE_MISMATCH");}chunks.push(value);}}finally{reader.releaseLock();}
    if(total!==expected)fail("DECOMPRESSED_SIZE_MISMATCH");const out=new Uint8Array(total);let p=0;for(const chunk of chunks){out.set(chunk,p);p+=chunk.length;}return out;
  };
  const decodeAscii=bytes=>{let out="";for(const b of bytes){if(b<0x20||b>0x7e)fail("NON_ASCII_PATH");out+=String.fromCharCode(b);}return out;};
  const validatePath=path=>{
    if(typeof path!=="string"||path.length<1||path.length>200||path.startsWith("/")||path.includes("\\")||!/^[A-Za-z0-9._/-]+$/.test(path))fail("INVALID_ARCHIVE_PATH");
    const parts=path.split("/");if(parts.some(p=>!p||p==="."||p===".."))fail("INVALID_ARCHIVE_PATH");
    if(path==="manifest.json"||path==="README.md")return;
    if(!path.startsWith("assets/")||parts.length<2||path!==path.toLowerCase())fail("UNSUPPORTED_ARCHIVE_FILE");
    const ext=path.slice(path.lastIndexOf(".")).toLowerCase();if(![".png",".ogg",".json",".mcmeta",".jem",".jpm",".bbmodel"].includes(ext))fail("UNSUPPORTED_ASSET_TYPE");
  };
  const decodeUtf8Default=bytes=>{if(typeof TextDecoder!=="function")fail("UTF8_DECODER_UNAVAILABLE");try{return new TextDecoder("utf-8",{fatal:true}).decode(bytes);}catch{fail("INVALID_UTF8");}};
  const validateAsset=(path,bytes,decodeUtf8)=>{
    if(path==="README.md"){decodeUtf8(bytes);return;}
    if(path==="manifest.json"||/\.(json|mcmeta|jem|jpm|bbmodel)$/.test(path)){let v;try{v=JSON.parse(decodeUtf8(bytes));}catch{fail("INVALID_ASSET_JSON");}if(!v||typeof v!=="object")fail("INVALID_ASSET_JSON");return;}
    if(path.endsWith(".png")){if(bytes.length<33||![137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v)||String.fromCharCode(...bytes.subarray(12,16))!=="IHDR")fail("INVALID_PNG");const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),w=v.getUint32(16),h=v.getUint32(20);if(!w||!h||w>4096||h>4096||w*h>16777216)fail("PNG_DIMENSIONS_LIMIT");return;}
    if(path.endsWith(".ogg")){if(bytes.length<4||String.fromCharCode(...bytes.subarray(0,4))!=="OggS")fail("INVALID_OGG");return;}
    fail("UNSUPPORTED_ASSET_TYPE");
  };
  const readMmse=async(bytes,options={})=>{
    if(!(bytes instanceof Uint8Array)||bytes.length<22||bytes.length>MAX_ARCHIVE)fail("ARCHIVE_SIZE_LIMIT");
    if(!options||typeof options!=="object"||typeof options.parseManifest!=="function")fail("MANIFEST_VALIDATOR_REQUIRED");
    const parseManifest=options.parseManifest,inflateRaw=options.inflateRaw||browserInflateRaw,decodeUtf8=options.decodeUtf8||decodeUtf8Default;
    const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),length=bytes.length;
    const need=(o,n,limit=length)=>Number.isInteger(o)&&Number.isInteger(n)&&o>=0&&n>=0&&o+n<=limit;
    const u16=o=>{if(!need(o,2))fail("ZIP_TRUNCATED");return view.getUint16(o,true);};
    const u32=o=>{if(!need(o,4))fail("ZIP_TRUNCATED");return view.getUint32(o,true);};
    let end=-1;for(let o=length-22;o>=Math.max(0,length-22-65535);o--)if(u32(o)===0x06054b50&&o+22+u16(o+20)===length){end=o;break;}
    if(end<0)fail("INVALID_EOCD");
    const disk=u16(end+4),centralDisk=u16(end+6),diskEntries=u16(end+8),count=u16(end+10),centralSize=u32(end+12),centralOffset=u32(end+16),comment=u16(end+20);
    if(end>=20&&u32(end-20)===0x07064b50)fail("ZIP64_UNSUPPORTED");
    if(comment!==0)fail("ZIP_COMMENT_UNSUPPORTED");
    if(disk!==0||centralDisk!==0||diskEntries!==count)fail("MULTI_DISK_UNSUPPORTED");
    if(count===0xffff||centralSize===0xffffffff||centralOffset===0xffffffff)fail("ZIP64_UNSUPPORTED");
    if(count<1||count>MAX_FILES)fail("ZIP_FILE_COUNT_LIMIT");
    if(centralOffset+centralSize!==end||!need(centralOffset,centralSize,end))fail("INVALID_CENTRAL_DIRECTORY");
    const entries=[],names=new Set(),offsets=new Set();let pos=centralOffset,total=0;
    for(let i=0;i<count;i++){
      if(!need(pos,46,end)||u32(pos)!==0x02014b50)fail("INVALID_CENTRAL_ENTRY");
      const madeBy=u16(pos+4),version=u16(pos+6),flags=u16(pos+8),method=u16(pos+10),crc=u32(pos+16),
        csize=u32(pos+20),usize=u32(pos+24),nameLen=u16(pos+28),extraLen=u16(pos+30),commentLen=u16(pos+32),
        diskStart=u16(pos+34),attrs=u32(pos+38),localOffset=u32(pos+42);
      if(version>20)fail("ZIP_VERSION_UNSUPPORTED");
      if(flags&~0x0806)fail("ZIP_FLAGS_UNSUPPORTED");
      if(method!==0&&method!==8)fail("ZIP_METHOD_UNSUPPORTED");
      if(method===0&&(flags&6))fail("ZIP_FLAGS_UNSUPPORTED");
      if(nameLen<1||nameLen>200||extraLen!==0||commentLen!==0)fail("ZIP_METADATA_UNSUPPORTED");
      if(diskStart!==0)fail("MULTI_DISK_UNSUPPORTED");
      if(csize===0xffffffff||usize===0xffffffff||localOffset===0xffffffff)fail("ZIP64_UNSUPPORTED");
      if(usize>MAX_FILE||csize>MAX_ARCHIVE)fail("ZIP_ENTRY_SIZE_LIMIT");
      if(usize>0&&(csize===0||usize>csize*100))fail("ZIP_COMPRESSION_RATIO_LIMIT");
      if(method===0&&csize!==usize)fail("ZIP_STORED_SIZE_MISMATCH");
      if(!need(pos+46,nameLen+extraLen+commentLen,end))fail("ZIP_TRUNCATED");
      const nameBytes=bytes.slice(pos+46,pos+46+nameLen),path=decodeAscii(nameBytes);validatePath(path);
      const folded=path.toLowerCase();if(names.has(folded))fail("DUPLICATE_ARCHIVE_PATH");names.add(folded);
      const hostOs=madeBy>>>8,mode=(attrs>>>16)&0xffff,fileType=mode&0xf000;
      if(attrs&0x10)fail("DIRECTORY_ENTRY_UNSUPPORTED");
      if(attrs&0x400)fail("NON_REGULAR_FILE_UNSUPPORTED");
      if(hostOs===3&&fileType!==0&&fileType!==0x8000)fail("NON_REGULAR_FILE_UNSUPPORTED");
      if(offsets.has(localOffset))fail("DUPLICATE_LOCAL_OFFSET");offsets.add(localOffset);
      entries.push({path,nameBytes,flags,method,crc,csize,usize,localOffset,version});
      total+=usize;if(total>MAX_TOTAL)fail("ZIP_TOTAL_SIZE_LIMIT");
      pos+=46+nameLen+extraLen+commentLen;
    }
    if(pos!==end)fail("CENTRAL_DIRECTORY_TRAILING_DATA");
    const ranges=[];
    for(const e of entries){
      const o=e.localOffset;if(!need(o,30,centralOffset)||u32(o)!==0x04034b50)fail("INVALID_LOCAL_HEADER");
      const ver=u16(o+4),flags=u16(o+6),method=u16(o+8),crc=u32(o+14),cs=u32(o+18),us=u32(o+22),nl=u16(o+26),xl=u16(o+28);
      if(ver!==e.version||ver>20||flags!==e.flags||method!==e.method||crc!==e.crc||cs!==e.csize||us!==e.usize)fail("LOCAL_CENTRAL_MISMATCH");
      if(nl!==e.nameBytes.length||xl!==0||!need(o+30,nl,centralOffset))fail("LOCAL_HEADER_METADATA_UNSUPPORTED");
      const localName=bytes.subarray(o+30,o+30+nl);if(localName.some((v,i)=>v!==e.nameBytes[i]))fail("LOCAL_CENTRAL_NAME_MISMATCH");
      const dataStart=o+30+nl,dataEnd=dataStart+e.csize;if(!need(dataStart,e.csize,centralOffset))fail("ZIP_DATA_OUT_OF_BOUNDS");
      ranges.push({start:o,end:dataEnd});e.dataStart=dataStart;
    }
    ranges.sort((a,b)=>a.start-b.start);
    if(ranges.length&&ranges[0].start!==0)fail("ZIP_PREAMBLE_UNSUPPORTED");
    for(let i=1;i<ranges.length;i++)if(ranges[i-1].end!==ranges[i].start)fail("ZIP_LOCAL_LAYOUT_GAP_OR_OVERLAP");
    if(ranges.length&&ranges[ranges.length-1].end!==centralOffset)fail("ZIP_LOCAL_LAYOUT_GAP_OR_OVERLAP");
    const files=[];
    for(const e of entries){
      const compressed=bytes.slice(e.dataStart,e.dataStart+e.csize),content=e.method===0?compressed:await inflateRaw(compressed,e.usize);
      if(!(content instanceof Uint8Array)||content.length!==e.usize)fail("DECOMPRESSED_SIZE_MISMATCH");
      if(crc32(content)!==e.crc)fail("CRC_MISMATCH");
      validateAsset(e.path,content,decodeUtf8);files.push({path:e.path,bytes:content,crc32:e.crc.toString(16).padStart(8,"0"),method:e.method});
    }
    const mf=files.find(f=>f.path==="manifest.json");if(!mf)fail("MANIFEST_MISSING");
    const manifestRaw=decodeUtf8(mf.bytes),manifest=parseManifest(manifestRaw);
    return {manifest,manifestRaw,assets:files.filter(f=>f.path.startsWith("assets/")).map(f=>({path:f.path,bytes:f.bytes.slice(),crc32:f.crc32})),readme:files.find(f=>f.path==="README.md")?.bytes.slice()??null,summary:{fileCount:files.length,assetCount:files.filter(f=>f.path.startsWith("assets/")).length,totalUncompressedBytes:total}};
  };
  return {crc32,readMmse};
};
return makeArchiveTools();
})();
const writerApi=(()=>{const {crc32,readMmse}=archiveApi;const {sha256Bytes}=packageApi;const makeArchiveWriterTools = ({crc32,readMmse,sha256Bytes}) => {
  const fail=code=>{throw new Error(code);};
  const MAX_ARCHIVE=8*1024*1024,MAX_FILES=64,MAX_FILE=1024*1024,MAX_TOTAL=4*1024*1024;
  const utf8Encode=value=>{
    if(typeof value!=="string")fail("INVALID_TEXT");const out=[];
    for(let i=0;i<value.length;i++){let cp=value.charCodeAt(i);
      if(cp>=0xd800&&cp<=0xdbff){if(i+1>=value.length)fail("INVALID_UNICODE");const lo=value.charCodeAt(++i);if(lo<0xdc00||lo>0xdfff)fail("INVALID_UNICODE");cp=0x10000+((cp-0xd800)<<10)+(lo-0xdc00);}
      else if(cp>=0xdc00&&cp<=0xdfff)fail("INVALID_UNICODE");
      if(cp<=0x7f)out.push(cp);else if(cp<=0x7ff)out.push(0xc0|(cp>>6),0x80|(cp&63));else if(cp<=0xffff)out.push(0xe0|(cp>>12),0x80|((cp>>6)&63),0x80|(cp&63));else out.push(0xf0|(cp>>18),0x80|((cp>>12)&63),0x80|((cp>>6)&63),0x80|(cp&63));
    }return Uint8Array.from(out);
  };
  const validPath=path=>{
    if(typeof path!=="string"||path.length<1||path.length>200||path.startsWith("/")||path.includes("\\")||!/^[A-Za-z0-9._/-]+$/.test(path))fail("INVALID_ARCHIVE_PATH");
    const parts=path.split("/");if(parts.some(p=>!p||p==="."||p===".."))fail("INVALID_ARCHIVE_PATH");
    if(path==="manifest.json"||path==="README.md")return;
    if(!path.startsWith("assets/")||parts.length<2||path!==path.toLowerCase())fail("UNSUPPORTED_ARCHIVE_FILE");
    const ext=path.slice(path.lastIndexOf(".")).toLowerCase();if(![".png",".ogg",".json",".mcmeta",".jem",".jpm",".bbmodel"].includes(ext))fail("UNSUPPORTED_ASSET_TYPE");
  };
  const exact=(obj,keys)=>obj&&typeof obj==="object"&&!Array.isArray(obj)&&Object.keys(obj).length===keys.length&&keys.every(k=>Object.hasOwn(obj,k));
  const concat=parts=>{const size=parts.reduce((n,p)=>n+p.length,0),out=new Uint8Array(size);let offset=0;for(const p of parts){out.set(p,offset);offset+=p.length;}return out;};
  const put16=(v,o,n)=>v.setUint16(o,n,true),put32=(v,o,n)=>v.setUint32(o,n>>>0,true);
  const createMmse=async(input,options={})=>{
    if(!options||typeof options!=="object"||typeof options.parseManifest!=="function")fail("MANIFEST_VALIDATOR_REQUIRED");
    if(!exact(input,Object.hasOwn(input||{},"readme")?["manifest","assets","readme"]:["manifest","assets"]))fail("INVALID_PACKAGE_INPUT");
    const manifestRaw=input.manifest;if(typeof manifestRaw!=="string"||manifestRaw.length>MAX_FILE)fail("MANIFEST_SIZE_LIMIT");options.parseManifest(manifestRaw);
    if(!Array.isArray(input.assets)||input.assets.length>MAX_FILES-1)fail("INVALID_ASSET_LIST");
    const entries=[{path:"manifest.json",bytes:utf8Encode(manifestRaw)}];
    if(Object.hasOwn(input,"readme")){const readme=typeof input.readme==="string"?utf8Encode(input.readme):input.readme;if(!(readme instanceof Uint8Array))fail("INVALID_README");entries.push({path:"README.md",bytes:readme.slice()});}
    const seen=new Set(["manifest.json","readme.md"]);
    for(const asset of input.assets){if(!exact(asset,["path","bytes"])||!(asset.bytes instanceof Uint8Array))fail("INVALID_ASSET");validPath(asset.path);const folded=asset.path.toLowerCase();if(seen.has(folded))fail("DUPLICATE_ARCHIVE_PATH");seen.add(folded);entries.push({path:asset.path,bytes:asset.bytes.slice()});}
    entries.sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0);if(entries.length>MAX_FILES)fail("ZIP_FILE_COUNT_LIMIT");
    let total=0;for(const e of entries){if(e.bytes.length>MAX_FILE)fail("ZIP_ENTRY_SIZE_LIMIT");total+=e.bytes.length;if(total>MAX_TOTAL)fail("ZIP_TOTAL_SIZE_LIMIT");}
    const localParts=[],centralParts=[];let localOffset=0;
    for(const e of entries){
      const name=Uint8Array.from(Array.from(e.path).map(c=>c.charCodeAt(0))),crc=crc32(e.bytes);
      const local=new Uint8Array(30+name.length),lv=new DataView(local.buffer);
      put32(lv,0,0x04034b50);put16(lv,4,20);put16(lv,6,0);put16(lv,8,0);put16(lv,10,0);put16(lv,12,0x21);put32(lv,14,crc);put32(lv,18,e.bytes.length);put32(lv,22,e.bytes.length);put16(lv,26,name.length);put16(lv,28,0);local.set(name,30);localParts.push(local,e.bytes);
      const central=new Uint8Array(46+name.length),cv=new DataView(central.buffer);
      put32(cv,0,0x02014b50);put16(cv,4,0x0314);put16(cv,6,20);put16(cv,8,0);put16(cv,10,0);put16(cv,12,0);put16(cv,14,0x21);put32(cv,16,crc);put32(cv,20,e.bytes.length);put32(cv,24,e.bytes.length);put16(cv,28,name.length);put16(cv,30,0);put16(cv,32,0);put16(cv,34,0);put16(cv,36,0);put32(cv,38,0x81a40000);put32(cv,42,localOffset);central.set(name,46);centralParts.push(central);localOffset+=local.length+e.bytes.length;
    }
    const localBytes=concat(localParts),centralBytes=concat(centralParts),eocd=new Uint8Array(22),ev=new DataView(eocd.buffer);
    put32(ev,0,0x06054b50);put16(ev,4,0);put16(ev,6,0);put16(ev,8,entries.length);put16(ev,10,entries.length);put32(ev,12,centralBytes.length);put32(ev,16,localBytes.length);put16(ev,20,0);
    const archive=concat([localBytes,centralBytes,eocd]);if(archive.length>MAX_ARCHIVE)fail("ARCHIVE_SIZE_LIMIT");
    await (options.readMmse||readMmse)(archive,{parseManifest:options.parseManifest,decodeUtf8:options.decodeUtf8,inflateRaw:options.inflateRaw});return archive;
  };
  const createMmseLockfile=async(archives,options={})=>{
    if(!Array.isArray(archives)||archives.length<1||archives.length>64)fail("LOCKFILE_PACKAGE_LIMIT");
    if(!options||typeof options!=="object"||typeof options.parseManifest!=="function")fail("MANIFEST_VALIDATOR_REQUIRED");
    const packages=[],ids=new Set();
    for(const bytes of archives){if(!(bytes instanceof Uint8Array))fail("INVALID_BYTES");const parsed=await readMmse(bytes,{parseManifest:options.parseManifest,decodeUtf8:options.decodeUtf8,inflateRaw:options.inflateRaw});const {id,version}=parsed.manifest;if(ids.has(id))fail("DUPLICATE_PACKAGE");ids.add(id);packages.push({id,version,sha256:sha256Bytes(bytes)});}
    packages.sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);return {schema:2,format:"mmse-1",packages};
  };
  const createAssetIndex=async(archive,options={})=>{
    if(!options||typeof options!=="object"||typeof options.parseManifest!=="function")fail("MANIFEST_VALIDATOR_REQUIRED");
    const parsed=await readMmse(archive,{parseManifest:options.parseManifest,decodeUtf8:options.decodeUtf8,inflateRaw:options.inflateRaw});
    const blobsByHash=new Map(),files=[];
    for(const asset of parsed.assets){
      const hash=sha256Bytes(asset.bytes),existing=blobsByHash.get(hash);
      if(existing){if(existing.length!==asset.bytes.length||existing.some((v,i)=>v!==asset.bytes[i]))fail("HASH_COLLISION");}
      else blobsByHash.set(hash,asset.bytes.slice());
      files.push({path:asset.path,sha256:hash,size:asset.bytes.length});
    }
    files.sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0);
    const blobs=[...blobsByHash.entries()].sort(([a],[b])=>a<b?-1:a>b?1:0).map(([sha256,bytes])=>({sha256,bytes}));
    return {schema:1,algorithm:"sha256",package:{id:parsed.manifest.id,version:parsed.manifest.version},files,blobs};
  };
  const verifyMmseLockfile=async(lockfile,archives,options={})=>{
    if(!exact(lockfile,["schema","format","packages"])||lockfile.schema!==2||lockfile.format!=="mmse-1"||!Array.isArray(lockfile.packages))fail("INVALID_LOCKFILE");
    const expected=await createMmseLockfile(archives,options);if(JSON.stringify(lockfile)!==JSON.stringify(expected))fail("LOCKFILE_MISMATCH");return true;
  };
  return {utf8Encode,sha256Bytes,createMmse,createMmseLockfile,verifyMmseLockfile,createAssetIndex};
};
return makeArchiveWriterTools({crc32,readMmse,sha256Bytes});
})();
const storeApi=(()=>{const {parseManifest,sha256Bytes}=packageApi;const {readMmse}=archiveApi;const {createAssetIndex}=writerApi;
const fail=code=>{throw new Error(code);};
const ROLLBACK_WINDOW_MS=24*60*60*1000;
const cmpVersion=(a,b)=>{const x=a.split(".").map(Number),y=b.split(".").map(Number);for(let i=0;i<3;i++)if(x[i]!==y[i])return x[i]<y[i]?-1:1;return 0;};
const topo=catalog=>{
  const state=new Map(),order=[];
  const visit=id=>{
    const s=state.get(id)||0;if(s===1)fail("DEPENDENCY_CYCLE");if(s===2)return;
    const p=catalog.get(id);if(!p)fail("PACKAGE_NOT_FOUND");state.set(id,1);
    for(const dep of Object.keys(p.dependencies||{}).sort()){const d=catalog.get(dep);if(!d||d.version!==p.dependencies[dep])fail("DEPENDENCY_UNSATISFIED");visit(dep);}
    state.set(id,2);order.push(id);
  };
  for(const id of [...catalog.keys()].sort())visit(id);
  return order;
};
const validateCatalog=catalog=>{
  const order=topo(catalog);
  for(const id of order){const p=catalog.get(id);if(p.active){for(const d of Object.keys(p.dependencies||{}))if(!catalog.get(d)?.active)fail("ACTIVE_DEPENDENCY_NOT_ACTIVE");const grants=new Set(p.grants||[]);for(const perm of p.permissions||[])if(!grants.has(perm))fail("PERMISSION_NOT_GRANTED");}}
  return order;
};

const cloneValue=value=>{if(value instanceof Uint8Array)return value.slice();if(Array.isArray(value))return value.map(cloneValue);if(value&&typeof value==="object"){const out={};for(const [k,v] of Object.entries(value))out[k]=cloneValue(v);return out;}return value;};
class MemoryKVBackend {
  #data=new Map();
  async run(work){
    const draft=new Map([...this.#data.entries()].map(([k,v])=>[k,cloneValue(v)]));let result;
    const api={
      get:(key,cb)=>cb(cloneValue(draft.get(key))),
      scan:(prefix,cb)=>cb([...draft.entries()].filter(([k])=>String(k).startsWith(prefix)).map(([k,v])=>[k,cloneValue(v)])),
      put:(key,value)=>draft.set(key,cloneValue(value)),
      delete:key=>draft.delete(key),
      finish:value=>{result=value;},
      fail:error=>{throw error instanceof Error?error:new Error(String(error));}
    };
    work(api);this.#data=draft;return result;
  }
  async dump(){return new Map([...this.#data.entries()].map(([k,v])=>[k,cloneValue(v)]));}
}

class IndexedDbKVBackend {
  #factory;#name;#dbPromise=null;
  constructor(name="mms-extension-store",factory=typeof indexedDB!=="undefined"?indexedDB:null){this.#name=name;this.#factory=factory;}
  async #open(){
    if(!this.#factory)fail("INDEXEDDB_UNAVAILABLE");
    if(!this.#dbPromise)this.#dbPromise=new Promise((resolve,reject)=>{
      const req=this.#factory.open(this.#name,1);
      req.onupgradeneeded=()=>{const db=req.result;if(!db.objectStoreNames.contains("kv"))db.createObjectStore("kv",{keyPath:"key"});};
      req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error||new Error("INDEXEDDB_OPEN_FAILED"));
    });
    return this.#dbPromise;
  }
  async run(work){
    const db=await this.#open();
    return new Promise((resolve,reject)=>{
      let result,settled=false,abortError=null;
      const tx=db.transaction("kv","readwrite"),store=tx.objectStore("kv");
      const rejectOnce=e=>{if(!settled){settled=true;reject(e instanceof Error?e:new Error(String(e||"INDEXEDDB_TRANSACTION_FAILED")));}};
      const abort=e=>{abortError=e;try{tx.abort();}catch{}rejectOnce(e);};
      const safe=fn=>{try{fn();}catch(e){abort(e);}};
      const api={
        get:(key,cb)=>{const req=store.get(key);req.onsuccess=()=>safe(()=>cb(req.result?.value));req.onerror=()=>abort(req.error);},
        scan:(prefix,cb)=>{const rows=[],req=store.openCursor();req.onsuccess=()=>safe(()=>{const cur=req.result;if(cur){if(String(cur.key).startsWith(prefix))rows.push([cur.key,cur.value.value]);cur.continue();}else cb(rows);});req.onerror=()=>abort(req.error);},
        put:(key,value)=>{store.put({key,value});},
        delete:key=>{store.delete(key);},
        finish:value=>{result=value;},
        fail:error=>abort(error)
      };
      tx.oncomplete=()=>{if(!settled){settled=true;resolve(result);}};
      tx.onerror=()=>abort(tx.error);tx.onabort=()=>rejectOnce(abortError||tx.error||new Error("INDEXEDDB_ABORTED"));
      safe(()=>work(api));
    });
  }
  async close(){if(this.#dbPromise){const db=await this.#dbPromise;db.close();this.#dbPromise=null;}}
}

class PersistentExtensionStore {
  constructor({backend,decodeUtf8,idFactory,now=()=>Date.now(),publisherTrust,requireSignatures=false}={}){
    if(!backend||typeof backend.run!=="function")fail("BACKEND_REQUIRED");
    if(typeof requireSignatures!=="boolean")fail("INVALID_SIGNATURE_POLICY");
    if(publisherTrust!==undefined&&typeof publisherTrust?.verifyPackageSignature!=="function")fail("INVALID_PUBLISHER_TRUST");
    if(requireSignatures&&!publisherTrust)fail("PUBLISHER_TRUST_REQUIRED");
    this.backend=backend;this.decodeUtf8=decodeUtf8;this.idFactory=idFactory||(()=>{const c=globalThis.crypto;if(c&&typeof c.randomUUID==="function")return "tx-"+c.randomUUID();fail("SECURE_RANDOM_UNAVAILABLE");});this.now=now;this.publisherTrust=publisherTrust;this.requireSignatures=requireSignatures;
  }
  #txId(){const id=this.idFactory();if(typeof id!=="string"||!/^tx-[A-Za-z0-9-]{1,80}$/.test(id))fail("INVALID_TRANSACTION_ID");return id;}
  #readOptions(){return {parseManifest,decodeUtf8:this.decodeUtf8};}
  #stage(api,journal,blobs,plan){
    api.get("journal:"+journal.txId,existing=>{
      if(existing){api.fail(new Error("TRANSACTION_ID_COLLISION"));return;}
      for(const blob of blobs)api.put("stage:"+journal.txId+":"+blob.sha256,{sha256:blob.sha256,bytes:blob.bytes.slice()});
      api.put("journal:"+journal.txId,journal);api.finish(plan);
    });
  }
  async prepareInstall(archives,options={}){
    if(!Array.isArray(archives)||archives.length<1||archives.length>32)fail("INVALID_INSTALL_BATCH");
    if(!options||typeof options!=="object"||Array.isArray(options)||Object.keys(options).some(k=>!["upgrade","signatures","certificates","revocations","now"].includes(k))||(options.upgrade!==undefined&&typeof options.upgrade!=="boolean"))fail("INVALID_INSTALL_OPTIONS");
    const upgrade=options.upgrade??false,signatures=options.signatures??{},certificates=options.certificates??{},revocations=options.revocations??[];
    if(!signatures||typeof signatures!=="object"||Array.isArray(signatures)||!certificates||typeof certificates!=="object"||Array.isArray(certificates)||!Array.isArray(revocations))fail("INVALID_SIGNATURE_INPUT");
    const candidates=[],blobMap=new Map(),seen=new Set(),candidateIds=new Set();
    for(const bytes of archives){
      if(!(bytes instanceof Uint8Array))fail("INVALID_ARCHIVE_BYTES");
      const parsed=await readMmse(bytes,this.#readOptions()),m=parsed.manifest;
      if(seen.has(m.id))fail("DUPLICATE_PACKAGE");seen.add(m.id);candidateIds.add(m.id);
      const signature=Object.hasOwn(signatures,m.id)?signatures[m.id]:undefined,certificate=Object.hasOwn(certificates,m.id)?certificates[m.id]:undefined;
      let publisher=null;
      if(this.requireSignatures||signature!==undefined||certificate!==undefined){
        if(!this.publisherTrust)fail("PUBLISHER_TRUST_UNAVAILABLE");
        if(!signature||!certificate)fail("PACKAGE_SIGNATURE_REQUIRED");
        const verification=await this.publisherTrust.verifyPackageSignature({archiveBytes:bytes,manifest:m,signature,certificate,revocations,now:options.now});
        if(!verification||verification.trusted!==true||typeof verification.keyId!=="string"||typeof verification.issuerKeyId!=="string")fail("PUBLISHER_VERIFICATION_FAILED");
        publisher={keyId:verification.keyId,issuerKeyId:verification.issuerKeyId,verifiedAt:this.now(),certificate:JSON.parse(JSON.stringify(certificate)),signature:JSON.parse(JSON.stringify(signature))};
      }
      const index=await createAssetIndex(bytes,this.#readOptions());
      candidates.push({id:m.id,version:m.version,manifestRaw:parsed.manifestRaw,archiveSha256:sha256Bytes(bytes),dependencies:{...m.dependencies},permissions:[...m.permissions],assets:index.files,active:false,grants:[],publisher});
      for(const blob of index.blobs){const prior=blobMap.get(blob.sha256);if(prior&&(prior.length!==blob.bytes.length||prior.some((v,i)=>v!==blob.bytes[i])))fail("HASH_COLLISION");blobMap.set(blob.sha256,blob.bytes.slice());}
    }
    if(Object.keys(signatures).some(id=>!candidateIds.has(id))||Object.keys(certificates).some(id=>!candidateIds.has(id)))fail("UNEXPECTED_PACKAGE_SIGNATURE");
    const blobs=[...blobMap.entries()].map(([sha256,bytes])=>({sha256,bytes}));
    for(const p of candidates)for(const a of p.assets)if(!blobMap.has(a.sha256))fail("ASSET_BLOB_MISSING");
    const txId=this.#txId();
    return this.backend.run(api=>{
      let pending=2,rows,revision;
      const ready=()=>{
        if(--pending!==0)return;
        try{
          const current=new Map(rows.map(([,p])=>[p.id,p])),next=new Map(current),previous=[],nextPackages=[],summary={installed:[],upgraded:[],unchanged:[]};
          for(const candidate of candidates){
            const old=current.get(candidate.id);
            if(old){
              const cmp=cmpVersion(candidate.version,old.version);
              if(cmp===0){if(candidate.archiveSha256!==old.archiveSha256)fail("VERSION_CONTENT_REUSE");summary.unchanged.push(candidate.id);continue;}
              if(cmp<0)fail("DOWNGRADE_REFUSED");
              if(!upgrade)fail("UPGRADE_REQUIRES_FLAG");
              if(old.active&&(candidate.permissions.some(p=>!(old.grants||[]).includes(p))))fail("NEW_PERMISSION_REQUIRES_CONSENT");
              candidate.active=!!old.active;candidate.grants=[...(old.grants||[])];
              summary.upgraded.push({id:candidate.id,from:old.version,to:candidate.version});
            }else summary.installed.push(candidate.id);
            previous.push({id:candidate.id,record:old||null});next.set(candidate.id,candidate);nextPackages.push(candidate);
          }
          if(!nextPackages.length)fail("NO_CHANGES");
          const activationOrder=validateCatalog(next);
          const journal={txId,kind:"install",state:"prepared",baseRevision:revision,createdAt:this.now(),previous,next:nextPackages,removeIds:[],stagedHashes:blobs.map(b=>b.sha256),summary};
          this.#stage(api,journal,blobs,{txId,summary,activationOrder,baseRevision:revision});
        }catch(e){api.fail(e);}
      };
      api.scan("pkg:",v=>{rows=v;ready();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;ready();});
    });
  }
  async prepareUninstall(ids){
    if(!Array.isArray(ids)||ids.length<1||ids.length>32||new Set(ids).size!==ids.length||ids.some(x=>typeof x!=="string"))fail("INVALID_UNINSTALL_BATCH");
    const txId=this.#txId();
    return this.backend.run(api=>{
      let pending=2,rows,revision;
      const ready=()=>{
        if(--pending!==0)return;
        try{
          const current=new Map(rows.map(([,p])=>[p.id,p])),remaining=new Map(current);
          for(const id of ids){if(!current.has(id))fail("PACKAGE_NOT_FOUND");remaining.delete(id);}
          const activationOrder=validateCatalog(remaining),previous=ids.map(id=>({id,record:current.get(id)}));
          const summary={removed:[...ids].sort()},journal={txId,kind:"uninstall",state:"prepared",baseRevision:revision,createdAt:this.now(),previous,next:[],removeIds:[...ids],stagedHashes:[],summary};
          this.#stage(api,journal,[],{txId,summary,activationOrder,baseRevision:revision});
        }catch(e){api.fail(e);}
      };
      api.scan("pkg:",v=>{rows=v;ready();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;ready();});
    });
  }
  async commit(txId,options={}){
    if(!options||options.approved!==true)fail("APPROVAL_REQUIRED");
    return this.backend.run(api=>{
      let pending=2,journal,revision;
      const begin=()=>{
        if(--pending!==0)return;
        try{
          if(!journal)fail("JOURNAL_NOT_FOUND");if(journal.state!=="prepared")fail("JOURNAL_NOT_PREPARED");
          if(revision!==journal.baseRevision)fail("STALE_PLAN");
          const staged=[],hashes=journal.stagedHashes||[];
          const apply=()=>{
            for(const b of staged){if(sha256Bytes(b.bytes)!==b.sha256)fail("STAGED_BLOB_HASH_MISMATCH");api.put("blob:"+b.sha256,b);api.delete("stage:"+txId+":"+b.sha256);}
            for(const p of journal.next||[])api.put("pkg:"+p.id,p);
            for(const id of journal.removeIds||[])api.delete("pkg:"+id);
            const nextRevision=revision+1,committedAt=this.now(),committed={...journal,state:"committed",commitRevision:nextRevision,committedAt,rollbackExpiresAt:committedAt+ROLLBACK_WINDOW_MS};
            api.put("journal:"+txId,committed);api.put("meta:revision",nextRevision);api.finish({txId,revision:nextRevision,summary:journal.summary});
          };
          if(!hashes.length){apply();return;}
          let left=hashes.length;
          for(const hash of hashes)api.get("stage:"+txId+":"+hash,b=>{if(!b){api.fail(new Error("STAGED_BLOB_MISSING"));return;}staged.push(b);if(--left===0){try{apply();}catch(e){api.fail(e);}}});
        }catch(e){api.fail(e);}
      };
      api.get("journal:"+txId,v=>{journal=v;begin();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;begin();});
    });
  }
  async rollback(txId,options={}){
    if(!options||options.approved!==true)fail("APPROVAL_REQUIRED");
    return this.backend.run(api=>{
      let pending=2,journal,revision;
      const apply=()=>{
        try{
          if(!journal)fail("JOURNAL_NOT_FOUND");if(journal.state!=="committed")fail("JOURNAL_NOT_COMMITTED");
          if(revision!==journal.commitRevision)fail("STALE_RECEIPT");
          if(!Number.isFinite(journal.rollbackExpiresAt)||this.now()>journal.rollbackExpiresAt)fail("ROLLBACK_EXPIRED");
          for(const p of journal.previous){if(p.record)api.put("pkg:"+p.id,p.record);else api.delete("pkg:"+p.id);}
          const nextRevision=revision+1;api.put("journal:"+txId,{...journal,state:"rolled_back",rollbackRevision:nextRevision,rolledBackAt:this.now()});api.put("meta:revision",nextRevision);api.finish({txId,revision:nextRevision,state:"rolled_back"});
        }catch(e){api.fail(e);}
      };
      const begin=()=>{
        if(--pending!==0)return;
        try{
          if(!journal)fail("JOURNAL_NOT_FOUND");if(journal.state!=="committed")fail("JOURNAL_NOT_COMMITTED");
          if(revision!==journal.commitRevision)fail("STALE_RECEIPT");
          if(!Number.isFinite(journal.rollbackExpiresAt)||this.now()>journal.rollbackExpiresAt)fail("ROLLBACK_EXPIRED");
          const hashes=[...new Set((journal.previous||[]).flatMap(p=>(p.record?.assets||[]).map(a=>a.sha256)))];
          if(!hashes.length){apply();return;}
          let left=hashes.length;
          for(const hash of hashes)api.get("blob:"+hash,b=>{if(!b){api.fail(new Error("ROLLBACK_BLOB_MISSING"));return;}if(--left===0)apply();});
        }catch(e){api.fail(e);}
      };
      api.get("journal:"+txId,v=>{journal=v;begin();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;begin();});
    });
  }
  async recover(){
    return this.backend.run(api=>api.scan("journal:",rows=>{
      let aborted=0;
      for(const [key,j] of rows){if(j.state!=="prepared")continue;for(const hash of j.stagedHashes||[])api.delete("stage:"+j.txId+":"+hash);api.put(key,{...j,state:"aborted",abortedAt:this.now()});aborted++;}
      api.finish({aborted});
    }));
  }
  async listPackages(){return this.backend.run(api=>api.scan("pkg:",rows=>api.finish(rows.map(([,p])=>p).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0))));}
  async getBlob(hash){return this.backend.run(api=>api.get("blob:"+hash,b=>api.finish(b?b.bytes.slice():null)));}
  async enableClosure(id,grantsById){
    if(!grantsById||typeof grantsById!=="object"||Array.isArray(grantsById))fail("INVALID_GRANT_MAP");
    return this.backend.run(api=>{
      let pending=2,rows,revision;
      const ready=()=>{
        if(--pending!==0)return;
        try{
          const catalog=new Map(rows.map(([,p])=>[p.id,p])),closure=new Set();
          const collect=k=>{if(closure.has(k))return;const p=catalog.get(k);if(!p)fail("PACKAGE_NOT_FOUND");closure.add(k);for(const d of Object.keys(p.dependencies||{}))collect(d);};collect(id);
          if(Object.keys(grantsById).some(k=>!closure.has(k)))fail("UNEXPECTED_GRANT_ENTRY");
          const order=topo(catalog).filter(k=>closure.has(k)),enabled=[];
          for(const k of order){const p=catalog.get(k);if(p.active)continue;const grants=grantsById[k],required=p.permissions||[];if(!Array.isArray(grants)||new Set(grants).size!==grants.length||grants.length!==required.length||required.some(x=>!grants.includes(x))||grants.some(x=>!required.includes(x)))fail("PERMISSION_DENIED");p.active=true;p.grants=[...grants].sort();api.put("pkg:"+k,p);enabled.push(k);}
          if(!enabled.length)fail("ALREADY_ACTIVE");
          validateCatalog(catalog);const nextRevision=revision+1;api.put("meta:revision",nextRevision);api.finish({enabled,generation:nextRevision});
        }catch(e){api.fail(e);}
      };
      api.scan("pkg:",v=>{rows=v;ready();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;ready();});
    });
  }
  async disable(id){
    return this.backend.run(api=>{
      let pending=2,rows,revision;
      const ready=()=>{
        if(--pending!==0)return;
        try{
          const catalog=new Map(rows.map(([,p])=>[p.id,p])),p=catalog.get(id);if(!p)fail("PACKAGE_NOT_FOUND");if(!p.active)fail("NOT_ACTIVE");
          for(const [other,q] of catalog)if(other!==id&&q.active&&Object.hasOwn(q.dependencies||{},id))fail("ACTIVE_DEPENDENT");
          p.active=false;p.grants=[];validateCatalog(catalog);const nextRevision=revision+1;api.put("pkg:"+id,p);api.put("meta:revision",nextRevision);api.finish({id,active:false,generation:nextRevision});
        }catch(e){api.fail(e);}
      };
      api.scan("pkg:",v=>{rows=v;ready();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;ready();});
    });
  }
  async collectGarbage(){
    return this.backend.run(api=>{
      let pending=4,packages,blobs,journals,revision;
      const ready=()=>{
        if(--pending!==0)return;
        const used=new Set();
        for(const p of packages)for(const a of p.assets||[])used.add(a.sha256);
        const now=this.now();
        for(const [,journal] of journals){
          if(journal.state!=="committed"||journal.commitRevision!==revision||!Number.isFinite(journal.rollbackExpiresAt)||now>journal.rollbackExpiresAt)continue;
          for(const previous of journal.previous||[])for(const asset of previous.record?.assets||[])used.add(asset.sha256);
        }
        let removed=0;for(const [key,b] of blobs)if(!used.has(b.sha256)){api.delete(key);removed++;}
        api.finish({removed,retained:blobs.length-removed});
      };
      api.scan("pkg:",rows=>{packages=rows.map(([,p])=>p);ready();});
      api.scan("blob:",rows=>{blobs=rows;ready();});
      api.scan("journal:",rows=>{journals=rows;ready();});
      api.get("meta:revision",value=>{revision=Number.isInteger(value)?value:0;ready();});
    });
  }
}

return {MemoryKVBackend,IndexedDbKVBackend,PersistentExtensionStore};})();
const trustApi=(()=>{const {sha256Bytes}=packageApi;
const fail=code=>{throw new Error(code);};
const exact=(v,keys)=>!!v&&typeof v==="object"&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const validId=v=>typeof v==="string"&&/^[a-z][a-z0-9-]{0,47}$/.test(v)&&!["constructor","prototype"].includes(v);
const validVersion=v=>typeof v==="string"&&v.length<=32&&/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(v)&&v.split(".").every(x=>Number.isSafeInteger(Number(x)));
const validHash=v=>typeof v==="string"&&/^[0-9a-f]{64}$/.test(v);
const validKeyId=validHash;
const validTime=v=>Number.isSafeInteger(v)&&v>=0;
const alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const encode64=bytes=>{
  let out="";
  for(let i=0;i<bytes.length;i+=3){
    const a=bytes[i],hasB=i+1<bytes.length,hasC=i+2<bytes.length,b=hasB?bytes[i+1]:0,c=hasC?bytes[i+2]:0;
    out+=alphabet[a>>2]+alphabet[((a&3)<<4)|(b>>4)]+(hasB?alphabet[((b&15)<<2)|(c>>6)]:"=")+(hasC?alphabet[c&63]:"=");
  }
  return out;
};
const decode64=value=>{
  if(typeof value!=="string"||value.length===0||value.length%4!==0||!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value))fail("INVALID_BASE64");
  const out=[];
  for(let i=0;i<value.length;i+=4){
    const a=alphabet.indexOf(value[i]),b=alphabet.indexOf(value[i+1]),c=value[i+2]==="="?0:alphabet.indexOf(value[i+2]),d=value[i+3]==="="?0:alphabet.indexOf(value[i+3]);
    out.push((a<<2)|(b>>4));
    if(value[i+2]!=="=")out.push(((b&15)<<4)|(c>>2));
    if(value[i+3]!=="=")out.push(((c&3)<<6)|d);
  }
  const bytes=Uint8Array.from(out);
  if(encode64(bytes)!==value)fail("INVALID_BASE64");
  return bytes;
};
const utf8=value=>new TextEncoder().encode(value);
const certPayload=c=>utf8([
  "MMS-EXT-KEY-CERT-V1",
  "issuer="+c.issuerKeyId,
  "subject="+c.subjectKeyId,
  "publicKey="+c.publicKey,
  "notBefore="+c.notBefore,
  "notAfter="+c.notAfter,
  "packageScopes="+c.packageScopes.join(","),
  ""
].join("\n"));
const revocationPayload=r=>utf8([
  "MMS-EXT-KEY-REVOCATION-V1",
  "issuer="+r.issuerKeyId,
  "target="+r.targetKeyId,
  "revokedAt="+r.revokedAt,
  "reason="+r.reasonCode,
  ""
].join("\n"));
const packagePayload=sig=>utf8([
  "MMS-EXT-PACKAGE-SIGNATURE-V1",
  "format=mmse-1",
  "packageId="+sig.packageId,
  "version="+sig.version,
  "archiveSha256="+sig.archiveSha256,
  "keyId="+sig.keyId,
  ""
].join("\n"));
const reasons=new Set(["COMPROMISED","ROTATED","RETIRED","POLICY_VIOLATION"]);
const validateScopes=scopes=>{
  if(!Array.isArray(scopes)||scopes.length<1||scopes.length>128||scopes.some(x=>!validId(x)))fail("INVALID_PACKAGE_SCOPES");
  const sorted=[...new Set(scopes)].sort();
  if(sorted.length!==scopes.length||sorted.some((x,i)=>x!==scopes[i]))fail("NON_CANONICAL_PACKAGE_SCOPES");
  return sorted;
};

const createPublisherTrust=({trustRoots,cryptoProvider=globalThis.crypto,hashBytes=sha256Bytes}={})=>{
  if(!Array.isArray(trustRoots)||trustRoots.length<1||trustRoots.length>32)fail("TRUST_ROOTS_REQUIRED");
  const subtle=()=>{const s=cryptoProvider?.subtle;if(!s||typeof s.importKey!=="function"||typeof s.verify!=="function"||typeof s.sign!=="function")fail("WEBCRYPTO_UNAVAILABLE");return s;};
  const roots=new Map();
  for(const root of trustRoots){
    if(!exact(root,["keyId","publicKey","packageScopes"])||!validKeyId(root.keyId)||!(root.publicKey instanceof Uint8Array)||root.publicKey.length!==32)fail("INVALID_TRUST_ROOT");
    validateScopes(root.packageScopes);
    if(roots.has(root.keyId))fail("DUPLICATE_TRUST_ROOT");
    roots.set(root.keyId,{keyId:root.keyId,publicKey:root.publicKey.slice(),packageScopes:[...root.packageScopes]});
  }
  const nowSeconds=now=>now===undefined?Math.floor(Date.now()/1000):validTime(now)?now:fail("INVALID_TIME");
  const publicKeyId=async bytes=>{
    if(!(bytes instanceof Uint8Array)||bytes.length!==32)fail("INVALID_PUBLIC_KEY");
    return hashBytes(bytes);
  };
  const rootFor=async keyId=>{
    const root=roots.get(keyId);if(!root)fail("UNTRUSTED_ISSUER");
    if(await publicKeyId(root.publicKey)!==root.keyId)fail("TRUST_ROOT_KEY_ID_MISMATCH");
    return root;
  };
  const importVerifyKey=async raw=>{
    if(!(raw instanceof Uint8Array)||raw.length!==32)fail("INVALID_PUBLIC_KEY");
    const api=subtle();try{return await api.importKey("raw",raw,{name:"Ed25519"},false,["verify"]);}catch{fail("ED25519_IMPORT_FAILED");}
  };
  const sign=async(privateKey,payload)=>{
    if(!privateKey)fail("PRIVATE_KEY_REQUIRED");
    try{return new Uint8Array(await subtle().sign({name:"Ed25519"},privateKey,payload));}catch{fail("ED25519_SIGN_FAILED");}
  };
  const verify=async(publicKey,signature,payload)=>{
    if(!(signature instanceof Uint8Array)||signature.length!==64)fail("INVALID_SIGNATURE_BYTES");
    const key=await importVerifyKey(publicKey);
    try{if(!await subtle().verify({name:"Ed25519"},key,signature,payload))fail("SIGNATURE_INVALID");}catch(e){if(e?.message==="SIGNATURE_INVALID")throw e;fail("ED25519_VERIFY_FAILED");}
    return true;
  };
  const assertRootScope=(root,scopes)=>{
    for(const id of scopes)if(!root.packageScopes.includes(id))fail("ROOT_SCOPE_EXCEEDED");
  };
  const createKeyCertificate=async({issuerKeyId,subjectPublicKey,notBefore,notAfter,packageScopes,issuerPrivateKey}={})=>{
    if(!validKeyId(issuerKeyId))fail("INVALID_ISSUER_KEY_ID");
    const root=await rootFor(issuerKeyId),scopes=validateScopes(packageScopes),start=nowSeconds(notBefore),end=nowSeconds(notAfter);
    if(start>=end)fail("INVALID_CERTIFICATE_VALIDITY");
    assertRootScope(root,scopes);
    const subjectKeyId=await publicKeyId(subjectPublicKey),unsigned={schema:1,algorithm:"Ed25519",issuerKeyId,subjectKeyId,publicKey:encode64(subjectPublicKey),notBefore:start,notAfter:end,packageScopes:scopes};
    return {...unsigned,signature:encode64(await sign(issuerPrivateKey,certPayload(unsigned)))};
  };
  const verifyCertificate=async(certificate,{packageId,now}={})=>{
    if(!exact(certificate,["schema","algorithm","issuerKeyId","subjectKeyId","publicKey","notBefore","notAfter","packageScopes","signature"])||certificate.schema!==1||certificate.algorithm!=="Ed25519")fail("INVALID_KEY_CERTIFICATE");
    if(!validKeyId(certificate.issuerKeyId)||!validKeyId(certificate.subjectKeyId))fail("INVALID_KEY_ID");
    if(!validTime(certificate.notBefore)||!validTime(certificate.notAfter)||certificate.notBefore>=certificate.notAfter)fail("INVALID_CERTIFICATE_VALIDITY");
    const current=nowSeconds(now);if(current<certificate.notBefore)fail("CERTIFICATE_NOT_YET_VALID");if(current>=certificate.notAfter)fail("CERTIFICATE_EXPIRED");
    const scopes=validateScopes(certificate.packageScopes);
    if(packageId!==undefined&&(!validId(packageId)||!scopes.includes(packageId)))fail("PACKAGE_OUTSIDE_CERTIFICATE_SCOPE");
    const root=await rootFor(certificate.issuerKeyId);assertRootScope(root,scopes);
    const publicKey=decode64(certificate.publicKey),signature=decode64(certificate.signature);
    if(await publicKeyId(publicKey)!==certificate.subjectKeyId)fail("SUBJECT_KEY_ID_MISMATCH");
    await verify(root.publicKey,signature,certPayload(certificate));
    return {keyId:certificate.subjectKeyId,issuerKeyId:certificate.issuerKeyId,publicKey,packageScopes:scopes,notBefore:certificate.notBefore,notAfter:certificate.notAfter};
  };
  const createRevocation=async({issuerKeyId,targetKeyId,revokedAt,reasonCode,issuerPrivateKey}={})=>{
    if(!validKeyId(issuerKeyId)||!validKeyId(targetKeyId))fail("INVALID_KEY_ID");
    await rootFor(issuerKeyId);const time=nowSeconds(revokedAt);
    if(!reasons.has(reasonCode))fail("INVALID_REVOCATION_REASON");
    const unsigned={schema:1,algorithm:"Ed25519",issuerKeyId,targetKeyId,revokedAt:time,reasonCode};
    return {...unsigned,signature:encode64(await sign(issuerPrivateKey,revocationPayload(unsigned)))};
  };
  const verifyRevocation=async(r)=>{
    if(!exact(r,["schema","algorithm","issuerKeyId","targetKeyId","revokedAt","reasonCode","signature"])||r.schema!==1||r.algorithm!=="Ed25519")fail("INVALID_REVOCATION");
    if(!validKeyId(r.issuerKeyId)||!validKeyId(r.targetKeyId)||!validTime(r.revokedAt)||!reasons.has(r.reasonCode))fail("INVALID_REVOCATION");
    const root=await rootFor(r.issuerKeyId);
    await verify(root.publicKey,decode64(r.signature),revocationPayload(r));
    return r;
  };
  const createPackageSignature=async({archiveBytes,manifest,keyId,privateKey}={})=>{
    if(!(archiveBytes instanceof Uint8Array))fail("INVALID_ARCHIVE_BYTES");
    if(!manifest||!validId(manifest.id)||!validVersion(manifest.version)||!validKeyId(keyId))fail("INVALID_PACKAGE_IDENTITY");
    const unsigned={schema:1,algorithm:"Ed25519",keyId,packageId:manifest.id,version:manifest.version,archiveSha256:hashBytes(archiveBytes)};
    return {...unsigned,signature:encode64(await sign(privateKey,packagePayload(unsigned)))};
  };
  const verifyPackageSignature=async({archiveBytes,manifest,signature,certificate,revocations=[],now}={})=>{
    if(!(archiveBytes instanceof Uint8Array))fail("INVALID_ARCHIVE_BYTES");
    if(!manifest||!validId(manifest.id)||!validVersion(manifest.version))fail("INVALID_PACKAGE_IDENTITY");
    if(!exact(signature,["schema","algorithm","keyId","packageId","version","archiveSha256","signature"])||signature.schema!==1||signature.algorithm!=="Ed25519")fail("INVALID_PACKAGE_SIGNATURE");
    if(!validKeyId(signature.keyId)||!validId(signature.packageId)||!validVersion(signature.version)||!validHash(signature.archiveSha256))fail("INVALID_PACKAGE_SIGNATURE");
    if(signature.packageId!==manifest.id||signature.version!==manifest.version)fail("PACKAGE_IDENTITY_MISMATCH");
    const digest=hashBytes(archiveBytes);if(signature.archiveSha256!==digest)fail("ARCHIVE_DIGEST_MISMATCH");
    const cert=await verifyCertificate(certificate,{packageId:manifest.id,now});
    if(signature.keyId!==cert.keyId)fail("SIGNER_CERTIFICATE_MISMATCH");
    if(!Array.isArray(revocations)||revocations.length>256)fail("INVALID_REVOCATION_LIST");
    const current=nowSeconds(now);
    for(const r of revocations){
      await verifyRevocation(r);
      if(r.targetKeyId===cert.keyId&&r.issuerKeyId===cert.issuerKeyId&&r.revokedAt<=current)fail("SIGNING_KEY_REVOKED");
    }
    await verify(cert.publicKey,decode64(signature.signature),packagePayload(signature));
    return {trusted:true,keyId:cert.keyId,issuerKeyId:cert.issuerKeyId,packageId:manifest.id,version:manifest.version,archiveSha256:digest};
  };
  return {publicKeyId,createKeyCertificate,verifyCertificate,createRevocation,verifyRevocation,createPackageSignature,verifyPackageSignature};
};

return {createPublisherTrust};})();
const hostApi=(()=>{const fail=(code,details)=>{const error=new Error(code);if(details!==undefined)error.details=details;throw error;};
const clone=value=>JSON.parse(JSON.stringify(value));
const record=value=>!!value&&typeof value==="object"&&!Array.isArray(value);

const createV25HostBridge=({core,getProject,replaceProject,onProjectChanged=()=>{},isEnabled=()=>false}={})=>{
  if(!record(core)||typeof core.migrate!=="function"||typeof core.encode!=="function"||typeof core.validate!=="function")fail("INVALID_V25_CORE");
  if(typeof getProject!=="function"||typeof replaceProject!=="function"||typeof onProjectChanged!=="function"||typeof isEnabled!=="function")fail("INVALID_HOST_CALLBACKS");
  if([core.migrate,core.encode,core.validate,getProject,replaceProject,onProjectChanged,isEnabled].some(fn=>fn.constructor?.name==="AsyncFunction"))fail("ASYNC_HOST_CALLBACK_UNSUPPORTED");
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

return {createV25HostBridge};})();
const fail=code=>{throw new Error(code);};
const validateRecipeContribution=data=>{
 if(!data||typeof data!=="object"||Array.isArray(data))fail("INVALID_RECIPE_CONTRIBUTION");
 const allowed=["name","description","ingredients"];
 if(Object.keys(data).some(k=>!allowed.includes(k)))fail("INVALID_RECIPE_FIELDS");
 if(typeof data.name!=="string"||!data.name.trim()||data.name.length>80)fail("INVALID_RECIPE_NAME");
 if(data.description!==undefined&&(typeof data.description!=="string"||data.description.length>240))fail("INVALID_RECIPE_DESCRIPTION");
 if(!Array.isArray(data.ingredients)||data.ingredients.length!==9)fail("INVALID_RECIPE_INGREDIENTS");
 const ingredients=data.ingredients.map(value=>{
  if(value==="")return "";
  if(typeof value!=="string")fail("INVALID_RECIPE_INGREDIENT_ID");
  if(value.startsWith("@item:")){
   const uid=value.slice(6);
   if(!uid||uid.length>500||Object.prototype.hasOwnProperty.call(Object.prototype,uid))fail("INVALID_RECIPE_INTERNAL_ID");
   return value;
  }
  if(value.length>193||!/^[a-z0-9_.-]{1,64}:[a-z0-9_./-]{1,128}$/.test(value))fail("INVALID_RECIPE_INGREDIENT_ID");
  const path=value.split(":")[1];if(path.startsWith("/")||path.endsWith("/")||path.split("/").some(x=>!x||x==="."||x===".."))fail("INVALID_RECIPE_INGREDIENT_ID");
  return value;
 });
 return {name:data.name.trim(),description:data.description||"",ingredients};
};
const collectRecipeContributions=packages=>{
 if(!Array.isArray(packages))fail("INVALID_PACKAGE_LIST");
 const out=[];
 for(const pkg of packages){if(pkg?.active!==true||typeof pkg.manifestRaw!=="string")continue;
  const manifest=packageApi.parseManifest(pkg.manifestRaw);
  for(const contribution of manifest.contributes){if(contribution.type!=="recipe")continue;
   try{out.push({packageId:pkg.id,packageVersion:pkg.version,contributionId:contribution.id,data:validateRecipeContribution(contribution.data),publisher:pkg.publisher||null});}
   catch(error){out.push({packageId:pkg.id,packageVersion:pkg.version,contributionId:contribution.id,error:error.message,data:null,publisher:pkg.publisher||null});}
  }
 }
 return out;
};
const stageRecipeMutation=(bridge,{itemUid,packageId,contributionId,data}={})=>{
 if(!bridge||typeof bridge.stageMutation!=="function")fail("HOST_BRIDGE_REQUIRED");
 if(typeof itemUid!=="string"||!itemUid)fail("ITEM_UID_REQUIRED");
 const recipe=validateRecipeContribution(data);
 return bridge.stageMutation(candidate=>{
  const target=candidate.items.find(x=>x.uid===itemUid);if(!target)fail("TARGET_ITEM_NOT_FOUND");
  for(const value of recipe.ingredients)if(value.startsWith("@item:")&&!candidate.items.some(x=>x.uid===value.slice(6)))fail("RECIPE_INTERNAL_ITEM_NOT_FOUND");
  target.recipe=[...recipe.ingredients];return candidate;
 },{type:"recipe-template",packageId,contributionId,itemUid,recipeName:recipe.name});
};
window.MMSV25ExtensionRuntime=Object.freeze({
 ...packageApi,...archiveApi,...writerApi,...storeApi,...trustApi,...hostApi,
 validateRecipeContribution,collectRecipeContributions,stageRecipeMutation
});
})();
