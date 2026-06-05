# catts — CatIntAssist local TTS server

CPU-only text-to-speech for [CatIntAssist](https://github.com/gatrivi/catintassist): `POST /tts` returns `audio/wav` for English and Spanish. No cloud API keys.

## Why Piper (not OmniVoice)

| Factor | Piper | OmniVoice Studio |
|--------|-------|------------------|
| GPU | ONNX Runtime **CPU** — no CUDA/ROCm needed | Heavier stack; GPU paths common |
| RX 6600 | Irrelevant (CPU inference) | AMD GPU unused without ROCm setup |
| API fit | Thin FastAPI wrapper on **:59125** `/tts` | Native `POST /generate` on **:8000** |
| Footprint | ~60–80 MB per medium voice | Larger models + desktop UI |
| Latency (warm) | Typically **&lt;2s** for ~20 words on modern CPU | Varies; often slower in CPU mode |

This repo is a **dedicated TTS microservice**, not a fork of OmniVoice. CatIntAssist only needs bytes back from `/tts`.

## Requirements

- Python 3.10+
- Linux or WSL2 (Windows host + WSL is fine)
- `espeak-ng` (Piper phonemizer dependency)

```bash
# Debian / Ubuntu / WSL
sudo apt update && sudo apt install -y espeak-ng ffmpeg
```

## Install

```bash
cd catts
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_voices.py
```

Default voices (medium quality):

- `en` → `en_US-lessac-medium`
- `es` → `es_MX-ald-medium` (Latin American Spanish)

Override with `TTS_VOICE_EN` / `TTS_VOICE_ES`.

## Start server

```bash
source .venv/bin/activate
python server.py
# listens on http://127.0.0.1:59125
```

Or:

```bash
uvicorn server:app --host 127.0.0.1 --port 59125
```

## API

### `GET /health`

```json
{
  "ok": true,
  "model": "piper",
  "device": "cpu",
  "port": 59125,
  "voices": { "en": { "voice": "en_US-lessac-medium", "loaded": true }, "es": { ... } }
}
```

### `POST /tts`

```bash
curl -sS -o /tmp/en.wav \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello from the local interpreter demo.","lang":"en"}' \
  http://127.0.0.1:59125/tts

curl -sS -o /tmp/es.wav \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola desde la demostración del intérprete local.","lang":"es"}' \
  http://127.0.0.1:59125/tts
```

Response: `200`, `Content-Type: audio/wav`.

## Smoke test

```bash
chmod +x scripts/test-tts.sh
./scripts/test-tts.sh
ffplay -nodisp -autoexit /tmp/catts-tts-test/en-warm2.wav
```

Browser UI (optional `setSinkId` for VB-Cable): open `static/test.html` or serve via the running server at `/static/test.html`.

## Resource use (approximate)

| Item | Size / RAM |
|------|------------|
| Each medium voice | ~60–80 MB disk |
| Server + 2 voices loaded | ~300–500 MB RAM |
| Cold first request | +1–3s (model load) |
| Warm ~20 words | ~0.3–1.5s on 4+ core CPU |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_PORT` | `59125` | Listen port |
| `TTS_MODELS_DIR` | `./models` | Piper `.onnx` files |
| `TTS_VOICE_EN` | `en_US-lessac-medium` | English voice id |
| `TTS_VOICE_ES` | `es_MX-ald-medium` | Spanish voice id |

## CatIntAssist wiring

See [INTEGRATION.md](./INTEGRATION.md) for `REACT_APP_TTS_URL` and `useTTS.js` changes.

## OmniVoice adapter (optional)

If you already run OmniVoice on `:8000`, you can keep it and add a thin proxy in this repo later — but for RX 6600 / CPU-only demos, Piper here is the simpler path.
