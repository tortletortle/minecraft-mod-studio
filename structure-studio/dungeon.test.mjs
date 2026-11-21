import * as core from './core.mjs';
import {generateDungeon} from './dungeon.mjs';
function suite(core,generateDungeon){
 let count=0;const a=(v,m)=>{if(!v)throw Error(m);count++;};const eq=(x,y,m)=>a(JSON.stringify(x)===JSON.stringify(y),m);const throws=f=>{let ok=false;try{f()}catch{ok=true;}a(ok,"invalid input must reject");};
 const scenarios=[[16,6,16,4],[20,8,20,4],[24,9,32,6],[31,7,25,8],[40,12,40,12],[48,16,48,16]];
 for(const [w,h,d,rooms] of scenarios)for(const style of ["stone","crypt","bunker"])for(const seed of [0,1,42,999,4294967295]){
  const opt={size:[w,h,d],rooms,style,seed,hiddenRooms:Math.min(2,rooms-3),loopChance:0.25};
  const s=generateDungeon(opt),walk=core.walkability(s);
  a(core.validate(s)===s,"core validation");eq(s,generateDungeon(opt),"determinism");
  a(s.metadata.generator==="room-graph-v1","generator metadata");eq(s.metadata.rooms.length,rooms,"room count");
  a(walk.entryValid&&walk.rooms.length===rooms&&walk.rooms.every(r=>r.reachable),"all rooms reachable");
  a(s.metadata.connections.filter(e=>e.kind==="tree").length===rooms-1,"spanning tree edge count");
  a(s.metadata.connections.every(e=>e.width>=1&&e.width<=3),"corridor widths");
  const hidden=s.metadata.rooms.filter(r=>r.hidden);eq(hidden.length,opt.hiddenRooms,"hidden room count");
  for(const room of s.metadata.rooms){a(room.pos[1]===1,"ground floor");a(s.blocks.some(c=>c.pos[0]===room.pos[0]&&c.pos[1]===1&&c.pos[2]===room.pos[2]&&c.block.name==="minecraft:air"),"room center open");if(room.lootTable){a(Array.isArray(room.lootPosition),"loot position metadata");const chest=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(room.lootPosition));a(chest?.block.name==="minecraft:chest","loot chest block");eq(chest.nbt.LootTable,room.lootTable,"chest loot table reference");}if(["guard","ritual","boss"].includes(room.type)){a(Array.isArray(room.encounterPositions)&&room.encounterPositions.length>0,"encounter positions");for(const pos of room.encounterPositions){const spot=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(pos));a(spot?.block.name==="minecraft:air","encounter floor clear");}}}
  a(s.blocks.some(c=>c.nbt?.id==="minecraft:chest"),"at least one loot chest");
  const nbt=core.encodeNBT(s,{dataVersion:4903});a(nbt[0]===10,"NBT root");
 }
 for(const opt of [{size:[15,16,16],rooms:4},{size:[16,5,16],rooms:4},{size:[16,6,16],rooms:5},{size:[31,7,25],rooms:3},{size:[31,7,25],rooms:8,hiddenRooms:7},{size:[31,7,25],rooms:8,style:"wood"},{size:[31,7,25],rooms:8,corridorWidth:4},{size:[31,7,25],rooms:8,loopChance:1.2},{size:[31,7,25],rooms:8,seed:-1},{size:[31,7,25],rooms:8,lootTablePrefix:"../evil"},{size:[31,7,25],rooms:8,encounterDifficulty:"nightmare"}])throws(()=>generateDungeon(opt));
 const custom=generateDungeon({size:[31,7,25],rooms:8,seed:42,lootTablePrefix:"mms_test:dungeons/ruins",encounterDifficulty:"hard"});
 a(custom.metadata.rooms.some(r=>r.lootTable==="mms_test:dungeons/ruins/treasure"),"custom loot table namespace");
 eq(custom.metadata.encounterDifficulty,"hard","encounter difficulty metadata");
 const underground=generateDungeon({size:[31,7,25],rooms:8,seed:42,shaftDepth:24});
 eq(underground.size,[31,24,25],"underground shaft extends template to surface");
 eq(underground.metadata.roomHeight,7,"underground room height remains compact");
 eq(underground.metadata.shaftDepth,24,"underground shaft depth metadata");
 const shaft=underground.metadata.entranceShaft;
 a(shaft&&shaft.depth===24,"entrance shaft metadata");
 const [sx,sy,sz]=shaft.position;
 const ladderBlocks=underground.blocks.filter(c=>c.block.name==="minecraft:ladder"&&c.pos[0]===sx&&c.pos[2]===sz);
 eq(ladderBlocks.length,23,"continuous ladder from room to surface");
 a(ladderBlocks.every(c=>c.block.properties.facing==="west"),"ladder faces exit");
 const exitBlock=underground.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(shaft.exit));
 eq(exitBlock?.block.name,"minecraft:air","surface exit is carved open");
 for(let y=1;y<24;y++){const support=underground.blocks.find(c=>c.pos[0]===sx+1&&c.pos[1]===y&&c.pos[2]===sz);eq(support?.block.name,"minecraft:stone_bricks","ladder has continuous support wall");}
 const undergroundWalk=core.walkability(underground);
 a(undergroundWalk.entryValid&&undergroundWalk.rooms.every(r=>r.reachable),"underground dungeon remains walkable");
 for(const seed of [0,1,42,999])for(const [w,h,d,rooms] of scenarios){const shafted=generateDungeon({size:[w,h,d],rooms,seed,shaftDepth:24});a(shafted.metadata.entranceShaft&&core.walkability(shafted).rooms.every(r=>r.reachable),"shafted parameter matrix remains connected");}
 throws(()=>generateDungeon({size:[31,7,25],rooms:8,shaftDepth:10}));
 throws(()=>generateDungeon({size:[31,12,25],rooms:8,shaftDepth:12}));
 throws(()=>generateDungeon({size:[31,7,25],rooms:8,shaftDepth:49}));
 return count;
}
console.log(suite(core,generateDungeon)+' dungeon assertions passed');
