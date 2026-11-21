import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from mcp import Client, StdioServerParameters
from mcp.client import stdio
import psutil


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def alive(proc):
    return proc is not None and proc.is_running()


def child_with_arg(parent, argument):
    for child in parent.children():
        try:
            if argument in child.cmdline():
                return child
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return None


async def discover(fn, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        await asyncio.sleep(0.1)
    raise TimeoutError('could not identify owned child process or test world')


def identity(proc):
    return {'pid': proc.pid, 'created': proc.create_time(), 'exe': proc.exe()}


def connections(ports):
    return [dict(pid=row.pid, port=row.laddr.port, address=row.laddr.ip)
            for row in psutil.net_connections('tcp') if row.status == psutil.CONN_LISTEN and row.laddr.port in ports]


async def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    args.work.mkdir(parents=True, exist_ok=False)
    private_cache = args.work / 'runtime-cache'
    shutil.copytree(args.cache, private_cache, ignore=shutil.ignore_patterns('*.lock'))
    java = args.jdk / 'bin' / 'java.exe'
    commit = subprocess.check_output(['git', '-C', str(args.lab), 'rev-parse', 'HEAD'], text=True).strip()
    assert commit == '3d265d533a412b453cc0b835b66a05c6f10126ad', commit
    report = dict(commit=commit, started_utc=now(), windows=platform.platform(), python=sys.version,
        mcp=importlib.metadata.version('mcp'), java=subprocess.run([str(java), '-version'], capture_output=True,
        text=True, check=True).stderr.strip(), scenarios=[])
    driver = psutil.Process()
    result = args.out / 'result.json'

    def save():
        result.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

    async def scenario(name, override=None, client_grace=None):
        directory = args.out / name
        directory.mkdir()
        private_tmp = args.work / name
        private_tmp.mkdir()
        env = {'PATH': str(java.parent)+os.pathsep+os.environ['PATH'], 'JAVA_HOME': str(args.jdk),
               'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=4', 'PYTHONDONTWRITEBYTECODE':'1',
               'TEMP':str(private_tmp), 'TMP':str(private_tmp), 'TMPDIR':str(private_tmp)}
        product_command = [str(args.lab/'playtest.py'), 'serve', '--assets', str(args.assets), '--evidence', str(directory/'launcher'),
                           '--runtime-cache-dir', str(private_cache), '--accept-eula']
        command = product_command
        if override is not None:
            # The production code is unchanged. Override one class setting in this test process only.
            wrapper = ('import sys; sys.path.insert(0, sys.argv[1]); sys.argv=sys.argv[2:]; '
                       'from startup_status import StartupTracker; StartupTracker.timeout=6; '
                       'import runpy; runpy.run_path(sys.argv[0], run_name="__main__")')
            command = ['-B', '-c', wrapper, str(args.lab), *product_command]
        stock_grace=stdio.PROCESS_TERMINATION_TIMEOUT
        record = {'name':name, 'test_override_seconds':override, 'command':[sys.executable,*command], 'started_utc':now(),
                  'mcp_client_close_grace_seconds':client_grace if client_grace else stock_grace}
        report['scenarios'].append(record)
        save()
        launcher = jvm = world = None
        ports = set()
        with (directory/'mcp.jsonl').open('w', encoding='utf-8', newline='\n') as log:
            async def call(client, name, arguments=None):
                response = await client.call_tool(name, arguments or {})
                log.write(json.dumps(dict(utc=now(), tool=name, arguments=arguments or {},
                                     response=response.model_dump(mode='json', by_alias=True)))+'\n')
                log.flush()
                return response

            async def state(client, expected, seconds):
                end = time.monotonic()+seconds
                while time.monotonic() < end:
                    answer = await call(client,'playtest_status')
                    assert not answer.is_error
                    evidence = answer.structured_content['evidence']
                    if evidence['status']==expected:
                        return evidence
                    assert evidence['status']!='stopped', evidence
                    await asyncio.sleep(0.5)
                raise TimeoutError(f'MCP did not observe {expected}')

            try:
                if client_grace:
                    stdio.PROCESS_TERMINATION_TIMEOUT=client_grace
                async with Client(StdioServerParameters(command=sys.executable,args=command,env=env,cwd=args.lab),
                                  read_timeout_seconds=25) as client:
                    launcher = await discover(lambda:child_with_arg(driver,str(directory/'launcher')))
                    jvm = await discover(lambda:child_with_arg(launcher,'fabric-server.jar'))
                    assert Path(jvm.exe()).samefile(java) and jvm.ppid()==launcher.pid
                    world = await discover(lambda:next((path for path in private_tmp.glob('mms-ai-world-*')
                                                        if (path/'server.properties').is_file()),None))
                    assert world.resolve().parent==private_tmp and not world.is_junction() and not world.is_symlink()
                    properties = dict(line.split('=',1) for line in (world/'server.properties').read_text().splitlines() if '=' in line)
                    ports = {int(properties[k]) for k in ('server-port','rcon.port')}
                    record.update(launcher=identity(launcher), jvm=identity(jvm), world_root=str(world), ports=sorted(ports))
                    save()
                    if override:
                        observed = await state(client,'startup_timeout',35)
                        assert observed['startup']['timeout_s']==override and observed['startup']['elapsed_s']>=override
                        assert observed['startup']['ready_elapsed_s'] is None and alive(jvm)
                        record.update(timeout=observed, jvm_alive_after_timeout=True)
                        denied=await call(client,'playtest_set_block',{'block':'minecraft:chest'})
                        assert denied.is_error
                        record['early_write_denied']=True
                    else:
                        observed = await state(client,'ready',120)
                        assert observed['startup']['timeout_s']==600 and (world/'world'/'level.dat').is_file()
                        record.update(ready=observed, listeners_before_crash=connections(ports))
                        assert jvm.ppid()==launcher.pid and jvm.create_time()==record['jvm']['created']
                        jvm.kill()
                        exit_code = jvm.wait(timeout=10)
                        assert exit_code!=0
                        stopped = await state(client,'stopped',20)
                        assert world.exists() and not connections(ports)
                        record.update(injected_jvm_exit_code=exit_code, state_after_jvm_exit=stopped,
                                      world_present_while_mcp_connected=True, listeners_after_crash=[])
                record.update(jvm_alive_after_disconnect=alive(jvm), launcher_alive_after_disconnect=alive(launcher),
                              world_present_after_disconnect=world.exists(), listeners_after_disconnect=connections(ports))
                record['clean_disconnect']=not any(record[k] for k in ('jvm_alive_after_disconnect',
                    'launcher_alive_after_disconnect','world_present_after_disconnect','listeners_after_disconnect'))
                if not record['clean_disconnect']:
                    await asyncio.sleep(4)
                    record['post_disconnect_observation_4s']={'jvm_alive':alive(jvm),'launcher_alive':alive(launcher),
                        'world_present':world.exists(),'listeners':connections(ports)}
                evidence_dir = directory / 'launcher'
                cache_files = list(evidence_dir.glob('playtest-*/cache.json'))
                assert len(cache_files)==1
                record['cache']=json.loads(cache_files[0].read_text(encoding='utf-8'))
                assert record['cache']['restore']['status']=='hit'
                if not override:
                    assert record['cache']['publish']['status']=='not_needed'
                record['passed']=True
            finally:
                stdio.PROCESS_TERMINATION_TIMEOUT=stock_grace
                for key,proc in [('jvm',jvm),('launcher',launcher)]:
                    if alive(proc) and proc.create_time()==record.get(key,{}).get('created'):
                        proc.kill()
                        proc.wait(timeout=10)
                        record.setdefault('fallback_killed',[]).append(key)
                if world and world.exists():
                    assert world.resolve().parent==private_tmp and not world.is_junction() and not world.is_symlink()
                    shutil.rmtree(world)
                    record['harness_removed_residual_world']=not world.exists()
                record['finished_utc']=now()
                save()
        return record

    try:
        timed_out = await scenario('short-deadline-stock-client',6)
        recovered = await scenario('stock-deadline-retry-with-jvm-crash')
        control = await scenario('short-deadline-extended-client-grace',6,40.0)
        assert timed_out['world_root']!=recovered['world_root'] and timed_out['jvm']!=recovered['jvm']
        assert recovered['clean_disconnect'] and control['clean_disconnect']
        report['passed']=timed_out['clean_disconnect']
    except Exception as exc:
        report['passed']=False
        report['error']=repr(exc)
        raise
    finally:
        report['finished_utc']=now()
        save()
        files=sorted(p for p in args.out.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
        (args.out/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(args.out).as_posix()}\n'
                                                       for p in files),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'result':str(result)}),flush=True)

parser=argparse.ArgumentParser()
for argument in ('out','work','cache','assets','lab','jdk'):
    parser.add_argument('--'+argument, required=True, type=lambda x:Path(x).resolve())
asyncio.run(run(parser.parse_args()))

