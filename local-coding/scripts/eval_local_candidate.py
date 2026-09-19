"""Bounded Gemma smoke, tool-use and cross-file trial; owns only its server."""
import ast,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import httpx,psutil
import argparse
parser=argparse.ArgumentParser(); parser.add_argument('--model',required=True); parser.add_argument('--label',required=True); parser.add_argument('--draft'); parser.add_argument('--smoke-only',action='store_true'); candidate=parser.parse_args()
root=Path(__file__).resolve().parents[1]
out=root/'data'/(candidate.label+'-eval-'+time.strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)
model=Path(candidate.model).resolve()
report={'context':8192,'runtime':'b95502ba9','model':str(model),'results':{}}
def save(): (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
manifest_path=model.parent/(model.name+'.verified.json')
if not manifest_path.exists(): manifest_path=model.parent/'verified.json'
if not model.exists() or not manifest_path.exists(): raise RuntimeError('Unverified model')
report['manifest']=json.loads(manifest_path.read_text())
if psutil.virtual_memory().available<4*1024**3: raise RuntimeError('Less than 4 GiB available RAM')
env=os.environ.copy(); env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM']='1'
args=['Z:/models/runtime/llama-vulkan/llama-server.exe','-m',str(model),'--host','127.0.0.1','--port','9103','--alias','local-candidate','--device','Vulkan1','-ngl','999','-c','8192','-np','1','-ctk','q8_0','-ctv','q8_0','-fa','on','--jinja','--no-warmup','--metrics','--no-mmap','-b','256','-ub','128','-lv','4']
if candidate.draft: args+=['--model-draft',candidate.draft,'--spec-type','draft-mtp','--spec-draft-n-max','4','--device-draft','Vulkan1','--gpu-layers-draft','999']
report['args']=args
log=(out/'server.log').open('w',encoding='utf-8')
p=None
try:
    import socket
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',9103))==0: raise RuntimeError('Port 9103 already occupied')
    p=subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    report['pid']=p.pid; save()
    with httpx.Client(base_url='http://127.0.0.1:9103',timeout=180) as c:
        for _ in range(120):
            if p.poll() is not None: raise RuntimeError('Server exited: '+str(p.returncode))
            if psutil.virtual_memory().available<1024**3: raise RuntimeError('Low RAM during load')
            try:
                if c.get('/health',timeout=2).status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(1)
        else: raise RuntimeError('Startup timeout')
        print('READY '+str(out),flush=True)
        def request(label,messages,max_tokens=1024):
            start=time.monotonic()
            r=c.post('/v1/chat/completions',json={'model':'local-candidate','messages':messages,'temperature':0,'max_tokens':max_tokens,'chat_template_kwargs':{'enable_thinking':False}})
            r.raise_for_status(); body=r.json()
            report['results'][label]={'seconds':round(time.monotonic()-start,2),'response':body,'available_ram':psutil.virtual_memory().available}; save()
            print(label+' '+json.dumps(body.get('timings',{})),flush=True)
            return body['choices'][0]['message'].get('content') or ''
        request('smoke',[{'role':'user','content':'Write a short Python function returning the first n Fibonacci numbers. Output only code.'}],256)
        if candidate.smoke_only: raise SystemExit(0)
        original={'units.py':'def cents_to_dollars(cents):\n    return cents // 100\n','receipt.py':'def receipt_total(items):\n    return sum(cents_to_dollars(cents) for cents in items)\n'}
        task='Update BOTH files: rename cents_to_dollars to cents_to_amount everywhere, fix fractional conversion, and reject negative individual cents with ValueError. Keep receipt_total name and support empty input. Files are loaded into one shared namespace by the host; do not add imports. Return ONLY a JSON object mapping these two exact filenames to their complete new contents. No markdown. Files:\n'+json.dumps(original)
        answer=request('cross_file',[{'role':'user','content':task}],1400)
        try:
            files=json.loads(answer)
            assert set(files)==set(original),'Expected exactly two files'
            for name,code in files.items():
                assert isinstance(code,str) and len(code)<8000
                tree=ast.parse(code)
                assert all(isinstance(n,ast.FunctionDef) for n in tree.body),'Functions only'
                for n in ast.walk(tree):
                    assert not isinstance(n,(ast.Import,ast.ImportFrom,ast.Attribute,ast.While,ast.With,ast.ClassDef,ast.AsyncFunctionDef)),'Unsupported syntax'
                    if isinstance(n,ast.Name): assert not n.id.startswith('__')
                    if isinstance(n,ast.FunctionDef): assert not n.decorator_list and not n.args.defaults and not n.args.kw_defaults
                    if isinstance(n,ast.Call): assert isinstance(n.func,ast.Name) and n.func.id in {'sum','ValueError','cents_to_amount'}
                assert 'cents_to_dollars' not in code,'Old name remains'
                (out/name).write_text(code)
            code=files['units.py']+'\n'+files['receipt.py']+'\nassert cents_to_amount(150)==1.5\nassert receipt_total([150,225])==3.75\nassert receipt_total([])==0\ntry:\n receipt_total([100,-1])\nexcept ValueError: pass\nelse: raise AssertionError("negative accepted")\nprint("PASS")\n'
            result=subprocess.run([sys.executable,'-I','-c',code],capture_output=True,text=True,timeout=5)
            report['results']['cross_file']['passed']=result.returncode==0
            report['results']['cross_file']['test_output']=result.stdout+result.stderr
        except Exception as e: report['results']['cross_file'].update(passed=False,error=str(e))
        save(); print('CROSS_FILE '+str(report['results']['cross_file']['passed']),flush=True)
        filler='\n'.join(f'record {i}: inactive historical placeholder; ignore this record.' for i in range(600))
        context_prompt='Remember start marker ALPHA42.\n'+filler+'\nEnd marker OMEGA73. Return only the start and end markers.'
        while len(c.post('/tokenize',json={'content':context_prompt}).json()['tokens'])>6800:
            filler=filler[:int(len(filler)*0.9)]
            context_prompt='Remember start marker ALPHA42.\n'+filler+'\nEnd marker OMEGA73. Return only the start and end markers.'
        actual=request('context_probe',[{'role':'user','content':context_prompt}],128)
        report['results']['context_probe']['passed']='ALPHA42' in actual and 'OMEGA73' in actual
        save()
        result=subprocess.run([sys.executable,str(root/'scripts/local_coder_exercise.py'),'--url','http://127.0.0.1:9103','--out',str(out/'tool-exercise')],timeout=480)
        report['tool_exercise_exit']=result.returncode; save()
except Exception as e:
    report['error']=str(e); print('ERROR '+str(e),flush=True)
finally:
    if p is not None and p.poll() is None:
        p.terminate()
        try: p.wait(timeout=15)
        except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=10)
    report['server_stopped']=p is None or p.poll() is not None
    log.close(); save(); print('REPORT '+str(out/'report.json'),flush=True)





