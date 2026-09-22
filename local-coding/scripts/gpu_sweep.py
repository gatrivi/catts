"""GPU bench sweep: -b/-ub x KV quant x runtime matrix, one model at a time.

Usage:
  python scripts/gpu_sweep.py [--models mini,qwen35,bonsai2] [--port 9151]
      [--ubs 256/128,512/256,1024/512] [--kvs q8_0,q4_0]
      [--ram-floor-mb 2500] [--load-timeout 600] [--force]

Extends scripts/bench_model.py: owns its own llama-server per run on <port>
and always stops it. Refuses to run if another llama-server is up (GPU must
be idle for honest numbers) unless --force. Writes
data/sweeps/sweep-<stamp>.json with every run and prints a best-per-model
verdict meant to feed back into local_models.py presets. Nothing is applied
automatically.
"""
import argparse, datetime, json, re, socket, subprocess, sys, time
from pathlib import Path

import httpx

try:
    import scripts.local_models as lm
except ImportError:
    import local_models as lm

ROOT = lm.ROOT
RUNTIMES = {'default': lm.DEFAULT_RUNTIME, 'prism': lm.PRISM_RUNTIME, 'b10964': lm.B10964_RUNTIME}
# Modelos representativos: rapido, el editor de Taller, y el ternario (solo prism).
SWEEP_MODELS = {
    'mini': {'key': 'mini', 'runtimes': ('default', 'b10964'), 'ctx': 8192},
    'qwen35': {'key': 'qwen35', 'runtimes': ('default', 'b10964'), 'ctx': 16384},
    'bonsai2': {'key': 'bonsai2', 'runtimes': ('prism',), 'ctx': 8192},
}
DEFAULT_PORTS_BASE = 9151


def detect_device(exe):
    """Primer device Vulkan de --list-devices (Vulkan1 si hay iGPU+dGPU; si no Vulkan0).

    Los lanzadores de la casa hardcodean Vulkan1; si la iGPU Vega no enumera
    hoy, la 6600 queda como Vulkan0 y esos lanzadores fallan (visto en la
    primera corrida del sweep). Detectar en vez de asumir.
    """
    try:
        out = subprocess.run([exe, '--list-devices'], capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return 'Vulkan1'
    devs = re.findall(r'Vulkan\d+', out)
    return 'Vulkan1' if 'Vulkan1' in devs else (devs[0] if devs else 'Vulkan1')


def build_runs(models, ubs, kvs):
    """Matriz (modelo x runtime x batch x KV) respetando la compatibilidad por modelo."""
    runs = []
    for m in models:
        spec = SWEEP_MODELS[m]
        for rt in spec['runtimes']:
            for b, ub in ubs:
                for kv in kvs:
                    runs.append({'model': m, 'runtime': rt, 'b': b, 'ub': ub, 'kv': kv})
    return runs


def server_argv(run, port, device):
    spec = SWEEP_MODELS[run['model']]
    return [RUNTIMES[run['runtime']], '-m', str(lm.model_path(spec['key'])),
            '--host', '127.0.0.1', '--port', str(port), '--alias', f"sweep-{run['model']}",
            '--device', device, '-ngl', '999', '-c', str(spec['ctx']), '-np', '1',
            '-ctk', run['kv'], '-ctv', run['kv'], '-fa', 'on', '--jinja',
            '--no-warmup', '--no-mmap', '-b', str(run['b']), '-ub', str(run['ub'])]


def gpu_busy():
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq llama-server.exe'],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return False  # no poder verificar no bloquea
    return 'llama-server.exe' in out


def free_ram_mb():
    try:
        out = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                              '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return int(out) // 1024
    except Exception:
        return None


def wait_health(port, timeout, srv=None):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if srv is not None and srv.poll() is not None:
            return None
        try:
            if httpx.get(f'http://127.0.0.1:{port}/health', timeout=2).status_code == 200:
                return time.monotonic() - t0
        except Exception:
            pass
        time.sleep(1)
    return None


def pp_prompt(blocks=220):
    body = ''.join(f'function f{i}(a){{return a + {i};}}\n' for i in range(blocks))
    return '```js\n' + body + '```\nSummarize what this code does in one short sentence.'


def payload(prompt, max_tokens):
    return {'model': 'sweep', 'temperature': 0, 'max_tokens': max_tokens,
            'chat_template_kwargs': {'enable_thinking': False},
            'messages': [{'role': 'user', 'content': prompt}]}


def chat(port, body, timeout=900):
    t = time.monotonic()
    r = httpx.post(f'http://127.0.0.1:{port}/v1/chat/completions', json=body, timeout=timeout)
    dt = time.monotonic() - t
    if r.status_code != 200:
        return None, dt
    j = r.json()
    tm = j.get('timings') or {}
    u = j.get('usage') or {}
    return {
        'pp_n': tm.get('prompt_n') or u.get('prompt_tokens'),
        'pp_tps': tm.get('prompt_per_second'),
        'tg_n': tm.get('predicted_n') or u.get('completion_tokens'),
        'tg_tps': tm.get('predicted_per_second'),
        'wall_s': round(dt, 2),
    }, dt


def run_one(run, port, ram_floor_mb, load_timeout, log_dir, device):
    """Levanta el server para una celda de la matriz, mide decode y prompt-processing."""
    res = dict(run)
    fr = free_ram_mb()
    if fr is not None and fr < ram_floor_mb:
        res['status'] = 'ram_floor'
        return res
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', port)) == 0:
            res['status'] = 'port_busy'
            return res
    argv = server_argv(run, port, device)
    log_dir.mkdir(parents=True, exist_ok=True)
    idx = f"{run['model']}-{run['runtime']}-b{run['b']}-{run['kv']}"
    with open(log_dir / f'{idx}.log', 'w', encoding='utf-8') as log:
        srv = subprocess.Popen(argv, stdout=log, stderr=log)
        t0 = time.monotonic()
        try:
            ready = wait_health(port, load_timeout, srv)
            if srv.poll() is not None:
                res['status'] = 'load_failed'
                with open(log.name, encoding='utf-8', errors='replace') as f:
                    res['error_tail'] = f.read()[-400:]
                return res
            if not ready:
                res['status'] = 'load_timeout'
                return res
            res['load_s'] = round(ready, 1)
            dec, _ = chat(port, payload('Count from 1 to 300, digits only, comma separated, one line.', 640))
            pp, _ = chat(port, payload(pp_prompt(), 48))
            res.update({'status': 'ok', 'decode': dec, 'pp': pp})
        finally:
            srv.terminate()
            try:
                srv.wait(20)
            except Exception:
                srv.kill()
            time.sleep(2)
    return res


def best_by(runs, field, parent):
    ok = [r for r in runs if r.get('status') == 'ok' and (r.get(parent) or {}).get(field)]
    return max(ok, key=lambda r: r[parent][field]) if ok else None


def fmt(rec):
    if not rec:
        return 'n/a'
    return (f"{rec['model']}/{rec['runtime']} -b {rec['b']} -ub {rec['ub']} kv {rec['kv']} "
            f"-> tg {rec['decode']['tg_tps']:.1f} t/s, pp {rec['pp']['pp_tps']:.1f} t/s")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--models', default='mini,qwen35,bonsai2')
    p.add_argument('--port', type=int, default=DEFAULT_PORTS_BASE)
    p.add_argument('--ubs', default='256/128,512/256,1024/512')
    p.add_argument('--kvs', default='q8_0,q4_0')
    p.add_argument('--ram-floor-mb', type=int, default=1800)
    p.add_argument('--load-timeout', type=int, default=600)
    p.add_argument('--force', action='store_true')
    a = p.parse_args()

    models = [m.strip() for m in a.models.split(',') if m.strip()]
    unknown = [m for m in models if m not in SWEEP_MODELS]
    if unknown:
        raise SystemExit(f'modelos desconocidos: {unknown}; validos: {list(SWEEP_MODELS)}')
    ubs = [tuple(int(x) for x in cell.split('/')) for cell in a.ubs.split(',')]
    kvs = a.kvs.split(',')
    if gpu_busy() and not a.force:
        raise SystemExit('ABORT: hay un llama-server activo; para el modelo primero (o --force).')

    runs = build_runs(models, ubs, kvs)
    log_dir = ROOT / 'data/sweeps/logs'
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    devices = {rt: detect_device(RUNTIMES[rt]) for rt in {r['runtime'] for r in runs}}
    for rt, dev in sorted(devices.items()):
        print(f"device {rt}: {dev}")
    print(f'sweep: {len(runs)} corridas, logs en {log_dir}')
    results = []
    for i, run in enumerate(runs):
        print(f"[{i + 1}/{len(runs)}] {run['model']}/{run['runtime']} -b {run['b']} -ub {run['ub']} kv {run['kv']} ...",
              flush=True)
        rec = run_one(run, a.port, a.ram_floor_mb, a.load_timeout, log_dir, devices[run['runtime']])
        if rec.get('status') == 'ok':
            print(f"    ok: load {rec['load_s']}s | tg {rec['decode']['tg_tps']:.1f} | pp {rec['pp']['pp_tps']:.1f}")
        else:
            print(f"    {rec['status']}")
        results.append(rec)

    out = ROOT / 'data/sweeps' / f'sweep-{stamp}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'stamp': stamp, 'runs': results}, indent=1), encoding='utf-8')
    print('\n=== mejores por modelo ===')
    for m in models:
        rs = [r for r in results if r['model'] == m]
        print(m, '| tg:', fmt(best_by(rs, 'tg_tps', 'decode')))
        print(m, '| pp:', fmt(best_by(rs, 'pp_tps', 'pp')))
    print('\nresultado completo:', out)
    return out


if __name__ == '__main__':
    main()
