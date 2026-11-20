// Pure transactional voxel editor; no browser dependencies.
import * as core from './core.mjs';
function makeEditor(core, initial){
  const MAX_HISTORY=80, AIR="minecraft:air";
  const key=p=>p.join(",");
  const clone=o=>JSON.parse(JSON.stringify(o));
  function canonical(s){
    core.validate(s);
    const b=core.createBuilder(s.size);
    for(const c of s.blocks)b.set(...c.pos,c.block);
    const m=s.metadata??{},meta={};
    if(typeof m.preset==="string")meta.preset=m.preset.slice(0,64);
    if(Number.isInteger(m.seed)&&m.seed>=0&&m.seed<=4294967295)meta.seed=m.seed;
    if(Array.isArray(m.rooms))meta.rooms=m.rooms.slice(0,128).filter(r=>r&&typeof r.id==="string"&&Array.isArray(r.pos)&&r.pos.length===3&&r.pos.every((n,i)=>Number.isInteger(n)&&n>=0&&n<s.size[i])).map(r=>({id:r.id.slice(0,64),pos:r.pos.slice()}));
    return b.finish(meta);
  }
  let size,metadata,cells,undo=[],redo=[];
  function load(s){const t=canonical(s);size=t.size;metadata=t.metadata;cells=new Map(t.blocks.map(c=>[key(c.pos),c]));undo=[];redo=[];}
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
  function snapshot(){return clone({schema:1,size:size.slice(),blocks:[...cells.values()].sort((a,b)=>a.pos[1]-b.pos[1]||a.pos[2]-b.pos[2]||a.pos[0]-b.pos[0]),metadata});}
  return {load,get,change,undo:()=>applyPatch(undo,redo,"before"),redo:()=>applyPatch(redo,undo,"after"),snapshot,size:()=>size.slice(),history:()=>({undo:undo.length,redo:redo.length}),count:()=>cells.size};
}
export const createEditor=initial=>makeEditor(core,initial);
