import test from "node:test";
import assert from "node:assert/strict";
import {parseManifest} from "./package-manager.mjs";
import {createMmse} from "./archive-writer.mjs";
import {MemoryKVBackend,PersistentExtensionStore} from "./persistent-store.mjs";

const manifest=(id,version="1.0.0")=>JSON.stringify({
  id,version,sdkVersion:"0.1.0",
  permissions:["template.register"],
  dependencies:{},
  contributes:[{type:"template",id:"starter",data:{preset:"starter"}}]
});
const archive=(id,version,assetByte)=>createMmse({
  manifest:manifest(id,version),
  assets:[{path:"assets/payload.bin",bytes:Uint8Array.from([assetByte,2,3,4])}]
},{parseManifest,decodeUtf8:bytes=>new TextDecoder().decode(bytes)});
const makeStore=(backend,now)=>{let serial=0;return new PersistentExtensionStore({
  backend,decodeUtf8:bytes=>new TextDecoder().decode(bytes),
  idFactory:()=>`tx-v09-${++serial}`,now
});};

test("uninstall rollback retains asset blobs through garbage collection",async()=>{
  const backend=new MemoryKVBackend(),store=makeStore(backend,()=>1_700_000_000_000);
  const install=await store.prepareInstall([await archive("undo-package","1.0.0",11)]);
  await store.commit(install.txId,{approved:true});
  const original=(await store.listPackages())[0],hash=original.assets[0].sha256;
  const uninstall=await store.prepareUninstall([original.id]);
  await store.commit(uninstall.txId,{approved:true});
  assert.deepEqual(await store.listPackages(),[]);
  const gc=await store.collectGarbage();
  assert.deepEqual(gc,{removed:0,retained:1});
  assert.deepEqual(await store.getBlob(hash),Uint8Array.from([11,2,3,4]));
  await store.rollback(uninstall.txId,{approved:true});
  assert.equal((await store.listPackages())[0].id,original.id);
  assert.deepEqual(await store.getBlob(hash),Uint8Array.from([11,2,3,4]));
});

test("upgrade rollback preserves the previous version assets",async()=>{
  const backend=new MemoryKVBackend(),store=makeStore(backend,()=>1_700_000_000_000);
  const first=await store.prepareInstall([await archive("upgrade-package","1.0.0",21)]);
  await store.commit(first.txId,{approved:true});
  const original=(await store.listPackages())[0],oldHash=original.assets[0].sha256;
  const upgrade=await store.prepareInstall([await archive("upgrade-package","1.1.0",22)],{upgrade:true});
  await store.commit(upgrade.txId,{approved:true});
  const newHash=(await store.listPackages())[0].assets[0].sha256;
  assert.notEqual(oldHash,newHash);
  await store.collectGarbage();
  assert.deepEqual(await store.getBlob(oldHash),Uint8Array.from([21,2,3,4]));
  await store.rollback(upgrade.txId,{approved:true});
  assert.equal((await store.listPackages())[0].version,"1.0.0");
  assert.deepEqual(await store.getBlob(oldHash),Uint8Array.from([21,2,3,4]));
  await store.collectGarbage();
  assert.equal(await store.getBlob(newHash),null);
});

test("expired rollback is rejected and its orphaned blobs can be collected",async()=>{
  const backend=new MemoryKVBackend();let now=1_700_000_000_000;
  const store=makeStore(backend,()=>now);
  const install=await store.prepareInstall([await archive("expired-package","1.0.0",31)]);
  await store.commit(install.txId,{approved:true});
  const hash=(await store.listPackages())[0].assets[0].sha256;
  const uninstall=await store.prepareUninstall(["expired-package"]);
  await store.commit(uninstall.txId,{approved:true});
  now+=24*60*60*1000+1;
  const gc=await store.collectGarbage();
  assert.deepEqual(gc,{removed:1,retained:0});
  assert.equal(await store.getBlob(hash),null);
  await assert.rejects(()=>store.rollback(uninstall.txId,{approved:true}),{message:"ROLLBACK_EXPIRED"});
  assert.deepEqual(await store.listPackages(),[]);
});

test("concurrent stale plans cannot both commit",async()=>{
  const store=makeStore(new MemoryKVBackend(),()=>1_700_000_000_000);
  const install=await store.prepareInstall([await archive("race-package","1.0.0",41)]);
  await store.commit(install.txId,{approved:true});
  const [first,second]=await Promise.all([
    store.prepareUninstall(["race-package"]),
    store.prepareUninstall(["race-package"])
  ]);
  await store.commit(first.txId,{approved:true});
  await assert.rejects(()=>store.commit(second.txId,{approved:true}),{message:"STALE_PLAN"});
  assert.deepEqual(await store.listPackages(),[]);
});
