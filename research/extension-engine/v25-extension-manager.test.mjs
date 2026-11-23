import test from "node:test";
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {createContext,runInContext} from "node:vm";

const root=new URL("./",import.meta.url);
const [html,runtime,manager]=await Promise.all([
 readFile(new URL("../../Minecraft_Mod_Studio_V25.html",root),"utf8"),
 readFile(new URL("./v25-extension-runtime.js",import.meta.url),"utf8"),
 readFile(new URL("./v25-extension-manager.js",import.meta.url),"utf8")
]);
const inline=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
assert.ok(inline.length>=2,"V25 StudioBehavior and StudioCore scripts must exist");
assert.ok(html.includes("<!-- MMS_V25_EXTENSION_INTEGRATION_START -->"));
assert.ok(html.includes(runtime),"standalone V25 HTML must embed the tested runtime bundle");
assert.ok(html.includes(manager),"standalone V25 HTML must embed the extension manager UI");

const setup=String.raw`
let document;
class FakeElement{
 constructor(tag="div"){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.dataset={};this.style={};this.classList={add(){},remove(){},toggle(){}};this.disabled=false;this.checked=false;this.value="";this.files=[];this.open=false;this.parentNode=null;this._text="";}
 set id(v){this._id=v;document.elements.set(v,this)}get id(){return this._id}
 set innerHTML(v){this.children=[];for(const m of v.matchAll(/id="([^"]+)"/g)){const e=new FakeElement();e.id=m[1];this.append(e)}}
 set textContent(v){this._text=String(v);this.children=[]}get textContent(){return this._text||this.children.map(x=>x.textContent).join("")}
 append(...nodes){for(const n of nodes){if(n&&typeof n==="object"){n.parentNode=this;this.children.push(n)}}}
 replaceChildren(...nodes){this.children=[];this.append(...nodes)}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}
 async dispatch(type,event={}){for(const fn of this.listeners[type]||[])await fn({target:this,...event})}
 async click(){if(this.disabled)return;const result=this.onclick?.({target:this});if(result?.then)await result;await this.dispatch("click")}
 after(node){node.parentNode=this.parentNode;this.parentNode.children.splice(this.parentNode.children.indexOf(this)+1,0,node)}
 setAttribute(k,v){this[k]=v}showModal(){this.open=true}close(){this.open=false}
}
document={elements:new Map(),createElement(tag){return new FakeElement(tag)},getElementById(id){return this.elements.get(id)||null},querySelector(selector){if(selector===".top-actions")return this.topActions;return null},querySelectorAll(){return[]}};
document.head=new FakeElement();document.body=new FakeElement();document.topActions=new FakeElement();
const resourceButton=new FakeElement("button");resourceButton.id="openResources";document.topActions.append(resourceButton);
const dbs=new Map();
const indexedDB={open(name){
 const request={};
 queueMicrotask(()=>{
  if(!dbs.has(name))dbs.set(name,new Map());
  const data=dbs.get(name);
  request.result={objectStoreNames:{contains:()=>true},createObjectStore(){},close(){},transaction(){
   const draft=new Map(data);let pending=0,started=false,done=false;
   const tx={};
   const check=()=>{if(started&&pending===0&&!done){done=true;queueMicrotask(()=>{data.clear();for(const [k,v] of draft)data.set(k,v);tx.oncomplete?.()})}};
   const schedule=fn=>{pending++;queueMicrotask(()=>{try{fn()}finally{pending--;check()}})};
   const store={
    get(key){const req={};schedule(()=>{req.result=draft.get(key);req.onsuccess?.({target:req})});return req},
    put(value){schedule(()=>draft.set(value.key,value))},
    delete(key){schedule(()=>draft.delete(key))},
    openCursor(){const req={},rows=[...draft.entries()];let i=0;const step=()=>schedule(()=>{const cursor=i<rows.length?{key:rows[i][0],value:rows[i][1],continue(){i++;step()}}:null;req.result=cursor;req.onsuccess?.({target:req})});step();return req}
   };
   tx.objectStore=()=>store;queueMicrotask(()=>{started=true;check()});return tx;
  }};
  request.onsuccess?.({target:request});
 });
 return request;
}};
const window={};
const localStorage={values:new Map(),getItem(k){return this.values.get(k)||null},setItem(k,v){this.values.set(k,String(v))}};
const confirm=()=>true;
`;

const app=String.raw`
let project=StudioCore.migrate({schemaVersion:1,name:"Stormshard Mod",modId:"stormshard_mod",target:{loader:"fabric",minecraft:"26.2"},items:[
 {uid:"item-1",id:"stormshard_sword",name:"Stormshard Sword",kind:"sword",damage:12,durability:2031,rarity:"Epic",stack:1,cooldown:0.5,pixels:Array(256).fill("#55edff"),recipe:Array(9).fill(""),behavior:null},
 {uid:"item-2",id:"stormshard_gem",name:"Stormshard Gem",kind:"gem",damage:0,durability:1,rarity:"Common",stack:64,cooldown:0,pixels:Array(256).fill("#40dcfb"),recipe:Array(9).fill(""),behavior:null}
]});
let current=project.items[0].uid,studioMode="items",undo=[],redo=[],projectGeneration=0,changedCount=0,renderCount=0,lastToast="",lastLog="",lastFocus="";
const changed=()=>{changedCount++},render=()=>{renderCount++},toast=s=>{lastToast=s},log=s=>{lastLog=s},focusTab=s=>{lastFocus=s};
`;

const exercise=String.raw`
(async()=>{
 const click=async id=>{const el=document.getElementById(id);if(!el)throw Error("MISSING_"+id);await el.click()};
 await click("mmsExtensionsOpen");await click("mmsExtDemo");
 const toggle=document.getElementById("mmsExtEnabled");toggle.checked=true;await toggle.dispatch("change");
 const packages=document.getElementById("mmsExtPackages");
 const findButton=(node,label)=>{if(node.tagName==="BUTTON"&&node.textContent===label)return node;for(const child of node.children){const found=findButton(child,label);if(found)return found}return null};
 const enable=findButton(packages,"启用并审查权限");if(!enable)throw Error("ENABLE_BUTTON_MISSING");
 await enable.click();
 const contributions=document.getElementById("mmsExtContributions"),apply=findButton(contributions,"应用到当前物品");if(!apply)throw Error("APPLY_BUTTON_MISSING");
 await apply.click();
 const validation=StudioCore.validate(project);
 const uninstall=findButton(packages,"卸载");if(!uninstall)throw Error("UNINSTALL_BUTTON_MISSING");
 await uninstall.click();
 const undo=document.getElementById("mmsExtUndo"),undoVisibleAfterUninstall=!!undo&&!undo.hidden;
 if(!undoVisibleAfterUninstall)throw Error("UNDO_BUTTON_NOT_VISIBLE");
 await undo.click();
 const packageRestored=packages.textContent.includes("mms-demo-recipes"),undoHiddenAfterRestore=undo.hidden===true;
 return {packageCount:packages.children.length,contributionCount:contributions.children.length,recipe:project.items[0].recipe,errors:validation.errors,warnings:validation.warnings,projectGeneration,changedCount,renderCount,lastToast,lastLog,lastFocus,dbKeys:[...dbs.values()].flatMap(x=>[...x.keys()]),undoVisibleAfterUninstall,packageRestored,undoHiddenAfterRestore};
})()
`;

test("V25 UI installs a local MMSE package, grants its permission, and applies a recipe through StudioCore",async()=>{
 let serial=0;
 const context=createContext({
  console,TextEncoder,TextDecoder,Uint8Array,DataView,Blob,queueMicrotask,
  crypto:{randomUUID:()=>`test-${++serial}`},
  confirm:()=>true
 });
 const source=[setup,inline[0],inline[1],runtime,app,manager,exercise].join("\n");
 const result=await runInContext(source,context,{timeout:10000});
 assert.equal(result.packageCount,1);
 assert.equal(result.contributionCount,2);
 assert.deepEqual(Array.from(result.recipe),["minecraft:diamond","minecraft:diamond","","minecraft:diamond","minecraft:stick","","","minecraft:stick",""]);
 assert.deepEqual(Array.from(result.errors),[]);
 assert.equal(result.projectGeneration,1);
 assert.equal(result.changedCount,1);
 assert.equal(result.lastToast,"配方模板已应用；记得保存项目");
 assert.equal(result.lastFocus,"recipe");
 assert.equal(result.undoVisibleAfterUninstall,true);
 assert.equal(result.packageRestored,true);
 assert.equal(result.undoHiddenAfterRestore,true);
 assert.ok(result.dbKeys.includes("pkg:mms-demo-recipes"));
});
