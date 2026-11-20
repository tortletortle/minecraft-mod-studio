// Pure resource planner; raw NBT bytes become gzip only at the IO boundary.
import * as core from './core.mjs';
function planPack(core, options){
 const fail=m=>{throw Error(m)}, check=(ok,m)=>{if(!ok)fail(m)}, integer=(n,min,max,label)=>{check(Number.isInteger(n)&&n>=min&&n<=max,label+" must be an integer in "+min+".."+max);return n;};
 const ns=options.namespace??"mms_structure";
 const segment=/^[a-z0-9][a-z0-9_-]{0,47}$/;
 check(typeof ns==="string"&&segment.test(ns)&&!["minecraft","realms"].includes(ns),"Invalid or reserved namespace");
 const specs=options.buildings;
 check(Array.isArray(specs)&&specs.length>=1&&specs.length<=8,"Expected 1..8 buildings");
 const files=new Map(), json=(path,o)=>{check(!files.has(path),"Duplicate pack path");files.set(path,JSON.stringify(o,null,2)+"\n");}, raw=(path,b)=>{check(!files.has(path),"Duplicate pack path");files.set(path,b);};
 json("pack.mcmeta",{pack:{description:"Minecraft Mod Studio structures — Java 26.2",min_format:[107,1],max_format:[107,1]}});
 const prefix="data/"+ns+"/",buildingIds=new Set(), reports=[], salts=new Set();
 for(const spec of specs){
  check(spec&&typeof spec==="object","Invalid building specification");
  const id=spec.id;check(typeof id==="string"&&segment.test(id)&&!buildingIds.has(id),"Invalid or duplicate building ID");buildingIds.add(id);
  const st=core.generate(spec), rid=ns+":"+id, w=core.walkability(st);
  check(w.entryValid&&w.rooms.every(r=>r.reachable),"Ground-floor reachability failed");
  raw(prefix+"structure/"+id+".nbt",core.encodeNBT(st,{dataVersion:4903,paletteKeys:"legacy"}));
  const report={id:rid,size:st.size,seed:st.metadata.seed,preset:st.metadata.preset,rooms:w,placeCommand:"/place template "+rid+" ~ ~ ~",worldgen:false};
  if(spec.worldgen!==undefined&&spec.worldgen!==false){
   const g=spec.worldgen;check(g&&typeof g==="object"&&!Array.isArray(g),"worldgen must be false or object");
   const spacing=integer(g.spacing??32,4,256,"spacing"),separation=integer(g.separation??8,1,spacing-1,"separation");
   const salt=integer(g.salt,0,2147483647,"salt");check(!salts.has(salt),"Duplicate worldgen salt");salts.add(salt);
   const biomes=g.biomes??["minecraft:plains"];
   check(Array.isArray(biomes)&&biomes.length>0&&biomes.length<=32&&biomes.every(x=>typeof x==="string"&&/^(?:[a-z0-9_.-]+):[a-z0-9_/-]+$/.test(x)),"Invalid biomes");
   const height=integer(g.heightOffset??0,-32,32,"heightOffset");
   json(prefix+"tags/worldgen/biome/"+id+".json",{replace:false,values:[...new Set(biomes)]});
   json(prefix+"worldgen/template_pool/"+id+".json",{fallback:"minecraft:empty",elements:[{weight:1,element:{element_type:"minecraft:single_pool_element",location:rid,processors:"minecraft:empty",projection:"rigid"}}]});
   json(prefix+"worldgen/structure/"+id+".json",{type:"minecraft:jigsaw",biomes:"#"+rid,step:"surface_structures",spawn_overrides:{},terrain_adaptation:"beard_thin",start_pool:rid,size:0,start_height:{absolute:height},project_start_to_heightmap:"WORLD_SURFACE_WG",max_distance_from_center:80,use_expansion_hack:false});
   json(prefix+"worldgen/structure_set/"+id+".json",{structures:[{structure:rid,weight:1}],placement:{type:"minecraft:random_spread",spacing,separation,salt}});
   Object.assign(report,{worldgen:true,spacing,separation,salt,locateCommand:"/locate structure "+rid,forceCommand:"/place structure "+rid+" ~ ~ ~"});
  }
  reports.push(report);
 }
 return {files,report:{schema:1,target:"Java 26.2",dataVersion:4903,packFormat:[107,1],namespace:ns,buildings:reports,warning:"Templates explicitly include air. Use a disposable world. Worldgen is experimental until game registry and new-chunk tests pass."}};
}
export const createPack=options=>planPack(core,options);
