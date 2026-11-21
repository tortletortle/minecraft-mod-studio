// Structure Studio v0.1 — standalone, no DOM dependencies.
function createStructureCore(){
  const ID=/^[a-z0-9_.-]+:[a-z0-9_./-]+$/, PART=/^[a-z0-9_]+$/;
  const MAX=48;
  function check(ok,msg){if(!ok)throw new Error(msg);}
  function int(n,min,max,label){check(Number.isInteger(n)&&n>=min&&n<=max,`${label}: expected integer ${min}..${max}`);return n;}
  function normalizeBlock(block){
    if(typeof block==="string")block={name:block};
    check(block&&typeof block.name==="string"&&ID.test(block.name)&&!block.name.includes(".."),"Invalid block ID");
    const props=block.properties??{};
    check(props&&typeof props==="object"&&!Array.isArray(props),"Invalid block properties");
    const properties={};
    for(const k of Object.keys(props).sort()){const v=props[k];check(PART.test(k)&&typeof v==="string"&&/^[a-z0-9_-]+$/.test(v),"Invalid block state property");properties[k]=v;}
    return {name:block.name,properties};
  }
  function normalizeBlockEntity(block,nbt){
    check(nbt&&typeof nbt==="object"&&!Array.isArray(nbt),"Invalid block entity NBT");
    check(block.name==="minecraft:chest"&&nbt.id==="minecraft:chest","Only chest block entities are supported");
    check(typeof nbt.LootTable==="string"&&ID.test(nbt.LootTable)&&!nbt.LootTable.includes(".."),"Invalid chest loot table ID");
    check(Object.keys(nbt).every(k=>k==="id"||k==="LootTable"),"Unsupported block entity field");
    return {id:"minecraft:chest",LootTable:nbt.LootTable};
  }
  const key=(x,y,z)=>`${x},${y},${z}`;
  function createBuilder(size){
    check(Array.isArray(size)&&size.length===3,"size must be [x,y,z]");
    const [w,h,d]=size.map((n,i)=>int(n,1,MAX,`size[${i}]`));
    const cells=new Map();
    function set(x,y,z,block,nbt){int(x,0,w-1,"x");int(y,0,h-1,"y");int(z,0,d-1,"z");const normalized=normalizeBlock(block),cell={pos:[x,y,z],block:normalized};if(nbt!==undefined)cell.nbt=normalizeBlockEntity(normalized,nbt);cells.set(key(x,y,z),cell);}
    function box(x1,y1,z1,x2,y2,z2,block){
      int(x1,0,w-1,"x1");int(x2,x1,w-1,"x2");int(y1,0,h-1,"y1");int(y2,y1,h-1,"y2");int(z1,0,d-1,"z1");int(z2,z1,d-1,"z2");
      for(let y=y1;y<=y2;y++)for(let z=z1;z<=z2;z++)for(let x=x1;x<=x2;x++)set(x,y,z,block);
    }
    function finish(metadata={}){
      const blocks=[...cells.values()].sort((a,b)=>a.pos[1]-b.pos[1]||a.pos[2]-b.pos[2]||a.pos[0]-b.pos[0]);
      return {schema:1,size:[w,h,d],blocks,metadata};
    }
    return {set,box,finish};
  }
  function rng(seed){let x=int(seed,0,0xffffffff,"seed")>>>0;return ()=>{x=(x+0x6D2B79F5)>>>0;let t=x;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}
  const air="minecraft:air";
  function generate(options={}){
    const preset=options.preset??"house";
    check(["house","tower","factory"].includes(preset),"Unknown preset");
    const defaults={house:[13,7,11],tower:[11,15,11],factory:[27,8,17]}[preset];
    const size=options.size??defaults;
    check(Array.isArray(size)&&size.length===3,"Invalid size");
    const [w,h,d]=size;
    int(w,preset==="factory"?19:7,MAX,"width");int(h,preset==="tower"?9:6,MAX,"height");int(d,preset==="factory"?11:7,MAX,"depth");
    const seed=int(options.seed??1,0,0xffffffff,"seed"),random=rng(seed);
    const mats={house:["oak_planks","stone_bricks","spruce_planks"],tower:["stone_bricks","cobbled_deepslate","dark_oak_planks"],factory:["deepslate_bricks","polished_andesite","iron_block"]}[preset].map(s=>"minecraft:"+s);
    const wall=normalizeBlock(options.wall??mats[0]),floor=normalizeBlock(options.floor??mats[1]),roof=normalizeBlock(options.roof??mats[2]);
    check([wall,floor,roof].every(b=>!["minecraft:air","minecraft:cave_air","minecraft:void_air","minecraft:structure_void"].includes(b.name)),"Shell materials must be non-air");
    const b=createBuilder(size),mid=Math.floor(w/2);
    // Explicit air clears the interior when placed; omitted cells preserve existing terrain.
    b.box(0,0,0,w-1,h-1,d-1,air);
    b.box(0,0,0,w-1,0,d-1,floor);b.box(0,h-1,0,w-1,h-1,d-1,roof);
    b.box(0,1,0,0,h-2,d-1,wall);b.box(w-1,1,0,w-1,h-2,d-1,wall);
    b.box(1,1,0,w-2,h-2,0,wall);b.box(1,1,d-1,w-2,h-2,d-1,wall);
    b.box(mid,1,0,mid,2,0,air);
    for(let x=2;x<w-2;x+=4)if(Math.abs(x-mid)>1){b.set(x,2,0,"minecraft:glass");b.set(x,2,d-1,"minecraft:glass");}
    for(let z=2;z<d-2;z+=4){b.set(0,2,z,"minecraft:glass");b.set(w-1,2,z,"minecraft:glass");}
    const rooms=[{id:"entry",pos:[mid,1,1]}];
    if(preset==="house"){
      for(let z=3;z<d-2;z+=3){if(random()<0.65)b.set(1,1,z,"minecraft:crafting_table");}
      b.set(w-2,1,d-2,"minecraft:bookshelf");
    }
    if(preset==="tower"){
      // Ladder on inner west wall, floor landings with aligned two-cell shaft.
      for(let y=1;y<h-1;y++){
        if(y%4===0&&y<=h-4){b.box(1,y,1,w-2,y,d-2,floor);}
        b.set(1,y,1,{name:"minecraft:ladder",properties:{facing:"east",waterlogged:"false"}});
        if(y%4===1&&y>1&&y<=h-3)rooms.push({id:`landing-${y}`,pos:[2,y,1]});
      }
      for(let y=5;y<h-2;y+=4){b.set(mid,y,0,"minecraft:glass");b.set(mid,y,d-1,"minecraft:glass");}
    }
    if(preset==="factory"){
      // Four side rooms surround a central 3-block corridor.
      const left=mid-2,right=mid+2,zsplit=Math.floor(d/2);
      for(const x of [left,right]){b.box(x,1,1,x,h-2,d-2,wall);for(const z of [Math.floor(zsplit/2),Math.floor((zsplit+d-1)/2)])b.box(x,1,z,x,2,z,air);}
      b.box(1,1,zsplit,left-1,h-2,zsplit,wall);b.box(right+1,1,zsplit,w-2,h-2,zsplit,wall);
      for(const [x1,x2] of [[1,left-1],[right+1,w-2]])for(const [z1,z2] of [[1,zsplit-1],[zsplit+1,d-2]]){
        const cx=Math.floor((x1+x2)/2),cz=Math.floor((z1+z2)/2);
        rooms.push({id:`room-${rooms.length}`,pos:[cx,1,cz]});
        b.set(x1,1,z1,random()<0.5?"minecraft:iron_block":"minecraft:copper_block");
        b.set(x2,1,z2,"minecraft:crafting_table");
      }
    }
    return b.finish({preset,seed,rooms});
  }
  function validate(s){
    check(s&&s.schema===1&&Array.isArray(s.size)&&s.size.length===3&&Array.isArray(s.blocks),"Invalid structure");
    const size=s.size.map((n,i)=>int(n,1,MAX,`size[${i}]`));
    check(s.blocks.length<=size[0]*size[1]*size[2],"Too many blocks");
    const seen=new Set();
    for(const c of s.blocks){check(c&&Array.isArray(c.pos)&&c.pos.length===3,"Invalid position");c.pos.forEach((n,i)=>int(n,0,size[i]-1,`pos[${i}]`));const k=key(...c.pos);check(!seen.has(k),"Duplicate block position");seen.add(k);const block=normalizeBlock(c.block);if(c.nbt!==undefined)normalizeBlockEntity(block,c.nbt);}
    return s;
  }
  function paletteFor(s){
    validate(s);const palette=[],byBlock=new Map(),blocks=[];
    for(const c of [...s.blocks].sort((a,b)=>a.pos[1]-b.pos[1]||a.pos[2]-b.pos[2]||a.pos[0]-b.pos[0])){
      const block=normalizeBlock(c.block),k=JSON.stringify(block);
      if(!byBlock.has(k)){byBlock.set(k,palette.length);palette.push(block);}
      const entry={pos:c.pos.slice(),state:byBlock.get(k)};if(c.nbt!==undefined)entry.nbt=normalizeBlockEntity(block,c.nbt);blocks.push(entry);
    }
    return {size:s.size.slice(),palette,blocks};
  }
  function walkability(s){
    validate(s);const [w,h,d]=s.size,lookup=new Map(s.blocks.map(c=>[key(...c.pos),normalizeBlock(c.block).name]));
    const pass=(x,y,z)=>{const n=lookup.get(key(x,y,z));return n==="minecraft:air"||n==="minecraft:ladder";};
    // Flat ground analysis only, not a substitute for collision/pathfinding in game.
    const stand=(x,z)=>x>=0&&x<w&&z>=0&&z<d&&h>=3&&pass(x,1,z)&&pass(x,2,z)&&lookup.has(key(x,0,z))&&!pass(x,0,z);
    const entry=s.metadata?.rooms?.[0]?.pos;
    if(!entry||entry[1]!==1||!stand(entry[0],entry[2]))return {scope:"ground-floor-only",reachable:0,rooms:[],entryValid:false};
    const q=[[entry[0],entry[2]]],seen=new Set([`${entry[0]},${entry[2]}`]);
    for(let i=0;i<q.length;i++){const [x,z]=q[i];for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1]]){const a=x+dx,b=z+dz,k=`${a},${b}`;if(stand(a,b)&&!seen.has(k)){seen.add(k);q.push([a,b]);}}}
    return {scope:"ground-floor-only",reachable:seen.size,entryValid:true,rooms:(s.metadata?.rooms??[]).filter(r=>r.pos[1]===1).map(r=>({id:r.id,reachable:seen.has(`${r.pos[0]},${r.pos[2]}`)}))};
  }
  // Java NBT big-endian; ASCII identifiers only. Explicit version supplied by caller.
  function encodeNBT(s,{dataVersion,paletteKeys="legacy"}={}){
    int(dataVersion,1,2147483647,"dataVersion");check(["legacy","modern"].includes(paletteKeys),"Invalid palette key format");
    const {size,palette,blocks}=paletteFor(s),out=[];
    const byte=n=>out.push(n&255);
    const short=n=>{byte(n>>>8);byte(n);};
    const i32=n=>{byte(n>>>24);byte(n>>>16);byte(n>>>8);byte(n);};
    const str=s=>{check(/^[\x00-\x7f]*$/.test(s)&&s.length<=65535,"NBT string must be ASCII");short(s.length);for(let i=0;i<s.length;i++)byte(s.charCodeAt(i));};
    const tag=(t,name)=>{byte(t);str(name);};
    const namedInt=(name,n)=>{tag(3,name);i32(n);};
    const namedString=(name,s)=>{tag(8,name);str(s);};
    const list=(name,type,arr,write)=>{tag(9,name);byte(type);i32(arr.length);for(const a of arr)write(a);};
    tag(10,"");namedInt("DataVersion",dataVersion);list("size",3,size,i32);
    list("palette",10,palette,b=>{namedString(paletteKeys==="legacy"?"Name":"id",b.name);if(Object.keys(b.properties).length){tag(10,paletteKeys==="legacy"?"Properties":"properties");for(const [k,v] of Object.entries(b.properties))namedString(k,v);byte(0);}byte(0);});
    list("blocks",10,blocks,b=>{list("pos",3,b.pos,i32);namedInt("state",b.state);if(b.nbt){tag(10,"nbt");namedString("id",b.nbt.id);namedString("LootTable",b.nbt.LootTable);byte(0);}byte(0);});
    list("entities",10,[],()=>{});byte(0);return Uint8Array.from(out);
  }
  return {createBuilder,generate,validate,paletteFor,walkability,encodeNBT};
}
export const {createBuilder,generate,validate,paletteFor,walkability,encodeNBT}=createStructureCore();
