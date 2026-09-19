"""Bounded local read/edit/test exercises; no shell tool or real project access."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import time
import httpx
import psutil

CASES = {
    'average': ('def average(xs):\n    return sum(xs) // len(xs)\n',
        'Fix average: arithmetic mean, including fractional results. Empty input raises ValueError.',
        [('average([1, 2])', 1.5), ('average([-2, 2])', 0.0), ('average([4])', 4.0)]),
    'settings': ('def settings(text):\n    return dict(line.split("=") for line in text.splitlines())\n',
        'Fix settings: parse key=value lines, strip surrounding spaces from keys/values, ignore blank lines and lines starting with # after stripping. Keep additional = characters in values. Malformed lines without = raise ValueError.',
        [('settings(" a = one=two\\n\\n # comment\\nb=3 ")', {'a':'one=two','b':'3'}), ('settings("")', {})]),
    'unique': ('def unique(xs):\n    return list(set(xs))\n',
        'Fix unique: remove duplicates while preserving first occurrence order. Input is a list of integers. Run tests and verify the fix.',
        [('unique([3, 1, 3, 2, 1])', [3,1,2]), ('unique([])', []), ('unique([0, -1, 0])', [0,-1])]),
}


def validate(source):
    tree = ast.parse(source)
    allowed = {'sum','len','ValueError','set','list','dict','int','str','range','enumerate','sorted'}
    methods = {'split','partition','splitlines','strip','startswith','append','add','get','items','fromkeys'}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.While, ast.With, ast.AsyncFunctionDef, ast.ClassDef)):
            raise ValueError('Only small pure functions are allowed in this exercise')
        if isinstance(node, ast.Name) and node.id.startswith('__'):
            raise ValueError('Dunder names prohibited')
        if isinstance(node, ast.Attribute) and node.attr not in methods:
            raise ValueError(f'Unsupported attribute {node.attr!r}; allowed methods: {", ".join(sorted(methods))}')
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in allowed:
                raise ValueError('Unsupported call')
            if not isinstance(node.func, (ast.Name, ast.Attribute)):
                raise ValueError('Unsupported call expression')
    if any(not isinstance(n, ast.FunctionDef) for n in tree.body):
        raise ValueError('Only function definitions at module scope')


def run_tests(case, path):
    source = path.read_text(encoding='utf-8')
    validate(source)
    checks = '\n'.join(f'assert {expression} == {expected!r}, {expression!r}' for expression, expected in CASES[case][2])
    exceptional = {'average':'average([])', 'settings':'settings("broken")'}.get(case)
    if exceptional:
        checks += f'\ntry:\n    {exceptional}\nexcept ValueError:\n    pass\nelse:\n    raise AssertionError("Expected ValueError")'
    code = source + '\n' + checks + '\nprint("PASS")'
    # No shell, imports or filesystem APIs in model-produced code; hard subprocess deadline.
    result = subprocess.run([sys.executable,'-I','-c',code],capture_output=True,text=True,timeout=5)
    return {'passed':result.returncode==0, 'output':(result.stdout+result.stderr)[-2000:]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:9102')
    parser.add_argument('--out',default='data/local-coding-exercises')
    args = parser.parse_args()
    folder = Path(args.out) / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    tools = [{'type':'function','function':{'name':name,'description':description,'parameters':schema}} for name,description,schema in [
        ('read_file','Read the sole editable file solution.py.',{'type':'object','properties':{},'additionalProperties':False}),
        ('write_file','Replace solution.py with corrected Python code. No markdown fences. Pure functions only.',{'type':'object','properties':{'content':{'type':'string'}},'required':['content'],'additionalProperties':False}),
        ('run_tests','Run fixed host-owned tests; return pass/fail.',{'type':'object','properties':{},'additionalProperties':False}),
    ]]
    report = []
    with httpx.Client(base_url=args.url,timeout=120) as client:
        model = client.get('/v1/models').json()['data'][0]['id']
        for case,(source,task,_) in CASES.items():
            root = folder / case
            root.mkdir()
            path = root / 'solution.py'
            path.write_text(source,encoding='utf-8')
            baseline = run_tests(case,path)
            if baseline['passed']:
                raise RuntimeError('Broken fixture unexpectedly passed')
            messages = [{'role':'system','content':'You are a coding assistant in a disposable exercise. Use tools to read solution.py, fix it, and run tests. No shell or imports. Use short pure Python functions. If tests fail, correct the code and rerun. Do not claim success before tests pass.'},
                {'role':'user','content':task}]
            events = []
            started = time.monotonic()
            saw_read = saw_write = saw_pass = False
            error = None
            try:
                for turn in range(10):
                    if psutil.virtual_memory().available < 1024**3:
                        raise RuntimeError('Low RAM; stopping exercise')
                    response = client.post('/v1/chat/completions',json={'model':model,'messages':messages,
                        'tools':tools,'temperature':0.2,'max_tokens':1024,'chat_template_kwargs':{'enable_thinking':False}})
                    response.raise_for_status()
                    body = response.json()
                    message = body['choices'][0]['message']
                    messages.append(message)
                    events.append({'message':message,'usage':body.get('usage'),'timings':body.get('timings')})
                    calls = message.get('tool_calls') or []
                    if not calls:
                        break
                    for call in calls:
                        name = call['function']['name']
                        try:
                            payload = json.loads(call['function']['arguments'])
                            if name == 'read_file':
                                result = {'content':path.read_text(encoding='utf-8')}
                                saw_read = True
                            elif name == 'write_file':
                                content = payload['content']
                                if len(content)>12000:
                                    raise ValueError('Code too long')
                                validate(content)
                                path.write_text(content,encoding='utf-8')
                                saw_write = True
                                saw_pass = False
                                result = {'written':True}
                            elif name == 'run_tests':
                                result = run_tests(case,path)
                                saw_pass = result['passed']
                            else:
                                raise ValueError('Unknown tool')
                        except Exception as exc:
                            result = {'error':str(exc)}
                        events.append({'tool':name,'result':result})
                        messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result)})
                    if saw_read and saw_write and saw_pass:
                        break
            except Exception as exc:
                error = str(exc)
            final = run_tests(case,path)
            record = {'case':case,'passed':saw_read and saw_write and saw_pass and final['passed'],
                'seconds':round(time.monotonic()-started,2),'error':error,'events':events}
            report.append(record)
            (folder/'report.json').write_text(json.dumps({'model':model,'results':report},indent=2),encoding='utf-8')
            print(f'{case}: {"PASS" if record["passed"] else "FAIL"} {record["seconds"]}s',flush=True)
    print(f'Report: {folder / "report.json"}',flush=True)
    return 0 if all(r['passed'] for r in report) else 2


if __name__ == '__main__':
    raise SystemExit(main())
