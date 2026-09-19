"""Wan2GP manager: check / rebuild / launch image+video gen on the RX6600.

The Z:\\AI\\WanGP install exists (app + venv + model slots + AMD doc) but:
  - its venv base Python is gone -> venv unusable until rebuilt;
  - no weights are downloaded (all model dirs ~0 GB);
  - upstream has no RDNA2 (gfx103X) GPU profile: RX6600 runs via TheRock
    staging wheels (experimental, MIOpen unstable -> FAST mode, see docs).

This script never touches Z:\\AI\\WanGP\\Wan2GP sources. Downloads happen
only under --rebuild --yes (multi-GB, Z: only).

  python scripts/wangp_local.py --check     # state, no changes, no loads
  python scripts/wangp_local.py --rebuild   # print plan only
  python scripts/wangp_local.py --rebuild --yes   # venv + torch + deps (downloads)
  python scripts/wangp_local.py --launch    # Gradio UI (needs venv + weights)
"""
import argparse, os, subprocess, sys
from pathlib import Path

WANGP = Path('Z:/AI/WanGP/Wan2GP')
VENV = Path('Z:/AI/WanGP/venv')
VENV_PY = VENV / 'Scripts/python.exe'
# TheRock staging for RDNA2 (gfx103X-dgpu); see Wan2GP docs/AMD-INSTALLATION.md.
THEROCK_INDEX = 'https://rocm.nightlies.amd.com/v2-staging/gfx103X-dgpu/'
# Model slots that fit 8GB: Wan 2.1 1.3B video, FLUX low-step image.
# Weights auto-download inside Wan2GP on first use (several GB each, Z:).
SLOTS = ('wan', 'flux')

AMD_ENV = {
    'MIOPEN_FIND_MODE': 'FAST',
    'FLASH_ATTENTION_TRITON_AMD_ENABLE': 'TRUE',
    'TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL': '1',
}


def rocm_bins():
    sp = VENV / 'Lib/site-packages'
    return [str(sp / '_rocm_sdk_core/bin'), str(sp / '_rocm_sdk_devel/bin'),
            str(sp / '_rocm_sdk_libraries_gfx103X_dgpu/bin')]


def slot_gb(slot):
    p = WANGP / 'models' / slot
    if not p.is_dir():
        return None
    return sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) / 2**30


def check():
    ok = True
    print('Wan2GP:', WANGP, 'exists:', WANGP.is_dir())
    print('venv python:', VENV_PY, 'exists:', VENV_PY.exists())
    if VENV_PY.exists():
        r = subprocess.run([str(VENV_PY), '-c',
            "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"],
            capture_output=True, text=True, timeout=120)
        print((r.stdout or r.stderr).strip() or '(no output)')
        ok = ok and r.returncode == 0 and 'cuda True' in (r.stdout or '')
    else:
        print('venv BROKEN (base Python gone): run --rebuild --yes')
        ok = False
    for s in SLOTS:
        gb = slot_gb(s)
        print(f'slot {s}: {gb:.2f} GB' if gb is not None else f'slot {s}: MISSING DIR')
        if not gb:
            ok = False
    print('CHECK', 'OK' if ok else 'GAPS (see above)')
    return 0 if ok else 1


def rebuild(download):
    print('Plan: recreate', VENV, 'with Python 3.11, install TheRock torch')
    print(' ', THEROCK_INDEX)
    print('  then Wan2GP requirements.txt. All weight/model data stays on Z:.')
    print('  Weights (~GBs per slot: wan_1.3B video, flux image) download on')
    print('  first launch inside Wan2GP, or pre-fetch manually into models/.')
    if not download:
        print('Dry run: nothing changed. Re-run with --yes to download.')
        return 0
    py = None
    for cand in (['py', '-3.11'], ['python']):
        try:
            subprocess.run(cand + ['--version'], check=True,
                           capture_output=True, timeout=30)
            py = cand
            break
        except Exception:
            continue
    if not py:
        print('No system Python 3.11 found: install it first.'); return 1
    subprocess.run(py + ['-m', 'venv', str(VENV)], check=True)
    pip = [str(VENV_PY), '-m', 'pip']
    subprocess.run(pip + ['install', '--upgrade', 'pip'], check=True)
    subprocess.run(pip + ['install', '--pre', 'torch', 'torchaudio',
        'torchvision', 'rocm[devel]', '--index-url', THEROCK_INDEX], check=True)
    subprocess.run(pip + ['install', '-r', str(WANGP / 'requirements.txt')],
                   check=True, cwd=str(WANGP))
    print('Rebuild done. Re-run --check to verify torch + slots.')
    return 0


def launch():
    if not VENV_PY.exists():
        print('venv broken: run --rebuild --yes first.'); return 1
    if not (WANGP / 'wgp.py').exists():
        print('wgp.py missing.'); return 1
    env = dict(os.environ, **AMD_ENV)
    env['PATH'] = os.pathsep.join(rocm_bins()) + os.pathsep + env.get('PATH', '')
    print('Launching Wan2GP (Gradio UI). Close the window / Ctrl+C to stop.')
    print('First run downloads weights for the selected slot (Z:).')
    return subprocess.run([str(VENV_PY), 'wgp.py'], cwd=str(WANGP), env=env).returncode


def main():
    ap = argparse.ArgumentParser(description='Wan2GP image/video manager (RX6600)')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--rebuild', action='store_true')
    ap.add_argument('--yes', action='store_true', help='allow downloads (Z: only)')
    ap.add_argument('--launch', action='store_true')
    args = ap.parse_args()
    if args.check or not (args.rebuild or args.launch):
        return check()
    if args.rebuild:
        return rebuild(args.yes)
    return launch()


if __name__ == '__main__':
    sys.exit(main())
