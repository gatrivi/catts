# Model pick + context overflow: what runs how fast, and why prompts "explode" (2026-09-23)

Rig: Ryzen 5 PRO 4650G, RX 6600 8 GB, 16 GB RAM, Z: HDD. All numbers measured on-rig
(roster 2026-09-07…22). One model at a time: the 8 GB card is exclusive.

## 1. Decision table (decode t/s and usable context)

| Alias (menu #) | Port | Weights (on disk) | Decode t/s | Usable ctx | Startup `-c` | RAM floor | Use for | Avoid for |
|---|---|---|---|---|---|---|---|---|
| `bonsai2` TQ2_0 (#1 + Smol) | 9103/9104 | 6.48 GB | **12–13** (8–9 contended) | 8K; 32K + KV q4 = 10.9 @16K fill | 8192 | 3 GB | smartest local, tools, golden-checked | >8K unless preset `high` |
| `bonsai2` PTQ1_0 | 9103 | 5.54 GB | 6.4–6.7 | 8K (16K viable, ~1 GB more headroom) | — | 3 GB | fidelity-critical (author's quant, IMO-95%) | speed |
| `qwen35` Qwen3.5-9B (#4) | 9102 | 5.29 GB | 21–25 @16K, 30–33 @32K | 32K validated (262K native) | 16384 | 2 GiB | project editing, best coding balance | huge documents |
| `neohorse` 4B Q8 (#3) | 9107 | 4.17 GB | 36–37 short, 29 @31K, 24 @64K, 21 @130K | **32K launcher default since 2026-09-23** (16K could not hold an agent prompt); 131K validated (q4 KV) | 32768 | ~1.5 GB | fast tier + long ctx, router, tools 3/3 | deep reasoning |
| `spark` Spark-X2.5 4B (#2) | 9105 | 4.07 GB | 16–25 @16K | 16K default; 64K/131K presets exist | 16384 | ~1.5 GB | quick chat; long ctx only with a raised preset | prompts >16K as shipped |
| `e4b` Gemma E4B QAT (Smol) | 9104 | 3.93 GB | 41–42 (50.8 w/ MTP smoke) | 32K | 32768 | 2.8 GB | best preliminary coding candidate | long docs |
| `minicpm5` 2B Q8 (Smol) | 9104 | 2.50 GB | 48–60 @32K (~20 deep) | 32K; 131K only with q4 KV | 32768 | 3 GB | long-doc reading | code (3–4/12) |
| `gemma12` 12B-coder Q3 (Smol) | 9104 | 5.67 GB | 18.4 @32K | 32K validated | 32768 | 1.8 GB | prose | tools 0/3 |
| `qwen27` Qwen3.8-27B Q3 (#5) | 9101 | 7.91 GB (roster's "~15 GB" looks stale) | ~7 | 262K native (partial offload) | 4096 | 6 GiB | slow consultant, long ctx | interactive work |
| `nanbeige` 3B Q8 (Smol) | 9104 | 4.13 GB | not re-measured | 16K (32K = 6.7 GB VRAM) | 16384 | 1.5 GB | reasoning experiments | daily driver |
| `coder7` Qwen2.5-Coder-7B (Smol) | 9104 | 4.36 GB | not re-measured | 32K | 32768 | 1.5 GB | code snippets | agentic loops |
| `bonsai` Bonsai 27B Q1 (Smol) | 9104 | 3.54 GB | slow (Q1_0, no fast kernel) | 32K | 32768 | 1.5 GB | legacy/fallback | anything time-sensitive |

Rules of thumb: Bonsai-2 = smart tier, NeoHorse = fast + long ctx, Qwen3.5-9B = editing,
MiniCPM5 = read-only long docs. Full presets live in `scripts/local_models.py` (single source
of truth; change them there, not in the docs).

## 2. "Prompts longer than the context are fine" — that is FALSE, with receipts

Evidence (hub-launched Spark, `data/hub/logs/spark.log`):

```
line 17  E srv send_error: task id=0,  error: request (19947 tokens) exceeds the available context size (16384 tokens), try increasing it
line 22  E srv send_error: task id=3,  error: request (19941 tokens) exceeds the available context size (16384 tokens), ...
line 454 E srv send_error: task id=11901, error: request (70076 tokens) exceeds the available context size (65536 tokens), ...
line 547 E srv send_error: task id=14489, error: request (70591 tokens) exceeds the available context size (65536 tokens), ...
```

Reproduced at both 16K and 64K configs, i.e. it is not an edge case.

Root cause: in llama.cpp's server, **context shift can only evict tokens already cached from
earlier requests**. A single request whose rendered prompt is bigger than `-c` cannot be shifted
into place, so the server answers with an error and the client sees a failed/completed-but-empty
call. `--no-context-shift` (Smol slot) makes the failure louder, it does not create the problem.
What *was* true: the Bonsai-2 summarizer proxy (`:9106`) keeps history under budget — but only for
clients that point at :9106. Nothing else did: Spark :9105, Qwen3.5 :9102, Qwen3.8 :9101,
MiniCPM5 :9104 and direct :9103 all took whatever the client sent.

Second failure mode (silent, worse): when history blew past the proxy budget, the last-resort
truncator kept "as many recent messages as fit" and could drop **the newest user turn entirely**
if that one message was bigger than the budget (a pasted file, a long tool dump). The model then
answered a question it never received — this is the "model explodes / answers nonsense" symptom,
and it produces no error line at all.

## 3. Fix applied (2026-09-23)

- `scripts/bonsai2_proxy.py`: `_hard_truncate()` now **pins the newest user turn**. If that single
  message exceeds the budget it is clipped in place (head + tail + `[...middle dropped by proxy...]`)
  instead of dropped; system message and recent turns still fit around it.
- New generic launcher `CTX_PROXY.cmd <upstream_port> <listen_port> <ctx> [budget] [model]`, e.g.
  `CTX_PROXY.cmd 9105 9109 16384 12000 spark25` — same proxy code, now reusable for any port.
  Point clients (Zed/agents) at the listen port.
- Tests: `tests/test_bonsai2_proxy.py` → 8 passed (3 new: oversized newest turn clipped, system
  kept while oldest turns drop, history ending in assistant still carries the instruction).

## 4. Remaining guidance for long prompts

1. Aim client traffic at a proxy port, never straight at :9103/:9105/:9102, when prompts can be big.
2. Budget must be < `-c` (headroom for system prompt + template + the reply). Bonsai-2 default:
   6000 budget vs 8192 ctx; for Spark 16K try `CTX_PROXY.cmd 9105 9109 16384 12000 spark25`.
3. If a task needs >16K of prompt, use a model whose *server* is started that big (NeoHorse 131K,
   Spark 64K preset, MiniCPM5 131K) instead of trusting shift/compaction.
4. `--no-context-shift` is currently passed for the whole Smol slot but stripped for Bonsai-2
   standalone (`smol_server_args`): keep that in mind when diagnosing "it forgot the beginning".
5. Agents are the worst case, measured 2026-09-23 on omp 18.2.8: a *single empty* prompt rendered
   18.2K prompt tokens (system prompt 19.7 KB + 13 tool schemas 60.3 KB) and the server rejects with
   `request (21411 tokens) exceeds the available context size (16384 tokens)` — 21411 = prompt +
   `max_tokens`, so the prompt budget is `-c` minus max_tokens. Size `-c` for the agent's baseline
   (here 32768) before blaming the model; omp's own estimator reported only ~5K for that payload.

## Actualizacion 2026-09-23 (tarde): MiniCPM5 ya no arranca a 32K por defecto
El camino `catts local` (hub `smol:mini` y `smol.py`) ahora usa el contexto COMPLETO del modelo
(131072, antes 32768) con KV q4_0 (el q8 faulta el driver a ~84K), por lo que la fila de
`minicpm5` de la tabla ("Usable ctx 32K", "Startup -c 32768") describe ya solo el preset `mid`.
omp declara contextWindow 131072 para minicpm5/smol.mini, asi que el baseline del agente
(~18-21K) ya no dispara compaction en el primer turno. Detalle: docs/SESSION_CONTEXT.md.
