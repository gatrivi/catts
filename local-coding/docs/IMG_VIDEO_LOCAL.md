# Image + video local (RX6600 8GB)

State 2026-09-13: venv rebuilt (TheRock torch 2.13 gfx103X + deps, Z:),
weights still missing. BLOCKED: ROCm staging crashes on this box (see below).

## What exists

- `Z:/AI/WanGP/Wan2GP` = Wan2GP app (Gradio UI, image + video, low-VRAM
  profiles incl. `wan_1.3B`, flux, ltx/qwen/z_image slots). Sources untouched.
- `Z:/AI/WanGP/venv` = rebuilt 2026-09-13 (`rocm-sdk init` done, reqs
  installed). `wangp_local.py --launch` now puts the ROCm bins on PATH.
- No weights anywhere (all model slots ~0 GB). Outputs/queues dirs empty.
- AMD path: RX6600 = gfx103X (RDNA2) via TheRock **staging** wheels;
  upstream ships no RDNA2 profile (only 110X/1151/1201), MIOpen is
  unstable -> `MIOPEN_FIND_MODE=FAST`. Expect experimental.

## Blocker 2026-09-13: ROCm stack segfaults (driver-level)

- `hipInfo.exe` dies with 0xC0000005; `import torch` fails because
  `MIOpen.dll` won't load (its static imports all resolve — DllMain/in init
  crashes). SDK self-tests pass except console-script probes.
- Adrenalin on the RX6600 is 32.0.21043 (18/06/2026) — current, so this is
  TheRock-staging immaturity for gfx103X, not an old driver.
- Next steps, in order: (a) retry after a newer Adrenalin/TheRock nightly;
  (b) image-only fallback via stable-diffusion.cpp Vulkan (no torch);
  (c) ZLUDA/CUDA-shim experiment. None authorized yet.

## LIVE 2026-09-14: image works (SDXL-Turbo, Vulkan, RX6600)

- Runtime `Z:/Models/runtime/sd-vulkan` (master-866, sha256 verified).
- Model `Z:/Models/images/sd_xl_turbo_1.0_fp16.safetensors` (6.9 GB).
- Smoke PASS: 512px red cat, 4 steps, cfg 1.5, seed 42, ~6 min wall
  (`Z:/AI/outputs/images/smoke-turbocat.png`). Output verified visually.
- Working shape (note: `--steps`, not `--sampling-steps`):
  `sd-cli.exe -m <model> -p "<prompt>" -o <out.png> -W 512 -H 512
  --steps 4 --cfg-scale 1.5 --backend "diffusion=vulkan0,clip=vulkan0,vae=vulkan0"`
- Video still blocked (ROCm, see below). Image needs no torch at all.

## Runbook

Politica: todo lo pesado en Z:. Nada en C:.

1. `WANGP.cmd --check` (or `npm run wangp:check`): state, no changes.
2. `python scripts/wangp_local.py --rebuild` prints the plan (dry run).
3. Authorized downloads only: `--rebuild --yes` recreates the venv +
   TheRock torch gfx103X + requirements (multi-GB, Z:).
4. `WANGP.cmd --launch`: Gradio UI; first run downloads the slot's
   weights (Z:). Close window / Ctrl+C stops it; stops its own server.

Capacity: image 1024px in low minutes; video 480p/seconds in many
minutes. CPU offload available in-app if VRAM overflows. No verdict on
quality/speed until the authorized first run.
