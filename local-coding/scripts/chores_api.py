"""Chores API: prompts in over HTTP, local Smol models do the work.

Superset of voice_gateway.py (same chat proxy + CORS): adds model
lifting and one agentic turn endpoint. The "pseudo-CLI pasting strings
into the input field" is OMP itself: --print --mode json --no-session
feeds the API string as the prompt, non-interactively, with tools.

  GET  /health                  {api, server_live, owner, model}
  GET  /models                  [{id, name, loaded}]
  POST /models/load  {model, thinking?, context?}   lift a model (loads GBs to VRAM)
  POST /models/stop              stop the API-owned server only
  POST /v1/chat/completions      streamed chat proxy (needs a loaded model)
  POST /agent/turn   {prompt, project?, max_time?}
     one tool turn in an operator-approved project root. Tools are
     read,grep,glob (+write,edit when --allow-writes); bash is never
     exposed. approval is not caller-configurable: 'approval' in the
     body is rejected. The API caller IS the approver: set
     CHORES_API_TOKEN and send 'Authorization: Bearer <token>';
     add --allow-origin for browser CORS. Requests without a token
     configured are rejected (401), so accidental open binding fails
     closed.
   POST /notes/organize {transcript} -> {title, body, tasks, recap, model}
     one non-stream chat call with the organizer prompt. Frontend saves
     the result to Firebase and reads `recap` back (browser speech now,
     CATTS TTS next).
   POST /notes/speak {text, voice?} -> {audio_url, voice, chars}
     proxies E: Piper TTS (CATTS_PIPER_URL or :8881), caches wav by hash.
   GET  /audio/<sha>.wav   cached speech audio for the phone <audio> tag.

  python scripts/chores_api.py --port 9111
  python scripts/chores_api.py --check      # no servers, no loads
Single owner: if SMOL.cmd (or anything) holds :9104, load refuses with
409; if the API owns it, SMOL.cmd will refuse in turn. One model at a time.
"""
import argparse, hashlib, hmac, ipaddress, json, os, socket, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import smol as S  # constants + server_args/agent_args/profile; no launches

UPSTREAM = f'http://127.0.0.1:{S.PORT}'
PIPER_URL = os.environ.get('CATTS_PIPER_URL', 'http://127.0.0.1:8881').rstrip('/')
INBOX = ROOT / 'data/chores/inbox'
JOURNAL = ROOT / 'data/chores/runs'
AUDIO = ROOT / 'data/chores/audio'
MAX_PROMPT = 64 * 1024
MAX_SPEAK = 4000

ORGANIZE_SYSTEM = (
    'Eres un organizador de notas personales. Te llega la transcripcion de '
    'una nota de voz (puede tener errores de dictado; corrige lo obvio sin '
    'inventar datos). Devuelve SOLO un JSON valido, sin markdown ni texto '
    'extra, con estas claves: "title" (titulo corto), "body" (nota limpia en '
    'markdown breve), "tasks" (lista de tareas concretas [] si no hay), '
    '"recap" (resumen de 2-3 frases, tono claro, pensado para leerse en voz '
    'alta como recap de la nota).'
)

state = {'server': None, 'model': None, 'thinking': None,
         'context': None, 'busy': False}
lock = threading.Lock()


def port_busy():
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1', S.PORT)) == 0


def upstream_live():
    try:
        with urlrequest.urlopen(UPSTREAM + '/health', timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def upstream_model():
    try:
        with urlrequest.urlopen(UPSTREAM + '/v1/models', timeout=5) as r:
            data = json.loads(r.read().decode())
            return (data.get('data') or [{}])[0].get('id')
    except Exception:
        return None


def start_server(key, thinking, context):
    S.check_model(key)
    argv = S.server_args(key, thinking, context)
    env = dict(os.environ)
    env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM'] = '1'
    log = JOURNAL / time.strftime('%Y%m%d-%H%M%S') / 'server.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(argv, env=env, stdout=open(log, 'w', encoding='utf-8'),
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + S.load_budget(key)
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('server died on launch; see ' + str(log))
        if upstream_live():
            return proc
        time.sleep(1)
    proc.terminate()
    raise RuntimeError('load timeout; see ' + str(log))


def run_turn(key, thinking, prompt, project, approval, max_time, allow_writes=False):
    env = dict(os.environ)
    env['PI_CODING_AGENT_DIR'] = str(S.profile(key, thinking))
    env.pop('OMP_PROFILE', None)
    argv = S.agent_args(key, project, 'project', thinking, False, prompt, approval)
    argv[argv.index('--tools') + 1] = 'read,grep,glob,write,edit' if allow_writes else 'read,grep,glob'
    argv[argv.index('--system-prompt') + 1] = (
        'Inspect the requested project using read, grep and glob. '
        + ('Apply only the requested changes using write or edit. ' if allow_writes else
           'Read-only task: explain findings; do not claim to have edited files. ')
        + 'No shell or test runner is available. Never claim tests ran. '
          'Stop after two identical tool failures. Preserve unrelated work and existing tests.')
    argv += ['--max-time', str(max_time)]
    env.pop('CHORES_API_TOKEN', None)
    jr = JOURNAL / time.strftime('%Y%m%d-%H%M%S-turn')
    jr.mkdir(parents=True, exist_ok=True)
    (jr / 'prompt.txt').write_text(prompt, encoding='utf-8')
    try:
        proc = subprocess.run(argv, env=env, capture_output=True, text=True,
                              timeout=max_time + 60,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return {'exit': None, 'error': 'turn exceeded max_time', 'text': ''}
    (jr / 'stdout.jsonl').write_text(proc.stdout or '', encoding='utf-8')
    (jr / 'stderr.log').write_text(proc.stderr or '', encoding='utf-8')
    text, stop, tools = '', None, []
    for line in (proc.stdout or '').splitlines():
        if not line.startswith('{'):
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('type') == 'message_end' and e.get('message', {}).get('role') == 'assistant':
            m = e['message']
            stop = m.get('stopReason')
            for b in m.get('content', []) or []:
                if b.get('type') == 'text':
                    text += b.get('text', '')
                if b.get('type') == 'toolcall':
                    tools.append(b.get('name') or b.get('tool', '?'))
    return {'exit': proc.returncode, 'stopReason': stop, 'tools': tools,
            'text': text, 'journal': str(jr), 'allow_writes': allow_writes}


class Handler(BaseHTTPRequestHandler):
    server_version = 'ChoresAPI/1'

    def log_message(self, *a):
        pass

    def _authorized(self):
        token = getattr(self.server, 'api_token', '')
        supplied = self.headers.get('Authorization', '')
        if not token or not hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode()):
            self._send(401, {'error': 'bearer authentication required'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in getattr(self.server, 'allowed_origins', ()):
            self._send(403, {'error': 'origin not allowed'})
            return False
        return True

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin in getattr(self.server, 'allowed_origins', ()):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return False
        if n < 0 or self.headers.get('Transfer-Encoding'):
            return False
        if n > MAX_PROMPT + 4096:
            return None
        raw = self.rfile.read(n) if n else b'{}'
        try:
            return json.loads(raw.decode())
        except ValueError:
            return False

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        if not self._authorized():
            return
        p = self.path.rstrip('/')
        if p.startswith('/audio/'):
            self._audio(p[len('/audio/'):])
        elif p in ('/health', '/api/health'):
            live = upstream_live()
            self._send(200, {'api': 'ok', 'server_live': live,
                             'owner': 'api' if state['server'] and state['server'].poll() is None else ('other' if live else None),
                             'model': upstream_model() if live else None})
        elif p in ('/models', '/api/models'):
            loaded = upstream_model() if upstream_live() else None
            self._send(200, {'models': [
                {'id': k, 'name': S.MODELS[k][0], 'loaded': k == loaded}
                for k in S.MODELS]})
        else:
            self.send_response(404); self._cors(); self.end_headers()

    def do_POST(self):
        if not self._authorized():
            return
        p = self.path.rstrip('/')
        data = self._body()
        if data is None:
            self._send(413, {'error': 'body too large'}); return
        if not isinstance(data, dict):
            self._send(400, {'error': 'JSON object required'}); return
        if p == '/models/load':
            self._load(data)
        elif p == '/models/stop':
            self._stop()
        elif p == '/v1/chat/completions':
            self._chat(data)
        elif p == '/agent/turn':
            self._turn(data)
        elif p == '/notes/organize':
            self._organize(data)
        elif p == '/notes/speak':
            self._speak(data)
        else:
            self.send_response(404); self._cors(); self.end_headers()

    def _load(self, data):
        key = data.get('model')
        if not isinstance(key, str) or key not in S.MODELS:
            self._send(400, {'error': f"unknown model; choices: {sorted(S.MODELS)}"}); return
        thinking = data.get('thinking', key == 'nanbeige')
        if not isinstance(thinking, bool):
            self._send(400, {'error': 'thinking must be boolean'}); return
        context = data.get('context')
        if context is not None and context not in S.CONTEXT_CHOICES:
            self._send(400, {'error': f'context choices: {S.CONTEXT_CHOICES}'}); return
        ctx = context or S.default_context(key)
        with lock:
            if state['busy']:
                self._send(409, {'error': 'a load or turn is already running'}); return
            if state['server'] and state['server'].poll() is None:
                same = state['model'] == key
                self._send(200, {'already': True, 'model': state['model'],
                                 'note': 'that model already live' if same else
                                 'a different API model is live; stop it first'})
                return
            if port_busy():
                self._send(409, {'error': f'port {S.PORT} busy (SMOL.cmd?). Close it first.'}); return
            state['busy'] = True
        try:
            proc = start_server(key, thinking, ctx)
        except Exception as e:
            with lock:
                state['busy'] = False
            self._send(500, {'error': str(e)}); return
        with lock:
            state.update(server=proc, model=key, thinking=thinking,
                         context=ctx, busy=False)
        self._send(200, {'loaded': True, 'model': key, 'thinking': thinking,
                         'context': ctx})

    def _stop(self):
        with lock:
            if state['busy']:
                self._send(409, {'error': 'a load or turn is already running'}); return
            proc = state['server']
            if not proc or proc.poll() is not None:
                state.update(server=None, model=None)
                self._send(200, {'stopped': False, 'note': 'no API-owned server'}); return
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            state.update(server=None, model=None)
            self._send(200, {'stopped': True})

    def _chat(self, data):
        payload = json.dumps(data).encode()
        try:
            req = urlrequest.Request(UPSTREAM + '/v1/chat/completions',
                                     data=payload,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
            up = urlrequest.urlopen(req, timeout=None)
        except HTTPError as e:
            detail = e.read()[:4096]
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(detail)))
            self._cors(); self.end_headers(); self.wfile.write(detail); return
        except (URLError, OSError):
            self._send(502, {'error': 'no model loaded; POST /models/load first'}); return
        self.send_response(200)
        self.send_header('Content-Type', up.headers.get('Content-Type', 'text/event-stream'))
        self._cors(); self.end_headers()
        try:
            while True:
                chunk = up.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (ConnectionAbortedError, BrokenPipeError):
            pass

    def _organize(self, data):
        transcript = data.get('transcript', '')
        if not isinstance(transcript, str) or not transcript.strip():
            self._send(400, {'error': 'transcript (non-empty string) required'}); return
        if len(transcript) > MAX_PROMPT:
            self._send(413, {'error': 'transcript too large'}); return
        if not upstream_live():
            self._send(502, {'error': 'no model loaded; POST /models/load first'}); return
        payload = json.dumps({
            'messages': [
                {'role': 'system', 'content': ORGANIZE_SYSTEM},
                {'role': 'user', 'content': transcript.strip()},
            ],
            'temperature': 0.3,
            'stream': False,
        }).encode()
        try:
            req = urlrequest.Request(UPSTREAM + '/v1/chat/completions',
                                     data=payload,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
            with urlrequest.urlopen(req, timeout=300) as up:
                raw = up.read().decode()
        except HTTPError as e:
            self._send(e.code, {'error': 'upstream chat failed',
                                'detail': e.read()[:1024].decode('utf-8', 'replace')}); return
        except (URLError, OSError) as e:
            self._send(502, {'error': f'upstream unreachable: {e}'}); return
        try:
            content = json.loads(raw)['choices'][0]['message']['content']
        except (ValueError, KeyError, IndexError, TypeError):
            self._send(502, {'error': 'unexpected upstream reply', 'raw': raw[:1024]}); return
        try:
            start, end = content.index('{'), content.rindex('}') + 1
            note = json.loads(content[start:end])
        except (ValueError, IndexError):
            note = {'title': '', 'body': content, 'tasks': [], 'recap': content[:500]}
        note.setdefault('title', '')
        note.setdefault('body', content)
        note.setdefault('tasks', [])
        note.setdefault('recap', '')
        note['model'] = upstream_model()
        self._send(200, note)

    def _audio(self, name):
        safe = Path(name).name
        if not safe.endswith('.wav') or safe != name:
            self.send_response(400); self._cors(); self.end_headers(); return
        path = AUDIO / safe
        if not path.is_file():
            self.send_response(404); self._cors(); self.end_headers(); return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Content-Length', str(len(data)))
        self._cors(); self.end_headers(); self.wfile.write(data)

    def _speak(self, data):
        text = data.get('text', '')
        if not isinstance(text, str) or not text.strip():
            self._send(400, {'error': 'text (non-empty string) required'}); return
        if len(text) > MAX_SPEAK:
            self._send(413, {'error': f'text too large (max {MAX_SPEAK} chars)'}); return
        voice = data.get('voice') or 'es_MX-claude-high'
        payload = json.dumps({'input': text.strip(), 'voice': voice,
                              'response_format': 'wav'}).encode()
        try:
            req = urlrequest.Request(PIPER_URL + '/v1/audio/speech', data=payload,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
            with urlrequest.urlopen(req, timeout=120) as up:
                wav = up.read()
        except (HTTPError, URLError, OSError) as e:
            self._send(502, {'error': 'piper TTS unreachable (start scripts/start_piper.ps1 on E:)',
                             'detail': str(e)[:200]}); return
        if not wav[:4] == b'RIFF':
            self._send(502, {'error': 'piper returned non-wav audio'}); return
        AUDIO.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha1((voice + '\n' + text.strip()).encode()).hexdigest()[:16] + '.wav'
        (AUDIO / name).write_bytes(wav)
        self._send(200, {'audio_url': '/audio/' + name, 'voice': voice,
                         'chars': len(text.strip())})

    def _turn(self, data):
        prompt = data.get('prompt', '')
        if not isinstance(prompt, str) or not prompt.strip():
            self._send(400, {'error': 'prompt (non-empty string) required'}); return
        if len(prompt) > MAX_PROMPT:
            self._send(413, {'error': 'prompt too large'}); return
        if 'approval' in data:
            self._send(400, {'error': 'permissions are configured by the server operator'}); return
        allow_writes = getattr(self.server, 'allow_writes', False)
        approval = 'yolo'
        try:
            max_time = int(data.get('max_time', 600))
        except (TypeError, ValueError):
            self._send(400, {'error': 'max_time must be seconds'}); return
        max_time = max(60, min(max_time, 3600))
        roots = getattr(self.server, 'project_roots', ())
        try:
            name = data.get('project')
            project = Path(name).resolve(strict=True) if name else next(iter(roots), None)
            if project not in roots or not project.is_dir():
                self._send(403, {'error': 'project must be an explicitly allowed root'}); return
        except (OSError, TypeError, ValueError):
            self._send(400, {'error': 'invalid project directory'}); return
        if not upstream_live():
            self._send(502, {'error': 'no model loaded; POST /models/load first'}); return
        with lock:
            if state['busy']:
                self._send(409, {'error': 'a turn is already running'}); return
            key = state['model'] or upstream_model()
            thinking = state['thinking'] if state['thinking'] is not None else (key == 'nanbeige')
            if not key:
                self._send(502, {'error': 'server live but model unknown'}); return
            state['busy'] = True
        try:
            res = run_turn(key, thinking, prompt.strip(), project, approval, max_time, allow_writes)
        except Exception:
            self._send(500, {'error': 'agent turn failed; inspect local journals'})
            return
        finally:
            with lock:
                state['busy'] = False
        self._send(200, res)


def main():
    ap = argparse.ArgumentParser(description='Chores API: HTTP in, local Smol models out')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=9111)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--project-root', action='append', default=[])
    ap.add_argument('--allow-origin', action='append', default=[])
    ap.add_argument('--allow-writes', action='store_true')
    args = ap.parse_args()
    for path in (S.RUNTIME, S.OMP):
        if not path.is_file():
            print('Falta: ' + str(path)); return 1
    if args.check:
        print('models:', ', '.join(S.MODELS))
        print('server_live:', upstream_live(), '| port_busy:', port_busy())
        print('OK chores_api (nothing loaded, nothing started)')
        return 0
    token = os.environ.get('CHORES_API_TOKEN', '')
    if len(token) < 32 or any(c.isspace() for c in token):
        ap.error('set CHORES_API_TOKEN to a random token of at least 32 characters')
    try:
        if not ipaddress.ip_address(args.host).is_loopback:
            ap.error('bind a loopback IP; use an authenticated SSH tunnel for remote access')
    except ValueError:
        ap.error('--host must be a loopback IP address')
    try:
        roots = tuple(Path(p).resolve(strict=True) for p in args.project_root)
        if any(not p.is_dir() for p in roots):
            ap.error('--project-root must be an existing directory')
    except (OSError, ValueError):
        ap.error('--project-root must be an existing directory')
    if not roots:
        INBOX.mkdir(parents=True, exist_ok=True)
        roots = (INBOX.resolve(),)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.api_token = token
    srv.allowed_origins = frozenset(args.allow_origin)
    srv.project_roots = roots
    srv.allow_writes = args.allow_writes
    print(f'chores_api on http://{args.host}:{args.port} (models load to :{S.PORT}; '
          f"auth={'on' if srv.api_token else 'OFF'}; writes={'on' if srv.allow_writes else 'off'}; "
          f'roots={len(roots)})')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    with lock:
        proc = state['server']
    if proc and proc.poll() is None:
        print('stopping owned server...')
        proc.terminate()
    return 0


if __name__ == '__main__':
    sys.exit(main())
