# Eval: incorporate `pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-GGUF` (2026-09-22)

**Verdict:** only plausible through the existing **stable-diffusion.cpp Vulkan** path
(`Z:/Models/runtime/sd-vulkan`), not through Smol/Taller (`scripts/local_models.py` is
chat/coding servers only). Nothing downloaded, nothing registered. A trial costs ~4.9-11 GB
on `Z:` and needs explicit download authorization.

## What the artifact is (observed, HF API)

- Repo: `pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-GGUF`, revision
  `025c7b7efed480e60150efcd12b036791dd6b827`, last modified 2026-09-21, license `apache-2.0`.
- GGUF arch `qwen3vl`, 262144 ctx, 34k downloads / 86 likes. Not gated.
- It is a **community refusal-ablated ("heretic") derivative of `Qwen/Qwen3-VL-8B-Instruct`** -
  the text encoder Qwen-Image-2.1 uses unmodified. Not an official Qwen release.
- Files (pinned sizes + LFS sha256, from `?blobs=true`):

| File | Bytes | sha256 (first 16) | Role |
|---|---:|---|---|
| `qwen3vl_8b_heretic-Q4_K_M.gguf` | 5,027,785,376 | `1338274ac7a6344f` | language tower (quantized, 4.90 bpw) |
| `mmproj-qwen3vl_8b_heretic-f16.gguf` | 1,159,030,464 | `4649839491c8df1e` | vision tower (f16) - only needed for image-conditioned work (Edit / I2I) |

- Upstream card claims: 100/100 -> 5/100 refusals, KL 0.0220 vs the stock encoder, vision
  tower deliberately left unquantized, INT8 `embed_tokens`/`lm_head` kept (Comfy-Org's scheme).

## Rig fit (observed)

- Card: RX 6600 8 GB, 16 GB RAM, `Z:` HDD, AMD only. `Z:/Models/images` holds only
  `sd_xl_turbo_1.0_fp16.safetensors` (6.9 GB). No ComfyUI anywhere on `Z:`/`Z:/Apps`.
- `Z:/AI/WanGP` exists but its torch path is the known ROCm-staging blocker
  (`IMG_VIDEO_LOCAL.md`); the working image path is exactly `sd.cpp` Vulkan.
- `Z:/Models/runtime/sd-vulkan`: `sd-cli.exe`, commit `42d6c0a`.
  - `--llm <path>` is documented as the **LLM text encoder** ("qwenvl2.5 for qwen-image,
    mistral-small3.2 for flux2, ..."), plus `--llm_vision` for the ViT/mmproj.
  - The shipped binary's LLM-encoder arch table contains `qwen2.5vl`, **`qwen3vl`**, `qwen3`,
    `mistral_small3.2`, `gemma3_12b` - i.e. this build knows the `qwen3vl` encoder arch.
  - It also carries `qwen_image` diffusion-arch strings (`qwen_image.hpp`,
    `qwen_image.prelude`, `qwen_image.transformer_blocks.`, `qwen_image_zero_cond_t`).
- Diffusion side exists upstream: `leejet/Qwen-Image-2.1-GGUF` (converted **with
  stable-diffusion.cpp**, README points at `stable-diffusion.cpp/docs/qwen_image_2.1.md`):
  Q2_K 2.56 GB, Q3_K 3.27 GB, Q4_0/Q4_K 4.20 GB, Q5_0 5.07 GB, Q6_K 6.00 GB, Q8_0 7.69 GB.
  VAE: `Comfy-Org/Qwen-Image-2.1` -> `qwen_image_2.1_vae_bf16.safetensors` 0.68 GB.
- Why this GGUF at all: the alternatives for the same encoder are Comfy-Org
  `qwen3vl_8b_int8_convrot` 9.35 GB / `w4a8` 6.31 GB / bf16 17.53 GB. At 4.68 GB this
  derivative is the only sub-5 GB option, which is its whole point on an 8 GB card.

## Load / memory math (candidate, not measured)

`--llm` 4.68 GiB + `--llm_vision` 1.08 GiB + Q4_K diffusion 4.20 GB + VAE 0.68 GB
= **~10.6 GB resident**. That does not fit 8 GB VRAM, so it would run only via
`--auto-fit` / `--offload-to-cpu` graph cutting, streaming from 16 GB RAM and an HDD.
For reference, SDXL-Turbo at 512px/4 steps already costs ~6 min wall on this card.
Text-to-image alone can drop the mmproj (t2i needs the language tower only).

## Not verified / blockers

- **[unverified]** Whether sd.cpp loads *this* third-party (llama.cpp-converted) Q4_K_M file
  as `--llm`. The arch name is present in the build's table, but sd.cpp's Qwen encoders
  normally come from its own converter; tensor-name/layout mismatch is the classic silent
  failure mode (the upstream card itself lists 5 such silent-wrong-file pitfalls).
- **[unverified]** Whether this build's `qwen_image` arch covers **2.1** specifically.
- **[unverified]** VAE loading from Comfy-Org safetensors, and any speed figure on the RX 6600.
- **[not done]** No download, no smoke run, no `local_models.py` change.

## Risks

- Abliterated derivative: 5/100 refusals and KL 0.0220 vs the stock encoder. Numerically
  close, but it is a modified encoder, and prompt-refusal behaviour differs by design.
  Apache-2.0 carries over; still a community artifact, not an official release.
- Disk/RAM: trial is ~4.9 GB (t2i: encoder + Q4_K diffusion + VAE) to ~11 GB (adding mmproj
  and a bigger diffusion quant) on `Z:`. Standing rule: nothing large on `C:`.
- Do not add it to the Smol/Taller registry; image assets belong under `Z:/Models/images`
  and the sd.cpp runtime, not `data/models`.

## Recommended next step (needs user go-ahead)

1. Authorize the downloads: `local-coding/scripts/download_verified_model.py` (pinned,
   resumable, SHA256-verified) for both GGUF files, plus `leejet/Qwen-Image-2.1-GGUF`
   `qwen_image_2.1-Q4_K.gguf` and the VAE. Target `Z:/Models/images/qwen-image-2.1/`.
2. Bounded smoke: 512px, few steps, t2i, `--backend "diffusion=vulkan0,llm=vulkan0,vae=vulkan0"`,
   then repeat with `--llm_vision` only if Edit/I2I is wanted.
3. Only if the smoke passes: document the working shape and decide whether an image-stack
   entry (separate from `local_models.py`) is worth it.

```
sd-cli.exe -M img_gen ^
  --diffusion-model Z:\Models\images\qwen-image-2.1\qwen_image_2.1-Q4_K.gguf ^
  --llm           Z:\Models\images\qwen-image-2.1\qwen3vl_8b_heretic-Q4_K_M.gguf ^
  --llm_vision    Z:\Models\images\qwen-image-2.1\mmproj-qwen3vl_8b_heretic-f16.gguf ^
  --vae           Z:\Models\images\qwen-image-2.1\qwen_image_2.1_vae_bf16.safetensors ^
  -p "<prompt>" -o smoke-qwen21.png -W 512 -H 512 --steps 8 ^
  --backend "diffusion=vulkan0,llm=vulkan0,vae=vulkan0"
```
