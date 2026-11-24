#!/usr/bin/env python3
"""Prepare an explicitly EULA-authorized, disposable test-only Fabric source set."""
import argparse, hashlib, importlib.util, json, shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--accept-eula',action='store_true')
    a=p.parse_args()
    if not a.accept_eula: p.error('Review https://aka.ms/MinecraftEULA before passing --accept-eula')
    src,dst=a.project.resolve(),a.work.resolve()
    if dst.exists() or dst.is_relative_to(src) or src.is_relative_to(dst): p.error('A new independent directory is required')
    spec=importlib.util.spec_from_file_location('doctor',src/'studio_build.py')
    doctor=importlib.util.module_from_spec(spec); spec.loader.exec_module(doctor)
    report,meta,digest=doctor.source_check(src)
    receipt=json.loads((src/'studio-build-result.json').read_text())
    jar=src/'build/libs'/f"{meta['id']}-{meta['version']}.jar"
    sha=doctor.check_jar(jar,report,meta)['sha256']
    if receipt.get('status')!='BUILD_VERIFIED' or receipt.get('sourceSha256')!=digest or receipt['jar']['sha256']!=sha or meta['id']!='stormshard_mod':
        raise SystemExit('Verified unchanged fixture required')
    manifest=json.loads((src/'studio-build-manifest.json').read_text())
    for name in [*manifest['files'],'studio-build-manifest.json']:
        target=dst/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src/name,target)
    # EULA approval applies only to this temporary test configuration.
    with (dst/'build.gradle').open('a') as f:
        f.write('\n' + '''fabricApi {
    configureTests {
        createSourceSet = true
        modId = "mms-world-test"
        enableGameTests = true
        enableClientGameTests = true
        eula = true
    }
}
''')
    testjava=dst/'src/gametest/java/studio/acceptance'
    testjava.mkdir(parents=True)
    for name in ['WorldGameTests.java','ClientWorldTest.java']: shutil.copyfile(HERE/name,testjava/name)
    resources=dst/'src/gametest/resources'; resources.mkdir(parents=True)
    (resources/'fabric.mod.json').write_text(json.dumps(dict(schemaVersion=1,id='mms-world-test',version='1.0.0',name='MMS disposable world tests',environment='*',entrypoints={'fabric-gametest':['studio.acceptance.WorldGameTests'],'fabric-client-gametest':['studio.acceptance.ClientWorldTest']},depends={'stormshard_mod':'*'}),indent=2)+'\n')
    # Loom handles client test EULA; server file is isolated and explicitly authorized.
    server=dst/'build/run/gameTest';server.mkdir(parents=True)
    (server/'eula.txt').write_text('eula=true\n')
    if doctor.source_check(src)[2]!=digest or doctor.check_jar(jar,report,meta)['sha256']!=sha: raise SystemExit('Baseline modified')
    (dst/'world-test-baseline.json').write_text(json.dumps(dict(sourceSha256=digest,jarSha256=sha,eulaOptIn=True,scope='test-only source set; production JAR unchanged; not production JAR runtime'),indent=2)+'\n')
    print('Prepared authorized isolated GameTest environment')
if __name__=='__main__':main()
