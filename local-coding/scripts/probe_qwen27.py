"""Bounded 27B experiment; owns and always stops its server and test child."""
import json
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil
from qwen35_local import EXE, ROOT, occupied, stop_owned

MODEL = Path('Z:/models/coding/Qwen3.8-27B-Q3-DOWN-XS/Qwen3.8-27B-Q3-DOWN-XS.gguf')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--layers', type=int, default=56)
    parser.add_argument('--context', type=int, default=4096)
    args = parser.parse_args()
    if any(occupied(p) for p in (8080, 9099, 9100, 9101, 9102)):
        raise RuntimeError('A GPU service is already listening; preserve it.')
    if psutil.virtual_memory().available < 6 * 1024**3:
        raise RuntimeError('Need 6 GiB free RAM.')
    if MODEL.stat().st_size != 8491269152:
        raise RuntimeError('Unexpected model size.')
    with MODEL.open('rb') as handle:
        if handle.read(4) != b'GGUF':
            raise RuntimeError('Invalid GGUF header.')
    folder = ROOT / 'data' / ('qwen27-probe-' + time.strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True)
    report = {'model': str(MODEL), 'context': args.context, 'gpu_layers': args.layers,
              'mmap': False, 'batch': 128}
    server = test = None
    started = time.monotonic()
    try:
        with (folder / 'server.log').open('w', encoding='utf-8') as log:
            env = os.environ.copy()
            env['GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM'] = '1'
            server = subprocess.Popen([str(EXE), '-m', str(MODEL), '--host', '127.0.0.1',
                '--port', '9101', '--alias', 'qwen27-probe', '--device', 'Vulkan1',
                '-ngl', str(args.layers), '-c', str(args.context), '-np', '1', '-ctk', 'q8_0', '-ctv', 'q8_0',
                '--no-mmap', '-b', '128', '-ub', '128',
                '-fa', 'on', '--jinja', '--reasoning', 'off', '--no-warmup'],
                stdout=log, stderr=log, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
            ready = False
            while True:
                if psutil.virtual_memory().available < 1.5 * 1024**3:
                    raise RuntimeError('RAM guard: less than 1.5 GiB free.')
                if server.poll() is not None:
                    raise RuntimeError(f'Server exited {server.returncode}')
                elapsed = time.monotonic() - started
                if elapsed > 600:
                    raise RuntimeError('Ten-minute experiment limit reached.')
                if not ready:
                    try:
                        ready = httpx.get('http://127.0.0.1:9101/health', timeout=1).status_code == 200
                    except httpx.HTTPError:
                        pass
                    if ready:
                        report['startup_seconds'] = round(elapsed, 2)
                        print(f'READY in {elapsed:.1f}s', flush=True)
                        test = subprocess.Popen([sys.executable, str(ROOT/'scripts/local_coder_exercise.py'),
                            '--url', 'http://127.0.0.1:9101', '--out', str(folder/'exercises')], cwd=ROOT)
                    elif elapsed > 240:
                        raise RuntimeError('Four-minute startup limit reached.')
                elif test.poll() is not None:
                    report['test_exit_code'] = test.returncode
                    break
                time.sleep(2)
    except Exception as exc:
        report['error'] = str(exc)
        print(str(exc), flush=True)
    finally:
        for process in (test, server):
            if process is not None and process.poll() is None:
                stop_owned(process)
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        (folder/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'Stopped owned workers. Report: {folder}', flush=True)
    return 0 if report.get('test_exit_code') == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
