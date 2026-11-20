// H0 synthetic differential trace research; no game or SDK integration.
// Run: node --input-type=module -e "import {runSelfTests} from './research/horizon/trace_compare.mjs'; console.log(runSelfTests())"

function canonical(v, depth=0) {
  if(depth>32) throw new Error("payload depth");
  if(v===null || typeof v==="boolean" || typeof v==="string") return JSON.stringify(v);
  if(typeof v==="number") {
    if(!Number.isFinite(v) || (Number.isInteger(v)&&!Number.isSafeInteger(v))) throw new Error("invalid number");
    return JSON.stringify(v);
  }
  if(Array.isArray(v)) return "["+v.map(x=>canonical(x,depth+1)).join(",")+"]";
  if(typeof v==="object" && (Object.getPrototypeOf(v)===Object.prototype || Object.getPrototypeOf(v)===null)) return "{"+Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+canonical(v[k],depth+1)).join(",")+"}";
  throw new Error("not JSON");
}

function validateTrace(t) {
  const need=(b,m)=>{if(!b)throw new Error(m);};
  need(t && typeof t==="object" && !Array.isArray(t),"trace object");
  need(t.schemaVersion===1 && t.scope==="SYNTHETIC","H0 accepts synthetic traces only");
  need(typeof t.runtime==="string" && t.runtime.length>0 && typeof t.build==="string" && t.build.length>0,"runtime/build required");
  need(typeof t.caseId==="string" && t.caseId.length>0 && /^[a-f0-9]{64}$/.test(t.fixtureSHA256||""),"case/fixture identity");
  need(typeof t.gameVersion==="string" && t.gameVersion.length>0 && Number.isSafeInteger(t.seed),"version/seed required");
  need(Object.hasOwn(t,"input") && Object.hasOwn(t,"initialState"),"input/initialState required");
  need(t.complete===true,"incomplete trace");
  need(Array.isArray(t.events)&&t.events.length>=2&&t.events.length<=10000,"event count");
  let tick=-1;
  for(const e of t.events) {
    need(e && typeof e==="object" && !Array.isArray(e),"event object");
    need(Object.keys(e).sort().join(",")==="kind,payload,tick","event fields");
    need(Number.isSafeInteger(e.tick)&&e.tick>=0&&e.tick>=tick,"tick order");
    need(typeof e.kind==="string"&&e.kind.length>0,"event kind");
    canonical(e.payload);tick=e.tick;
  }
  need(t.events[0].kind==="case.begin"&&t.events[0].tick===0&&t.events.at(-1).kind==="case.end","case boundaries");
  need(t.events.slice(1,-1).every(e=>!["case.begin","case.end"].includes(e.kind)),"nested boundary");
  canonical(t.input);canonical(t.initialState);
}

function compareTraces(a,b) {
  for(const [side,t] of [["reference",a],["candidate",b]]) {
    try {validateTrace(t);} catch(e) {return {status:"INVALID",scope:"SYNTHETIC",side,reason:e.message};}
  }
  for(const key of ["caseId","fixtureSHA256","gameVersion","seed","input","initialState"]) {
    if(canonical(a[key])!==canonical(b[key])) return {status:"NOT_COMPARABLE",scope:"SYNTHETIC",reason:key};
  }
  const n=Math.max(a.events.length,b.events.length);
  for(let i=0;i<n;i++) {
    const x=a.events[i],y=b.events[i];
    if(!x || !y || canonical(x)!==canonical(y)) return {status:"DIFFERENT",scope:"SYNTHETIC",firstDifference:{index:i,reference:x??null,candidate:y??null}};
  }
  return {status:"MATCH",scope:"SYNTHETIC",comparedEvents:n,gameVerification:"NOT_RUN"};
}

function runSelfTests() {
  const base={schemaVersion:1,scope:"SYNTHETIC",runtime:"synthetic-java",build:"fixture-1",caseId:"B01",fixtureSHA256:"a".repeat(64),gameVersion:"26.3",seed:17,input:{hand:"main"},initialState:{cooldown:0},complete:true,events:[{tick:0,kind:"case.begin",payload:{}},{tick:0,kind:"spawn",payload:{id:"lightning",x:2}},{tick:0,kind:"cooldown",payload:{ticks:20}},{tick:1,kind:"case.end",payload:{success:true}}]};
  const copy=()=>JSON.parse(JSON.stringify(base));
  const tests=[
    ["same observations / different runtime",b=>{b.runtime="synthetic-rust";}, "MATCH"],
    ["key order ignored",b=>{b.events[1].payload={x:2,id:"lightning"};},"MATCH"],
    ["missing effect",b=>{b.events.splice(1,1);},"DIFFERENT"],
    ["duplicated effect",b=>{b.events.splice(1,0,b.events[1]);},"DIFFERENT"],
    ["reordered effects",b=>{[b.events[1],b.events[2]]=[b.events[2],b.events[1]];},"DIFFERENT"],
    ["effect payload changed",b=>{b.events[1].payload.x=3;},"DIFFERENT"],
    ["effect type changed",b=>{b.events[1].payload.x="2";},"DIFFERENT"],
    ["effect timing changed",b=>{b.events[3].tick=2;},"DIFFERENT"],
    ["game version differs",b=>{b.gameVersion="26.2";},"NOT_COMPARABLE"],
    ["seed differs",b=>{b.seed=18;},"NOT_COMPARABLE"],
    ["input differs",b=>{b.input.hand="off";},"NOT_COMPARABLE"],
    ["initial state differs",b=>{b.initialState.cooldown=1;},"NOT_COMPARABLE"],
    ["fixture differs",b=>{b.fixtureSHA256="b".repeat(64);},"NOT_COMPARABLE"],
    ["case differs",b=>{b.caseId="B02";},"NOT_COMPARABLE"],
    ["incomplete",b=>{b.complete=false;},"INVALID"],
    ["missing boundary",b=>{b.events.pop();},"INVALID"],
    ["backward tick",b=>{b.events[1].tick=2;},"INVALID"],
    ["real game claims forbidden in H0",b=>{b.scope="GAME";},"INVALID"],
    ["unknown event fields",b=>{b.events[1].timestamp=7;},"INVALID"],
    ["missing build provenance",b=>{delete b.build;},"INVALID"],
    ["non-finite number",b=>{b.events[1].payload.x=Infinity;},"INVALID"]
  ];
  const results=tests.map(([name,mutate,expected])=>{const candidate=copy();mutate(candidate);const actual=compareTraces(base,candidate);return {name,expected,actual:actual.status,pass:actual.status===expected};});
  if(results.some(x=>!x.pass))throw new Error(JSON.stringify(results));
  return results;
}

export { compareTraces, runSelfTests };
