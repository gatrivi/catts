"""Quick live probes against the :9103 Bonsai-2 server. Usage: python bonsai2_probe_live.py [base_url]"""
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9103"


def chat(payload):
    t = time.monotonic()
    r = httpx.post(f"{BASE}/v1/chat/completions", json=payload, timeout=600)
    r.raise_for_status()
    r = r.json()
    dt = time.monotonic() - t
    u = r.get("usage", {})
    ct = u.get("completion_tokens", 0)
    print(f"  prompt {u.get('prompt_tokens')} tk | decode {ct} tk in {dt:.1f}s "
          f"=> {ct / max(dt, 0.01):.2f} tok/s")
    return r


base = {"model": "bonsai2", "temperature": 0, "max_tokens": 64,
        "chat_template_kwargs": {"enable_thinking": False}}

print("PROBE 1 (decode):")
base["messages"] = [{"role": "user", "content": "Count from 1 to 20, digits only."}]
r = chat(base)
print("  text:", r["choices"][0]["message"]["content"][:120].replace("\n", " "))

print("PROBE 2 (tool call):")
base["max_tokens"] = 256
base["messages"] = [{"role": "user",
                     "content": "Call read_file with path AGENTS.md now. Do not answer in prose."}]
base["tools"] = [{"type": "function", "function": {
    "name": "read_file", "description": "r",
    "parameters": {"type": "object",
                   "properties": {"path": {"type": "string"}},
                   "required": ["path"]}}}]
r = chat(base)
import json
print("  calls:", json.dumps(r["choices"][0]["message"].get("tool_calls") or [])[:400])
print("DONE")
