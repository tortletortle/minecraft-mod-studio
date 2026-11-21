import {parseManifest,sha256Bytes} from './package-manager.mjs';
import {readMmse} from './archive.mjs';
import {createAssetIndex} from './archive-writer.mjs';

const fail=code=>{throw new Error(code);};
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
export class MemoryKVBackend {
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

export class IndexedDbKVBackend {
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

export class PersistentExtensionStore {
  constructor({backend,decodeUtf8,idFactory,now=()=>Date.now()}={}){
    if(!backend||typeof backend.run!=="function")fail("BACKEND_REQUIRED");
    this.backend=backend;this.decodeUtf8=decodeUtf8;this.idFactory=idFactory||(()=>{const c=globalThis.crypto;if(c&&typeof c.randomUUID==="function")return "tx-"+c.randomUUID();fail("SECURE_RANDOM_UNAVAILABLE");});this.now=now;
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
    if(!options||typeof options!=="object"||Array.isArray(options)||Object.keys(options).some(k=>k!=="upgrade")||(options.upgrade!==undefined&&typeof options.upgrade!=="boolean"))fail("INVALID_INSTALL_OPTIONS");
    const upgrade=options.upgrade??false,candidates=[],blobMap=new Map(),seen=new Set();
    for(const bytes of archives){
      if(!(bytes instanceof Uint8Array))fail("INVALID_ARCHIVE_BYTES");
      const parsed=await readMmse(bytes,this.#readOptions()),index=await createAssetIndex(bytes,this.#readOptions()),m=parsed.manifest;
      if(seen.has(m.id))fail("DUPLICATE_PACKAGE");seen.add(m.id);
      candidates.push({id:m.id,version:m.version,manifestRaw:parsed.manifestRaw,archiveSha256:sha256Bytes(bytes),dependencies:{...m.dependencies},permissions:[...m.permissions],assets:index.files,active:false,grants:[]});
      for(const blob of index.blobs){const prior=blobMap.get(blob.sha256);if(prior&&(prior.length!==blob.bytes.length||prior.some((v,i)=>v!==blob.bytes[i])))fail("HASH_COLLISION");blobMap.set(blob.sha256,blob.bytes.slice());}
    }
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
            const nextRevision=revision+1,committed={...journal,state:"committed",commitRevision:nextRevision,committedAt:this.now()};
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
        if(--pending!==0)return;
        try{
          if(!journal)fail("JOURNAL_NOT_FOUND");if(journal.state!=="committed")fail("JOURNAL_NOT_COMMITTED");
          if(revision!==journal.commitRevision)fail("STALE_RECEIPT");
          for(const p of journal.previous){if(p.record)api.put("pkg:"+p.id,p.record);else api.delete("pkg:"+p.id);}
          const nextRevision=revision+1;api.put("journal:"+txId,{...journal,state:"rolled_back",rollbackRevision:nextRevision,rolledBackAt:this.now()});api.put("meta:revision",nextRevision);api.finish({txId,revision:nextRevision,state:"rolled_back"});
        }catch(e){api.fail(e);}
      };
      api.get("journal:"+txId,v=>{journal=v;apply();});api.get("meta:revision",v=>{revision=Number.isInteger(v)?v:0;apply();});
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
      let pending=2,packages,blobs;
      const ready=()=>{
        if(--pending!==0)return;
        const used=new Set();for(const p of packages)for(const a of p.assets||[])used.add(a.sha256);
        let removed=0;for(const [key,b] of blobs)if(!used.has(b.sha256)){api.delete(key);removed++;}
        api.finish({removed,retained:blobs.length-removed});
      };
      api.scan("pkg:",rows=>{packages=rows.map(([,p])=>p);ready();});api.scan("blob:",rows=>{blobs=rows;ready();});
    });
  }
}
