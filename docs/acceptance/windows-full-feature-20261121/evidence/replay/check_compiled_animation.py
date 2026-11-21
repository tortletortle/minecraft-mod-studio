from pathlib import Path
import hashlib, json, os, subprocess, sys
from xml.etree import ElementTree

ROOT = Path.cwd().resolve()
WORK = ROOT / 'work/full-generation-20261121'
OUT = ROOT / 'outputs/full-feature-acceptance-20261121/compiled-animation-production'
PROJECTS = {
    'pr6': ROOT / 'outputs/crystal-lab-full-pipeline/fabric-project',
    'main': ROOT / 'outputs/full-feature-acceptance-20261121/main-snapshot-verified/fabric-project',
}
JVM = ROOT / 'work/jdk25-round3/jdk-25.0.5+8/bin/java.exe'
CACHE = Path(os.environ.get('GRADLE_USER_HOME') or str(Path.home() / '.gradle')) / 'caches'
EXTERNAL = CACHE / 'modules-2/files-2.1'
VENDOR = json.loads((CACHE / 'fabric-loom/26.2/mojang_minecraft_info.json').read_text(encoding='utf-8'))

OUT.mkdir(parents=True, exist_ok=False)

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run_variant(name, project):
    production = project / 'build/libs/crystal_lab-1.0.0.jar'
    client_jars = sorted((project / '.gradle/loom-cache/minecraftMaven').rglob('*.jar'))
    assert production.is_file() and len(client_jars) == 2, (production, client_jars)
    deps = []
    for library in VENDOR['libraries']:
        org, artifact, version, *classifier = library['name'].split(':')
        if classifier:
            continue
        name_part = f'{artifact}-{version}.jar'
        dep = next((EXTERNAL / org / artifact / version).glob(f'*/{name_part}'), None)
        if dep and dep not in deps:
            deps.append(dep)
    api_ver = '0.161.0+26.2'
    pom = next((EXTERNAL / 'net.fabricmc.fabric-api/fabric-api' / api_ver).glob(f'*/fabric-api-{api_ver}.pom'))
    api = []
    ns = {'pom':'http://maven.apache.org/POM/4.0.0'}
    for dep in ElementTree.parse(pom).findall('pom:dependencies/pom:dependency', ns):
        group, artifact, version = (dep.findtext('pom:' + key, namespaces=ns) for key in ('groupId','artifactId','version'))
        match = next((EXTERNAL / group / artifact / version).glob(f'*/{artifact}-{version}.jar'), None)
        if match:
            api.append(match)
    classpath = os.pathsep.join(p.as_posix() for p in [production, *client_jars, *deps, *api])
    args = '\n'.join(['-Duser.language=en', '-Duser.country=US', '-Dfile.encoding=UTF-8', '-cp', f'"{classpath}"', f'"{(WORK / "CompiledAnimationCheck.java").as_posix()}"', ''])
    args_file = OUT / f'{name}.args.txt'
    args_file.write_text(args, encoding='utf-8')
    result = subprocess.run([str(JVM), '@' + str(args_file)], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    (OUT / f'{name}.stdout.json').write_text(result.stdout, encoding='utf-8')
    (OUT / f'{name}.stderr.log').write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return {'production_jar_sha256':sha256(production), **json.loads(result.stdout)}

def main():
    observations = {name: run_variant(name, project) for name, project in PROJECTS.items()}
    assert observations['pr6']['samples'][0] == observations['main']['samples'][0]
    assert observations['pr6']['samples'][2] == observations['main']['samples'][2]
    assert observations['pr6']['samples'][2]['left_arm_x_rotation'] == -1.25
    assert [observations[name]['samples'][1]['left_leg_x_rotation'] for name in PROJECTS] == [0.5, -0.5]
    result = {'status':'OBSERVED_BRANCH_DIFFERENCE', 'minecraft':'26.2', 'scope':'Production JAR setupAnim with actual Minecraft ModelPart, controlled renderer snapshot, no client frame', 'observations':observations}
    formatted = json.dumps(result, indent=2)
    (OUT/'result.json').write_text(formatted+'\n',encoding='utf-8')
    print(formatted)

if __name__ == '__main__':
    main()
