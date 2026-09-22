"""Captura un golden dump local contra un llama-server VIVO (Vulkan/HIP/CUDA).

Complemento local de kaggle/golden_kernel.py: mismo spec congelado
(kaggle/golden_prompts.json) y mismo formato de salida, para comparar contra la
referencia CUDA de Kaggle con scripts/golden_check.py. No gestiona servidores
(regla un-modelo-a-la-vez): arranca el tuyo y apuntalo con --url.

Uso:
  python scripts/golden_capture.py --url http://127.0.0.1:9103 \
      --name bonsai2-ptq10-hip --note "prism b10687 hip + HSA_OVERRIDE" \
      [--out data/golden/mi-dump.json]
"""
import argparse
import datetime
import hashlib
import json
import time
import urllib.request
from pathlib import Path

try:
    import scripts.local_models as lm
except ImportError:
    import local_models as lm

PROMPTS_FILE = lm.ROOT / "kaggle" / "golden_prompts.json"
TEXT_CAP = 8000


def chat(url, body, timeout=1800):
    req = urllib.request.Request(f"{url}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def try_logprobs(url):
    body = {"model": "probe", "temperature": 0, "seed": 42, "max_tokens": 1,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": "hi"}],
            "logprobs": True, "top_logprobs": 2}
    try:
        ch = chat(url, body, timeout=300).get("choices", [{}])[0]
        return bool((ch.get("logprobs") or {}).get("content"))
    except Exception:
        return False


def run_prompt(url, spec, p, want_logprobs):
    body = {"model": "golden", "temperature": spec["sampling"]["temperature"],
            "seed": spec["sampling"]["seed"], "max_tokens": p["max_tokens"],
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": p["prompt"]}]}
    if want_logprobs:
        body["logprobs"] = True
        body["top_logprobs"] = spec["top_logprobs"]
    j = chat(url, body)
    ch = j.get("choices", [{}])[0]
    text = (ch.get("message") or {}).get("content") or ""
    entry = {"id": p["id"], "text": text[:TEXT_CAP],
             "n": (j.get("usage") or {}).get("completion_tokens"),
             "finish": ch.get("finish_reason"),
             "tg_tps": (j.get("timings") or {}).get("predicted_per_second")}
    lps = (ch.get("logprobs") or {}).get("content") or []
    if want_logprobs and lps:
        toks = []
        for i, e in enumerate(lps):
            t = {"t": e.get("token"), "lp": round(float(e.get("logprob", 0.0)), 4)}
            if i < spec["detail_tokens"]:
                t["top"] = [[a.get("token"), round(float(a.get("logprob", 0.0)), 4)]
                            for a in (e.get("top_logprobs") or [])]
            toks.append(t)
        entry["tokens"] = toks
    return entry


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", required=True, help="base URL del server, ej http://127.0.0.1:9103")
    p.add_argument("--name", required=True, help="etiqueta del dump, ej bonsai2-ptq10-hip")
    p.add_argument("--note", default="", help="build/backend/flags para el registro")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)
    spec = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
    want_lp = try_logprobs(a.url)
    print(f"logprobs: {'top' if want_lp else 'text-only'} | spec {spec_hash}")
    prompts_out = []
    for pr in spec["prompts"]:
        t0 = time.time()
        try:
            e = run_prompt(a.url, spec, pr, want_lp)
            prompts_out.append(e)
            print(f"  [{pr['id']}] {e.get('n')} tokens, {time.time() - t0:.0f}s")
        except Exception as ex:
            prompts_out.append({"id": pr["id"], "status": "error", "error": str(ex)[:300]})
            print(f"  [{pr['id']}] ERROR {str(ex)[:120]}")
    status = "ok" if all(not x.get("status") for x in prompts_out) else "partial"
    out = {"kind": "golden", "spec_hash": spec_hash, "spec": spec,
           "env": {"note": a.note, "url": a.url,
                   "captured": datetime.datetime.now().isoformat(timespec="seconds")},
           "models": [{"name": a.name, "repo": None, "file": None, "status": status,
                       "logprobs_mode": "top" if want_lp else "text",
                       "prompts": prompts_out}]}
    path = Path(a.out) if a.out else lm.ROOT / "data" / "golden" / f"{a.name}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{status} -> {path}")
    print("comparar: python scripts/golden_check.py <golden_kaggle.json> " + str(path))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
