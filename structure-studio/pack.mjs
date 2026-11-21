// Pure resource planner; raw NBT bytes become gzip only at the IO boundary.
import * as core from './core.mjs';
import {generateDungeon} from './dungeon.mjs';
function planPack(core, options){
 const fail=m=>{throw Error(m)}, check=(ok,m)=>{if(!ok)fail(m)}, integer=(n,min,max,label)=>{check(Number.isInteger(n)&&n>=min&&n<=max,label+" must be an integer in "+min+".."+max);return n;};
 const ns=options.namespace??"mms_structure";
 const segment=/^[a-z0-9][a-z0-9_-]{0,47}$/;
 check(typeof ns==="string"&&segment.test(ns)&&!["minecraft","realms"].includes(ns),"Invalid or reserved namespace");
 const specs=options.buildings;
 check(Array.isArray(specs)&&specs.length>=1&&specs.length<=8,"Expected 1..8 buildings");
 const files=new Map(), json=(path,o)=>{check(!files.has(path),"Duplicate pack path");files.set(path,JSON.stringify(o,null,2)+"\n");}, raw=(path,b)=>{check(!files.has(path),"Duplicate pack path");files.set(path,b);};
 const lootTables={
  treasure:{type:"minecraft:chest",pools:[{rolls:2,entries:[{type:"minecraft:item",name:"minecraft:iron_ingot",weight:8},{type:"minecraft:item",name:"minecraft:gold_ingot",weight:5},{type:"minecraft:item",name:"minecraft:emerald",weight:3},{type:"minecraft:item",name:"minecraft:diamond",weight:1}]}]},
  boss:{type:"minecraft:chest",pools:[{rolls:3,entries:[{type:"minecraft:item",name:"minecraft:gold_ingot",weight:8},{type:"minecraft:item",name:"minecraft:diamond",weight:4},{type:"minecraft:item",name:"minecraft:emerald",weight:4},{type:"minecraft:item",name:"minecraft:netherite_scrap",weight:1},{type:"minecraft:item",name:"minecraft:golden_apple",weight:2}]}]},
  hidden:{type:"minecraft:chest",pools:[{rolls:1,entries:[{type:"minecraft:item",name:"minecraft:iron_ingot",weight:6},{type:"minecraft:item",name:"minecraft:lapis_lazuli",weight:5},{type:"minecraft:item",name:"minecraft:amethyst_shard",weight:4},{type:"minecraft:item",name:"minecraft:diamond",weight:1}]}]},
  puzzle:{type:"minecraft:chest",pools:[{rolls:2,entries:[{type:"minecraft:item",name:"minecraft:amethyst_shard",weight:8},{type:"minecraft:item",name:"minecraft:emerald",weight:6},{type:"minecraft:item",name:"minecraft:gold_ingot",weight:5},{type:"minecraft:item",name:"minecraft:diamond",weight:2},{type:"minecraft:item",name:"minecraft:enchanted_golden_apple",weight:1}]}]}
 };
 const encounterProfiles={
  easy:{guard:["minecraft:zombie"],ritual:["minecraft:skeleton"],boss:["minecraft:vindicator"]},
  standard:{guard:["minecraft:zombie","minecraft:skeleton"],ritual:["minecraft:witch"],boss:["minecraft:evoker","minecraft:vindicator"]},
  hard:{guard:["minecraft:zombie","minecraft:skeleton","minecraft:vindicator"],ritual:["minecraft:witch","minecraft:skeleton"],boss:["minecraft:evoker","minecraft:vindicator","minecraft:vindicator"]}
 };
 const stableTag=value=>{let h=2166136261;for(let i=0;i<value.length;i++){h^=value.charCodeAt(i);h=Math.imul(h,16777619);}return "mmsd_"+(h>>>0).toString(16)};
 json("pack.mcmeta",{pack:{description:"Minecraft Mod Studio structures — Java 26.2",min_format:[107,1],max_format:[107,1]}});
 const prefix="data/"+ns+"/",buildingIds=new Set(), reports=[], salts=new Set(), loadInitLines=[], objectiveNames=new Set();
 for(const spec of specs){
  check(spec&&typeof spec==="object","Invalid building specification");
  const id=spec.id;check(typeof id==="string"&&segment.test(id)&&!buildingIds.has(id),"Invalid or duplicate building ID");buildingIds.add(id);
  const isDungeon=spec.preset==="dungeon"||spec.generator==="dungeon";
  const difficulty=spec.encounterDifficulty??spec.metadata?.encounterDifficulty??"standard";
  if(isDungeon)check(Object.hasOwn(encounterProfiles,difficulty),"Invalid dungeon encounter difficulty");
  const g=spec.worldgen===undefined||spec.worldgen===false?null:spec.worldgen;
  if(g)check(g&&typeof g==="object"&&!Array.isArray(g),"worldgen must be false or object");
  const worldgenMode=g?.mode??"surface";
  if(g)check(["surface","underground"].includes(worldgenMode),"worldgen mode must be surface or underground");
  if(worldgenMode==="underground")check(isDungeon,"Underground mode currently supports dungeon structures only");
  if(worldgenMode==="underground")check(g.heightOffset===undefined,"Use depth instead of heightOffset for underground mode");
  if(worldgenMode==="surface")check(g?.depth===undefined,"depth is only valid for underground mode");
  const undergroundDepth=worldgenMode==="underground"?integer(g.depth??24,12,48,"depth"):0;
  const st=isDungeon?generateDungeon({...spec,shaftDepth:undergroundDepth,encounterDifficulty:difficulty,lootTablePrefix:ns+":dungeons/"+id}):core.generate(spec), rid=ns+":"+id, w=core.walkability(st);
  check(w.entryValid&&w.rooms.every(r=>r.reachable),"Ground-floor reachability failed");
  raw(prefix+"structure/"+id+".nbt",core.encodeNBT(st,{dataVersion:4903,paletteKeys:"legacy"}));
  let encounterCount=0,activateCommand=null,activationOrigin=null;
  if(isDungeon){
   const kinds=new Set(st.metadata.rooms.map(r=>r.type).filter(k=>Object.hasOwn(lootTables,k)));if(st.metadata.puzzles?.length)kinds.add("puzzle");
   for(const kind of kinds)json(prefix+"loot_table/dungeons/"+id+"/"+kind+".json",lootTables[kind]);
   const tag=stableTag(ns+":"+id),once=[`summon minecraft:marker ~ ~ ~ {Tags:["${tag}"]}`];
   for(const room of st.metadata.rooms){const mobs=encounterProfiles[difficulty][room.type]??[],positions=room.encounterPositions??[];for(let i=0;i<Math.min(mobs.length,positions.length);i++){const [x,y,z]=positions[i];once.push(`summon ${mobs[i]} ~${x+0.5} ~${y} ~${z+0.5}`);encounterCount++;}}
   raw(prefix+"function/dungeon/"+id+"/activate.mcfunction",`execute unless entity @e[type=minecraft:marker,tag=${tag},distance=..1] run function ${ns}:dungeon/${id}/activate_once\n`);
   raw(prefix+"function/dungeon/"+id+"/activate_once.mcfunction",once.join("\n")+"\n");
   activateCommand=`/function ${ns}:dungeon/${id}/activate`;
   activationOrigin="Run immediately after /place template from the same execution position. If activating later, use the structure origin: /execute positioned X Y Z run function ${ns}:dungeon/${id}/activate. Natural world generation does not call this function automatically.";
   const setupLines=[];
   for(const door of st.metadata.interactiveDoors??[]){
    const doorBase=ns+":dungeon/"+id+"/door/"+door.id,doorPath=prefix+"function/dungeon/"+id+"/door/"+door.id+"/";
    const [dx,dy,dz]=door.position;
    setupLines.push(`execute positioned ~${dx} ~${dy} ~${dz} unless entity @e[type=minecraft:interaction,tag=${door.tag},distance=..0.25] run summon minecraft:interaction ~ ~ ~ {width:${door.width}.0f,height:2.0f,response:1b,Tags:["${door.tag}"]}`);
    const selector=`@e[type=minecraft:interaction,tag=${door.tag},sort=nearest,limit=1,distance=..4]`;
    const advancement=ns+":dungeon/"+id+"/door/"+door.id;
    const lines=[];
    const start=-Math.floor(door.width/2),end=door.width-1-Math.floor(door.width/2);
    const fill=door.axis==="x"?`fill ~ ~ ~${start} ~ ~1 ~${end} minecraft:air`:`fill ~${start} ~ ~ ~${end} ~1 ~ minecraft:air`;
    if(door.kind==="locked"){
     const keyPredicate=`minecraft:tripwire_hook[minecraft:custom_data~{mmsd_key:"${door.keyId}"}]`;
     lines.push(`execute at ${selector} if items entity @s container.* ${keyPredicate} run function ${doorBase}/open`);
     lines.push(`execute at ${selector} if items entity @s weapon.offhand ${keyPredicate} run function ${doorBase}/open`);
     lines.push(`execute at ${selector} unless items entity @s container.* ${keyPredicate} unless items entity @s weapon.offhand ${keyPredicate} run tellraw @s {text:"The gate is locked. Find the ancient key.",color:"red"}`);
     raw(doorPath+"open.mcfunction",[`clear @s ${keyPredicate} 1`,fill,`execute as @e[type=minecraft:interaction,tag=${door.tag},distance=..3] run kill @s`,"playsound minecraft:block.iron_door.open block @s ~ ~ ~ 0.8 0.9",'tellraw @s {text:"The ancient key turns. The gate opens.",color:"gold"}'].join("\n")+"\n");
    }else{
     lines.push(`execute at ${selector} run function ${doorBase}/open`);
     raw(doorPath+"open.mcfunction",[fill,`execute as @e[type=minecraft:interaction,tag=${door.tag},distance=..3] run kill @s`,"playsound minecraft:block.piston.extend block @s ~ ~ ~ 0.7 1.1",'tellraw @s {text:"A hidden passage slides open.",color:"green"}'].join("\n")+"\n");
    }
    lines.push(`advancement revoke @s only ${advancement}`);
    raw(doorPath+"interact.mcfunction",lines.join("\n")+"\n");
    json(prefix+"advancement/dungeon/"+id+"/door/"+door.id+".json",{criteria:{interact:{trigger:"minecraft:player_interacted_with_entity",conditions:{entity:{type:"minecraft:interaction",nbt:`{Tags:["${door.tag}"]}`}}}},rewards:{function:doorBase+"/interact"}});
   }
   for(const puzzle of st.metadata.puzzles??[]){
    const puzzleBase=ns+":dungeon/"+id+"/puzzle/"+puzzle.id,puzzlePath=prefix+"function/dungeon/"+id+"/puzzle/"+puzzle.id+"/";
    for(const objective of [puzzle.scoreboardObjective,puzzle.scratchObjective]){
     check(typeof objective==="string"&&/^[a-z0-9_.+-]{1,16}$/.test(objective),"Invalid puzzle scoreboard objective");
     check(!objectiveNames.has(objective),"Duplicate puzzle scoreboard objective");objectiveNames.add(objective);
     loadInitLines.push("scoreboard objectives add "+objective+" dummy");
    }
    const completionRune=puzzle.runes.find(r=>r.index===puzzle.sequence[2]);
    const dx1=puzzle.gate.from[0]-completionRune.position[0],dy1=puzzle.gate.from[1]-2,dz1=puzzle.gate.from[2]-completionRune.position[2];
    const dx2=puzzle.gate.to[0]-completionRune.position[0],dy2=puzzle.gate.to[1]-2,dz2=puzzle.gate.to[2]-completionRune.position[2];
    raw(puzzlePath+"complete.mcfunction",[
     `fill ~${dx1} ~${dy1} ~${dz1} ~${dx2} ~${dy2} ~${dz2} minecraft:air`,
     "playsound minecraft:block.iron_door.open block @a[distance=..16] ~ ~ ~ 0.9 1.0",
     'tellraw @s {text:"The three runes align. The seal breaks and the vault opens.",color:"gold"}'
    ].join("\n")+"\n");
    for(const rune of puzzle.runes){
     const [x,,z]=rune.position;
     setupLines.push(`execute positioned ~${x+0.5} ~2 ~${z+0.5} unless entity @e[type=minecraft:interaction,tag=${rune.tag},distance=..0.25] run summon minecraft:interaction ~ ~ ~ {width:0.9f,height:1.5f,response:1b,Tags:["${rune.tag}"]}`);
     const step=puzzle.sequence.indexOf(rune.index),advancement=puzzleBase+"/"+rune.id;
     const interactLines=[
      `scoreboard players add @s ${puzzle.scoreboardObjective} 0`,
      `scoreboard players set @s ${puzzle.scratchObjective} 0`,
      `scoreboard players operation @s ${puzzle.scratchObjective} = @s ${puzzle.scoreboardObjective}`,
      `execute if score @s ${puzzle.scratchObjective} matches ${step} run scoreboard players set @s ${puzzle.scoreboardObjective} ${step+1}`,
      `execute unless score @s ${puzzle.scratchObjective} matches ${step} unless score @s ${puzzle.scratchObjective} matches 3 run scoreboard players set @s ${puzzle.scoreboardObjective} 0`,
      `execute if score @s ${puzzle.scratchObjective} matches ${step} run tellraw @s {text:"Rune ${step+1}/3 activated.",color:"aqua"}`,
      `execute unless score @s ${puzzle.scratchObjective} matches ${step} unless score @s ${puzzle.scratchObjective} matches 3 run tellraw @s {text:"Wrong rune. The sequence resets.",color:"red"}`,
      `execute if score @s ${puzzle.scratchObjective} matches 3 run tellraw @s {text:"The vault seal is already open.",color:"gray"}`,
      `execute if score @s ${puzzle.scratchObjective} matches 2 if score @s ${puzzle.scoreboardObjective} matches 3 run function ${puzzleBase}/complete`,
      `advancement revoke @s only ${advancement}`
     ];
     raw(puzzlePath+rune.id+".mcfunction",interactLines.join("\n")+"\n");
     json(prefix+"advancement/dungeon/"+id+"/puzzle/"+puzzle.id+"/"+rune.id+".json",{criteria:{interact:{trigger:"minecraft:player_interacted_with_entity",conditions:{entity:{type:"minecraft:interaction",nbt:`{Tags:["${rune.tag}"]}`}}}},rewards:{function:advancement}});
    }
   }
   raw(prefix+"function/dungeon/"+id+"/setup.mcfunction",setupLines.join("\n")+"\n");
   const placeOffset=worldgenMode==="underground"?"~ ~-"+undergroundDepth+" ~":"~ ~ ~";
   const setupAt=worldgenMode==="underground"?`execute positioned ~ ~-${undergroundDepth} ~ run function ${ns}:dungeon/${id}/setup`:`function ${ns}:dungeon/${id}/setup`;
   raw(prefix+"function/dungeon/"+id+"/place.mcfunction",[`place template ${rid} ${placeOffset}`,setupAt].join("\n")+"\n");
  }
  const placeCommand=worldgenMode==="underground"?"/place template "+rid+" ~ ~-"+undergroundDepth+" ~":"/place template "+rid+" ~ ~ ~";
  const placeWithInteractionsCommand=isDungeon?"/function "+ns+":dungeon/"+id+"/place":null;
  const setupCommand=isDungeon?(worldgenMode==="underground"?"/execute positioned ~ ~-"+undergroundDepth+" ~ run function "+ns+":dungeon/"+id+"/setup":"/function "+ns+":dungeon/"+id+"/setup"):null;
  if(worldgenMode==="underground"&&activateCommand){activateCommand="/execute positioned ~ ~-"+undergroundDepth+" ~ run function "+ns+":dungeon/"+id+"/activate";activationOrigin="Run this command from the same position used for the underground /place template command; it offsets execution to the dungeon origin. Natural world generation does not call this function automatically.";}
  const report={id:rid,size:st.size,seed:st.metadata.seed,preset:spec.preset??spec.generator??st.metadata.preset,generator:st.metadata.generator??null,rooms:w,lootContainers:st.metadata.rooms.filter(r=>r.lootTable).map(r=>({roomId:r.id,type:r.type,position:r.lootPosition,lootTable:r.lootTable})),keyChest:st.metadata.keyChest??null,keyGiveCommand:st.metadata.keyChest?`/give @p minecraft:tripwire_hook[minecraft:custom_data={mmsd_key:"${st.metadata.keyChest.keyId}"},minecraft:custom_name={text:"Ancient Key",color:"gold",italic:false}] 1`:null,interactiveDoors:(st.metadata.interactiveDoors??[]).map(d=>({id:d.id,kind:d.kind,position:d.position,blocks:d.blocks,tag:d.tag,keyId:d.keyId??null})),traps:(st.metadata.traps??[]).map(t=>({id:t.id,kind:t.kind,roomId:t.roomId,triggerPosition:t.triggerPosition,dispensers:t.dispensers,wirePositions:t.wirePositions})),puzzles:(st.metadata.puzzles??[]).map(p=>({id:p.id,kind:p.kind,roomId:p.roomId,sequence:p.sequence,runes:p.runes,gate:p.gate,rewardPosition:p.rewardPosition,lootTable:p.lootTable,cluePositions:p.cluePositions,clueBlocks:p.clueBlocks,scoreboardObjective:p.scoreboardObjective})),placeWithInteractionsCommand,setupCommand,encounterDifficulty:isDungeon?difficulty:null,encounterCount,activateCommand,activationOrigin,placeCommand,worldgen:false,worldgenMode:g?worldgenMode:null,worldgenDepth:worldgenMode==="underground"?undergroundDepth:null};
  if(g){
   const spacing=integer(g.spacing??32,4,256,"spacing"),separation=integer(g.separation??8,1,spacing-1,"separation");
   const salt=integer(g.salt,0,2147483647,"salt");check(!salts.has(salt),"Duplicate worldgen salt");salts.add(salt);
   const biomes=g.biomes??["minecraft:plains"];
   check(Array.isArray(biomes)&&biomes.length>0&&biomes.length<=32&&biomes.every(x=>typeof x==="string"&&/^(?:[a-z0-9_.-]+):[a-z0-9_/-]+$/.test(x)),"Invalid biomes");
   const height=worldgenMode==="underground"?-undergroundDepth:integer(g.heightOffset??0,-32,32,"heightOffset");
   json(prefix+"tags/worldgen/biome/"+id+".json",{replace:false,values:[...new Set(biomes)]});
   json(prefix+"worldgen/template_pool/"+id+".json",{fallback:"minecraft:empty",elements:[{weight:1,element:{element_type:"minecraft:single_pool_element",location:rid,processors:"minecraft:empty",projection:"rigid"}}]});
   json(prefix+"worldgen/structure/"+id+".json",{type:"minecraft:jigsaw",biomes:"#"+rid,step:worldgenMode==="underground"?"underground_structures":"surface_structures",spawn_overrides:{},terrain_adaptation:worldgenMode==="underground"?"bury":"beard_thin",start_pool:rid,size:0,start_height:{absolute:height},project_start_to_heightmap:"WORLD_SURFACE_WG",max_distance_from_center:80,use_expansion_hack:false});
   json(prefix+"worldgen/structure_set/"+id+".json",{structures:[{structure:rid,weight:1}],placement:{type:"minecraft:random_spread",spacing,separation,salt}});
   Object.assign(report,{worldgen:true,worldgenMode,worldgenDepth:worldgenMode==="underground"?undergroundDepth:null,accessShaft:worldgenMode==="underground",spacing,separation,salt,locateCommand:"/locate structure "+rid,forceCommand:"/place structure "+rid+" ~ ~ ~"});
  }
  reports.push(report);
 }
 if(loadInitLines.length){
  raw(prefix+"function/load.mcfunction",`execute unless data storage ${ns}:runtime initialized run function ${ns}:initialize\n`);
  raw(prefix+"function/initialize.mcfunction",loadInitLines.join("\n")+"\n"+`data modify storage ${ns}:runtime initialized set value 1b\n`);
  json("data/minecraft/tags/function/load.json",{replace:false,values:[ns+":load"]});
 }
 return {files,report:{schema:1,target:"Java 26.2",dataVersion:4903,packFormat:[107,1],namespace:ns,buildings:reports,warning:"Templates explicitly include air. Use a disposable world. Worldgen is experimental until game registry and new-chunk tests pass."}};
}
export const createPack=options=>planPack(core,options);
