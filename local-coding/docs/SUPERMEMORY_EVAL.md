# supermemory self-host eval (2026-09-19): WORKS OFFLINE-ISH, GOOD FIT, opt-in adoption

## IMPLEMENTED (2026-09-20, stage 2): Bonsai-2 proxy + overnight runner + SMOL flag
All fail-open: memory down = today's behavior exactly.
- **bonsai2_proxy.py (:9106)** — `inject_memory()` prepends a "Persistent local memory"
  system message (query = latest user message, cap = remaining BUDGET tokens, min 150).
  Runs after compression, counts against the 6K budget so the 8K window stays safe.
  Skipped when the marker is already present. Only injects when memory is UP; no auto-start.
- **local_task.py (overnight runner)** — `ask()` prefixes planner/executor/reviewer system
  prompts with `memory_prefix(goal)` (2400 chars, cache-consistent via saved_answer).
  `remember_handoff()` stores a run-outcome fact at completion and on pause (best-effort),
  so future runs recall prior results and rig rules (correct project path, model quirks).
- **smol.py** — optional `--memory` flag (chat/project): appends the memory block to the
  argv system prompt. Default off; existing launches unchanged.
- Tests: test_bonsai2_proxy.py 4, test_local_task_memory.py 3, SmolMemoryTests 2 — all pass.
  Full suite 51 passed + 3 subtests, EXCEPT test_turn_without_model_is_502 which is
  environment-sensitive: it fails whenever a model happens to be live on the smol slot
  :9104 (was live during this session's final run; user-launched, left untouched).
- Live-verified: proxy injection with real memory server (1961-char block), smol
  agent_args(memory=True) injects 2156-char prompt, memory_prefix returns real facts.
- Model-quality win is NOT yet measured: a Bonsai-2 with/without-memory bake-off on real
  tasks is the next step and needs a user-authorized trial slot.

## IMPLEMENTED (2026-09-20): memory wired into the Taller editor
- `scripts/memory_ctx.py` — `--ensure` (auto-start :6767, no-op if up), `--get QUERY`
  (profile+search, deduped, capped, silent empty output if down), `--add TEXT` (needs a
  model slot up for extraction), `--stop`/`--status`. Stdlib only, venv python.
- `MEMORY.cmd` — user control: start / stop (frees ~0.7 GB RAM) / status / save a fact.
- `scripts/local-work.ps1` — after the consultant-note block, retrieves facts for the
  project and appends to `--append-system-prompt` (3000-char cap, "verify against source"
  header). Skipped silently when memory is down; sessions never block on it.
- Gotcha found: without `OPENAI_BASE_URL` configured the server does NOT expose `/health`
  (404) but serves search/profile/console fine — `_health` falls back to `/`.
- Reading is embedding-only (works with no model up); ingestion auto-targets the first
  healthy slot (9107, 9104, 9103, 9105, 9102, 9101).
- Tests: `tests/test_memory_ctx.py` (4); suite 43 passed.
- The 5 seeded rig facts live in container `localstack`; add more via `MEMORY.cmd` or
  `memory_ctx.py --add` (extraction ~1 min/doc with a small model).


Eval task: "quick eval of supermemory to improve use of local models". Hands-on trial
approved (plan mode). Sandbox only; no existing files modified; servers stopped after.

## Setup tested
- Binary `server-v0.0.8` (self-reports Bun 1.3.4) win64, 291 MB, sha256-verified, at
  `vendor/supermemory/supermemory-server.exe`. It is a compiled Bun app, no CLI flags; config is env vars.
- Wired to existing NeoHorse-1-4B Q8 (`scripts/start_neohorse.ps1` args, :9107):
  `OPENAI_BASE_URL=http://127.0.0.1:9107/v1 OPENAI_API_KEY=local OPENAI_MODEL=neohorse
  SUPERMEMORY_DATA_DIR=.../vendor/supermemory/data SUPERMEMORY_DISABLE_TELEMETRY=1`.
- Embeddings: local ONNX `Xenova/bge-base-en-v1.5` 768d, ~17 ms/chunk.
  CAVEAT: weights are NOT fully bundled — first embeddings call auto-downloaded
  `onnx/model_quantized.onnx` from HuggingFace into `data/models`. For true offline use,
  pre-seed that cache or it will phone HF once.
- License banner: "supermemory lite — licensed up to 10k documents" (enforced). Encrypted
  local storage, single auto key, auto-applied for unauthenticated localhost.

## Results (rig: RX6600 8GB, 16GB RAM, HDD)
- Boot 4.4-6 s. RAM: supermemory ~729 MB + NeoHorse llama-server 4.77 GB (fits the 8 GB cap).
- Ingest `POST /v3/documents`: 0.06-0.68 s accept (async pipeline), 5 docs done in ~6.5 min
  — extraction runs a memory-agent LLM loop per doc (~1.3 min/doc on the 4B @ 35 t/s).
  Cost is per-ingest, not per-query. A bigger model would not be much faster (token-bound).
- Search `POST /v4/search`: 40-80 ms, local only. Relevance 4/4 correct, clean atomic
  facts distilled from prose, similarity 0.65-0.77.
- `POST /v4/profile` (note: `containerTag` singular): returns dated fact list ready to
  paste as system-prompt context. This is the killer feature for the local stack.
- Persistence PASS: kill + restart with same data dir -> same key, same memory IDs,
  search intact.

## Verdict
Adopt as opt-in memory layer. The 4B handled extraction and tool-free distillation fine;
search/latency/RAM all fit the rig. Best integration (cheapest first):
1. `scripts/local-work.ps1` — fetch `/v4/profile` and append to the existing
   `--append-system-prompt` (pattern already there, line ~42).
2. `mcp_local_agents/server.py` — a `local_memory` tool wrapping add/search.
3. `bonsai2_proxy.py` — auto-prepend profile for any client on :9106 (most invasive).

## Risks
- Pre-1.0 lite binary; v0.0.7->0.0.8 had a data-loss migration upstream. Snapshot
  `vendor/supermemory/data` before any version change; pin this binary.
- 10k-doc cap (irrelevant at our scale, but enforced at API level).
- First-run HF download (see above) breaks pure-offline claims.
- Ingest is slow on small models; batch memories, don't stream per-message.

## Layout
- `vendor/supermemory/supermemory-server.exe` — pinned binary
- `vendor/supermemory/data/` — encrypted store + ONNX cache
- `vendor/supermemory/eval-logs/` — llama-9107.log, supermemory.log, supermemory-restart.log
