// H0 research only. Telemetry tolerances are synthetic assumptions, not measured game bounds.
// Run: node --input-type=module -e "import {runPolicyTests} from './research/horizon/trace_policy.mjs'; console.log(runPolicyTests())"
import { compareTraces } from './trace_compare.mjs';

function parsePolicy(p) {
  if(!p||Object.keys(p).sort().join(",")!=="channels,reorderSameTick,schemaVersion"||p.schemaVersion!==1||typeof p.reorderSameTick!=="boolean"||!Array.isArray(p.channels)||p.channels.length>64) throw Error("invalid policy");
  const channels=new Map();
  for(const c of p.channels){
    if(!c||Object.keys(c).sort().join(",")!=="absoluteTolerance,id"||typeof c.id!=="string"||!/^[a-z][a-z0-9_.-]{0,63}$/.test(c.id)||channels.has(c.id)||typeof c.absoluteTolerance!=="number"||!Number.isFinite(c.absoluteTolerance)||c.absoluteTolerance<0||c.absoluteTolerance>0.001)throw Error("invalid channel policy");
    channels.set(c.id,c.absoluteTolerance);
  }
  return channels;
}

function compareWithPolicy(a,b,policy) {
  const strict=compareTraces(a,b);
  if(strict.status==="INVALID"||strict.status==="NOT_COMPARABLE")return strict;
  let channels;
  try{channels=parsePolicy(policy);}catch(e){return {status:"INVALID_POLICY",scope:"SYNTHETIC",reason:e.message};}
  const sample=e=>e.kind==="telemetry.sample"&&e.payload&&Object.keys(e.payload).sort().join(",")==="channel,value"&&channels.has(e.payload.channel)&&typeof e.payload.value==="number";
  // Only explicitly named synthetic observation channels. Every other event is a barrier.
  // Repeated channels in a run are ambiguous: fail closed rather than pair by value.
  function normalize(trace){
    const events=[],reordered=[];
    for(let i=0;i<trace.events.length;){
      const e=trace.events[i];
      if(!sample(e)){events.push(e);i++;continue;}
      let j=i+1;
      while(j<trace.events.length&&sample(trace.events[j])&&trace.events[j].tick===e.tick)j++;
      const run=trace.events.slice(i,j),ids=run.map(x=>x.payload.channel);
      if(new Set(ids).size!==ids.length)return {ambiguous:true,index:i};
      const sorted=policy.reorderSameTick?run.slice().sort((x,y)=>x.payload.channel<y.payload.channel?-1:x.payload.channel>y.payload.channel?1:0):run;
      if(sorted.some((x,k)=>x!==run[k]))reordered.push({start:i,tick:e.tick,original:ids,normalized:sorted.map(x=>x.payload.channel)});
      events.push(...sorted);i=j;
    }
    return {events,reordered};
  }
  const x=normalize(a),y=normalize(b);
  if(x.ambiguous||y.ambiguous)return {status:"AMBIGUOUS",scope:"SYNTHETIC",reason:"repeated channel in contiguous same-tick run",referenceIndex:x.index??null,candidateIndex:y.index??null};
  const adjustments=[];
  const events=y.events.slice();
  for(let i=0;i<Math.min(x.events.length,events.length);i++){
    const left=x.events[i],right=events[i];
    if(!sample(left)||!sample(right)||left.tick!==right.tick||left.payload.channel!==right.payload.channel)continue;
    const epsilon=channels.get(left.payload.channel),delta=Math.abs(left.payload.value-right.payload.value);
    if(delta>0&&delta<=epsilon){
      adjustments.push({index:i,tick:left.tick,channel:left.payload.channel,reference:left.payload.value,candidate:right.payload.value,delta,absoluteTolerance:epsilon});
      events[i]={...right,payload:{...right.payload,value:left.payload.value}};
    }
  }
  const normalized=compareTraces({...a,events:x.events},{...b,events});
  if(normalized.status!=="MATCH")return {...strict,normalizedDifference:normalized.firstDifference,scope:"SYNTHETIC"};
  if(strict.status==="MATCH")return strict;
  return {status:"MATCH_UNDER_POLICY",scope:"SYNTHETIC",gameVerification:"NOT_RUN",policy,strictStatus:strict.status,adjustments,referenceReorders:x.reordered,candidateReorders:y.reordered};
}

function runPolicyTests(){
  const e=(kind,payload,tick=0)=>({kind,payload,tick});
  const t=(channel,value,tick=0)=>e("telemetry.sample",{channel,value},tick);
  const base={schemaVersion:1,scope:"SYNTHETIC",runtime:"synthetic-java",build:"fixture-1",caseId:"B01",fixtureSHA256:"a".repeat(64),gameVersion:"26.3",seed:17,input:{hand:"main"},initialState:{cooldown:0},complete:true,events:[e("case.begin",{}),t("position.x",0.125),t("position.y",0.25),e("cooldown",{ticks:20}),e("case.end",{success:true},1)]};
  const policy={schemaVersion:1,reorderSameTick:true,channels:[{id:"position.x",absoluteTolerance:0.0001},{id:"position.y",absoluteTolerance:0.0001}]};
  const cases=[
    ["exact",()=>{},"MATCH"],
    ["small float delta",b=>{b.events[1].payload.value+=0.00005;},"MATCH_UNDER_POLICY"],
    ["large float delta",b=>{b.events[1].payload.value+=0.001;},"DIFFERENT"],
    ["same tick independent reorder",b=>{[b.events[1],b.events[2]]=[b.events[2],b.events[1]];},"MATCH_UNDER_POLICY"],
    ["reorder and delta",b=>{b.events[1].payload.value+=0.00005;[b.events[1],b.events[2]]=[b.events[2],b.events[1]];},"MATCH_UNDER_POLICY"],
    ["reorder disabled",(b,p)=>{p.reorderSameTick=false;[b.events[1],b.events[2]]=[b.events[2],b.events[1]];},"DIFFERENT"],
    ["zero tolerance",(b,p)=>{p.channels[0].absoluteTolerance=0;b.events[1].payload.value+=0.00001;},"DIFFERENT"],
    ["cross barrier",b=>{[b.events[2],b.events[3]]=[b.events[3],b.events[2]];},"DIFFERENT"],
    ["cooldown strict",b=>{b.events[3].payload.ticks=21;},"DIFFERENT"],
    ["missing observation",b=>{b.events.splice(1,1);},"DIFFERENT"],
    ["duplicate channel",b=>{b.events.splice(1,0,{...b.events[1]});},"AMBIGUOUS"],
    ["different tick",b=>{b.events[2].tick=1;b.events[3].tick=1;},"DIFFERENT"],
    ["unlisted channel",b=>{b.events[1].payload.channel="foreign";},"DIFFERENT"],
    ["extra semantic field",b=>{b.events[1].payload.entity="other";},"DIFFERENT"],
    ["type change",b=>{b.events[1].payload.value="0.125";},"DIFFERENT"],
    ["mismatched seed",b=>{b.seed=18;},"NOT_COMPARABLE"],
    ["incomplete trace",b=>{b.complete=false;},"INVALID"],
    ["real game scope",b=>{b.scope="GAME";},"INVALID"],
    ["excessive tolerance",(b,p)=>{p.channels[0].absoluteTolerance=1;},"INVALID_POLICY"],
    ["duplicate rule",(b,p)=>{p.channels.push(p.channels[0]);},"INVALID_POLICY"],
    ["negative tolerance",(b,p)=>{p.channels[0].absoluteTolerance=-1;},"INVALID_POLICY"],
    ["unknown policy field",(b,p)=>{p.ignoreAll=true;},"INVALID_POLICY"]
  ];
  const copy=v=>JSON.parse(JSON.stringify(v));
  const results=cases.map(([name,mutate,expected])=>{const b=copy(base),p=copy(policy);mutate(b,p);const before=JSON.stringify([base,b,p]);const r=compareWithPolicy(base,b,p);if(JSON.stringify([base,b,p])!==before)throw Error("input mutated");return {name,expected,actual:r.status,pass:r.status===expected};});
  const b=copy(base);b.events[1].payload.value+=0.00005;[b.events[1],b.events[2]]=[b.events[2],b.events[1]];
  const r=compareWithPolicy(base,b,policy);
  results.push({name:"adjustment and original ordering recorded",pass:r.adjustments?.length===1&&r.candidateReorders?.length===1&&r.strictStatus==="DIFFERENT"&&r.gameVerification==="NOT_RUN"});
  if(results.some(x=>!x.pass))throw Error(JSON.stringify(results));
  return results;
}

export { compareWithPolicy, runPolicyTests };
