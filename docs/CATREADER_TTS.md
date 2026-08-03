# CatReader ↔ CATTS (chaptered books + live TTS)

Base URL: `http://127.0.0.1:59200` (or Tailscale host)

## API key (why it asks)

CATTS reads `CATTS_API_KEY` from `.env`.

| `.env` value | CatReader should |
|---|---|
| **empty** | Omit `X-API-Key` entirely (blank is fine). If the app *requires* a field, put anything or leave blank — CATTS ignores the header when key is unset. |
| **`catts-local`** (recommended for LAN) | Send header `X-API-Key: catts-local` |

If CatReader always shows an API-key box, set both sides to **`catts-local`**.

## Chaptered book + subtitles

```
GET  /books
GET  /books/{book_id}
GET  /books/{book_id}/chapters/{n}/audio      → audio/mpeg (mp3)
GET  /books/{book_id}/chapters/{n}/subtitles  → text/srt
GET  /books/{book_id}/download               → application/zip (ready mp3s)
```


Auth: same `X-API-Key` rule as above.

Example book id: `KEEP_The_Secret_of_the_Rosary`

```json
// GET /books/KEEP_The_Secret_of_the_Rosary
{
  "id": "KEEP_The_Secret_of_the_Rosary",
  "title": "The Secret of the Rosary",
  "chapters": 52,
  "chapters_ready": 52,
  "ready": true,
  "has_subtitles": true,
  "chapters_detail": [
    {
      "index": 1,
      "title": "Preface",
      "empty": false,
      "audio_url": "/books/KEEP_The_Secret_of_the_Rosary/chapters/1/audio",
      "subtitle_url": "/books/KEEP_The_Secret_of_the_Rosary/chapters/1/subtitles"
    }
  ]
}
```

Player: load chapter N audio URL; load matching `subtitle_url` as SRT (cues start at 00:00:00 per chapter).

Skip chapters with `"empty": true` until album re-render finishes (legacy title-only stubs).

## Live page sentence TTS (streaming read-along)

```
POST /tts/speak
Content-Type: application/json
X-API-Key: catts-local   // if key set

{"text":"One sentence.","lang":"en"}
→ audio/wav
```

Short bursts: `POST /tts/live` (≤80 words for kokoro).

Prefetch next sentence while current plays.

## Engine

`GET /tts/engines` · `PUT /tts/engine` `{"engine":"kokoro"}`  
Need FastKokoro on `:8880` for local EN: `.\scripts\start_kokoro.ps1`

## Health

`GET /health` — no key. Check `tts_ready` + `tts_engine`.
