# CATTS Pocket-TTS engine handoff

**CATTS version:** `v0.7.2`

This doc covers the “smol TTS now” engine integration using **kyutai-labs/pocket-tts**.

---

## 1) What changed

- New engine implementation:
  - `services/pocket_tts.py`
- Engine wiring:
  - `services/tts_client.py`
- Health/UI support fields:
  - `api/schemas.py` (`tts_ready`, `tts_message`)
  - `api/routes/health.py`
- Dependency:
  - `requirements.txt` now includes `pocket-tts`

---

## 2) How to enable it

Set in `.env` (or `.env.example` then copy to `.env`):

- `CATTS_TTS_ENGINE=pocket`

Then install deps into `.venv`:
- run `scripts/setup_api.ps1` (or `pip install -r requirements.txt`)

---

## 3) Behavior

- Book TTS (`POST /jobs/audiobook` → chapter synthesis) uses pocket-tts when enabled.
- If a voice has a reference/sample audio, pocket-tts uses that reference as the voice prompt.
- Otherwise it uses a built-in pre-made voice by language:
  - `en` → `alba`
  - `es` → `lola`

---

## 4) Live interpreting caveat

`/tts/live` is still XTTS-oriented in its availability messaging and reference resolution.
Pocket-t-ts supports synthesizing locally, but “live interpreting” semantics still assume an XTTS-style voice reference flow.

If you want `/tts/live` to fully work with pocket-tts (no XTTS), tell me and I’ll wire it end-to-end.

