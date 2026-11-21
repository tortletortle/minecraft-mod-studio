const makeArchiveTools = () => {
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
export const {crc32,readMmse}=makeArchiveTools();
