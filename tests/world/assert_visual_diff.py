#!/usr/bin/env python3
"""Assert that a real rendered idle-to-attack pose changes pixels around the mob."""
import argparse, json
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--screenshots",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    idle=next(a.screenshots.glob("*guardian_idle.png"))
    attack=next(a.screenshots.glob("*guardian_attack.png"))
    x=Image.open(idle).convert("RGB")
    y=Image.open(attack).convert("RGB")
    if x.size!=y.size: raise SystemExit("Screenshot dimensions differ")
    w,h=x.size
    box=(int(w*.35),int(h*.18),int(w*.65),int(h*.82))
    dx=ImageChops.difference(x.crop(box),y.crop(box))
    mask=dx.convert("L").point(lambda value:255 if value>=12 else 0)
    changed=sum(1 for value in mask.getdata() if value)
    total=mask.width*mask.height
    ratio=changed/total
    mean=max(ImageStat.Stat(dx).mean)
    result={"status":"PASS" if changed>=120 and ratio>=0.001 else "FAIL","idle":idle.name,"attack":attack.name,"crop":box,"changed_pixels":changed,"crop_pixels":total,"changed_ratio":round(ratio,6),"max_channel_mean_delta":round(mean,4),"threshold_pixels":120,"threshold_ratio":0.001}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    if result["status"]!="PASS": raise SystemExit("Rendered attack pose did not produce a sufficient visual difference")
if __name__=="__main__":main()
