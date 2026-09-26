# Tweet thread draft — 4 tweets (ready to post, 2026-09-25)

**1/4**
We run Bonsai-2-27B (ternary, 2.06 bpw, 6.48 GB) on an RX 6600 (RDNA2, 224 GB/s) via llama.cpp Vulkan. Stock path: 12–13 tok/s = 38% of memory bandwidth. After porting the missing int-dot MMVQ path + an int8 lookup-table fix (LDS 5KB→1.25KB): 53 ms/token GPU-time, 20.5 tok/s = 55% of peak. Measured with per-op timestamp queries on the live server, ±1% variance across runs. All local, all open tooling.

**2/4**
The biggest lesson cost us weeks: cache-warm benchmarks LIE. With the working set inside RDNA2's 32MB Infinity Cache, every kernel variant we tried tied at the same issue-limited plateau — real differences only appear cold. Per-op timestamp captures on the live server (GGML_VK_PERF_LOGGER) are the only oracle. Worse: we found a quant type whose vecq file had NEVER compiled — llama.cpp silently fell back to a slower path and every benchmark "confirmed" it.

**3/4**
Ground truth on this card: memory copies run 185 GB/s real (64–256 MB working sets), 445–644 GB/s when Infinity-Cache-resident. Our ternary decode now streams at 169–193 GB/s on production shapes — at copy rate. A single q4_0 matvec hits 217 GB/s cold (97% of peak). The silicon streams fine; the gap is in how the 2-bit decode consumes it.

**4/4**
RDNA2/Vulkan kernel people: an RTX 3060 reportedly does ~46 tok/s on this same model (83% of its bandwidth) on CUDA. We're at 55%. Measured-and-ruled-out: load redundancy, LUT size, workgroup width, activation path. Suspects left: 2-bit field extraction cost, wave scheduling, barrier patterns, per-instance dispatch. Fork + full measurement set public — where's the last 30% hiding?

---

Posting notes:
- Add the fork/measurements links in 4/4 before posting (the C:/src baseline is committed; push when ready).
- The 46 tok/s 3060 figure is stated as "reportedly" — be ready for "source?" as the first reply; that's the point of posting.
- Suggested hashtags: #AMD #RDNA2 #llama.cpp #LocalLLM
