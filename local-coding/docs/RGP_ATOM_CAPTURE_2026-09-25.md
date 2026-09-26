# RGP ATOM-LEVEL CAPTURE — WORKING (2026-09-25 21:00)

The item that was blocked in `HANDOFF_2026-09-25.md` §7.3 ("RGP profiling-init
debug") is **solved and automated**. No GUI, no manual step, ~2 min for all four
captures.

## 1. What was actually wrong

Not a driver-version or service problem. Two facts:

1. `RadeonDeveloperPanelCLI.exe` **fails to initialize the capture API** unless
   `--remote-host 127.0.0.1` is passed explicitly. With the default host it dies
   with `Failed to initialize capture context` / `Capture API initialized
   successfully` never printed. With the flag: capture API comes up, sees both
   GPUs, driver 26.6.2 on the RX 6600, pins clocks to peak, traces.
2. Dispatches **1 and 2 are buffer transfers**. RGP compute tracing on them fails
   with `Profiling (RGP) trace failed with result: -2`. The matmul compute
   dispatch is **#3**, stably, for every shape and every quant type tested
   (6144x5120 and 248320x5120, tq2_0 and q4_0). Sweep 3,4 is enough; 1,2 are
   dead weight.

## 2. Tooling (all local, no cloud)

- `scripts/rgp_capture.ps1` — guarded headless harness. Starts
  `RadeonDeveloperService` if absent (UDP 27300, ~33 MB), starts the CLI with
  auto-capture, runs a **single-shape** `test-backend-ops perf` workload, waits
  for the trace, cleans up only its own PIDs. Guards: lock file, RAM floor
  (5000 MB), CPU-busy ceiling (55%), GPU-already-busy, port squatter. Every guard
  *skips*, never fails the night.
- `scripts/rgp_isa_notes.py` — headless reader. RGP embeds the captured shader as
  AMDGPU ELF64 (machine 224) objects; the script reports **ISA code bytes** and
  can extract the shader to a standalone `.elf` (`--extract`) for RGA or any
  gfx1032 disassembler.
- `night_campaign.ps1` → `RGP` slice — the old no-op stub is replaced. 4 captures
  in ~2 min, each recorded as knowledge cells.

## 3. Results (measured 2026-09-25, RX 6600, driver 26.6.2, C:/src build)

| Capture | Shape | Type | Mode | Size | ISA code bytes |
|---|---|---|---|---|---|
| `rgp_tiny-tq2_0` | 6144x1x5120 | tq2_0 | trace+counters | 454 KB | **11788** |
| `rgp_tiny-q4_0` | 6144x1x5120 | q4_0 | trace+counters | 600 KB | **6872** |
| `rgp_lmhead-tq2_0` | 248320x1x5120 | tq2_0 | plain SQTT | 1878 KB | 11788 |
| `rgp_lmhead-q4_0` | 248320x1x5120 | q4_0 | plain SQTT | 3754 KB | 6872 |

Findings:

- **The TQ2_0 kernel is 1.71x the code size of the q4_0 kernel** (11788 vs 6872
  bytes of ISA). The vecq port that won −35% bought its speed with ~4.9 KB more
  instructions per invocation.
- **Kernel code is shape-independent** — identical byte counts at 6144 and
  248320 rows. So the tiny capture is a faithful stand-in for lm_head; only the
  dispatch *timing* differs, and that comes from the plain lm_head captures.
- **Trace mode does not fit at lm_head.** The q4_0 lm_head trace wants 20.7 MB of
  dispatch data and the workload runs dry at 77% → `-2`. Hence the split matrix:
  trace+counters on the tiny shape, plain SQTT at production shape. A future
  longer-lived workload (e.g. a server with a real prompt) could carry the
  lm_head trace too.

## 4. What still needs a human (once, ~10 min)

Counters and timings (SQ occupancy, effective BW %, stall reasons) live in the
trace's binary sections and only decode in the GUI. To read the headline pair:

1. `C:\tools\rdts\RadeonDeveloperToolSuite-2026-05-28-1806\RadeonGPUProfiler.exe`
2. Open `data\profile\rgp\rgp_tiny-tq2_0_*.rgp` and `rgp_tiny-q4_0_*.rgp`
   (and the two `lmhead-*` for the production-shape dispatch).
3. Compare: SQ_WAVE occupancy, VALU vs memory instruction mix, effective
   bandwidth per dispatch, against the campaign ground truth (185 GB/s copy,
   224 GB/s peak, 29 ms/tok floor at 100% BW).

For pure instruction listing without the GUI, open the extracted
`*.shader1.elf` in RGA or a gfx1032 disassembler.

## 5. Do not re-derive

- `--rgp-sqtt-buffer-size maximum` is **rejected** on this driver
  ("Failed to enable Profiling (RGP) feature"). Leave it at default.
- The workload must be `test-backend-ops perf` with a **single** shape
  (`type_a=<qtype>.*m=...,n=1,k=...`). Note the param name is `type_a=`, not
  `type=` — a `type=` filter silently matches zero cases and the process exits
  immediately, which looks like a capture failure.
- `perf` mode allocates on the GPU only: ~1 core, host RAM stays flat, so these
  captures are safe to run while the machine is in use (the guards enforce it).
- Filters that work: `type_a=tq2_0.*m=6144,n=1,k=5120` (tiny),
  `type_a=tq2_0.*m=248320,n=1,k=5120` (lm_head).
