// H0: synthetic end-to-end experiment pipeline. No SDK or real game integration.
import { createHash } from 'node:crypto';
import { compareTraces } from './trace_compare.mjs';
import { compareWithPolicy } from './trace_policy.mjs';
import { aggregateMatrix } from './experiment_matrix.mjs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync, statSync } from 'node:fs';
import assert from 'node:assert/strict';

function canonical(v, depth=0){
  if(depth>32)throw Error('JSON depth');
  if(v===null||typeof v==='string'||typeof v==='boolean')return JSON.stringify(v);
  if(typeof v==='number'&&Number.isFinite(v)&&(!Number.isInteger(v)||Number.isSafeInteger(v)))return JSON.stringify(v);
  if(Array.isArray(v)){
    if(Object.keys(v).length!==v.length)throw Error('non-JSON array');
    return '['+v.map(x=>canonical(x,depth+1)).join(',')+']';
  }
  if(v&&typeof v==='object'&&(Object.getPrototypeOf(v)===Object.prototype||Object.getPrototypeOf(v)===null))return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k],depth+1)).join(',')+'}';
  throw Error('non-JSON value');
}
export const digest=v=>createHash('sha256').update(canonical(v),'utf8').digest('hex');
export const conditionDigest=t=>digest({seed:t.seed,input:t.input,initialState:t.initialState});

export function runPipeline(plan,policy,pairs,expectedPlanSHA256){
  const scope='SYNTHETIC',gameVerification='NOT_RUN';
  const invalid=reason=>({status:'INVALID_PIPELINE',scope,reason,gameVerification,cause:'UNDETERMINED'});
  try{
    const planSHA256=digest(plan);
    if(expectedPlanSHA256!==planSHA256)return invalid('plan fingerprint mismatch');
    const empty=aggregateMatrix(plan,[]);
    if(empty.status!=='ANALYZED')return invalid(empty.reason);
    const ctx=plan.context;
    if(digest(policy)!==ctx.policySHA256)return invalid('policy fingerprint mismatch');
    if(!Array.isArray(pairs)||pairs.length>empty.planned)return invalid('invalid pair count');
    const probe={schemaVersion:1,scope,runtime:'synthetic-probe',build:'probe',caseId:ctx.caseId,fixtureSHA256:ctx.fixtureSHA256,gameVersion:ctx.gameVersion,seed:0,input:{},initialState:{},complete:true,events:[{tick:0,kind:'case.begin',payload:{}},{tick:0,kind:'case.end',payload:{}}]};
    if(policy!==null&&compareWithPolicy(probe,probe,policy).status!=='MATCH')return invalid('invalid comparison policy');
    const seeds=new Map(plan.seeds.map(s=>[s.seed,s.conditionSHA256])),seen=new Set(),rows=[],details=[];
    for(const pair of pairs){
      if(!pair||Object.keys(pair).sort().join(',')!=='candidate,reference,repeat,seed')return invalid('invalid pair fields');
      const {seed,repeat,reference,candidate}=pair,key=seed+':'+repeat;
      if(!seeds.has(seed)||!Number.isInteger(repeat)||repeat<1||repeat>plan.repeats||seen.has(key))return invalid('unplanned or duplicate pair: '+key);
      seen.add(key);
      const conditionSHA256=seeds.get(seed);
      const strict=compareTraces(reference,candidate);
      let result=strict;
      let referenceTraceSHA256=null,candidateTraceSHA256=null;
      try{referenceTraceSHA256=digest(reference);candidateTraceSHA256=digest(candidate);}catch{result={status:'INVALID',reason:'non-JSON trace'};}
      if(result.status!=='INVALID'){
        for(const [side,t,build] of [['reference',reference,ctx.referenceBuild],['candidate',candidate,ctx.candidateBuild]]){
          if(t.caseId!==ctx.caseId||t.seed!==seed||t.gameVersion!==ctx.gameVersion||t.fixtureSHA256!==ctx.fixtureSHA256||t.build!==build||conditionDigest(t)!==conditionSHA256){result={status:'NOT_COMPARABLE',reason:'planned identity or condition mismatch',side};break;}
        }
        if(result.status!=='NOT_COMPARABLE'&&policy!==null)result=compareWithPolicy(reference,candidate,policy);
      }
      const row={scope,context:ctx,seed,repeat,conditionSHA256,status:result.status};
      if(['MATCH','MATCH_UNDER_POLICY','DIFFERENT'].includes(row.status))row.referenceObservationSHA256=digest(reference.events);
      rows.push(row);
      details.push({seed,repeat,referenceTraceSHA256,candidateTraceSHA256,strict,result});
    }
    details.sort((a,b)=>a.seed<b.seed?-1:a.seed>b.seed?1:a.repeat-b.repeat);
    const summary=aggregateMatrix(plan,rows);
    if(summary.status!=='ANALYZED')return invalid(summary.reason);
    return {status:'REPORT',scope,planSHA256,policySHA256:ctx.policySHA256,summary,details,cause:'UNDETERMINED',gameVerification};
  }catch(e){return invalid(e.message);}
}

export function runPipelineTests(){
  const copy=v=>JSON.parse(JSON.stringify(v));
  const policy={schemaVersion:1,reorderSameTick:true,channels:[{id:'position.x',absoluteTolerance:0.0001}]};
  const context={caseId:'B01',fixtureSHA256:'a'.repeat(64),gameVersion:'26.3',referenceBuild:'synthetic-java',candidateBuild:'synthetic-rust',policySHA256:digest(policy)};
  const trace=(seed,build)=>({schemaVersion:1,scope:'SYNTHETIC',runtime:build,build,caseId:context.caseId,fixtureSHA256:context.fixtureSHA256,gameVersion:context.gameVersion,seed,input:{hand:'main'},initialState:{cooldown:0},complete:true,events:[{tick:0,kind:'case.begin',payload:{}},{tick:0,kind:'telemetry.sample',payload:{channel:'position.x',value:0.125}},{tick:0,kind:'cooldown',payload:{ticks:20}},{tick:1,kind:'case.end',payload:{}}]});
  const plan={schemaVersion:1,scope:'SYNTHETIC',context,repeats:3,seeds:[17,31,59].map(seed=>({seed,conditionSHA256:conditionDigest(trace(seed,context.referenceBuild))}))};
  const pairs=plan.seeds.flatMap(({seed})=>[1,2,3].map(repeat=>({seed,repeat,reference:trace(seed,context.referenceBuild),candidate:trace(seed,context.candidateBuild)})));
  const cases=[
    ['exact',()=>{},'NO_DIFFERENCE_OBSERVED'],
    ['tolerated',p=>p[0].candidate.events[1].payload.value+=0.00005,'NO_DIFFERENCE_OBSERVED'],
    ['one difference',p=>p[0].candidate.events[2].payload.ticks++,'MIXED_WITHIN_SEED'],
    ['seed associated',p=>p.slice(0,3).forEach(x=>x.candidate.events[2].payload.ticks++),'SEED_ASSOCIATED_PATTERN'],
    ['all differ',p=>p.forEach(x=>x.candidate.events[2].payload.ticks++),'REPEATED_ACROSS_TESTED_SEEDS'],
    ['unstable baseline',p=>p[0].reference.events[2].payload.ticks++,'REFERENCE_VARIATION'],
    ['missing',p=>p.pop(),'INCOMPLETE'],
    ['both conditions changed',p=>{p[0].reference.input.hand='off';p[0].candidate.input.hand='off';},'INCOMPLETE'],
    ['both versions changed',p=>{p[0].reference.gameVersion='26.2';p[0].candidate.gameVersion='26.2';},'INCOMPLETE'],
    ['wrong candidate build',p=>p[0].candidate.build='other','INCOMPLETE'],
    ['invalid trace',p=>p[0].candidate.complete=false,'INCOMPLETE'],
    ['duplicate pair',p=>p[1]=p[0],'INVALID_PIPELINE'],
    ['unplanned seed',p=>p[0].seed=123,'INVALID_PIPELINE'],
    ['forged outcome',p=>p[0].status='MATCH','INVALID_PIPELINE'],
    ['real game scope rejected',p=>p[0].candidate.scope='GAME','INCOMPLETE'],
    ['changed policy',(p,q)=>q.channels[0].absoluteTolerance=0,'INVALID_PIPELINE'],
    ['changed plan',(p,q,s)=>s.repeats=4,'INVALID_PIPELINE']
  ];
  const results=[];
  for(const [name,mutate,expected] of cases){const p=copy(pairs),q=copy(policy),s=copy(plan);mutate(p,q,s);const before=digest([s,q,p]);const r=runPipeline(s,q,p,digest(plan));assert.equal(r.summary?.pattern||r.status,expected,name);assert.equal(r.gameVerification,'NOT_RUN');assert.equal(digest([s,q,p]),before);results.push(name);}
  const p=copy(pairs);p[0].candidate.events[1].payload.value+=0.00005;const x=runPipeline(plan,policy,p,digest(plan));assert.equal(x.summary.counts.exact,8);assert.equal(x.summary.counts.tolerated,1);assert.equal(x.details[0].strict.status,'DIFFERENT');assert.equal(x.details[0].result.adjustments.length,1);assert.notEqual(x.details[0].referenceTraceSHA256,x.details[0].candidateTraceSHA256);results.push('exact/tolerated evidence');
  const rev=runPipeline(plan,policy,[...p].reverse(),digest(plan));assert.deepEqual(rev,x);results.push('arrival order independent');
  const s=copy(plan);s.context.policySHA256=digest(null);const y=runPipeline(s,null,p,digest(s));assert.equal(y.summary.pattern,'MIXED_WITHIN_SEED');results.push('strict-only policy');
  const bad=copy(policy);bad.channels[0].absoluteTolerance=1;s.context.policySHA256=digest(bad);assert.equal(runPipeline(s,bad,[],digest(s)).status,'INVALID_PIPELINE');results.push('reject invalid locked policy on empty matrix');
  return results;
}

if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const args=process.argv.slice(2);
  if(args.length===1&&args[0]==='--self-test')console.log(JSON.stringify({scope:'SYNTHETIC',passed:runPipelineTests(),gameVerification:'NOT_RUN'},null,2));
  else if(args.length===4){
    try{const read=p=>{if(statSync(p).size>16*1024*1024)throw Error('input too large');return JSON.parse(readFileSync(p,'utf8'));};const report=runPipeline(read(args[0]),read(args[1]),read(args[2]),args[3]);console.log(JSON.stringify(report,null,2));process.exitCode=report.status!=='REPORT'?2:report.summary.pattern==='NO_DIFFERENCE_OBSERVED'?0:1;}
    catch(e){console.error(e.message);process.exitCode=2;}
  }else{console.error('Usage: node experiment_pipeline.mjs --self-test OR plan.json policy.json pairs.json expectedPlanSHA256');process.exitCode=2;}
}
