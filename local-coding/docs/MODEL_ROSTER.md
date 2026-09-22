# Local model roster (rig: Ryzen 5 PRO 4650G, RX 6600 8 GB, 16 GB RAM, Z: HDD)

Measured on-rig unless noted. "RAM need" = free system RAM floor at launch
(weights mmap from HDD; full GPU offload assumed). One model at a time on the
8 GB card. Sources: SESSION_CONTEXT.md entries 2026-09-07…19, launcher scripts.

| Model (alias) | Port | Size on disk / resident | Decode t/s | Usable ctx | KV / notes | RAM floor | Tools | Role |
|---|---|---|---|---|---|---|---|---|
| Bonsai-2 27B TQ2_0 (bonsai2) | 9103 | 6.48 GiB / ~5.0 GB | 12–13 (8–9 contended) | 8K (100K = 3.2 t/s, skip; 32K via q4_0 KV = 10.9 t/s @16k fill, pp 70 t/s) | q8 KV, ngl 99, --reasoning-effort medium (xhigh template default = empty answers @4k, see BONSAI2_REASONING_EFFORT.md); json_object truncates | 3 GB | yes | smartest local; golden-check vs CUDA T4 CERRADO 2026-09-22: 4/8 prompts divergen (siempre al token rank-2/3 del golden, texto aun correcto) = fidelity gap, no corrupcion |
| Bonsai-2 27B PTQ1_0 | 9103 | ~5.9 GB | 6.4–6.7 (was 3.3) | 8K, 16K+ viable (~1 GB less VRAM than TQ2) | matvec fixed 9/22 (601→247us LUT kernel, golden-verified 7/8 vs CUDA T4); ceiling outside matmul; fix lives in C:/src build, NOT in shipped b10685 runtime | 3 GB | yes | upstream-PR ready; TQ2_0 still 2x faster |
| NeoHorse-1 4B Q8 (neohorse) | 9107 | ~4.5 GB | 36–37 short; 29 @31K, 24 @64K, 21 @130K | 16K default; 32K/64K/131K VALIDATED 2026-09-20 (needle PASS at all rungs; 131K needs q4 KV) | prefill ~300 t/s @31K, 166 @64K, 91 @130K → first token 2 min / 6.5 min / 24 min | ~1.5 GB | yes 3/3 | fast tier; long-ctx champ; router candidate |
| Spark 4B (spark) | 9105 | ~2.6 GB | 16 (21–25 @16K in trial) | 32K | SWA hybrid keeps KV small; 1M native untested | ~1.5 GB | partial | fast tier, long-ctx option |
| MiniCPM5-2B Q8 (minicpm5) | 9104 | 2.5 GB / ~3.0 GiB @32K | 48–60 @32K; ~20 deep | 32K validated; 65K ~50 min prefill; 131K q8 KV FAULTED driver @84K, q4 KV stable but ~2 h prefill | long-doc use via MINICPM5-CODE-131K.cmd (q4 KV + proxy :9108 + supermemory) | 3 GB | yes 4/4 | long-doc reader; NOT for code (3–4/12 tests) |
| Qwen3.5-9B (taller) | 9102 | ~5.4 GiB @32K | 21–25 @16K; 30–33 @32K | 16K default, 32K validated (262K native) | no-mmap + cache-reuse | 2 GiB | yes | project editor; best coding balance |
| Qwen3.5-27B consultant (qwen27) | 9101 | ~15 GB Q? | ~7 | 262K | partial offload (CPU assist) | 6 GiB | yes | slow consultant, long ctx |
| Gemma-3n E4B (E4B) | — | ~4.4 GB | 41–42 (50.8 w/ MTP, one smoke) | 32K | RAM floor 2.8 GB (host embeddings 1.9 GB) | 2.8 GB | yes 3/3 | best preliminary coding candidate |
| Gemma-3 12B Q3 (Google, Mar 2025) | — | ~6.7 GB @32K | 18.4 | 32K validated; 262K native-UNTESTED (VRAM-infeasible on 8 GB) | tools 0/3 (prose) | 1.8 GB | no | chat only |

Rules of thumb: 100K+ ctx on Bonsai-2 pushes weights to CPU — never; NeoHorse is the
validated long-ctx model (131K w/ q4 KV); MiniCPM 131K is stability-validated on q4 KV
only (q8 device-faults) and prefill-bound; free-RAM assumption cap ~8 GB (user directive).
2026-09-20 probe: tmp/ctx_eval.py, needle-recall + server timings, thinking on for answers.
