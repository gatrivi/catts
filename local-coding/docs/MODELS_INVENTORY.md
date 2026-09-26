# Local models: what we have, how fast, how much context, SWE evidence (2026-09-18)

Measured on this rig (Ryzen 5 PRO 4650G, RX 6600 8 GB, 16 GB RAM) unless marked otherwise.
"SWE" = SWE-bench Verified by default; author/3rd-party numbers are NOT local measurements.

| Model | File | Native ctx | Notes on ctx | Decode (measured here) | SWE evidence |
|---|---|---|---|---|---|
| NeoHorse-1-4B Q8 | 4.17 GB | 262144 | 32768 launcher default since 2026-09-23 (16K refused agent prompts) | **36 tok/s** (26.8 ms/token); prefill 18-192 | no SWE published; agentic +6..+10 vs Qwen base |
| Qwen3.5-9B Q4_K_M | 5.29 GB | 262144 | 32K validated | 30-33 tok/s | 50.8 (author/3rd-party table) |
| Qwen2.5-Coder-7B Q4_K_M | 4.36 GB | 32768 | 32K fits | 33-48 tok/s | unknown |
| MiniCPM5-2B Q8 | 2.50 GB | 131072 | 32K validated | 48-60 tok/s | 46.4 Verified (3rd-party); local gate 3-4/12 |
| MiniCPM5-2B Q4_K_M | 1.45 GB | 131072 | 32K validated (own launcher) | 65 tok/s (16K, rig 2026-09-18) | 46.4 Verified (3rd-party review) |
| Gemma-4-E4B QAT Q4_K_XL | 3.93 GB | - | 32K loads | 41-42 tok/s | n/a |
| Nanbeige4.2-3B Q8 | 4.13 GB | 262144 | 16K default (32K = 6.7 GB VRAM) | not measured (VRAM blocked 2026-09-18) | 63.6 Verified / 46.9 Pro (author) |
| Gemma-4-12B coder Q3_K_M | 5.67 GB | 262144 | 32K tight (6.3 GB) | 18-18.5 tok/s | n/a: tools 0/3 |
| Bonsai-27B Q1_0 | 3.54 GB | 262144 | - | 16.7 tok/s | n/a: 7/12 on the local checkout suite |
| Bonsai-2 27B PTQ1_0 | 5.54 GB | 262144 | 8K + q8 KV | **3.3 tok/s** (Prism fork only, kernel-limited) | n/a: 2/2 tool probes pass |
| Bonsai-2 27B TQ2_0 (converted) | 6.48 GB | 262144 | 8K + q4 KV planned | not measured (A/B paused) | untested |
| Granite-4.2-8B Q4_K_M | 4.98 GB | - | - | not measured | unknown |
| Spark-X2.5-4B Q8 | 4.07 GB | 1048576 | 16K probed (b10964 loads it) | 40 tok/s (16K, rig 2026-09-18) | SWE Pro 44.4 / Verified 41.6 (author) |
| Qwen3.5-4B Q8 | 4.30 GB | 262144 | 16K trialed | 27-32 tok/s (project trial) | 38.8 base / 43.0 Leaf harness (report) |
| Qwen3.8-27B Q3-DOWN-XS | 7.91 GB | 262144 | partial offload | 6.8-7.5 tok/s | LiveCodeBench v6 76.6 (author) |
| Qwen3.8-27B IQ2_XS-MTP | 8.17 GB | 262144 | partial offload | 1.42 tok/s (measured, poor) | unknown |
| Qwen3.8-27B UD-IQ4_XS | 13.27 GB | 262144 | does not fit 8 GB | n/a | unknown |

Rule of thumb: <=5.5 GB fits 8 GB VRAM with a usable KV cache; 6.5-8 GB runs only partially
offloaded (slow); >9 GB does not fit.

## Launchers (non-technical entry points)
- Desktop **"Smol local"** -> `SMOL.cmd` -> `scripts/smol.py` (menu of installed models, chat or project).
- Desktop **"Taller local"** -> `TALLER.cmd` (older launcher/project workspace).
- `BONSAI2.cmd` (Bonsai-2 self-try), `MINICPM5-CODING.cmd` (MiniCPM5 131K server), `E4B.cmd`, `WANGP.cmd`.
- 2026-09-18: `smol.py` had a syntax break (indentation in agent_args) - repaired; `--check` passes for
  all 8 registered models and the 35 host tests pass. NeoHorse-1-4B added to the Smol menu as `neo`
  (36 tok/s, native tool call) - currently the best small local agent we have.