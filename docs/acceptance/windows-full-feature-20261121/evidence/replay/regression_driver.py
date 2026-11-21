import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid

from mcp import Client, StdioServerParameters
import psutil


with_cli = '--with-cli' in sys.argv[7:]
out, lab, assets, source_cache, jdk, scratch = [Path(arg).resolve() for arg in sys.argv[1:7]]
out.mkdir(parents=True, exist_ok=False)
scratch.mkdir(parents=True, exist_ok=False)
private = scratch / 'windows-temp'
private.mkdir()
cache = scratch / 'runtime-cache'
shutil.copytree(source_cache, cache, ignore=shutil.ignore_patterns('*.lock'))
java_path = jdk / 'bin' / 'java.exe'
expected_commit = '3d265d533a412b453cc0b835b66a05c6f10126ad'
commit = subprocess.check_output(['git','-C',str(lab),'rev-parse','HEAD'], text=True).strip()
assert commit == expected_commit, commit

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

started = time.monotonic()
report = dict(source_commit=commit, python=sys.version, windows=platform.platform(),
              mcp=importlib.metadata.version('mcp'),
              java=subprocess.run([str(java_path), '-version'], capture_output=True, text=True, check=True).stderr.strip(),
              start_utc=utc(), checks={})

def persist():
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

def check(label, condition, observed=None):
    report['checks'][label] = dict(passed=bool(condition), observed=observed)
    persist()
    if not condition:
        raise AssertionError(f'{label}: {observed!r}')

def identity(proc):
    return {'pid':proc.pid, 'created':proc.create_time(), 'exe':proc.exe()}

def matching_child(parent, needle):
    for child in parent.children():
        try:
            if needle in child.cmdline():
                return child
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def owned_alive(proc, ident):
    try:
        return bool(proc and ident and proc.is_running() and proc.create_time()==ident['created'])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

async def wait_for(fn, timeout, description):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result := fn():
            return result
        await asyncio.sleep(0.25)
    raise TimeoutError(description)

env = {'PATH': str(java_path.parent)+os.pathsep+os.environ['PATH'], 'JAVA_HOME': str(jdk),
       'TEMP': str(private), 'TMP':str(private), 'TMPDIR':str(private),
       'PYTHONDONTWRITEBYTECODE':'1', 'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=4'}
serve_args = [str(lab/'playtest.py'),'serve','--assets',str(assets),'--evidence',str(out/'launcher'),
              '--runtime-cache-dir',str(cache),'--accept-eula']
report['command'] = [sys.executable, *serve_args]
report['jvm_options'] = env['JAVA_TOOL_OPTIONS']
report['asset_hashes'] = json.loads((assets/'hashes.json').read_text(encoding='utf-8'))

async def run():
    driver = psutil.Process()
    launcher = jvm = world = None
    ports = set()
    transcript = out/'mcp-transcript.jsonl'
    passed = False
    with transcript.open('w', encoding='utf-8', newline='\n') as records:
        def record(**message):
            records.write(json.dumps(message, ensure_ascii=True)+'\n')
            records.flush()

        async def call(client, tool, args=None, *, want_error=False, expected_text=None, service='playtest'):
            args = args or {}
            began = utc()
            mark = time.monotonic()
            response = await client.call_tool(tool, args)
            record(service=service, tool=tool, arguments=args, start_utc=began, finish_utc=utc(),
                   elapsed_s=round(time.monotonic()-mark,3), response=response.model_dump(mode='json', by_alias=True))
            if bool(response.is_error) != want_error:
                raise AssertionError(f'{tool} returned unexpected MCP error flag: {response.content!r}')
            if expected_text and expected_text not in str(response.content):
                raise AssertionError(f'{tool} omitted expected error: {response.content!r}')
            if want_error:
                return ' '.join(getattr(item,'text','') for item in response.content)
            return response.structured_content['evidence']

        try:
            async with Client(StdioServerParameters(command=sys.executable,args=serve_args,env=env,cwd=lab),
                              read_timeout_seconds=45) as client:
                tools_response = await client.list_tools()
                record(service='playtest', tool='tools/list', response=tools_response.model_dump(mode='json',by_alias=True))
                names = {t.name for t in tools_response.tools}
                check('playtest_tool_discovery', names=={'mods_inventory','game_native_snapshot','game_recipe_status',
                      'mods_diagnose_recipe','trials_summarize','game_tick_observe','playtest_status',
                      'playtest_set_block','playtest_tick_steps'}, sorted(names))
                launcher = await wait_for(lambda:matching_child(driver,str(lab/'playtest.py')),25,'MCP launcher')
                jvm = await wait_for(lambda:matching_child(launcher,'fabric-server.jar'),25,'Minecraft JVM')
                report.update(launcher=identity(launcher),jvm=identity(jvm))
                world = await wait_for(lambda:next((p for p in private.glob('mms-ai-world-*')
                                                     if (p/'server.properties').is_file()),None),25,'private world')
                check('owned_jvm_private_world',Path(jvm.exe()).samefile(java_path) and jvm.ppid()==launcher.pid
                      and world.resolve().parent==private and not world.is_junction(), str(world))
                properties = dict(line.split('=',1) for line in (world/'server.properties').read_text().splitlines() if '=' in line)
                ports = {int(properties[k]) for k in ('server-port','rcon.port')}
                report.update(world_root=str(world), ports=sorted(ports))
                check('loopback_game_port_configuration',properties['server-ip']=='127.0.0.1' and len(ports)==2)
                deadline = time.monotonic()+650
                while True:
                    state = await call(client,'playtest_status')
                    if state['status']=='ready':
                        break
                    if state['status'] not in {'starting','waiting_for_probe'} or time.monotonic()>=deadline:
                        raise RuntimeError(f'Unready temporary server: {state!r}')
                    await asyncio.sleep(1)
                sid = state['session']
                report.update(startup=state['startup'],session=sid,driver_to_ready_s=round(time.monotonic()-started,3))
                check('real_temporary_world_ready', (world/'world'/'level.dat').is_file() and str(uuid.UUID(sid))==sid)
                inventory = await call(client,'mods_inventory')
                ids = sorted(jar['id'] for jar in inventory['data']['jars'] if jar.get('id'))
                check('fixture_and_probe_inventory', 'mms_playtest' in ids and len(ids)==3, ids)
                recipe = (await call(client,'game_recipe_status',{'session':sid}))['data']
                check('real_recipe_assembly',recipe['recipe']['id']=='mms_playtest:gem'
                      and recipe['recipe']['experiment'].get('status')=='matched'
                      and recipe['recipe']['experiment'].get('output')=='minecraft:emerald', recipe['recipe'])
                diagnosis = (await call(client,'mods_diagnose_recipe',{'session':sid,'recipe':'mms_playtest:gem'}))['data']
                check('recipe_cross_check', diagnosis['in_memory_experiment']['output']=='minecraft:emerald'
                      and set(diagnosis['plan']['covered_by_configured_snapshot'])=={'query_active_recipe','query_active_tag_members'}
                      and 'tag_resolution_unknown' not in {h['kind'] for h in diagnosis['hypotheses']}, diagnosis['plan'])
                baseline = (await call(client,'game_native_snapshot',{'session':sid}))['data']
                check('live_probe_snapshot',baseline['session']==sid and baseline['schema']==1 and bool(baseline.get('at')))

                async def run_diagnostic(name, args, input_bytes=None, *, rcon=False, timeout=25):
                    child_env={**os.environ, **env}
                    if rcon:
                        child_env['MC_DEBUG_RCON_PASSWORD']=properties['rcon.password']
                    proc=await asyncio.create_subprocess_exec(sys.executable,'-B',str(lab/name),*map(str,args),
                        cwd=lab, env=child_env, stdin=asyncio.subprocess.PIPE if input_bytes else asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    try:
                        stdout,stderr=await asyncio.wait_for(proc.communicate(input_bytes), timeout)
                    except BaseException:
                        if proc.returncode is None:
                            proc.kill()
                            await proc.wait()
                        raise
                    (out/(name+'.stdout')).write_bytes(stdout)
                    (out/(name+'.stderr')).write_bytes(stderr)
                    if proc.returncode:
                        raise RuntimeError(f'{name} launched with exit code {proc.returncode}')
                    return stdout

                trace_task=None
                if with_cli:
                    trace_task=asyncio.create_task(run_diagnostic('native_trace.py',
                        ['--workspace',world,'--session',sid,'--seconds',22,'--interval',0.5],timeout=30))
                    await asyncio.sleep(1.5)

                observed_blocks=[]
                for block in ('minecraft:chest','minecraft:stone'):
                    placed = await call(client,'playtest_set_block',{'block':block})
                    check('rcon_verified_'+block, placed['status']=='verified' and placed['operation']['pos']==[0,80,0], placed)
                    deadline=time.monotonic()+20
                    while True:
                        snap=(await call(client,'game_native_snapshot',{'session':sid}))['data']
                        b=snap['block']
                        matching=b.get('id')==block and (b['x'],b['y'],b['z'])==(0,80,0)
                        if matching and snap['at']!=baseline['at']:
                            break
                        if time.monotonic()>=deadline:
                            raise TimeoutError(f'probe never reported {block}: {b}')
                        await asyncio.sleep(.65)
                    observed_blocks.append(dict(block=b, at=snap['at']))
                    baseline=snap
                    if with_cli and block=='minecraft:chest':
                        location={'dimension':'minecraft:overworld','pos':[0,80,0]}
                        operations=[{'op':'players'},{'op':'ticks'},{'op':'gametime'},
                                    {'op':'block_nbt',**location},{'op':'block_matches',**location,'block':'minecraft:chest'},
                                    {'op':'entity_nbt','dimension':'minecraft:overworld','uuid':str(uuid.uuid4())}]
                        messages=[dict(id=1,method='tools.list',params={}),
                            dict(id=2,method='tools.call',params={'name':'game.observe','arguments':{'operations':operations}})]
                        encoded=''.join(json.dumps(m)+'\n' for m in messages).encode()
                        replies=[json.loads(line) for line in (await run_diagnostic('ide_bridge.py',
                                 ['--workspace',world,'--port',properties['rcon.port']],encoded,rcon=True)).splitlines()]
                        (out/'ide-bridge-input.json').write_text(json.dumps(messages,indent=2)+'\n',encoding='utf-8')
                        measurements=replies[1]['result']['data']['measurements']
                        observed={m['operation']['op']:m.get('raw_response','') for m in measurements}
                        check('real_readonly_ide_jsonl',replies[0]['result']['protocol']=='mms-ide-jsonl/1'
                              and replies[0]['result']['capabilities']==dict(rcon_configured=True,read_only=True,write=False)
                              and len(measurements)==6 and all(m['transport']=='received' for m in measurements)
                              and all(value in observed[op].lower() for op,value in
                                      [('players','players online'),('ticks','game is running'),('gametime','game time is'),
                                       ('block_nbt','minecraft:chest'),('block_matches','test passed'),('entity_nbt','no entity')]),
                              observed)
                check('probe_observed_two_world_writes', len(observed_blocks)==2, observed_blocks)
                if with_cli:
                    trace=json.loads(await trace_task)
                    check('live_native_timeline_cli',any(event['type']=='observed_block_changed'
                          and event['before']['id']=='minecraft:chest' and event['after']['id']=='minecraft:stone'
                          for event in trace['events']), trace['events'])
                    knowledge=json.loads(await run_diagnostic('mod_knowledge.py',[world/'mods']))
                    check('live_mod_directory_knowledge_cli',any(row['id']=='mms_playtest:gem' for row in knowledge['resources'])
                          and {'minecraft:stone','minecraft:planks','minecraft:emerald'} <= {e['target'] for e in knowledge['edges']},
                          {'archives':len(knowledge['archives']),'resources':len(knowledge['resources']),'edges':len(knowledge['edges'])})
                for steps in ([1],[2,5]):
                    value=await call(client,'playtest_tick_steps',{'steps':steps})
                    deltas=[event['delta'] for event in value['events'] if event['kind']=='step_verified']
                    check(f'exact_tick_steps_{steps}',value['status']=='passed' and deltas==steps
                          and value['cleanup']=='verified_running', {'deltas':deltas,'cleanup':value['cleanup']})
                timing=await call(client,'game_tick_observe',{'operations':['ticks','gametime'],'repeat':2})
                check('rcon_tick_read_after_resume','the game is running' in json.dumps(timing).lower(), timing)
                rows=json.loads((lab/'example-trials.json').read_text(encoding='utf-8'))
                totals=await call(client,'trials_summarize',{'trials':rows})
                check('descriptive_trials',totals['conditions']['synthetic_demo']['label']=='intermittent'
                      and totals['conditions']['synthetic_demo']['valid']==3,totals)
                await call(client,'playtest_set_block',{'block':'minecraft:dirt'},want_error=True)
                await call(client,'playtest_tick_steps',{'steps':[100,100,1]},want_error=True,expected_text='total at most 200')
                await call(client,'game_tick_observe',{'operations':['players']},want_error=True)
                await call(client,'game_native_snapshot',{'session':str(uuid.uuid4())},want_error=True,
                           expected_text='Diagnostic failed or evidence unavailable.')
                check('invalid_arguments_and_session_rejected',True)

                log_args=[str(lab/'mcp_adapter.py'),'--workspace',str(world),'--allow-logs']
                async with Client(StdioServerParameters(command=sys.executable,args=log_args,env=env,cwd=lab),
                                  read_timeout_seconds=20) as read_client:
                    read_tools=await read_client.list_tools()
                    record(service='diagnostic_adapter',tool='tools/list',response=read_tools.model_dump(mode='json',by_alias=True))
                    read_names={t.name for t in read_tools.tools}
                    check('independent_readonly_adapter_capabilities', 'logs_tail' in read_names
                          and 'game_tick_observe' not in read_names and not any(n.startswith('playtest_') for n in read_names),
                          sorted(read_names))
                    log_evidence=await call(read_client,'logs_tail',service='diagnostic_adapter')
                    check('optional_real_logs_tail', log_evidence['trust']=='untrusted_log_data'
                          and 'Loading Minecraft 26.2' in log_evidence['text'],
                          {'truncated':log_evidence['truncated'],'utf8_bytes':len(log_evidence['text'].encode())})
                count=4
                for index in range(20):
                    block=('minecraft:chest','minecraft:air')[index%2]
                    value=await call(client,'playtest_set_block',{'block':block})
                    if value['status']!='verified':
                        raise AssertionError(f'budget fill action {count+1} not verified: {value!r}')
                    count+=1
                budget_block_error=await call(client,'playtest_set_block',{'block':'minecraft:stone'},want_error=True)
                budget_tick_error=await call(client,'playtest_tick_steps',{'steps':[1]},want_error=True)
                report['budget_feedback']={'message_expected':'playtest action budget exhausted',
                     'actual_block':budget_block_error,'actual_tick':budget_tick_error,
                     'explicit_cause_disclosed':all('playtest action budget exhausted' in message
                                                     for message in (budget_block_error,budget_tick_error))}
                after=await call(client,'playtest_status')
                read_after=await call(client,'game_tick_observe',{'operations':['ticks']})
                actions_path=Path(state['evidence_dir'])/'actions.jsonl'
                actions=[json.loads(line) for line in actions_path.read_text(encoding='utf-8').splitlines()]
                check('24_shared_write_budget_then_readonly_still_operates', count==24 and after['status']=='ready'
                      and 'the game is running' in json.dumps(read_after).lower()
                      and [action['sequence'] for action in actions]==list(range(1,25)), dict(action_types=Counter(a['action'] for a in actions),
                      accepted_count=count, denied=['playtest_set_block','playtest_tick_steps']))
            product_logs=list((out/'launcher').glob('playtest-*/server.log'))
            check('verified_launcher_evidence',len(product_logs)==1)
            cache_data=json.loads(product_logs[0].with_name('cache.json').read_text(encoding='utf-8'))
            report['cache']=cache_data
            log_text=product_logs[0].read_text(encoding='utf-8',errors='replace')
            check('real_fabric_start_stop',all(x in log_text for x in ('Loading Minecraft 26.2 with Fabric Loader 0.20.1',
                 'Done (','Stopping server')) and 'No key layers in MapLike' not in log_text)
            check('warm_private_cache_restore',cache_data['restore']['status']=='hit' and cache_data['publish']['status']=='not_needed')
            listeners=[{'pid':c.pid,'port':c.laddr.port} for c in psutil.net_connections('tcp')
                       if c.status==psutil.CONN_LISTEN and c.laddr.port in ports]
            cleanup=dict(launcher_alive=owned_alive(launcher,report.get('launcher')),jvm_alive=owned_alive(jvm,report.get('jvm')),
                         world_exists=world.exists(),listeners=listeners)
            check('normal_disconnect_reaps_jvm_world_and_listeners',not any(cleanup.values()),cleanup)
            passed=report['budget_feedback']['explicit_cause_disclosed']
        except Exception as exc:
            report['failure']=dict(type=type(exc).__name__,message=str(exc))
            raise
        finally:
            # Product normally closes on stdio EOF. Fall back only for the exact captured children.
            for name,proc in [('jvm',jvm),('launcher',launcher)]:
                if owned_alive(proc,report.get(name)):
                    report.setdefault('fallback_killed',[]).append(name)
                    proc.kill()
                    proc.wait(timeout=10)
            report.update(passed=passed,finish_utc=utc())
            persist()
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
    (out/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out).as_posix()}\n'
                                                 for p in files),encoding='utf-8')
    print(json.dumps({'passed':passed,'check_count':len(report['checks']),'startup_s':report.get('startup',{}).get('ready_elapsed_s'),
                      'result':str(out/'result.json')}),flush=True)
    return 0 if passed else 1


sys.exit(asyncio.run(run()))

