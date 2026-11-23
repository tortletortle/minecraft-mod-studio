import assert from "node:assert/strict";
import {createServer} from "node:http";
import {readFile} from "node:fs/promises";
import {resolve} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright";
import {parseManifest} from "./package-manager.mjs";
import {createMmse} from "./archive-writer.mjs";

const repoRoot=resolve(fileURLToPath(new URL("../../",import.meta.url)));
const htmlPath=resolve(repoRoot,"Minecraft_Mod_Studio_V25.html");
const manifest=JSON.stringify({
  id:"mms-v09-race",version:"1.0.0",sdkVersion:"0.1.0",
  permissions:["template.register"],dependencies:{},
  contributes:[{type:"template",id:"base",data:{preset:"multitab"}}]
});
const archive=await createMmse({
  manifest,
  assets:[{path:"assets/probe.ogg",bytes:Uint8Array.from([79,103,103,83,11,22,33,44])}]
},{parseManifest});
const server=createServer(async(req,res)=>{
  try{
    const pathname=new URL(req.url,"http://127.0.0.1").pathname;
    if(pathname==="/favicon.ico"){res.writeHead(204);res.end();return;}
    if(pathname!=="/")throw Error("NOT_FOUND");
    res.writeHead(200,{"content-type":"text/html; charset=utf-8","cache-control":"no-store"});
    res.end(await readFile(htmlPath));
  }catch(error){res.writeHead(404,{"content-type":"text/plain"});res.end(error.message);}
});
await new Promise(resolveListen=>server.listen(0,"127.0.0.1",resolveListen));
const address=server.address();
const browser=await chromium.launch({headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
const context=await browser.newContext();
const pages=[await context.newPage(),await context.newPage()];
const pageErrors=[];
for(const page of pages)page.on("pageerror",error=>pageErrors.push(error.message));
const dbName="mms-v09-multitab-acceptance";
try{
  await Promise.all(pages.map(page=>page.goto(`http://127.0.0.1:${address.port}/`,{waitUntil:"domcontentloaded"})));
  await Promise.all(pages.map(page=>page.waitForFunction(()=>!!window.MMSV25ExtensionRuntime?.PersistentExtensionStore)));
  await Promise.all(pages.map(page=>page.evaluate(name=>{
    const R=window.MMSV25ExtensionRuntime;
    window.__v09Store=new R.PersistentExtensionStore({
      backend:new R.IndexedDbKVBackend(name),
      decodeUtf8:bytes=>new TextDecoder().decode(bytes)
    });
  },dbName)));
  const bytes=Array.from(archive);
  const install=await pages[0].evaluate(async input=>{
    const store=window.__v09Store;
    const plan=await store.prepareInstall([Uint8Array.from(input)]);
    await store.commit(plan.txId,{approved:true});
    const pkg=(await store.listPackages())[0];
    return {id:pkg.id,hash:pkg.assets[0].sha256};
  },bytes);
  assert.equal(install.id,"mms-v09-race");

  const [planA,planB]=await Promise.all(pages.map(page=>page.evaluate(()=>window.__v09Store.prepareUninstall(["mms-v09-race"]))));
  assert.equal(planA.baseRevision,planB.baseRevision,"both tabs should stage against the same catalog revision");

  await pages[0].evaluate(txId=>window.__v09Store.commit(txId,{approved:true}),planA.txId);
  const loser=await pages[1].evaluate(async txId=>{
    try{await window.__v09Store.commit(txId,{approved:true});return null;}
    catch(error){return error.message;}
  },planB.txId);
  assert.equal(loser,"STALE_PLAN","the second tab must not overwrite a newer catalog revision");

  const gc=await pages[0].evaluate(()=>window.__v09Store.collectGarbage());
  assert.deepEqual(gc,{removed:0,retained:1},"rollback-retained assets must survive browser IndexedDB garbage collection");
  const blob=await pages[1].evaluate(async hash=>{
    const value=await window.__v09Store.getBlob(hash);
    return value?Array.from(value):null;
  },install.hash);
  assert.deepEqual(blob,[79,103,103,83,11,22,33,44]);

  await pages[0].evaluate(txId=>window.__v09Store.rollback(txId,{approved:true}),planA.txId);
  const restored=await pages[1].evaluate(async hash=>{
    const packages=await window.__v09Store.listPackages();
    const blob=await window.__v09Store.getBlob(hash);
    return {packages:packages.map(p=>p.id),asset:blob?Array.from(blob):null};
  },install.hash);
  assert.deepEqual(restored,{packages:["mms-v09-race"],asset:[79,103,103,83,11,22,33,44]});
  assert.deepEqual(pageErrors,[],"neither tab should emit uncaught JavaScript errors");
  console.log(JSON.stringify({
    pass:true,browser:"Chromium",tabs:2,
    concurrentPlans:"same base revision",
    winningCommit:planA.txId,
    rejectedCommit:{txId:planB.txId,error:loser},
    garbageCollection:gc,
    rollback:"restored package metadata and original asset bytes",
    pageErrors
  },null,2));
}finally{
  await browser.close();
  await new Promise(resolveClose=>server.close(resolveClose));
}
