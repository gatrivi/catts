# Discord + web recon: gfx1032 (RX 6600) HIP / ROCm for llama.cpp

Date: 2026-09-22 (evening). Author: research/recon agent (not the implementation agent).
Scope: answer the HIP/ROCm questions for the RX 6600 (Navi 23, gfx1032) and flag anything that
could make Bonsai-2 run better on this rig.

Method: read the live Discord window (server "AMD Developer Community", forum
`rocm-ai-assistant` -> thread `ML`) by capturing the maximized window at full resolution and
OCR/vision-transcribing it, driving Discord's search box with synthetic keystrokes. Web part is
`web_search` snippets only - no page could be fetched in that session, so every web item below
is snippet-level evidence, not verified page content. No repository files were changed by this
recon (this document is the one exception, written afterwards on request).

Relationship to existing docs: `GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` already carries a short
"Discord recon addendum". This document extends it with the actual message bodies, per-query
result counts, and the TheRock CI evidence. It does not contradict that addendum; the
TheRock PR #5719 claim there is now corroborated by two additional messages in the same thread.

## 1. Discord evidence (observed - transcribed from the live window)

### 1.1 ROCm AI Assistant (bot) - `rocm-ai-assistant` > `ML`, "Yesterday" (~2026-09-21)

> Good news: RX 6000 (RDNA2 / gfx1030) is officially supported on Linux in current ROCm (7.2.4),
> so the training + inference pipeline I described earlier will work - with some important caveats
> depending on which specific RX 6000 card you have.
>
> Supported RX 6000 cards (gfx1030 / Navi 21):
> - RX 6800, RX 6800 XT, RX 6900 XT, RX 6950 XT
> - Radeon PRO W6800, PRO V620
>
> These have full official ROCm support on Linux (Ubuntu 22.04/24.04, RHEL 9.x) across ROCm 5.0
> through 7.2.4.
>
> NOT officially supported (lower-tier RDNA2 dies):
> - RX 6700 XT / 6750 XT -> gfx1031 (Navi 22) - not in the support matrix
> - RX 6600 / 6650 XT -> gfx1032 (Navi 23) - not in the support matrix
>
> If you're on one of these unsupported cards, the community workaround is:
> export HSA_OVERRIDE_GFX_VERSION=10.3.0
> This forces the runtime to treat your GPU as gfx1030. It often works but is not officially
> supported and may cause runtime errors with some prebuilt libraries.
>
> Windows: Consumer RX 6000 GPUs are not officially supported by the HIP SDK on Windows. You'd
> need to use WSL2 or a Linux dual-boot for the ROCm path.

Same message, later in the thread (impact paragraph for gfx1030, useful as the ceiling of what
Navi 21 gets - Navi 23 is a smaller die of the same family):

> - FP16 matrix cores - RDNA2 supports FP16 at 2x FP32 rate via dual-issue, but does NOT have the
>   dedicated matrix/tensor cores found on CDNA or RDNA3. This means no MFMA instructions; FP16
>   GEMM throughput will be lower than RDNA3+.
> - No FP8 support - FP8 quantization (AMD Quark) requires gfx950 (MI350) or gfx1200/1201 (RDNA4).
>   On gfx1030, you're limited to FP16/BF16 and INT8.
> - Memory bandwidth - RX 6900 XT has 512 GB/s (16GB GDDR6); RX 6800 has 384 GB/s (16GB).
> - HIP Graphs - fully supported on gfx1030; critical for eliminating kernel launch overhead.
> - torch.compile + Triton - supported; auto-tuning will generate gfx1030-specific kernels.

Reading: this is the strongest statement in the server that (a) gfx1032 is out of the official
matrix, (b) `HSA_OVERRIDE_GFX_VERSION=10.3.0` remains the path, (c) Windows HIP is a
non-starter and WSL2/native Linux is the only ROCm route. Note the wording "may cause runtime
errors with some prebuilt libraries" - that is exactly the rocBLAS/Tensile class of failure
below, and it argues for the self-built `-DAMDGPU_TARGETS=gfx1032` route over prebuilt blobs.

### 1.2 nym - `# rocm-build-install` (locked, ROCm Developer Help), 05/06/2025 12:03

> [rocBLAS] > UserWarning: File in manifest
> [rocBLAS] `E:\rk\build\math-libs\BLAS\rocBLAS\build\Tensile\library\TensileLibrary_lazy_gfx1032.dat`
> [rocBLAS] not found.
> [rocBLAS] Failed to verify all files in manifest
>
> when building with -DTHEROCK_AMDGPU_FAMILIES=gfx103x-dgpu

Reading: concrete, dated evidence of a **missing gfx1032 Tensile kernel artifact in rocBLAS**.
This is the "known-bad combination" the request asked about: rocBLAS ships no gfx1032 code object
in the normal packaging, so a binary linking rocBLAS will either warn-and-fall-back or fail
depending on the code path. hipBLASLt specifically: no gfx1032 report was found (see gaps).

### 1.3 AJO [OSAI] - `# ai-general`, 19/09/2026 01:12

> I couldn't get llama.cpp running rocm at all on wsl2 or Windows directly, maybe thats a whole
> knowledge area claude is lacking in, the best I could do was vulkan at 16tps, compared to 90 out
> of LM Studio direct on the 9700. And I can't sensibly convert my daily world to Linux, I tried
> dual boot for 3 months and the back and forth killed me, so i compromised on windows/wsl mix.

Caveat: the card here is RDNA4-class (RX 9700), **not** Navi 23, so this is not gfx1032 evidence.
It is included because it is a 3-day-old, real-user failure report for exactly our L1/L2 shape
(llama.cpp + ROCm on Windows and on WSL2) and it independently supports "WSL2 is not a free win".

### 1.4 TheRock CI evidence - `# rocm-github`

nunnikri, on TheRock PR #8327 (17-18/09/2026):

> Looking at all the changes, now I am wondering whether we should just package gfx1250 and
> gfx1250-strict separately like gfx1030 and gfx1031/gfx1032.

marbre, on TheRock PR #8281 (17/09/2026 20:33), quoting the math-libs gfx942 stage config:

```
-- Dist targets:
gfx942;gfx1100;gfx1101;gfx1102;gfx1103;gfx1151;gfx1200;gfx1201;gfx1250
-- Test targets:
gfx900;gfx90c;gfx906;gfx908;gfx90a;gfx942;gfx950;gfx1010;gfx1011;gfx1012;gfx1030;gfx1031;gfx1032;gfx1033;gfx1034;gfx1035;gfx1036;gfx1100;gfx1101;gfx1102;gfx1103;gfx1150;gfx1151;gfx1152;gfx1153;gfx1200;gfx1201;gfx1250
-- * Dist bundle:
gfx94X-dcgpu
```

dplyoz, 07/09/2026 21:31, on TheRock PR #5719 ("ci(gfx103x): re-enable Linux nightlies and build
ergonomics"):

> Independent gfx1030 hardware validation (RX 6800 / Linux)
> ... providing independent gfx1030 physical hardware validation on Linux to complement the
> gfx1032 results already shared on this PR.

Reading - this is the most actionable finding of the recon:
1. TheRock (the ROCm packaging/build project, the successor to the pip wheels) **builds and tests
   math-libs for gfx1032 on Linux today** - gfx1032 appears in `-- Test targets` (17/09/2026).
2. It is still **not** in `-- Dist targets`, i.e. it is validated in CI but not necessarily
   shipped in the default dist bundle. So "gfx1032 ROCm libs exist" is true conditionally, and a
   prebuilt consumer must pick the gfx103x-dgpu artifact, not the default one.
3. **TheRock PR #5719 contains real gfx1032 hardware validation results on Linux.** That PR
   thread is the single best next read for "does any of this actually work on gfx1032".

### 1.5 Discord search result counts (tool caveat)

Queries driven into Discord's search box and the counts it displayed:

| Query | Displayed results | Notes |
|---|---|---|
| `gfx1032` | 52 | paginated 3 pages; page 1 read (incl. scroll-backs) |
| `gfx1032 rocblas` | 1 | the nym message above |
| `navi 23` | 1 | the ROCm AI Assistant message above |
| `llama.cpp rocm` | 61 | two cards read (AJO above + an unrelated K2.5 post) |
| `hipblaslt` | 1423 | almost entirely TheRock GitHub bot noise |
| `gfx1032 rocm` | 0 | inconsistent - see caveat |
| `gfx1032 hip` | 0 | |
| `gfx1032 llama` | 0 | |
| `gfx1032 override` | 0 | |
| `gfx1032 fault` | 0 | |
| `gfx1032 prebuilt` | 0 | |
| `gfx1032 hipblaslt` | 0 | |
| `6600 hip` | 0 | |
| `6600 llama.cpp` | 0 | |

CAVEAT, do not over-read the zeros: the multi-term counts are internally inconsistent. The
`gfx1032` search returns the ROCm AI Assistant message, and that message demonstrably contains
both the string "gfx1032" and "ROCm", yet `gfx1032 rocm` returns 0. Either the queries were
scoped differently from one another, or terms were mangled in transit. Treat every 0 above as
"unreliable / not proven absent", not as "no such message exists". The only safe statement is:
no gfx1032 + llama.cpp success report was *found* in the first page of results read.

## 2. Web evidence (search snippets only - NOT page-verified)

Label each of these as candidate until someone opens the page.

1. AMD HIP SDK, "System requirements for Windows" (rocm.docs.amd.com) - snippet: "gfx1032
   [cross]. Prebuilt HIP SDK libraries are not officially supported and might cause runtime
   errors." -> consistent with the bot statement and with L1's FAIL; closes the Windows rung
   harder than our own test alone did.
2. TheRock PR #5719 (via GitHub) - gfx103x-dgpu Linux nightlies re-enabled, gfx1032 "Sanity
   Tested" on Linux (83/87 ctest, the 4 failures a missing RDC artifact, not GPU). Windows stays
   disabled. (Already in the assessment addendum; now corroborated from Discord too.)
3. llama.cpp issue #26996 - "win-rocm-7.14 Windows release missing hipblas.dll": `ggml-hip.dll`
   in `win-rocm-7.14-x64` has an import dependency on `hipblas.dll`; the report mentions the
   build "correctly recognizes gfx1151". -> i.e. the upstream Windows ROCm release is broken by
   packaging *independently of gfx1032*, and its targets are RDNA3.5 iGPU class, not Navi 23.
   This is the same err=126 / missing-dependency failure class as our L1.
4. `lemonade-sdk/llamacpp-rocm` - nightly llama.cpp builds with ROCm 7 acceleration "based on
   TheRock". If TheRock ships gfx1032 math-libs for gfx103x-dgpu, this is the most plausible
   **prebuilt that could skip the build entirely**. Unconfirmed for gfx1032; Phoronix's coverage
   of Lemonade 11.9 mentions gfx1100/gfx1151 targets, not gfx1032.
5. AMD official prebuilts - rocm.docs.amd.com "Llama.cpp pre-built binaries" and
   `repo.radeon.com/rocm/llama.cpp/windows/`. GPU target list not verified; the doc states
   llama.cpp b6652 needs ROCm 7.0.0 on Ubuntu 22.04/24.04.
6. `atomicmilkshake/llama-cpp-turboquant-binaries` (HuggingFace) - "Pre-built Windows x64 Release
   binaries for the atomicmilkshake/llama-cpp-turboquant fork", RDNA2/RDNA3/RDNA4/MI-series
   mentioned in the parent discussion, which also says "The crash happens because the compiled
   binary has no kernel path for that [arch]". Arch coverage unverified.
7. quantized.uk quick start - RDNA2 llama.cpp HIP described as a widely used workaround, "not a
   supported configuration".
8. llama.cpp "Misc. bug: ROCm gfx1031 build report" (Aug 2026) - snippet ends "Please ensure to
   upgrade your drivers. HSA_OVERRIDE_GFX_VERSION is no longer required." Context is gfx1031 and
   the snippet is truncated, so this is a **candidate** at best: it may mean recent ROCm/driver
   builds synthesize the code object without the override. Worth one direct check before we
   assume the override is mandatory on Linux.
9. willitrunai.com - RX 6600: "ROCm support on this card is limited to the HIP Runtime only (not
   the full HIP SDK)".
10. Phoronix, "AMD ROCm 7.1 vs. RADV Vulkan For Llama.cpp" (Nov 2025) and several forum reports -
    Vulkan frequently wins **token generation** on RDNA2, ROCm wins **prompt processing**.

## 3. Direct answers to the four questions

1. **llama.cpp HIP success reports on gfx1032 + ROCm 6.x**: none found. Not in Discord (no message
   in the server matched gfx1032 + llama), and the web hits are community-generic rather than
   gfx1032-specific. Honest status: NOT FOUND, not "does not exist".
2. **Was HSA_OVERRIDE_GFX_VERSION=10.3.0 required, and which ROCm version?** Per the resident
   ROCm bot: yes on gfx1032 (still out of matrix), and it warns that the override remaps the
   device target for prebuilt libraries, which "may cause runtime errors". Key nuance: if
   llama.cpp itself is compiled with `-DAMDGPU_TARGETS=gfx1032`, hipcc emits genuine gfx1032 code
   objects, so the override is primarily needed for **prebuilt math libraries** (rocBLAS et al.),
   not for ggml's own kernels. ROCm version evidence: gfx1030 official through 7.2.4 on Linux
   (bot) and a CachyOS user on ROCm 7.13 (already in the assessment addendum); the "no longer
   required" lead above is unverified.
3. **Known-bad combinations**: (a) rocBLAS/Tensile missing the gfx1032 library artifact -
   observed in Discord, dated 2025-06-05; (b) AMD's own Windows HIP SDK requirements page
   explicitly marks gfx1032 unsupported and warns prebuilt HIP SDK libraries "might cause runtime
   errors"; (c) the generic "compiled binary has no kernel path for that arch" crash reported for
   the turboquant HIP binaries. **Memory faults on Navi 23: NO corroborating report found** -
   `gfx1032 fault` returned nothing and no web hit supported it. Treat as an open question.
4. **Prebuilt gfx1032 llama.cpp HIP binaries**: no confirmed one. Ranked leads: (1) TheRock-based
   Linux nightlies / `lemonade-sdk/llamacpp-rocm` - cheapest free probe, unconfirmed for gfx1032;
   (2) AMD official prebuilts (`repo.radeon.com/rocm/llama.cpp/windows/`, upstream
   `win-rocm-7.14-x64`) - packaging bug #26996 plus RDNA3.5-class targets, so expect nothing for
   Navi 23; (3) turboquant Windows x64 prebuilts - arch coverage unverified.

## 4. What this means for Bonsai-2 on this rig

- The L1 conclusion (Windows HIP = dead end) is now backed by AMD's own support matrix text, not
  just by our err=126 test. Nothing found reopens it.
- L2 keeps its original shape: an external-SSD or WSL2 Linux install with ROCm 7.x and a
  self-built fork targeting gfx1032 (`-DAMDGPU_TARGETS=gfx1032`). The override is a fallback for
  prebuilt libs, not a substitute for building for the right target.
- NEW and cheap: before spending AMD cloud credits, probe a TheRock-based Linux prebuilt
  (lemonade llamacpp-rocm nightly, gfx103x-dgpu artifact). If those carry gfx1032 code objects,
  that is the "skip the build" path - and it also de-risks L3's step 0.
- Expect a rocBLAS warning storm (missing `TensileLibrary_lazy_gfx1032.dat`) on the first Linux
  run; it is a known artifact gap, not necessarily fatal - llama.cpp routes most quantized
  matmuls through its own kernels.
- Do not sell a HIP port as a decode win. Phoronix and multiple community reports put Vulkan
  ahead for token generation on RDNA2. Our own bottleneck is already localised outside the trit
  matmul, so HIP is more plausibly a prefill/quality-path gain than the missing 2x.
- Unchanged free wins already documented elsewhere: adopt the `high` preset (`-c 32768 -ctk q4_0
  -ctv q4_0`, 10.9 t/s at 16K fill), run the Colab F16 -> TQ2_0 requant for the fidelity drift,
  and run `gpu_sweep.py` once with the GPU idle.

## 5. Unverified / gaps

- No page was fetched; every web claim above is snippet-level.
- TheRock PR #5719's gfx1032 validation result body was not read - only the mention of it.
- hipBLASLt behaviour on gfx1032: no data.
- Navi 23 memory faults: no data either way.
- Whether `HSA_OVERRIDE_GFX_VERSION=10.3.0` is still needed on current ROCm/driver Linux builds:
  contradictory signals, needs one direct test.
- Discord multi-term search counts are unreliable (see 1.5), so absence of a report in Discord
  is weakly established.
