"""Sweep local de variantes del kernel mul_mat_vec_ptq1_0 (fuentes en
kaggle/shader_variants/*.comp): por cada variante, reemplaza el .comp canonico,
rebuild (ninja test-backend-ops), corre correctness+perf y registra. Al final
restaura v0. Resultados: data/shader_sweep/sweep-<stamp>.json.

Uso: E:/.../python.exe scripts/shader_sweep.py [--skip v0_scalar,v1_packed16]
Nota: compila SIN -O (shim) -> sirve para RANKING; el ganador se optimiza via
Kaggle (shader_build_kernel) y se compara despues.
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
SRC = Path("C:/src/llama.cpp")
CANON = SRC / "ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vec_ptq1_0.comp"
VDIR = ROOT / "kaggle" / "shader_variants"
BUILD = SRC / "build"
TOOLPATH = ["C:/tools/bin", "C:/tools/llvm-mingw/bin", "C:/tools/glslang/bin",
            "E:/zengatrivi-drive-e/catts/.venv/Scripts"]
NINJA = "E:/zengatrivi-drive-e/catts/.venv/Scripts/ninja.exe"  # CreateProcess no usa el env PATH pasado


def run(cmd, timeout=900, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def bench(env):
    r = run([str(BUILD / "bin" / "test-backend-ops.exe"), "test", "-b", "Vulkan1",
             "-o", "MUL_MAT", "-p", "ptq1_0"], env=env, timeout=1200)
    ok = "3/3 backends passed" in r.stdout
    r2 = run([str(BUILD / "bin" / "test-backend-ops.exe"), "perf", "-b", "Vulkan1",
              "-o", "MUL_MAT", "-p", "ptq1_0.*n=1,"], env=env, timeout=1200)
    m = re.search(r"m=4096,n=1,k=14336[^\n]*?([\d.]+) us/run[^\n]*?([\d.]+)\s*(G|T)FLOPS", r2.stdout)
    if not m:
        return {"ok": ok, "perf_raw": r2.stdout[-300:]}
    us = float(m.group(1))
    gf = float(m.group(2)) * (1000 if m.group(3) == "T" else 1)
    return {"ok": ok, "us": us, "gflops": round(gf, 1)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--skip", default="")
    a = p.parse_args()
    skip = set(filter(None, a.skip.split(",")))
    import os
    env = dict(os.environ, PATH=";".join(TOOLPATH) + ";" + os.environ.get("PATH", ""))
    variants = sorted(v for v in VDIR.glob("*.comp") if v.stem not in skip)
    if not variants:
        raise SystemExit(f"sin variantes en {VDIR}")
    backup = CANON.read_text(encoding="utf-8")
    outdir = ROOT / "data" / "shader_sweep"
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        for v in variants:
            print(f"== {v.stem}", flush=True)
            shutil.copy(v, CANON)
            r = run([NINJA, "-C", str(BUILD), "-j", "2", "test-backend-ops"], env=env, timeout=1800)
            if r.returncode != 0:
                results.append({"variant": v.stem, "build": "fail",
                                "log": (r.stdout + r.stderr)[-400:]})
                print(f"   build FAIL", flush=True)
                continue
            res = bench(env)
            res.update(variant=v.stem, build="ok")
            results.append(res)
            print(f"   ok={res.get('ok')} us={res.get('us')} gflops={res.get('gflops')}", flush=True)
    finally:
        CANON.write_text(backup, encoding="utf-8")
        run([NINJA, "-C", str(BUILD), "-j", "2", "test-backend-ops"], env=env, timeout=1800)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = outdir / f"sweep-{stamp}.json"
    path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    good = [r for r in results if r.get("ok") and r.get("us")]
    if good:
        best = min(good, key=lambda r: r["us"])
        print(f"BEST: {best['variant']} {best['us']} us / {best['gflops']} GFLOPS")
    print(f"-> {path} (canonico restaurado a v0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
