import * as core from './core.mjs';
import {createPack} from './pack.mjs';
function readNBT(bytes){
  const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let i=0;
  const b=()=>v.getUint8(i++),n=()=>{const x=v.getInt32(i,false);i+=4;return x;},str=()=>{const len=v.getUint16(i,false);i+=2;let s="";for(let j=0;j<len;j++)s+=String.fromCharCode(b());return s;};
  function parse(type){switch(type){case 3:return n();case 8:return str();case 9:{const t=b(),length=n();if(length<0||length>200000)throw Error("bad list length");return Array.from({length},()=>parse(t));}case 10:{const o={};for(let t=b();t!==0;t=b()){const name=str();o[name]=parse(t);}return o;}default:throw Error("unsupported tag "+type);}}
  if(b()!==10||str()!=="")throw Error("bad root");const obj=parse(10);if(i!==bytes.length)throw Error("trailing bytes");return obj;
}

function packSuite(core,createPack,readNBT){
 let count=0;const check=(ok,msg)=>{if(!ok)throw Error(msg);count++;};const eq=(a,b,m)=>check(JSON.stringify(a)===JSON.stringify(b),m);const throws=(fn)=>{let yes=false;try{fn();}catch{yes=true;}check(yes,"expected rejection");};
 const g={spacing:24,separation:6,salt:1234,biomes:["minecraft:plains","minecraft:forest","minecraft:plains"],heightOffset:-1};
 for(const seed of [0,1,42,4294967295]){
  const options={namespace:"mms_test",buildings:[{id:"home",preset:"house",seed},{id:"tower",preset:"tower",seed},{id:"works",preset:"factory",seed,worldgen:g}]};
  const {files,report}=createPack(options);const j=p=>JSON.parse(files.get(p)),base="data/mms_test/";
  eq([...files.keys()].sort(),["pack.mcmeta",base+"structure/home.nbt",base+"structure/tower.nbt",base+"structure/works.nbt",base+"worldgen/template_pool/works.json",base+"worldgen/structure/works.json",base+"worldgen/structure_set/works.json",base+"tags/worldgen/biome/works.json"].sort(),"file inventory");
  eq(j("pack.mcmeta").pack.min_format,[107,1],"pack version");eq(j("pack.mcmeta").pack.max_format,[107,1],"max version");
  for(const {id,preset} of options.buildings){const nbt=readNBT(files.get(base+"structure/"+id+".nbt"));eq(nbt.DataVersion,4903,"version");eq(nbt.size,core.generate({preset,seed}).size,"size");check(nbt.blocks.every(x=>x.state>=0&&x.state<nbt.palette.length),"palette indexes");}
  const wg=j(base+"worldgen/structure/works.json"),pool=j(base+"worldgen/template_pool/works.json"),set=j(base+"worldgen/structure_set/works.json");
  eq(wg.start_pool,"mms_test:works","pool reference");eq(wg.biomes,"#mms_test:works","biome tag");eq(pool.elements[0].element.location,"mms_test:works","template reference");eq(set.structures[0].structure,"mms_test:works","structure reference");eq(set.placement.spacing,24,"spacing");eq(set.placement.separation,6,"separation");eq(set.placement.salt,1234,"salt");eq(wg.start_height.absolute,-1,"offset");eq(wg.size,0,"single piece");eq(j(base+"tags/worldgen/biome/works.json").values,["minecraft:plains","minecraft:forest"],"dedup biomes");eq(report.buildings.map(x=>x.worldgen),[false,false,true],"opt-in");eq(report.buildings[2].locateCommand,"/locate structure mms_test:works","locate");
  eq([...createPack(options).files].map(([k,v])=>[k,typeof v==="string"?v:[...v]]),[...files].map(([k,v])=>[k,typeof v==="string"?v:[...v]]),"deterministic pack");
 }
 for(const ns of ["../evil","minecraft","a/b","bad:ns","UPPER"])throws(()=>createPack({namespace:ns,buildings:[{id:"house"}]}));
 for(const id of ["..","a/b","a\\b","UPPER"])throws(()=>createPack({buildings:[{id}]}));
 for(const worldgen of [{salt:0,spacing:8,separation:8},{salt:-1},{salt:4,biomes:[]},{salt:4,biomes:["bad"]},true])throws(()=>createPack({buildings:[{id:"a",worldgen}]}));
 throws(()=>createPack({buildings:[{id:"a"},{id:"a"}]}));throws(()=>createPack({buildings:[{id:"a",worldgen:{salt:1}},{id:"b",worldgen:{salt:1}}]}));throws(()=>createPack({buildings:[]}));
 for(let h=9;h<=48;h++){const s=core.generate({preset:"tower",size:[11,h,11]});const map=new Map(s.blocks.map(c=>[c.pos.join(","),c.block.name]));for(const r of s.metadata.rooms.slice(1)){const [x,y,z]=r.pos;eq(map.get([x,y-1,z].join(",")),"minecraft:cobbled_deepslate","landing solid floor");eq(map.get([x,y,z].join(",")),"minecraft:air","feet");eq(map.get([x,y+1,z].join(",")),"minecraft:air","head");eq(map.get([x-1,y,z].join(",")),"minecraft:ladder","ladder access");}}
 return count;
}
console.log(packSuite(core,createPack,readNBT)+' pack and landing assertions passed');
