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
  for(const room of s.metadata.rooms){a(room.pos[1]===1,"ground floor");a(s.blocks.some(c=>c.pos[0]===room.pos[0]&&c.pos[1]===1&&c.pos[2]===room.pos[2]&&["minecraft:air","minecraft:stone_pressure_plate"].includes(c.block.name)),"room center remains traversable");if(room.lootTable){a(Array.isArray(room.lootPosition),"loot position metadata");const chest=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(room.lootPosition));a(chest?.block.name==="minecraft:chest","loot chest block");eq(chest.nbt.LootTable,room.lootTable,"chest loot table reference");}if(["guard","ritual","boss"].includes(room.type)){a(Array.isArray(room.encounterPositions)&&room.encounterPositions.length>0,"encounter positions");for(const pos of room.encounterPositions){const spot=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(pos));a(spot?.block.name==="minecraft:air","encounter floor clear");}}}
  a(s.blocks.some(c=>c.nbt?.id==="minecraft:chest"),"at least one loot chest");
  eq(s.metadata.traps.length,1,"one physical trap per dungeon");
  const trap=s.metadata.traps[0],plate=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(trap.triggerPosition));
  eq(plate?.block.name,"minecraft:stone_pressure_plate","trap pressure plate block");
  a(trap.dispensers.length>=1&&trap.dispensers.length<=4,"trap has one to four dispensers");
  for(const dispenser of trap.dispensers){const block=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(dispenser.position));eq(block?.block.name,"minecraft:dispenser","trap dispenser block");eq(block?.block.properties.facing,dispenser.facing,"trap dispenser orientation");eq(block?.nbt.Items[0].id,"minecraft:arrow","trap dispenser arrow inventory");eq(block?.nbt.Items[0].count,8,"trap dispenser ammunition");}
  for(const pos of trap.wirePositions){const wire=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(pos));eq(wire?.block.name,"minecraft:redstone_wire","trap redstone wiring");}

  const puzzles=s.metadata.puzzles??[];
  a(puzzles.length<=1,"at most one rune sequence puzzle per dungeon");
  for(const puzzle of puzzles){
   eq(puzzle.kind,"three-rune-sequence","rune puzzle kind");
   eq(puzzle.runes.length,3,"three rune pedestals");
   eq([...puzzle.sequence].sort((a,b)=>a-b),[0,1,2],"rune clue is a permutation");
   eq(puzzle.clueBlocks,puzzle.sequence.map(index=>puzzle.runes[index].block),"wall clue matches sequence");
   eq(s.metadata.rooms.find(r=>r.id===puzzle.roomId)?.puzzleId,puzzle.id,"puzzle room metadata");
   for(const rune of puzzle.runes){const block=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(rune.position));eq(block?.block.name,rune.block,"rune pedestal block");a(s.entities.some(e=>e.nbt.id==="minecraft:interaction"&&e.nbt.Tags.includes(rune.tag)),"rune interaction entity tag");}
   for(let i=0;i<3;i++){const clue=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(puzzle.cluePositions[i]));eq(clue?.block.name,puzzle.clueBlocks[i],"visible wall clue order");}
   for(const pos of puzzle.gate.blocks){const block=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(pos));eq(block?.block.name,"minecraft:iron_bars","sealed vault barrier");}
   const reward=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(puzzle.rewardPosition));eq(reward?.block.name,"minecraft:chest","sealed reward chest");eq(reward?.nbt.LootTable,puzzle.lootTable,"puzzle reward loot table");
   a(puzzle.gate.blocks.length>=2,"vault gate has a two-block barrier");
   for(const pos of puzzle.gate.sideWalls??[]){const block=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(pos));a(block&&block.block.name!=="minecraft:air"&&block.block.name!=="minecraft:iron_bars","vault alcove sidewall block");}
  }
  eq(s.metadata.interactiveDoors.length,1+opt.hiddenRooms,"one lock plus each secret door");
  eq(s.entities.length,1+opt.hiddenRooms+puzzles.reduce((n,p)=>n+p.runes.length,0),"door and rune interaction entity count");
  const keyChest=s.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(s.metadata.keyChest.position));
  a(keyChest?.block.name==="minecraft:chest","key chest block");
  eq(keyChest.nbt.Items[0].id,"minecraft:tripwire_hook","key item type");
  eq(keyChest.nbt.Items[0].components["minecraft:custom_data"].mmsd_key,s.metadata.keyChest.keyId,"key identity");
  a(s.metadata.keyRoom!==s.metadata.lockedRoom&&!s.metadata.rooms[s.metadata.keyRoom].hidden,"key chest is on the reachable side");
  const lock=s.metadata.interactiveDoors.find(d=>d.kind==="locked");
  eq(s.metadata.connections.filter(e=>(e.from===lock.from&&e.to===lock.to)||(e.from===lock.to&&e.to===lock.from)).length,1,"locked edge is unique");
  const reachesWithout=(blocked,goal)=>{
   const seen=new Set([0]),queue=[0];
   for(let q=0;q<queue.length;q++)for(const edge of s.metadata.connections){
    if((edge.from===blocked.from&&edge.to===blocked.to)||(edge.from===blocked.to&&edge.to===blocked.from))continue;
    const next=edge.from===queue[q]?edge.to:edge.to===queue[q]?edge.from:-1;
    if(next>=0&&!seen.has(next)){seen.add(next);queue.push(next);}
   }
   return seen.has(goal);
  };
  a(!reachesWithout(lock,s.metadata.lockedRoom),"locked branch cannot be bypassed");
  for(const door of s.metadata.interactiveDoors){
   eq(door.blocks.length,door.width*2,"door barrier covers full corridor width and height");
   const expected=door.kind==="locked"?"minecraft:iron_bars":"minecraft:bookshelf";
   a(door.blocks.every(pos=>s.blocks.some(c=>JSON.stringify(c.pos)===JSON.stringify(pos)&&c.block.name===expected)),"door barrier blocks placed");
   a(s.entities.some(e=>e.nbt.id==="minecraft:interaction"&&e.nbt.Tags.includes(door.tag)),"interactive entity tag matches door");
   const edgeCount=s.metadata.connections.filter(e=>(e.from===door.from&&e.to===door.to)||(e.from===door.to&&e.to===door.from)).length;
   eq(edgeCount,1,"interactive door edge is a graph bridge");
   if(door.kind==="secret"){const hiddenIndex=Number(door.id.slice("secret-".length));a(!reachesWithout(door,hiddenIndex),"secret room has no graph bypass");}
  }
  const nbt=core.encodeNBT(s,{dataVersion:4903});a(nbt[0]===10,"NBT root");
 }
 for(const opt of [{size:[15,16,16],rooms:4},{size:[16,5,16],rooms:4},{size:[16,6,16],rooms:5},{size:[31,7,25],rooms:3},{size:[31,7,25],rooms:8,hiddenRooms:7},{size:[31,7,25],rooms:8,style:"wood"},{size:[31,7,25],rooms:8,corridorWidth:4},{size:[31,7,25],rooms:8,loopChance:1.2},{size:[31,7,25],rooms:8,seed:-1},{size:[31,7,25],rooms:8,lootTablePrefix:"../evil"},{size:[31,7,25],rooms:8,encounterDifficulty:"nightmare"}])throws(()=>generateDungeon(opt));
 const puzzleSample=generateDungeon({size:[31,7,25],rooms:8,seed:42,shaftDepth:24});
 eq(puzzleSample.metadata.puzzles.length,1,"default dungeon contains a multi-stage rune puzzle");
 eq(puzzleSample.metadata.puzzles[0].sequence,[1,2,0],"seeded rune sequence is deterministic");
 a(puzzleSample.metadata.rooms.every(r=>r.puzzleId===undefined||r.puzzleId===puzzleSample.metadata.puzzles[0].id),"puzzle room metadata is unique");
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
 a(ladderBlocks.every(c=>c.block.properties.facing===shaft.facing),"ladder faces exit");
 const exitBlock=underground.blocks.find(c=>JSON.stringify(c.pos)===JSON.stringify(shaft.exit));
 eq(exitBlock?.block.name,"minecraft:air","surface exit is carved open");
 for(let y=1;y<24;y++){const support=underground.blocks.find(c=>c.pos[0]===shaft.support[0]&&c.pos[1]===y&&c.pos[2]===shaft.support[2]);eq(support?.block.name,"minecraft:stone_bricks","ladder has continuous support wall");}
 const undergroundWalk=core.walkability(underground);
 a(undergroundWalk.entryValid&&undergroundWalk.rooms.every(r=>r.reachable),"underground dungeon remains walkable");
 for(const seed of [0,1,42,999])for(const [w,h,d,rooms] of scenarios){const shafted=generateDungeon({size:[w,h,d],rooms,seed,shaftDepth:24});a(shafted.metadata.entranceShaft&&core.walkability(shafted).rooms.every(r=>r.reachable),"shafted parameter matrix remains connected");}
 throws(()=>generateDungeon({size:[31,7,25],rooms:8,shaftDepth:10}));
 throws(()=>generateDungeon({size:[31,12,25],rooms:8,shaftDepth:12}));
 throws(()=>generateDungeon({size:[31,7,25],rooms:8,shaftDepth:49}));
 return count;
}
console.log(suite(core,generateDungeon)+' dungeon assertions passed');
