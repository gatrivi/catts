"""Compara dos golden dumps (golden.json de Kaggle vs un run local HIP/Vulkan).

Uso:
  python scripts/golden_check.py a.json b.json

Exit 0 = sin divergencia; 1 = divergencia (o prompt faltante/erroneo) en >=1
prompt; 2 = error estructural (nada comparable). La divergencia temprana en
generacion greedy es la senal de un kernel erroneo; deltas de logprob grandes
con texto igual senalan numerica distinta (menos grave, registrar).
"""
import argparse
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]


def first_diff(a, b):
    if a == b:
        return None
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return i


def prompt_metrics(pa, pb):
    m = {"id": pa.get("id")}
    if pa.get("status") or pb.get("status"):
        m["error"] = pa.get("status") or pb.get("status")
        return m
    ta, tb = pa.get("text") or "", pb.get("text") or ""
    m["chars"] = [len(ta), len(tb)]
    m["first_diff_char"] = first_diff(ta, tb)
    ka = [t.get("t") for t in (pa.get("tokens") or [])]
    kb = [t.get("t") for t in (pb.get("tokens") or [])]
    if ka and kb:
        m["tokens"] = [len(ka), len(kb)]
        m["first_diff_token"] = first_diff(ka, kb)
        la = [t.get("lp") for t in pa["tokens"]]
        lb = [t.get("lp") for t in pb["tokens"]]
        ds = [abs(x - y) for x, y in zip(la, lb) if x is not None and y is not None]
        if ds:
            m["lp_max_d"] = round(max(ds), 4)
            m["lp_mean_d"] = round(sum(ds) / len(ds), 4)
    return m


def compare_golds(a, b):
    out = {"spec_hash": [a.get("spec_hash"), b.get("spec_hash")],
           "spec_match": a.get("spec_hash") == b.get("spec_hash"),
           "models": [], "structural_error": None}
    bm = {m.get("name") or m.get("file"): m for m in b.get("models", [])}
    pairs = 0
    for ma in a.get("models", []):
        mb = bm.get(ma.get("name") or ma.get("file"))
        if not mb:
            out["models"].append({"name": ma.get("name"), "missing_in_b": True})
            continue
        bp = {p.get("id"): p for p in mb.get("prompts") or []}
        prompts = []
        for pa in ma.get("prompts") or []:
            pb = bp.get(pa.get("id"))
            if pb is None:
                prompts.append({"id": pa.get("id"), "missing_in_b": True})
                continue
            pairs += 1
            prompts.append(prompt_metrics(pa, pb))
        out["models"].append({"name": ma.get("name"),
                              "status": [ma.get("status"), mb.get("status")],
                              "prompts": prompts})
    if pairs == 0:
        out["structural_error"] = "no hay pares de prompts comparables"
    out["prompts_compared"] = pairs
    out["prompts_diverged"] = sum(
        1 for mo in out["models"] for p in mo.get("prompts", [])
        if p.get("first_diff_char") is not None or p.get("missing_in_b") or p.get("error"))
    return out


def verdict(summary):
    if summary.get("structural_error"):
        return 2
    return 1 if summary["prompts_diverged"] else 0


def print_summary(s):
    tag = "match" if s["spec_match"] else "DIFFER - prompts/build distintos, comparar con cuidado"
    print(f"spec: {s['spec_hash'][0]} vs {s['spec_hash'][1]} ({tag})")
    for mo in s["models"]:
        if mo.get("missing_in_b"):
            print(f"{mo.get('name')}: FALTA en b")
            continue
        print(f"{mo.get('name')} [{mo['status'][0]} vs {mo['status'][1]}]:")
        for p in mo.get("prompts", []):
            if p.get("missing_in_b"):
                print(f"  {p['id']}: FALTA en b")
            elif p.get("error"):
                print(f"  {p['id']}: ERROR {p['error']}")
            elif p.get("first_diff_char") is None:
                lp = f" | lp_d max {p['lp_max_d']} mean {p['lp_mean_d']}" if "lp_max_d" in p else ""
                print(f"  {p['id']}: OK ({p['chars'][0]} chars{lp})")
            else:
                fd = p.get("first_diff_token", p["first_diff_char"])
                print(f"  {p['id']}: DIVERGE en ~{fd} ({p['chars'][0]} vs {p['chars'][1]} chars)")
    print(f"prompts: {s['prompts_compared']} comparados, {s['prompts_diverged']} divergentes")
    if s.get("structural_error"):
        print("ERROR estructural:", s["structural_error"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("a")
    p.add_argument("b")
    a = p.parse_args(argv)
    s = compare_golds(load(a.a), load(a.b))
    print_summary(s)
    return verdict(s)


if __name__ == "__main__":
    raise SystemExit(main())
