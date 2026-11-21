import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {runInThisContext} from "node:vm";

globalThis.window??={};
const source=await readFile(new URL("./v25-extension-runtime.js",import.meta.url),"utf8");
runInThisContext(source,{filename:"v25-extension-runtime.js"});
const R=globalThis.window.MMSV25ExtensionRuntime;
assert.ok(R,"browser runtime bundle must publish its API");

const recipeData={name:"Diamond Sword",description:"Demo recipe",ingredients:[
 "minecraft:diamond","minecraft:diamond","","minecraft:diamond","minecraft:stick","","","minecraft:stick",""
]};
const manifest=()=>({id:"mms-demo-recipes",version:"1.0.0",sdkVersion:"0.1.0",permissions:["recipe.register"],dependencies:{},contributes:[{type:"recipe",id:"diamond-sword",data:recipeData}]});
const makeArchive=async()=>R.createMmse({manifest:JSON.stringify(manifest()),assets:[]},{parseManifest:R.parseManifest});
const makeStore=()=>{let n=0;return new R.PersistentExtensionStore({backend:new R.MemoryKVBackend(),idFactory:()=>`tx-${++n}`});};
const makeProject=()=>({schemaVersion:3,name:"Test",modId:"test_mod",items:[{uid:"item-1",id:"test_sword",name:"Test Sword",recipe:Array(9).fill("")}],studio:{blocks:[],mobs:[],quests:[],effects:[],guis:[],links:{}}});
const makeBridge=project=>R.createV25HostBridge({
 core:{migrate:p=>p,encode:p=>JSON.stringify(p),validate:p=>({errors:[],warnings:[]})},
 getProject:()=>project.value,replaceProject:p=>{project.value=p;},isEnabled:()=>true
});

test("MMSE writer and strict reader round-trip a data-only recipe package",async()=>{
 const archive=await makeArchive();
 const parsed=await R.readMmse(archive,{parseManifest:R.parseManifest});
 assert.equal(parsed.manifest.id,"mms-demo-recipes");
 assert.equal(parsed.assets.length,0);
 assert.equal(parsed.summary.fileCount,1);
});

test("package install is persistent and disabled until explicit permission grant",async()=>{
 const store=makeStore(),archive=await makeArchive(),prepared=await store.prepareInstall([archive]);
 await store.commit(prepared.txId,{approved:true});
 let packages=await store.listPackages();
 assert.equal(packages.length,1);assert.equal(packages[0].active,false);
 await assert.rejects(store.enableClosure("mms-demo-recipes",{"mms-demo-recipes":[]}),{message:"PERMISSION_DENIED"});
 await store.enableClosure("mms-demo-recipes",{"mms-demo-recipes":["recipe.register"]});
 packages=await store.listPackages();
 assert.equal(packages[0].active,true);assert.deepEqual(packages[0].grants,["recipe.register"]);
});

test("only enabled packages publish validated recipe contributions",async()=>{
 const store=makeStore(),prepared=await store.prepareInstall([await makeArchive()]);
 await store.commit(prepared.txId,{approved:true});
 assert.deepEqual(R.collectRecipeContributions(await store.listPackages()),[]);
 await store.enableClosure("mms-demo-recipes",{"mms-demo-recipes":["recipe.register"]});
 const rows=R.collectRecipeContributions(await store.listPackages());
 assert.equal(rows.length,1);assert.equal(rows[0].data.name,"Diamond Sword");
 assert.throws(()=>R.validateRecipeContribution({name:"bad",ingredients:["../../escape"]}),{message:"INVALID_RECIPE_INGREDIENTS"});
 assert.throws(()=>R.validateRecipeContribution({name:"bad",ingredients:Array(9).fill("minecraft:../escape")}),{message:"INVALID_RECIPE_INGREDIENT_ID"});
});

test("recipe contribution applies through validated host bridge only after approval",async()=>{
 const project={value:makeProject()},bridge=makeBridge(project);
 const plan=R.stageRecipeMutation(bridge,{itemUid:"item-1",packageId:"mms-demo-recipes",contributionId:"diamond-sword",data:recipeData});
 assert.deepEqual(project.value.items[0].recipe,Array(9).fill(""));
 bridge.commit(plan.token,{approved:true});
 assert.deepEqual(project.value.items[0].recipe,recipeData.ingredients);
});

test("stale V25 host plan cannot overwrite a later editor change",async()=>{
 const project={value:makeProject()},bridge=makeBridge(project);
 const plan=R.stageRecipeMutation(bridge,{itemUid:"item-1",packageId:"mms-demo-recipes",contributionId:"diamond-sword",data:recipeData});
 project.value={...project.value,name:"Edited in Studio"};
 assert.throws(()=>bridge.commit(plan.token,{approved:true}),{message:"HOST_PROJECT_CHANGED"});
 assert.equal(project.value.name,"Edited in Studio");
});

test("archive corruption is rejected before installation",async()=>{
 const archive=await makeArchive();archive[40]^=0x01;
 await assert.rejects(R.readMmse(archive,{parseManifest:R.parseManifest}));
});

test("recipe mutation rejects missing target and unsafe identifiers",async()=>{
 const project={value:makeProject()},bridge=makeBridge(project);
 assert.throws(()=>R.stageRecipeMutation(bridge,{itemUid:"missing",packageId:"p",contributionId:"c",data:recipeData}),error=>error.message==="MUTATION_STAGE_FAILED"&&error.details==="TARGET_ITEM_NOT_FOUND");
 assert.throws(()=>R.validateRecipeContribution({name:"bad",ingredients:Array(9).fill("minecraft:foo/../bar")}),{message:"INVALID_RECIPE_INGREDIENT_ID"});
});
