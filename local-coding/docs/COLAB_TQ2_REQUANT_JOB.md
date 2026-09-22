# Colab job: requant Bonsai-2 TQ2_0 from F16 (fix the double-quant drift)

Purpose: rebuild `Ternary-Bonsai-2-27B-TQ2_0.gguf` from the author's F16 source instead
of from PTQ1_0, killing the fidelity drift found 2026-09-22 (golden-check 4/8 divergent,
proven weight-side by the CPU control: CPU and Vulkan byte-identical on 7/8, same 4
divergences as the golden — kernel hypothesis dead, see
`docs/GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` addendum).

## Host constraints (why Colab, why these numbers)

- Source `Ternary-Bonsai-2-27B-F16.gguf` = **53.8 GB**; local disks can't hold it
  (C 12.5 / E 4.0 / Z 18.3 GB free). Kaggle working+tmp ≈40 GB is too small → **Colab**.
- Peak disk need: source 53.8 + output **6.9** + second output 6.9 + imatrix ~0.1
  ≈ **67.7 GB** → verify `df -h /content` shows ≥72 GB free before starting the download
  (confirm the instance at run time; the 5.7 GB figure above was PTQ1_0's size at 1.75 bpw
  — TQ2_0 is 2.06 bpw = 6622 MiB, from the logged local run).
  If the instance is short: run the plain requant only (60 GB), or delete nothing and
  do one output per session.
- **No GPU needed for quantize** (streams tensors, CPU-bound; the local PTQ1_0→TQ2_0 run
  took 6 min on 6 cores, and that read only 5.95 GB). Expect ~20–60 min for a 53.8 GB
  source on Colab's 2 vCPU free tier. GPU (T4) only speeds the optional imatrix pass.
- Session cap ~12 h free tier; the whole job is ~2–3 h worst case. Download is the long
  pole (53.8 GB at HF CDN speeds, 15–60 min). Enable resume.

## Steps

1. **Runtime + disk gate.** CPU runtime is enough; check `df -h /content` ≥72 GB free.
2. **Toolchain: use the prism fork binaries, NOT upstream llama.cpp** — TQ2_0/PTQ1_0 are
   fork-only types (verified: `llama-quantize --help` lists `TQ2_0` = type 37, 2.06 bpw
   ternarization, and `PTQ1_0` = 143, 1.75 bpw). Use the **Linux CPU** asset:
   `llama-prism-b10709-9a9394a-bin-ubuntu-x64.tar.gz` (17.1 MB) from
   `https://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10709-9a9394a/`.
   **Verified 2026-09-22** by listing the tarball: it contains `llama-quantize` and
   `llama-imatrix`, CPU-only (`libggml-cpu-*.so`, no CUDA/ROCm/vulkan libs) → runs on a
   plain CPU runtime with no driver risk. No source build needed. (The missing
   `test-backend-ops` in the CUDA asset was a red herring — it isn't needed here.)
3. **Download source** — repo confirmed from the live HF API on 2026-09-22
   (`prism-ml/Ternary-Bonsai-2-27B-gguf`; it also holds PTQ1_0 5.95 GB, PQ2_0 7.21 GB,
   F16 **53.81 GB**, plus the mmproj files):
   `export HF_HOME=/content/hf`  # keep the cache on /content, not the root fs
   `hf download prism-ml/Ternary-Bonsai-2-27B-gguf Ternary-Bonsai-2-27B-F16.gguf --local-dir /content/src`
   (`pip install -q huggingface_hub hf_transfer` first; enable hf_transfer for speed +
   resume; if the repo is gated, export HF_TOKEN).
4. **Plain requant (the hypothesis test — do this first).** The type is a **positional**
   argument and both special tensors must be forced, exactly as the logged local run did:
   `./llama-quantize /content/src/Ternary-Bonsai-2-27B-F16.gguf \
       /content/Bonsai2-TQ2_0-f16src.gguf TQ2_0 \
       --token-embedding-type TQ2_0 --output-tensor-type TQ2_0`
   — source=F16, so **no `--allow-requantize`**. Omitting the two `--*-type TQ2_0`
   overrides lets the default plan promote `token_embd`/`output.weight` to q4_K/q6_K
   (7674 MiB instead of 6622 MiB, measured 2026-09-18) and silently changes the quality
   profile versus the file being replaced. Preflight with the same args plus `--dry-run`
   (no output path) to print the final size before committing to the real pass.
5. **Optional imatrix variant (second output, same session if disk allows):**
   calibration corpus matching the use domain (code+chat, ~1–2 MB text), then
   `llama-imatrix -m <F16> -f corpus.txt -o /content/bonsai2.imatrix --chunk 512`
   (GPU if the runtime has one) and repeat step 4 with `--imatrix /content/bonsai2.imatrix`.
   The author's PQ2_0 was presumably made from F16 with imatrix — this variant is the one
   that matches author methodology.
6. **Smoke check before upload:** gguf metadata shows type TQ2_0 and size ≈6622 MiB
   (2.07 BPW, as written by the local run; ~6.9 GB). A ~7.5 GB file means the `--*-type`
   overrides were dropped in step 4.
7. **Persist outputs immediately** (sessions die). **Recommended: a private HF repo** —
   `hf upload <user>/bonsai2-tq2-f16src /content/Bonsai2-TQ2_0-f16src.gguf`, then pull it on
   the rig with `hf download`. Drive mounting works but the free tier holds only 15 GB and a
   6.9 GB write over the FUSE mount is slow; keep Drive as the fallback. Either way copy as
   soon as the file exists, not at the end of the session.
8. **Local acceptance gate (back on the rig, ~30 min):** drop the new GGUF in
   `data/models/`, golden-capture on Vulkan with `--name bonsai2-ptq10`, then
   `golden_check.py data/kaggle_runs/gold-20260921/golden.json <dump>`.
   **PASS bar: ≤1/8 divergences.** Also spot-check decode ≈12–13 t/s (should be unchanged —
   same kernel path). If both variants exist, gate both and keep the better one; report
   deltas in `MODEL_ROSTER.md` + SESSION_CONTEXT.

## Expected result

If the double-stack was the whole story (all evidence says it is): golden-check passes,
daily driver stays 12–13 t/s **and** becomes golden-faithful. If it still fails >1/8, the
drift is inherent to TQ2_0 vs PTQ1_0 numerics (not stacking) → fall back to PTQ1_0+LUT as
the fidelity config and shift effort to item 3 / upstream PR.

## Risks / notes

- Session death mid-download: `hf_transfer` resumes; rerun the same cell.
- Don't run two outputs if disk is <72 GB — plain requant first, imatrix in a second session.
- Do NOT download PQ2_0 hoping to skip this: no Vulkan kernel (CPU-only ≈ unusable).
- Keep the old TQ2_0 file until the new one passes the gate.
