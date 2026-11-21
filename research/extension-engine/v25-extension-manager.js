/* V25 in-editor extension manager. Local, data-only packages; no package code execution. */
(()=>{
"use strict";
const R=window.MMSV25ExtensionRuntime;
const byId=id=>document.getElementById(id);
const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const button=(text,fn,cls="")=>{const b=make("button",cls,text);b.type="button";b.addEventListener("click",fn);return b;};
const style=make("style");
style.textContent=`
.mms-ext-dialog{width:min(1050px,96vw);height:min(780px,92vh);max-width:none;max-height:none;margin:auto;padding:0;background:#171a21;color:#eee9df;border:1px solid #796a50;border-radius:10px;box-shadow:0 22px 80px #000b;overflow:hidden}
.mms-ext-dialog::backdrop{background:#05060bd9}.mms-ext-dialog[open]{display:flex;flex-direction:column}
.mms-ext-dialog button,.mms-ext-dialog input{font:inherit;color:inherit;background:#292d37;border:1px solid #596273;border-radius:5px;padding:7px 10px;min-width:0;max-width:100%}
.mms-ext-dialog button{cursor:pointer}.mms-ext-dialog button:hover{border-color:#e2b76b;color:#ffe2a5}.mms-ext-dialog button:disabled{opacity:.42;cursor:not-allowed}
.mms-ext-head{display:flex;gap:12px;align-items:center;padding:14px 18px;background:linear-gradient(100deg,#3c3028,#252b37);border-bottom:1px solid #66563e}
.mms-ext-head>div:first-child{flex:1}.mms-ext-head h2{margin:0;color:#f6dca9;font-size:19px}.mms-ext-head small{color:#b7b8c0}
.mms-ext-toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;padding:11px 14px;background:#20242d;border-bottom:1px solid #414855}
.mms-ext-toggle{display:flex;align-items:center;gap:7px;margin-right:auto}.mms-ext-toggle input{accent-color:#78c98d}
.mms-ext-status{padding:8px 14px;color:#b7c6d4;background:#1b2028;font-size:12px;border-bottom:1px solid #343b47}
.mms-ext-body{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:0;flex:1;min-height:0}
.mms-ext-column{padding:13px;overflow:auto;min-width:0}.mms-ext-column+ .mms-ext-column{border-left:1px solid #3b424e}
.mms-ext-column h3{margin:0 0 10px;color:#e6c88d;font-size:14px}
.mms-ext-card{padding:11px;margin:0 0 9px;border:1px solid #444d5a;border-radius:7px;background:#202630;min-width:0}
.mms-ext-card-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.mms-ext-card-head strong{overflow-wrap:anywhere}.mms-ext-pill{font-size:10px;padding:3px 6px;border:1px solid #596576;border-radius:999px;color:#b9d9e9}
.mms-ext-card p{margin:7px 0;color:#b8c0cb;font-size:12px;overflow-wrap:anywhere}.mms-ext-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.mms-ext-actions button{font-size:12px}.mms-ext-empty{padding:18px 10px;text-align:center;color:#9ea6b2;border:1px dashed #4c5564;border-radius:7px;font-size:12px}
.mms-ext-warning{padding:10px 14px;background:#30271e;color:#e8c99b;border-top:1px solid #5b4a34;font-size:11px;line-height:1.55}
.mms-ext-footer{display:flex;gap:8px;align-items:center;justify-content:space-between;padding:10px 14px;background:#1d222b;border-top:1px solid #414855}
.mms-ext-footer small{color:#9ca6b3}
@media(max-width:700px){.mms-ext-dialog{width:100vw;height:96vh}.mms-ext-body{grid-template-columns:1fr;overflow:auto}.mms-ext-column{overflow:visible}.mms-ext-column+.mms-ext-column{border-left:0;border-top:1px solid #3b424e}.mms-ext-head{flex-wrap:wrap}.mms-ext-toggle{margin-right:0}}
`;
document.head.append(style);
const open=make("button","metal","🧩 扩展");
open.id="mmsExtensionsOpen";open.type="button";open.title="Data-only extension manager";
const topActions=document.querySelector(".top-actions"),resourceButton=byId("openResources");
if(resourceButton)resourceButton.after(open);else if(topActions)topActions.append(open);
const dialog=make("dialog","mms-ext-dialog");
dialog.id="mmsExtensionManager";
dialog.setAttribute("aria-label","Minecraft Mod Studio extension manager");
dialog.innerHTML=`
<header class="mms-ext-head"><div><h2>🧩 扩展管理器 / EXTENSION MANAGER</h2><small>V25 · declarative data packages · local catalog</small></div><button id="mmsExtClose" type="button">关闭</button></header>
<div class="mms-ext-toolbar">
 <label class="mms-ext-toggle"><input id="mmsExtEnabled" type="checkbox"> 启用扩展功能</label>
 <button id="mmsExtImport" type="button">导入 .mmse</button>
 <button id="mmsExtDemo" type="button">安装演示扩展</button>
 <button id="mmsExtRefresh" type="button">刷新</button>
 <button id="mmsExtRecover" type="button">恢复未完成事务</button>
 <input id="mmsExtFile" type="file" accept=".mmse,.zip,application/zip" hidden>
</div>
<div class="mms-ext-status" id="mmsExtStatus" role="status">正在初始化扩展管理器…</div>
<div class="mms-ext-body">
 <section class="mms-ext-column"><h3>已安装扩展 / INSTALLED PACKAGES</h3><div id="mmsExtPackages"></div></section>
 <section class="mms-ext-column"><h3>已启用配方模板 / ACTIVE RECIPE TEMPLATES</h3><div id="mmsExtContributions"></div></section>
</div>
<div class="mms-ext-warning">安全边界：只接受 .mmse 数据包，不执行包内 JavaScript。当前版本仅将 recipe 类型贡献接入 V25；其他类型保持惰性数据。导入包默认未签名，只建议导入可信来源。远程市场安装尚未开放。</div>
<footer class="mms-ext-footer"><small id="mmsExtFooter">扩展目录使用独立 IndexedDB，不修改项目保存数据库。</small><button id="mmsExtDone" type="button">完成</button></footer>`;
document.body.append(dialog);
const ui={
 status:byId("mmsExtStatus"),packages:byId("mmsExtPackages"),contributions:byId("mmsExtContributions"),
 enabled:byId("mmsExtEnabled"),file:byId("mmsExtFile"),footer:byId("mmsExtFooter")
};
let store=null,backend=null,bridge=null,featureEnabled=false,catalog=[],busy=false,preferencePersistent=true;
const FEATURE_KEY="mms.v25.extensions.enabled";
const status=(message,kind="")=>{ui.status.textContent=message;ui.status.dataset.kind=kind;};
const explain=error=>{const detail=Array.isArray(error?.details)?": "+error.details.join("; "):error?.details?": "+String(error.details):"";return String(error?.message||error)+detail;};
const setBusy=value=>{busy=value;for(const id of ["mmsExtImport","mmsExtDemo","mmsExtRefresh","mmsExtRecover"])byId(id).disabled=value;};
const readFeatureFlag=()=>{try{return localStorage.getItem(FEATURE_KEY)==="1";}catch{return false;}};
const writeFeatureFlag=value=>{featureEnabled=value;preferencePersistent=true;try{localStorage.setItem(FEATURE_KEY,value?"1":"0");}catch{preferencePersistent=false;}ui.enabled.checked=featureEnabled;};
const ensureBridge=()=>{
 if(bridge)return bridge;
 bridge=R.createV25HostBridge({
  core:{migrate:p=>StudioCore.migrate(p),encode:p=>StudioCore.encode(p),validate:p=>StudioCore.validate(p)},
  getProject:()=>project,
  replaceProject:next=>{
   const selected=current,mode=studioMode;
   project=StudioCore.migrate(next);projectGeneration++;
   current=project.items.some(x=>x.uid===selected)?selected:project.items[0]?.uid;
   studioMode=mode;undo=[];redo=[];changed();render();
  },
  onProjectChanged:()=>{},
  isEnabled:()=>featureEnabled
 });
 return bridge;
};
const ensureStore=async()=>{
 if(store)return store;
 if(!R||typeof R.IndexedDbKVBackend!=="function")throw Error("EXTENSION_RUNTIME_UNAVAILABLE");
 backend=new R.IndexedDbKVBackend("minecraft-mod-studio-extension-store-v1");
 store=new R.PersistentExtensionStore({backend,requireSignatures:false});
 return store;
};
const card=(title,sub)=>{const n=make("article","mms-ext-card");const head=make("div","mms-ext-card-head");head.append(make("strong","",title));if(sub)head.append(make("span","mms-ext-pill",sub));n.append(head);return n;};
const empty=(text)=>ui.packages.append(make("div","mms-ext-empty",text));
const renderPackages=()=>{
 ui.packages.replaceChildren();
 if(!catalog.length){empty("尚未安装扩展。可以导入 .mmse，或安装演示扩展。");return;}
 for(const pkg of catalog){
  let manifest;try{manifest=R.parseManifest(pkg.manifestRaw);}catch(error){const bad=card(pkg.id,"元数据异常");bad.append(make("p","",explain(error)));ui.packages.append(bad);continue;}
  const item=card(pkg.id,pkg.active?"已启用":"已安装 · 未启用");
  const trust=pkg.publisher?"已验证签名 · "+pkg.publisher.keyId.slice(0,12):"本地导入 · 未签名";
  item.append(make("p","",`版本 ${pkg.version} · ${trust}`));
  item.append(make("p","",`权限：${pkg.permissions.length?pkg.permissions.join("、"):"无"}`));
  item.append(make("p","",`依赖：${Object.keys(pkg.dependencies||{}).length?Object.entries(pkg.dependencies).map(([k,v])=>k+"@"+v).join("、"):"无"}`));
  item.append(make("p","",`贡献：${manifest.contributes.map(c=>c.type+":"+c.id).join("、")}`));
  const actions=make("div","mms-ext-actions");
  if(pkg.active){
   actions.append(button("禁用",()=>runAction(async()=>{await store.disable(pkg.id);await refresh();status("已禁用 "+pkg.id,"ok");}),""));
  }else{
   const enable=button("启用并审查权限",()=>runAction(()=>enablePackage(pkg.id)),"");
   enable.disabled=!featureEnabled;enable.title=featureEnabled?"":"先启用上方扩展功能开关";
   actions.append(enable);
  }
  const remove=button("卸载",()=>runAction(()=>uninstallPackage(pkg.id)),"");actions.append(remove);
  item.append(actions);ui.packages.append(item);
 }
};
const renderContributions=()=>{
 ui.contributions.replaceChildren();
 let rows;try{rows=R.collectRecipeContributions(catalog);}catch(error){ui.contributions.append(make("div","mms-ext-empty",explain(error)));return;}
 if(!rows.length){ui.contributions.append(make("div","mms-ext-empty","启用包含 recipe 贡献的扩展后，配方模板会显示在这里。"));return;}
 for(const row of rows){
  if(row.error){const bad=card(row.contributionId,"数据无效");bad.append(make("p","",row.packageId+" · "+row.error));ui.contributions.append(bad);continue;}
  const item=card(row.data.name,row.packageId+"@"+row.packageVersion);
  if(row.data.description)item.append(make("p","",row.data.description));
  item.append(make("p","",row.data.ingredients.map((v,i)=>v||"—").join(" · ")));
  const apply=button("应用到当前物品",()=>runAction(()=>applyRecipe(row)),"");
  apply.disabled=!featureEnabled||!catalog.find(p=>p.id===row.packageId)?.active;
  const actions=make("div","mms-ext-actions");actions.append(apply);item.append(actions);
  ui.contributions.append(item);
 }
};
const renderAll=()=>{
 ui.enabled.checked=featureEnabled;
 renderPackages();renderContributions();
 const active=catalog.filter(p=>p.active).length;
 status(`扩展功能：${featureEnabled?"已启用":"已关闭"} · 已安装 ${catalog.length} · 已激活 ${active}${preferencePersistent?"":" · 本次会话临时设置"}`);
 ui.footer.textContent="独立 IndexedDB：minecraft-mod-studio-extension-store-v1 · 项目保存仍由 StudioCore 管理";
};
const refresh=async()=>{
 await ensureStore();catalog=await store.listPackages();renderAll();
};
const runAction=async work=>{
 if(busy)return;setBusy(true);
 try{await work();}
 catch(error){status("操作失败："+explain(error),"error");if(typeof log==="function")log("Extension manager: "+explain(error),"error");}
 finally{setBusy(false);}
};
const enablePackage=async id=>{
 if(!featureEnabled)throw Error("EXTENSION_FEATURE_DISABLED");
 const map=new Map(catalog.map(p=>[p.id,p])),grants={},visited=new Set(),order=[];
 const visit=key=>{
  if(visited.has(key))return;const pkg=map.get(key);if(!pkg)throw Error("DEPENDENCY_NOT_INSTALLED: "+key);
  visited.add(key);const manifest=R.parseManifest(pkg.manifestRaw);
  for(const dep of Object.keys(manifest.dependencies).sort())visit(dep);
  grants[key]=[...manifest.permissions];order.push({id:key,permissions:[...manifest.permissions],active:pkg.active});
 };
 visit(id);
 const review=order.filter(x=>!x.active).map(x=>x.id+"： "+(x.permissions.join(", ")||"无权限")).join("\n");
 if(!confirm("即将启用以下数据扩展：\n"+review+"\n\n授权仅允许注册声明式贡献，不会执行扩展包代码。是否继续？"))return;
 const result=await store.enableClosure(id,grants);await refresh();status("已启用："+result.enabled.join(" → "),"ok");
};
const uninstallPackage=async id=>{
 const pkg=catalog.find(p=>p.id===id);if(!pkg)throw Error("PACKAGE_NOT_FOUND");
 if(!confirm(`卸载 ${id}@${pkg.version}？其注册的扩展贡献将不再可用；已应用到项目的数据不会自动删除。`))return;
 const plan=await store.prepareUninstall([id]);await store.commit(plan.txId,{approved:true});await refresh();status("已卸载 "+id,"ok");
};
const inspectArchive=async bytes=>{
 if(!(bytes instanceof Uint8Array)||bytes.length<22||bytes.length>8*1024*1024)throw Error("ARCHIVE_SIZE_LIMIT");
 const parsed=await R.readMmse(bytes,{parseManifest:R.parseManifest});
 for(const c of parsed.manifest.contributes)if(c.type==="recipe")R.validateRecipeContribution(c.data);
 return parsed;
};
const installArchive=async(bytes,label="本地文件")=>{
 await ensureStore();
 const parsed=await inspectArchive(bytes),m=parsed.manifest;
 const details=[
  "来源："+label,
  "包："+m.id+"@"+m.version,
  "权限："+(m.permissions.join(", ")||"无"),
  "依赖："+(Object.keys(m.dependencies).join(", ")||"无"),
  "贡献："+m.contributes.map(c=>c.type+":"+c.id).join(", "),
  "资产文件："+parsed.summary.assetCount,
  "",
  "此包将作为本地未签名扩展导入，不会执行包内代码。"
 ].join("\n");
 if(!confirm(details+"\n\n确认安装？"))return;
 const prepared=await store.prepareInstall([bytes]);
 await store.commit(prepared.txId,{approved:true});
 await refresh();status("安装成功："+m.id+"@"+m.version+"（尚未启用）","ok");
};
const installDemo=async()=>{
 const manifest={id:"mms-demo-recipes",version:"1.0.0",sdkVersion:"0.1.0",permissions:["recipe.register"],dependencies:{},contributes:[
  {type:"recipe",id:"diamond-sword",data:{name:"钻石剑配方",description:"演示：将声明式配方模板应用到当前选中物品。",ingredients:["minecraft:diamond","minecraft:diamond","","minecraft:diamond","minecraft:stick","","","minecraft:stick",""]}},
  {type:"recipe",id:"golden-apple",data:{name:"金苹果配方",description:"第二个配方模板，用于验证同一扩展可注册多个贡献。",ingredients:["minecraft:gold_ingot","minecraft:gold_ingot","minecraft:gold_ingot","minecraft:gold_ingot","minecraft:apple","minecraft:gold_ingot","minecraft:gold_ingot","minecraft:gold_ingot","minecraft:gold_ingot"]}}
 ]};
 const archive=await R.createMmse({manifest:JSON.stringify(manifest),assets:[]},{parseManifest:R.parseManifest});
 await installArchive(archive,"内置演示生成器");
};
const applyRecipe=async row=>{
 if(!featureEnabled)throw Error("EXTENSION_FEATURE_DISABLED");
 const target=project.items.find(x=>x.uid===current);if(!target)throw Error("TARGET_ITEM_NOT_FOUND");
 const plan=R.stageRecipeMutation(ensureBridge(),{itemUid:target.uid,packageId:row.packageId,contributionId:row.contributionId,data:row.data});
 const warning=plan.warnings.length?"\n校验警告："+plan.warnings.join("；"):"";
 if(!confirm(`将“${row.data.name}”应用到当前物品“${target.name}”的 3×3 配方槽。\n这会修改当前项目草稿，不会自动保存。${warning}\n\n确认应用？`))return;
 const result=ensureBridge().commit(plan.token,{approved:true});
 if(typeof log==="function")log(`Recipe extension ${row.packageId}:${row.contributionId} applied to ${target.id}; project remains unsaved.`,"ok");
 if(typeof toast==="function")toast("配方模板已应用；记得保存项目");
 if(typeof focusTab==="function")focusTab("recipe");
 status("已应用 "+row.data.name+" · 项目尚未保存","ok");
 return result;
};
open.addEventListener("click",async()=>{
 if(!dialog.open)dialog.showModal();
 await runAction(refresh);
});
byId("mmsExtClose").onclick=()=>dialog.close();
byId("mmsExtDone").onclick=()=>dialog.close();
byId("mmsExtImport").onclick=()=>byId("mmsExtFile").click();
byId("mmsExtFile").addEventListener("change",async()=>{
 const file=ui.file.files?.[0];ui.file.value="";if(!file)return;
 await runAction(async()=>{if(file.size>8*1024*1024)throw Error("ARCHIVE_SIZE_LIMIT");await installArchive(new Uint8Array(await file.arrayBuffer()),file.name);});
});
byId("mmsExtDemo").onclick=()=>runAction(installDemo);
byId("mmsExtRefresh").onclick=()=>runAction(refresh);
byId("mmsExtRecover").onclick=()=>runAction(async()=>{
 if(!confirm("恢复会将目录中所有尚未提交的安装事务标记为中止。请先关闭其他标签页中的扩展安装操作。继续？"))return;
 const result=await (await ensureStore()).recover();await refresh();status("恢复完成：中止 "+result.aborted+" 个未完成事务","ok");
});
ui.enabled.addEventListener("change",()=>{
 writeFeatureFlag(ui.enabled.checked);
 renderAll();
 status(`扩展功能已${featureEnabled?"启用":"关闭"}。${preferencePersistent?"":"当前浏览器不允许持久化此开关，仅本次会话有效。"}`);
});
dialog.addEventListener("cancel",e=>{if(busy)e.preventDefault();});
featureEnabled=readFeatureFlag();ui.enabled.checked=featureEnabled;
if(!R){
 open.disabled=true;status("扩展运行时未加载。请保留 research/extension-engine 目录并从仓库根目录打开 V25 文件。","error");
}else{
 try{ensureBridge();}catch(error){status("Host Bridge 初始化失败："+explain(error),"error");open.disabled=true;}
}
})();
