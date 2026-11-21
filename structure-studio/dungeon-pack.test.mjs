import * as core from './core.mjs';
import {createPack} from './pack.mjs';
import {generateDungeon} from './dungeon.mjs';
function suite(core,createPack,generateDungeon){
 let n=0;const a=(v,m)=>{if(!v)throw Error(m);n++;};const eq=(x,y,m)=>a(JSON.stringify(x)===JSON.stringify(y),m);
 for(const seed of [0,1,42,999]){
  const options={namespace:"mms_dungeon",buildings:[{id:"ruins",preset:"dungeon",seed,rooms:8,hiddenRooms:1,style:"crypt",encounterDifficulty:"standard"},{id:"bunker",generator:"dungeon",seed,rooms:6,hiddenRooms:2,style:"bunker",encounterDifficulty:"hard",worldgen:{mode:"underground",depth:24,salt:992,spacing:40,separation:10,biomes:["minecraft:mountains"]}}]};
  const {files,report}=createPack(options);
  for(const spec of options.buildings){const id=spec.id,prefix="mms_dungeon:dungeons/"+id,st=generateDungeon({...spec,...(spec.worldgen?.mode==="underground"?{shaftDepth:spec.worldgen.depth}:{}),lootTablePrefix:prefix}),raw=files.get("data/mms_dungeon/structure/"+id+".nbt");a(raw instanceof Uint8Array,"raw NBT");a(raw[0]===10,"NBT root");eq(st.size,spec.worldgen?.mode==="underground"?[31,24,25]:[31,7,25],"surface or underground template size");a(core.walkability(st).rooms.every(r=>r.reachable),"all rooms reachable");const ascii=new TextDecoder().decode(raw);a(ascii.includes("minecraft:interaction"),"interaction entities encoded in structure NBT");a(ascii.includes("minecraft:tripwire_hook")&&ascii.includes("mmsd_key"),"key item encoded in structure NBT");eq(st.entities.length,1+(spec.hiddenRooms??1),"interaction entity count");for(const room of st.metadata.rooms.filter(r=>r.lootTable)){a(ascii.includes(room.lootTable),"NBT loot table reference");const path="data/mms_dungeon/loot_table/dungeons/"+id+"/"+room.type+".json";a(files.has(path),"loot table resource");const table=JSON.parse(files.get(path));eq(table.type,"minecraft:chest","loot table context");a(table.pools.length>0&&table.pools.every(p=>p.entries.length>0),"loot table entries");}}
  const r=report.buildings[0];eq(r.preset,"dungeon","preset report");eq(r.generator,"room-graph-v1","generator report");eq(r.rooms.rooms.length,8,"room report");eq(report.buildings[1].worldgen,true,"worldgen opt in");
  eq(report.buildings[0].keyChest.keyId,"mms_dungeon:dungeons/ruins/bronze_key","key chest report");
  a(report.buildings[0].keyGiveCommand.includes("mmsd_key"),"key give fallback command");
  eq(report.buildings[0].interactiveDoors.length,2,"lock and secret door report");
  a(report.buildings[0].interactiveDoors.some(d=>d.kind==="locked")&&report.buildings[0].interactiveDoors.some(d=>d.kind==="secret"),"both door types reported");
  a(report.buildings[0].placeWithInteractionsCommand==="/function mms_dungeon:dungeon/ruins/place","manual placement wrapper report");
  a(report.buildings[0].setupCommand==="/function mms_dungeon:dungeon/ruins/setup","manual entity setup fallback report");
  a(files.has("data/mms_dungeon/function/dungeon/ruins/setup.mcfunction"),"interaction setup function");
  a(files.has("data/mms_dungeon/function/dungeon/ruins/place.mcfunction"),"entity-safe placement wrapper");
  const setup=files.get("data/mms_dungeon/function/dungeon/ruins/setup.mcfunction");
  const place=files.get("data/mms_dungeon/function/dungeon/ruins/place.mcfunction");
  a(setup.includes("unless entity @e[type=minecraft:interaction")&&setup.includes("run summon minecraft:interaction"),"setup avoids duplicate interaction entities");
  a(place.includes("place template mms_dungeon:ruins")&&place.includes("function mms_dungeon:dungeon/ruins/setup"),"placement wrapper places template then ensures entities");
  const undergroundJson=JSON.parse(files.get("data/mms_dungeon/worldgen/structure/bunker.json"));
  eq(undergroundJson.step,"underground_structures","underground generation step");
  eq(undergroundJson.terrain_adaptation,"bury","underground terrain adaptation");
  eq(undergroundJson.start_height,{absolute:-24},"underground heightmap offset");
  eq(undergroundJson.project_start_to_heightmap,"WORLD_SURFACE_WG","underground surface-relative placement");
  eq(report.buildings[1].worldgenMode,"underground","underground mode report");
  eq(report.buildings[1].worldgenDepth,24,"underground depth report");
  eq(report.buildings[1].accessShaft,true,"underground access shaft report");
  eq(report.buildings[1].size,[31,24,25],"shaft reaches projected surface");
  a(report.buildings[1].placeCommand.includes("~-24"),"manual underground placement offset");
  a(report.buildings[1].activateCommand.includes("positioned ~ ~-24 ~"),"underground encounter origin offset");a(r.lootContainers.length>=2,"loot container report");
  eq(r.encounterDifficulty,"standard","encounter difficulty report");a(r.encounterCount>=3,"encounter count report");a(r.activateCommand.includes("mms_dungeon:dungeon/ruins/activate"),"activation command report");a(r.activateCommand.startsWith("/function "),"direct activation command");a(r.activationOrigin.includes("same execution position"),"activation origin note");
  const activate=files.get("data/mms_dungeon/function/dungeon/ruins/activate.mcfunction"),once=files.get("data/mms_dungeon/function/dungeon/ruins/activate_once.mcfunction");
  a(typeof activate==="string"&&activate.includes("execute unless entity @e[type=minecraft:marker"),"one-shot activation guard");a(typeof once==="string"&&once.includes("summon minecraft:marker"),"activation marker");a(once.includes("summon minecraft:"),"encounter summons");
  const hard=report.buildings[1];eq(hard.encounterDifficulty,"hard","hard profile report");a(hard.encounterCount>=1,"hard encounter output");
  let rejected=false;try{createPack({namespace:"mms_dungeon",buildings:[{id:"bad",preset:"dungeon",encounterDifficulty:"impossible"}]});}catch{rejected=true;}a(rejected,"invalid encounter profile rejected");
  for(const worldgen of [{mode:"sideways",salt:1},{mode:"underground",depth:8,salt:2},{mode:"underground",depth:49,salt:3},{mode:"underground",depth:24,heightOffset:0,salt:4}]){let bad=false;try{createPack({namespace:"mms_dungeon",buildings:[{id:"bad",preset:"dungeon",worldgen}]});}catch{bad=true;}a(bad,"invalid underground worldgen configuration rejected");}
  let nonDungeon=false;try{createPack({namespace:"mms_dungeon",buildings:[{id:"bad",preset:"house",worldgen:{mode:"underground",depth:24,salt:5}}]});}catch{nonDungeon=true;}a(nonDungeon,"underground mode rejects non-dungeon presets");
  a(files.has("data/mms_dungeon/worldgen/structure/bunker.json"),"worldgen resource");
  const doorSpec=options.buildings[0],doorId=doorSpec.id,doorPrefix="mms_dungeon:dungeons/"+doorId,doorDungeon=generateDungeon({...doorSpec,lootTablePrefix:doorPrefix});
  for(const door of doorDungeon.metadata.interactiveDoors){
   const advancementPath="data/mms_dungeon/advancement/dungeon/"+doorId+"/door/"+door.id+".json";
   const interactPath="data/mms_dungeon/function/dungeon/"+doorId+"/door/"+door.id+"/interact.mcfunction";
   const openPath="data/mms_dungeon/function/dungeon/"+doorId+"/door/"+door.id+"/open.mcfunction";
   a(files.has(advancementPath)&&files.has(interactPath)&&files.has(openPath),"door advancement and functions generated");
   const advancement=JSON.parse(files.get(advancementPath));
   eq(advancement.criteria.interact.trigger,"minecraft:player_interacted_with_entity","door advancement interaction trigger");
   a(advancement.criteria.interact.conditions.entity.nbt.includes(door.tag),"door advancement tag predicate");
   const interact=files.get(interactPath),open=files.get(openPath);
   a(interact.includes("advancement revoke @s only"),"door advancement is repeatable");
   if(door.kind==="locked"){a(interact.includes("if items entity @s inventory.*")&&open.includes("clear @s minecraft:tripwire_hook"),"locked door requires and consumes matching key");a(open.includes("fill ")&&open.includes("minecraft:air"),"locked door opens barrier");}
   else {a(!interact.includes("if items")&&open.includes("minecraft:air"),"secret door opens without key");}
  }
 }
 return n;
}
console.log(suite(core,createPack,generateDungeon)+' dungeon pack assertions passed');
