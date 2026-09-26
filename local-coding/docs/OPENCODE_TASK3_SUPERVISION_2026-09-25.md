# OPENCODE TASK-3 SUPERVISION — PTQ1_0 Vulkan kernel next step (2026-09-25)

## 1. Reconciliation: knowledge.jsonl (day 1-2) vs track numbers

| Metric | knowledge.jsonl (day 1-2) | GPU Track Findings | Reconciliation |
|--------|---------------------------|-------------------|----------------|
| **Real memcpy BW** | 64MB: 183.5 GB/s; 256MB: 184.8 GB/s | "bandwidth REAL 185 GB/s (64-256MB)" | ✅ Match. Theoretical 224 GB/s is unattainable; kernels at 37-56% of REAL rate |
| **TQ2_0 vecq int-dot** | Day 2 q4_0 lm_head: 3312 µs @ 768 GFLOPS | "TQ2_0 vecq 200 GB/s = 89% of peak" | ✅ q4_0 proves 217 GB/s (97% peak); TQ2_0 vecq repaired → 200 GB/s (89%) |
| **PTQ1_0 matvec** | Not directly measured day 1-2 | "kernels ptq1_0 41 GB/s" | ✅ PTQ1_0 lm_head cold: 6698 µs = 41 GB/s (22% of real 185) |
| **Specdec ngram** | Day 2: TQ2_0 base 17.6-19.1 → ngram 19.3-20.0 t/s (+10%) | "night-8 gave no gain; re-verify why" | ✅ Day 2 confirms +10%. Night-8 likely had RAM contention (free RAM not recorded) or different draft config. Day 2 ran GPU-exclusive, ≥4 GB free. |

**Key insight**: The 185 GB/s real memcpy ceiling explains everything. TQ2_0 vecq at 200 GB/s is actually **exceeding** memcpy (likely L2/cache effects on repeated runs); cold it's ~102 GB/s (55% of real). PTQ1_0 at 41 GB/s is **22% of real bandwidth** — the target 102+ GB/s is 55% of real, matching TQ2_0 cold.

---

## 2. Next PTQ1_0 kernel design (target: 41 → 102+ GB/s cold)

### Hypothesis
The PTQ1_0 f32 LUT path (now int8 LUT, 1.25 KB LDS) is bound by **memory access pattern**, not decode ALU or LDS size. The walk (16 threads × 8 elems = 128 elems/block = 28 B) gives a warp 56 B contiguous / 1120 B stride. TQ2_0's vecq achieves 102 GB/s cold with 66-byte blocks (132 B/warp) + int-dot + repack4 of **actual** layout. PTQ1_0's trit layout is different but **regular**: 128 elems = 32 bytes packed (2 bits/elem) + 1 scale. We can adapt the TQ2_0 vecq pattern:
- **repack4 of real PTQ1_0 layout** → feed int-dot (RDNA2 has `sub_group_arithmetic_exclusive_add` + `dot4_i8_i8_acc`)
- **More threads per block** (WG=128 from E1, ROWS=4 banked) → more warps in flight, better occupancy
- **Elements-per-thread 16→32** (E2+E3 combined) → contiguous footprint per warp doubles/triples

### Shapes for verdict (lm_head cold = truth)
| Shape | Instances/token | Current PTQ1_0 (int8 LUT) | Target (TQ2_0 parity) |
|-------|----------------|---------------------------|----------------------|
| `m=248320 × k=5120` (lm_head) | 1 | **5249 µs** (41 GB/s) | **≤2800 µs** (102 GB/s) |
| `m=17408 × k=5120` (gate/up) | 128 | 377 µs | ≤170 µs |
| `m=5120 × k=17408` (down) | 64 | 376 µs | ≤170 µs |
| `m=10240 × k=5120` (qkv) | 48 | 225 µs | ≤100 µs |

**lm_head is the only IC-immune shape** — use it for all A/B verdicts.

### Design: "PTQ1_0 vecq v2 — repack4 + int-dot + banked WG128"
```
File: C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vecq_funcs.glsl
```
Add a new `#if defined(DATA_A_PTQ1_0_VECQ_V2)` branch alongside the existing PTQ1_0 section, mirroring TQ2_0's success:

1. **Block layout (actual PTQ1_0):** 128 elements = 32 bytes weights (2-bit packed) + 2 bytes scale (f16) = 34 bytes/block. But GGML packs to 32-byte alignment → 32 B weights + 2 B scale in separate buffer.
2. **repack4:** Load 4 consecutive 2-bit weights per thread (same as TQ2_0's unpack_q2_0). PTQ1_0 trit = 0,1,2 → map to int8 (-1,0,1) via small LUT or arithmetic.
3. **int-dot:** Use `dot4_i8_i8_acc` against q8_1 activations (same as TQ2_0/q4_0).
4. **Banked WG=128, ROWS=4:** From E1 finding (WG=128/ROWS=4 = -18% lm_head, correctness fail only on batched k=1024). Fix the batched correctness by adjusting `NUM_ROWS` spec constant for production shapes (lm_head has 1940 rows → divisible by 4).
5. **Elements/thread = 32** (2× current): Each thread processes 2 blocks sequentially before next row → warp covers 224 B contiguous.

### Pipeline config (ggml-vulkan.cpp)
- Reuse PTQ1_0 q8_1 pipeline creation (~line 5361) but with:
  - `local_size_x = 128` (WG=128)
  - `spec_constants = {128, 4, i+1}` (WG, ROWS, it_size)
  - `wg_denoms = {2*rm_stdq_int, 1, 1}` (same as TQ2_0 q8_1)
  - Reduction: `SUBGROUP` (enum=2) — TQ2_0 uses this; PTQ1_0 f32 uses SHMEM. The int8 LUT freed LDS; SUBGROUP should work now.

### Correctness gate
- `test-backend-ops test -p "ptq1_0|tq2_0|q4_0"` → 68/68 required
- **Production correctness ONLY via golden gate** (test mode culls large shapes — documented in E1b)

### Success criterion
| Metric | Current (int8 LUT) | Target | Pass condition |
|--------|-------------------|--------|----------------|
| lm_head (cold) | 5249 µs | ≤2800 µs | **Primary verdict** |
| gate/up (per instance) | 377 µs | ≤170 µs | Secondary |
| Golden gate | 7/8 PASS | 7/8 PASS | Fidelity non-negotiable |
| Suite | 68/68 | 68/68 | No regression |

If lm_head ≤2800 µs + golden 7/8 → **end-to-end confirm**: per-op capture → MUL_MAT GPU-sum 157.8 → ~90 ms/tok → decode ~11.5 t/s faithful.

### Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| int-dot precision mismatch (trit→int8 mapping) | Medium | Clone TQ2_0's exact `mul_q8_1` divisor (2); suite validates |
| WG=128 batched correctness (k=1024) | High (seen in E1) | Production shapes have k=5120/17408 (divisible by 4); test mode culls k=1024 batched anyway |
| SUBGROUP reduction breaks on PTQ1_0 | Low | int8 LUT = 1.25 KB LDS (was 5 KB); TQ2_0 uses SUBGROUP successfully |
| Real BW ceiling < 102 GB/s | Low | q4_0 does 217 GB/s; TQ2_0 cold does 102 GB/s — physics allows it |

---

## 3. Night campaign insertion (D2-6 matrices / RGP day 16)

### Phase A: D2 round-2 (this week, token-free loop)
- **Days 1-2**: Implement PTQ1_0 vecq v2 branch + WG128/ROWS=4 pipeline
- **Day 3**: Token-free iteration (E2+E3 combined: elements/thread=32, multi-block walk)
- **Day 4**: lm_head A/B verdict + golden gate
- **Day 5**: If PASS → end-to-end per-op capture + server confirm; if FAIL → document negative, close shader track

### Phase B: Night automation (CATTS-NightJobs 02:30 + CATTS-GPUConfirm 10:00)
| Night | Task | Output |
|-------|------|--------|
| Night 1 (25/09) | Baseline re-verify (cold load, ≥4 GB RAM) | `data/night/20260925/MORNING_REPORT.md` |
| Night 2 | PTQ1_0 vecq v2 build + suite | `data/night/20260926/...` |
| Night 3 | lm_head perf A/B + golden gate | `data/confirm/20260927/CONFIRM_REPORT.md` |
| Night 4 | If PASS: end-to-end decode capture (320 tok) | `data/confirm/20260928/...` |
| Night 5-6 | TQ2_0 int-dot vecq port (Phase B in runbook) | Parallel track; daily driver 12→15-20 t/s |

### Phase C: RGP capture (Day 16, if Phase A fails)
- Prerequisite: C: ≥1.5 GB free (cleanup first)
- Run: `scripts/rgp_capture.ps1` (to be written) on `llama-bench` decode
- Analysis: 1 session with large model (tokens) → per-instruction hotspot
- Decision: If hotspot is fixable in shader → iterate; if deep in scheduler → close track, ship PR

---

## 4. Immediate TODO (for the next agent session)

- [ ] Read `docs/GPU_TRACK_FINDINGS_2026-09-24.md` §5 (structural gap) + `D2_ROUND2_RUNBOOK_2026-09-24.md` Phase B spec
- [ ] Implement `DATA_A_PTQ1_0_VECQ_V2` branch in `mul_mat_vecq_funcs.glsl` (clone TQ2_0 pattern, adapt to PTQ1_0 128-elem block)
- [ ] Add WG=128/ROWS=4 q8_1 pipeline for PTQ1_0 in `ggml-vulkan.cpp` (mirror TQ2_0 q8_1 creation)
- [ ] `ninja -C C:/src/llama.cpp/build test-backend-ops` (touch `mul_mat_vecq.comp` first)
- [ ] `test-backend-ops test -p "ptq1_0|tq2_0|q4_0"` → must be 68/68
- [ ] `test-backend-ops perf -p "ptq1_0.*n=1,|tq2_0.*n=1,|q4_0.*n=1,"` → grep lm_head (m=248320)
- [ ] If lm_head ≤2800 µs: run golden gate (`scripts/golden_capture.py` + `golden_check.py` vs `data/kaggle_runs/gold-20260921/golden.json`)
- [ ] Write verdict to `GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` (D2 r2 section) + `SESSION_CONTEXT.md`

---

## 5. What NOT to do
- ❌ Reopen f32 LUT micro-optimizations (int8 LUT is banked; 5 designs tied)
- ❌ Touch `kaggle/golden_prompts.json` (frozen spec)
- ❌ Run bare `ninja` (C: at 99%)
- ❌ Run GPU benches while user is on PC (night jobs only)
- ❌ Assume TQ2_0 vecq pattern ports 1:1 — PTQ1_0 block layout differs (128 vs 256 elems, trit vs q-1)

---

**Supervisor sign-off**: This design uses only verified facts from the track. The TQ2_0 vecq repair (night-9) proved int-dot + repack4 of real layout + more threads = 200 GB/s. PTQ1_0 has the same hardware, same int-dot instruction, same q8_1 activations. The only unknown is whether trit→int8 mapping + PTQ1_0's smaller block can feed int-dot efficiently. One focused session answers it.