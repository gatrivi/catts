"""Step 1: four isolated OMP tool probes for MiniCPM (16K/32K x default/XML).

Loads the verified MiniCPM Q8 on the Smol port, runs one read-task prompt per
config via `--print --mode json`, records whether OMP received a real tool call,
then stops the server. Evidence: data/smol/probes/<ts>/.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smol

PROBE = 'Read SMOL_CHECK.txt using the read tool and return its exact contents.'


def load_server(key, thinking, ctx, out_dir, log_name):
    job = smol.RuntimeJob()
    server = None
    try:
        with (out_dir / log_name).open('w', encoding='utf-8') as log:
            server = subprocess.Popen(smol.server_args(key, thinking, ctx), env=env_base(),
                                      stdout=log, stderr=log,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            job.assign(server)
        import httpx
        deadline = time.monotonic() + smol.load_budget(key)
        with httpx.Client(base_url=f'http://127.0.0.1:{smol.PORT}', timeout=5) as client:
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('server exited; see ' + log_name)
                try:
                    if client.get('/health').status_code == 200:
                        if client.get('/v1/models').json()['data'][0]['id'] != key:
                            raise RuntimeError('unexpected served model')
                        return job, server
                except httpx.HTTPError:
                    pass
                time.sleep(1)
        raise RuntimeError('load timeout')
    except BaseException:
        smol.stop(server)
        job.close()
        raise


def env_base():
    env = dict(os.environ, GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM='1')
    env.pop('OMP_PROFILE', None)
    return env


def summarize(case):
    events = [json.loads(line) for line in (case / 'agent.jsonl').read_text(encoding='utf-8').splitlines()
              if line.startswith('{')]
    messages = [e.get('message', {}) for e in events if e.get('type') == 'message_end']
    calls = [b for m in messages if m.get('role') == 'assistant'
             for b in m.get('content', []) if str(b.get('type', '')).lower() == 'toolcall']
    results = [m for m in messages if m.get('role') == 'toolResult']
    successful = {m.get('toolCallId') for m in results if not m.get('isError')}
    texts = ''.join(b.get('text', '') for m in messages if m.get('role') == 'assistant'
                    for b in m.get('content', []) if b.get('type') == 'text')
    passed = any(c.get('name') == 'read' and c.get('id') in successful for c in calls)
    return {'tool_calls': [b.get('name') for b in calls], 'saw_marker': 'PROBE_MARKER_OK' in texts,
            'successful_reads': sum(c.get('name') == 'read' and c.get('id') in successful for c in calls),
            'result': 'pass' if passed and 'PROBE_MARKER_OK' in texts else 'fail'}


def run_probe(key, ctx, xml, out_dir):
    original_data = smol.DATA
    smol.DATA = out_dir / f'profile-{ctx}-{xml}'
    try:
        profile_dir = smol.profile(key, False, ctx)
    finally:
        smol.DATA = original_data
    if xml:
        path = profile_dir / 'models.yml'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['providers']['smol']['compat']['extraBody']['chat_template_kwargs']['tool_call_format'] = 'xml'
        smol.write_json(path, data)
    tag = f'{ctx}-{"xml" if xml else "default"}'
    case = out_dir / tag
    case.mkdir(parents=True, exist_ok=True)
    job, server = load_server(key, False, ctx, case, 'server.log')
    row = {'context': ctx, 'tool_call_format': 'xml' if xml else 'default'}
    agent = None
    agent_job = None
    try:
        agent_job = smol.RuntimeJob()
        argv = smol.agent_args(key, out_dir / 'fixture', 'project', False, prompt=PROBE)
        argv[argv.index('--config') + 1] = str(profile_dir / 'limits.json')
        with (case / 'agent.jsonl').open('w', encoding='utf-8') as out, \
             (case / 'agent.stderr.log').open('w', encoding='utf-8') as err:
            agent = subprocess.Popen(argv, env={**env_base(), 'PI_CODING_AGENT_DIR': str(profile_dir)},
                                     stdout=out, stderr=err,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            agent_job.assign(agent)
            try:
                agent.wait(timeout=240)
            except subprocess.TimeoutExpired:
                agent.kill()
                row['result'] = 'agent_timeout'
                return row
        row['agent_exit'] = agent.returncode
        row.update(summarize(case))
        if agent.returncode:
            row['result'] = 'agent_error'
    finally:
        smol.stop(agent)
        if agent_job:
            agent_job.close()
        smol.stop(server)
        job.close()
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate', type=Path)
    parser.add_argument('--validate-case', type=Path)
    args = parser.parse_args()
    if args.validate_case:
        events = [json.loads(line) for line in (args.validate_case / 'agent.jsonl').read_text(encoding='utf-8').splitlines()
                  if line.startswith('{')]
        raw_reads = [block for event in events if event.get('type') == 'message_end'
                     and event.get('message', {}).get('role') == 'assistant'
                     for block in event['message'].get('content', [])
                     if block.get('type') == 'toolCall' and block.get('name') == 'read']
        assert len(raw_reads) > 0, 'Raw log contains no completed read toolCall'
        row = summarize(args.validate_case)
        assert row['tool_calls'].count('read') == len(raw_reads), 'Parser lost read calls'
        assert row['successful_reads'] > 0, 'No matching successful toolResult'
        assert row['result'] == 'pass', 'Probe did not complete successfully'
        print(json.dumps({'raw_read_calls': len(raw_reads), **row}), flush=True)
        return
    if args.validate:
        rows = []
        for ctx in (16384, 32768):
            for fmt in ('default', 'xml'):
                row = {'context': ctx, 'tool_call_format': fmt,
                       **summarize(args.validate / f'{ctx}-{fmt}')}
                rows.append(row)
                print(json.dumps(row), flush=True)
        if not all(row['result'] == 'pass' for row in rows):
            raise SystemExit(1)
        return
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', smol.PORT)) == 0:
            raise RuntimeError('Port busy; another model server is active.')
    smol.check_model('mini')
    if smol.find_prior():
        raise RuntimeError('Existing model server preserved; close it before probing.')
    if smol.psutil.virtual_memory().available < 1536 * 2**20:
        raise RuntimeError('Insufficient free RAM')
    out_dir = smol.DATA / 'probes' / time.strftime('%Y%m%d-%H%M%S')
    out_dir.mkdir(parents=True)
    fixture = out_dir / 'fixture'
    fixture.mkdir()
    (fixture / 'SMOL_CHECK.txt').write_text('PROBE_MARKER_OK', encoding='utf-8')
    rows = []
    for ctx in (16384, 32768):
        for xml in (False, True):
            row = run_probe_with_retry(out_dir, ctx, xml)
            rows.append(row)
            (out_dir / 'rows.jsonl').open('a', encoding='utf-8').write(json.dumps(row) + '\n')
            print(json.dumps(row, ensure_ascii=False), flush=True)
    print('DONE ' + str(out_dir), flush=True)


def run_probe_with_retry(out_dir, ctx, xml):
    try:
        return run_probe('mini', ctx, xml, out_dir)
    except RuntimeError as exc:
        row = {'context': ctx, 'tool_call_format': 'xml' if xml else 'default',
               'result': 'error', 'error': str(exc)}
        return row


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        sys.exit(1)
