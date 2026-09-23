"""Centro de control local de CATTS: un solo terminal para arrancar, cambiar y
apagar modelos y apps, sin abrir ventanas nuevas.

Todo proceso hijo se lanza oculto (CREATE_NO_WINDOW) y con log a data/hub/.
Uso: CATTS.cmd            (menu interactivo)
     CATTS.cmd status
     CATTS.cmd start bonsai2 --preset low
     CATTS.cmd switch qwen35
     CATTS.cmd stop --all
     CATTS.cmd chat mini
     CATTS.cmd check      (no carga nada; valida rutas, manifiestos y argv)
     CATTS.cmd profile [preflight]   (day-1 baseline del GPU; GPU exclusivo)
"""
import argparse, json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx, psutil

import local_models as reg

ROOT = reg.ROOT
DATA = ROOT / 'data/hub'
STATE = DATA / 'state.json'
LOG_DIR = DATA / 'logs'
RUNTIMES = {reg.DEFAULT_RUNTIME, reg.PRISM_RUNTIME, reg.B10964_RUNTIME}


def write_json(path, value):
 path.parent.mkdir(parents=True, exist_ok=True)
 temp = path.with_suffix(path.suffix + '.tmp')
 temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
 temp.replace(path)


def load_state():
 if STATE.exists():
  try:
   return json.loads(STATE.read_text(encoding='utf-8'))
  except json.JSONDecodeError:
   return {}
 return {}


def save_state(state):
 write_json(STATE, state)


def free_ram_gb():
 return round(psutil.virtual_memory().available / 1024 ** 3, 1)


def port_alive(port):
 try:
  with socket.create_connection(('127.0.0.1', port), timeout=0.3): return True
 except OSError: return False


def health(port):
 try:
  return httpx.get(f'http://127.0.0.1:{port}/health', timeout=2).json().get('status')
 except Exception: return None


def served_model(port):
 try:
  return httpx.get(f'http://127.0.0.1:{port}/v1/models', timeout=3).json()['data'][0]['id']
 except Exception: return None


def model_specs():
 """Todas las entradas arrancables: modelos sueltos (puerto propio), ranura Smol y apps.

 Las claves de la ranura Smol llevan prefijo 'smol:' para no chocar con el mismo
 modelo arrancado en su puerto propio (bonsai2, spark, qwen35, qwen27).
 """
 specs = {}
 for key, spec in reg.STANDALONE.items():
  specs[key] = dict(spec, kind='model')
 for key in reg.SMOL_MODELS:
  specs[f'smol:{key}'] = dict(kind='smol', model_key=key, label=reg.SMOL_MODELS[key][0],
   port=reg.SMOL_PORT, alias=key, runtime=reg.RUNTIMES.get(key, reg.DEFAULT_RUNTIME),
   presets=reg.PRESETS.get(key, []), ram_floor_mb=reg.RAM_FLOOR_MB.get(key, 1536),
   note='Ranura Smol (:9104), un modelo a la vez.', zed=('smol', key))
 for key, spec in reg.APPS.items():
  specs[key] = dict(spec, kind='app')
 return specs


SPECS = model_specs()


def identify(port, alias, model):
 """Que entrada del registro corresponde a un llama-server vivo (por puerto/alias/ruta)."""
 if port == reg.SMOL_PORT and alias and f'smol:{alias}' in SPECS: return f'smol:{alias}'
 for name, spec in SPECS.items():
  if spec['kind'] == 'smol' or spec['port'] != port: continue
  path = spec.get('model')
  if not model or not path: return name
  if str(Path(path).resolve()).lower() == str(Path(model).resolve()).lower(): return name
 return None


def find_servers():
 """llama-server vivos. Filtra por NOMBRE antes de leer cmdline: psutil tardaba ~7 s."""
 servers = []
 for p in psutil.process_iter(['pid', 'name']):
  if ((p.info.get('name') or '')).lower() != 'llama-server.exe': continue
  try:
   cmd = p.cmdline(); started = p.create_time()
  except (psutil.AccessDenied, psutil.NoSuchProcess):
   cmd, started = [], None
  def value(flag):
   return cmd[cmd.index(flag) + 1] if flag in cmd and cmd.index(flag) + 1 < len(cmd) else None
  model = value('-m') or value('--model')
  port_text = value('--port')
  port = int(port_text) if (port_text or '').isdigit() else None
  alias = value('--alias')
  servers.append({'pid': p.pid, 'key': identify(port, alias, model), 'port': port,
   'alias': alias, 'model': model, 'started': started, 'cmdline': cmd})
 return servers


def probe(port, timeout=2):
 """Una sola llamada: devuelve (estado, alias servido)."""
 try:
  data = httpx.get(f'http://127.0.0.1:{port}/v1/models', timeout=timeout).json()['data']
  return 'ok', (data[0]['id'] if data else None)
 except Exception:
  return ('cargando' if port_alive(port) else 'down'), None


def describe(srv):
 if srv['key']:
  spec = SPECS[srv['key']]
  return f"{spec['label']} (: {srv['port']}, PID {srv['pid']})"
 return f"SERVIDOR DESCONOCIDO (: {srv['port']}, PID {srv['pid']}) {Path(srv['model'] or '?').name}"


def print_status(servers=None, verbose=True):
 servers = find_servers() if servers is None else servers
 print(f"\nRAM libre: {free_ram_gb()} GB   |   modelos vivos: {len(servers)}")
 if not servers:
  print('  (ningun modelo arriba)')
 for srv in servers:
  state, alias = probe(srv['port']) if srv['port'] else ('proceso sin puerto', None)
  print(f"  {describe(srv)}  estado={state}  alias={alias}")
  apps = [s for s in servers if s['key'] in reg.APPS]
 if verbose:
  for key, spec in reg.APPS.items():
   live = [s for s in servers if s['key'] == key]
   port_state = probe(spec['port'])[0]
   print(f"  APP {spec['label']} (: {spec['port']}) estado={port_state}"
         + (f" PID {live[0]['pid']}" if live else ''))
 return servers


def log_path(name):
 LOG_DIR.mkdir(parents=True, exist_ok=True)
 # Las claves smol traen ':' (smol:mini): en NTFS eso crea un flujo alternativo,
 # invisible en el Explorador; se reemplaza para que el log sea un archivo normal.
 return LOG_DIR / f"{name.replace(':', '-')}.log"


def tail(name, lines=40):
 """Ultimas lineas del log de un modelo/app (comando 'l N' y error de carga)."""
 path = log_path(name)
 try: text = path.read_text(encoding='utf-8', errors='replace')
 except OSError: return f'(no hay log en {path})'
 return '\n'.join(text.splitlines()[-lines:]) or '(log vacio)'




def build_argv(key, preset=None, context=None):
 spec = SPECS[key]
 kind = spec['kind']
 if kind == 'smol':
  model_key = spec['model_key']
  return reg.smol_server_args(model_key, False, context, preset or reg.DEFAULT_PRESET.get(model_key))
 if kind == 'model':
  return reg.standalone_args(key, preset)
 return list(spec['argv'])


def model_size_gb(key):
 spec = SPECS[key]
 if spec['kind'] == 'app': return 0.0
 path = spec.get('model') or reg.model_path(spec['model_key'])
 try: return path.stat().st_size / 1024 ** 3
 except OSError: return 0.0


def load_budget(key):
 """Z: es un HDD de ~34 MB/s: margen a 20 MB/s, mas 120 s de arranque."""
 return 120 + int(model_size_gb(key) * 1024 / 20)


def start(key, preset=None, context=None, force=False, wait=True):
 spec = SPECS[key]
 if key not in SPECS: raise RuntimeError(f'No conozco {key}')
 port = spec['port']
 if spec['kind'] == 'app' and port_alive(port) and health(port):
  print(f"{spec['label']} ya responde en : {port}"); return True
 if spec['kind'] != 'app':
  others = [s for s in find_servers() if s['key'] != key]
  if others:
   text = '; '.join(describe(s) for s in others)
   if not force:
    raise RuntimeError(f'Otro modelo esta arriba: {text}\n'
     f'La GPU es exclusiva: usa "w {key}" para cambiar de modelo, o --force para forzar.')
   print(f'Aviso: siguen arriba {text}; pueden no entrar juntos en VRAM.')
  same = [s for s in find_servers() if s['key'] == key]
  if same:
   print(f"{spec['label']} ya esta arriba (: {port}, PID {same[0]['pid']})"); return True
 if port_alive(port):
  raise RuntimeError(f'El puerto {port} esta ocupado por otro proceso; no lo toco.')
 floor = spec.get('ram_floor_mb', 1536)
 if free_ram_gb() * 1024 < floor:
  raise RuntimeError(f'Necesito {floor // 1024} GB de RAM libre y hay {free_ram_gb()} GB.')
 argv = build_argv(key, preset, context)
 shown = ' '.join(argv[:1] + argv[1:3]) + ' ...'
 print(f"Cargando {spec['label']} en : {port} (log data/hub/logs/{key.replace(':', '-')}.log)")
 print(f'  {shown}')
 env = os.environ.copy()
 env['GGML_VK_DISABLE_HOST_VISIBLE_VMEM'] = '1'
 env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM'] = '1'
 with log_path(key).open('a', encoding='utf-8') as log:
  log.write(f"\n--- hub start {time.strftime('%Y-%m-%d %H:%M:%S')} preset={preset} ---\n")
  proc = subprocess.Popen(argv, cwd=str(ROOT), env=env, stdout=log, stderr=log,
   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
 state = load_state()
 state[key] = {'pid': proc.pid, 'port': port, 'kind': spec['kind'], 'preset': preset,
  'started': time.strftime('%Y-%m-%d %H:%M:%S'), 'argv': argv}
 save_state(state)
 if not wait: return proc.pid
 if spec['kind'] == 'app':
  # Las apps responden cuando el puerto esta abierto (no todas tienen /health).
  for _ in range(25):
   if proc.poll() is not None: raise RuntimeError(f"{key} murio al arrancar; mira el log ({log_path(key)})")
   if port_alive(port):
    print(f"{spec['label']} escuchando en : {port}" + ('' if health(port) else ' (sin /health propio)'))
    return proc.pid
   time.sleep(1)
  raise RuntimeError(f"{spec['label']} no abrio : {port}; mira el log ({log_path(key)})")
 budget = load_budget(key)
 deadline = time.monotonic() + budget
 printed = 0
 while time.monotonic() < deadline:
  if proc.poll() is not None:
   raise RuntimeError(f'El modelo no pudo cargar (codigo {proc.returncode}). Ultimas lineas:\n{tail(key, 12)}')
  if health(port) == 'ok':
   alias = served_model(port)
   print(f"Listo en {int(time.monotonic() - (deadline - budget))}s: : {port} alias={alias}")
   print(zed_hint(key))
   return proc.pid
  waited = int(time.monotonic() - (deadline - budget))
  if waited >= printed + 15:
   printed = waited
   print(f'  cargando de Z: (HDD) ... {waited}s de un maximo de {budget}s')
  time.sleep(2)
 raise RuntimeError(f'La carga paso de {budget}s; mira el log ({log_path(key)})')


def stop_pid(pid, expect_model=None, timeout=25):
 try: proc = psutil.Process(pid)
 except psutil.NoSuchProcess: return 'ya no existia'
 if expect_model and (proc.name() or '').lower() not in ('llama-server.exe', 'python.exe'):
  return f'no lo toco: es {proc.name()}'
 try:
  proc.terminate()
  proc.wait(timeout=timeout)
 except psutil.TimeoutExpired:
  proc.kill(); proc.wait(timeout=10)
 except psutil.AccessDenied:
  return 'sin permisos para detenerlo'
 return 'detenido'


def stop(key=None, everything=False, include_apps=False):
 """Apaga modelos (y apps si se pide). Con key apaga ese; sin key, todos los modelos."""
 state = load_state()
 done = []
 if key and key in SPECS and SPECS[key]['kind'] == 'app':
  record = state.get(key)
  if not record: return f"{SPECS[key]['label']} no lo arranco el hub (o ya estaba apagado)"
  result = stop_pid(record['pid'], expect_model=True)
  done.append(f"{SPECS[key]['label']} : {record['port']} -> {result}")
  state.pop(key); save_state(state)
  return '\n'.join(done)
 if not key:
  targets = [s for s in find_servers()]
  if include_apps:
   for app_key, record in list(state.items()):
    if app_key in reg.APPS:
     targets.append({'pid': record['pid'], 'port': record['port'], 'key': app_key, 'model': None})
 else:
  targets = [s for s in find_servers() if s['key'] == key]
  if not targets and key in state:
   targets = [{'pid': state[key]['pid'], 'port': state[key]['port'], 'key': key, 'model': None}]
  if not targets: return f'{key} no estaba arriba'
 for srv in targets:
  if srv['key'] is None and not everything:
   done.append(f"no detengo el servidor desconocido de : {srv['port']} (usa 'stop all --force')")
   continue
  result = stop_pid(srv['pid'], expect_model=True)
  label = SPECS[srv['key']]['label'] if srv['key'] else 'desconocido'
  done.append(f"{label} : {srv['port']} -> {result}")
  if srv['key'] in state: state.pop(srv['key'])
 save_state(state)
 return '\n'.join(done) if done else 'nada que apagar'


def switch(key, preset=None, context=None):
 print(stop(everything=False, include_apps=False))
 for _ in range(30):
  if not [s for s in find_servers() if s['key'] not in reg.APPS]: break
  time.sleep(1)
 time.sleep(2)  # deja que la VRAM se libere antes de cargar el siguiente
 return start(key, preset, context, force=True)


def chat(key, limit=512):
 spec = SPECS[key]
 if spec['kind'] == 'app': raise RuntimeError('Las apps no tienen chat; usa un modelo.')
 port = spec['port']
 if not (port_alive(port) and health(port) == 'ok'):
  print('No esta arriba: lo cargo primero.')
  start(key)
 alias = served_model(port) or spec.get('alias', key)
 url = f'http://127.0.0.1:{port}/v1/chat/completions'
 messages = []
 print(f"\nChat directo con {spec['label']} (: {port}, alias {alias}).")
 print('  /new borra el historial | /exit vuelve al menu')
 while True:
  try: text = input('vos> ').strip()
  except (EOFError, KeyboardInterrupt): print(); return
  if not text: continue
  if text in ('/exit', '/quit'): return
  if text == '/new': messages.clear(); print('historial borrado'); continue
  messages.append({'role': 'user', 'content': text})
  payload = {'model': alias, 'messages': messages, 'max_tokens': limit, 'stream': True}
  if key in reg.THINKING_KWARG_OK: payload['chat_template_kwargs'] = {'enable_thinking': False}
  print('modelo> ', end='', flush=True)
  answer = []
  try:
   with httpx.stream('POST', url, json=payload, timeout=900) as response:
    if response.status_code != 200:
     print(f"\n[el servidor respondio {response.status_code}]")
     messages.pop(); continue
    for line in response.iter_lines():
     if not line.startswith('data: '): continue
     chunk = line[6:]
     if chunk == '[DONE]': break
     try: delta = json.loads(chunk)['choices'][0]['delta']
     except (json.JSONDecodeError, KeyError, IndexError): continue
     piece = delta.get('content') or ''
     if piece: answer.append(piece); print(piece, end='', flush=True)
  except httpx.HTTPError as exc:
   print(f'\n[error de red: {exc}]'); messages.pop(); continue
  print()
  if answer: messages.append({'role': 'assistant', 'content': ''.join(answer)})


def zed_hint(key):
 spec = SPECS[key]
 provider, model = spec.get('zed', ('?', '?'))
 return (f"  Zed -> provider '{provider}', model '{model}' (Settings > Language Models, o el selector del agente)\n"
         f"  omp -> --model {provider}/{model} (el picker de omp lo muestra; responde solo con el modelo arriba)")


def actions():
 """Numeros estables del menu: modelos sueltos, ranura Smol, apps."""
 rows = [('model', key) for key in reg.STANDALONE]
 rows += [('smol', f'smol:{key}') for key in reg.SMOL_MODELS]
 rows += [('app', key) for key in reg.APPS]
 return rows


def print_menu(rows, servers):
 live = {srv['key'] for srv in servers}
 print('\n' + '=' * 78)
 print(f" CATTS local | RAM libre {free_ram_gb()} GB | modelos vivos:"
      f" {len([s for s in servers if s['key'] not in reg.APPS])}")
 print('=' * 78)
 section = None
 titles = {'model': '-- Modelos con puerto propio --',
  'smol': '-- Ranura Smol (:9104, un modelo a la vez) --', 'app': '-- Apps del proyecto --'}
 for n, (kind, key) in enumerate(rows, 1):
  spec = SPECS[key]
  if kind != section:
   section = kind
   print(f'\n{titles[kind]}')
  presets = ','.join(p for p, _, _ in spec.get('presets', []))
  print(f"  {n:2}. {spec['label'][:40]:40} : {spec['port']:5} "
        f"{'ENCENDIDO' if key in live else 'apagado':9}" + (f" presets: {presets}" if presets else ''))
 print('\n  s N [preset] arrancar | w N [preset] cambiar | x N apagar | a apagar modelos')
 print('  c N chat directo | l N ver log | z N: que elegir en Zed | r refrescar')
 print('  t Taller (sesion) | m Smol (sesion) | q salir | qa salir y apagar todo | h ayuda')


def resolve(token, rows):
 if token.isdigit() and 1 <= int(token) <= len(rows): return rows[int(token) - 1][1]
 if token in SPECS: return token
 if f'smol:{token}' in SPECS: return f'smol:{token}'  # nombre pelado = ranura Smol
 return None


def taller_session():
 return subprocess.call(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
  '-File', str(ROOT / 'scripts/taller.ps1')], cwd=str(ROOT))


def smol_session():
 print(stop(everything=False, include_apps=False))
 return subprocess.call([reg.PYTHON, str(ROOT / 'scripts/smol.py')], cwd=str(ROOT))


def check():
 """Valida todo sin cargar nada: runtimes, modelos, manifiestos, puertos y argv."""
 problems = []
 for key, spec in SPECS.items():
  if spec['kind'] == 'app':
   argv = spec['argv']
   if not Path(argv[0]).is_file(): problems.append(f'{key}: falta {argv[0]}')
   script = Path(argv[-1]) if str(argv[-1]).endswith('.py') else None
   if script and not script.is_file(): problems.append(f'{key}: falta {script}')
   print(f"APP  {key:10} {spec['label'][:32]:32} : {spec['port']:5}")
   continue
  runtime = Path(spec['runtime'])
  if not runtime.is_file(): problems.append(f'{key}: falta el runtime {runtime}')
  path = spec.get('model') or reg.model_path(spec['model_key'])
  if not path.is_file(): problems.append(f'{key}: falta el modelo {path}')
  else:
   manifest = path.with_name(path.name + '.verified.json')
   if not manifest.exists(): manifest = path.parent / 'verified.json'
   if manifest.exists():
    expected = json.loads(manifest.read_text(encoding='utf-8-sig'))['bytes']
    if path.stat().st_size != expected: problems.append(f'{key}: el modelo cambio de tamano')
   else:
    print(f"  aviso: {key} sin manifiesto .verified.json (tamano no verificado)")
  presets = ','.join(n for n, _, _ in spec.get('presets', [])) or '-'
  build_argv(key)
  print(f"MOD  {key:10} {spec['label'][:32]:32} : {spec['port']:5} presets={presets}"
        + (' UP' if port_alive(spec['port']) else ''))
 print(f"\nRAM libre {free_ram_gb()} GB | problemas: {len(problems)}")
 for problem in problems: print('  - ' + problem)
 return problems


HELP_TEXT = """
  Ordenes del menu:
    N o s N [preset]   arrancar el modelo numero N (ej: 6, s 6, s 14 mid)
    w N [preset]       cambiar: apaga el modelo actual y arranca N
    x N | x all        apagar un modelo | todo (modelos y apps)
    a                  apagar todos los modelos
    c N                chat directo con N
    l N                ultimas lineas del log de N
    z N                que provider/model elegir en Zed para N
    t / m              sesion Taller / Smol (en esta misma ventana)
    r                  refrescar la pantalla
    q                  salir (los modelos quedan arriba)
    qa                 salir y apagar todo
  N es el numero de la lista (1-19) o el nombre (mini, qwen35, bonsai2...)."""


def menu():
 rows = actions()
 while True:
  servers = print_status()
  print_menu(rows, servers)
  try: entry = input('\norden> ').strip()
  except (EOFError, KeyboardInterrupt): print(); return 0
  if not entry: continue
  parts = entry.split()
  cmd = parts[0].lower()
  arg = parts[1] if len(parts) > 1 else None
  preset = parts[2] if len(parts) > 2 else None
  try:
   if cmd in ('q', 'salir', 'exit'): return 0
   if cmd in ('qa', 'quit-all'):
    print(stop(everything=True, include_apps=True)); return 0
   if cmd in ('h', 'help', 'ayuda', '?'):
    print(HELP_TEXT); continue
   if cmd in ('r', 'refrescar'): continue
   if cmd == 'a':
    print(stop(everything=True, include_apps=False)); continue
   if cmd == 't': taller_session(); continue
   if cmd == 'm': smol_session(); continue
   if cmd == 'check': check(); continue
   if cmd.isdigit(): cmd, arg = 's', cmd  # numero suelto = arrancar ese modelo
   if cmd in ('s', 'start', 'w', 'switch', 'x', 'stop', 'c', 'chat', 'l', 'logs', 'z', 'zed'):
    if cmd in ('x', 'stop') and arg in (None, 'all', 'todo'):
     print(stop(everything=True, include_apps=True)); continue
    key = resolve(arg or '', rows)
    if not key:
     print(f'  numero del 1 al {len(rows)} o nombre del modelo (ej: "s 6" o "mini").'); continue
    if cmd in ('s', 'start'): start(key, preset)
    elif cmd in ('w', 'switch'): switch(key, preset)
    elif cmd in ('x', 'stop'): print(stop(key))
    elif cmd in ('c', 'chat'): chat(key)
    elif cmd in ('l', 'logs'): print(tail(key))
    else: print(zed_hint(key))
    continue
   print('  orden no reconocida. Para arrancar: "6" o "s 6". Escribi "h" para la ayuda.')
  except RuntimeError as exc:
   print(f'  {exc}')
  except KeyboardInterrupt:
   print('\n  interrumpido')


def main():
 parser = argparse.ArgumentParser(description='Centro de control de modelos locales y apps de CATTS')
 parser.add_argument('action', nargs='?', default='menu',
  choices=['menu', 'status', 'check', 'profile', 'start', 'stop', 'switch', 'restart', 'chat', 'logs', 'list'])
 parser.add_argument('target', nargs='?', help='clave o numero del modelo/app')
 parser.add_argument('--preset', help='preset de arranque (mid/low/high, fast/balanced/max, long)')
 parser.add_argument('--context', type=int, help='contexto para la ranura Smol')
 parser.add_argument('--force', action='store_true', help='arrancar aunque haya otro modelo arriba')
 parser.add_argument('--all', action='store_true', help='con stop: incluye apps y servidores desconocidos')
 opts = parser.parse_args()
 if opts.action == 'list':
  for n, (kind, key) in enumerate(actions(), 1):
   print(f"{n:2}. {kind:5} {key:10} : {SPECS[key]['port']:5} {SPECS[key]['label']}")
  return 0
 if opts.action == 'status':
  print_status(); return 0
 if opts.action == 'check':
  return 1 if check() else 0
 if opts.action == 'profile':
  # Day-1 baseline del GPU (GPU exclusivo): ver docs/GPU_SPEEDUP_ASSESSMENT_2026-09-22.md
  cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         str(ROOT / 'scripts' / 'profile_day1.ps1')]
  if opts.target == 'preflight':
   cmd.append('-Preflight')
  return subprocess.call(cmd)
 if opts.action == 'menu':
  return menu()
 if opts.action in ('logs', 'chat', 'start', 'switch', 'restart'):
  if not opts.target: raise SystemExit('Falta el modelo: por ejemplo "hub.py start bonsai2"')
  if opts.target not in SPECS: raise SystemExit(f'No conozco {opts.target} (mira "hub.py list")')
 if opts.action == 'logs':
  print(tail(opts.target)); return 0
 if opts.action == 'chat':
  chat(opts.target); return 0
 if opts.action == 'start':
  start(opts.target, opts.preset, opts.context, opts.force); return 0
 if opts.action in ('switch', 'restart'):
  switch(opts.target, opts.preset, opts.context); return 0
 if opts.action == 'stop':
  if opts.target in (None, 'all') or opts.all:
   print(stop(everything=True, include_apps=True)); return 0
  print(stop(opts.target)); return 0
 return 0


if __name__ == '__main__':
 try:
  sys.exit(main())
 except KeyboardInterrupt:
  sys.exit(130)
 except Exception as exc:
  print(f'Error: {exc}', file=sys.stderr); sys.exit(1)
