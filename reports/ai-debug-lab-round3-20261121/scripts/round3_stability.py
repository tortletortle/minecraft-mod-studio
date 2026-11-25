"""Real-process timeout/recovery and cleanup test for the stock playtest launcher."""
import argparse, asyncio, importlib.metadata, json, os, platform, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
import psutil
from mcp import Client, StdioServerParameters

def utc(): return datetime.now(timezone.utc).isoformat()
def write(path, obj):
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8'); tmp.replace(path)
def info(p): return {'pid':p.pid,'create_time':p.create_time(),'exe':p.exe()}
def alive(p):
    try: return p is not None and p.is_running() and p.status()!=psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess,psutil.AccessDenied): return False
def owned_child(parent, pred):
    for p in parent.children():
        try:
            if pred(p): p.create_time(); return p
        except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    return None
def ports_in(world):
    values={}
    for line in (world/'server.properties').read_text().splitlines():
        k,_,v=line.partition('=')
        if k in ('server-port','rcon.port'): values[k]=int(v)
    if len(values)!=2: raise RuntimeError('temporary server port config missing')
    return values
def listeners(ports):
    return [{'pid':c.pid,'port':c.laddr.port} for c in psutil.net_connections('tcp')
            if c.status==psutil.CONN_LISTEN and c.laddr.port in ports.values()]
async def wait_for(fn, seconds, label):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=fn()
        if value: return value
        await asyncio.sleep(.1)
    raise TimeoutError(label)

async def run(a):
    a.out.mkdir(parents=True,exist_ok=False)
    java_bin=a.jdk/'bin'/('java.exe' if os.name=='nt' else 'java')
    if not java_bin.is_file(): raise RuntimeError('Java 25 not found at '+str(java_bin))
    env={'PATH':str(java_bin.parent)+os.pathsep+os.environ['PATH'],'JAVA_HOME':str(a.jdk),
         'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=4','PYTHONDONTWRITEBYTECODE':'1'}
    args=[str(a.lab/'playtest.py'),'serve','--assets',str(a.assets),'--evidence',str(a.out/'launcher'),'--accept-eula']
    version=subprocess.run([str(java_bin),'-version'],capture_output=True,text=True,timeout=20,check=True).stderr
    driver=psutil.Process(); launcher=java=world=None; ports=None; is_suspended=False
    report={'case':a.case,'begin_utc':utc(),'driver':info(driver),'python':sys.version,
      'os':platform.platform(),'mcp_version':importlib.metadata.version('mcp'),'psutil_version':psutil.__version__,
      'java_version':version.strip(),'java_path':str(java_bin),'command':[sys.executable,*args],
      'asset_hashes':json.loads((a.assets/'hashes.json').read_text()),
      'jvm_options':env['JAVA_TOOL_OPTIONS'],'events':[]}
    result=a.out/'result.json'
    def mark(name,**data):
        event={'event':name,'utc':utc(),**data}; report['events'].append(event); write(result,report); print(json.dumps(event),flush=True)
    async def poll(client,log):
        start=utc(); response=(await client.call_tool('playtest_status',{})).model_dump(mode='json',by_alias=True)
        log.write(json.dumps({'started_utc':start,'finished_utc':utc(),'tool':'playtest_status','response':response})+'\n'); log.flush()
        if response.get('isError'): raise RuntimeError('playtest_status returned an MCP error')
        report['poll_count']=report.get('poll_count',0)+1
        return response['structuredContent']['evidence']
    async def until(client,log,want,deadline,cadence=1):
        while time.monotonic()<deadline:
            item=await poll(client,log)
            if item['status']==want:return item
            if item['status']=='stopped' and want!='stopped':raise RuntimeError('server stopped before '+want)
            await asyncio.sleep(cadence)
        raise TimeoutError('waiting for '+want)
    try:
      with tempfile.TemporaryDirectory(prefix='mms-r3-private-') as tmp:
        tmp=Path(tmp).resolve(); env.update(TEMP=str(tmp),TMP=str(tmp),TMPDIR=str(tmp))
        server=StdioServerParameters(command=sys.executable,args=args,env=env,cwd=a.lab)
        with (a.out/'mcp.jsonl').open('w',encoding='utf-8',newline='\n') as log:
          async with Client(server,read_timeout_seconds=25) as client:
            launcher=await wait_for(lambda:owned_child(driver,lambda p: str(a.lab/'playtest.py') in p.cmdline() and str(a.out/'launcher') in p.cmdline()),20,'owned MCP server process')
            java=await wait_for(lambda:owned_child(launcher,lambda p:Path(p.exe()).samefile(java_bin) and 'fabric-server.jar' in p.cmdline() and '-Dmms.debug.enabled=true' in p.cmdline()),20,'owned Java process')
            world=await wait_for(lambda:next((p for p in tmp.glob('mms-ai-world-*') if (p/'server.properties').is_file()),None),20,'private disposable world')
            if world.resolve().parent!=tmp or world.is_symlink() or world.is_junction():raise RuntimeError('world escaped private temporary root')
            ports=ports_in(world)
            report.update(launcher=info(launcher),java=info(java),world=str(world),ports=ports,private_temp=str(tmp))
            mark('owned_processes_verified')
            if a.case=='timeout-recovery':
                # Pause only the exact, freshly spawned JVM child while the real 600s deadline advances.
                if not alive(java) or java.ppid()!=launcher.pid:raise RuntimeError('JVM ownership changed before suspend')
                java.suspend(); is_suspended=True; suspended_at=time.monotonic()
                mark('owned_jvm_suspended',pid=java.pid,create_time=java.create_time(),cpu_s=sum(java.cpu_times()[:2]))
                timeout=await until(client,log,'startup_timeout',suspended_at+650,1)
                if timeout['startup']['timeout_s']!=600 or timeout['startup']['elapsed_s']<600:raise RuntimeError('unexpected timeout threshold')
                mark('real_600s_timeout_observed',observation=timeout,java_alive=alive(java),cpu_s=sum(java.cpu_times()[:2]),suspended_s=round(time.monotonic()-suspended_at,2))
                gate=a.out/'resume.request'; deadline=time.monotonic()+1800
                mark('awaiting_resume_gate',gate=str(gate),max_wait_seconds=1800)
                while not gate.exists() and time.monotonic()<deadline:await asyncio.sleep(1)
                if not gate.exists():raise TimeoutError('resume.request gate not received within 1800 seconds')
                if not alive(java) or java.create_time()!=report['java']['create_time']:raise RuntimeError('exact owned JVM identity changed while paused')
                java.resume(); is_suspended=False; resumed=time.monotonic(); mark('owned_jvm_resumed')
                ready=await until(client,log,'ready',resumed+900,1)
                mark('same_jvm_recovered',observation=ready,seconds_after_resume=round(time.monotonic()-resumed,3),listeners=listeners(ports))
            else:
                ready=await until(client,log,'ready',time.monotonic()+900,1)
                mark('ready_before_launcher_crash',observation=ready,listeners=listeners(ports))
            if not alive(java) or java.ppid()!=launcher.pid or java.create_time()!=report['java']['create_time']:
                raise RuntimeError('owned JVM identity mismatch before abnormal exit')
            killed_pid, killed_ct = java.pid, java.create_time()
            java.kill(); java.wait(10); mark('owned_jvm_killed',pid=killed_pid,create_time=killed_ct)
            stopped=await until(client,log,'stopped',time.monotonic()+15,.25)
            mark('mcp_observed_stopped',observation=stopped,world_present=world.exists(),listeners=listeners(ports))
            report['scenario_completed']=True
    except Exception as exc:
      report['scenario_completed']=False; mark('failure',type=type(exc).__name__,message=str(exc)); raise
    finally:
      if is_suspended and alive(java):java.resume(); is_suspended=False
      for name,p in [('java',java),('launcher',launcher)]:
        if alive(p):
          if p.pid==report.get(name,{}).get('pid') and p.create_time()==report[name]['create_time']:
            p.kill(); p.wait(10); mark('exact_owned_process_cleanup',name=name,pid=p.pid)
          else:mark('ownership_mismatch_left_untouched',name=name,pid=p.pid)
      mark('final_cleanup',java_alive=alive(java),launcher_alive=alive(launcher),world_present=bool(world and world.exists()),listeners=listeners(ports) if ports else [])

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--case',choices=['timeout-recovery','jvm-crash'],required=True)
 p.add_argument('--lab',type=lambda x:Path(x).resolve(),required=True)
 p.add_argument('--assets',type=lambda x:Path(x).resolve(),required=True)
 p.add_argument('--jdk',type=lambda x:Path(x).resolve(),required=True)
 p.add_argument('--out',type=lambda x:Path(x).resolve(),required=True)
 p.add_argument('--eula-reviewed',action='store_true',required=True)
 asyncio.run(run(p.parse_args()))
if __name__=='__main__':main()
