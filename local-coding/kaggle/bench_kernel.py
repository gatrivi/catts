"""Kaggle GPU kernel (script): benchmark candidate GGUFs on T4 before downloading them locally.

Pushed by scripts/kaggle_bench.py, which injects the candidate list over the
__CANDIDATES__ marker below. Run standalone it falls back to kaggle/candidates.json.
Needs GPU + internet enabled in kernel-metadata.json. Results land in
/kaggle/working/results.json (kernel output) with the same probes as the local
sweep (decode, prompt-processing, tool call, code sanity) for apples-to-apples.
"""
import glob
import json
import os
import shutil
import subprocess
import tarfile
import time

BASE = "https://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10709-9a9394a"
BUILDS = ["llama-prism-b10709-9a9394a-bin-linux-cuda-12.8-x64.tar.gz",
          "llama-prism-b10709-9a9394a-bin-linux-cuda-12.4-x64.tar.gz"]
PORT = 8080
TMP = "/kaggle/tmp"
OUT = "/kaggle/working"
CANDIDATES = __CANDIDATES__


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def load_candidates():
    if "__CANDIDATES__" not in str(CANDIDATES):
        return CANDIDATES
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "candidates.json"), "candidates.json"):
        if os.path.isfile(cand):
            with open(cand, encoding="utf-8") as f:
                return json.load(f).get("items", [])
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
            return binroot + "/llama-server", env
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
            return binroot + "/llama-server", env
    raise SystemExit("no usable CUDA build - check the output above")


def wait_health(timeout_s):
    import urllib.request
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


def chat(body, timeout=900):
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    tm = j.get("timings") or {}
    return {"pp_n": tm.get("prompt_n"), "pp_tps": tm.get("prompt_per_second"),
            "tg_n": tm.get("predicted_n"), "tg_tps": tm.get("predicted_per_second")}


def payload(prompt, max_tokens):
    return {"model": "bench", "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": prompt}]}


def pp_prompt(blocks=220):
    body = "".join(f"function f{i}(a){{return a + {i};}}\n" for i in range(blocks))
    return "```js\n" + body + "```\nSummarize what this code does in one short sentence."


def bench_one(cand, bin_path, env):
    from huggingface_hub import hf_hub_download
    res = {"name": cand.get("name"), "repo": cand.get("repo"), "file": cand.get("file")}
    t0 = time.time()
    model = hf_hub_download(cand["repo"], cand["file"], local_dir=os.path.join(TMP, "models"))
    res["download_s"] = round(time.time() - t0, 1)
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
                res["status"] = "load_failed"
                res["error_tail"] = f.read()[-400:]
            return res
        res["load_s"] = round(ready, 1)
        res["decode"] = chat(payload("Count from 1 to 300, digits only, comma separated, one line.", 640))
        res["pp"] = chat(payload(pp_prompt(), 48))
        tool = payload('Call read_file with path AGENTS.md now. Do not answer in prose.', 256)
        tool["tools"] = [{"type": "function", "function": {"name": "read_file", "description": "r",
                          "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                                         "required": ["path"]}}}]
        res["toolcall"] = chat(tool)
        res["code"] = chat(payload("Write a JavaScript function toCents(value) that converts a non-negative "
                                   "number of dollars to integer cents and throws on invalid input. Code only.", 192))
        res["status"] = "ok"
        print(f"== {cand['name']}: tg {res['decode']['tg_tps']:.1f} t/s | pp {res['pp']['pp_tps']:.1f} t/s", flush=True)
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
    bin_path, env = get_binary()
    results = []
    for cand in load_candidates():
        if not cand.get("repo") or not cand.get("file"):
            print("skip (repo/file vacio):", cand.get("name"), flush=True)
            continue
        print(f"--- benchmarking {cand['name']} ({cand['file']})", flush=True)
        try:
            results.append(bench_one(cand, bin_path, env))
        except Exception as e:  # un candidato roto no mata el resto
            results.append({"name": cand.get("name"), "status": "error", "error": str(e)[:400]})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("\n=== resumen ===")
    for r in results:
        if r.get("status") == "ok":
            print(f"{r['name']}: tg {r['decode']['tg_tps']:.1f} t/s | pp {r['pp']['pp_tps']:.1f} t/s | load {r['load_s']}s")
        else:
            print(f"{r['name']}: {r.get('status')}")


if __name__ == "__main__":
    main()
