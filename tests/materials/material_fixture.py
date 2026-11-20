#!/usr/bin/env python3
"""Generate and verify a specialized material + locomotion fixture from the real Studio compiler.
No Minecraft boot or EULA acceptance. Use a clean export from test_browser_export.py.
"""
import argparse, io, json, os, subprocess, tempfile, zipfile
from collections import Counter
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

SHIM = '''<script>(()=>{const m=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(k,String(v)),removeItem:k=>m.delete(k),clear:()=>m.clear(),key:i=>[...m.keys()][i]??null,get length(){return m.size}}});})();</script>'''
HARNESS = '''import studio.generated.m_73746f726d73686172645f6d6f64.StormGuardianRig;
class MaterialFixtureCheck {
  static int checks;
  static void near(double a,double b){if(!Double.isFinite(a)||Math.abs(a-b)>1e-7)throw new AssertionError(a+" != "+b);checks++;}
  public static void main(String[] args){
    for(int tick=-20;tick<=40;tick++){
      double t=Math.floorMod(tick,20), expected=t<=10?0.5-t/10:-0.5+(t-10)/10;
      near(StormGuardianRig.poseAt("idle","leg_l",tick).rx(),0);
      near(StormGuardianRig.poseAt("walk","leg_l",tick).rx(),expected);
      near(StormGuardianRig.poseAt("walk","leg_r",tick).rx(),-expected);
      for(double speed:new double[]{0,0.05,0.325,0.6,1}){
        double w=speed<=.05?0:speed>=.6?1:.5;
        double actual=StormGuardianRig.locomotionBlend(speed,.05,.6);
        near(actual,w);
        near(StormGuardianRig.blend(StormGuardianRig.poseAt("idle","leg_l",tick),StormGuardianRig.poseAt("walk","leg_l",tick),actual).rx(),expected*w);
      }
    }
    near(StormGuardianRig.poseAt("attack","arm_r",-2).rx(),0);
    near(StormGuardianRig.poseAt("attack","arm_r",2).rx(),1.25);
    near(StormGuardianRig.poseAt("attack","arm_r",8).rx(),0);
    near(StormGuardianRig.poseAt("attack","arm_r",99).rx(),0);
    System.out.println("RIG_ASSERTIONS="+checks);
  }
}'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--html',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True,help='studio-project.json from default export')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=False)
    project=json.loads(a.baseline.read_text()); mob=next(m for m in project['studio']['mobs'] if m['id']=='storm_guardian'); model=mob['model']
    mats={m['id']:m for m in model['materials']}
    mats['mat_71a8ba'].update(mode='translucent',opacity=.5)
    mats['mat_8ac2d0'].update(mode='cutout',opacity=1,emissive=True,emissiveColor='#ffffff',emissiveIntensity=1)
    assert model['texture']['width']==256 and model['texture']['height']==64
    model['texture']['painted'][str(12*256+40)]='#ffffff00'
    assert all(x['id']!='idle' for x in model['animations'])
    model['animations'].append(dict(id='idle',name='Idle',duration=20,loop=True,keyframes=[dict(time=t,bone=b,rotation=[0,0,0],position=[0,0,0],easing='linear') for b in ['leg_l','leg_r'] for t in [0,10]],events=[]))
    model['animationController']['idleAnimation']='idle'
    next(x for x in mob['animationStateMachine']['states'] if x['id']=='idle')['animation']='idle'
    errors=[]
    with sync_playwright() as pw:
        opts={'headless':True,'args':['--no-sandbox']}
        if os.getenv('CHROMIUM'): opts['executable_path']=os.environ['CHROMIUM']
        browser=pw.chromium.launch(**opts); page=browser.new_page(accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(a.html.read_text(encoding='utf-8-sig').replace('<script>',SHIM+'<script>',1),wait_until='load')
        raw=page.evaluate('p=>Array.from(StudioCompiler.compile(p,{allowPartial:true}).zip())',project)
        browser.close()
    assert not errors,errors
    archive=a.out/'material-source.zip'; archive.write_bytes(bytes(raw))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
        assert all(not n.startswith('/') and '..' not in n.split('/') and '\\' not in n for n in z.namelist())
        z.extractall(a.out/'project')
        base='src/main/resources/assets/stormshard_mod/textures/entity/storm_guardian'
        def image(suffix):return Image.open(io.BytesIO(z.read(base+suffix+'.png'))).convert('RGBA')
        color,orm,emissive=map(image,['','_orm','_emissive'])
        checks=[color.size==orm.size==emissive.size==(256,64),color.getpixel((8,8))==(113,168,186,128),color.getpixel((40,12))[3]==0,color.getpixel((41,12))[3]==255,emissive.getpixel((41,12))==(255,255,255,255),emissive.getpixel((40,12))[3]==0,emissive.getpixel((8,8))[3]==0,emissive.getpixel((64,12))[3]==0,color.getchannel('A').tobytes()==orm.getchannel('A').tobytes()]
        assert all(checks),checks
        names=z.namelist(); pick=lambda suffix: z.read(next(n for n in names if n.endswith(suffix))).decode()
        assert 'RenderTypes.entityTranslucent(TEXTURE)' in pick('StormGuardianRenderer.java')
        assert 'registrationHelper.register(new StormGuardianEmissiveLayer(renderer))' in pick('StudioClient.java')
        assert 'RenderTypes.eyes(' in pick('StormGuardianEmissiveLayer.java')
        model_java=pick('StormGuardianEntityModel.java')
        assert 'String idleAnimation = "idle"' in model_java and 'String walkAnimation = "walk"' in model_java
        assert 'new State("idle","idle",true)' in pick('StormGuardianAnimationStateMachine.java')
        # This is a design risk, not a failed gameplay assertion: controller-triggered locomotion clips currently override the blend at weight 1.
        overlay='StormGuardianRig.poseAt(state.studioAnimationId,"leg_l",state.studioAnimationTime),1.0)' in model_java
    root=a.out/'project'; loader=root/'studio_build.py'
    # Run the export's own validator, independently of the fixture checks.
    import importlib.util
    spec=importlib.util.spec_from_file_location('studio_build',loader); doctor=importlib.util.module_from_spec(spec);spec.loader.exec_module(doctor)
    report,meta,digest=doctor.source_check(root)
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp); harness=tmp/'MaterialFixtureCheck.java';harness.write_text(HARNESS)
        subprocess.run(['javac','-d',str(tmp),str(next(root.rglob('StormGuardianRig.java'))),str(harness)],check=True)
        result=subprocess.run(['java','-cp',str(tmp),'MaterialFixtureCheck'],check=True,capture_output=True,text=True).stdout.strip()
    evidence={'status':'SOURCE_FIXTURE_VERIFIED','material_pixel_assertions':len(checks),'source_wiring_assertions':5,'rig_assertions':int(result.split('=')[1]),'atlas_alpha_counts':dict(Counter(color.getchannel('A').tobytes())),'sourceSha256':digest,'expectedJarEntries':len(report['expectedJarEntries']),'locomotion_overlay_risk':overlay,'fabric_build':'NOT_RUN_BY_THIS_SCRIPT','game_runtime':'NOT_RUN','eula_written':False}
    (a.out/'result.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
if __name__=='__main__':main()
