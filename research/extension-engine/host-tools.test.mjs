import {RecipeTransactions,planStructure} from './host-tools.mjs';
function runHostTests(makeHostTools,example){
 const {RecipeTransactions,planStructure}=makeHostTools(),results=[];
 const eq=(a,b)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error("ASSERT");};
 const throws=(f,c)=>{try{f()}catch(e){eq(e.message,c);return;}throw Error("EXPECTED "+c);};
 const test=(name,f)=>{try{f();results.push({name,pass:true})}catch(e){results.push({name,pass:false,error:e.message})}};
 const make=()=>{
   // Schema-3 fixture shaped from V2.5 make()/migrate(), not an imported user's actual draft.
   const item={uid:"item-1",id:"demo",name:"Demo",kind:"blank",damage:0,durability:1,rarity:"Common",stack:64,cooldown:0,pixels:Array(256).fill(null),recipe:Array(9).fill(""),behavior:null};
   const fixture={schemaVersion:3,name:"Demo",modId:"mms_structure",target:{loader:"fabric",minecraft:"26.2"},items:[item],studio:{blocks:[],mobs:[],quests:[],effects:[],guis:[],links:{}}};
   let raw=JSON.stringify(fixture),rev=0,failWrite=false,allowed=true;
   const host={read:()=>({revision:String(rev),raw}),compareAndSwap:(s,n)=>{if(s.revision!==String(rev)||s.raw!==raw)throw Error("STALE_PROJECT");if(failWrite)throw Error("WRITE_FAILED");raw=n;rev++;return {revision:String(rev)};}};
   const ingredients=["minecraft:oak_planks","","","","minecraft:stick","","","",""];
   let recipe={ingredients};
   let building={kind:"structure-preset",...example.buildings[0]};
   let active=true;
   const registry={list:t=>!active?[]:t==="recipe"?[{key:"demo:recipe",data:recipe}]:[{key:"demo:building",data:building}]};
   const validate=p=>({errors:allowed?[]:["mock validator rejected"]});
   return {host,fixture,ingredients,registry,tx:new RecipeTransactions({host,registry,validate}),setActive:b=>active=b,setRecipe:x=>recipe=x,setBuilding:x=>building=x,setWriteFailure:x=>failWrite=x,setValidate:x=>allowed=x,edit:f=>{const p=JSON.parse(raw);f(p);raw=JSON.stringify(p);rev++;}};
 };
 const preview=s=>s.tx.preview("demo:recipe","item-1");
 const commit=(s,p)=>s.tx.commit(p.token,{approved:true});
 test("preview preserves original snapshot",()=>{const s=make(),b=s.host.read(),p=preview(s);eq(s.host.read(),b);eq(p.diff.after,s.ingredients)});
 test("explicit approval required",()=>{const s=make(),p=preview(s);throws(()=>s.tx.commit(p.token),"APPROVAL_REQUIRED");eq(s.host.read().revision,"0")});
 test("valid commit modifies only recipe",()=>{const s=make();commit(s,preview(s));const expected=JSON.parse(JSON.stringify(s.fixture));expected.items[0].recipe=s.ingredients;eq(JSON.parse(s.host.read().raw),expected)});
 test("forged token refused",()=>{const s=make();throws(()=>s.tx.commit({}, {approved:true}),"INVALID_TOKEN")});
 test("token cannot be replayed",()=>{const s=make(),p=preview(s);commit(s,p);throws(()=>commit(s,p),"INVALID_TOKEN")});
 test("mutated preview cannot alter operation",()=>{const s=make(),p=preview(s);p.diff.after.fill("minecraft:diamond");commit(s,p);eq(JSON.parse(s.host.read().raw).items[0].recipe,s.ingredients)});
 test("concurrent project edit refused",()=>{const s=make(),p=preview(s);s.edit(p=>p.name="Edited");const current=s.host.read();throws(()=>commit(s,p),"STALE_PROJECT");eq(s.host.read(),current)});
 test("ABA edit refused by revision",()=>{const s=make(),p=preview(s);s.edit(p=>p.name="Edited");s.edit(p=>p.name="Demo");throws(()=>commit(s,p),"STALE_PROJECT")});
 test("two previews cannot overwrite",()=>{const s=make(),a=preview(s),b=preview(s);commit(s,a);throws(()=>commit(s,b),"STALE_PROJECT")});
 test("inactive package refused at preview",()=>{const s=make();s.setActive(false);throws(()=>preview(s),"CONTRIBUTION_NOT_ACTIVE")});
 test("revoked package refused at commit",()=>{const s=make(),p=preview(s);s.setActive(false);throws(()=>commit(s,p),"CONTRIBUTION_NOT_ACTIVE");eq(s.host.read().revision,"0")});
 test("changed contribution refused",()=>{const s=make(),p=preview(s);s.setRecipe({ingredients:Array(9).fill("minecraft:stone")});throws(()=>commit(s,p),"STALE_CONTRIBUTION")});
 test("invalid recipe size rejected",()=>{const s=make();s.setRecipe({ingredients:["minecraft:stone"]});throws(()=>preview(s),"INVALID_RECIPE")});
 test("empty recipe rejected",()=>{const s=make();s.setRecipe({ingredients:Array(9).fill("")});throws(()=>preview(s),"INVALID_RECIPE")});
 test("path traversal ingredient rejected",()=>{const s=make();s.setRecipe({ingredients:Array(9).fill("minecraft:../bad")});throws(()=>preview(s),"INVALID_RECIPE")});
 test("non-vanilla recipe refused by v0.2 policy",()=>{const s=make();s.setRecipe({ingredients:Array(9).fill("external:gem")});throws(()=>preview(s),"INVALID_RECIPE")});
 test("missing item rejected",()=>{const s=make();throws(()=>s.tx.preview("demo:recipe","missing"),"ITEM_NOT_FOUND")});
 test("host validator rejection during preview",()=>{const s=make();s.setValidate(false);throws(()=>preview(s),"PROJECT_VALIDATION_FAILED")});
 test("host validator rejection at commit",()=>{const s=make(),p=preview(s);s.setValidate(false);throws(()=>commit(s,p),"PROJECT_VALIDATION_FAILED");eq(s.host.read().revision,"0")});
 test("failed write leaves project intact and token retryable",()=>{const s=make(),p=preview(s),b=s.host.read();s.setWriteFailure(true);throws(()=>commit(s,p),"WRITE_FAILED");eq(s.host.read(),b);s.setWriteFailure(false);commit(s,p);eq(s.host.read().revision,"1")});
 test("undo restores exact original bytes",()=>{const s=make(),b=s.host.read(),r=commit(s,preview(s));s.tx.undo(r,{approved:true});eq(s.host.read().raw,b.raw);eq(s.host.read().revision,"2")});
 test("undo requires approval",()=>{const s=make(),r=commit(s,preview(s));throws(()=>s.tx.undo(r),"APPROVAL_REQUIRED")});
 test("undo never overwrites later edit",()=>{const s=make(),r=commit(s,preview(s));s.edit(p=>p.name="Later");const b=s.host.read();throws(()=>s.tx.undo(r,{approved:true}),"STALE_PROJECT");eq(s.host.read(),b)});
 test("invalid receipt denied",()=>{const s=make();throws(()=>s.tx.undo({}, {approved:true}),"INVALID_RECEIPT")});
 test("undo receipt single use",()=>{const s=make(),r=commit(s,preview(s));s.tx.undo(r,{approved:true});throws(()=>s.tx.undo(r,{approved:true}),"INVALID_RECEIPT")});
 test("same recipe no-op refused",()=>{const s=make();commit(s,preview(s));throws(()=>preview(s),"NO_CHANGE")});
 test("recipe preview rejects incompatible target",()=>{const s=make();s.edit(p=>p.target.loader="forge");throws(()=>preview(s),"UNSUPPORTED_PROJECT")});
 test("real structure sample house/tower/factory mapped without worldgen",()=>{const s=make();for(const spec of example.buildings){const {worldgen,...safe}=spec;s.setBuilding({kind:"structure-preset",...safe});const b=s.host.read();eq(planStructure(s.registry,"demo:building",s.fixture),{namespace:example.namespace,buildings:[safe]});eq(s.host.read(),b)}});
 test("worldgen is explicitly rejected at L1 boundary",()=>{const s=make();s.setBuilding({kind:"structure-preset",...example.buildings.find(x=>x.worldgen)});throws(()=>planStructure(s.registry,"demo:building",s.fixture),"INVALID_STRUCTURE_TEMPLATE")});
 test("structure traversal ID rejected",()=>{const s=make();s.setBuilding({kind:"structure-preset",id:"../x",preset:"house",seed:1});throws(()=>planStructure(s.registry,"demo:building",s.fixture),"INVALID_STRUCTURE_TEMPLATE")});
 test("structure reserved namespace rejected",()=>{const s=make();throws(()=>planStructure(s.registry,"demo:building",{...s.fixture,modId:"minecraft"}),"INVALID_NAMESPACE")});
 test("structure seed bounds enforced",()=>{const s=make();s.setBuilding({kind:"structure-preset",id:"house",preset:"house",seed:-1});throws(()=>planStructure(s.registry,"demo:building",s.fixture),"INVALID_STRUCTURE_TEMPLATE")});
 test("structure request rejects inactive contribution",()=>{const s=make();s.setActive(false);throws(()=>planStructure(s.registry,"demo:building",s.fixture),"CONTRIBUTION_NOT_ACTIVE")});
 return results;
}
const example={
  "namespace": "mms_structure",
  "buildings": [
    {
      "id": "house",
      "preset": "house",
      "seed": 42
    },
    {
      "id": "tower",
      "preset": "tower",
      "seed": 42
    },
    {
      "id": "factory",
      "preset": "factory",
      "seed": 42,
      "worldgen": {
        "spacing": 32,
        "separation": 8,
        "salt": 194207,
        "biomes": [
          "minecraft:plains"
        ]
      }
    }
  ]
};
const results=runHostTests(()=>({RecipeTransactions,planStructure}),example);
console.log(JSON.stringify(results,null,2));
if(results.some(x=>!x.pass))process.exitCode=1;
