# Voice cloning preference (user)

Last updated: 2026-07-08

## Preference
**Zero-shot is not a goal.** “Clone from the smallest sample in the least time” is irrelevant here.

OK if voice training takes **hours or days**. Use cases:

1. **Audiobooks** of our books — offline batch, no rush.
2. **Interpreting** — train voice on day X, use from day Y.

### Where performance *does* matter
- **Live interpreting TTS soundbites** (breath / period / comma): latency matters.
- **Voice training / fine-tune:** latency does **not** matter.
- **Audiobook render:** overnight OK.

Optimize for: **sounds like the speaker (Córdoba ES / EN)**, commercial-safe when possible.

**Accent method:** see `docs/ACCENT_CORDOBA.md`. Do not treat Piper→RVC as proven Córdoba dialect.

Commercial / cloud GPU findings: `docs/COMMERCIAL_VOICE_DEPLOYMENT.md`.

## Consequence for engine choice
| Approach | Fit |
|---|---|
| XTTS / Fish zero-shot | Fast to try; quality/accent often poor; XTTS non-commercial |
| **GPT-SoVITS-class few-shot train** | Better clone quality; MIT; needs train pipeline; AMD Win is hard (NVIDIA packages dominate) |
| Chatterbox MIT | Commercial-friendly zero/few-shot; AMD path unclear |
| Kokoro | No clone — narration only |

**Do not** spend more tokens chasing zero-shot “instant clone” demos. Prefer **train once → reuse forever**.

## Honest note
We spent time on XTTS/Kokoro/Fish zero-shot because early docs optimized for “live interpreting latency” and AMD ZLUDA. Given this preference, **GPT-SoVITS (or similar train-once)** should have been evaluated earlier for audiobook quality. Remaining blocker is still **hardware path** (NVIDIA-centric SoVITS vs AMD Win), not “training time.”

## How much audio (honest)
| Goal | Minutes (clean, deduped, one speaker) | Notes |
|---|---|---|
| RVC timbre only | **15–30 min** | We have ~28 min. Enough for “sounds like him,” **not** Córdoba phonetics. |
| GPT-SoVITS / F5 few-shot clone | **~10–30 min** usable | Common sweet spot; quality jumps with clean single-speaker audio. |
| Strong audiobook / accent lock | **30–60+ min** | Better prosody + stable ñ/tildes/accent; diversity of sentences beats raw hours of noisy WhatsApp. |
| Production-grade custom TTS | **hours of curated** | Studio-ish reading, transcripts, balanced phonemes — not 10h of zero-shot tinkering. |

**We already have ~28 min** (`data/rvc/gaston/dataset/`). That is in the right ballpark for a *trained* clone. Last night’s low quality was mostly **wrong method** (zero-shot XTTS/Fish/Kokoro+partial RVC that never finished), not “need 10 more hours of audio.”

More audio helps only if: (1) original speaker recordings, (2) no TTS-generated copies, (3) train GPT-SoVITS-class (or finish RVC as timbre fallback). Cloud NVIDIA overnight > another 10h on AMD zero-shot.

## Next (when budget allows)
1. Finish HIP 5.7.1 only if still pursuing Fish; else skip.
2. Spike GPT-SoVITS on cloud NVIDIA with the existing ~28 min corpus (add toward 45–60 min if easy).
3. Wire trained SoVITS (or equivalent) into CATTS `/tts` for books + live.
