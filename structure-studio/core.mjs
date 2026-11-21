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
    if(typeof nbt.LootTable==="string"){
      check(ID.test(nbt.LootTable)&&!nbt.LootTable.includes(".."),"Invalid chest loot table ID");
      check(Object.keys(nbt).every(k=>k==="id"||k==="LootTable"),"Unsupported loot chest field");
      return {id:"minecraft:chest",LootTable:nbt.LootTable};
    }
    check(Array.isArray(nbt.Items)&&nbt.Items.length>=1&&nbt.Items.length<=27,"Invalid chest Items");
    check(Object.keys(nbt).every(k=>k==="id"||k==="Items"),"Unsupported item chest field");
    const slots=new Set(),Items=nbt.Items.map(item=>{
      check(item&&typeof item==="object"&&!Array.isArray(item),"Invalid chest item");
      check(Number.isInteger(item.Slot)&&item.Slot>=0&&item.Slot<=26&&!slots.has(item.Slot),"Invalid or duplicate chest slot");slots.add(item.Slot);
      check(typeof item.id==="string"&&ID.test(item.id)&&!item.id.includes(".."),"Invalid chest item ID");
      check(Number.isInteger(item.count)&&item.count>=1&&item.count<=64,"Invalid chest item count");
      const components=item.components;
      check(components&&typeof components==="object"&&!Array.isArray(components),"Invalid chest item components");
      check(Object.keys(components).every(k=>k==="minecraft:custom_data"||k==="minecraft:custom_name"),"Unsupported chest item component");
      const data=components["minecraft:custom_data"],name=components["minecraft:custom_name"];
      check(data&&typeof data==="object"&&!Array.isArray(data)&&typeof data.mmsd_key==="string"&&ID.test(data.mmsd_key)&&!data.mmsd_key.includes(".."),"Invalid dungeon key custom data");
      check(name&&typeof name==="object"&&!Array.isArray(name)&&typeof name.text==="string"&&name.text.length>0&&name.text.length<=64&&name.color==="gold"&&name.italic===false&&Object.keys(name).every(k=>["text","color","italic"].includes(k)),"Invalid dungeon key display name");
      check(Object.keys(item).every(k=>["Slot","id","count","components"].includes(k)),"Unsupported chest item field");
      return {Slot:item.Slot,id:item.id,count:item.count,components:{"minecraft:custom_data":{mmsd_key:data.mmsd_key},"minecraft:custom_name":{text:name.text,color:name.color,italic:false}}};
    });
    return {id:"minecraft:chest",Items};
  }
  function normalizeStructureEntity(entity,size){
    check(entity&&typeof entity==="object"&&!Array.isArray(entity),"Invalid structure entity");
    check(entity.nbt&&entity.nbt.id==="minecraft:interaction","Only interaction entities are supported in structure templates");
    check(Array.isArray(entity.pos)&&entity.pos.length===3&&entity.pos.every((n,i)=>typeof n==="number"&&Number.isFinite(n)&&n>=0&&n<size[i]),"Invalid structure entity position");
    const blockPos=entity.pos.map(Math.floor);
    check(Array.isArray(entity.blockPos)&&entity.blockPos.length===3&&entity.blockPos.every((n,i)=>Number.isInteger(n)&&n===blockPos[i]),"Invalid structure entity block position");
    const nbt=entity.nbt,width=nbt.width??1,height=nbt.height??1,response=nbt.response??false,Tags=nbt.Tags;
    check(Number.isFinite(width)&&width>=0.1&&width<=4&&Number.isFinite(height)&&height>=0.1&&height<=4,"Invalid interaction entity hitbox");
    check(typeof response==="boolean","Invalid interaction entity response");
    check(Array.isArray(Tags)&&Tags.length>=1&&Tags.length<=8&&Tags.every(t=>typeof t==="string"&&/^[a-z0-9_.-]{1,64}$/.test(t)),"Invalid interaction entity tags");
    check(Object.keys(nbt).every(k=>["id","width","height","response","Tags"].includes(k)),"Unsupported interaction entity field");
    return {pos:entity.pos.slice(),blockPos,nbt:{id:"minecraft:interaction",width,height,response,Tags:[...new Set(Tags)]}};
  }
  const key=(x,y,z)=>`${x},${y},${z}`;
  function createBuilder(size){
    check(Array.isArray(size)&&size.length===3,"size must be [x,y,z]");
    const [w,h,d]=size.map((n,i)=>int(n,1,MAX,`size[${i}]`));
    const cells=new Map(),entities=[];
    function set(x,y,z,block,nbt){int(x,0,w-1,"x");int(y,0,h-1,"y");int(z,0,d-1,"z");const normalized=normalizeBlock(block),cell={pos:[x,y,z],block:normalized};if(nbt!==undefined)cell.nbt=normalizeBlockEntity(normalized,nbt);cells.set(key(x,y,z),cell);}
    function addEntity(pos,nbt){entities.push(normalizeStructureEntity({pos,blockPos:pos.map(Math.floor),nbt},[w,h,d]));}
    function box(x1,y1,z1,x2,y2,z2,block){
      int(x1,0,w-1,"x1");int(x2,x1,w-1,"x2");int(y1,0,h-1,"y1");int(y2,y1,h-1,"y2");int(z1,0,d-1,"z1");int(z2,z1,d-1,"z2");
      for(let y=y1;y<=y2;y++)for(let z=z1;z<=z2;z++)for(let x=x1;x<=x2;x++)set(x,y,z,block);
    }
    function finish(metadata={}){
      const blocks=[...cells.values()].sort((a,b)=>a.pos[1]-b.pos[1]||a.pos[2]-b.pos[2]||a.pos[0]-b.pos[0]);
      return {schema:1,size:[w,h,d],blocks,entities:entities.map(e=>JSON.parse(JSON.stringify(e))),metadata};
    }
    return {set,box,addEntity,finish};
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
    check(s.entities===undefined||Array.isArray(s.entities),"Invalid structure entities");
    check((s.entities??[]).length<=256,"Too many structure entities");
    for(const entity of s.entities??[])normalizeStructureEntity(entity,size);
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
    const interactive=new Set((s.metadata?.interactiveDoors??[]).flatMap(door=>Array.isArray(door.blocks)?door.blocks.map(p=>key(...p)):[]));
    const pass=(x,y,z)=>{const k=key(x,y,z),n=lookup.get(k);return n==="minecraft:air"||n==="minecraft:ladder"||interactive.has(k);};
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
    const f32=n=>{const buf=new ArrayBuffer(4);new DataView(buf).setFloat32(0,n,false);for(const v of new Uint8Array(buf))byte(v);};
    const f64=n=>{const buf=new ArrayBuffer(8);new DataView(buf).setFloat64(0,n,false);for(const v of new Uint8Array(buf))byte(v);};
    const str=s=>{check(/^[\x00-\x7f]*$/.test(s)&&s.length<=65535,"NBT string must be ASCII");short(s.length);for(let i=0;i<s.length;i++)byte(s.charCodeAt(i));};
    const tag=(t,name)=>{byte(t);str(name);};
    const namedInt=(name,n)=>{tag(3,name);i32(n);};
    const namedString=(name,s)=>{tag(8,name);str(s);};
    const list=(name,type,arr,write)=>{tag(9,name);byte(type);i32(arr.length);for(const a of arr)write(a);};
    tag(10,"");namedInt("DataVersion",dataVersion);list("size",3,size,i32);
    list("palette",10,palette,b=>{namedString(paletteKeys==="legacy"?"Name":"id",b.name);if(Object.keys(b.properties).length){tag(10,paletteKeys==="legacy"?"Properties":"properties");for(const [k,v] of Object.entries(b.properties))namedString(k,v);byte(0);}byte(0);});
    list("blocks",10,blocks,b=>{list("pos",3,b.pos,i32);namedInt("state",b.state);if(b.nbt){tag(10,"nbt");namedString("id",b.nbt.id);if(b.nbt.LootTable)namedString("LootTable",b.nbt.LootTable);if(b.nbt.Items)list("Items",10,b.nbt.Items,item=>{tag(1,"Slot");byte(item.Slot);namedString("id",item.id);namedInt("count",item.count);tag(10,"components");tag(10,"minecraft:custom_data");namedString("mmsd_key",item.components["minecraft:custom_data"].mmsd_key);byte(0);tag(10,"minecraft:custom_name");namedString("text",item.components["minecraft:custom_name"].text);namedString("color",item.components["minecraft:custom_name"].color);tag(1,"italic");byte(0);byte(0);byte(0);});byte(0);}byte(0);});
    list("entities",10,s.entities??[],e=>{list("pos",6,e.pos,f64);list("blockPos",3,e.blockPos,i32);tag(10,"nbt");namedString("id",e.nbt.id);tag(5,"width");f32(e.nbt.width);tag(5,"height");f32(e.nbt.height);tag(1,"response");byte(e.nbt.response?1:0);list("Tags",8,e.nbt.Tags,str);byte(0);});byte(0);return Uint8Array.from(out);
  }
  return {createBuilder,generate,validate,paletteFor,walkability,encodeNBT};
}
export const {createBuilder,generate,validate,paletteFor,walkability,encodeNBT}=createStructureCore();
