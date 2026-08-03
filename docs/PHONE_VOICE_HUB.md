# Phone voice hub + multi-project workers

**Mic needs HTTPS** (phone blocks `http://` for getUserMedia).

| Mode | URL |
|------|-----|
| **HTTPS self-signed (now)** | `https://100.87.252.18:59200/static/talk.html` — accept warning once |
| Short | `https://100.87.252.18:59200/static/t.html` |
| Tailscale Serve (best) | `https://catboxprime.tail6be020.ts.net/static/talk.html` after enable |

Hold-to-talk → STT → project router → chat (OmniRoute) or Agents inbox → Edge TTS.

## Enable HTTPS on PC

```powershell
cd E:\zengatrivi-drive-e\catts
# stop plain HTTP API on :59200 first if running
.\scripts\start_api_https.ps1
```

**Tailscale Serve (valid cert, no warning):** open once  
https://login.tailscale.com/f/serve?node=na5746KeCj11CNTRL  
then: `tailscale serve --bg 59200`  
(also auto-attempted by `start_remote_stack.ps1`).

## Projects

| Chip | Worker (Agents UI) | cwd |
|------|--------------------|-----|
| CatTS | `catbox-catts` (+ alias `catboxprime`) | `E:\zengatrivi-drive-e\catts` |
| Rosario | `catbox-rosario` | `C:\zengatrivi\REACTJS\rosario-cards-v1` |
| CatReader | `catbox-catreader` | `C:\zengatrivi\REACTJS\catreader` |

Registry: `data/voice_projects.json`.

## Spoken switches

- `proyecto rosario …` / `project catreader …` — override chip
- `código …` / `code …` / `agents …` — append `data/voice_inbox/<id>.jsonl` + TTS ack (open [cursor.com/agents](https://cursor.com/agents) → that worker)

## Boot (PC)

```powershell
cd E:\zengatrivi-drive-e\catts
.\scripts\start_remote_stack.ps1   # API + multi workers
.\scripts\start_api_https.ps1      # if mic / insecure warning
# or workers only:
.\scripts\start_cloud_workers.ps1
```

STT first turn may be slow unless `CATTS_STT_WARMUP=1`. Chat needs OmniRoute (`CATTS_OMNIROUTE_URL`, default `:20128/v1`); if down, short fallback reply still TTS.

## API

- `GET /voice/projects`
- `POST /voice/turn` multipart: `audio`, `project`, `lang`

## Related

`PHONE_STACK.md` · `CLOUD_AGENTS.md` · `SESSION_CONTEXT.md`
