import hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

base = Path(__file__).resolve().parents[2]
evidence = base / 'outputs/full-feature-acceptance-20261121/client'
profile_file = evidence / 'fabric-profile.json'
run_name = sys.argv[1] if len(sys.argv) > 1 else 'crystal'
if run_name == 'materials':
    evidence = evidence.parent / 'materials-client'
game = evidence / 'game'
gradle = Path.home() / '.gradle/caches'
loom = gradle / 'fabric-loom'
modules = gradle / 'modules-2/files-2.1'
version = loom / '26.2'
jdk = Path.home() / 'AppData/Local/Programs/Eclipse Adoptium/jdk-25.0.5+8'
original = base / 'outputs/crystal-lab-full-pipeline/fabric-project/build/libs/crystal_lab-1.0.0.jar'
if run_name == 'materials':
    original = base / 'outputs/full-claimed-acceptance-20261121/browser/materials/project/build/libs/stormshard_mod-1.0.0.jar'
template = base / 'outputs/mod-studio-test/function-export/run'


def resolve(coordinate):
    group, artifact, release, *classifier = coordinate.split(':')
    filename = '-'.join([artifact, release, *classifier]) + '.jar'
    matches = list((modules / group / artifact / release).glob(f'*/{filename}'))
    if len(matches) != 1:
        raise RuntimeError((coordinate, matches))
    return matches[0]


def allowed(entry):
    if 'rules' not in entry:
        return True
    decision = False
    for rule in entry['rules']:
        osrule = rule.get('os', {})
        if rule.get('features') or osrule.get('name', 'windows') != 'windows':
            continue
        if osrule.get('arch', 'x86_64') not in {'x86_64', 'amd64'}:
            continue
        if 'version' in osrule and not re.search(osrule['version'], '.'.join(map(str, os.sys.getwindowsversion().platform_version))):
            continue
        decision = rule['action'] == 'allow'
    return decision


def main():
    evidence.mkdir(parents=True, exist_ok=True)
    (game / 'mods').mkdir(parents=True, exist_ok=True)
    jar = game / 'mods' / original.name
    shutil.copyfile(original, jar)
    fabric_api = resolve('net.fabricmc.fabric-api:fabric-api:0.161.0+26.2')
    shutil.copyfile(fabric_api, game / 'mods' / fabric_api.name)
    world = game / 'saves/MMSAcceptance'
    if not world.exists():
        shutil.copytree(template / 'saves/New World', world, ignore=shutil.ignore_patterns('session.lock', 'playerdata', 'advancements', 'stats'))
    if not (game / 'options.txt').exists():
        options = (template / 'options.txt').read_text(encoding='utf-8')
        values = {'renderDistance': '6', 'simulationDistance': '5', 'guiScale': '2', 'key_key.use': 'key.keyboard.r'}
        for key, value in values.items():
            options = re.sub(r'^' + re.escape(key) + r':.*$', f'{key}:{value}', options, flags=re.M)
        (game / 'options.txt').write_text(options, encoding='utf-8')
    if run_name == 'materials':
        prepare_material_world(world)
    profile = json.loads(profile_file.read_text(encoding='utf-8-sig'))
    minecraft = json.loads((version / 'mojang_minecraft_info.json').read_text(encoding='utf-8'))
    coordinates = {x['name'] for x in profile['libraries']}
    libs = [resolve(x['name']) for x in profile['libraries']]
    libs += [resolve(x['name']) for x in minecraft['libraries'] if allowed(x) and x['name'] not in coordinates]
    cp = os.pathsep.join(str(p) for p in [*libs, version / 'minecraft-client.jar'])
    args = ['-Xmx1800m', '-XX:ActiveProcessorCount=4', '-Djava.net.preferIPv4Stack=true', '-classpath', cp, profile['mainClass'],
            '--username', 'MMSAcceptance', '--uuid', '76faf72f-305f-3ab8-8537-ccd9396d1b53', '--accessToken', '0',
            '--version', '26.2-fabric-0.20.1', '--gameDir', str(game), '--assetsDir', str(loom / 'assets'), '--assetIndex', '26.2-32',
            '--width', '1000', '--height', '650', '--quickPlaySingleplayer', 'MMSAcceptance']
    def quote(arg):
        return '"' + arg.replace('\\', '/').replace('"', '\\"') + '"'
    argfile = evidence / 'client.args'
    argfile.write_text('\n'.join(map(quote, args)) + '\n', encoding='utf-8')
    env = dict(os.environ, STUDIO_TRACE='1')
    with (evidence / 'console.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(jdk / 'bin/java.exe'), '@' + str(argfile)], cwd=game, env=env, stdout=log, stderr=subprocess.STDOUT)
        (evidence / 'launch.json').write_text(json.dumps({'pid': process.pid, 'gameDir': str(game), 'jarSha256': hashlib.sha256(jar.read_bytes()).hexdigest(), 'log': 'console.log', 'mods': sorted(p.name for p in (game / 'mods').glob('*.jar'))}, indent=2), encoding='utf-8')
        print(f'Production client PID {process.pid}', flush=True)
        return process.wait()


def prepare_material_world(world):
    pack = world / 'datapacks/mms_material_client'
    functions = pack / 'data/mms_material/function'
    tags = pack / 'data/minecraft/tags/function'
    functions.mkdir(parents=True, exist_ok=True)
    tags.mkdir(parents=True, exist_ok=True)
    (pack / 'pack.mcmeta').write_text(json.dumps({'pack': {'description': 'Isolated material render fixture', 'min_format': [107, 1], 'max_format': [107, 1]}}), encoding='utf-8')
    (tags / 'load.json').write_text(json.dumps({'values': ['mms_material:load']}), encoding='utf-8')
    (functions / 'load.mcfunction').write_text('schedule function mms_material:setup 8s replace\n', encoding='utf-8')
    (functions / 'setup.mcfunction').write_text('''execute if entity @a run function mms_material:scene
execute unless entity @a run schedule function mms_material:setup 3s replace
''', encoding='utf-8')
    (functions / 'scene.mcfunction').write_text('''time set midnight
weather clear
gamerule minecraft:spawn_mobs false
execute at @a run fill -3 175 -3 3 175 7 minecraft:polished_diorite
execute at @a run fill -3 176 5 3 179 6 minecraft:oxidized_copper_grate
tp @a 0.5 176 0.5 0 7
gamemode creative @a
clear @a
item replace entity @a hotbar.0 with stormshard_mod:charged_ingot
summon stormshard_mod:storm_guardian 0.5 176 3.5 {NoAI:1b,PersistenceRequired:1b,Rotation:[180f,0f]}
say MMS_MATERIAL_READY
''', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
