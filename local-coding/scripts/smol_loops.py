"""Detecta bucles: la misma llamada a herramienta repetida, o turnos con error seguidos, en registros de OMP.

Uso: python scripts/smol_loops.py [archivo.jsonl ...]
Sin argumentos analiza el ultimo run de Smol y las sesiones guardadas de los perfiles.
Solo informa; la interrupcion en vivo requeriria cambiar OMP.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def events(path):
 for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
  if line.startswith('{'):
   try: yield json.loads(line)
   except ValueError: pass

def analyze(path, streak=3):
 calls = errors = same = failing = worst_same = worst_failing = 0
 last = None
 for e in events(path):
  if e.get('type') != 'turn_end': continue
  for b in e.get('message', {}).get('content', []):
   if b.get('type') != 'toolCall': continue
   calls += 1
   sig = (b.get('name'), json.dumps(b.get('arguments', b.get('args')), sort_keys=True))
   same = same + 1 if sig == last else 1
   last = sig; worst_same = max(worst_same, same)
  bad = [r for r in e.get('toolResults') or [] if r.get('isError') or '"iserror":true' in json.dumps(r).lower()]
  errors += len(bad)
  failing = failing + 1 if bad else 0
  worst_failing = max(worst_failing, failing)
 return {'file': str(path), 'tool_calls': calls, 'tool_errors': errors,
  'max_identical_streak': worst_same, 'max_failing_streak': worst_failing,
  'loop': worst_same >= streak or worst_failing >= streak}

def default_files():
 runs = sorted((ROOT / 'data/smol/runs').glob('*/agent.jsonl'))
 return runs[-1:] + list((ROOT / 'data/smol/profiles').glob('*/sessions/**/*.jsonl'))

def main():
 files = [Path(a) for a in sys.argv[1:]] or default_files()
 if not files: print('Sin registros.'); return
 for f in files:
  r = analyze(f)
  print(f"{'BUCLE' if r['loop'] else 'ok':5} llamadas={r['tool_calls']} errores={r['tool_errors']} "
   f"racha_igual={r['max_identical_streak']} racha_error={r['max_failing_streak']}  {f}")

if __name__ == '__main__': main()
