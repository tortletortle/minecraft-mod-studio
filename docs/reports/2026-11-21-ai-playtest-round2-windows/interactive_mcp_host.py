"""Persistent MCP host. Tool choices come from the interactive external agent.

No gameplay assertions or gameplay commands are scripted here. JSON requests are
forwarded to the official MCP SDK; full results are retained for an audit trail.
"""
import argparse
import asyncio
import importlib.metadata
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from mcp import Client, StdioServerParameters

def utc():
    return datetime.now(timezone.utc).isoformat()

def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)

async def host(repo, assets, out):
    queue = out/'requests'
    queue.mkdir(parents=True, exist_ok=True)
    results = out/'responses'
    results.mkdir(parents=True, exist_ok=True)
    parameters = StdioServerParameters(command=sys.executable, args=[
        str(repo/'ai-debug-lab/playtest.py'), 'serve', '--assets', str(assets),
        '--evidence', str(out/'launcher'), '--accept-eula'
    ])
    started = utc()
    with (out/'host-events.jsonl').open('a', encoding='utf-8') as transcript:
        async with Client(parameters) as client:
            discovery = await client.list_tools()
            ready = {'started': started, 'host': 'interactive external agent via official Python MCP Client',
                     'python': sys.version, 'mcp': importlib.metadata.version('mcp'),
                     'tools': discovery.model_dump(mode='json', by_alias=True)}
            write_json(out/'host-ready.json', ready)
            print('INTERACTIVE_MCP_HOST_READY', flush=True)
            while True:
                if (out/'shutdown.request').exists():
                    break
                for request_path in sorted(queue.glob('*.json')):
                    response_path = results/request_path.name
                    if response_path.exists():
                        continue
                    request = json.loads(request_path.read_text(encoding='utf-8'))
                    entry = {'id': request_path.stem, 'started': utc(), 'request': request}
                    t0 = time.monotonic()
                    try:
                        answer = await client.call_tool(request['name'], request.get('arguments', {}))
                        entry['response'] = answer.model_dump(mode='json', by_alias=True)
                    except Exception as exc:
                        entry['host_exception'] = {'type': type(exc).__name__, 'message': str(exc)}
                    entry['elapsed_s'] = round(time.monotonic()-t0, 3)
                    entry['finished'] = utc()
                    write_json(response_path, entry)
                    transcript.write(json.dumps(entry, ensure_ascii=True)+'\n')
                    transcript.flush()
                    print('MCP_RESPONSE', request_path.stem, flush=True)
                await asyncio.sleep(0.15)
        write_json(out/'host-closed.json', {'started': started, 'closed': utc(), 'status': 'MCP_CONTEXT_CLOSED'})
        print('INTERACTIVE_MCP_HOST_CLOSED', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    asyncio.run(host(args.repo.resolve(), args.assets.resolve(), args.out.resolve()))
