# CatIntAssist integration

Wire the React parent app to this server on port **59125**.

## Environment (CatIntAssist `.env`)

```bash
REACT_APP_TTS_URL=http://127.0.0.1:59125
```

The hook should call `POST ${REACT_APP_TTS_URL}/tts` (not `/generate`).

## Contract

```http
POST /tts
Content-Type: application/json

{"text": "…", "lang": "en" | "es"}
```

→ `200 OK`, body = `audio/wav` bytes.

## `useTTS.js` — `prefetchTTS`

Point prefetch at this server; keep existing dual-`<audio>` `playTTS` (headphones + `setSinkId` virtual cable):

```javascript
const TTS_BASE = process.env.REACT_APP_TTS_URL || 'http://127.0.0.1:59125';

export async function prefetchTTS(text, lang = 'en') {
  const res = await fetch(`${TTS_BASE}/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang }),
  });
  if (!res.ok) {
    throw new Error(`TTS failed: ${res.status} ${await res.text()}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
```

`playTTS(blobUrl)` stays unchanged: one `<audio>` to default output, one with `setSinkId` to VB-Cable for the call.

## Health check (optional)

```javascript
const health = await fetch(`${TTS_BASE}/health`).then((r) => r.json());
// { ok: true, model: "piper", device: "cpu", ... }
```

## WSL note

Run **both** CatIntAssist (browser on Windows) and **catts** inside the same WSL distro so `127.0.0.1:59125` from Windows reaches the server (WSL2 forwards localhost by default). If needed, use the WSL IP from `hostname -I` and set `REACT_APP_TTS_URL` accordingly.

## OmniVoice alternative

OmniVoice Studio uses `POST http://127.0.0.1:8000/generate` with a different JSON shape. Do **not** point CatIntAssist at that URL directly unless you add an adapter. This repo implements the CatIntAssist contract natively.
