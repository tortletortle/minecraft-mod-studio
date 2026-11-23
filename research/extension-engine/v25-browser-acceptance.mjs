import assert from "node:assert/strict";
import {createServer} from "node:http";
import {readFile} from "node:fs/promises";
import {resolve,extname} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright";
import {parseManifest} from "./package-manager.mjs";
import {createMmse} from "./archive-writer.mjs";

const repoRoot=resolve(fileURLToPath(new URL("../../",import.meta.url)));
const manifest=await readFile(new URL("./examples/recipe-pack/manifest.json",import.meta.url),"utf8");
const archive=await createMmse({manifest,assets:[]},{parseManifest});
const server=createServer(async(req,res)=>{
 try{
  const pathname=new URL(req.url,"http://127.0.0.1").pathname;
  if(pathname==="/favicon.ico"){res.writeHead(204);res.end();return;}
  const relative=pathname==="/"?"Minecraft_Mod_Studio_V25.html":decodeURIComponent(pathname.slice(1));
  const path=resolve(repoRoot,relative);
  if(path!==repoRoot&&!path.startsWith(repoRoot+"/"))throw Error("PATH_OUTSIDE_REPOSITORY");
  const bytes=await readFile(path);
  const type=extname(path)===".html"?"text/html; charset=utf-8":extname(path)===".js"?"text/javascript; charset=utf-8":"application/octet-stream";
  res.writeHead(200,{"content-type":type,"cache-control":"no-store"});res.end(bytes);
 }catch(error){res.writeHead(404,{"content-type":"text/plain"});res.end(error.message);}
});
await new Promise(resolveListen=>server.listen(0,"127.0.0.1",resolveListen));
const address=server.address();
const browser=await chromium.launch({headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
const context=await browser.newContext();
const page=await context.newPage();
const pageErrors=[];
page.on("pageerror",error=>pageErrors.push(error.message));
page.on("dialog",dialog=>dialog.accept());
try{
 await page.goto(`http://127.0.0.1:${address.port}/`,{waitUntil:"networkidle"});
 await page.locator("#mmsExtensionsOpen").waitFor();
 await page.locator("#mmsExtensionsOpen").click();
 await page.locator("#mmsExtensionManager[open]").waitFor();
 await page.locator("#mmsExtImport").click();
 await page.locator("#mmsExtFile").setInputFiles({name:"mms-demo-recipes.mmse",mimeType:"application/zip",buffer:Buffer.from(archive)});
 await page.waitForFunction(()=>document.querySelector("#mmsExtPackages")?.textContent.includes("mms-demo-recipes"));
 await page.locator("#mmsExtEnabled").check();
 await page.locator("#mmsExtPackages button").filter({hasText:"启用并审查权限"}).click();
 await page.waitForFunction(()=>document.querySelector("#mmsExtContributions")?.textContent.includes("钻石剑配方"));
 await page.locator("#mmsExtContributions button").filter({hasText:"应用到当前物品"}).first().click();
 await page.waitForFunction(()=>document.querySelector("#mmsExtStatus")?.textContent.includes("项目尚未保存"));
 await page.locator("#mmsExtDone").click();
 const expected=["minecraft:diamond","minecraft:diamond","","minecraft:diamond","minecraft:stick","","","minecraft:stick",""];
 const beforeSave=await page.evaluate(()=>{
  const selected=project.items.find(x=>x.uid===current);
  return {id:selected.id,recipe:selected.recipe,errors:StudioCore.validate(project).errors};
 });
 assert.deepEqual(beforeSave.recipe,expected,"V25 selected item should receive the demo recipe");
 assert.deepEqual(beforeSave.errors,[],"StudioCore should accept the applied recipe");
 await page.locator("#save").click();
 await page.waitForFunction(()=>document.querySelector("#saveStatus")?.textContent.includes("Saved locally"));
 await page.reload({waitUntil:"networkidle"});
 const afterReload=await page.evaluate(()=>{
  const selected=project.items.find(x=>x.uid===current);
  return {id:selected.id,recipe:selected.recipe,errors:StudioCore.validate(project).errors};
 });
 assert.deepEqual(afterReload.recipe,expected,"recipe should survive the real V25 local save/reload cycle");
 assert.deepEqual(afterReload.errors,[],"reloaded project should remain valid");
 await page.locator("#mmsExtensionsOpen").click();
 await page.locator("#mmsExtPackages").getByText("mms-demo-recipes").waitFor();
 const persistedCatalog=await page.locator("#mmsExtPackages").innerText();
 assert.match(persistedCatalog,/已启用/,"IndexedDB package activation should survive reload");
 await page.locator("#mmsExtPackages button").filter({hasText:"卸载"}).click();
 await page.waitForFunction(()=>document.querySelector("#mmsExtPackages")?.textContent.includes("尚未安装扩展"));
 await page.locator("#mmsExtUndo").waitFor({state:"visible"});
 await page.locator("#mmsExtUndo").click();
 await page.waitForFunction(()=>document.querySelector("#mmsExtPackages")?.textContent.includes("mms-demo-recipes"));
 const afterUndo=await page.locator("#mmsExtPackages").innerText();
 assert.match(afterUndo,/已启用/,"undo should restore the previous package activation state");
 await page.locator("#mmsExtUndo").waitFor({state:"hidden"});
 await page.locator("#mmsExtPackages button").filter({hasText:"卸载"}).click();
 await page.waitForFunction(()=>document.querySelector("#mmsExtPackages")?.textContent.includes("尚未安装扩展"));
 assert.deepEqual(pageErrors,[],"browser page should not emit uncaught JavaScript errors");
 console.log(JSON.stringify({pass:true,browser:"Chromium",beforeSave,afterReload,catalogPersisted:true,uninstall:"passed",undo:"passed",afterUndo,pageErrors},null,2));
}finally{
 await browser.close();
 await new Promise(resolveClose=>server.close(resolveClose));
}
