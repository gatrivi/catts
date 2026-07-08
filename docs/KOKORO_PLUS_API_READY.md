# Kokoro Plus API readiness (localhost)

Goal: make CATTS use Kokoro-FastAPI locally via the OpenAI-compatible TTS endpoints, so `CATTS_TTS_ENGINE=kokoro` works immediately.

This is docs-only prep for the later “live interpreting ttw” upgrade (fish-speech-zluda will plug in then, while this endpoint stays stable).

---

## 1) Required env vars (CATTS .env)

Set these (or copy from `.env.example`):

```txt
CATTS_TTS_ENGINE=kokoro
CATTS_KOKORO_URL=http://127.0.0.1:8880
CATTS_KOKORO_VOICE=af_bella
```

CATTS config source:
- `CATTS_TTS_ENGINE` chooses the engine in `services/tts_client.py`
- `CATTS_KOKORO_URL` + `CATTS_KOKORO_VOICE` drive Kokoro requests in `services/kokoro_tts.py`

---

## 2) Start Kokoro-FastAPI (localhost)

From repo root `e:\zengatrivi-drive-e\catts`:

```powershell
.\scripts\setup_kokoro.ps1
.\scripts\start_kokoro.ps1
```

Notes:
- First synth may download/load the Kokoro pipeline (can be slow on cold start).
- The Kokoro server listens on `http://127.0.0.1:8880`.

---

## 3) What CATTS calls (Kokoro “OpenAI-compatible”)

Kokoro endpoints expected by CATTS:

### 3.1 List voices

`GET {CATTS_KOKORO_URL}/v1/audio/voices`

CATTS uses this in `kokoro_tts.ready()` to decide if Kokoro is reachable/healthy.

### 3.2 Synthesize audio (used by both “book TTS” and “live TTS” for kokoro)

`POST {CATTS_KOKORO_URL}/v1/audio/speech`

JSON payload sent by CATTS:

```json
{
  "model": "kokoro",
  "input": "<text>",
  "voice": "<CATTS_KOKORO_VOICE>",
  "response_format": "wav",
  "speed": 1.0
}
```

Response:
- raw WAV bytes (`media_type: audio/wav`)

---

## 4) Verify end-to-end in CATTS

Run CATTS API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200
```

### 4.1 CATTS health should show Kokoro ready

`GET http://127.0.0.1:59200/health`

You want:
- `tts_engine: "kokoro"`
- `tts_ready: true`

### 4.2 Live TTS should return `audio/wav`

`POST http://127.0.0.1:59200/tts/live`

Body (example):

```json
{ "text": "Hello this is a CATTS test", "lang": "en" }
```

Expect:
- HTTP 200
- response `Content-Type: audio/wav`
- header `X-TTS-Engine: kokoro`

CATTS live endpoint uses this same Kokoro synth path but also enforces the live length limit (80 words for kokoro).

---

## 5) LAN/static-ip note (no implementation yet)

Today this is `127.0.0.1`.

Later, when you want other deployed apps to reach Kokoro:
- expose the Kokoro server by setting `KOKORO_HOST` (in `scripts/kokoro_server.py`) to a reachable interface like `0.0.0.0` or your LAN IP
- update `CATTS_KOKORO_URL` to `http://<static-ip>:8880`

No code changes are required in CATTS beyond updating env vars; `/v1/audio/speech` stays the same.

