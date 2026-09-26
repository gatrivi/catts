---
license: apache-2.0
base_model:
- pottokao/Qwen-Image-2.1-Text-Encoder-Heretic
tags:
- quantized
- gguf
- llama-cpp
- qwen-image
- abliterated
- text-encoder
- comfyui
---


# Qwen-Image-2.1 Text Encoder (Heretic) — GGUF Q4_K_M

> **Not affiliated with, or endorsed by, Alibaba / Qwen.** Community derivative
> (refusal-ablated) of [`Qwen/Qwen3-VL-8B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
> — the model Qwen-Image-2.1 uses, unmodified, as its text encoder. Qwen releases that
> model under **Apache-2.0**, so this derivative is redistributed under Apache-2.0
> (see `LICENSE` and `NOTICE`).


GGUF Q4_K_M build of [`Qwen-Image-2.1-Text-Encoder-Heretic`](https://huggingface.co/pottokao/Qwen-Image-2.1-Text-Encoder-Heretic),
the abliterated text encoder of [`Qwen/Qwen-Image-2.1`](https://huggingface.co/Qwen/Qwen-Image-2.1).

**File:** `qwen3vl_8b_heretic-Q4_K_M.gguf` — 4.68 GB (4.90 bits/weight, from 15.26 GB bf16 GGUF)

## Ablation (inherited from the bf16 source)

| | Refusals | KL divergence |
|---|---:|---:|
| Stock Qwen-Image-2.1 text encoder | 100/100 | 0 *(by definition)* |
| **This family** | **5/100** | **0.0220** |

Produced with [Heretic](https://github.com/p-e-w/heretic) directional ablation
(`o_proj` + `down_proj`), 200 trials / 60 startup trials, knee point of the Pareto
front. Measured on `mlabonne/harmful_behaviors` (refusals) and
`mlabonne/harmless_alpaca` (KL). Independently re-checked on the bf16 source:
**0/20** refusals, **4/4** benign questions answered correctly.

Full methodology, Pareto table and reproduction command are in the
[bf16 repo](https://huggingface.co/pottokao/Qwen-Image-2.1-Text-Encoder-Heretic).

## Who this is for

**Mac / Apple Silicon, and anything else in the llama.cpp ecosystem.**

This is the honest answer for non-NVIDIA hardware: the NVFP4 and W4A8 builds in
this family rely on CUDA kernels and fall back to dequantize-then-compute
elsewhere — memory saving, but no speedup. GGUF has real Metal support.

## What is quantized, what is protected

Recipe decoded from Comfy-Org's own `qwen3vl_8b_w4a8.safetensors` and reproduced
exactly — **the same protection scheme is used for every format in this family**:

| Layers | Count | Precision |
|---|---:|---|
| FFN + attention projections | 252 | **4-bit** (this repo's format) |
| `embed_tokens`, `lm_head` | 2 | INT8, per-channel + convrot |
| Vision tower | 351 tensors | **bf16 — untouched** |
| norms / biases | — | bf16 |

79.2 % of parameters go to 4-bit, 14.2 % stay at 8-bit, 6.6 % stay at bf16.

## Format details

Converted with `llama.cpp` (`conversion/qwen3vl.py` registers
`Qwen3VLForConditionalGeneration`), then quantized with `llama-quantize` to
`Q4_K_M` — llama.cpp's own mixed-precision K-quant scheme, which keeps selected
tensors at higher bit depth automatically.

```
source   15,623 MiB  (16.00 bpw)
Q4_K_M    4,789 MiB  ( 4.90 bpw)
```

### Vision tower is included — as a separate mmproj file

llama.cpp splits multimodal models in two. **Both files are published here and you
need both for image-conditioned work (Qwen-Image-2.1 Edit):**

| File | Tensors | Size | Contains |
|---|---:|---:|---|
| `qwen3vl_8b_heretic-Q4_K_M.gguf` | 399 | 4.68 GB | language tower (quantized) |
| `mmproj-qwen3vl_8b_heretic-f16.gguf` | 352 | 1.08 GB | **vision tower** (f16, unquantized) |

399 + 352 accounts for all 750 tensors of the source model (+1 projector
parameter). The vision tower is kept at f16 — the same choice the safetensors
builds make, where all 351 vision tensors stay bf16.

Text-to-image only? The main file alone is enough.

## Usage

```bash
llama-cli -m qwen3vl_8b_heretic-Q4_K_M.gguf -p "your prompt" -ngl 99
```

or load through `ComfyUI-GGUF` as a text encoder.

## Pitfalls found while building this

Each of these produces a **valid-looking file that is silently wrong** — same size,
same tensor count, same format strings. They were only caught by diffing against
the official release, or by actually running the model.

1. **The vision tower must be excluded.** Comfy-Org leaves all 351 vision tensors
   in bf16; a naive "quantize every 2-D weight" pass eats them.
2. **`int8_tensorwise` needs `convrot=True` explicitly.** The 4-bit path applies
   convolution rotation internally; the INT8 path defaults to `False`.
3. **`comfy_quant` must serialize the whole per-layer config**, not just
   `{"format": …}`, or `convrot` / `convrot_groupsize` are dropped.
4. **MXFP8 scales must be stored as `uint8`.** `TensorCoreMXFP8Layout.quantize()`
   returns `float8_e8m0`, which ComfyUI's safetensors loader cannot parse
   (`KeyError: 'F8_E8M0'`).
5. **Comfy-Org's repack strips the `model.language_model.` prefix.** Quantizing
   straight from the HF layout yields keys ComfyUI never finds — the model loads
   "successfully" and emits noise.

## The rest of this family

| Repo | What it is |
|---|---|
| [`Qwen-Image-2.1-Text-Encoder-Heretic`](https://huggingface.co/pottokao/Qwen-Image-2.1-Text-Encoder-Heretic) | **bf16 source** — full precision, 17 GB |
| [`Qwen-Image-2.1-Text-Encoder-Heretic-NVFP4`](https://huggingface.co/pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-NVFP4) | NVFP4 (w4) for Blackwell — native FP4 tensor cores, 5.87 GB |
| [`Qwen-Image-2.1-Text-Encoder-Heretic-W4A8`](https://huggingface.co/pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-W4A8) | Asymmetric W4A8 INT8 — same format Comfy-Org ships, 5.88 GB |
| [`Qwen-Image-2.1-Text-Encoder-Heretic-GGUF`](https://huggingface.co/pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-GGUF) | GGUF Q4_K_M — Mac / llama.cpp, 4.68 GB ← **you are here** |
