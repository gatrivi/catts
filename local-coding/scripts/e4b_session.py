"""Dedicated supervised E4B/OMP session; owns and cleans up its runtime."""
import argparse,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
import httpx,psutil
ROOT=Path(__file__).resolve().parents[1]
PYTHON=Path('E:/zengatrivi-drive-e/catts/.venv/Scripts/python.exe')
RUNTIME=Path('Z:/models/runtime/llama-vulkan/llama-server.exe')
MODEL=ROOT/'data/models/gemma-e4b-qat/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf'
OMP=Path(os.environ['USERPROFILE'])/'.bun/bin/omp.exe'
PROFILE=ROOT/'data/e4b-omp'

def stop(process):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=15)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)

def main():
    parser=argparse.ArgumentParser(description='Editor E4B local con aprobacion de escrituras.')
    parser.add_argument('project',nargs='?')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--prompt')
    parser.add_argument('--print',action='store_true',dest='print_mode')
    parser.add_argument('--pause-qwen',action='store_true',help='Pausar Qwen2.5 :8123 y restaurarlo al salir.')
    parser.add_argument('--trial',action='store_true',help='Solo fixtures en data/e4b-project-trials; autoaprobar sus ediciones.')
    opts=parser.parse_args()
    for path in (PYTHON,RUNTIME,MODEL,OMP,MODEL.with_name(MODEL.name+'.verified.json'),ROOT/'config/e4b-omp/models.yml',ROOT/'config/e4b-omp/config.yml'):
        if not path.is_file(): raise RuntimeError('Falta: '+str(path))
    verified=json.loads(MODEL.with_name(MODEL.name+'.verified.json').read_text(encoding='utf-8-sig'))
    if MODEL.stat().st_size!=verified['bytes']: raise RuntimeError('Model size differs from verified manifest')
    if opts.check:
        print('OK: runtime, modelo verificado y editor presentes. No se inicio ningun modelo.')
        return 0
    project=Path(opts.project or input('Carpeta del proyecto: ').strip().strip('"')).resolve()
    if not project.is_dir(): raise RuntimeError('No existe el proyecto')
    if opts.trial and not project.is_relative_to(ROOT/'data/e4b-project-trials'):
        raise RuntimeError('--trial solo permite proyectos descartables bajo data/e4b-project-trials')
    prior=None
    for process in psutil.process_iter(['pid','name','exe','cmdline','create_time']):
        info=process.info
        if info['name']!='llama-server.exe': continue
        cmd=info['cmdline'] or []
        is_qwen=(info['exe'] and Path(info['exe']).resolve()==Path('Z:/ai/llama.cpp/llama-server.exe').resolve() and '8123' in cmd and any('qwen2.5-coder-7b-instruct-q4_k_m.gguf' in arg for arg in cmd))
        if not is_qwen or not opts.pause_qwen or prior is not None:
            raise RuntimeError('Otro modelo activo. Para pausar/restaurar el Qwen2.5 conocido, usa --pause-qwen.')
        prior=info
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',9103))==0: raise RuntimeError('Puerto 9103 ocupado')
    journal=ROOT/'data'/('e4b-session-'+time.strftime('%Y%m%d-%H%M%S'))
    journal.mkdir(parents=True)
    PROFILE.mkdir(parents=True,exist_ok=True)
    for name in ('models.yml','config.yml'):
        if not (PROFILE/name).exists(): shutil.copyfile(ROOT/'config/e4b-omp'/name,PROFILE/name)
    env=os.environ.copy(); env['PI_CODING_AGENT_DIR']=str(PROFILE)
    env.pop('OMP_PROFILE',None)
    env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM']='1'
    server=None; log=None; paused=False
    report={'project':str(project),'trial':opts.trial,'model':str(MODEL),'manifest':verified}
    try:
        if prior:
            p=psutil.Process(prior['pid'])
            if p.create_time()!=prior['create_time'] or p.cmdline()!=prior['cmdline']: raise RuntimeError('Servidor previo cambio')
            (journal/'prior-server.json').write_text(json.dumps({'executable':prior['exe'],'argumentLine':subprocess.list2cmdline(prior['cmdline'][1:]),'pid':prior['pid']},indent=2))
            p.terminate(); paused=True; p.wait(timeout=20)
            print('Qwen2.5 pausado; se restaura al salir.',flush=True)
        if psutil.virtual_memory().available<3*1024**3: raise RuntimeError('Menos de 3 GiB RAM libres')
        argv=[str(RUNTIME),'-m',str(MODEL),'--host','127.0.0.1','--port','9103','--alias','gemma-e4b-local','--device','Vulkan1','-ngl','999','-c','16384','-np','1','-ctk','q8_0','-ctv','q8_0','-fa','on','--jinja','--no-warmup','--metrics','--no-mmap','-b','256','-ub','128','--reasoning','off','-lv','4']
        report['server_args']=argv
        log=(journal/'server.log').open('w',encoding='utf-8')
        server=subprocess.Popen(argv,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        report['server_pid']=server.pid
        deadline=time.monotonic()+300
        with httpx.Client(base_url='http://127.0.0.1:9103',timeout=2) as client:
            while time.monotonic()<deadline:
                if server.poll() is not None: raise RuntimeError('Servidor fallo; ver '+str(journal/'server.log'))
                if psutil.virtual_memory().available<1024**3: raise RuntimeError('RAM disponible demasiado baja')
                try:
                    if client.get('/health').status_code==200: break
                except httpx.HTTPError: pass
                time.sleep(1)
            else: raise RuntimeError('Tiempo de carga agotado')
            if client.get('/v1/models').json()['data'][0]['id']!='gemma-e4b-local': raise RuntimeError('Modelo inesperado')
        role='e4b/gemma-e4b-local'
        agent=[str(OMP),'--cwd',str(project),'--model',role,'--smol',role,'--slow',role,'--plan',role,'--thinking','off','--no-title','--no-extensions','--no-skills','--no-lsp','--no-pty','--no-prewalk','--tools','read,write,grep,glob','--approval-mode','write','--max-time','6m','--system-prompt','You are a supervised local coding assistant. Read AGENTS.md if present, then relevant files before editing. Complete one small task. Preserve unrelated code and tests. Do not use shell, network, subagents or external tools. Use read to inspect each affected file, then write its complete corrected contents. No edit tool is available. Keep explanations short; do not emit a long plan or repeat file contents in prose. After two unsuccessful repair attempts stop and explain. No test runner is available: provide the exact test command for the user and never claim tests passed. Keep your final answer concise.']
        if opts.print_mode: agent+=['--print','--mode','json']
        if opts.trial: agent+=['--auto-approve','--no-session']
        if opts.prompt: agent.append(opts.prompt)
        report['agent_args']=agent
        print('E4B listo. Aprobacion de escrituras activa.' if not opts.trial else 'E4B listo. Prueba descartable autoaprobada.',flush=True)
        if opts.print_mode:
            with (journal/'agent.jsonl').open('w',encoding='utf-8') as output, (journal/'agent.stderr.log').open('w',encoding='utf-8') as errors:
                run=subprocess.run(agent,env=env,stdout=output,stderr=errors,timeout=420)
        else: run=subprocess.run(agent,env=env)
        if opts.print_mode:
            failures=[]
            for line in (journal/'agent.jsonl').read_text(encoding='utf-8').splitlines():
                try: event=json.loads(line)
                except ValueError: continue
                message=event.get('message',{})
                if event.get('type')=='message_end' and message.get('role')=='assistant' and message.get('stopReason')=='error': failures.append(message.get('errorMessage','Model request failed'))
            if failures: report['model_errors']=failures
        report['agent_exit']=run.returncode
        return run.returncode or (2 if report.get('model_errors') else 0)
    except Exception as e:
        report['error']=str(e); raise
    finally:
        if server: stop(server)
        if log: log.close()
        report['server_stopped']=server is None or server.poll() is not None
        (journal/'session.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        if paused:
            result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/restore_e4b_prior_server.ps1'),'-Journal',str(journal)],timeout=480)
            if result.returncode: raise RuntimeError('Revisar restauracion en '+str(journal))
        print('Registro: '+str(journal),flush=True)

if __name__=='__main__': raise SystemExit(main())


