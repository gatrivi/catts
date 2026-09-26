# Eval: `inclusionAI/Ming-Image-0.1-Design` vs our Qwen-Image-2.1 stack (2026-09-22)

**Verdict: our Qwen-Image-2.1 stack is the better fit, and it is the only one of the two that
can run on this rig at all.** Ming-Image-0.1-Design is purpose-built for UI / infographic /
poster design with text rendering and RGBA transparency, and it is probably the stronger model
for exactly those tasks - but it is not runnable here: no GGUF, no ComfyUI or
stable-diffusion.cpp support, ~53 GB of weights, a custom torch repo, and a validated target of
a single 80 GiB CUDA GPU. Our only working image path is sd.cpp Vulkan, which needs no torch.

Companion doc: `QWEN_IMAGE_2.1_TEXT_ENCODER_EVAL_2026-09-22.md`.

## What Ming-Image-0.1-Design is (observed, HF API + model card)

- `inclusionAI/Ming-Image-0.1-Design`, revision `1cd7fac3b0dcb54196fe2cd12b80da09edf8fcf4`,
  published 2026-09-22 (same day as this eval), MIT license, 0 downloads / 59 likes, not gated,
  card marks `inference: false`.
- Positioning: a 6B text-to-image model for "UI, infographics, posters, and other text-rich
  visual designs", RGBA output with transparent backgrounds, ships its own UI/UX leaderboard
  asset and a transparency showcase.
- Layout (safetensors, BF16, no quantized or GGUF variant published):

| Component | Size |
|---|---:|
| `mllm/` (7 shards) | 34.00 GB |
| `connector/` (2 shards) | 6.17 GB |
| `transformer/` (5 shards) | 12.31 GB |
| `mlp/` | 0.12 GB |
| `vae/` | 0.25 GB |
| **Total** | **~52.9 GB** |

- Card requirements: 2048x2048 (1024 for faster), 12 steps, CFG 1.0, BF16, hardware "one CUDA
  GPU with 80 GiB VRAM (validated configuration)"; inference via the `inclusionAI/Ming-Image`
  repo (`infer.py`) or vLLM-Omni recipes; prompt enhancement via `Ling-3.0-flash-VL` or
  `qwen3.8-27B`.
- Sibling: `inclusionAI/Ming-Image-0.1-Design-Layer` (layered output), also 0 downloads.

## Rig fit (observed)

- No GGUF in the family: an HF search for "Ming-Image" returns only the two `inclusionAI` repos
  (0 downloads each), and the GGUF-filtered search for "Ming" returns unrelated MING-1.8B LLMs.
- Our `sd-cli.exe` build (commit `42d6c0a`) has no Ming support: the only `ming*` substrings in
  the binary are parts of unrelated English words (`mingw`, `mingled`, ...); its diffusion-arch
  table carries `qwen_image`, `anima`, `flux`, `krea2*`, `cosmos*`, `gemma*` - not Ming.
- The torch route is the known dead end on this box: ROCm/TheRock staging crashes on gfx103X
  (`IMG_VIDEO_LOCAL.md`), and there is no ComfyUI install on `Z:`.
- Even ignoring runtime support, 52.9 GB of weights against an 80 GiB-VRAM reference target is
  an order of magnitude away from 8 GB VRAM / 16 GB RAM / HDD, with no quantized path to close
  the gap.

## Head-to-head

| | Qwen-Image-2.1 (+ heretic encoder GGUF) | Ming-Image-0.1-Design |
|---|---|---|
| Purpose | general text-to-image (plus Edit / I2I) | UI, infographics, posters, text rendering, RGBA transparency |
| Runnable on this rig | plausibly yes, via sd.cpp Vulkan (unverified until a smoke test) | no path |
| Quantized / GGUF availability | yes: `leejet/Qwen-Image-2.1-GGUF` (sd.cpp's own author) plus the encoder GGUF | none published (released today) |
| Trial download size | ~4.9 - 11 GB | ~52.9 GB |
| Runtime | sd.cpp Vulkan (installed; SDXL-Turbo smoke already passes) | custom torch repo / vLLM-Omni |
| Reference hardware | 8 GB-ish with offload, speed unknown | one CUDA GPU, 80 GiB VRAM |
| Text encoder | qwen3vl 8B, 4.68 GiB heretic GGUF (or 6.31 - 17.5 GB official) | 34 GB MLLM + 6.17 GB connector |
| License | Apache-2.0 for the encoder derivative; Qwen research license for the diffusion model | MIT |
| Strength for us | runnable, cheap, general purpose | likely better for design / text-rich / RGBA output |
| Weakness for us | general purpose; text rendering weaker than a design model | not runnable here at any reasonable cost |

## Watchlist trigger

Re-open this if a GGUF port of Ming-Image appears for sd.cpp or ComfyUI, or if someone ships a
<=8 GB 4-bit build with a torch-free runtime. Until then, using Ming-Image means renting a CUDA
GPU, not running it locally.

## Addendum 2026-09-23 — author announcement (marketing claims, verdict unchanged)

Announcement circulated with ModelScope links (`inclusionAI/Ming-Image-0.1-Design` and `-Layer`):
two complementary **6B** models, **MIT**, Design ranks #1 among open-weight models on the Artificial
Analysis UI/UX Design leaderboard, Layer leads all 12 evaluated Crello settings and runs **4.3x
faster than the evaluated 20B open-weight baseline**, up to **2048x2048**, transparent **RGBA**
output, strong text rendering; Layer decomposes flattened graphics into editable RGBA layers.
Pipeline: multimodal prompt conditioning + diffusion transformer + 4-channel VAE (Layer adds
multi-frame generation).

Nothing here changes the 2026-09-22 verdict: still **no GGUF, no sd.cpp/ComfyUI support,
~52.9 GB of weights, custom torch repo, 80 GiB CUDA reference target** — not runnable on
RX 6600 8 GB / 16 GB RAM / HDD. The leaderboard and 4.3x figures are the vendor's own evaluation
against a 20B open-weight baseline; they say nothing about feasibility on this rig. The only new
usable fact is the MIT license (no redistribution worry if a port ever appears).

Watchlist trigger unchanged: a GGUF / <=8 GB 4-bit build for sd.cpp or ComfyUI, or a torch-free
runtime. Until then, Ming-Image means renting a CUDA GPU.

## Evidence gaps

- No Ming-Image weights were downloaded; every Ming number here comes from the HF API listing
  and the model card.
- "Qwen-Image-2.1 plausibly runs here" is still unverified - no smoke test has been run. See the
  companion doc.
