"""Owned, RAM-guarded launch of the already-installed Bonsai worker."""
import argparse
from pathlib import Path
import subprocess
import time

import psutil

from qwen35_local import ROOT, occupied, stop_owned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner-pid', type=int, required=True)
    args = parser.parse_args()
    owner = psutil.Process(args.owner_pid)
    candidates = [Path('E:/zengatrivi-drive-e/catts/external/Bonsai-demo'), Path('Z:/models/external/Bonsai-demo')]
    base = next((p for p in candidates if (p / 'bin/vulkan/llama-server.exe').is_file()
                 and (p / 'models/gguf/4B/Bonsai-4B-Q1_0.gguf').is_file()), None)
    if base is None:
        raise RuntimeError('Installed Bonsai runtime/model missing; no downloads attempted.')
    if any(occupied(p) for p in (8080, 9099, 9100, 9101, 9102)):
        raise RuntimeError('Existing workload preserved; a model port is occupied.')
    if psutil.virtual_memory().available < 2 * 1024**3:
        raise RuntimeError('Bonsai worker requires at least 2 GiB available RAM.')
    command = [str(base / 'bin/vulkan/llama-server.exe'), '-m',
               str(base / 'models/gguf/4B/Bonsai-4B-Q1_0.gguf'),
               '--host', '127.0.0.1', '--port', '9099', '--alias', 'bonsai-local',
               '-ngl', '99', '-fa', 'on', '-c', '8192', '-np', '1', '--device', 'Vulkan1',
               '--temp', '0.5', '--top-p', '0.85', '--top-k', '20', '--reasoning', 'off']
    started = time.monotonic()
    print('Loading installed Bonsai 4B; data/bonsai-worker.log', flush=True)
    with (ROOT / 'data/bonsai-worker.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            ready = False
            while process.poll() is None:
                if not owner.is_running():
                    break
                if psutil.virtual_memory().available < 1024**3:
                    raise RuntimeError('Bonsai RAM guard reached.')
                if not ready and occupied(9099):
                    ready = True
                    print(f'Bonsai port open after {time.monotonic() - started:.1f}s', flush=True)
                if not ready and time.monotonic() - started > 300:
                    raise RuntimeError('Bonsai startup timeout.')
                time.sleep(1)
            if process.returncode:
                raise RuntimeError(f'Bonsai exited {process.returncode}; see data/bonsai-worker.log')
        finally:
            if process.poll() is None:
                stop_owned(process)


if __name__ == '__main__':
    main()
