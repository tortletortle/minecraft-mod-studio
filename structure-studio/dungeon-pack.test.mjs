import * as core from './core.mjs';
import {createPack} from './pack.mjs';
import {generateDungeon} from './dungeon.mjs';
function suite(core,createPack,generateDungeon){
 let n=0;const a=(v,m)=>{if(!v)throw Error(m);n++;};const eq=(x,y,m)=>a(JSON.stringify(x)===JSON.stringify(y),m);
 for(const seed of [0,1,42,999]){
  const options={namespace:"mms_dungeon",buildings:[{id:"ruins",preset:"dungeon",seed,rooms:8,hiddenRooms:1,style:"crypt"},{id:"bunker",generator:"dungeon",seed,rooms:6,hiddenRooms:2,style:"bunker",worldgen:{salt:992,spacing:40,separation:10,biomes:["minecraft:mountains"]}}]};
  const {files,report}=createPack(options);
  for(const spec of options.buildings){const id=spec.id,prefix="mms_dungeon:dungeons/"+id,st=generateDungeon({...spec,lootTablePrefix:prefix}),raw=files.get("data/mms_dungeon/structure/"+id+".nbt");a(raw instanceof Uint8Array,"raw NBT");a(raw[0]===10,"NBT root");eq(st.size,[31,7,25],"default size");a(core.walkability(st).rooms.every(r=>r.reachable),"all rooms reachable");const ascii=new TextDecoder().decode(raw);for(const room of st.metadata.rooms.filter(r=>r.lootTable)){a(ascii.includes(room.lootTable),"NBT loot table reference");const path="data/mms_dungeon/loot_table/dungeons/"+id+"/"+room.type+".json";a(files.has(path),"loot table resource");const table=JSON.parse(files.get(path));eq(table.type,"minecraft:chest","loot table context");a(table.pools.length>0&&table.pools.every(p=>p.entries.length>0),"loot table entries");}}
  const r=report.buildings[0];eq(r.preset,"dungeon","preset report");eq(r.generator,"room-graph-v1","generator report");eq(r.rooms.rooms.length,8,"room report");eq(report.buildings[1].worldgen,true,"worldgen opt in");a(r.lootContainers.length>=2,"loot container report");
  a(files.has("data/mms_dungeon/worldgen/structure/bunker.json"),"worldgen resource");
 }
 return n;
}
console.log(suite(core,createPack,generateDungeon)+' dungeon pack assertions passed');
