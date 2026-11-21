import * as core from './core.mjs';
import {createEditor} from './editor-model.mjs';
import {projection} from './projection.mjs';
import {generateDungeon} from './dungeon.mjs';
function editorSuite(core,createEditor,projection){
 let n=0;const a=(ok,m)=>{if(!ok)throw Error(m);n++;};const eq=(x,y,m)=>a(JSON.stringify(x)===JSON.stringify(y),m);const throws=f=>{let yes=false;try{f();}catch{yes=true;}a(yes,"reject invalid edit");};
 const initial=core.createBuilder([4,4,4]).finish(),ed=createEditor(initial);
 a(ed.change([[1,2,3]],"place","minecraft:stone"),"place");eq(ed.get([1,2,3]).block.name,"minecraft:stone","placed");
 a(!ed.change([[1,2,3]],"place","minecraft:stone"),"noop");eq(ed.history(),{undo:1,redo:0},"history");
 a(ed.change([[1,2,3]],"erase"),"erase");eq(ed.get([1,2,3]).block.name,"minecraft:air","air");
 a(ed.change([[1,2,3]],"preserve"),"preserve");eq(ed.get([1,2,3]),null,"absent");
 a(ed.undo(),"undo");eq(ed.get([1,2,3]).block.name,"minecraft:air","undo preserve");
 a(ed.undo(),"undo");eq(ed.get([1,2,3]).block.name,"minecraft:stone","undo erase");
 a(ed.redo(),"redo");eq(ed.get([1,2,3]).block.name,"minecraft:air","redo erase");
 const before=ed.snapshot();throws(()=>ed.change([[0,0,0],[4,0,0]],"place","minecraft:glass"));eq(ed.snapshot(),before,"atomic invalid position");
 throws(()=>ed.change([[0,0,0]],"place","bad"));eq(ed.snapshot(),before,"atomic invalid block");
 a(ed.change([[0,0,0],[0,0,0],[0,1,0]],"place","minecraft:glass"),"multi-edit");eq(ed.history().redo,0,"invalidate redo");eq(ed.count(),3,"dedup");
 const snap=ed.snapshot();snap.blocks[0].block.name="minecraft:air";a(ed.snapshot().blocks[0].block.name!=="minecraft:air","copy isolation");
 ed.load(initial);eq(ed.history(),{undo:0,redo:0},"reset");eq(ed.count(),0,"empty");
 for(let i=0;i<90;i++)ed.change([[0,0,0]],"place",i%2?"minecraft:stone":"minecraft:glass");eq(ed.history().undo,80,"cap history");for(let i=0;i<80;i++)a(ed.undo(),"bounded undo");a(!ed.undo(),"empty history");for(let i=0;i<80;i++)a(ed.redo(),"redo");
 for(const size of [[4,4,4],[27,8,17],[48,48,48],[1,1,1]])for(const rot of [0,1,2,3])for(const layer of [0,size[1]-1])for(const viewport of [[800,600],[350,420]]){
  const pr=projection(size,rot,layer,viewport);for(const x of new Set([0,Math.floor(size[0]/2),size[0]-1]))for(const z of new Set([0,Math.floor(size[2]/2),size[2]-1]))eq(pr.pick(...pr.point(x+.5,layer+1,z+.5),layer+1),[x,z],"roundtrip all rotations");
  eq(pr.pick(...pr.point(-.5,layer+1,0.5),layer+1),null,"out-of-bounds pick");
  a(pr.point(0,layer+1,0).every(Number.isFinite),"finite");
 }
 const dungeon=generateDungeon({seed:42,rooms:10,style:"crypt",hiddenRooms:2,corridorWidth:3,loopChance:0.34}),d=createEditor(dungeon),dm=d.snapshot().metadata;
 eq(dm.generator,"room-graph-v1","dungeon generator metadata");
 eq(dm.style,"crypt","dungeon style metadata");
 eq(dm.roomCount,10,"dungeon room count metadata");
 eq(dm.hiddenPassages,2,"dungeon hidden-room metadata");
 eq(dm.corridorWidth,3,"dungeon corridor metadata");
 eq(dm.loopChance,0.34,"dungeon loop metadata");
 eq(dm.rooms.map(r=>[r.id,r.type,r.hidden,r.pos,r.bounds]),dungeon.metadata.rooms.map(r=>[r.id,r.type,r.hidden,r.pos,r.bounds]),"dungeon room metadata roundtrip");
 eq(dm.connections,dungeon.metadata.connections,"dungeon graph metadata roundtrip");
 const factory=core.generate({preset:"factory",seed:42}),f=createEditor(factory);eq(f.snapshot(),factory,"generated roundtrip");const original=f.snapshot();f.change([[13,1,1]],"place","minecraft:stone");a(!core.walkability(f.snapshot()).entryValid,"blocked entry");f.undo();eq(f.snapshot(),original,"restore generated map");
 return n;
}
console.log(editorSuite(core,createEditor,projection)+' editor and projection assertions passed');
