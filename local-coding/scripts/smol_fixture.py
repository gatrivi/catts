"""Humo de edicion: fixture React minimo, tarea 'mover el div', verifica que la edicion quedo aplicada.

Uso: python scripts/smol_fixture.py --model qwen35 coder7
Un modelo por vez en el puerto de Smol; se detiene al terminar cada uno.
Resultado: data/smol/fixture-runs/<ts>/rows.jsonl y el estado final de App.jsx.
Es verificacion funcional del launcher y del prompt, no un ensayo comparativo de modelos.
"""
import argparse, json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent))
import smol
from smol_loops import analyze

APP = '''export default function App() {
  return (
    <div className="app">
      <Header />
      <div className="promo-banner">Summer sale</div>
      <Main />
      <footer className="site-footer">&copy; 2026</footer>
    </div>
  )
}
'''
TASK = ('Move the promo-banner div so it renders after the site-footer footer element. '
 'Make the edit with the edit tool now.')

def passed(path):
 text = path.read_text(encoding='utf-8')
 return (text.count('promo-banner') == 1 and 'Header' in text and 'Main' in text
  and text.index('promo-banner') > text.index('site-footer'))

def run_fixture(key, env, out_dir, task='move-div'):
 fixture = out_dir / (key + '-fixture'); fixture.mkdir(parents=True, exist_ok=True)
 button = '.button {\n  height: 32px;\n  padding: 8px 16px;\n  color: white;\n}\n'
 app = fixture / ('Button.css' if task == 'button-size' else 'App.jsx')
 app.write_text(button if task == 'button-size' else APP, encoding='utf-8')
 prompt = ('In Button.css, change .button height from 32px to 44px. Change nothing else. '
           'Read the file, then apply the edit now.') if task == 'button-size' else TASK
 row = {'model': key, 'context': smol.default_context(key)}
 job = smol.RuntimeJob()
 with (out_dir / (key + '-server.log')).open('w', encoding='utf-8') as log:
  server = subprocess.Popen(smol.server_args(key, False), env=env, stdout=log, stderr=log,
   creationflags=subprocess.CREATE_NO_WINDOW)
  job.assign(server)
 try:
  deadline = time.monotonic() + smol.load_budget(key)
  with httpx.Client(base_url=f'http://127.0.0.1:{smol.PORT}', timeout=5) as client:
   while time.monotonic() < deadline:
    if server.poll() is not None: row['result'] = 'server_exited:' + str(server.returncode); return row
    try:
     if client.get('/health').status_code == 200: break
    except httpx.HTTPError: pass
    time.sleep(1)
   else: row['result'] = 'server_timeout'; return row
   argv = smol.agent_args(key, fixture, 'project', False, prompt=prompt, approval='write') + ['--max-time', '600', '-e', str(smol.ROOT / 'scripts/smol_loop_guard.mjs')]
   guard_env = dict(env, SMINI_LOOP_LOG=str(out_dir / (key + '-guard.jsonl')))
   with (out_dir / (key + '-agent.jsonl')).open('w', encoding='utf-8') as out, \
        (out_dir / (key + '-agent.stderr.log')).open('w', encoding='utf-8') as err:
    agent = subprocess.Popen(argv, env=guard_env, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    job.assign(agent)
    try: agent.wait(timeout=660)
    except subprocess.TimeoutExpired: agent.kill(); row['result'] = 'agent_timeout'; return row
   row['agent_exit'] = agent.returncode
   row['loops'] = analyze(out_dir / (key + '-agent.jsonl'))['loop']
   correct = app.read_text(encoding='utf-8') == button.replace('32px', '44px') if task == 'button-size' else passed(app)
   row['task'] = task
   row['result'] = 'pass' if correct and agent.returncode == 0 else 'fail_no_edit'
   row['app_after'] = app.read_text(encoding='utf-8')
 finally:
  smol.stop(server); job.close()
 return row

def main():
 parser = argparse.ArgumentParser(description='Humo de edicion sobre fixture React')
 parser.add_argument('--models', nargs='+', choices=smol.MODELS, default=['qwen35', 'coder7'])
 parser.add_argument('--task', choices=['move-div','button-size'], default='move-div')
 opts = parser.parse_args()
 if smol.find_prior(): raise RuntimeError('Servidor existente preservado; cerralo antes de la prueba.')
 for key in opts.models: smol.check_model(key)
 with socket.socket() as sock:
  if sock.connect_ex(('127.0.0.1', smol.PORT)) == 0: raise RuntimeError(f'Puerto {smol.PORT} ocupado')
 env = dict(os.environ, GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM='1',
  PI_CODING_AGENT_DIR=str(smol.profile(opts.models[0], False)))
 env.pop('OMP_PROFILE', None)
 out_dir = smol.DATA / 'fixture-runs' / time.strftime('%Y%m%d-%H%M%S'); out_dir.mkdir(parents=True)
 with (out_dir / 'rows.jsonl').open('a', encoding='utf-8') as out:
   for key in opts.models:
    env['PI_CODING_AGENT_DIR'] = str(smol.profile(key, False))
    row = run_fixture(key, env, out_dir, opts.task)
   out.write(json.dumps(row) + '\n'); out.flush()
   print(json.dumps({k: row[k] for k in row if k != 'app_after'}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
 try: main()
 except KeyboardInterrupt: pass
 except Exception as exc:
  print('Error: ' + str(exc), file=sys.stderr); sys.exit(1)
