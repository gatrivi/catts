"""Generic single-model bench/probe: load time, decode tok/s, native tool call, light code sanity.

Usage:
  python scripts/bench_model.py --exe <llama-server.exe> --model <file.gguf> [--ctx 16384] [--port 9105]
                               [--ctk q8_0] [--ctv q8_0] [--ngl 99] [--label name] [--toolcheck]
Owns its own server on <port> and always stops it. Aborts if free RAM is under the floor.
Writes nothing except <label>-bench.log next to the model's parent's parent (data/).
"""
import argparse, json, os, socket, subprocess, sys, time

import httpx

p = argparse.ArgumentParser()
p.add_argument('--exe', required=True)
p.add_argument('--model', required=True)
p.add_argument('--ctx', default='16384')
p.add_argument('--port', type=int, default=9105)
p.add_argument('--ctk', default='q8_0')
p.add_argument('--ctv', default='q8_0')
p.add_argument('--ngl', default='99')
p.add_argument('--label', default='bench')
p.add_argument('--ram-floor-mb', type=int, default=2500)
p.add_argument('--no-toolcheck', action='store_true')
a = p.parse_args()

LOG = f"Z:/catts/local-coding/data/{a.label}-bench.log"
try:
    out = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                          "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                         capture_output=True, text=True).stdout.strip()
    free_mb = int(out) // 1024
except Exception:
    free_mb = None
print('free RAM MB:', free_mb)
if free_mb is not None and free_mb < a.ram_floor_mb:
    print(f'ABORT: only {free_mb} MB free RAM (floor {a.ram_floor_mb} MB)')
    raise SystemExit(2)
with socket.socket() as s:
    if s.connect_ex(('127.0.0.1', a.port)) == 0:
        print(f'ABORT: port {a.port} busy')
        raise SystemExit(3)

args = [a.exe, '-m', a.model, '--host', '127.0.0.1', '--port', str(a.port), '--alias', a.label,
        '--device', 'Vulkan1', '-ngl', a.ngl, '-c', a.ctx, '-np', '1',
        '-ctk', a.ctk, '-ctv', a.ctv, '-fa', 'on', '--jinja', '--no-warmup',
        '-b', '256', '-ub', '128', '--temp', '0.2', '--top-p', '0.95', '--top-k', '40']
print('launch:', ' '.join(args))
log = open(LOG, 'w', encoding='utf-8')
srv = subprocess.Popen(args, stdout=log, stderr=log)
t0 = time.monotonic()
try:
    ready = None
    while time.monotonic() - t0 < 900:
        if srv.poll() is not None:
            print('SERVER EXITED code', srv.returncode)
            break
        try:
            if httpx.get(f'http://127.0.0.1:{a.port}/health', timeout=2).status_code == 200:
                ready = time.monotonic() - t0
                break
        except Exception:
            pass
        time.sleep(1)
    print(f'LOAD_SECONDS {ready}')
    if not ready:
        print(open(LOG, encoding='utf-8', errors='replace').read()[-2500:])
        raise SystemExit(4)

    def chat(payload, tag):
        t = time.monotonic()
        r = httpx.post(f'http://127.0.0.1:{a.port}/v1/chat/completions', json=payload, timeout=900)
        dt = time.monotonic() - t
        if r.status_code != 200:
            print(f'  [{tag}] HTTP {r.status_code}: {r.text[:300]}')
            return None
        j = r.json()
        u = j.get('usage', {})
        ct = u.get('completion_tokens', 0)
        print(f"  [{tag}] prompt {u.get('prompt_tokens')} tk | decode {ct} tk / {dt:.1f}s = {ct/max(dt,0.01):.2f} tok/s | {json.dumps(j.get('timings', {}))[:140]}")
        return j

    base = {'model': a.label, 'temperature': 0, 'max_tokens': 128,
            'chat_template_kwargs': {'enable_thinking': False}}
    base['messages'] = [{'role': 'user', 'content': 'Count from 1 to 20, digits only.'}]
    j = chat(base, 'decode')
    if j:
        print('  text:', j['choices'][0]['message']['content'][:120].replace('\n', ' '))
    if not a.no_toolcheck:
        base['messages'] = [{'role': 'user', 'content': 'Call read_file with path AGENTS.md now. Do not answer in prose.'}]
        base['max_tokens'] = 256
        base['tools'] = [{'type': 'function', 'function': {'name': 'read_file', 'description': 'r',
                         'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}]
        j = chat(base, 'toolcall')
        if j:
            print('  calls:', json.dumps(j['choices'][0]['message'].get('tool_calls') or [])[:400])
            print('  prose:', (j['choices'][0]['message'].get('content') or '')[:160].replace('\n', ' '))
    base.pop('tools', None)
    base['max_tokens'] = 192
    base['messages'] = [{'role': 'user', 'content': 'Write a JavaScript function toCents(value) that converts a non-negative number of dollars to integer cents and throws on invalid input. Code only.'}]
    j = chat(base, 'code')
    if j:
        print('  text:', j['choices'][0]['message']['content'][:250].replace('\n', ' | '))
finally:
    srv.terminate()
    try:
        srv.wait(20)
    except Exception:
        srv.kill()
    log.close()
    print('STOPPED', a.label)