# Recon: `dealignai/Bonsai-2-27B-1bit-CRACK-GGUF` (2026-09-23) — same file we already have

Status: RESOLVED, no download needed, no runtime change. Triggered by a user-supplied link,
checked because it looked like it might be a *new* 1-bit Bonsai-2 quant.

## Verdict

It is **not a new model and not related to Ming-Image**. It is a third-party re-upload of the
author's PTQ1_0 ternary weights under a "CRACK" label, and **we already hold the canonical file**.

## Evidence

HF page (fetched 2026-09-23, `huggingface.co/dealignai/Bonsai-2-27B-1bit-CRACK-GGUF`):

- single GGUF: `Bonsai-2-27B-PTQ1_0-CRACK.gguf`, `totalFileSize: 5946648928` bytes (~5.54 GiB)
- `isQuantized: true`, `licenseFilePath: LICENSE`, bos `<|endoftext|>`, eos `<|im_end|>`

Local canonical artifact (`data/models/bonsai2-27b-ptq10/`, `*.verified.json`):

| | value |
|---|---|
| repo / revision | `prism-ml/Ternary-Bonsai-2-27B-gguf` / `6ed5e12bf84b7a63069882c91dd9e9218647d17b` |
| file | `Ternary-Bonsai-2-27B-PTQ1_0.gguf` |
| bytes | **5946648928 (exact match with the CRACK re-upload)** |
| sha256 | `53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3` |

Byte-identical size to the author's PTQ1_0 = the "1bit"/"CRACK" naming is a re-label of the same
quant, not a new bit-width (we already run it at 6.4–6.7 t/s, and PTQ1_0 is the quant the author
benchmarked). Proving identity beyond size would need the third-party file's own SHA256, which the
page does not publish — not worth a 5.5 GB download.

## Side finding: the re-upload's chat template independently confirms our reasoning-effort doc

The page embeds the model's Jinja template. It contains:

```
{%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}
{%- if resolved_reasoning_effort not in ('xhigh', 'medium', 'low') %}
  {{- raise_exception('Unexpected reasoning effort ...') }}
```

So the template default really is `xhigh` and the **only** legal levels are `xhigh`, `medium`,
`low` — there is no "high". Any T1 A/B must use one of those three strings or the request raises.
The template also confirms `<think>` blocks, `preserve_thinking`, and the `<tool_call>/<function=>`
XML tool format we already rely on for tool use.

## Hygiene / policy

- Provenance is unverified and the name implies a license-bypass conversion; nothing about it
  should be cited as an upstream artifact. Our rule stands: model downloads only through
  `scripts/download_verified_model.py` (SHA256 + provenance recorded in `.verified.json`).
- If a future task ever needs that exact file, verify its SHA256 against `53107f53...` first and
  treat any difference as a different artifact.

## Cross-refs

- `BONSAI2_REASONING_EFFORT.md` — template default `xhigh`; legal levels now independently confirmed.
- `MODEL_ROSTER.md` — PTQ1_0 row (5.54 GB, 6.4–6.7 t/s, fidelity-critical).
- `MING_IMAGE_0.1_DESIGN_EVAL_2026-09-22.md` — the unrelated inclusionAI family from the same message.
