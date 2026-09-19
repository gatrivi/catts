"""Sonda de carga: tiempo hasta /health, RAM pico del servidor y buffers VRAM por modelo/contexto.

Uso: python scripts/probe_load.py --models qwen35 mini --context 32768 24576 [--mmap] [--deadline 900]
Prueba los contextos de mayor a menor y corta en el primero que carga y genera. Un servidor por vez en el
puerto de Smol; escribe data/smol/probes/<ts>/rows.jsonl y detiene el modelo al terminar.
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path
import httpx, psutil
sys.path.insert(0, str(Path(__file__).resolve().parent))
import smol

def probe(key, context, mmap, deadline_s, out_dir):
 argv = smol.server_args(key, False, context) + ['-lv', '4']
 if mmap: argv.remove('--no-mmap')
 label = f'{key}-{context // 1024}k-{"mmap" if mmap else "nommap"}'
 log_path = out_dir / (label + '.log')
 env = dict(os.environ, GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM='1')
 row = {'label': label, 'key': key, 'context': context, 'mmap': mmap,
  'ram_free_mb_start': psutil.virtual_memory().available // 2**20}
 t0 = time.monotonic(); peak = 0
 job = smol.RuntimeJob()
 with log_path.open('w', encoding='utf-8') as log:
  proc = subprocess.Popen(argv, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
  job.assign(proc)
 try:
  ps = psutil.Process(proc.pid)
  with httpx.Client(base_url=f'http://127.0.0.1:{smol.PORT}', timeout=5) as client:
   while time.monotonic() - t0 < deadline_s:
    if proc.poll() is not None: row['result'] = 'exited:' + str(proc.returncode); break
    try: peak = max(peak, ps.memory_info().rss)
    except psutil.Error: pass
    try:
     if client.get('/health').status_code == 200: row['load_s'] = round(time.monotonic() - t0, 1); break
    except httpx.HTTPError: pass
    time.sleep(1)
   else: row['result'] = 'timeout'
   if 'load_s' in row:
    t1 = time.monotonic()
    r = client.post('/v1/chat/completions', json={'model': key, 'temperature': 0, 'max_tokens': 8,
     'messages': [{'role': 'user', 'content': 'Say OK.'}]}, timeout=180)
    row['gen_s'] = round(time.monotonic() - t1, 1)
    row['result'] = 'ok' if r.status_code == 200 else 'gen_http_' + str(r.status_code)
    if r.status_code == 200: row['usage'] = r.json().get('usage')
 finally:
  smol.stop(proc); job.close()
 row['peak_rss_mb'] = peak // 2**20
 text = log_path.read_text(encoding='utf-8', errors='replace')
 row['buffers'] = [m.strip() for m in re.findall(r'(\S+ (?:model|KV|compute) buffer size\s*=\s*[\d.]+ MiB)', text)]
 row['log'] = str(log_path)
 return row

def main():
 parser = argparse.ArgumentParser(description='Sonda de carga de modelos Smol')
 parser.add_argument('--models', nargs='+', choices=smol.MODELS, required=True)
 parser.add_argument('--context', type=int, nargs='+', default=[smol.CONTEXT])
 parser.add_argument('--mmap', action='store_true', help='Quitar --no-mmap (Smol usa --no-mmap por defecto)')
 parser.add_argument('--deadline', type=int, default=900)
 opts = parser.parse_args()
 out_dir = smol.DATA / 'probes' / time.strftime('%Y%m%d-%H%M%S'); out_dir.mkdir(parents=True)
 with (out_dir / 'rows.jsonl').open('a', encoding='utf-8') as out:
  for key in opts.models:
   for ctx in sorted(opts.context, reverse=True):
    row = probe(key, ctx, opts.mmap, opts.deadline, out_dir)
    out.write(json.dumps(row) + '\n'); out.flush()
    print(json.dumps(row, ensure_ascii=False), flush=True)
    if row['result'] == 'ok': break

if __name__ == '__main__': main()
