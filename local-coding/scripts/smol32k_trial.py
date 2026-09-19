"""One bounded MiniCPM 32K-context trial: memory, long-context recall, OMP smoke, one real task.

Protocol from docs/SMOL.md: measure memory at load and with long input, verify reading and
response, then one small change with a real test. Single attempt, no repairs. Stops owned
servers; restores a paused prior server on exit.
"""
import json, os, socket, subprocess, sys, time
from pathlib import Path
import httpx, psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import smol

OUT = ROOT / 'data' / ('smol32k-trial-' + time.strftime('%Y%m%d-%H%M%S'))
OUT.mkdir(parents=True)
CTX = 32768
report = {'context': CTX, 'model': 'mini', 'phases': {},
          'limits': {'turns': 8, 'task_seconds': 300, 'test_runs': 1}}
def save():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

def gpu_ps(query, pid=None):
    try:
        script = ("(Get-Counter '" + query + "').CounterSamples"
                  + (" | Where-Object {$_.InstanceName -like 'pid_" + str(pid) + "_*'}" if pid else '')
                  + " | Measure-Object -Property CookedValue -Sum | Select-Object -ExpandProperty Sum")
        value = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
                               capture_output=True, text=True, timeout=30).stdout.strip()
        return float(value) if value else None
    except Exception as e:
        return 'error: ' + str(e)[:120]

def vram(pid):
    return {'process_bytes': gpu_ps('\\GPU Process Memory(*)\\Local Usage', pid),
            'adapter_dedicated_bytes': gpu_ps('\\GPU Adapter Memory(*)\\Dedicated Usage')}

FILLER = 'alpha bravo charlie delta echo foxtrot golf hotel'

def build_prompt(lines):
    parts = ['Read this log carefully.']
    for i in range(1, lines + 1):
        parts.append(f'L{i:04d}: {FILLER}')
        if i == 150: parts.append('MARKER_ALPHA = K7Q4')
        if i == lines // 2: parts.append('MARKER_BRAVO = Z2M8')
        if i == lines - 100: parts.append('MARKER_CHARLIE = D9T3')
    parts.append('From the log above, return only this line exactly: '
                 'ALPHA=<value> BRAVO=<value> CHARLIE=<value>')
    return '\n'.join(parts)

def chat(client, messages, max_tokens, timeout=600):
    start = time.monotonic()
    try:
        r = client.post('/v1/chat/completions', timeout=timeout, json={
            'model': 'mini', 'temperature': 0, 'max_tokens': max_tokens,
            'messages': messages, 'chat_template_kwargs': {'enable_thinking': False}})
    except Exception as e:
        return {'error': str(e)[:300], 'seconds': round(time.monotonic() - start, 1)}
    if r.status_code != 200:
        return {'error': f'HTTP {r.status_code}: ' + r.text[:300], 'seconds': round(time.monotonic() - start, 1)}
    body = r.json(); usage = body.get('usage', {}); secs = time.monotonic() - start
    return {'body': body, 'text': body['choices'][0]['message'].get('content') or '',
            'finish': body['choices'][0].get('finish_reason'),
            'prompt_tokens': usage.get('prompt_tokens'), 'completion_tokens': usage.get('completion_tokens'),
            'seconds': round(secs, 1),
            'prompt_tok_s': round(usage.get('prompt_tokens', 0) / max(secs, 0.001)),
            'decode_tok_s': round(usage.get('completion_tokens', 0) / max(secs, 0.001))}

def main():
    prior = None
    for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'create_time']):
        i = p.info
        if (i['name'] or '').lower() != 'llama-server.exe': continue
        cmd = i['cmdline'] or []
        if prior or not i['exe'] or '8123' not in cmd or not any('qwen2.5-coder-7b-instruct-q4_k_m.gguf' in a for a in cmd):
            raise RuntimeError('Unexpected active model server; refusing overlap')
        prior = i
    smol.check_model('mini')
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1', smol.PORT)) == 0: raise RuntimeError('Port 9104 occupied')
    if psutil.virtual_memory().available < 3 * 1024**3: raise RuntimeError('Insufficient free RAM')
    env = os.environ.copy()
    env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM'] = '1'
    env['PI_CODING_AGENT_DIR'] = str(smol.profile('mini', False, CTX))
    env.pop('OMP_PROFILE', None)
    paused = False
    server = None
    log = (OUT / 'server.log').open('w', encoding='utf-8')
    try:
        if prior:
            p = psutil.Process(prior['pid'])
            if p.create_time() != prior['create_time'] or p.cmdline() != prior['cmdline']:
                raise RuntimeError('Prior server changed')
            (OUT / 'prior-server.json').write_text(json.dumps({'executable': prior['exe'],
                'argumentLine': subprocess.list2cmdline(prior['cmdline'][1:]), 'pid': prior['pid']}))
            p.terminate(); paused = True; p.wait(20)
        argv = smol.server_args('mini', False, CTX)
        # Launcher defaults (-b 256 -ub 128) throttle prefill badly; measure with sane batch
        argv[argv.index('-b') + 1] = '2048'
        argv[argv.index('-ub') + 1] = '512'
        report['server_args'] = argv
        report['launcher_batch_default'] = ['-b', '256', '-ub', '128']; save()
        server = subprocess.Popen(argv, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        t0 = time.monotonic()
        client = httpx.Client(base_url=f'http://127.0.0.1:{smol.PORT}', timeout=330)
        ready = time.monotonic() + 240
        while time.monotonic() < ready:
            if server.poll() is not None: raise RuntimeError('Server exited during load')
            try:
                if client.get('/health').status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(1)
        else: raise RuntimeError('Load timeout')
        report['phases']['load'] = {'vram': vram(server.pid), 'seconds': round(time.monotonic() - t0, 1)}
        save(); print('LOADED', flush=True)

        # Phase A: long-context marker recall, then decode speed near the window
        for lines in (1400, 1100):
            recall = chat(client, [{'role': 'user', 'content': build_prompt(lines)}], 256)
            if 'error' in recall:
                report['phases']['recall'] = {'lines': lines, **recall}; save()
                print('RECALL RETRY', recall['error'][:120], flush=True); continue
            found = {k: (v in recall['text']) for k, v in
                     [('ALPHA', 'K7Q4'), ('BRAVO', 'Z2M8'), ('CHARLIE', 'D9T3')]}
            report['phases']['recall'] = {'lines': lines, **{k: recall[k] for k in
                ('prompt_tokens', 'completion_tokens', 'seconds', 'prompt_tok_s', 'finish')},
                'response': recall['text'][:400], 'markers_found': found,
                'all_markers': all(found.values()), 'vram_after': vram(server.pid)}
            save(); print('RECALL', lines, 'lines, prompt_tokens', recall['prompt_tokens'], flush=True)
            break
        lines = report['phases'].get('recall', {}).get('lines', 1500)
        follow = chat(client, [
            {'role': 'user', 'content': build_prompt(lines)},
            {'role': 'assistant', 'content': report['phases'].get('recall', {}).get('response', '') or 'ALPHA=K7Q4 BRAVO=Z2M8 CHARLIE=D9T3'},
            {'role': 'user', 'content': 'Now list 20 short uses for a paperclip, numbered, one per line.'}], 512)
        if 'error' in follow:
            report['phases']['decode_near_window'] = follow
        else:
            report['phases']['decode_near_window'] = {k: follow[k] for k in
                ('prompt_tokens', 'completion_tokens', 'seconds', 'decode_tok_s', 'finish')} | {
                'lines_returned': follow['text'].count('\n') + 1, 'vram_after': vram(server.pid)}
        save(); print('DECODE DONE', flush=True)

        # Phase B: OMP project smoke at 32K advertised context
        project = OUT / 'project'; project.mkdir()
        (project / 'SMOL_CHECK.txt').write_text(
            'SMOL_CHECK_OK_9F3K: the quick purple elephant paints at midnight.', encoding='utf-8')
        argv = smol.agent_args('mini', project, 'project', False,
                               prompt='Read SMOL_CHECK.txt using the read tool and return its exact contents.')
        report['omp_smoke_args'] = argv; save()
        with (OUT / 'agent.jsonl').open('w', encoding='utf-8') as out, (OUT / 'agent.stderr.log').open('w', encoding='utf-8') as err:
            agent = subprocess.Popen(argv, env=env, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
            try: agent.wait(timeout=180)
            except subprocess.TimeoutExpired: agent.kill()
        events = [json.loads(l) for l in (OUT / 'agent.jsonl').read_text(encoding='utf-8').splitlines() if l.startswith('{')]
        answers = [e.get('message', {}) for e in events if e.get('type') == 'message_end' and e.get('message', {}).get('role') == 'assistant']
        smoke_text = ' '.join(b.get('text', '') for m in answers for b in m.get('content', []))
        report['phases']['omp_smoke'] = {
            'exit': agent.returncode, 'stop_reasons': [m.get('stopReason') for m in answers],
            'text': smoke_text[:400],
            'passed': agent.returncode == 0 and bool(answers)
                      and all(m.get('stopReason') != 'error' for m in answers)
                      and 'SMOL_CHECK_OK_9F3K' in smoke_text}
        save(); print('OMP SMOKE', report['phases']['omp_smoke']['passed'], flush=True)

        # Phase C: one small real change, host-controlled tools, one test run, no repairs
        run_task(env)
    except Exception as e:
        report['error'] = str(e); print('ERROR ' + str(e), flush=True)
    finally:
        if server:
            server.terminate()
            try: server.wait(15)
            except subprocess.TimeoutExpired: server.kill()
        try: client.close()
        except Exception: pass
        log.close()
        report['server_stopped'] = server is None or server.poll() is not None
        save()
        if paused:
            subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                            str(ROOT / 'scripts/restore_e4b_prior_server.ps1'), '-Journal', str(OUT)],
                           check=True, timeout=200)
        print('REPORT ' + str(OUT / 'report.json'), flush=True)

TASK_DIR_NAME = 'task'
ALLOWED = {'cart.py'}
TOOLS = [{'type': 'function', 'function': {'name': 'read_file', 'description': 'Read one task file',
          'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                          'required': ['path'], 'additionalProperties': False}}},
         {'type': 'function', 'function': {'name': 'write_file', 'description': 'Replace cart.py after reading it',
          'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
                          'required': ['path', 'content'], 'additionalProperties': False}}}]

def run_task(env):
    task = OUT / TASK_DIR_NAME; task.mkdir()
    (task / 'cart.py').write_text(
        'def apply_discount(price, percent):\n'
        '    """Return price after applying a percent discount (0-100)."""\n'
        '    return price - percent\n', encoding='utf-8')
    test_src = ('from cart import apply_discount\n'
                'assert apply_discount(80, 50) == 40.0\n'
                'assert apply_discount(19.99, 10) == round(19.99 * 0.9, 2)\n'
                'assert apply_discount(200, 0) == 200\n'
                "print('ALL PASS')\n")
    (task / 'test_cart.py').write_text(test_src, encoding='utf-8')
    test_hash = __import__('hashlib').sha256(test_src.encode()).hexdigest()
    base = time.monotonic()
    messages = [{'role': 'system', 'content': 'You are a coding assistant. Use read_file and write_file. '
                'Fix cart.py so test_cart.py passes. No shell, no network. Keep responses short.'},
                {'role': 'user', 'content': 'Read cart.py and test_cart.py, then fix apply_discount in cart.py '
                'so every assertion in test_cart.py passes. percent is a percentage (50 means half off). '
                'Use write_file for the fixed cart.py. Finish after writing.'}]
    seen, turns, used = set(), [], 0
    with httpx.Client(base_url=f'http://127.0.0.1:{smol.PORT}', timeout=330) as client:
        for _ in range(report['limits']['turns']):
            if time.monotonic() - base > report['limits']['task_seconds']:
                report['phases']['task_stop'] = 'time limit'; break
            turn = chat(client, messages, 1024, timeout=max(30, report['limits']['task_seconds'] - (time.monotonic() - base)))
            if 'error' in turn:
                report['phases']['task_error'] = turn; break
            message = turn['body']['choices'][0]['message']
            turns.append({'seconds': turn['seconds'], 'response': turn['body']}); used += 1
            messages.append(message)
            calls = message.get('tool_calls') or []
            print('TASK TURN', used, ','.join(c['function']['name'] for c in calls) or '(no tools)', flush=True)
            if not calls:
                report['phases']['task_stop'] = 'no tool calls'; break
            for call in calls:
                try:
                    fn = call['function']; a = json.loads(fn['arguments']); name = a['path']
                    if name not in ('cart.py', 'test_cart.py'): raise ValueError('Unknown path')
                    if fn['name'] == 'read_file':
                        result = (task / name).read_text(encoding='utf-8'); seen.add(name)
                    elif name == 'cart.py' and name in seen and isinstance(a.get('content'), str) and len(a['content']) <= 5000:
                        (task / name).write_text(a['content'], encoding='utf-8'); result = 'Written'
                    else: raise ValueError('Write denied: protected or unread file')
                except Exception as e:
                    result = 'ERROR: ' + str(e)
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': result})
        else:
            report['phases']['task_stop'] = 'turn limit'
    test = subprocess.run(['E:/zengatrivi-drive-e/catts/.venv/Scripts/python.exe', 'test_cart.py'],
                          cwd=task, capture_output=True, text=True, timeout=60)
    (OUT / 'task-test.log').write_text(test.stdout + test.stderr, encoding='utf-8')
    report['phases']['task'] = {
        'turns': used, 'test_exit': test.returncode, 'test_output': (test.stdout + test.stderr)[:400],
        'passed': test.returncode == 0 and 'ALL PASS' in test.stdout,
        'protected_test_intact': __import__('hashlib').sha256((task / 'test_cart.py').read_bytes()).hexdigest() == test_hash}
    save(); print('TASK TEST EXIT', test.returncode, flush=True)

if __name__ == '__main__':
    main()
