import * as core from './core.mjs';
import {createPack} from './pack.mjs';
import {generateDungeon} from './dungeon.mjs';
function suite(core,createPack,generateDungeon){
 let n=0;const a=(v,m)=>{if(!v)throw Error(m);n++;};const eq=(x,y,m)=>a(JSON.stringify(x)===JSON.stringify(y),m);
 for(const seed of [0,1,42,999]){
  const options={namespace:"mms_dungeon",buildings:[{id:"ruins",preset:"dungeon",seed,rooms:8,hiddenRooms:1,style:"crypt"},{id:"bunker",generator:"dungeon",seed,rooms:6,hiddenRooms:2,style:"bunker",worldgen:{salt:992,spacing:40,separation:10,biomes:["minecraft:mountains"]}}]};
  const {files,report}=createPack(options);
  for(const spec of options.buildings){const id=spec.id,st=generateDungeon(spec),raw=files.get("data/mms_dungeon/structure/"+id+".nbt");a(raw instanceof Uint8Array,"raw NBT");a(raw[0]===10,"NBT root");eq(st.size,[31,7,25],"default size");a(core.walkability(st).rooms.every(r=>r.reachable),"all rooms reachable");}
  const r=report.buildings[0];eq(r.preset,"dungeon","preset report");eq(r.generator,"room-graph-v1","generator report");eq(r.rooms.rooms.length,8,"room report");eq(report.buildings[1].worldgen,true,"worldgen opt in");
  a(files.has("data/mms_dungeon/worldgen/structure/bunker.json"),"worldgen resource");
 }
 return n;
}
console.log(suite(core,createPack,generateDungeon)+' dungeon pack assertions passed');
