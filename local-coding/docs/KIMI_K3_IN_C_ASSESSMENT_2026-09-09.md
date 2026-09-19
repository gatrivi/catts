# Kimi-k3-in-c — assessment for later use (2026-09-09)

Source: https://github.com/FareedKhan-dev/kimi-k3-in-c — Apache-2.0, ~7.3k stars.
Assessment only per user request ("consider for later"). No download, no run, no runtime change.

## What it is
- Kimi K3 (2.78T-param MoE) inference on CPU only: 176 KB portable C99 engine, no BLAS,
  no framework, **no GPU path at all** (OpenMP threads only).
- Checkpoint is 1.56 TB on disk. Experts stored MXFP4 (~0.53 B/weight); matmul reads packed
  nibbles directly, never dequantizes (saves ~194 GB memory traffic per token).
- RAM budget buys only speed, not truncation: byte-identical output 8 GB → 224 GB budget.
  Measured 8.24 GB peak RSS; ~1.45 TB of expert weights stream off disk per token at low budgets.
- Repo benchmarks (strong CPUs, fast disk): 8 GB → 26.5 s/token; 32 GB → 24.2; 64 GB → 19.8;
  128 GB+ → ~5 s/token.

## Fit vs our rig (Ryzen5 PRO 4650G, RX 6600 8GB, 16GB RAM, ~8GB free cap)
- Uses zero GPU → ignores the RX 6600 entirely; opposite of the "smaller model, better GPU use" goal.
- Disk-bound on our RAM: at ~8 GB budget every token reads ~1.45 TB from disk → minutes-to-hours
  per token on consumer NVMe/SATA; our 4650G CPU is below the repo's benchmark machines anyway.
- 1.56 TB download in a custom checkpoint format (not GGUF); will not load in our
  llama.cpp Vulkan runtime. Verified Q8 4B-class candidates remain the right track
  (Spark-X2.5-4B queued plan, Qwen3.5-4B, MiniCPM5-2B).
- Verdict: REJECT for our use. Do not queue a download. Revisit only if a small MoE ships
  MXFP4-only weights AND we have a compatible runtime.

## Ideas worth keeping (no action)
- mmap streaming + packed-MXFP4 direct matmul without dequantization. llama.cpp already covers
  MXFP4 GGUF; relevant only as a technique if we ever verify quant conversions ourselves.
- Zero-tolerance bit-exact tests vs reference: the nibble-order bug class (same multiset of
  values, positions swapped — all distribution stats pass, output wrong) is a good check shape.
- Defensive quant detail: scale byte 0xFF (NaN in MXFP4 spec) zeroes one 32-weight group instead
  of poisoning the whole row with NaN.
