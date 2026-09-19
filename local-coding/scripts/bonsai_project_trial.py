"""One bounded, source-only Bonsai project trial; no automatic code execution."""
import argparse, hashlib, json, os, re, socket, subprocess, sys, time
from pathlib import Path
import httpx, psutil
from e4b_session import stop

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--model', type=Path, default=ROOT/'data/models/bonsai27-q1/Bonsai-27B-Q1_0.gguf')
parser.add_argument('--label', default='bonsai')
parser.add_argument('--probe-tools', action='store_true')
parser.add_argument('--nanbeige-thinking', action='store_true', help='Nanbeige agent settings with legacy GGUF metadata overrides')
parser.add_argument('--test-feedback', action='store_true', help='Fixed read-only Node test tool; initial validation plus two repairs, 12 minutes')
opts = parser.parse_args()
if not opts.label.replace('-', '').isalnum(): raise ValueError('Invalid label')
MODEL = opts.model.resolve()
OUT = ROOT/'data'/(opts.label+'-project-'+time.strftime('%Y%m%d-%H%M%S'))
OUT.mkdir(parents=True)
report = {'model': str(MODEL), 'turns': [], 'limit_seconds': 720 if opts.test_feedback else 360, 'test_runs': []}
template_kwargs = {'enable_thinking': False}
sampling = {'temperature': 0}
if opts.nanbeige_thinking:
    template_kwargs = {'enable_thinking': True, 'preserve_thinking': True, 'tool_call_format': 'xml'}
    sampling = {'temperature': 1.0, 'top_p': 0.95, 'top_k': 20}
report['template_kwargs'] = template_kwargs
report['sampling'] = sampling
def save():
    (OUT/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

def main():
    manifest = json.loads(MODEL.with_name(MODEL.name+'.verified.json').read_text())
    if MODEL.stat().st_size != manifest['bytes']:
        raise RuntimeError('Model differs from verified size')
    prior = None
    for p in psutil.process_iter(['pid','name','exe','cmdline','create_time']):
        info = p.info
        if info['name'] != 'llama-server.exe': continue
        cmd = info['cmdline'] or []
        if prior or '8123' not in cmd or not any('qwen2.5-coder-7b-instruct-q4_k_m.gguf' in a for a in cmd):
            raise RuntimeError('Unexpected active model; refusing overlap')
        prior = info
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',9103)) == 0: raise RuntimeError('Port occupied')
    fixture = subprocess.run([sys.executable, str(ROOT/'scripts/prepare_e4b_project_trial.py')], capture_output=True, text=True, check=True)
    project = Path(fixture.stdout.strip()).resolve()
    baseline = json.loads(project.with_name(project.name+'-baseline.json').read_text())
    report['project'] = str(project)
    allowed = {'src/money.cjs','src/cart.cjs','src/receipt.cjs'}
    seen = set()
    tools = []
    for name, desc, props in [
        ('read_file','Read one project file',{'path':{'type':'string'}}),
        ('write_file','Replace a source file after reading it; only src/money.cjs, src/cart.cjs, src/receipt.cjs are writable',{'path':{'type':'string'},'content':{'type':'string'}})
    ]:
        tools.append({'type':'function','function':{'name':name,'description':desc,'parameters':{'type':'object','properties':props,'required':list(props),'additionalProperties':False}}})
    if opts.test_feedback:
        tools.append({'type':'function','function':{'name':'run_tests','description':'Run the fixed original checkout suite after edits. No arguments. Maximum three calls: initial validation and two repair validations. Returns actual Node output.','parameters':{'type':'object','properties':{},'additionalProperties':False}}})
    task = ('Fix the checkout project. Read AGENTS.md, the three src files and tests/checkout.test.cjs. '
        'Replace dollars with toCents and add formatCents, updating imports/callers. Accept nonnegative numbers or trimmed decimal strings with at most two decimal places; reject invalid monetary values. '
        'Use integer cents throughout. Quantities must be positive integers. totals returns subtotalCents, shippingCents, totalCents. Shipping is 500 cents below 5000 subtotal, otherwise zero; empty cart shipping is zero. '
        'receipt returns Total: $5.30 (shipping $5.00) in that exact format. Use write_file to complete all three files. Preserve every other file. No test tool exists; host will run original tests. Finish after edits.')
    messages = [{'role':'system','content':'You are a coding assistant. Complete one task using read_file and write_file. Only three source files are writable. No shell/network. Keep responses short. Do not claim tests ran.'}, {'role':'user','content':task}]
    if opts.test_feedback:
        messages[0]['content']='Complete the checkout task using read_file, write_file, and run_tests. Only three source files are writable. No shell/network. After editing, run_tests; use failures to repair at most twice. Stop when tests pass or after three test runs. Keep explanations short.'
        messages[1]['content']=task.replace('No test tool exists; host will run original tests. Finish after edits.', 'After editing, call run_tests. Repair based on its actual failures, then run_tests again. At most two repair rounds after the first test run; three test runs total. The AGENTS note that the host runs tests refers to this host-controlled run_tests tool. Finish after a passing run or the third test run.')
    def fixed_tests():
        for name,digest in baseline['hashes'].items():
            if name not in allowed and hashlib.sha256((project/name).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Protected file changed: '+name)
        index=len(report['test_runs'])+1
        test_args=['node','--experimental-permission','--allow-fs-read='+str(project),'tests/checkout.test.cjs']
        try:
            result=subprocess.run(test_args,cwd=project,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(1,min(20,deadline-time.monotonic())))
            output=result.stdout+result.stderr
            code=result.returncode
        except subprocess.TimeoutExpired:
            output='Fixed test runner timed out'; code=124
        (OUT/('tests-'+str(index)+'.log')).write_text(output,encoding='utf-8')
        passed=code==0 and re.search(r'^# pass 12$',output,re.M) is not None and re.search(r'^# fail 0$',output,re.M) is not None
        record={'index':index,'exit':code,'passed':passed,'argv':test_args,'source_hashes':{n:hashlib.sha256((project/n).read_bytes()).hexdigest() for n in allowed}}
        report['test_runs'].append(record);save()
        print('TEST RUN '+str(index)+' EXIT '+str(code),flush=True)
        return 'Exit code: '+str(code)+'\n'+output[:14000]
    server = None
    paused = False
    log = (OUT/'server.log').open('w',encoding='utf-8')
    try:
        if prior:
            p = psutil.Process(prior['pid'])
            if p.create_time()!=prior['create_time'] or p.cmdline()!=prior['cmdline']: raise RuntimeError('Prior server changed')
            (OUT/'prior-server.json').write_text(json.dumps({'executable':prior['exe'],'argumentLine':subprocess.list2cmdline(prior['cmdline'][1:]),'pid':prior['pid']}))
            p.terminate(); paused=True; p.wait(20)
        if psutil.virtual_memory().available < 3*1024**3: raise RuntimeError('Insufficient free RAM')
        args = ['Z:/models/runtime/llama-vulkan/llama-server.exe','-m',str(MODEL),'--host','127.0.0.1','--port','9103','--alias','bonsai-trial','--device','Vulkan1','-ngl','999','-c','16384','-np','1','-ctk','q8_0','-ctv','q8_0','-fa','on','--jinja','--no-warmup','-b','256','-ub','128']
        if opts.nanbeige_thinking:
            args += ['--override-kv','nanbeige.block_count=int:22,nanbeige.num_loops=int:2','--reasoning-format','deepseek']
        env=os.environ.copy(); env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM']='1'
        server=subprocess.Popen(args,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        report.update(server_pid=server.pid,server_args=args); save()
        with httpx.Client(base_url='http://127.0.0.1:9103',timeout=180) as client:
            ready=time.monotonic()+180
            while time.monotonic()<ready:
                if server.poll() is not None: raise RuntimeError('Server exited')
                try:
                    if client.get('/health',timeout=2).status_code==200: break
                except httpx.HTTPError: pass
                time.sleep(1)
            else: raise RuntimeError('Load timeout')
            print('READY '+str(OUT),flush=True)
            if opts.nanbeige_thinking:
                check_messages = [{'role':'user','content':'Read a file'},
                    {'role':'assistant','content':'','reasoning_content':'PRESERVE_REASONING_42',
                     'tool_calls':[{'id':'check1','type':'function','function':{'name':'read_file','arguments':'{"path":"AGENTS.md"}'}}]},
                    {'role':'tool','tool_call_id':'check1','content':'File contents'}]
                check = client.post('/apply-template',json={'messages':check_messages,'tools':tools,'chat_template_kwargs':template_kwargs}).raise_for_status().json()
                report['reasoning_template_check'] = 'PRESERVE_REASONING_42' in check.get('prompt','')
                save()
                if not report['reasoning_template_check']: raise RuntimeError('Runtime did not preserve reasoning in template')
            if opts.probe_tools:
                probe = client.post('/v1/chat/completions', json={
                    'model':'bonsai-trial','messages':[{'role':'user','content':'Call read_file with path AGENTS.md now. Do not answer in prose.'}],
                    'tools':tools[:1], **sampling, 'max_tokens':2048 if opts.nanbeige_thinking else 512,
                    'chat_template_kwargs':template_kwargs
                }, timeout=90).raise_for_status().json()
                report['tool_probe'] = probe; save()
                calls = probe['choices'][0]['message'].get('tool_calls') or []
                if len(calls)!=1 or calls[0]['function']['name']!='read_file' or json.loads(calls[0]['function']['arguments'])!={'path':'AGENTS.md'}:
                    raise RuntimeError('Native tool compatibility probe failed; no project attempt')
                print('NATIVE TOOL PROBE PASS',flush=True)
            deadline=time.monotonic()+report['limit_seconds']
            for turn in range(24 if opts.test_feedback else 16):
                remaining=deadline-time.monotonic()
                if remaining<1: raise RuntimeError('Trial time limit')
                start=time.monotonic()
                response=client.post('/v1/chat/completions',json={'model':'bonsai-trial','messages':messages,'tools':tools,**sampling,'max_tokens':8192 if opts.nanbeige_thinking else 2200,'chat_template_kwargs':template_kwargs},timeout=httpx.Timeout(remaining)).raise_for_status().json()
                message=response['choices'][0]['message']
                report['turns'].append({'seconds':time.monotonic()-start,'response':response}); save()
                messages.append(message)
                calls=message.get('tool_calls') or []
                print('TURN '+str(turn+1)+' '+','.join(c['function']['name'] for c in calls),flush=True)
                if not calls:
                    finish=response['choices'][0].get('finish_reason')
                    report['finished']=finish=='stop'
                    report['stop']='response token limit' if finish=='length' else 'assistant returned without tools'
                    break
                for call in calls:
                    try:
                        function=call['function']; a=json.loads(function['arguments'])
                        if function['name']=='run_tests' and opts.test_feedback:
                            if a: raise ValueError('run_tests takes no arguments')
                            if len(report['test_runs'])>=3: raise ValueError('Three test runs exhausted')
                            result=fixed_tests()
                            messages.append({'role':'tool','tool_call_id':call['id'],'content':result})
                            if report['test_runs'][-1]['passed'] or len(report['test_runs'])>=3:
                                report['stop']='tests passed' if report['test_runs'][-1]['passed'] else 'two repair rounds exhausted'
                                return
                            continue
                        name=a['path']
                        if name not in baseline['files']: raise ValueError('Unknown path')
                        path=project/name
                        if function['name']=='read_file': result=path.read_text(); seen.add(name)
                        elif function['name']=='write_file':
                            if name not in allowed or name not in seen: raise ValueError('Write denied: protected or unread file')
                            if not isinstance(a['content'],str) or len(a['content'])>20000: raise ValueError('Invalid content')
                            path.write_text(a['content'],encoding='utf-8'); result='Written'
                        else: raise ValueError('Unknown tool')
                    except Exception as e: result='ERROR: '+str(e)
                    messages.append({'role':'tool','tool_call_id':call['id'],'content':result})
            else: report['stop']='turn limit'
    except Exception as e:
        report['error']=str(e); print('ERROR '+str(e),flush=True)
    finally:
        if server: stop(server)
        log.close()
        report['server_stopped']=server is None or server.poll() is not None
        report['changed']=[n for n,h in baseline['hashes'].items() if hashlib.sha256((project/n).read_bytes()).hexdigest()!=h]
        report['protected_intact']=all(n in allowed for n in report['changed'])
        save()
        if paused:
            subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/restore_e4b_prior_server.ps1'),'-Journal',str(OUT)],check=True,timeout=200)
        print('REPORT '+str(OUT/'report.json'),flush=True)

if __name__=='__main__': main()
