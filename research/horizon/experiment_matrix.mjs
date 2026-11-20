// H0 synthetic experiment aggregation, not actual game testing or statistical inference.
// Observations are externally supplied pair outcomes and fingerprints, not authenticated raw traces.
// Reference fingerprint: hash of a fixed canonical observation protocol's events, excluding runtime metadata.
// Pre-register conditions, seeds, repeats and policy; caller must independently establish preregistration and provenance.
// Run from repo root: node --input-type=module -e "import {runMatrixTests} from './research/horizon/experiment_matrix.mjs'; console.log(runMatrixTests())"

function aggregateMatrix(plan, observations){
  const fail=m=>{throw Error(m)};
  const hash=x=>typeof x==="string"&&/^[a-f0-9]{64}$/.test(x);
  const str=x=>typeof x==="string"&&x.length>0&&x.length<=256;
  const keys=["caseId","fixtureSHA256","gameVersion","referenceBuild","candidateBuild","policySHA256"];
  const contextValid=c=>c&&keys.every(k=>k.endsWith("SHA256")?hash(c[k]):str(c[k]));
  const outcomes=new Set(["MATCH","MATCH_UNDER_POLICY","DIFFERENT","INVALID","NOT_COMPARABLE","AMBIGUOUS","INVALID_POLICY"]);
  try {
    if(!plan||plan.schemaVersion!==1||plan.scope!=="SYNTHETIC"||!contextValid(plan.context))fail("invalid synthetic plan");
    if(!Number.isInteger(plan.repeats)||plan.repeats<2||plan.repeats>20||!Array.isArray(plan.seeds)||plan.seeds.length<3||plan.seeds.length>100)fail("invalid matrix dimensions");
    const seedMap=new Map();
    for(const s of plan.seeds){
      if(!s||!Number.isSafeInteger(s.seed)||seedMap.has(s.seed)||!hash(s.conditionSHA256))fail("invalid or duplicate seed");
      seedMap.set(s.seed,s.conditionSHA256);
    }
    if(!Array.isArray(observations)||observations.length>plan.repeats*seedMap.size)fail("invalid observation count");
    const byCell=new Map();
    for(const o of observations){
      if(!o||o.scope!=="SYNTHETIC"||!contextValid(o.context)||keys.some(k=>o.context[k]!==plan.context[k]))fail("observation context mismatch");
      if(!seedMap.has(o.seed)||o.conditionSHA256!==seedMap.get(o.seed)||!Number.isInteger(o.repeat)||o.repeat<1||o.repeat>plan.repeats)fail("unplanned or mismatched cell");
      if(!outcomes.has(o.status))fail("unknown comparison status");
      if(["MATCH","MATCH_UNDER_POLICY","DIFFERENT"].includes(o.status)&&!hash(o.referenceObservationSHA256))fail("missing reference observation fingerprint");
      const key=o.seed+":"+o.repeat;
      if(byCell.has(key))fail("duplicate cell");
      byCell.set(key,o);
    }
    const groups=[],missing=[],unusable=[];
    let exact=0,tolerated=0,different=0;
    for(const seed of seedMap.keys()){
      const group={seed,exact:0,tolerated:0,different:0,missing:0,unusable:0,referenceVariation:false};
      const refs=new Set();
      for(let repeat=1;repeat<=plan.repeats;repeat++){
        const o=byCell.get(seed+":"+repeat);
        if(!o){missing.push({seed,repeat});group.missing++;continue;}
        if(o.status==="MATCH"){exact++;group.exact++;}
        else if(o.status==="MATCH_UNDER_POLICY"){tolerated++;group.tolerated++;}
        else if(o.status==="DIFFERENT"){different++;group.different++;}
        else{unusable.push({seed,repeat,status:o.status});group.unusable++;continue;}
        refs.add(o.referenceObservationSHA256);
      }
      group.referenceVariation=refs.size>1;
      group.pattern=group.missing||group.unusable?"INCOMPLETE":group.referenceVariation?"REFERENCE_VARIATION":group.different===0?"NO_DIFFERENCE_OBSERVED":group.different===plan.repeats?"REPEATED_DIFFERENCE":"MIXED_WITHIN_SEED";
      groups.push(group);
    }
    let pattern;
    if(missing.length||unusable.length)pattern="INCOMPLETE";
    else if(groups.some(g=>g.referenceVariation))pattern="REFERENCE_VARIATION";
    else if(groups.some(g=>g.pattern==="MIXED_WITHIN_SEED"))pattern="MIXED_WITHIN_SEED";
    else if(different===0)pattern="NO_DIFFERENCE_OBSERVED";
    else if(groups.every(g=>g.pattern==="REPEATED_DIFFERENCE"))pattern="REPEATED_ACROSS_TESTED_SEEDS";
    else pattern="SEED_ASSOCIATED_PATTERN";
    return {status:"ANALYZED",scope:"SYNTHETIC",pattern,planned:plan.repeats*seedMap.size,received:observations.length,counts:{exact,tolerated,different,missing:missing.length,unusable:unusable.length},groups,missing,unusable,cause:"UNDETERMINED",gameVerification:"NOT_RUN"};
  }catch(e){return {status:"INVALID_MATRIX",scope:"SYNTHETIC",reason:e.message,cause:"UNDETERMINED",gameVerification:"NOT_RUN"};}
}

function runMatrixTests(){
  const ctx={caseId:"B01",fixtureSHA256:"a".repeat(64),gameVersion:"26.3",referenceBuild:"synthetic-java-r1",candidateBuild:"synthetic-rust-r1",policySHA256:"b".repeat(64)};
  const plan={schemaVersion:1,scope:"SYNTHETIC",context:ctx,repeats:3,seeds:[{seed:17,conditionSHA256:"c".repeat(64)},{seed:31,conditionSHA256:"d".repeat(64)},{seed:59,conditionSHA256:"e".repeat(64)}]};
  const rows=plan.seeds.flatMap((s,i)=>[1,2,3].map(repeat=>({scope:"SYNTHETIC",context:{...ctx},...s,repeat,status:"MATCH",referenceObservationSHA256:String(i+1).repeat(64)})));
  const clone=x=>JSON.parse(JSON.stringify(x));
  const cases=[
    ["all exact",()=>{},"NO_DIFFERENCE_OBSERVED"],
    ["all tolerance match",r=>{r.forEach(o=>o.status="MATCH_UNDER_POLICY")},"NO_DIFFERENCE_OBSERVED"],
    ["all differ",r=>{r.forEach(o=>o.status="DIFFERENT")},"REPEATED_ACROSS_TESTED_SEEDS"],
    ["only one seed differs throughout",r=>{r.filter(o=>o.seed===17).forEach(o=>o.status="DIFFERENT")},"SEED_ASSOCIATED_PATTERN"],
    ["one intermittent difference",r=>{r[0].status="DIFFERENT"},"MIXED_WITHIN_SEED"],
    ["mixed overrides seed-associated pattern",r=>{r.slice(0,4).forEach(o=>o.status="DIFFERENT")},"MIXED_WITHIN_SEED"],
    ["reference fingerprint changes",r=>{r[0].status="DIFFERENT";r[0].referenceObservationSHA256="f".repeat(64)},"REFERENCE_VARIATION"],
    ["different reference fingerprints across seeds allowed",()=>{},"NO_DIFFERENCE_OBSERVED"],
    ["missing observation",r=>{r.pop()},"INCOMPLETE"],
    ["unusable pair",r=>{r[0].status="NOT_COMPARABLE"},"INCOMPLETE"],
    ["ambiguous pair",r=>{r[0].status="AMBIGUOUS"},"INCOMPLETE"],
    ["invalid policy",r=>{r[0].status="INVALID_POLICY"},"INCOMPLETE"],
    ["incomplete overrides apparent repeated difference",r=>{r.forEach(o=>o.status="DIFFERENT");r.pop()},"INCOMPLETE"],
    ["duplicate cell",r=>{r[1]=clone(r[0])},"INVALID_MATRIX"],
    ["unplanned seed",r=>{r[0].seed=87},"INVALID_MATRIX"],
    ["repeat out of range",r=>{r[0].repeat=4},"INVALID_MATRIX"],
    ["changed condition fingerprint",r=>{r[0].conditionSHA256="0".repeat(64)},"INVALID_MATRIX"],
    ["build changes mid-run",r=>{r[0].context.candidateBuild="other"},"INVALID_MATRIX"],
    ["policy changes mid-run",r=>{r[0].context.policySHA256="0".repeat(64)},"INVALID_MATRIX"],
    ["missing baseline fingerprint",r=>{delete r[0].referenceObservationSHA256},"INVALID_MATRIX"],
    ["unsupported comparison outcome",r=>{r[0].status="PASS"},"INVALID_MATRIX"],
    ["non-synthetic data",r=>{r[0].scope="GAME"},"INVALID_MATRIX"],
    ["duplicate planned seed",(r,p)=>{p.seeds[1]=p.seeds[0]},"INVALID_MATRIX"],
    ["too few distinct seeds",(r,p)=>{p.seeds.pop()},"INVALID_MATRIX"]
  ];
  const results=cases.map(([name,change,expected])=>{const r=clone(rows),p=clone(plan);change(r,p);const before=JSON.stringify([p,r]);const x=aggregateMatrix(p,r);if(before!==JSON.stringify([p,r]))throw Error("input changed");return {name,expected,actual:x.pattern||x.status,pass:(x.pattern||x.status)===expected&&x.cause==="UNDETERMINED"&&x.gameVerification==="NOT_RUN"}});
  const r=clone(rows);r[0].status="MATCH_UNDER_POLICY";r[1].status="DIFFERENT";r[2].status="INVALID";r.pop();
  const x=aggregateMatrix(plan,r);
  results.push({name:"separate exact, tolerated, different, missing and unusable counts",pass:x.counts.exact===5&&x.counts.tolerated===1&&x.counts.different===1&&x.counts.unusable===1&&x.counts.missing===1});
  const forward=aggregateMatrix(plan,rows),reverse=aggregateMatrix(plan,rows.slice().reverse());
  results.push({name:"arrival order independent",pass:JSON.stringify(forward)===JSON.stringify(reverse)});
  if(results.some(r=>!r.pass))throw Error(JSON.stringify(results));
  return results;
}

export { aggregateMatrix, runMatrixTests };
