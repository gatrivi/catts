"""np_curve.py - curva de concurrencia de PTQ1_0 27B, reproducible y con control.

Por que existe: data/np_curve_20260926.json llega hasta np=4 pero se corrio ad-hoc
(sin script, gpu:"" sin confirmar, args de servidor desconocidos). Este lo reemplaza
en rigor: puntos de CONTROL np=1 y np=2 para detectar drift contra los 7.79/13.10
previos, y los puntos NUEVOS np=5/6/8 para encontrar el codo de saturacion.
Criterio: si el agregado se aplana antes de 8, ahi esta el techo real.

Que NO es oraculo: si np=1 difiere de 7.79, los args de este run no son los del
curva vieja y la comparacion entre archivos no vale (solo vale dentro de este run).
Velocidad = solo este script. En-suite mide ratios, no t/s.

Uso: python scripts/np_curve.py [--points 1,2,5,6,8] [--tokens 256] [--runs 1]
                                 [--slot-ctx 2048] [--kv q8_0]
"""
import argparse
import asyncio
import ctypes
import json
import os
import socket
import subprocess
import sys
import time

import httpx

EXE = 'C:/src/llama.cpp/build/bin/llama-server.exe'
MODEL = 'Z:/catts/local-coding/data/models/bonsai2-27b-ptq10/Ternary-Bonsai-2-27B-PTQ1_0.gguf'
PORT = 9103
OUT_DIR = 'Z:/catts/local-coding/data'

# Prompt fijo: largo y determinista, para que cada punto genere el mismo numero de
# tokens y el wall-clock sea comparable entre puntos.
PROMPT = ('Write a detailed technical explanation of how a Vulkan compute shader '
          'implements an integer dot-product matrix-vector kernel. Cover workgroup '
          'memory layout, bank conflicts, and why arithmetic vs memory bound matters.')

# llvm-mingw runtime: sin esto el server muere al arrancar con 0xC0000139.
os.environ['PATH'] = 'C:\\tools\\llvm-mingw\\bin;' + os.environ.get('PATH', '')


def free_ram_mb() -> int:
    class MEMSTAT(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    st = MEMSTAT()
    st.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return int(st.ullAvailPhys / 1024 / 1024)


def port_busy(p: int) -> bool:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex(('127.0.0.1', p)) == 0
    finally:
        s.close()


def llama_running() -> bool:
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq llama-server.exe'],
                         capture_output=True, text=True).stdout
    return 'llama-server.exe' in out


def preflight(min_ram_mb: int):
    """Gate. NO mata procesos: si algo esta ocupado, aborta y lo dice."""
    if llama_running():
        sys.exit('ABORT: hay un llama-server corriendo')
    if port_busy(PORT):
        sys.exit(f'ABORT: puerto {PORT} ocupado')
    ram = free_ram_mb()

def wait_health(timeout_s=300) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            if httpx.get(f'http://127.0.0.1:{PORT}/health', timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


async def one_stream(client: httpx.AsyncClient, n_tokens: int) -> int:
    """Un stream decode. Cuenta tokens por usage, no por chunks SSE: el conteo de
    deltas es fragil (el server agrupa deltas) y sesgaria el wall-clock."""
    r = await client.post(f'http://127.0.0.1:{PORT}/v1/chat/completions', json={
        'model': 'np-curve', 'messages': [{'role': 'user', 'content': PROMPT}],
        'max_tokens': n_tokens, 'temperature': 0.0, 'stream': True,
        'stream_options': {'include_usage': True},
        'chat_template_kwargs': {'enable_thinking': False},
    }, timeout=900)
    r.raise_for_status()
    toks = 0
    for line in r.iter_lines():
        if not line or not line.startswith('data: '):
            continue
        body = line[6:]
        if body.strip() == '[DONE]':
            break
        try:
            j = json.loads(body)
        except json.JSONDecodeError:
            continue
        if j.get('usage'):
            toks = j['usage'].get('completion_tokens', toks)
    return toks


async def run_point(a, np_: int) -> dict:
    ctx = np_ * a.slot_ctx
    log = open(f'{OUT_DIR}/np_curve_server_np{np_}_r{a.run}.log', 'w', encoding='utf-8')
    srv = subprocess.Popen([
        EXE, '-m', MODEL, '--host', '127.0.0.1', '--port', str(PORT), '--alias', 'np-curve',
        '--device', 'Vulkan1', '-ngl', '99', '-c', str(ctx), '-np', str(np_),
        '-ctk', a.kv, '-ctv', a.kv, '-fa', 'on', '--jinja', '--no-warmup',
        '-b', '256', '-ub', '128', '--temp', '0.0',
    ], stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        if not wait_health():
            raise RuntimeError(f'server np={np_} no quedo healthy (ver server_np{np_}_r{a.run}.log)')
        print(f'[np={np_}] healthy, ctx={ctx} ({a.slot_ctx}/slot), {np_} streams', flush=True)
        t0 = time.perf_counter()
        async with httpx.AsyncClient() as client:
            toks = await asyncio.gather(*[one_stream(client, a.tokens) for _ in range(np_)])
        wall = time.perf_counter() - t0
        total = sum(toks)
        agg = total / wall
        row = {'np': np_, 'run': a.run, 'streams': np_, 'ctx_total': ctx,
               'kv': a.kv, 'tokens_per_stream': toks[0], 'tokens_total': total,
               'wall_s': round(wall, 2), 'tps_agg': round(agg, 3),
               'tps_per_stream': round(agg / np_, 3),
               'msgs_s': round(np_ / wall, 4)}
        print(f'[np={np_}] {total} tok en {wall:.1f}s -> agg {agg:.2f} t/s, '
              f'stream {agg / np_:.2f}', flush=True)
        return row
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=30)
        except subprocess.TimeoutExpired:
            srv.kill()
        log.close()
        time.sleep(3)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--points', default='1,2,5,6,8')
    ap.add_argument('--tokens', type=int, default=256)
    ap.add_argument('--runs', type=int, default=1)
    ap.add_argument('--slot-ctx', type=int, default=2048)
    ap.add_argument('--kv', default='q8_0')
    ap.add_argument('--min-ram-mb', type=int, default=8000)
    ap.add_argument('--out', default=f'{OUT_DIR}/np_curve_ext.json')
    a = ap.parse_args()

    preflight(a.min_ram_mb)
    points = [int(x) for x in a.points.split(',')]
    rows = []
    for run_i in range(1, a.runs + 1):
        a.run = run_i
        for np_ in points:
            try:
                rows.append(await run_point(a, np_))
            except Exception as e:
                print(f'[np={np_}] ERROR {e}', flush=True)
                rows.append({'np': np_, 'run': run_i, 'error': str(e)})
            # checkpoint por punto: si algo muere, los previos no se pierden
            json.dump(rows, open(a.out, 'w'), indent=4)
    print('DONE', flush=True)


if __name__ == '__main__':
    asyncio.run(main())

    if ram < min_ram_mb:
        sys.exit(f'ABORT: RAM libre {ram} MB < {min_ram_mb} MB')
    print(f'[gate] ok: sin servers, :{PORT} libre, RAM libre {ram} MB', flush=True)
