// Deterministic room-graph dungeon generator. No UI or filesystem dependencies.
import * as core from './core.mjs';
function createDungeonGenerator(core){
 const fail=m=>{throw new Error(m)},check=(v,m)=>{if(!v)fail(m)};
 const integer=(v,min,max,name)=>{check(Number.isInteger(v)&&v>=min&&v<=max,`${name} must be an integer ${min}..${max}`);return v;};
 function rng(seed){let x=seed>>>0;return ()=>{x=(x+0x6D2B79F5)>>>0;let t=x;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}
 function generateDungeon(options={}){
  const size=options.size??[31,7,25];check(Array.isArray(size)&&size.length===3,"size must be [x,y,z]");
  const [w,roomHeight,d]=size;
  integer(w,16,48,"width");integer(roomHeight,6,16,"roomHeight");integer(d,16,48,"depth");
  const shaftDepth=options.shaftDepth??0;
  if(shaftDepth!==0)integer(shaftDepth,12,48,"shaftDepth");
  check(shaftDepth===0||shaftDepth>=roomHeight+4,"shaftDepth must leave room for the dungeon ceiling and access shaft");
  const totalHeight=shaftDepth||roomHeight;
  const maxCols=Math.floor((w-4)/6),maxRows=Math.floor((d-4)/6);
  const capacity=maxCols*maxRows;
  const count=integer(options.rooms??8,4,Math.min(16,capacity),"rooms");
  const seed=integer(options.seed??42,0,0xffffffff,"seed"),random=rng(seed);
  const style=options.style??"stone";
  check(["stone","crypt","bunker"].includes(style),"Unknown dungeon style");
  const encounterDifficulty=options.encounterDifficulty??"standard";
  check(["easy","standard","hard"].includes(encounterDifficulty),"Unknown encounter difficulty");
  const lootTablePrefix=options.lootTablePrefix??null;
  if(lootTablePrefix!==null)check(typeof lootTablePrefix==="string"&&/^[a-z0-9_.-]+:[a-z0-9_./-]+$/.test(lootTablePrefix)&&!lootTablePrefix.includes(".."),"Invalid loot table prefix");
  const vanillaLoot={treasure:"minecraft:chests/simple_dungeon",boss:"minecraft:chests/stronghold_crossing",hidden:"minecraft:chests/abandoned_mineshaft"};
  const lootTableFor=kind=>lootTablePrefix?lootTablePrefix+"/"+kind:vanillaLoot[kind];
  const corridorWidth=integer(options.corridorWidth??2,1,3,"corridorWidth");
  const hiddenCount=integer(options.hiddenRooms??1,0,2,"hiddenRooms");
  check(hiddenCount<count-2,"Too many hidden rooms");
  const loopChance=options.loopChance??0.18;check(typeof loopChance==="number"&&Number.isFinite(loopChance)&&loopChance>=0&&loopChance<=0.6,"loopChance must be 0..0.6");
  let cols=Math.min(maxCols,Math.max(2,Math.round(Math.sqrt(count*w/d))));
  let rows=Math.ceil(count/cols);
  if(rows>maxRows){cols=Math.ceil(count/maxRows);rows=Math.ceil(count/cols);}
  check(cols>=2&&rows>=2&&cols<=maxCols&&rows<=maxRows,"Dimensions too small for requested room count");
  const palette={
   stone:{wall:"minecraft:stone_bricks",floor:"minecraft:polished_andesite",ceiling:"minecraft:stone_bricks",accent:"minecraft:iron_bars",light:"minecraft:glowstone"},
   crypt:{wall:"minecraft:deepslate_bricks",floor:"minecraft:polished_deepslate",ceiling:"minecraft:deepslate_bricks",accent:"minecraft:bone_block",light:"minecraft:shroomlight"},
   bunker:{wall:"minecraft:polished_andesite",floor:"minecraft:iron_block",ceiling:"minecraft:deepslate_tiles",accent:"minecraft:iron_block",light:"minecraft:sea_lantern"}
  }[style];
  const b=core.createBuilder([w,totalHeight,d]),air="minecraft:air";
  // The playable rooms retain a compact ceiling; underground mode adds a separate vertical access shaft.
  b.box(0,0,0,w-1,0,d-1,palette.floor);
  b.box(0,roomHeight-1,0,w-1,roomHeight-1,d-1,palette.ceiling);
  b.box(0,1,0,w-1,roomHeight-2,d-1,palette.wall);
  const cells=[];
  for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){
   const index=row*cols+col;if(index>=count)continue;
   const xa=2+Math.floor(col*(w-4)/cols),xb=2+Math.floor((col+1)*(w-4)/cols)-1;
   const za=2+Math.floor(row*(d-4)/rows),zb=2+Math.floor((row+1)*(d-4)/rows)-1;
   const cw=xb-xa+1,cd=zb-za+1;check(cw>=6&&cd>=6,"Room cell too small");
   const rw=Math.max(4,cw-(random()<0.5?1:2)),rd=Math.max(4,cd-(random()<0.5?1:2));
   const cx=Math.floor((xa+xb)/2),cz=Math.floor((za+zb)/2);
   const x1=cx-Math.floor(rw/2),x2=x1+rw-1,z1=cz-Math.floor(rd/2),z2=z1+rd-1;
   cells.push({index,row,col,cx,cz,x1,x2,z1,z2});
  }
  // Room graph: randomized Kruskal spanning tree, plus optional loops.
  const byCell=new Map(cells.map(r=>[`${r.row},${r.col}`,r.index]));
  const edges=[];
  for(const room of cells){
   for(const [dr,dc] of [[0,1],[1,0]]){
    const other=byCell.get(`${room.row+dr},${room.col+dc}`);
    if(other!==undefined)edges.push([room.index,other]);
   }
  }
  for(let i=edges.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[edges[i],edges[j]]=[edges[j],edges[i]];}
  const parent=Array.from({length:count},(_,i)=>i),find=x=>parent[x]===x?x:(parent[x]=find(parent[x]));
  const tree=[],extra=[];
  for(const edge of edges){const a=find(edge[0]),c=find(edge[1]);if(a!==c){parent[a]=c;tree.push(edge);}else if(random()<loopChance)extra.push(edge);}
  check(tree.length===count-1,"Room graph is disconnected");
  const hidden=new Set(Array.from({length:hiddenCount},(_,i)=>count-1-i));
  const corridorCells=new Set();
  const allEdges=[...tree.map(edge=>({edge,tree:true})),...extra.map(edge=>({edge,tree:false}))];
  function carveLine(a,c,width){
   const offsets=Array.from({length:width},(_,i)=>i-Math.floor((width-1)/2));
   if(a.row===c.row){
    for(let x=Math.min(a.cx,c.cx);x<=Math.max(a.cx,c.cx);x++)for(const dz of offsets){
     const z=a.cz+dz;if(z>0&&z<d-1){corridorCells.add(`${x},${z}`);b.box(x,1,z,x,roomHeight-2,z,air);}
    }
   }else{
    for(let z=Math.min(a.cz,c.cz);z<=Math.max(a.cz,c.cz);z++)for(const dx of offsets){
     const x=a.cx+dx;if(x>0&&x<w-1){corridorCells.add(`${x},${z}`);b.box(x,1,z,x,roomHeight-2,z,air);}
    }
   }
  }
  // Carve room interiors.
  for(const room of cells){
   b.box(room.x1+1,1,room.z1+1,room.x2-1,roomHeight-2,room.z2-1,air);
  }
  for(const item of allEdges){
   const [ia,ib]=item.edge,a=cells[ia],c=cells[ib];
   const narrow=item.tree&&(hidden.has(ia)||hidden.has(ib));
   carveLine(a,c,narrow?1:corridorWidth);
  }
  const entrance=cells[0];
  // Two-wide approach from the world edge into the first room.
  for(let z=0;z<=entrance.cz;z++)for(let dx=0;dx<2;dx++){
   const x=entrance.cx+dx;if(x>0&&x<w-1){corridorCells.add(`${x},${z}`);b.box(x,1,z,x,roomHeight-2,z,air);}
  }
  let entranceShaft=null;
  if(shaftDepth){
   const directions=[{dx:1,dz:0,facing:"west"},{dx:-1,dz:0,facing:"east"},{dx:0,dz:1,facing:"north"},{dx:0,dz:-1,facing:"south"}];
   const candidates=[];
   for(let x=entrance.x1+1;x<=entrance.x2-1;x++)for(let z=entrance.z1+1;z<=entrance.z2-1;z++){
    if(x===entrance.cx&&z===entrance.cz)continue;
    for(const dir of directions){
     const sx2=x+dir.dx,sz2=z+dir.dz;
     if(sx2<entrance.x1||sx2>entrance.x2||sz2<entrance.z1||sz2>entrance.z2)continue;
     if(sx2===entrance.cx&&sz2===entrance.cz)continue;
     const score=Number(corridorCells.has(`${x},${z}`))+Number(corridorCells.has(`${sx2},${sz2}`));
     if(score<2)candidates.push({x,z,...dir,support:[sx2,sz2],score});
    }
   }
   candidates.sort((a,c)=>a.score-c.score);
   check(candidates.length>0,"Entrance room has no clear cell for the access shaft");
   const chosen=candidates[0],{x:sx,z:sz,dx,dz,facing}=chosen,ladder={name:"minecraft:ladder",properties:{facing}};
   for(let y=1;y<totalHeight;y++){b.set(sx,y,sz,ladder);b.set(sx+dx,y,sz+dz,palette.wall);}
   // The ladder faces away from its support wall; carve that side open at the surface.
   const exit=[sx-dx,totalHeight-1,sz-dz];
   b.set(...exit,air);
   b.set(sx-dz,totalHeight-1,sz+dx,palette.wall);
   b.set(sx+dz,totalHeight-1,sz-dx,palette.wall);
   entranceShaft={position:[sx,1,sz],support:[sx+dx,1,sz+dz],depth:shaftDepth,facing,exit};
  }
  const types=["entrance","library","treasure","guard","ritual","storage","boss","hidden"];
  const rooms=cells.map((room,i)=>{
   const isHidden=hidden.has(i);
   let type=isHidden?"hidden":(i===0?"entrance":i===count-2&&count>=6?"boss":types[1+(i-1)%5]);
   const metadata={id:`room-${i}`,type,hidden:isHidden,pos:[room.cx,1,room.cz],bounds:[room.x1,room.z1,room.x2,room.z2]};
   // Decorative blocks occupy corners, never the center used for connectivity tests.
   const decorations=type==="library"?["minecraft:bookshelf","minecraft:bookshelf"]:
    type==="treasure"?["minecraft:gold_block","minecraft:chiseled_stone_bricks"]:
    type==="boss"?[palette.accent,palette.accent]:
    type==="ritual"?["minecraft:crying_obsidian","minecraft:crying_obsidian"]:
    type==="hidden"?["minecraft:bookshelf","minecraft:bookshelf"]:
    ["minecraft:barrel","minecraft:chiseled_stone_bricks"];
   const corners=[[room.x1+1,room.z1+1],[room.x2-1,room.z1+1],[room.x1+1,room.z2-1],[room.x2-1,room.z2-1]];
   const safe=corners.filter(([x,z],index)=>!(x===room.cx&&z===room.cz)&&!(entranceShaft&&room.index===0&&x===entranceShaft.position[0]&&z===entranceShaft.position[2])&&!(entranceShaft&&room.index===0&&x===entranceShaft.support[0]&&z===entranceShaft.support[2])&&!corridorCells.has(`${x},${z}`)&&corners.findIndex(p=>p[0]===x&&p[1]===z)===index);
   const lootKind=type==="treasure"?"treasure":type==="boss"?"boss":type==="hidden"?"hidden":null;
   const lootSpot=lootKind&&safe.length?safe.pop():null;
   const hasEncounter=["guard","ritual","boss"].includes(type);
   if(!hasEncounter){
    if(safe[0])b.set(safe[0][0],1,safe[0][1],decorations[0]);
    if(safe[1])b.set(safe[1][0],1,safe[1][1],decorations[1]);
    if(safe[2])b.set(safe[2][0],1,safe[2][1],palette.light);
   }
   if(lootSpot){const lootTable=lootTableFor(lootKind);b.set(lootSpot[0],1,lootSpot[1],{name:"minecraft:chest",properties:{facing:"north",type:"single",waterlogged:"false"}},{id:"minecraft:chest",LootTable:lootTable});metadata.lootPosition=[lootSpot[0],1,lootSpot[1]];metadata.lootTable=lootTable;}
   if(hasEncounter){const used=lootSpot?new Set([lootSpot.join(",")]):new Set();metadata.encounterPositions=[];for(let x=room.x1+1;x<=room.x2-1;x++)for(let z=room.z1+1;z<=room.z2-1;z++)if(!corridorCells.has(`${x},${z}`)&&!used.has(`${x},${z}`))metadata.encounterPositions.push([x,1,z]);if(!metadata.encounterPositions.length)metadata.encounterPositions.push([room.cx,1,room.cz]);}
   return metadata;
  });
  const result=b.finish({generator:"room-graph-v1",style,seed,encounterDifficulty,roomHeight,shaftDepth,entranceShaft,roomCount:count,corridorWidth,loopChance,rooms,connections:allEdges.map(x=>({from:x.edge[0],to:x.edge[1],kind:x.tree?"tree":"loop",width:x.tree&&(hidden.has(x.edge[0])||hidden.has(x.edge[1]))?1:corridorWidth})),entrance:[entrance.cx,1,0],hiddenPassages:hiddenCount});
  core.validate(result);
  const walk=core.walkability(result);
  check(walk.entryValid&&walk.rooms.length===count&&walk.rooms.every(r=>r.reachable),"Generated room graph is not walkable");
  return result;
 }
 return {generateDungeon};
}
export const {generateDungeon}=createDungeonGenerator(core);
