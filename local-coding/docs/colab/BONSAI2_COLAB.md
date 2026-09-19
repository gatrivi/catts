# Bonsai-2 27B on Google Colab — try it yourself (~10 min)

**File:** `Z:\catts\local-coding\docs\colab\bonsai2_cuda_colab.ipynb`

## Setup (once)
1. Go to https://colab.research.google.com
2. **File > Upload notebook** → pick `bonsai2_cuda_colab.ipynb`
3. **Runtime > Change runtime type > T4 GPU** → Save

## Run (every session)
Run the 6 code cells top to bottom (`Shift+Enter`):
1. **GPU check** — confirms T4/A100 and picks the matching prebuilt Prism CUDA binary
2. **llama.cpp download** — prebuilt, no compiling (~200 MB, ~1 min)
3. **Model download** — 5.54 GB from Hugging Face (~2-5 min on Colab's pipe)
4. **Launch server** — full GPU offload, 16K context (~1-2 min)
5. **Benchmark** — the tok/s numbers we came for (compare vs. 3.3 local)
6. **Tunnel** — prints a public `https://...trycloudflare.com` URL

## Why this should be much faster than our 3.3 tok/s
Bonsai-2's packed-ternary (type-143) kernels **only exist in the Prism fork**, and only for
**CUDA** (and Metal). Our RX 6600 gets a slow Vulkan fallback; Colab's NVIDIA cards run the
real kernels. Measured expectations: T4 ~5-15 tok/s, L4 ~15-40, A100 ~30-80. Free tier = T4.

## Using it from your PC while Colab runs
- Cell 6's URL: test with a browser (`<url>/health`) or `Invoke-WebRequest "<url>/v1/chat/completions" ...`
- Points any OpenAI-compatible client at `<url>/v1`. Bonsai-2 passed 2/2 native tool-call
  probes locally (just slow); on CUDA it may finally be usable as an agent.
- Tunnel dies when the Colab VM sleeps/disconnects — rerun cell 6.

## Optional: keep the 5.54 GB model across sessions
Cell 3 has a commented Drive-cache block. Uncommenting needs Drive mount permission.
5.54 GB of your ~15 GB Drive quota.

## Notes / limits
- Colab free tier: VM may disconnect on long idle; T4 can be unavailable at peak.
- If cell 2's prebuilt binary complains about CUDA libs, the cell auto-installs CUDA
  runtime wheels and retries (Colab preinstalls torch with its own CUDA — the wheels path is a fallback).
- If BOTH builds fail (e.g. driver ships CUDA 13), note the error — plan B is a llama-box
  variant for L4/A100, not yet in the notebook.
- Faster paid option later: Colab Pro L4 (~$10/mo) or RunPod A100 (~$1-2/h) — same notebook.
- No local machine cost: runs entirely in the cloud VM; Z: files untouched.
