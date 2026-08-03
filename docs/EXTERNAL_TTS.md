# External apps → CATTS TTS

Base: `http://<catts-host>:59200` (LAN/`0.0.0.0`; Tailscale OK)  
Auth: header `X-API-Key: <CATTS_API_KEY from .env>`  
**CatReader:** use `catts-local` (set in `.env`). Blank key = auth off, but many apps still demand a field — hence the concrete value. See `docs/CATREADER_TTS.md`.

## Chaptered book + subtitles (CatReader)

```
GET /books
GET /books/{book_id}
GET /books/{book_id}/chapters/{n}/audio
GET /books/{book_id}/chapters/{n}/subtitles
```

Example id: `KEEP_The_Secret_of_the_Rosary` · header `X-API-Key: catts-local`

## Speak (readings — use this)

`POST /tts/speak`  
Body JSON: `{ "text": "...", "lang": "es" }`  (or `"en"`)  
Max ~12k chars. Response: `audio/wav`  
Headers: `X-TTS-Engine`, `X-TTS-Latency-Ms`

```powershell
# ES HQ (default engine=edge → es-AR-TomasNeural)
curl.exe -s -X POST "http://127.0.0.1:59200/tts/speak" `
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" `
  -d "{\"text\":\"Hola, esto es una prueba de lectura.\",\"lang\":\"es\"}" `
  -o reading.es.wav
```

## Live chunks (interpreting)

`POST /tts/live` — short only (≤500 chars / word cap). Same auth.

## Engine

`GET /tts/engines` · `PUT /tts/engine` `{"engine":"edge"}`  

**ES highest quality ready now:** **`edge`** (`es-AR-TomasNeural`). Endpoint live on `:59200`.

| Rank | Engine | When |
|---|---|---|
| 1 ready | **edge** | Neural LatAm; needs net; `.env` default |
| 1 local clone | **chatterbox** + voice `0b0ad49fcac94af4` | Best clone; needs ~8 GB free RAM (kill STT/Cursor) |
| 2 local | **melotts** | Offline ES preset; no clone |

```powershell
curl.exe -s -X PUT "http://127.0.0.1:59200/tts/engine" -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" -d "{\"engine\":\"edge\"}"
curl.exe -s -X POST "http://127.0.0.1:59200/tts/speak" -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" -d "{\"text\":\"Hola, lectura de prueba.\",\"lang\":\"es\"}" `
  -o reading.es.wav
```

Smoke: `data/tts_tests/hq_es_edge_smoke.wav`. Sample: `/tts/samples/edge-es-ar.wav`.


## Audiobook (external app)

`POST /jobs/audiobook` (multipart) — same auth.  
Fields: `file` (pdf/epub/txt), `lang=es`, optional `title`/`author`/`voice_id`.  
Uses the **active** TTS engine (`PUT /tts/engine` first). Poll `GET /jobs/{id}`.

```powershell
curl.exe -s -X PUT "http://127.0.0.1:59200/tts/engine" -H "X-API-Key: YOUR_KEY" `
  -H "Content-Type: application/json" -d "{\"engine\":\"melotts\"}"
curl.exe -s -X POST "http://127.0.0.1:59200/jobs/audiobook" -H "X-API-Key: YOUR_KEY" `
  -F "file=@book.pdf" -F "lang=es" -F "title=Mi libro"
```

Sample phrase: `GET /tts/samples/melotts-es.wav`

## Keep running

```powershell
# MeloTTS needs no extra server (worker starts on first synth)
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 59200
# optional EN/ES alt:
.\scripts\start_kokoro.ps1         # :8880
```
