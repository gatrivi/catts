"""Foreground Qwen3.5 9B launcher with ownership and memory guard."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import psutil
import httpx

ROOT = Path(__file__).resolve().parents[1]
MODEL = Path('Z:/models/coding/Qwen3.5-9B/Qwen3.5-9B-Q4_K_M.gguf')
EXE = Path('Z:/models/runtime/llama-vulkan/llama-server.exe')
PIDFILE = ROOT/'data/qwen35.pid.json'


def occupied(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=0.3):
            return True
    except OSError:
        return False


def stop_owned(process):
    process.terminate()
    try:
        process.wait(timeout=10)
    except (subprocess.TimeoutExpired,psutil.TimeoutExpired):
        process.kill()
        process.wait(timeout=10)


def main():
    global MODEL, PIDFILE
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop',action='store_true')
    parser.add_argument('--expert', action='store_true', help='Use the measured 27B CPU/GPU consultant profile')
    parser.add_argument('--owner-pid', type=int, help='Stop when this launcher window exits')
    args = parser.parse_args()
    port = 9101 if args.expert else 9102
    label = 'Qwen27' if args.expert else 'Qwen3.5'
    alias = 'qwen27-local' if args.expert else 'qwen35-local'
    logname = 'qwen27-server.log' if args.expert else 'qwen35-server.log'
    if args.expert:
        MODEL = Path('Z:/models/coding/Qwen3.8-27B-Q3-DOWN-XS/Qwen3.8-27B-Q3-DOWN-XS.gguf')
        PIDFILE = ROOT/'data/qwen27.pid.json'
    owner = psutil.Process(args.owner_pid) if args.owner_pid else None
    if args.stop:
        if not PIDFILE.exists():
            print(f'No managed {label} PID recorded.')
            return
        record = json.loads(PIDFILE.read_text())
        try:
            process = psutil.Process(record['pid'])
            if process.create_time()!=record['created'] or Path(process.exe()).resolve()!=EXE.resolve():
                raise RuntimeError('PID no longer belongs to this model; refusing to stop it')
            stop_owned(process)
        except psutil.NoSuchProcess:
            pass
        PIDFILE.unlink(missing_ok=True)
        print(f'{label} stopped.')
        return
    if args.expert:
        if MODEL.stat().st_size != 8491269152:
            raise RuntimeError('Unexpected 27B file size')
    else:
        if not MODEL.exists() or not (MODEL.parent/'verified.json').exists():
            raise RuntimeError('Run scripts/download_qwen35.py first')
        metadata = json.loads((MODEL.parent/'verified.json').read_text())
        if MODEL.stat().st_size!=metadata['bytes']:
            raise RuntimeError('Model size changed since checksum verification')
    conflicts = [port for port in [8080,9099,9100,9101,9102] if occupied(port)]
    if conflicts:
        raise RuntimeError(f'Existing GPU workload/port: {conflicts}. Preserve it or stop it first.')
    # 9B: todo en VRAM con --no-mmap, el proceso queda en <1 GB de RAM (medido 876 MB).
    # 27B: -ngl 56 deja capas en RAM, por eso conserva el piso de 6 GiB.
    ram_floor = 6 if args.expert else 2
    if psutil.virtual_memory().available < ram_floor*1024**3:
        raise RuntimeError(f'Need at least {ram_floor} GiB free system RAM before this experiment')
    PIDFILE.parent.mkdir(parents=True,exist_ok=True)
    env = os.environ.copy()
    env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM']='1'
    command = [str(EXE),'-m',str(MODEL),'--host','127.0.0.1','--port',str(port),'--alias',alias,
        '--device','Vulkan1','-ngl','56' if args.expert else '99','-c','4096' if args.expert else '16384','-np','1','-ctk','q8_0','-ctv','q8_0','-fa','on',
        '--jinja','--reasoning','off','--reasoning-format','none','--chat-template-kwargs','{"enable_thinking":false}',
        '--no-warmup','--temp','0.2','--no-mmap','--cache-reuse','256']
    if args.expert:
        command += ['-b', '128', '-ub', '128']
    with (ROOT/'data'/logname).open('a',encoding='utf-8') as log:
        process = subprocess.Popen(command,stdout=log,stderr=log,env=env,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        PIDFILE.write_text(json.dumps({'pid':process.pid,'created':psutil.Process(process.pid).create_time()}))
        print(f'Loading {label}; log: data/{logname}. Ctrl+C stops this server.',flush=True)
        start = time.monotonic()
        ready = False
        try:
            while process.poll() is None:
                if owner is not None and not owner.is_running():
                    print('Launcher closed; stopping model.', flush=True)
                    break
                if psutil.virtual_memory().available < (1.5 if args.expert else 1)*1024**3:
                    raise RuntimeError('RAM guard reached; stopping model to protect the desktop')
                if not ready:
                    try:
                        ready = httpx.get(f'http://127.0.0.1:{port}/health',timeout=1).status_code==200
                    except httpx.HTTPError:
                        pass
                    if ready:
                        print(f'READY in {time.monotonic()-start:.1f}s: http://127.0.0.1:{port}',flush=True)
                    elif time.monotonic()-start>300:
                        raise RuntimeError('Startup exceeded five minutes; see log')
                time.sleep(2)
            if process.returncode:
                raise RuntimeError(f'Server exited {process.returncode}; see data/qwen35-server.log')
        finally:
            if process.poll() is None:
                stop_owned(process)
            PIDFILE.unlink(missing_ok=True)


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped.')
