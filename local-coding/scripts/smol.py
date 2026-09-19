"""Personal OMP launcher: one installed local model at a time."""
import argparse, ctypes, json, msvcrt, os, socket, subprocess, sys, time
from pathlib import Path
import httpx, psutil

import local_models as reg

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/smol'
OMP = Path(os.environ['USERPROFILE']) / '.bun/bin/omp.exe'
# Registro compartido con scripts/hub.py: una sola fuente de verdad (modelos, runtimes,
# presets, pisos de RAM). Editar local_models.py, no duplicar valores aqui.
RUNTIME = Path(reg.DEFAULT_RUNTIME)
PORT = reg.SMOL_PORT
CONTEXT = reg.SMOL_CONTEXT
CONTEXT_CHOICES = reg.CONTEXT_CHOICES
DEFAULT_CONTEXT = reg.DEFAULT_CONTEXT
RAM_FLOOR_MB = reg.RAM_FLOOR_MB
MODELS = reg.SMOL_MODELS
TEMPS = reg.TEMPS
RUNTIMES = reg.RUNTIMES
PRESETS = reg.PRESETS
DEFAULT_PRESET = reg.DEFAULT_PRESET
ROOTS = reg.MODEL_ROOTS
model_path = reg.model_path
default_context = reg.default_context
preset_ctx = reg.preset_ctx

def write_json(path, value):
 path.parent.mkdir(parents=True, exist_ok=True)
 temp = path.with_suffix(path.suffix + '.tmp')
 temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
 temp.replace(path)

def check_model(key):
 path = model_path(key)
 manifest_path = path.with_name(path.name + '.verified.json')
 if not manifest_path.exists(): manifest_path = path.parent / 'verified.json'
 manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
 if path.stat().st_size != manifest['bytes']:
  raise RuntimeError('Modelo distinto del archivo verificado: ' + str(path))
 return path

def load_budget(key):
 """Segundos de espera de carga: el HDD de Z: rinde ~34 MB/s secuencial (medido), margen a 20 MB/s."""
 return 120 + model_path(key).stat().st_size // (20 * 2**20)

def inventory():
 """Todos los GGUF de Z: y su estado frente a Smol y los 8 GB de VRAM. Solo informa; no borra."""
 smol_paths = {model_path(k).resolve() for k in MODELS}
 rows, seen = [], {}
 for root in map(Path, ROOTS):
  if not root.is_dir(): continue
  for p in root.rglob('*'):
   if not p.is_file(): continue
   size = p.stat().st_size; gb = size / 2**30
   if root.name == 'blobs':
    if size < 512 * 2**20: continue
    status = 'blob Ollama sin ollama.exe; llama-server lo carga por ruta'
   elif p.suffix.lower() != '.gguf': continue
   elif p.resolve() in smol_paths: status = 'Smol'
   elif gb < 1: status = 'muy chico: sidecar (mtp/mmproj) o descarga incompleta'
   elif gb <= 6.5: status = 'cabe en VRAM: register_local_model.py y sumar a MODELS'
   elif gb <= 9.5: status = 'solo carga parcial (-ngl bajo), lento'
   else: status = 'no entra en 8 GB de VRAM'
   first = seen.setdefault(p.name.lower(), p)
   if first is not p: status += ' | duplicado de ' + str(first)
   rows.append((gb, status, p))
 print('\nInventario GGUF en Z: (informativo, nada se borra)')
 for gb, status, p in sorted(rows, reverse=True): print(f'{gb:6.2f} GB  {p}\n           {status}')

def tool_caps(context):
 """OMP overlay: hard tool-output caps sized for the context window."""
 return {
  'tools': {'artifactSpillThreshold': 8, 'artifactHeadBytes': 2,
            'artifactTailBytes': 4, 'artifactTailLines': 60},
  'read': {'defaultLimit': 250},
  'shellMinimizer': {'maxCaptureBytes': 65536},
  'compaction': {'keepRecentTokens': 3000 if context <= 16384 else 6000}}

default_context = reg.default_context  # mismo criterio que el hub

def profile(key, thinking, context=None):
 ctx = context or default_context(key)
 path = DATA / 'profiles' / key
 kwargs = {'enable_thinking': thinking, 'preserve_thinking': True}
 if key == 'nanbeige': kwargs['tool_call_format'] = 'xml'
 if key == 'bonsai2': kwargs['enable_thinking'] = thinking
 compat = {
  'supportsStore': False, 'supportsDeveloperRole': False,
  'supportsReasoningEffort': False, 'maxTokensField': 'max_tokens',
  'reasoningContentField': 'reasoning_content',
  'requiresReasoningContentForToolCalls': True,
  'requiresReasoningContentForAllAssistantTurns': True,
  'allowsSyntheticReasoningContentForToolCalls': False,
  'extraBody': {'chat_template_kwargs': kwargs, 'max_tokens': -1,
                'temperature': 1.0 if thinking and key == 'nanbeige' else TEMPS.get(key, 0.3)}}
 write_json(path / 'models.yml', {'providers': {'smol': {
  'baseUrl': f'http://127.0.0.1:{PORT}/v1', 'api': 'openai-completions',
  'apiKey': 'local', 'auth': 'none', 'compat': compat,
  'models': [{'id': key, 'name': MODELS[key][0], 'reasoning': True,
              'contextWindow': ctx, 'maxTokens': ctx,
              'temperature': TEMPS.get(key, 0.3)}]}}})
 write_json(path / 'limits.json', tool_caps(ctx))
 if not (path / 'config.yml').exists():
  write_json(path / 'config.yml', {'setupVersion': 1, 'shellPath': 'C:/Program Files/Git/bin/bash.exe',
   'modelRoles': {role: f'smol/{key}' for role in ['default', 'smol', 'slow', 'plan']},
   'compaction': {'enabled': True, 'midTurnEnabled': True, 'thresholdPercent': 65}})
 return path

server_args = reg.smol_server_args  # argv medido de la ranura Smol, compartido con hub.py

def agent_args(key, project, mode, thinking, resume=False, prompt=None, approval='always-ask'):
 role = 'smol/' + key
 args = [str(OMP), '--cwd', str(project), '--model', role, '--smol', role,
  '--slow', role, '--plan', role, '--models', role,
  '--config', str(DATA / 'profiles' / key / 'limits.json'),
  '--thinking', 'medium' if thinking else 'off', '--no-title', '--no-extensions',
  '--no-skills', '--no-lsp', '--no-pty', '--no-prewalk']
 if mode == 'chat':
  args += ['--no-tools', '--no-rules', '--system-prompt',
   "You are a helpful local assistant. Reply in the user's language. Be concise and direct. "
   "You have no tools in this mode. Do not emit tool calls or js/node_repl/browser code; answer in text only."]
 else:
   tools = 'read,write,grep,glob,bash' if key == 'mini' else 'read,write,edit,grep,glob,bash'
   args += ['--tools', tools, '--approval-mode', approval,
   '--system-prompt', 'You are a local coding assistant working inside the user\'s project with tools. '
    'Only these tools exist: read,write,edit,grep,glob,bash. Never call js, node_repl, browser, status-bar, '
    'or any other tool; never use require, process, node:process, window, or document. '
    'When the user asks for a change, make it now: read the file with the read tool, then apply the change in this same turn. '
    'Never answer with instructions or code for the user to paste; the edit is your answer. '
    'For changes of a few lines, use the write tool to save the complete file with the change applied. '
    'Make exactly the requested change and nothing else; preserve unrelated work and existing tests. '
   'If a tool call fails twice the same way, stop and tell the user what failed instead of retrying. '
   'If you cannot make the change, say in one sentence what is blocking you. '
   'Run relevant tests when they exist and use actual failures to correct your changes; never claim tests passed without their output. '
   'Ask before destructive commands. Reply briefly, in the user\'s language.']
 if resume: args.append('--continue')
 if prompt is not None: args += ['--print', '--mode', 'json', '--no-session', prompt]
 return args

class RuntimeJob:
 """Closing the launcher kills its owned backend, even on a window close."""
 def __init__(self):
  from ctypes import wintypes as w
  class BASIC(ctypes.Structure):
   _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
    ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
    ('process_limit', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
  class IO(ctypes.Structure):
   _fields_ = [(n, ctypes.c_uint64) for n in ['read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes']]
  class EXT(ctypes.Structure):
   _fields_ = [('basic', BASIC), ('io', IO), ('process_mem', ctypes.c_size_t),
    ('job_mem', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
  self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
  self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
  self.kernel.CreateJobObjectW.restype = w.HANDLE
  self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
  self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
  self.kernel.CloseHandle.argtypes = [w.HANDLE]
  self.handle = self.kernel.CreateJobObjectW(None, None)
  if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
  info = EXT(); info.basic.flags = 0x2000
  if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
   self.close(); raise ctypes.WinError(ctypes.get_last_error())
 def assign(self, process):
  if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
   raise ctypes.WinError(ctypes.get_last_error())
 def close(self):
  if self.handle:
   self.kernel.CloseHandle(self.handle); self.handle = None

def stop(process):
 if process and process.poll() is None:
  process.terminate()
  try: process.wait(timeout=15)
  except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)

def loop_check(profile_dir, since):
 """Revisa las sesiones escritas desde `since` y avisa si el modelo entro en bucle de herramientas."""
 from smol_loops import analyze
 rows = [analyze(p) for p in profile_dir.glob('sessions/**/*.jsonl') if p.stat().st_mtime >= since]
 for r in rows:
  if r['loop']:
   print(f"Aviso: bucle de herramientas ({r['max_identical_streak']} llamadas iguales seguidas, "
    f"{r['max_failing_streak']} turnos con error seguidos). Cambia la instruccion o el modelo.", flush=True)
 return rows

def find_prior():
 prior = None
 for p in psutil.process_iter(['pid','name','exe','cmdline','create_time']):
  i = p.info
  if (i['name'] or '').lower() != 'llama-server.exe': continue
  try:
   cmd = i['cmdline']
  except psutil.AccessDenied:
   cmd = None
  if not cmd:
   # Residuo inalcanzable (trabajo huerfano con ACL): solo bloquea si ocupa un puerto Smol.
   continue
  known = i['exe'] and Path(i['exe']).resolve() == Path('Z:/ai/llama.cpp/llama-server.exe').resolve()
  if prior or not known or '8123' not in cmd or not any('qwen2.5-coder-7b-instruct-q4_k_m.gguf' in a for a in cmd):
   raise RuntimeError('Otro servidor de modelos esta activo. Cerralo antes de abrir Smol.')
  prior = i
 return prior

preset_ctx = reg.preset_ctx

def run(key, mode, project, thinking, resume=False, smoke=False, context=None, preset=None):
 preset = preset or DEFAULT_PRESET.get(key)
 if preset is not None and preset not in [n for n, _, _ in PRESETS.get(key, [])]:
  raise RuntimeError(f'Preset desconocido para {key}: {preset}')
 ctx = context or preset_ctx(key, preset)
 check_model(key)
 if not project.is_dir(): raise RuntimeError('No existe la carpeta: ' + str(project))
 with socket.socket() as sock:
  if sock.connect_ex(('127.0.0.1', PORT)) == 0: raise RuntimeError(f'Puerto {PORT} ocupado')
 prior = find_prior()
 journal = DATA / 'runs' / time.strftime('%Y%m%d-%H%M%S')
 journal.mkdir(parents=True)
 report = {'model': key, 'mode': mode, 'project': str(project), 'thinking': thinking,
  'preset': preset, 'context': ctx, 'output_limit': 'remaining context; no trial time/token cap',
  'tool_caps': tool_caps(ctx)}
 env = os.environ.copy()
 env['PI_CODING_AGENT_DIR'] = str(profile(key, thinking, ctx))
 env.pop('OMP_PROFILE', None)
 env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM'] = '1'
 runtime = agent = job = None
 paused = False
 try:
  if prior:
   write_json(journal / 'prior-server.json', {'executable': prior['exe'],
    'argumentLine': subprocess.list2cmdline(prior['cmdline'][1:]), 'pid': prior['pid']})
   p = psutil.Process(prior['pid'])
   if p.create_time() != prior['create_time'] or p.cmdline() != prior['cmdline']:
    raise RuntimeError('El servidor previo cambio')
   p.terminate(); paused = True; p.wait(timeout=20)
   print('Qwen pausado; se restaura al salir.', flush=True)
  floor_mb = RAM_FLOOR_MB.get(key, 1536)
  if psutil.virtual_memory().available < floor_mb * 2**20:
   raise RuntimeError(f'Menos de {floor_mb // 1024} GB de RAM libre para {MODELS[key][0]}. Cerra aplicaciones pesadas.')
  job = RuntimeJob()
  with (journal / 'server.log').open('w', encoding='utf-8') as log:
   argv = server_args(key, thinking, ctx, preset)
   report['server_args'] = argv
   runtime = subprocess.Popen(argv, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
   job.assign(runtime)
   report['server_pid'] = runtime.pid
   write_json(journal / 'session.json', report)
  budget = load_budget(key)
  print(f'Cargando {MODELS[key][0]} ... (desde HDD, hasta ~{budget // 60} min)', flush=True)
  deadline = time.monotonic() + budget
  with httpx.Client(base_url=f'http://127.0.0.1:{PORT}', timeout=3) as client:
   while time.monotonic() < deadline:
    if runtime.poll() is not None: raise RuntimeError('El modelo no pudo cargar. Ver ' + str(journal / 'server.log'))
    try:
     if client.get('/health').status_code == 200: break
    except httpx.HTTPError: pass
    time.sleep(1)
   else: raise RuntimeError('La carga tardo demasiado. Ver ' + str(journal / 'server.log'))
   if client.get('/v1/models').json()['data'][0]['id'] != key: raise RuntimeError('Modelo inesperado')
  print('Listo. Esc: interrumpir respuesta. /resume: sesiones. /exit: volver al menu.', flush=True)
  prompt = ('Read SMOL_CHECK.txt using the read tool and return its exact contents.' if mode == 'project' else 'Reply with exactly SMOL_READY.') if smoke else None
  argv = agent_args(key, project, mode, thinking, resume, prompt)
  report['agent_args'] = argv
  if smoke:
   with (journal / 'agent.jsonl').open('w', encoding='utf-8') as out, (journal / 'agent.stderr.log').open('w', encoding='utf-8') as err:
    agent = subprocess.Popen(argv, env=env, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    agent.wait(timeout=180)
   events = [json.loads(line) for line in (journal / 'agent.jsonl').read_text(encoding='utf-8').splitlines() if line.startswith('{')]
   answers = [e.get('message', {}) for e in events if e.get('type') == 'message_end' and e.get('message', {}).get('role') == 'assistant']
   report['smoke_passed'] = bool(answers) and agent.returncode == 0 and all(m.get('stopReason') != 'error' for m in answers) and any(b.get('type') == 'text' and 'SMOL_READY' in b.get('text', '') for m in answers for b in m.get('content', []))
   if not report['smoke_passed']: raise RuntimeError('OMP smoke failed; see ' + str(journal))
  else:
   started = time.time()
   agent = subprocess.Popen(argv, env=env)
   agent.wait()
   report['loops'] = loop_check(Path(env['PI_CODING_AGENT_DIR']), started)
  report['agent_exit'] = agent.returncode
 finally:
  stop(agent); stop(runtime)
  if job: job.close()
  report['server_stopped'] = runtime is None or runtime.poll() is not None
  write_json(journal / 'session.json', report)
  if paused:
   subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
    str(ROOT / 'scripts/restore_e4b_prior_server.ps1'),'-Journal',str(journal)], check=True, timeout=200)
  print('Modelo cerrado. Registro: ' + str(journal), flush=True)

def main():
 parser = argparse.ArgumentParser(description='Smol local: OMP + modelos instalados')
 parser.add_argument('project', nargs='?', type=Path)
 parser.add_argument('--model', choices=MODELS)
 parser.add_argument('--preset', help='Preset de arranque (ver menu por modelo); default = recomendado')
 parser.add_argument('--mode', choices=['chat','project'])
 parser.add_argument('--thinking', choices=['on','off'])
 parser.add_argument('--context', type=int, choices=CONTEXT_CHOICES,
  help='Ventana de contexto; 32K validado para todos los modelos (sonda 2026-09-10)')
 parser.add_argument('--continue', dest='resume', action='store_true')
 parser.add_argument('--docs', action='store_true', help='Leer la guia sin cargar un modelo')
 parser.add_argument('--check', action='store_true')
 parser.add_argument('--smoke', action='store_true')
 opts = parser.parse_args()
 if opts.docs:
  print((ROOT / 'docs/SMOL.md').read_text(encoding='utf-8')); return
 for path in (RUNTIME, OMP):
  if not path.is_file(): raise RuntimeError('Falta: ' + str(path))
 if opts.check:
  for key in MODELS: check_model(key); print('OK ' + MODELS[key][0])
  print('OMP y runtime presentes. No se cargo ningun modelo.')
  inventory(); return
 DATA.mkdir(parents=True, exist_ok=True)
 lock = (DATA / 'launcher.lock').open('a+b')
 try:
  lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
 except OSError:
  lock.close(); raise RuntimeError('Smol ya esta abierto en otra ventana.')
 try:
  settings_path = DATA / 'last.json'
  settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
  while True:
   keys = list(MODELS)
   key = opts.model
   quick = False
   if key is None:
    print('\nSMOL LOCAL\n')
    for n,k in enumerate(keys,1): print(f'  {n}. {MODELS[k][0]}')
    print('  ?. Ayuda: como usarlo y como funciona\n  0. Salir')
    selected = input('Enter: MiniCPM ediciones simples | numero: configurar modelo: ').strip()
    if selected.lower() in ('?', 'help', 'ayuda'):
     print((ROOT / 'docs/SMOL.md').read_text(encoding='utf-8'))
     input('Enter para volver al menu: ')
     continue
    quick = not selected
    selected = selected or '1'
    if selected == '0': return
    if not selected.isdigit() or not 1 <= int(selected) <= len(keys): continue
    key = keys[int(selected)-1]
   mode = opts.mode or ('project' if opts.project or quick else None)
   if mode is None: mode = 'project' if input('1. Chat  2. Proyecto [1]: ').strip() == '2' else 'chat'
   project = opts.project
   if mode == 'project' and project is None:
    previous = settings.get('project','')
    text = input('Carpeta del proyecto' + (f' [{previous}]' if previous else '') + ': ').strip().strip('"') or previous
    if not text: continue
    project = Path(text)
   if mode == 'chat':
    project = DATA / 'chat'; project.mkdir(parents=True, exist_ok=True)
   project = project.resolve()
   default_thinking = key == 'nanbeige'
   thinking = opts.thinking == 'on' if opts.thinking else default_thinking
   if opts.model is None and not quick:
    choice = input('Razonamiento: 1. Rapido  2. Pensar [' + ('2' if default_thinking else '1') + ']: ').strip()
    if choice: thinking = choice == '2'
   resume = opts.resume
   if opts.model is None and not quick: resume = input('1. Conversacion nueva  2. Continuar anterior [1]: ').strip() == '2'
   preset = opts.preset
   if preset is None and opts.model is None and not quick and key in PRESETS:
    options = PRESETS[key]
    print('Forma de arranque:')
    for n, (name, desc, _) in enumerate(options, 1):
     print(f'  {n}. {name} - {desc}')
    pick = input(f'Enter = {options[0][0]}: ').strip()
    if pick:
     if not pick.isdigit() or not 1 <= int(pick) <= len(options): continue
     preset = options[int(pick) - 1][0]
   if mode == 'project': settings['project'] = str(project)
   settings.update(model=key, thinking=thinking, preset=preset)
   write_json(settings_path, settings)
   print('Esc: detener respuesta | /exit: volver | /new: empezar de cero | /resume: recuperar')
   print('Contexto: ' + str((opts.context or preset_ctx(key, preset)) // 1024) + 'K. Sin limite de minutos. Respuestas hasta completar o llenar el contexto.')
   try: run(key,mode,project,thinking,resume,opts.smoke,opts.context,preset)
   except KeyboardInterrupt: print('\nSesion interrumpida.')
   except Exception as e:
    print('Error: ' + str(e))
    if opts.model or opts.smoke: raise
   if opts.model or opts.smoke: return
 finally: lock.close()

if __name__ == '__main__':
 try: main()
 except KeyboardInterrupt: pass
 except Exception as exc:
  print('Error: ' + str(exc), file=sys.stderr); sys.exit(1)
