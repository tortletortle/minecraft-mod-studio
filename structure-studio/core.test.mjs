import {strict as assert} from 'node:assert';
import {gzipSync,gunzipSync} from 'node:zlib';
import * as core from './core.mjs';
function readNBT(bytes){
  const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let i=0;
  const b=()=>v.getUint8(i++),n=()=>{const x=v.getInt32(i,false);i+=4;return x;},str=()=>{const len=v.getUint16(i,false);i+=2;let s="";for(let j=0;j<len;j++)s+=String.fromCharCode(b());return s;};
  function parse(type){switch(type){case 3:return n();case 8:return str();case 9:{const t=b(),length=n();if(length<0||length>200000)throw Error("bad list length");return Array.from({length},()=>parse(t));}case 10:{const o={};for(let t=b();t!==0;t=b()){const name=str();o[name]=parse(t);}return o;}default:throw Error("unsupported tag "+type);}}
  if(b()!==10||str()!=="")throw Error("bad root");const obj=parse(10);if(i!==bytes.length)throw Error("trailing bytes");return obj;
}
function suite(core,readNBT){
  let pass=0;
  const a=(ok,msg)=>{if(!ok)throw new Error(msg);pass++;};
  const eq=(x,y,msg)=>a(JSON.stringify(x)===JSON.stringify(y),msg);
  const throws=(fn,msg)=>{let caught=false;try{fn();}catch{caught=true;}a(caught,msg);};
  const sets={house:[[7,6,7],[13,7,11],[48,6,48]],tower:[[7,9,7],[11,15,11],[9,48,9]],factory:[[19,6,11],[27,8,17],[48,8,48]]};
  const seeds=[0,1,7,42,4294967295];
  for(const [preset,sizes] of Object.entries(sets))for(const size of sizes)for(const seed of seeds){
    const s=core.generate({preset,size,seed}),p=core.paletteFor(s),path=core.walkability(s);
    eq(s,core.generate({preset,size,seed}),"determinism");a(core.validate(s)===s,"validation");eq(s.blocks.length,size.reduce((x,y)=>x*y),"volume");
    a(path.entryValid&&path.rooms.every(x=>x.reachable),`ground paths ${preset} ${size}`);
    const raw=core.encodeNBT(s,{dataVersion:4903}),decoded=readNBT(raw);
    eq(decoded.size,size,"NBT sizes");eq(decoded.DataVersion,4903,"NBT version");eq(decoded.entities,[],"entities");eq(decoded.blocks,p.blocks,"NBT positions and indexes");
    eq(decoded.palette,p.palette.map(b=>Object.keys(b.properties).length?{Name:b.name,Properties:b.properties}:{Name:b.name}),"NBT block states");
    a(decoded.blocks.every(b=>b.state>=0&&b.state<decoded.palette.length),"palette indexes");
  }
  const c=core.createBuilder([3,3,3]);c.set(1,1,1,"minecraft:stone");c.set(1,1,1,"minecraft:glass");eq(c.finish().blocks.length,1,"overwrite not duplicate");
  eq(c.finish().blocks[0].block.name,"minecraft:glass","last write wins");
  c.box(0,0,0,2,0,2,"minecraft:stone");eq(c.finish().blocks.length,10,"inclusive cuboid");
  throws(()=>c.set(-1,0,0,"minecraft:stone"),"negative");
  throws(()=>c.set(3,0,0,"minecraft:stone"),"out of bounds");
  throws(()=>c.set(0,0,0,"invalid"),"bad block id");
  throws(()=>c.box(2,0,0,1,0,0,"minecraft:stone"),"inverted box");
  throws(()=>core.generate({preset:"castle"}),"bad preset");
  throws(()=>core.generate({size:[49,6,7]}),"oversize");
  throws(()=>core.generate({seed:-1}),"bad seed");
  throws(()=>core.generate({wall:"minecraft:air"}),"air wall");
  throws(()=>core.validate({schema:1,size:[2,2,2],blocks:[{pos:[0,0,0],block:"minecraft:stone"},{pos:[0,0,0],block:"minecraft:glass"}]}),"duplicate");
  throws(()=>core.encodeNBT(c.finish()),"missing version");
  a(JSON.stringify(core.generate({preset:"factory",seed:1}))!==JSON.stringify(core.generate({preset:"factory",seed:42})),"seed variation");
  const modern=readNBT(core.encodeNBT(c.finish(),{dataVersion:5023,paletteKeys:"modern"}));a(modern.palette.every(x=>x.id&&!x.Name),"modern keys");
  return pass;
}
const count=suite(core,readNBT);
for(const preset of ['house','tower','factory']){const raw=core.encodeNBT(core.generate({preset,seed:42}),{dataVersion:4903});const zipped=gzipSync(raw);assert.deepEqual(gunzipSync(zipped),Buffer.from(raw));assert.equal(readNBT(gunzipSync(zipped)).DataVersion,4903);}
console.log(count+' core assertions + 6 gzip assertions passed');
