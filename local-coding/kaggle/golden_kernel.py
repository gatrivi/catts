"""Kaggle GPU kernel (script): golden-reference dump of PTQ1_0 on CUDA (T4).

Pushed by scripts/kaggle_bench.py (push --golden), which inlines the candidates
and the frozen prompt spec over the __CANDIDATES__/__PROMPTS__ markers. For each
model: deterministic generations (temperature 0, fixed seed) over the frozen
prompt set, capturing full text plus per-token top logprobs when the endpoint
supports them, and test-backend-ops MUL_MAT output when that binary ships in
the tarball (it self-checks GPU vs CPU, so it is the kernel-level gate; the
generations are the end-to-end gate). Results land in /kaggle/working/golden.json.

Purpose: correctness ground truth for any later HIP/ROCm or Vulkan port of the
packed-ternary kernels. Compare dumps locally with scripts/golden_check.py.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import urllib.request

BASE = "https://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10709-9a9394a"
BUILDS = ["llama-prism-b10709-9a9394a-bin-linux-cuda-12.8-x64.tar.gz",
          "llama-prism-b10709-9a9394a-bin-linux-cuda-12.4-x64.tar.gz"]
PORT = 8080
TMP = "/kaggle/tmp"
OUT = "/kaggle/working"
CANDIDATES = __CANDIDATES__
PROMPTS = __PROMPTS__
TEXT_CAP = 8000         # chars of generated text kept per prompt
OPS_OUTPUT_CAP = 20000  # chars of test-backend-ops stdout kept


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def load_candidates():
    """Solo items marcados golden=true; sin marca, el primero valido (semilla = PTQ1_0)."""
    def pick(items):
        gold = [c for c in items if c.get("repo") and c.get("file") and c.get("golden")]
        if gold:
            return gold
        return [c for c in items if c.get("repo") and c.get("file")][:1]
    if "__CANDIDATES__" not in str(CANDIDATES):
        return pick(CANDIDATES)
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "candidates.json"), "candidates.json"):
        if os.path.isfile(cand):
            with open(cand, encoding="utf-8") as f:
                return pick(json.load(f).get("items", []))
    return []


def get_binary():
    os.makedirs(TMP, exist_ok=True)
    binroot = os.path.join(TMP, "llama-prism")
    os.makedirs(binroot, exist_ok=True)
    for tarname in BUILDS:
        tgz = os.path.join(TMP, tarname)
        print("--- trying", tarname, flush=True)
        if sh(["curl", "-L", "-q", "-o", tgz, f"{BASE}/{tarname}"]).returncode != 0:
            print("download failed:", tarname)
            continue
        with tarfile.open(tgz) as t:
            t.extractall(binroot)
        os.remove(tgz)
        hits = glob.glob(binroot + "/**/llama-server", recursive=True)
        if not hits:
            print("no llama-server in tarball")
            continue
        src = os.path.dirname(hits[0])
        for f in os.listdir(src):
            if os.path.isfile(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), binroot)
        env = dict(os.environ, LD_LIBRARY_PATH=binroot + ":" + os.environ.get("LD_LIBRARY_PATH", ""))
        r = sh([binroot + "/llama-server", "--version"], env=env)
        print((r.stdout.strip() or r.stderr.strip())[:300])
        if r.returncode == 0:
            return binroot + "/llama-server", binroot, env
    # fallback: CUDA runtime wheels provide the missing .so files
    print("installing CUDA runtime wheels and retrying")
    sh(["pip", "install", "-q", "nvidia-cuda-runtime-cu12", "nvidia-cublas-cu12"])
    import importlib.util
    wdirs = []
    for wh in ("nvidia.cuda_runtime", "nvidia.cublas"):
        s = importlib.util.find_spec(wh)
        if s:
            wdirs.append(os.path.join(os.path.dirname(s.origin), "lib"))
    env = dict(os.environ, LD_LIBRARY_PATH=binroot + ":" + ":".join(wdirs))
    for tarname in BUILDS:
        tgz = os.path.join(TMP, tarname)
        if not os.path.isfile(tgz):
            if sh(["curl", "-L", "-q", "-o", tgz, f"{BASE}/{tarname}"]).returncode != 0:
                continue
            with tarfile.open(tgz) as t:
                t.extractall(binroot)
        r = sh([binroot + "/llama-server", "--version"], env=env)
        if r.returncode == 0:
            return binroot + "/llama-server", binroot, env
    raise SystemExit("no usable CUDA build - check the output above")


def wait_health(timeout_s):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as r:
                if r.status == 200:
                    return time.time() - t0
        except Exception:
            pass
        time.sleep(2)
    return None


def chat(body, timeout=1800):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def try_logprobs():
    """True si el endpoint soporta logprobs (probe de 1 token)."""
    body = {"model": "probe", "temperature": 0, "seed": 42, "max_tokens": 1,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": "hi"}],
            "logprobs": True, "top_logprobs": 2}
    try:
        j = chat(body, timeout=300)
        ch = j.get("choices", [{}])[0]
        return bool((ch.get("logprobs") or {}).get("content"))
    except Exception:
        return False


def run_prompt(spec, p, want_logprobs):
    body = {"model": "golden", "temperature": spec["sampling"]["temperature"],
            "seed": spec["sampling"]["seed"], "max_tokens": p["max_tokens"],
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": p["prompt"]}]}
    if want_logprobs:
        body["logprobs"] = True
        body["top_logprobs"] = spec["top_logprobs"]
    j = chat(body)
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


def backend_ops_dump(binroot, env):
    """test-backend-ops MUL_MAT si viene en el tarball (chequea GPU vs CPU solo)."""
    hits = glob.glob(binroot + "/**/test-backend-ops", recursive=True)
    if not hits:
        return {"present": False}
    try:
        r = sh([hits[0], "test", "-o", "MUL_MAT"], env=env, timeout=1800)
    except Exception as e:
        return {"present": True, "error": str(e)[:300]}
    out = ((r.stdout or "") + (r.stderr or ""))[-OPS_OUTPUT_CAP:]
    return {"present": True, "exit": r.returncode, "output_tail": out}


def golden_one(cand, bin_path, env, spec):
    from huggingface_hub import hf_hub_download
    res = {"name": cand.get("name"), "repo": cand.get("repo"), "file": cand.get("file")}
    model = hf_hub_download(cand["repo"], cand["file"], local_dir=os.path.join(TMP, "models"))
    argv = [bin_path, "-m", model, "-ngl", "99", "-c", str(cand.get("ctx", 16384)), "-np", "1",
            "-ctk", cand.get("kv", "q8_0"), "-ctv", cand.get("kv", "q8_0"), "-fa", "on",
            "--host", "127.0.0.1", "--port", str(PORT),
            "-b", str(cand.get("b", 256)), "-ub", str(cand.get("ub", 128))]
    log = open(os.path.join(TMP, "server.log"), "w")
    srv = subprocess.Popen(argv, stdout=log, stderr=log)
    try:
        ready = wait_health(600)
        if srv.poll() is not None or not ready:
            log.flush()
            with open(log.name, encoding="utf-8", errors="replace") as f:
                res.update(status="load_failed", error_tail=f.read()[-400:])
            return res
        res["load_s"] = round(ready, 1)
        want_lp = try_logprobs()
        res["logprobs_mode"] = "top" if want_lp else "text"
        prompts_out = []
        for p in spec["prompts"]:
            try:
                prompts_out.append(run_prompt(spec, p, want_lp))
                print(f"  [{p['id']}] {prompts_out[-1].get('n')} tokens", flush=True)
            except Exception as e:
                prompts_out.append({"id": p["id"], "status": "error", "error": str(e)[:300]})
        res["prompts"] = prompts_out
        res["status"] = "ok" if all(not x.get("status") for x in prompts_out) else "partial"
        print(f"== {cand['name']}: {res['status']}, logprobs={res['logprobs_mode']}", flush=True)
    finally:
        srv.terminate()
        try:
            srv.wait(20)
        except Exception:
            srv.kill()
        log.close()
        time.sleep(2)
    return res


def main():
    print(sh(["nvidia-smi"]).stdout[:600], flush=True)
    bin_path, binroot, env = get_binary()
    ver = sh([bin_path, "--version"], env=env)
    env_info = {"builds_tried": BUILDS,
                "server": (ver.stdout or ver.stderr).strip()[:400]}
    spec = PROMPTS if isinstance(PROMPTS, dict) else {}
    spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
    results, ops = [], None
    for cand in load_candidates():
        print(f"--- golden dump {cand.get('name')} ({cand.get('file')})", flush=True)
        try:
            res = golden_one(cand, bin_path, env, spec)
        except Exception as e:  # un modelo roto no mata el resto
            res = {"name": cand.get("name"), "status": "error", "error": str(e)[:400]}
        if res.get("status") in ("ok", "partial") and ops is None:
            ops = backend_ops_dump(binroot, env)
        results.append(res)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "golden.json"), "w", encoding="utf-8") as f:
        json.dump({"kind": "golden", "spec_hash": spec_hash, "spec": spec,
                   "env": env_info, "backend_ops": ops or {"present": False},
                   "models": results}, f, indent=1)
    print(f"\n=== golden {spec_hash} ===")
    for r in results:
        if r.get("status") == "ok":
            toks = sum(p.get("n") or 0 for p in r.get("prompts", []))
            print(f"{r['name']}: {len(r.get('prompts', []))} prompts, {toks} tokens, logprobs={r.get('logprobs_mode')}")
        else:
            print(f"{r.get('name')}: {r.get('status')}")
    if ops and ops.get("present"):
        print("test-backend-ops exit:", ops.get("exit"))


if __name__ == "__main__":
    main()
