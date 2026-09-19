"""Registro unico de servidores locales (Smol, Taller, hub) y de las apps de CATTS.

Fuente de verdad de: modelos, puertos, alias, runtime por modelo, presets de
arranque y pisos de RAM. Lo usan scripts/smol.py, scripts/hub.py y los
lanzadores de Taller. Nada aqui carga un modelo: solo describen como arrancarlo.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = r'E:\zengatrivi-drive-e\catts\.venv\Scripts\python.exe'
DEFAULT_RUNTIME = 'Z:/models/runtime/llama-vulkan/llama-server.exe'
PRISM_RUNTIME = 'Z:/models/runtime/llama-prism-b10685-vulkan/llama-server.exe'
B10964_RUNTIME = 'Z:/models/runtime/llama-vulkan-b10964/llama-server.exe'

# --- Modelos que Smol puede servir, todos en el puerto 9104 con alias = clave ---
SMOL_PORT = 9104
SMOL_CONTEXT = 32768
CONTEXT_CHOICES = (16384, 24576, 32768)
SMOL_MODELS = {
 'mini': ('MiniCPM5 2B - rapido', 'minicpm5-2b-q8/MiniCPM5-2B-Q8_0.gguf'),
 'nanbeige': ('Nanbeige 4.2 3B - razonamiento', 'nanbeige42-q8/Nanbeige4.2-3B-Q8_0.gguf'),
 'e4b': ('Gemma E4B QAT', 'gemma-e4b-qat/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf'),
 'bonsai': ('Bonsai 27B Q1', 'bonsai27-q1/Bonsai-27B-Q1_0.gguf'),
 'qwen35': ('Qwen3.5 9B - editor', 'Z:/Models/coding/Qwen3.5-9B/Qwen3.5-9B-Q4_K_M.gguf'),
 'coder7': ('Qwen2.5 Coder 7B - codigo', 'Z:/Models/coding/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf'),
 'gemma12': ('Gemma 12B coder - mas pesado', 'gemma4-coder-q3/gemma4-coding-Q3_K_M.gguf'),
 'neo': ('NeoHorse 1 4B - agente local', 'neohorse14b-q8/NeoHorse-1-4B-Q8_0.gguf'),
 'bonsai2': ('Bonsai-2 27B TQ2 - consultor pesado', 'bonsai2-27b-tq2_0/Ternary-Bonsai-2-27B-TQ2_0.gguf'),
 'spark': ('Spark-X2.5 4B - 1M ctx', 'spark25/Spark-X2.5-4B-Q8_0.gguf'),
 'qwen27': ('Qwen3.8 27B Q3 - consultor experto', 'Z:/Models/coding/Qwen3.8-27B-Q3-DOWN-XS/Qwen3.8-27B-Q3-DOWN-XS.gguf'),
}
TEMPS = {'qwen35': 0.2, 'coder7': 0.2, 'neo': 0.2, 'spark': 0.2}
# Runtime por modelo: los nuevos no cargan con llama-vulkan b10964 (arch nuevas / ternary).
RUNTIMES = {'bonsai2': PRISM_RUNTIME, 'spark': B10964_RUNTIME, 'neo': B10964_RUNTIME}
# Presets de arranque estilo esfuerzo low/mid/high. Cada uno ajusta args del server.
PRESETS = {
 'bonsai2': [
  ('mid', 'Estandar: todo GPU, 8K, ~12-13 tok/s (medido)', {}),
  ('low', 'Liviano: 40 capas GPU, 4K, KV q4 (usa poca VRAM, ~1 tok/s)', {'-ngl': '40', '-c': '4096', '-ctk': 'q4_0', '-ctv': 'q4_0'}),
  ('high', 'Ambicioso: 32K ctx (cae a ~3 tok/s, KV empuja pesos a RAM)', {'-c': '32768'}),
 ],
 'spark': [
  ('fast', 'Rapido: 16K, KV q8 (medido 16.5 tok/s)', {'-c': '16384'}),
  ('balanced', 'Equilibrado: 64K, KV q8', {'-c': '65536'}),
  ('max', 'Maximo: 131K, KV q4 (lento, contexto enorme)', {'-c': '131072', '-ctk': 'q4_0', '-ctv': 'q4_0'}),
 ],
 'qwen27': [
  ('mid', 'Estandar: 56 capas GPU, 4K, KV q8 (perfil consultor medido)', {'-ngl': '56', '-c': '4096'}),
  ('low', 'Liviano: 32 capas GPU, 4K, KV q4 (entra con otros procesos)', {'-ngl': '32', '-c': '4096', '-ctk': 'q4_0', '-ctv': 'q4_0'}),
 ],
}
DEFAULT_PRESET = {k: v[0][0] for k, v in PRESETS.items()}  # el primero es el recomendado/medido
DEFAULT_CONTEXT = {'nanbeige': 16384, 'bonsai2': 8192, 'qwen27': 4096}  # nanbeige: a 32K ocupa 6.7 GB VRAM; bonsai2/qwen27: perfiles medidos
RAM_FLOOR_MB = {'e4b': 2800, 'gemma12': 1800, 'qwen27': 6200, 'bonsai2': 3000}  # piso = RSS pico medido + margen; el resto, 1.5 GB
MODEL_ROOTS = ('Z:/Models/coding', 'Z:/AI/models', 'Z:/LocalModels', 'Z:/ollama/models/blobs', ROOT / 'data/models')


def model_path(key):
 rel = Path(SMOL_MODELS[key][1])
 return rel if rel.is_absolute() else ROOT / 'data/models' / rel


def default_context(key):
 return DEFAULT_CONTEXT.get(key, SMOL_CONTEXT)


def preset_ctx(key, preset):
 if preset:
  for n, _, overrides in PRESETS.get(key, []):
   if n == preset and '-c' in overrides: return int(overrides['-c'])
 return default_context(key)


def smol_server_args(key, thinking, context=None, preset=None):
 """argv de llama-server para la ranura Smol (puerto 9104, alias = clave)."""
 # --no-mmap: Z: es un HDD; la lectura secuencial carga ~2x mas rapido que paginar por mmap,
 # y con todo en VRAM (-ngl 999) el proceso usa <1 GB de RAM (medido: 876 MB pico con 5.7 GB).
 args = [RUNTIMES.get(key, DEFAULT_RUNTIME), '-m', str(model_path(key)), '--host', '127.0.0.1',
  '--port', str(SMOL_PORT), '--alias', key, '--device', 'Vulkan1', '-ngl', '999',
  '-c', str(context or default_context(key)), '-np', '1', '-ctk', 'q8_0', '-ctv', 'q8_0', '-fa', 'on',
  '--jinja', '--no-warmup', '--no-mmap', '-b', '256', '-ub', '128',
  '--reasoning-format', 'deepseek', '--no-context-shift', '-n', '-1',
  '--cache-reuse', '256']
 if key == 'nanbeige':
  args += ['--override-kv', 'nanbeige.block_count=int:22,nanbeige.num_loops=int:2']
 if key == 'bonsai2':
  args += ['--temp', '0.6', '--top-p', '0.95', '--top-k', '20']
 if preset:
  overrides = next((o for n, _, o in PRESETS.get(key, []) if n == preset), None)
  if overrides is None: raise RuntimeError(f'Preset desconocido para {key}: {preset}')
  if context is not None: overrides = {k: v for k, v in overrides.items() if k != '-c'}
  i = 0
  while i < len(args) - 1:
   if args[i] in overrides: args[i + 1] = overrides[args[i]]
   i += 1
 if key == 'bonsai2':
  args = [a for a in args if a not in ('--reasoning-format', '--no-context-shift')]
 return args


# Preset extra de la ranura Smol: MiniCPM con contexto largo (necesita la VRAM sola).
PRESETS['mini'] = [
 ('mid', 'Estandar: 32K, KV q8 (entra junto al escritorio)', {}),
 ('long', '131K ctx: necesita la VRAM sola (~7 GB), carga lenta', {'-c': '131072'}),
]
DEFAULT_PRESET['mini'] = 'mid'
# Plantillas que aceptan el kwarg para apagar el razonamiento.
THINKING_KWARG_OK = set(SMOL_MODELS) - {'spark'}

# --- Servidores sueltos: puerto y alias fijos (lo que Zed ya tiene configurado) ---
STANDALONE = {
 'bonsai2': {
  'label': 'Bonsai-2 27B TQ2 (consultor pesado)', 'port': 9103, 'alias': 'bonsai2',
  'runtime': PRISM_RUNTIME, 'model': ROOT / 'data/models/bonsai2-27b-tq2_0/Ternary-Bonsai-2-27B-TQ2_0.gguf',
  'args': ['--device', 'Vulkan1', '-ngl', '99', '-c', '8192', '-np', '1', '-ctk', 'q8_0', '-ctv', 'q8_0',
   '-fa', 'on', '--jinja', '--no-warmup', '-b', '256', '-ub', '128',
   '--temp', '0.6', '--top-p', '0.95', '--top-k', '20'],
  'presets': PRESETS['bonsai2'], 'ram_floor_mb': 3000, 'zed': ('bonsai2', 'bonsai2'),
  'note': 'GPU exclusiva; 100K ctx no conviene (medido 3.2 tok/s).'},
 'spark': {
  'label': 'Spark-X2.5 4B (1M ctx anunciado)', 'port': 9105, 'alias': 'spark25',
  'runtime': B10964_RUNTIME, 'model': ROOT / 'data/models/spark25/Spark-X2.5-4B-Q8_0.gguf',
  'args': ['-ngl', '99', '-c', '16384', '-np', '1', '-fa', 'on', '--no-warmup', '--jinja'],
  'presets': PRESETS['spark'], 'ram_floor_mb': 1536, 'zed': ('spark', 'spark25'),
  'note': 'Medido 16.5 tok/s; ctx >16K sin validar.'},
 'neohorse': {
  'label': 'NeoHorse-1 4B (router rapido)', 'port': 9107, 'alias': 'neohorse',
  'runtime': B10964_RUNTIME, 'model': ROOT / 'data/models/neohorse14b-q8/NeoHorse-1-4B-Q8_0.gguf',
  'args': ['--device', 'Vulkan1', '-ngl', '99', '-c', '16384', '-np', '1', '-ctk', 'q8_0', '-ctv', 'q8_0',
   '-fa', 'on', '--jinja', '--no-warmup', '--temp', '0.5', '--top-p', '0.85', '--top-k', '20'],
  'presets': [], 'ram_floor_mb': 1536, 'zed': ('neohorse', 'neohorse'),
  'note': '36 tok/s medido; tool calls nativos OK.'},
 'qwen35': {
  'label': 'Qwen3.5 9B (editor de Taller)', 'port': 9102, 'alias': 'qwen35-local',
  'runtime': DEFAULT_RUNTIME, 'model': Path('Z:/models/coding/Qwen3.5-9B/Qwen3.5-9B-Q4_K_M.gguf'),
  'args': ['--device', 'Vulkan1', '-ngl', '99', '-c', '16384', '-np', '1', '-ctk', 'q8_0', '-ctv', 'q8_0',
   '-fa', 'on', '--jinja', '--reasoning', 'off', '--reasoning-format', 'none',
   '--chat-template-kwargs', '{"enable_thinking":false}', '--no-warmup', '--temp', '0.2',
   '--no-mmap', '--cache-reuse', '256'],
  'presets': [], 'ram_floor_mb': 2048, 'zed': ('qwen35-local', 'qwen35-local'),
  'note': 'Todo en VRAM; proceso <1 GB de RAM.'},
 'qwen27': {
  'label': 'Qwen3.8 27B Q3 (consultor de Taller)', 'port': 9101, 'alias': 'qwen27-local',
  'runtime': DEFAULT_RUNTIME, 'model': Path('Z:/models/coding/Qwen3.8-27B-Q3-DOWN-XS/Qwen3.8-27B-Q3-DOWN-XS.gguf'),
  'args': ['--device', 'Vulkan1', '-ngl', '56', '-c', '4096', '-np', '1', '-ctk', 'q8_0', '-ctv', 'q8_0',
   '-fa', 'on', '--jinja', '--reasoning', 'off', '--reasoning-format', 'none',
   '--chat-template-kwargs', '{"enable_thinking":false}', '--no-warmup', '--temp', '0.2',
   '--no-mmap', '--cache-reuse', '256', '-b', '128', '-ub', '128'],
  'presets': PRESETS['qwen27'], 'ram_floor_mb': 6144, 'zed': ('qwen27-local', 'qwen27-local'),
  'note': 'Capas en RAM: pide 6 GB libres y es lento (consultor, no editor).'},
}

# --- Apps del proyecto (mismo hub, mismo terminal) ---
APPS = {
 'catts': {
  'label': 'CATTS API (TTS/OCR/agente)', 'port': 59200, 'cwd': ROOT,
  'argv': [PYTHON, '-m', 'api.main'], 'ram_floor_mb': 1024,
  'note': 'Interfaz web en http://127.0.0.1:59200'},
 'chores': {
  'label': 'Chores API (Kaizen del hogar)', 'port': 9111, 'cwd': ROOT,
  'argv': [PYTHON, 'scripts/chores_api.py', '--port', '9111'], 'ram_floor_mb': 1024,
  'check_argv': [PYTHON, 'scripts/chores_api.py', '--check'], 'note': 'Habla con :9104 (Smol) y Piper.'},
 'voicegw': {
  'label': 'Gateway de voz (proxya :9104)', 'port': 9110, 'cwd': ROOT,
  'argv': [PYTHON, 'scripts/voice_gateway.py', '--port', '9110'], 'ram_floor_mb': 512,
  'check_argv': [PYTHON, 'scripts/voice_gateway.py', '--check'], 'note': 'No carga modelos; requiere uno arriba.'},
}


def standalone_args(key, preset=None):
 spec = STANDALONE[key]
 args = [spec['runtime'], '-m', str(spec['model']), '--host', '127.0.0.1',
  '--port', str(spec['port']), '--alias', spec['alias']] + list(spec['args'])
 if preset:
  overrides = next((o for n, _, o in spec['presets'] if n == preset), None)
  if overrides is None: raise RuntimeError(f'Preset desconocido para {key}: {preset}')
  i = 0
  while i < len(args) - 1:
   if args[i] in overrides: args[i + 1] = overrides[args[i]]
   i += 1
 return args