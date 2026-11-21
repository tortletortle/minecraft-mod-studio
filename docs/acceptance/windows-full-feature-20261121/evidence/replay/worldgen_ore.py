from __future__ import annotations

import argparse
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from zipfile import ZipFile
import zlib

import runtime_generated as base

sys.path.insert(0, str(Path(__file__).with_name('nbt-deps')))
import nbtlib

BLOCK = 'crystal_lab:storm_crystal_ore'
SEED = 42
CHUNKS = [(x,z) for z in range(3) for x in range(3)]


def inspect_chunks(region, out):
    ore_positions = []
    chunk_counts = []
    with region.open('rb') as reader:
        header = reader.read(4096)
        for cx, cz in CHUNKS:
            index = (cz % 32) * 32 + cx % 32
            sector = int.from_bytes(header[4*index:4*index+3], 'big')
            assert sector >= 2, ('chunk missing from saved region', cx, cz)
            reader.seek(sector * 4096)
            total, compression = struct.unpack('>IB', reader.read(5))
            packed = reader.read(total-1)
            assert compression == 2 and len(packed) == total-1, (cx, cz, compression, total)
            (out/f'chunk.{cx}.{cz}.nbt.zlib').write_bytes(packed)
            chunk = nbtlib.File.parse(io.BytesIO(zlib.decompress(packed)))
            assert (int(chunk['xPos']), int(chunk['zPos'])) == (cx, cz)
            status = str(chunk['Status'])
            assert status == 'minecraft:full', (cx, cz, status)
            positions = []
            stone_blocks = 0
            for section in chunk['sections']:
                states = section.get('block_states', {})
                names = [str(row['Name']) for row in states.get('palette', [])]
                if not names:
                    continue
                needed = {i for i, name in enumerate(names) if name in {BLOCK,'minecraft:stone','minecraft:deepslate'}}
                if not needed:
                    continue
                bits = max(4, (len(names)-1).bit_length())
                data = states.get('data')
                if len(names) > 1:
                    assert data is not None and len(data) == (4096 + (64//bits) - 1)//(64//bits), (cx,cz,len(names))
                for n in range(4096):
                    entry = 0 if len(names)==1 else (int(data[n // (64//bits)]) >> (bits*(n % (64//bits)))) & ((1<<bits)-1)
                    if entry not in needed:
                        continue
                    if names[entry] != BLOCK:
                        stone_blocks += 1
                        continue
                    positions.append([16*cx+n%16, 16*int(section['Y'])+n//256, 16*cz+(n//16)%16])
            assert stone_blocks > 0, ('chunk missing stone/deepslate control', cx, cz)
            ore_positions.extend(positions)
            chunk_counts.append({'chunk':[cx,cz], 'status':status, 'ore_blocks':len(positions), 'stone_or_deepslate_blocks':stone_blocks})
    return ore_positions, chunk_counts


def wait_log(log, proc, token, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert proc.poll() is None, f'Java exited waiting for {token}'
        if token in log.read_text(encoding='utf-8', errors='replace'):
            return
        time.sleep(.5)
    raise TimeoutError(f'Server log did not contain {token!r}')


def run(jar, out, evidence):
    sys.path.insert(0, str(base.REPO/'ai-debug-lab'))
    from live_smoke import free_port
    from runtime_cache import RuntimeCache
    evidence['seed'] = SEED
    evidence['level_type'] = 'minecraft:normal'
    evidence['jar_sha256'] = base.sha256(jar)
    evidence['decoder'] = 'nbtlib ' + version('nbtlib')
    evidence['java_version'] = subprocess.check_output([str(base.JAVA),'-version'],stderr=subprocess.STDOUT,text=True)
    evidence['test_chunks'] = CHUNKS
    worldgen = '/worldgen/'
    with ZipFile(jar) as archive:
        for path in ['placed_feature','configured_feature']:
            data = json.loads(archive.read('data/crystal_lab' + worldgen + path + '/storm_crystal_ore.json'))
            base.dump(out/(path+'.json'), data)
            evidence[path] = data
    placer = evidence['placed_feature']['placement']
    assert placer[0] == {'type':'minecraft:count','count':6}
    assert placer[2]['height']['min_inclusive']['absolute'] == -48
    assert placer[2]['height']['max_inclusive']['absolute'] == 32
    assert evidence['configured_feature']['config']['size'] == 8
    log = out/'server.log'
    transcript = out/'console-commands.txt'
    with tempfile.TemporaryDirectory(prefix='ore-private-', dir=out) as run_dir:
        root = Path(run_dir)/'instance'
        root.mkdir()
        cache = Path(run_dir)/'cache'
        cache.mkdir()
        private_temp = Path(run_dir)/'tmp'
        private_temp.mkdir()
        cache_obj = RuntimeCache(base.ASSETS, cache)
        shutil.copytree(base.CACHE/cache_obj.key, cache/cache_obj.key)
        evidence['cache'] = cache_obj.restore(root)
        assert evidence['cache']['status'] == 'hit', evidence['cache']
        for name in ('fabric-server.jar','server.jar'):
            shutil.copyfile(base.ASSETS/name, root/name)
        mods = root/'mods'
        mods.mkdir()
        shutil.copyfile(base.ASSETS/'fabric-api.jar', mods/'fabric-api.jar')
        shutil.copyfile(jar, mods/'crystal_lab.jar')
        settings = f'''level-seed={SEED}
level-type=minecraft:normal
level-name=ore-test
server-ip=127.0.0.1
server-port={free_port()}
view-distance=3
simulation-distance=3
online-mode=true
pause-when-empty-seconds=-1
'''
        (root/'server.properties').write_text(settings,encoding='utf-8')
        (root/'eula.txt').write_text('eula=true\n', encoding='utf-8')
        (out/'tested-settings.txt').write_text(settings,encoding='utf-8')
        env = os.environ.copy()
        env.update({key:str(private_temp) for key in ('TEMP','TMP','TMPDIR')})
        argv = [str(base.JAVA),'-Xms512M','-Xmx2G','-XX:ActiveProcessorCount=4','-jar','fabric-server.jar','nogui']
        with log.open('wb') as logfile, transcript.open('w', encoding='utf-8') as commands:
            start = time.monotonic()
            process = subprocess.Popen(argv,cwd=root,env=env,stdin=subprocess.PIPE,stdout=logfile,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            evidence['java_pid'] = process.pid
            def issue(command):
                commands.write('%.3f %s\n' % (time.monotonic()-start,command))
                commands.flush()
                base.send_console(process,command)
            try:
                wait_log(log, process, 'Done (', 120)
                evidence['ready_s'] = round(time.monotonic()-start,3)
                wait_log(log, process, 'STUDIO_INIT_V1 crystal_lab', 5)
                issue('execute in minecraft:overworld run forceload add 0 0 47 47')
                issue('seed')
                wait_log(log, process, 'Seed: [42]', 10)
                condition = ''.join(f' if loaded {cx*16} 64 {cz*16}' for cx,cz in CHUNKS)
                for _ in range(15):
                    issue('execute in minecraft:overworld' + condition + ' run say MMS_ORE_CHUNKS_READY')
                    try:
                        wait_log(log,process,'MMS_ORE_CHUNKS_READY',3)
                    except TimeoutError:
                        continue
                    break
                else:
                    raise TimeoutError('Failed to load all nine target chunks')
                issue('save-all flush')
                wait_log(log,process,'Saved the game',50)
                region = next(p for p in (root/'ore-test').rglob('r.0.0.mca') if p.parent.name=='region' and 'minecraft:the_nether' not in p.parts)
                evidence['region_relpath'] = region.relative_to(root).as_posix()
                evidence['region_sha256'] = base.sha256(region)
                positions, counts = inspect_chunks(region,out)
                evidence['positions'] = positions
                evidence['chunks'] = counts
                evidence['ore_count'] = len(positions)
                assert positions, 'No natural ore in nine fully generated chunks'
                evidence['observed_y_range'] = [min(p[1] for p in positions),max(p[1] for p in positions)]
                witnesses = []
                for i, row in enumerate(counts):
                    cx, cz = row['chunk']
                    if row['ore_blocks'] <= 0:
                        continue
                    x,y,z = next(p for p in positions if p[0]//16 == cx and p[2]//16 == cz)
                    marker = f'MMS_ORE_PRESENT_{i}'
                    issue(f'execute in minecraft:overworld if block {x} {y} {z} {BLOCK} run say {marker}')
                    wait_log(log, process, marker, 8)
                    witnesses.append({'pos':[x,y,z], 'marker':marker})
                evidence['live_witnesses'] = witnesses
            finally:
                commands.write('%.3f stop\n' % (time.monotonic()-start))
                evidence['server_exit'] = base.stop_server(process)
                for path in (root/'crash-reports').glob('*.txt'):
                    shutil.copyfile(path,out/path.name)
    evidence['temporary_instance_removed'] = not Path(run_dir).exists()
    assert evidence['server_exit'] == {'method':'console_stop','exit_code':0}
    assert evidence['temporary_instance_removed']


def main():
    parser = argparse.ArgumentParser(description='Generate nine fresh Minecraft 26.2 chunks and count generated ore.')
    parser.add_argument('--accept-eula', action='store_true', required=True)
    parser.add_argument('--out',type=Path, required=True)
    parser.add_argument('--jar',type=Path,required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True,exist_ok=False)
    evidence = {'status':'FAIL'}
    try:
        run(args.jar.resolve(), out, evidence)
        evidence['status'] = 'NATURAL_ORE_GENERATION_PASS'
    except Exception as error:
        evidence['error'] = str(error)
        (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        base.dump(out/'result.json', evidence)
        base.dump(out/'sha256.json', {path.name: base.sha256(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != 'sha256.json'})
    print(json.dumps({key:value for key,value in evidence.items() if key not in {'positions','cache'}},indent=2))
    return int(evidence['status'] == 'FAIL')


if __name__ == '__main__':
    raise SystemExit(main())
