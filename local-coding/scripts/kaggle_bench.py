"""Driver de Kaggle para el bench-shortlist: push/status/pull del kernel GPU.

Uso:
  python scripts/kaggle_bench.py check
  python scripts/kaggle_bench.py push  [--candidates kaggle/candidates.json] [--slug N]
                                       [--golden] [--estimate-hours H] [--dry-run] [--force]
  python scripts/kaggle_bench.py status --slug N
  python scripts/kaggle_bench.py pull   --slug N

Genera el kernel (kaggle/bench_kernel.py + candidatos inlined), aplica el
presupuesto semanal (data/kaggle/quota_ledger.json, 30 h/semana por defecto),
empuja con la CLI de kaggle, y descarga results.json a data/kaggle_runs/<slug>/.
Requiere ~/.kaggle/kaggle.json (o KAGGLE_CONFIG_DIR) y el paquete kaggle en el
venv de E:. Ganadores: se descargan localmente SOLO con OK del usuario via
download_verified_model.py.
"""
import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import scripts.local_models as lm
except ImportError:
    import local_models as lm

ROOT = lm.ROOT
TEMPLATE = ROOT / 'kaggle' / 'bench_kernel.py'
GOLDEN_TEMPLATE = ROOT / 'kaggle' / 'golden_kernel.py'
GOLDEN_PROMPTS = ROOT / 'kaggle' / 'golden_prompts.json'
SHADER_TEMPLATE = ROOT / 'kaggle' / 'shader_build_kernel.py'
SHADER_VARIANTS = ROOT / 'kaggle' / 'shader_variants'
SHADER_TYPES = Path('C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/types.glsl')
LEDGER = ROOT / 'data' / 'kaggle' / 'quota_ledger.json'
DEFAULT_BUDGET_H = 30
DEFAULT_ESTIMATE_PER_CAND = 0.6  # descarga + bench por candidato en T4, horas
GOLDEN_EST_H = 0.6               # golden: 1 modelo, ~1200 tokens greedy en T4
OVERHEAD_H = 0.3


# --- utilidades planas, patcheables en tests -------------------------------

def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def kaggle_cmd():
    exe = shutil.which('kaggle')
    return [exe] if exe else [sys.executable, '-m', 'kaggle']


def kaggle_conf():
    """kaggle.json clasico, o token-file ~/.kaggle/access_token (username via `kaggle config view`, cache en data/kaggle/user.json)."""
    import os
    base = Path(os.environ.get('KAGGLE_CONFIG_DIR', Path.home() / '.kaggle'))
    f = base / 'kaggle.json'
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            return None
    if (base / 'access_token').is_file():
        cache = ROOT / 'data' / 'kaggle' / 'user.json'
        if cache.is_file():
            try:
                u = json.loads(cache.read_text(encoding='utf-8')).get('username')
                if u:
                    return {'username': u, 'auth': 'token'}
            except Exception:
                pass
        r = run(kaggle_cmd() + ['config', 'view'], timeout=60)
        m = re.search(r'username:\s*(\S+)', r.stdout or '')
        if m:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({'username': m.group(1)}), encoding='utf-8')
            return {'username': m.group(1), 'auth': 'token'}
    return None


def week_key():
    iso = datetime.date.today().isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def read_ledger():
    if LEDGER.is_file():
        try:
            return json.loads(LEDGER.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {'budget_h': DEFAULT_BUDGET_H, 'weeks': {}}


def quota_check(needed_h):
    """(ok, usado, presupuesto) para la semana ISO actual."""
    led = read_ledger()
    used = led['weeks'].get(week_key(), 0.0)
    return used + needed_h <= led['budget_h'] + 1e-9, used, led['budget_h']


def quota_log(h):
    led = read_ledger()
    wk = week_key()
    led['weeks'][wk] = round(led['weeks'].get(wk, 0.0) + h, 2)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=1), encoding='utf-8')
    return led['weeks'][wk]


def load_candidates(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    items = [c for c in data.get('items', []) if c.get('repo') and c.get('file')]
    if not items:
        raise SystemExit(f'{path}: ningun candidato con repo+file; edita kaggle/candidates.json')
    return items


def generate_kernel(items, workdir):
    """Copia la plantilla con los candidatos inlined + kernel-metadata.json."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE.is_file():
        raise SystemExit(f'plantilla no encontrada: {TEMPLATE}')
    src = TEMPLATE.read_text(encoding='utf-8')
    marker = 'CANDIDATES = __CANDIDATES__'
    if marker not in src:
        raise SystemExit(f'{TEMPLATE}: falta el marcador {marker!r}')
    src = src.replace(marker, f'CANDIDATES = {repr(items)}', 1)
    (workdir / 'bench_kernel.py').write_text(src, encoding='utf-8')
    user = kaggle_conf()
    if not user or not user.get('username'):
        raise SystemExit('kaggle.json no encontrado (usa KAGGLE_CONFIG_DIR o ~/.kaggle/kaggle.json)')
    return user['username'], workdir


def generate_golden_kernel(items, workdir):
    """Igual que generate_kernel pero con la plantilla golden (candidatos + spec congelado)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    for f in (GOLDEN_TEMPLATE, GOLDEN_PROMPTS):
        if not f.is_file():
            raise SystemExit(f'plantilla no encontrada: {f}')
    src = GOLDEN_TEMPLATE.read_text(encoding='utf-8')
    for marker in ('CANDIDATES = __CANDIDATES__', 'PROMPTS = __PROMPTS__'):
        if marker not in src:
            raise SystemExit(f'{GOLDEN_TEMPLATE}: falta el marcador {marker!r}')
    spec = json.loads(GOLDEN_PROMPTS.read_text(encoding='utf-8'))
    src = src.replace('CANDIDATES = __CANDIDATES__', f'CANDIDATES = {repr(items)}', 1)
    src = src.replace('PROMPTS = __PROMPTS__', 'PROMPTS = ' + repr(spec), 1)
    (workdir / 'golden_kernel.py').write_text(src, encoding='utf-8')
    user = kaggle_conf()
    if not user or not user.get('username'):
        raise SystemExit('kaggle.json no encontrado (usa KAGGLE_CONFIG_DIR o ~/.kaggle/kaggle.json)')
    return user['username'], workdir


def generate_shader_kernel(workdir):
    """Kernel CPU que compila las variantes del shader ptq1_0 con glslang+spirv-opt -O."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if not SHADER_TEMPLATE.is_file():
        raise SystemExit(f'plantilla no encontrada: {SHADER_TEMPLATE}')
    if not SHADER_TYPES.is_file():
        raise SystemExit(f'types.glsl del build local no encontrado: {SHADER_TYPES}')
    payload = {'__types_glsl__': SHADER_TYPES.read_text(encoding='utf-8')}
    for v in sorted(SHADER_VARIANTS.glob('*.comp')):
        payload[v.stem] = v.read_text(encoding='utf-8')
    if len(payload) < 2:
        raise SystemExit(f'sin variantes en {SHADER_VARIANTS}')
    src = SHADER_TEMPLATE.read_text(encoding='utf-8')
    if 'PAYLOAD = __PAYLOAD__' not in src:
        raise SystemExit('falta el marcador PAYLOAD = __PAYLOAD__')
    src = src.replace('PAYLOAD = __PAYLOAD__', 'PAYLOAD = ' + repr(payload), 1)
    (workdir / 'shader_build_kernel.py').write_text(src, encoding='utf-8')
    user = kaggle_conf()
    if not user or not user.get('username'):
        raise SystemExit('kaggle.json/token no encontrado')
    return user['username'], workdir


def write_metadata(workdir, user, slug, code_file='bench_kernel.py', enable_gpu=True):
    meta = {
        'id': f'{user}/{slug}',
        'title': slug.replace('-', ' ')[:60],
        'code_file': code_file,
        'language': 'python',
        'kernel_type': 'script',
        'enable_gpu': enable_gpu,
        'enable_internet': True,
        'dataset_sources': [],
        'competition_sources': [],
        'kernel_sources': [],
        'model_sources': [],
    }
    (Path(workdir) / 'kernel-metadata.json').write_text(json.dumps(meta, indent=1), encoding='utf-8')
    return meta


def parse_status(out):
    m = re.search(r'has status "?([A-Za-z]+)"?', out or '')
    return m.group(1).lower() if m else None


# --- verbos -----------------------------------------------------------------

def cmd_check(a):
    conf = kaggle_conf()
    ok = bool(conf and conf.get('username'))  # key solo aplica al kaggle.json clasico
    print('kaggle.json:', 'ok' if ok else 'FALTA (descargalo de kaggle.com -> Account -> API)')
    r = run(kaggle_cmd() + ['--version'])
    print('CLI kaggle:', (r.stdout or r.stderr).strip()[:80] or 'NO INSTALADA (pip install kaggle)')
    led = read_ledger()
    used = led['weeks'].get(week_key(), 0.0)
    print(f"cuota esta semana: {used:.1f} / {led['budget_h']} h")
    return 0 if ok and r.returncode == 0 else 2


def cmd_push(a):
    golden = getattr(a, 'golden', False)
    shader = getattr(a, 'shader', False)
    items = load_candidates(a.candidates)
    if shader:
        est = a.estimate_hours if a.estimate_hours is not None else 0.2
    elif golden:
        est = a.estimate_hours if a.estimate_hours is not None else round(OVERHEAD_H + GOLDEN_EST_H, 2)
    else:
        est = a.estimate_hours if a.estimate_hours is not None else round(OVERHEAD_H + DEFAULT_ESTIMATE_PER_CAND * len(items), 2)
    ok, used, budget = quota_check(est)
    tag = ' (shader)' if shader else ' (golden)' if golden else ''
    print(f'candidatos: {len(items)}{tag} | estimado {est} h | semana {week_key()}: {used:.1f}/{budget} h')
    if not ok and not a.force:
        raise SystemExit(f'ABORT: excede el presupuesto semanal ({used + est:.1f} > {budget} h). --force para ignorar.')
    stamp = datetime.datetime.now().strftime('%Y%m%d')
    slug = a.slug or (f'shader-{stamp}' if shader else f'gold-{stamp}' if golden else f'bench-{stamp}')
    workdir = ROOT / 'data' / 'kaggle' / f'push-{slug}'
    if shader:
        user, workdir = generate_shader_kernel(workdir)
        write_metadata(workdir, user, slug, code_file='shader_build_kernel.py', enable_gpu=False)
    elif golden:
        user, workdir = generate_golden_kernel(items, workdir)
        write_metadata(workdir, user, slug, code_file='golden_kernel.py')
    else:
        user, workdir = generate_kernel(items, workdir)
        write_metadata(workdir, user, slug)
    print('kernel generado en', workdir)
    if a.dry_run:
        print('dry-run: no se empuja. Revisa bench_kernel.py y kernel-metadata.json ahi.')
        return 0
    r = run(kaggle_cmd() + ['kernels', 'push', '-p', str(workdir)], timeout=300)
    print((r.stdout or '') + (r.stderr or ''))
    if r.returncode != 0:
        return r.returncode or 1
    quota_log(est)
    print(f'registrado {est} h en la cuota. status: kaggle_bench.py status --slug {slug}')
    return 0


def cmd_status(a):
    conf = kaggle_conf()
    if not conf:
        raise SystemExit('kaggle.json no encontrado')
    r = run(kaggle_cmd() + ['kernels', 'status', f"{conf['username']}/{a.slug}"], timeout=120)
    print((r.stdout or r.stderr).strip())
    st = parse_status(r.stdout + r.stderr)
    if st == 'complete':
        print('listo para pull: kaggle_bench.py pull --slug', a.slug)
    return r.returncode


def cmd_pull(a):
    conf = kaggle_conf()
    if not conf:
        raise SystemExit('kaggle.json no encontrado')
    dest = ROOT / 'data' / 'kaggle_runs' / a.slug
    dest.mkdir(parents=True, exist_ok=True)
    r = run(kaggle_cmd() + ['kernels', 'output', f"{conf['username']}/{a.slug}", '-p', str(dest)], timeout=600)
    print((r.stdout or r.stderr).strip())
    if r.returncode != 0:
        return r.returncode
    res = dest / 'results.json'
    if res.is_file():
        for item in json.loads(res.read_text(encoding='utf-8')):
            if item.get('status') == 'ok':
                print(f"{item['name']}: tg {item['decode']['tg_tps']:.1f} t/s | pp {item['pp']['pp_tps']:.1f} t/s")
            else:
                print(f"{item.get('name')}: {item.get('status')}")
    else:
        print('sin results.json; revisa el log del kernel en la web de Kaggle')
    gold = dest / 'golden.json'
    if gold.is_file():
        g = json.loads(gold.read_text(encoding='utf-8'))
        print(f"golden spec {g.get('spec_hash')}:")
        for m in g.get('models', []):
            if m.get('status') == 'ok':
                toks = sum(p.get('n') or 0 for p in m.get('prompts', []))
                print(f"  {m['name']}: {len(m.get('prompts', []))} prompts, {toks} tokens, logprobs={m.get('logprobs_mode')}")
            else:
                print(f"  {m.get('name')}: {m.get('status')}")
        print('comparar local: python scripts/golden_check.py <golden.json> <dump de golden_capture.py>')
    spvdir = dest / 'spv'
    if spvdir.is_dir():
        n = len(list(spvdir.glob('*.spv')))
        print(f"spv precompilados: {n} en {spvdir}")
        print('importar: copiar a C:/tools/bin/spv-precompiled/ y ninja test-backend-ops (shim los usa por clave fnv)')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='verb', required=True)
    sub.add_parser('check')
    push = sub.add_parser('push')
    push.add_argument('--candidates', default=str(ROOT / 'kaggle' / 'candidates.json'))
    push.add_argument('--slug', default=None)
    push.add_argument('--estimate-hours', type=float, default=None)
    push.add_argument('--golden', action='store_true',
                      help='kernel golden-reference (golden_kernel.py + spec congelado)')
    push.add_argument('--shader', action='store_true',
                      help='kernel CPU que compila variantes del shader ptq1_0 con spirv-opt -O')
    push.add_argument('--dry-run', action='store_true')
    push.add_argument('--force', action='store_true')
    st = sub.add_parser('status')
    st.add_argument('--slug', required=True)
    pull = sub.add_parser('pull')
    pull.add_argument('--slug', required=True)
    a = p.parse_args()
    return {'check': cmd_check, 'push': cmd_push, 'status': cmd_status, 'pull': cmd_pull}[a.verb](a)


if __name__ == '__main__':
    raise SystemExit(main())
