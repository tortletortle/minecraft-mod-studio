// Pure transactional voxel editor; no browser dependencies.
import * as core from './core.mjs';
function makeEditor(core, initial){
  const MAX_HISTORY=80, AIR="minecraft:air";
  const key=p=>p.join(",");
  const clone=o=>JSON.parse(JSON.stringify(o));
  const validPosition=(p,size)=>Array.isArray(p)&&p.length===3&&p.every((n,i)=>Number.isInteger(n)&&n>=0&&n<size[i]);
  function canonical(s){
    core.validate(s);
    const b=core.createBuilder(s.size);
    for(const c of s.blocks)b.set(...c.pos,c.block,c.nbt);
    for(const entity of s.entities??[])b.addEntity(entity.pos,entity.nbt);
    const m=s.metadata??{},meta={};
    for(const field of ["preset","generator","style"])if(typeof m[field]==="string"&&/^[a-z0-9_-]{1,64}$/.test(m[field]))meta[field]=m[field];
    if(Number.isInteger(m.seed)&&m.seed>=0&&m.seed<=4294967295)meta.seed=m.seed;
    if(Array.isArray(m.rooms))meta.rooms=m.rooms.slice(0,128).filter(r=>r&&typeof r.id==="string"&&Array.isArray(r.pos)&&r.pos.length===3&&r.pos.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])).map(r=>{const item={id:r.id.slice(0,64),pos:r.pos.slice()};if(typeof r.type==="string"&&/^[a-z0-9_-]{1,32}$/.test(r.type))item.type=r.type;if(typeof r.hidden==="boolean")item.hidden=r.hidden;if(Array.isArray(r.bounds)&&r.bounds.length===4&&r.bounds.every(Number.isInteger))item.bounds=r.bounds.slice();if(Array.isArray(r.lootPosition)&&r.lootPosition.length===3&&r.lootPosition.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i]))item.lootPosition=r.lootPosition.slice();if(typeof r.lootTable==="string"&&/^[a-z0-9_.-]+:[a-z0-9_./-]+$/.test(r.lootTable)&&!r.lootTable.includes(".."))item.lootTable=r.lootTable;if(Array.isArray(r.encounterPositions))item.encounterPositions=r.encounterPositions.slice(0,16).filter(p=>Array.isArray(p)&&p.length===3&&p.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])).map(p=>p.slice());if(Array.isArray(r.keyPosition)&&r.keyPosition.length===3&&r.keyPosition.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i]))item.keyPosition=r.keyPosition.slice();return item;});
    if(Array.isArray(m.connections))meta.connections=m.connections.slice(0,256).filter(e=>e&&Number.isInteger(e.from)&&Number.isInteger(e.to)&&e.from>=0&&e.to>=0&&e.from<128&&e.to<128&&["tree","loop"].includes(e.kind)&&Number.isInteger(e.width)&&e.width>=1&&e.width<=3).map(e=>({from:e.from,to:e.to,kind:e.kind,width:e.width}));
    if(Array.isArray(m.entrance)&&m.entrance.length===3&&m.entrance.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i]))meta.entrance=m.entrance.slice();
    if(Number.isInteger(m.hiddenPassages)&&m.hiddenPassages>=0&&m.hiddenPassages<=2)meta.hiddenPassages=m.hiddenPassages;
    if(Number.isInteger(m.roomCount)&&m.roomCount>=4&&m.roomCount<=16)meta.roomCount=m.roomCount;
    if(Number.isInteger(m.corridorWidth)&&m.corridorWidth>=1&&m.corridorWidth<=3)meta.corridorWidth=m.corridorWidth;
    if(typeof m.loopChance==="number"&&Number.isFinite(m.loopChance)&&m.loopChance>=0&&m.loopChance<=0.6)meta.loopChance=m.loopChance;
    if(["easy","standard","hard"].includes(m.encounterDifficulty))meta.encounterDifficulty=m.encounterDifficulty;
    if(Number.isInteger(m.roomHeight)&&m.roomHeight>=6&&m.roomHeight<=16)meta.roomHeight=m.roomHeight;
    if(Number.isInteger(m.shaftDepth)&&m.shaftDepth>=0&&m.shaftDepth<=48)meta.shaftDepth=m.shaftDepth;
    if(Array.isArray(m.interactiveDoors))meta.interactiveDoors=m.interactiveDoors.slice(0,8).filter(d=>d&&typeof d.id==="string"&&/^[a-z0-9_-]{1,32}$/.test(d.id)&&["locked","secret"].includes(d.kind)&&["x","z"].includes(d.axis)&&Array.isArray(d.blocks)&&d.blocks.length>=2&&d.blocks.length<=6&&d.blocks.every(p=>Array.isArray(p)&&p.length===3&&p.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i]))&&Array.isArray(d.position)&&d.position.length===3&&d.position.every((n,i)=>typeof n==="number"&&Number.isFinite(n)&&n>=0&&n<s.size[i])&&Number.isInteger(d.width)&&d.width>=1&&d.width<=3&&typeof d.tag==="string"&&/^[a-z0-9_.-]{1,64}$/.test(d.tag)).map(d=>({id:d.id,kind:d.kind,from:d.from,to:d.to,axis:d.axis,blocks:d.blocks.map(p=>p.slice()),position:d.position.slice(),width:d.width,tag:d.tag,...(typeof d.keyId==="string"?{keyId:d.keyId}:{})}));
    if(Array.isArray(m.traps))meta.traps=m.traps.slice(0,8).filter(t=>t&&typeof t.id==="string"&&/^[a-z0-9_-]{1,32}$/.test(t.id)&&t.kind==="pressure-plate-arrow-volley"&&typeof t.roomId==="string"&&Array.isArray(t.triggerPosition)&&t.triggerPosition.length===3&&t.triggerPosition.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])&&Array.isArray(t.dispensers)&&t.dispensers.length>=1&&t.dispensers.length<=4&&t.dispensers.every(d=>d&&Array.isArray(d.position)&&d.position.length===3&&d.position.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])&&["north","south","east","west"].includes(d.facing)&&Number.isInteger(d.arrowCount)&&d.arrowCount>=1&&d.arrowCount<=64)&&Array.isArray(t.wirePositions)&&t.wirePositions.length<=32&&t.wirePositions.every(p=>Array.isArray(p)&&p.length===3&&p.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i]))).map(t=>({id:t.id,kind:t.kind,roomId:t.roomId,triggerPosition:t.triggerPosition.slice(),dispensers:t.dispensers.map(d=>({position:d.position.slice(),facing:d.facing,arrowCount:d.arrowCount})),wirePositions:t.wirePositions.map(p=>p.slice())}));
    if(Array.isArray(m.puzzles))meta.puzzles=m.puzzles.slice(0,4).filter(p=>p&&typeof p.id==="string"&&/^[a-z0-9_-]{1,32}$/.test(p.id)&&p.kind==="three-rune-sequence"&&typeof p.roomId==="string"&&Array.isArray(p.sequence)&&p.sequence.length===3&&p.sequence.every(n=>Number.isInteger(n)&&n>=0&&n<=2)&&new Set(p.sequence).size===3&&Array.isArray(p.runes)&&p.runes.length===3&&p.runes.every(r=>r&&typeof r.id==="string"&&/^[a-z0-9_-]{1,32}$/.test(r.id)&&Number.isInteger(r.index)&&r.index>=0&&r.index<=2&&validPosition(r.position,s.size)&&typeof r.tag==="string"&&/^[a-z0-9_.-]{1,64}$/.test(r.tag)&&typeof r.block==="string"&&/^[a-z0-9_.-]+:[a-z0-9_/-]+$/.test(r.block))&&p.gate&&["x","z"].includes(p.gate.axis)&&["north","south","east","west"].includes(p.gate.side)&&validPosition(p.gate.from,s.size)&&validPosition(p.gate.to,s.size)&&Array.isArray(p.gate.blocks)&&p.gate.blocks.length>=2&&p.gate.blocks.length<=64&&p.gate.blocks.every(pos=>validPosition(pos,s.size))&&validPosition(p.rewardPosition,s.size)&&typeof p.lootTable==="string"&&/^[a-z0-9_.-]+:[a-z0-9_/-]+$/.test(p.lootTable)&&Array.isArray(p.cluePositions)&&p.cluePositions.length===3&&p.cluePositions.every(pos=>validPosition(pos,s.size))&&Array.isArray(p.clueBlocks)&&p.clueBlocks.length===3&&p.clueBlocks.every(id=>typeof id==="string"&&/^[a-z0-9_.-]+:[a-z0-9_/-]+$/.test(id))&&typeof p.scoreboardObjective==="string"&&/^[a-z0-9_.+-]{1,16}$/.test(p.scoreboardObjective)&&typeof p.scratchObjective==="string"&&/^[a-z0-9_.+-]{1,16}$/.test(p.scratchObjective)).map(p=>({id:p.id,kind:p.kind,roomId:p.roomId.slice(0,64),sequence:p.sequence.slice(),runes:p.runes.map(r=>({id:r.id,index:r.index,position:r.position.slice(),tag:r.tag,block:r.block})),gate:{axis:p.gate.axis,side:p.gate.side,from:p.gate.from.slice(),to:p.gate.to.slice(),blocks:p.gate.blocks.map(pos=>pos.slice())},rewardPosition:p.rewardPosition.slice(),lootTable:p.lootTable,cluePositions:p.cluePositions.map(pos=>pos.slice()),clueBlocks:p.clueBlocks.slice(),scoreboardObjective:p.scoreboardObjective,scratchObjective:p.scratchObjective}));
    if(m.keyChest&&Array.isArray(m.keyChest.position)&&m.keyChest.position.length===3&&m.keyChest.position.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])&&typeof m.keyChest.keyId==="string"&&/^[a-z0-9_.-]+:[a-z0-9_./-]+$/.test(m.keyChest.keyId))meta.keyChest={roomId:String(m.keyChest.roomId??"").slice(0,64),position:m.keyChest.position.slice(),keyId:m.keyChest.keyId};
    if(m.entranceShaft&&Array.isArray(m.entranceShaft.position)&&m.entranceShaft.position.length===3&&m.entranceShaft.position.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])&&Array.isArray(m.entranceShaft.support)&&m.entranceShaft.support.length===3&&m.entranceShaft.support.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])&&Array.isArray(m.entranceShaft.exit)&&m.entranceShaft.exit.length===3&&m.entranceShaft.exit.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])&&Number.isInteger(m.entranceShaft.depth)&&m.entranceShaft.depth>=12&&m.entranceShaft.depth<=48&&["north","south","east","west"].includes(m.entranceShaft.facing))meta.entranceShaft={position:m.entranceShaft.position.slice(),support:m.entranceShaft.support.slice(),depth:m.entranceShaft.depth,facing:m.entranceShaft.facing,exit:m.entranceShaft.exit.slice()};
    return b.finish(meta);
  }
  let size,metadata,entities,cells,undo=[],redo=[];
  function load(s){const t=canonical(s);size=t.size;metadata=t.metadata;entities=t.entities??[];cells=new Map(t.blocks.map(c=>[key(c.pos),c]));undo=[];redo=[];}
  load(initial);
  function get(p){return clone(cells.get(key(p))??null);}
  function change(positions,mode,block){
    if(!["place","erase","preserve"].includes(mode)||!Array.isArray(positions)||positions.length>size.reduce((a,b)=>a*b,1))throw Error("Invalid edit");
    // Build and validate the entire edit before applying anything.
    const seen=new Set(),patch=[];
    for(const p of positions){
      if(!Array.isArray(p)||p.length!==3)throw Error("Invalid position");
      const b=core.createBuilder(size);b.set(...p,mode==="place"?block:AIR);
      const k=key(p);if(seen.has(k))continue;seen.add(k);
      const before=cells.get(k)??null;
      const after=mode==="preserve"?null:b.finish().blocks[0];
      if(JSON.stringify(before)!==JSON.stringify(after))patch.push({k,before,after});
    }
    if(!patch.length)return false;
    for(const {k,after} of patch)after?cells.set(k,after):cells.delete(k);
    undo.push(patch);if(undo.length>MAX_HISTORY)undo.shift();redo=[];return true;
  }
  function applyPatch(stack,other,field){
    const p=stack.pop();if(!p)return false;
    for(const x of p){const c=x[field];c?cells.set(x.k,c):cells.delete(x.k);}other.push(p);return true;
  }
  function snapshot(){return clone({schema:1,size:size.slice(),blocks:[...cells.values()].sort((a,b)=>a.pos[1]-b.pos[1]||a.pos[2]-b.pos[2]||a.pos[0]-b.pos[0]),entities,metadata});}
  return {load,get,change,undo:()=>applyPatch(undo,redo,"before"),redo:()=>applyPatch(redo,undo,"after"),snapshot,size:()=>size.slice(),history:()=>({undo:undo.length,redo:redo.length}),count:()=>cells.size};
}
export const createEditor=initial=>makeEditor(core,initial);
