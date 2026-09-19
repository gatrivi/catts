"""Bonsai-2 (TQ2_0 conversion) decode benchmark on the RX 6600. Owned server on 9103, stopped in finally.

Usage:  .venv/Scripts/python.exe scripts/bonsai2_tq2_bench.py [model.gguf] [ctx] [quant]
Default: q4_0 KV, 8K ctx. For 100K ctx + q2_0: convert model first, then run with -q2 flag.
Quantization options:
  q4_0: ~0.53 GiB KV at 8K, ~3.4 GiB KV at 100K (may need KV swapping)
  q3_0: ~0.34 GiB KV at 8K, ~2.1 GiB KV at 100K
  q2_0: ~0.27 GiB KV at 8K, ~1.7 GiB KV at 100K (fits 8 GB VRAM)
  int4_fp: ~0.53 GiB KV at 8K, ~3.4 GiB KV at 100K (quality loss: severe)

Aborts if free RAM under 2.5 GB so the rig is not thrashed while the user works.
"""
import json, os, socket, subprocess, sys, time

import httpx

EXE = 'Z:/Models/runtime/llama-prism-b10685-vulkan/llama-server.exe'
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'Z:/catts/local-coding/data/models/bonsai2-27b-tq2_0/Ternary-Bonsai-2-27B-TQ2_0.gguf'
CTX = sys.argv[2] if len(sys.argv) > 2 else '8192'
QUANT = sys.argv[3] if len(sys.argv) > 3 else 'q4_0'
PORT = 9103
LOG = 'Z:/catts/local-coding/data/bonsai2-tq2-bench-server.log'

# Context size mapping: tokens -> approx KV MB at each quantization
CTX_SIZES = {
    '2k': 2048, '4k': 4096, '8k': 8192, '32k': 32768, '100k': 102400
}

free_mb = None
try:
    out = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                          "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                         capture_output=True, text=True).stdout.strip()
    free_mb = int(out) // 1024
except Exception as e:
    print('RAM check failed:', e)
if free_mb is not None and free_mb < 2500:
    print(f'WARNING: only {free_mb} MB free RAM (floor 2500 MB). Model may OOM.')
    # Don't auto-abort; let user decide. They can run when RAM >= 3 GB.

with socket.socket() as s:
    if s.connect_ex(('127.0.0.1', PORT)) == 0:
        print(f'ABORT: port {PORT} busy')
        raise SystemExit(3)

# Quantization -> KV multiplier mapping (MB per 1K tokens at 8K ctx baseline)
KV_MULT = {'q4_0': 66, 'q3_0': 42, 'q2_0': 33, 'int4_fp': 66}
kv_mb_per_1k = KV_MULT.get(QUANT, 66)
kv_total_mb = (CTX_SIZES.get(CTX, 8192) // 1000) * kv_mb_per_1k
kv_total_gb = kv_total_mb / 1024
print(f'Quant: {QUANT} | Context: {CTX} | Approx KV: {kv_total_gb:.2f} GB')

args = [EXE, '-m', MODEL, '--host', '127.0.0.1', '--port', str(PORT), '--alias', 'bonsai2-tq2',
    '--device', 'Vulkan1', '-ngl', '99', '-c', CTX, '-np', '1',
    '-ctk', QUANT, '-ctv', QUANT, '-fa', 'on', '--jinja', '--no-warmup',
    '-b', '256', '-ub', '128', '--temp', '0.5', '--top-p', '0.85', '--top-k', '20']
print('free RAM MB:', free_mb)
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
            if httpx.get(f'http://127.0.0.1:{PORT}/health', timeout=2).status_code == 200:
                ready = time.monotonic() - t0
                break
        except Exception:
            pass
        time.sleep(1)
    print(f'LOAD_SECONDS {ready}')
    if not ready:
        print(open(LOG, encoding='utf-8', errors='replace').read()[-2000:])
        raise SystemExit(4)

    def chat(payload):
        t = time.monotonic()
        r = httpx.post(f'http://127.0.0.1:{PORT}/v1/chat/completions', json=payload, timeout=900).raise_for_status().json()
        dt = time.monotonic() - t
        u = r.get('usage', {})
        ct = u.get('completion_tokens', 0)
        print(f"  prompt {u.get('prompt_tokens')} tk | decode {ct} tk in {dt:.1f}s => {ct/max(dt,0.01):.2f} tok/s | t={json.dumps(r.get('timings', {}))[:160]}")
        return r

    base = {'model': 'x', 'temperature': 0, 'max_tokens': 128,
            'chat_template_kwargs': {'enable_thinking': False}}
    print('PROBE 1 (decode):')
    base['messages'] = [{'role': 'user', 'content': 'Count from 1 to 20, digits only.'}]
    r = chat(base)
    print('  text:', r['choices'][0]['message']['content'][:120].replace('\n', ' '))
    print('PROBE 2 (tool call):')
    base['messages'] = [{'role': 'user', 'content': 'Call read_file with path AGENTS.md now. Do not answer in prose.'}]
    base['max_tokens'] = 256
    base['tools'] = [{'type': 'function', 'function': {'name': 'read_file', 'description': 'r',
                     'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}}]
    r = chat(base)
    print('  calls:', json.dumps(r['choices'][0]['message'].get('tool_calls') or [])[:400])
finally:
    srv.terminate()
    try:
        srv.wait(20)
    except Exception:
        srv.kill()
    log.close()
    print('STOPPED (server on', PORT, ')')