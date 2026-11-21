import * as core from './core.mjs';
import {createEditor} from './editor-model.mjs';
import {projection} from './projection.mjs';
import {generateDungeon} from './dungeon.mjs';
const $=id=>document.getElementById(id),canvas=$('view'),ctx=canvas.getContext('2d');
const materials=[['stone_bricks','#92979c','石砖'],['oak_planks','#b89662','橡木板'],['spruce_planks','#856243','云杉木板'],['dark_oak_planks','#624832','深色橡木板'],['deepslate_bricks','#51555b','深板岩砖'],['polished_andesite','#a3a5a7','磨制安山岩'],['cobbled_deepslate','#686a70','深板岩圆石'],['iron_block','#c4c9cd','铁块'],['copper_block','#bc7450','铜块'],['glass','#8fc3cb','玻璃'],['crafting_table','#b18b55','工作台'],['bookshelf','#8f694b','书架'],['ladder','#bf9c63','梯子'],['glowstone','#e3b968','萤石'],['grass_block','#779a57','草方块'],['polished_deepslate','#53565d','磨制深板岩'],['bone_block','#d7d0bc','骨块'],['shroomlight','#e4b56a','菌光体'],['sea_lantern','#b9dcd8','海晶灯'],['chiseled_stone_bricks','#888c91','錾制石砖'],['gold_block','#e4c34d','金块'],['crying_obsidian','#51406d','哭泣的黑曜石'],['iron_bars','#9ca4aa','铁栏杆']];
const colors=new Map(materials.map(([id,color])=>['minecraft:'+id,color]));
const air=new Set(['minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:structure_void']);
const idOf=c=>typeof c?.block==='string'?c.block:c?.block?.name;
const coord=(x,y,z)=>x+','+y+','+z;
let preset='factory',editor=createEditor(core.generate({preset,seed:42})),view,rotation=0,full=false,layer=3,mode='place',selection=[13,8],dirty=false,st,lookup,solid,frame=0;
function notify(s){$('status').textContent=s;$('error').textContent='';}
function fail(e){$('error').textContent=e.message??String(e);}
function act(fn){return (...args)=>{try{fn(...args);}catch(e){fail(e);}};}
function shade(hex,n){const a=parseInt(hex.slice(1),16),v=s=>Math.max(0,Math.min(255,Math.round(s*n)));return 'rgb('+[v(a>>16),v((a>>8)&255),v(a&255)].join(',')+')';}
function setMode(m){mode=m;for(const b of document.querySelectorAll('[data-mode]'))b.classList.toggle('active',b.dataset.mode===m);notify({place:'放置方块',erase:'擦除：写入空气',preserve:'保留地形：移除模板位置'}[m]);}
function palette(){const q=$('search').value.toLowerCase();$('materials').replaceChildren();for(const [id,color,label] of materials){const name='minecraft:'+id;if(![name,label].some(x=>x.toLowerCase().includes(q)))continue;const b=document.createElement('button'),sw=document.createElement('span');sw.className='swatch';sw.style.background=color;b.append(sw,document.createTextNode(label+' · '+id));b.classList.toggle('active',$('material').value===name);b.onclick=()=>{$('material').value=name;palette();setMode('place');};$('materials').append(b);}}
function refresh(reset=false){st=editor.snapshot();lookup=new Map(st.blocks.map(c=>[coord(...c.pos),c]));solid=st.blocks.filter(c=>!air.has(idOf(c)));const [w,h,d]=st.size;
 if(reset){$('width').value=w;$('height').value=h;$('depth').value=d;$('seed').value=st.metadata?.seed??42;layer=Math.min(h-1,3);selection=[Math.floor(w/2),Math.floor(d/2)];}
 $('layer').max=h-1;$('layer').value=layer;$('x').max=w-1;$('z').max=d-1;
 $('counts').textContent='尺寸 '+st.size.join(' × ')+' · 实体 '+solid.length+' · 写入 '+st.blocks.length+' · 保留 '+(w*h*d-st.blocks.length);
 const hist=editor.history();$('undo').disabled=!hist.undo;$('redo').disabled=!hist.redo;
 const nodes=[];const add=s=>{const el=document.createElement('div');el.textContent=s;nodes.push(el);};add('✓ 结构坐标与格式有效');
 if(st.metadata?.rooms?.length){const r=core.walkability(st);add((r.entryValid?'✓':'!')+' 地面入口 '+(r.entryValid?'有效':'受阻'));add('地面房间 '+r.rooms.filter(x=>x.reachable).length+'/'+st.metadata.rooms.filter(r=>r.pos[1]===1).length+' 可达');add('可达地面格 '+r.reachable);if(st.metadata.generator==='room-graph-v1'){add('隐藏房间 '+(st.metadata.hiddenPassages??0));add('连接关系 '+(st.metadata.connections?.length??0)+' 条');add('房间类型 '+[...new Set(st.metadata.rooms.map(x=>x.type))].join(' / '));}}else add('— 未配置入口/房间标记');
 $('checks').replaceChildren(...nodes);updateSelection();schedule();
}
function updateSelection(){$('x').value=selection[0];$('z').value=selection[1];$('layerLabel').textContent=layer+' / '+(st.size[1]-1);const b=lookup.get(coord(selection[0],layer,selection[1]));$('selected').textContent='('+selection[0]+', '+layer+', '+selection[1]+') · '+(b?idOf(b):'未写入 / 保留');$('apply').disabled=full;}
function schedule(){if(!frame)frame=requestAnimationFrame(()=>{frame=0;draw();});}
function polygon(points,fill,stroke){ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.stroke();}}
function draw(){
 const rect=canvas.getBoundingClientRect(),ww=rect.width,hh=rect.height;if(ww<1||hh<1)return;
 const ratio=Math.min(window.devicePixelRatio||1,2),cw=Math.round(ww*ratio),ch=Math.round(hh*ratio);if(canvas.width!==cw||canvas.height!==ch){canvas.width=cw;canvas.height=ch;}ctx.setTransform(ratio,0,0,ratio,0,0);ctx.fillStyle='#191d21';ctx.fillRect(0,0,ww,hh);
 const [w,h,d]=st.size,top=full?h-1:layer;
 view=projection(st.size,rotation,top,[ww,hh]);const P=view.point;
 ctx.lineWidth=.6;const line=(a,b,color)=>{ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.strokeStyle=color;ctx.stroke();};
 for(let x=0;x<=w;x++)line(P(x,0,0),P(x,0,d),'#343a40');for(let z=0;z<=d;z++)line(P(0,0,z),P(w,0,z),'#343a40');
 const faces=[{dx:1,dz:0,pts:(x,y,z)=>[[x+1,y,z],[x+1,y,z+1],[x+1,y+1,z+1],[x+1,y+1,z]]},{dx:0,dz:1,pts:(x,y,z)=>[[x,y,z+1],[x+1,y,z+1],[x+1,y+1,z+1],[x,y+1,z+1]]},{dx:-1,dz:0,pts:(x,y,z)=>[[x,y,z],[x,y,z+1],[x,y+1,z+1],[x,y+1,z]]},{dx:0,dz:-1,pts:(x,y,z)=>[[x,y,z],[x+1,y,z],[x+1,y+1,z],[x,y+1,z]]}];
 const visible=(x,y,z)=>y<=top&&lookup.has(coord(x,y,z))&&!air.has(idOf(lookup.get(coord(x,y,z))));
 const list=solid.filter(c=>c.pos[1]<=top).sort((a,b)=>view.depth(...a.pos)-view.depth(...b.pos)||a.pos[1]-b.pos[1]);
 for(const c of list){const [x,y,z]=c.pos,base=colors.get(idOf(c))??'#b1a5b9';for(const [k,i] of [rotation,(rotation+1)%4].entries()){const f=faces[i];if(!visible(x+f.dx,y,z+f.dz))polygon(f.pts(x,y,z).map(p=>P(...p)),shade(base,k?.68:.82),'#20252b');}
 if(!visible(x,y+1,z))polygon([[x,y+1,z],[x+1,y+1,z],[x+1,y+1,z+1],[x,y+1,z+1]].map(p=>P(...p)),shade(base,1.06),'#353a3f');}
 if(!full){const y=layer+1;for(let x=0;x<=w;x++)line(P(x,y,0),P(x,y,d),'#72b6a344');for(let z=0;z<=d;z++)line(P(0,y,z),P(w,y,z),'#72b6a344');const [x,z]=selection;ctx.lineWidth=1.8;polygon([[x,y,z],[x+1,y,z],[x+1,y,z+1],[x,y,z+1]].map(p=>P(...p)),'#51d88b45','#60f5a1');}
}
function load(s,newPreset){editor.load(s);preset=newPreset;full=false;$('all').classList.remove('active');$('all').textContent='完整预览';dirty=false;for(const b of document.querySelectorAll('[data-preset]'))b.classList.toggle('active',b.dataset.preset===preset);refresh(true);notify('建筑已加载');}
const canReplace=()=>!dirty||confirm('当前有未保存编辑，是否替换？');
const numeric=id=>{const el=$(id);if(el.value===''||!Number.isInteger(el.valueAsNumber))throw Error('请输入有效整数：'+id);return el.valueAsNumber;};
function regenerate(p,custom=false){if(!canReplace())return;const options={preset:p,seed:numeric('seed')};if(custom)options.size=['width','height','depth'].map(numeric);const structure=p==='dungeon'?generateDungeon({seed:options.seed,...(custom?{size:options.size}:{}),rooms:8,style:'stone',hiddenRooms:1}):core.generate(options);load(structure,p);}
function apply(){if(full)throw Error('请退出完整预览，选择活动层');const p=[selection[0],layer,selection[1]];if(editor.change([p],mode,$('material').value)){dirty=true;refresh();notify('编辑已应用 · '+p.join(', '));}else notify('未发生改变');}
function selectInputs(){const x=numeric('x'),z=numeric('z');if(x<0||x>=st.size[0]||z<0||z>=st.size[2])throw Error('坐标越界');selection=[x,z];updateSelection();schedule();}
function undo(){if(editor.undo()){dirty=true;refresh();notify('已撤销');}}
function redo(){if(editor.redo()){dirty=true;refresh();notify('已重做');}}
document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=act(()=>regenerate(b.dataset.preset)));
document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));
$('blank').onclick=act(()=>{if(!canReplace())return;const size=['width','height','depth'].map(numeric);load(core.createBuilder(size).finish({preset:'blank'}),'blank');});
$('generate').onclick=act(()=>{if(preset==='blank'){if(canReplace())load(core.createBuilder(['width','height','depth'].map(numeric)).finish({preset:'blank'}),'blank');}else regenerate(preset,true);});
$('search').oninput=palette;$('material').oninput=palette;$('undo').onclick=undo;$('redo').onclick=redo;
$('rotateLeft').onclick=()=>{rotation=(rotation+3)%4;schedule();};$('rotateRight').onclick=()=>{rotation=(rotation+1)%4;schedule();};
$('all').onclick=()=>{full=!full;$('all').classList.toggle('active',full);$('all').textContent=full?'返回分层编辑':'完整预览';$('hint').textContent=full?'完整预览：不可编辑 · 可旋转':'点击当前层网格编辑 · Shift 点击选择坐标 · 空气会清除原方块';updateSelection();schedule();};
$('layer').oninput=()=>{layer=Number($('layer').value);updateSelection();schedule();};$('apply').onclick=act(()=>{selectInputs();apply();});$('x').onchange=act(selectInputs);$('z').onchange=act(selectInputs);
canvas.addEventListener('pointerdown',act(e=>{if(e.button!==0||full||!view)return;const rect=canvas.getBoundingClientRect(),p=view.pick(e.clientX-rect.left,e.clientY-rect.top,layer+1);if(!p)return;selection=p;updateSelection();if(e.shiftKey)schedule();else apply();}));
document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;const k=e.key.toLowerCase();if((e.ctrlKey||e.metaKey)&&k==='z'){e.preventDefault();e.shiftKey?redo():undo();}else if((e.ctrlKey||e.metaKey)&&k==='y'){e.preventDefault();redo();}else if(!e.ctrlKey&&!e.metaKey&&['b','e','p'].includes(k))setMode({b:'place',e:'erase',p:'preserve'}[k]);});
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('json').onclick=act(()=>{download(new Blob([JSON.stringify(editor.snapshot())],{type:'application/json'}),'structure.json');dirty=false;notify('JSON 导出已请求');});
$('nbt').onclick=async()=>{try{if(typeof CompressionStream!=='function')throw Error('浏览器缺少 gzip CompressionStream，请使用新版 Chromium 或 CLI');const n=core.encodeNBT(editor.snapshot(),{dataVersion:4903,paletteKeys:'legacy'}),stream=new Blob([n]).stream().pipeThrough(new CompressionStream('gzip')),blob=await new Response(stream).blob();download(blob,'structure.nbt');notify('NBT gzip 导出已请求');}catch(e){fail(e);}};
$('import').onclick=()=>$('file').click();$('file').onchange=async()=>{try{const file=$('file').files[0];if(!file||!canReplace())return;if(file.size>20*1024*1024)throw Error('文件超过 20 MiB');const s=JSON.parse(await file.text());const p=s.metadata?.preset;load(s,['house','tower','factory'].includes(p)?p:'blank');}catch(e){fail(e);}finally{$('file').value='';}};
new ResizeObserver(schedule).observe(canvas);palette();refresh(true);
