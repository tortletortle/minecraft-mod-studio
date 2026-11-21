import {crc32,readMmse} from './archive.mjs';
import {sha256Bytes} from './package-manager.mjs';
const makeArchiveWriterTools = ({crc32,readMmse,sha256Bytes}) => {
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
  const verifyMmseLockfile=async(lockfile,archives,options={})=>{
    if(!exact(lockfile,["schema","format","packages"])||lockfile.schema!==2||lockfile.format!=="mmse-1"||!Array.isArray(lockfile.packages))fail("INVALID_LOCKFILE");
    const expected=await createMmseLockfile(archives,options);if(JSON.stringify(lockfile)!==JSON.stringify(expected))fail("LOCKFILE_MISMATCH");return true;
  };
  return {utf8Encode,sha256Bytes,createMmse,createMmseLockfile,verifyMmseLockfile};
};
export const {utf8Encode,sha256Bytes:hashBytes,createMmse,createMmseLockfile,verifyMmseLockfile}=makeArchiveWriterTools({crc32,readMmse,sha256Bytes});
