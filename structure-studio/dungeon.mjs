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
  const vanillaLoot={treasure:"minecraft:chests/simple_dungeon",boss:"minecraft:chests/stronghold_crossing",hidden:"minecraft:chests/abandoned_mineshaft",puzzle:"minecraft:chests/stronghold_corridor"};
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
  // Hidden rooms are deliberately attached as leaves; one additional core leaf becomes a true key-locked branch.
  const hidden=new Set(Array.from({length:hiddenCount},(_,i)=>count-1-i));
  const byCell=new Map(cells.map(r=>[`${r.row},${r.col}`,r.index]));
  const edges=[];
  for(const room of cells){
   for(const [dr,dc] of [[0,1],[1,0]]){
    const other=byCell.get(`${room.row+dr},${room.col+dc}`);
    if(other!==undefined)edges.push([room.index,other]);
   }
  }
  const shuffle=list=>{for(let i=list.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[list[i],list[j]]=[list[j],list[i]];}return list;};
  const coreEdges=shuffle(edges.filter(([a,c])=>!hidden.has(a)&&!hidden.has(c)));
  const parent=Array.from({length:count},(_,i)=>i),find=x=>parent[x]===x?x:(parent[x]=find(parent[x]));
  const tree=[],extra=[];
  for(const edge of coreEdges){const a=find(edge[0]),c=find(edge[1]);if(a!==c){parent[a]=c;tree.push(edge);}}
  check(tree.length===count-hidden.size-1,"Non-hidden room graph is disconnected");
  const coreAdj=Array.from({length:count},()=>[]);
  for(const [a,c] of tree){coreAdj[a].push(c);coreAdj[c].push(a);}
  const distance=Array(count).fill(-1),queue=[0];distance[0]=0;
  for(let i=0;i<queue.length;i++){const node=queue[i];for(const next of coreAdj[node])if(distance[next]<0){distance[next]=distance[node]+1;queue.push(next);}}
  const lockCandidates=cells.filter(r=>!hidden.has(r.index)&&r.index!==0&&coreAdj[r.index].length===1);
  check(lockCandidates.length>0,"No non-entrance leaf available for a key lock");
  lockCandidates.sort((a,c)=>distance[c.index]-distance[a.index]||a.index-c.index);
  const lockedRoom=lockCandidates[0].index,lockedEdge=tree.find(([a,c])=>a===lockedRoom||c===lockedRoom);
  const hiddenParents=new Map();
  for(const index of [...hidden].sort((a,b)=>a-b)){
   const candidates=edges.filter(([a,c])=>(a===index&&!hidden.has(c))||(c===index&&!hidden.has(a)));
   check(candidates.length>0,"Hidden room has no non-hidden neighbour");
   const edge=candidates[Math.floor(random()*candidates.length)],other=edge[0]===index?edge[1]:edge[0];
   tree.push(edge);hiddenParents.set(index,other);
  }
  check(tree.length===count-1,"Room graph is disconnected");
  // Extra loops never touch a hidden leaf or the locked leaf, so neither barrier can be bypassed.
  const treeKeys=new Set(tree.map(([a,c])=>a<c?`${a},${c}`:`${c},${a}`));
  for(const edge of edges){const [a,c]=edge,k=a<c?`${a},${c}`:`${c},${a}`;if(!treeKeys.has(k)&&!hidden.has(a)&&!hidden.has(c)&&a!==lockedRoom&&c!==lockedRoom&&random()<loopChance)extra.push(edge);}
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
  const typeFor=i=>hidden.has(i)?"hidden":(i===0?"entrance":i===count-2&&count>=6?"boss":types[1+(i-1)%5]);
  const puzzleCells=new Set();
  const safeCorners=room=>{
   const corners=[[room.x1+1,room.z1+1],[room.x2-1,room.z1+1],[room.x1+1,room.z2-1],[room.x2-1,room.z2-1]];
   return corners.filter(([x,z],index)=>!(x===room.cx&&z===room.cz)&&!(entranceShaft&&room.index===0&&x===entranceShaft.position[0]&&z===entranceShaft.position[2])&&!(entranceShaft&&room.index===0&&x===entranceShaft.support[0]&&z===entranceShaft.support[2])&&!corridorCells.has(`${x},${z}`)&&!puzzleCells.has(`${x},${z}`)&&!traps.some(t=>(t.triggerPosition[0]===x&&t.triggerPosition[2]===z)||t.wirePositions.some(p=>p[0]===x&&p[2]===z)||t.dispensers.some(p=>p.position[0]===x&&p.position[2]===z))&&corners.findIndex(p=>p[0]===x&&p[1]===z)===index);
  };
  const keyId=(lootTablePrefix??"mms_structure:dungeons/generated")+"/bronze_key";
  const traps=[];
  const trapPlans=room=>[
   {facing:"east",axis:"x",edge:room.x1,x:room.x1,z:room.cz},
   {facing:"west",axis:"x",edge:room.x2,x:room.x2,z:room.cz},
   {facing:"south",axis:"z",edge:room.z1,x:room.cx,z:room.z1},
   {facing:"north",axis:"z",edge:room.z2,x:room.cx,z:room.z2}
  ];
  const trapRoomCandidates=cells.filter(room=>room.index!==0&&!hidden.has(room.index)&&room.index!==lockedRoom).map(room=>({room,clear:trapPlans(room).filter(p=>!corridorCells.has(`${p.x},${p.z}`)&&(p.axis==="x"?Math.abs(p.edge-room.cx):Math.abs(p.edge-room.cz))>1).length,priority:typeFor(room.index)==="guard"?0:1})).filter(x=>x.clear>=1);
  trapRoomCandidates.sort((a,c)=>c.clear-a.clear||a.priority-c.priority||a.room.index-c.room.index);
  const trapRoom=trapRoomCandidates[0]?.room;
  if(trapRoom){
   const [tx,tz]=[trapRoom.cx,trapRoom.cz],triggerPosition=[tx,1,tz],dispenserPlans=[
    {dx:-1,dz:0,facing:"east",axis:"x",edge:trapRoom.x1},
    {dx:1,dz:0,facing:"west",axis:"x",edge:trapRoom.x2},
    {dx:0,dz:-1,facing:"south",axis:"z",edge:trapRoom.z1},
    {dx:0,dz:1,facing:"north",axis:"z",edge:trapRoom.z2}
   ];
   const dispensers=[],wirePositions=[];
   b.set(tx,1,tz,{name:"minecraft:stone_pressure_plate",properties:{powered:"false"}});
   for(const plan of dispenserPlans){
    const [wx,wz]=plan.axis==="x"?[plan.edge,tz]:[tx,plan.edge];
    if(corridorCells.has(`${wx},${wz}`))continue;
    const line=[];
    if(plan.axis==="x"){
     for(let x=Math.min(tx,wx)+1;x<Math.max(tx,wx);x++)line.push([x,tz]);
    }else{
     for(let z=Math.min(tz,wz)+1;z<Math.max(tz,wz);z++)line.push([tx,z]);
    }
    if(!line.length)continue;
    b.set(wx,1,wz,{name:"minecraft:dispenser",properties:{facing:plan.facing,triggered:"false"}},{id:"minecraft:dispenser",Items:[{Slot:0,id:"minecraft:arrow",count:8}]});
    for(const [x,z] of line){
     const properties=plan.axis==="x"?{east:"side",north:"none",power:"0",south:"none",west:"side"}:{east:"none",north:"side",power:"0",south:"side",west:"none"};
     b.set(x,1,z,{name:"minecraft:redstone_wire",properties});
     wirePositions.push([x,1,z]);
    }
    dispensers.push({position:[wx,1,wz],facing:plan.facing,arrowCount:8});
   }
   check(dispensers.length>=1,"No room can fit a functional redstone trap");
   traps.push({id:"arrow-volley-0",kind:"pressure-plate-arrow-volley",roomId:"room-"+trapRoom.index,triggerPosition,dispensers,wirePositions});
  }
  const keyRoomCandidates=cells.filter(room=>!hidden.has(room.index)&&room.index!==lockedRoom).map(room=>({room,safe:safeCorners(room),type:typeFor(room.index)})).filter(item=>item.safe.length>=(["treasure","boss"].includes(item.type)?2:1));
  const keyPriority={entrance:0,library:1,storage:2,treasure:3,guard:4,ritual:5,boss:6};
  keyRoomCandidates.sort((a,c)=>(keyPriority[a.type]??9)-(keyPriority[c.type]??9)||c.safe.length-a.safe.length||a.room.index-c.room.index);
  check(keyRoomCandidates.length>0,"No reachable room has a safe position for the key chest");
  const keyRoomIndex=keyRoomCandidates[0].room.index;
  const hash=value=>{let h=2166136261;for(let i=0;i<value.length;i++){h^=value.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(16);};
  const baseTag=(lootTablePrefix??"mms_structure:dungeons/generated")+":"+seed;
  const interactiveDoors=[];
  const addDoor=(id,kind,edge,width,key=null)=>{
   const [ia,ib]=edge,a=cells[ia],c=cells[ib],axis=a.row===c.row?"x":"z";
   const mid=axis==="x"?Math.floor((a.cx+c.cx)/2):Math.floor((a.cz+c.cz)/2);
   const crossStart=axis==="x"?a.cz:a.cx;
   const blocks=[];
   for(let offset=0;offset<width;offset++)for(let y=1;y<=2;y++){
    const pos=axis==="x"?[mid,y,crossStart+offset]:[crossStart+offset,y,mid];
    blocks.push(pos);b.set(...pos,kind==="locked"?"minecraft:iron_bars":"minecraft:bookshelf");
   }
   const nearIndex=kind==="locked"?(edge[0]===lockedRoom?edge[1]:edge[0]):(hiddenParents.get(edge[0])??hiddenParents.get(edge[1]));
   const farIndex=kind==="locked"?lockedRoom:(hidden.has(edge[0])?edge[0]:edge[1]);
   const near=cells[nearIndex],far=cells[farIndex];
   const nearNegative=axis==="x"?near.cx<far.cx:near.cz<far.cz;
   const position=axis==="x"?[mid+(nearNegative?0.35:0.65),1,crossStart+width/2]:[crossStart+width/2,1,mid+(nearNegative?0.35:0.65)];
   const tag="mmsd_"+hash(baseTag+":"+id);
   b.addEntity(position,{id:"minecraft:interaction",width:Math.max(1,width),height:2,response:true,Tags:[tag]});
   const door={id,kind,from:ia,to:ib,axis,blocks,position,width,tag,...(key?{keyId:key}:{})};
   interactiveDoors.push(door);
   return door;
  };
  const lockDoor=addDoor("lock-0","locked",lockedEdge,corridorWidth,keyId);
  const secretDoors=[...hidden].sort((a,c)=>a-c).map(index=>addDoor("secret-"+index,"secret",[index,hiddenParents.get(index)],1));
  const puzzleGatePlans=room=>[
   {axis:"x",side:"east",plane:room.x2-2,reward:[room.x2-1,1,room.cz],wall:room.x2,centerSide:room.cx<room.x2-2,from:[room.x2-2,1,room.z1+1],to:[room.x2-2,2,room.z2-1],line:Array.from({length:room.z2-room.z1-1},(_,i)=>[room.x2-2,room.z1+1+i])},
   {axis:"x",side:"west",plane:room.x1+2,reward:[room.x1+1,1,room.cz],wall:room.x1,centerSide:room.cx>room.x1+2,from:[room.x1+2,1,room.z1+1],to:[room.x1+2,2,room.z2-1],line:Array.from({length:room.z2-room.z1-1},(_,i)=>[room.x1+2,room.z1+1+i])},
   {axis:"z",side:"south",plane:room.z2-2,reward:[room.cx,1,room.z2-1],wall:room.z2,centerSide:room.cz<room.z2-2,from:[room.x1+1,1,room.z2-2],to:[room.x2-1,2,room.z2-2],line:Array.from({length:room.x2-room.x1-1},(_,i)=>[room.x1+1+i,room.z2-2])},
   {axis:"z",side:"north",plane:room.z1+2,reward:[room.cx,1,room.z1+1],wall:room.z1,centerSide:room.cz>room.z1+2,from:[room.x1+1,1,room.z1+2],to:[room.x2-1,2,room.z1+2],line:Array.from({length:room.x2-room.x1-1},(_,i)=>[room.x1+1+i,room.z1+2])}
  ].filter(plan=>plan.centerSide&&plan.line.length>=2&&plan.line.every(([x,z])=>!corridorCells.has(`${x},${z}`))&&!corridorCells.has(`${plan.reward[0]},${plan.reward[2]}`));
  const puzzlePriority={ritual:0,library:1,storage:2,treasure:3,guard:4,boss:5};
  const puzzleCandidates=cells.filter(room=>room.index!==0&&!hidden.has(room.index)&&room.index!==lockedRoom&&room.index!==trapRoom?.index).map(room=>{
   const gates=puzzleGatePlans(room),safe=safeCorners(room);
   const keyReserved=room.index===keyRoomIndex?safe[safe.length-1]:null;
   const options=gates.map(gate=>{
    const candidates=[];
    for(let x=room.x1+1;x<=room.x2-1;x++)for(let z=room.z1+1;z<=room.z2-1;z++){
     if(gate.axis==="x"&&(gate.side==="east"?x>=gate.plane:x<=gate.plane)||gate.axis==="z"&&(gate.side==="south"?z>=gate.plane:z<=gate.plane))continue;
     if((x===room.cx&&z===room.cz)||corridorCells.has(`${x},${z}`)||(keyReserved&&keyReserved[0]===x&&keyReserved[1]===z))continue;
     candidates.push([x,z]);
    }
    return {gate,candidates};
   }).filter(option=>option.candidates.length>=3);
   return {room,gates,options,safe,keyReserved,type:typeFor(room.index)};
  }).filter(item=>item.options.length&&item.safe.length>=(item.room.index===keyRoomIndex?4:0));
  puzzleCandidates.sort((a,c)=>Math.max(...c.options.map(x=>x.candidates.length))-Math.max(...a.options.map(x=>x.candidates.length))||(puzzlePriority[a.type]??9)-(puzzlePriority[c.type]??9)||a.room.index-c.room.index);
  const puzzles=[];
  const puzzleCandidate=puzzleCandidates[0];
  if(puzzleCandidate){
   const {room}=puzzleCandidate;
   puzzleCandidate.options.sort((a,c)=>c.candidates.length-a.candidates.length);
   const gate=puzzleCandidate.options[0].gate,candidates=puzzleCandidate.options[0].candidates.slice();
   const distance=(a,c)=>Math.abs(a[0]-c[0])+Math.abs(a[1]-c[1]);
   candidates.sort((a,c)=>distance(c,[room.cx,room.cz])-distance(a,[room.cx,room.cz])||a[1]-c[1]||a[0]-c[0]);
   const runePositions=[candidates.shift()];
   while(runePositions.length<3){
    candidates.sort((a,c)=>Math.min(...runePositions.map(p=>distance(c,p)))-Math.min(...runePositions.map(p=>distance(a,p)))||a[1]-c[1]||a[0]-c[0]);
    runePositions.push(candidates.shift());
   }
   const runeBlocks=["minecraft:redstone_block","minecraft:lapis_block","minecraft:emerald_block"];
   const sequence=shuffle([0,1,2]);
   const objective="mmsd_"+hash(baseTag+":puzzle").padStart(8,"0").slice(0,8);
   const scratchObjective="mmsd_"+hash(baseTag+":puzzle-scratch").padStart(8,"0").slice(0,8);
   const runes=runePositions.map(([x,z],index)=>{
    const tag="mmsd_"+hash(baseTag+":rune:"+index);
    b.set(x,1,z,runeBlocks[index]);
    b.addEntity([x+0.5,2,z+0.5],{id:"minecraft:interaction",width:0.9,height:1.5,response:true,Tags:[tag]});
    puzzleCells.add(`${x},${z}`);
    return {id:"rune-"+index,index,position:[x,1,z],tag,block:runeBlocks[index]};
   });
   const gateBlocks=[];
   for(let x=gate.from[0];x<=gate.to[0];x++)for(let z=gate.from[2];z<=gate.to[2];z++)for(let y=1;y<=2;y++){
    b.set(x,y,z,"minecraft:iron_bars");
    gateBlocks.push([x,y,z]);
   }
   const rewardPosition=gate.reward.slice();
   const puzzleLoot=lootTableFor("puzzle");
   b.set(...rewardPosition,{name:"minecraft:chest",properties:{facing:"north",type:"single",waterlogged:"false"}},{id:"minecraft:chest",LootTable:puzzleLoot});
   const clueOffsets=(gate.side==="west"||gate.side==="south")?[1,0,-1]:[-1,0,1];
   const cluePositions=gate.axis==="x"?clueOffsets.map(offset=>[gate.wall,3,room.cz+offset]):clueOffsets.map(offset=>[room.cx+offset,3,gate.wall]);
   const clueBlocks=sequence.map(index=>runeBlocks[index]);
   cluePositions.forEach((position,index)=>b.set(...position,clueBlocks[index]));
   const puzzle={id:"rune-sequence-0",kind:"three-rune-sequence",roomId:"room-"+room.index,sequence,runes,gate:{axis:gate.axis,side:gate.side,from:gate.from,to:gate.to,blocks:gateBlocks},rewardPosition,lootTable:puzzleLoot,cluePositions,clueBlocks,scoreboardObjective:objective,scratchObjective};
   puzzles.push(puzzle);
  }
  const rooms=cells.map((room,i)=>{
   const isHidden=hidden.has(i);
   const type=typeFor(i);
   const metadata={id:`room-${i}`,type,hidden:isHidden,pos:[room.cx,1,room.cz],bounds:[room.x1,room.z1,room.x2,room.z2]};const roomPuzzle=puzzles.find(p=>p.roomId===metadata.id);if(roomPuzzle)metadata.puzzleId=roomPuzzle.id;
   // Decorative blocks occupy corners, never the center used for connectivity tests.
   const decorations=type==="library"?["minecraft:bookshelf","minecraft:bookshelf"]:
    type==="treasure"?["minecraft:gold_block","minecraft:chiseled_stone_bricks"]:
    type==="boss"?[palette.accent,palette.accent]:
    type==="ritual"?["minecraft:crying_obsidian","minecraft:crying_obsidian"]:
    type==="hidden"?["minecraft:bookshelf","minecraft:bookshelf"]:
    ["minecraft:barrel","minecraft:chiseled_stone_bricks"];
   const safe=safeCorners(room);
   const keySpot=room.index===keyRoomIndex&&safe.length?safe.pop():null;
   const lootKind=type==="treasure"?"treasure":type==="boss"?"boss":type==="hidden"?"hidden":null;
   const lootSpot=lootKind&&safe.length?safe.pop():null;
   const hasEncounter=["guard","ritual","boss"].includes(type);
   if(!hasEncounter){
    if(safe[0])b.set(safe[0][0],1,safe[0][1],decorations[0]);
    if(safe[1])b.set(safe[1][0],1,safe[1][1],decorations[1]);
    if(safe[2])b.set(safe[2][0],1,safe[2][1],palette.light);
   }
   if(keySpot){
    b.set(keySpot[0],1,keySpot[1],{name:"minecraft:chest",properties:{facing:"north",type:"single",waterlogged:"false"}},{id:"minecraft:chest",Items:[{Slot:0,id:"minecraft:tripwire_hook",count:1,components:{"minecraft:custom_data":{mmsd_key:keyId},"minecraft:custom_name":{text:"Ancient Key",color:"gold",italic:false}}}]});
    metadata.keyPosition=[keySpot[0],1,keySpot[1]];
   }
   if(lootSpot){const lootTable=lootTableFor(lootKind);b.set(lootSpot[0],1,lootSpot[1],{name:"minecraft:chest",properties:{facing:"north",type:"single",waterlogged:"false"}},{id:"minecraft:chest",LootTable:lootTable});metadata.lootPosition=[lootSpot[0],1,lootSpot[1]];metadata.lootTable=lootTable;}
   if(hasEncounter){const trap=traps.find(t=>t.roomId===metadata.id),used=new Set([...(lootSpot?[lootSpot]:[]),...(trap?[trap.triggerPosition,...trap.wirePositions,...trap.dispensers.map(d=>d.position)]:[]),...(roomPuzzle?[...roomPuzzle.runes.map(r=>r.position),...roomPuzzle.gate.blocks,roomPuzzle.rewardPosition]:[])].map(p=>p.length===2?p.join(","):[p[0],p[2]].join(",")));metadata.encounterPositions=[];for(let x=room.x1+1;x<=room.x2-1;x++)for(let z=room.z1+1;z<=room.z2-1;z++)if(!corridorCells.has(`${x},${z}`)&&!used.has(`${x},${z}`))metadata.encounterPositions.push([x,1,z]);if(!metadata.encounterPositions.length)metadata.encounterPositions.push([room.cx,1,room.cz]);}
   return metadata;
  });
  const keyRoom=rooms[keyRoomIndex];
  const result=b.finish({generator:"room-graph-v1",style,seed,encounterDifficulty,roomHeight,shaftDepth,entranceShaft,roomCount:count,corridorWidth,loopChance,rooms,connections:allEdges.map(x=>({from:x.edge[0],to:x.edge[1],kind:x.tree?"tree":"loop",width:x.tree&&(hidden.has(x.edge[0])||hidden.has(x.edge[1]))?1:corridorWidth})),interactiveDoors,traps,puzzles,keyChest:{roomId:keyRoom.id,position:keyRoom.keyPosition,keyId},keyRoom:keyRoomIndex,lockedRoom,entrance:[entrance.cx,1,0],hiddenPassages:hiddenCount});
  core.validate(result);
  const walk=core.walkability(result);
  check(walk.entryValid&&walk.rooms.length===count&&walk.rooms.every(r=>r.reachable),"Generated room graph is not walkable");
  return result;
 }
 return {generateDungeon};
}
export const {generateDungeon}=createDungeonGenerator(core);
