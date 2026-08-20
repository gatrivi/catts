# fish-speech-zluda status (2026-07-31)

## Verdict
**Working** on RX 6600 via ZLUDA. Health `:8080` OK. ES clone synth with Gaston ref succeeded.

## Measured (this PC)
| Step | Time |
|------|------|
| Cold start + warmup compile (`Hello world.`) | **~9 min** (PID up → listening) |
| First real synth (28w + 15s ref, still compiling) | **~452 s** |
| Second synth (14w + ref, kernels warm) | **~68 s** → ~7.6 tok/s, ~3.1 GB VRAM |
| Live UI cap | 80 words |

Both smokes hit `max_new_tokens=512` → ~23.7 s WAV each (cap, not text length). Tune tokens down for short clips.

## Layout
- Fish root: `E:\zengatrivi-drive-e\fish-speech-zluda` (not under `catts/external/`)
- gfx1032: copied into `C:\Program Files\AMD\ROCm\5.7\bin\rocblas\library` (no `hip57-shadow` needed)
- Start: `.\scripts\start_fish_zluda.ps1` (`FISH_SKIP_WARMUP=1` patched in `tools/server/model_manager.py` — next boot binds before compile)
- Smoke WAVs: `data/fish_smoke_es.wav`, `data/fish_smoke_es2.wav`

## Start
```powershell
.\scripts\start_fish_zluda.ps1
# wait for GET http://127.0.0.1:8080/v1/health -> {"status":"ok"}
```

Kill when idle (`docs/HEAVY_PROCESSES.md`). Weights **CC-BY-NC-SA-4.0**.
