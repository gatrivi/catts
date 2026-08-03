# CATTS en la PC (crib compartido)

Repo: `E:\zengatrivi-drive-e\catts` · Tailscale **`100.87.252.18`**

| App | URL |
|-----|-----|
**Live (prod):**
https://rosario.gatrivi.com
https://cathedral.gatrivi.com
https://catreader.gatrivi.com

**LAN/Tailscale only (dev):** CatReader often `:3002` (if `:3000` taken) · Rosario `:3001` · Cathedral `:3002` clash check · CatTS `:59200`. Not for share links.

**Rosario Liber audio on prod:** needs `/voice/en/*.wav` in the Vercel deploy. Commit ready on `cloud-rosary-v2` (`1ee73cb`). Push requires GitHub auth (`gh auth login` then `git push origin cloud-rosary-v2`). Until then prod returns SPA HTML for those paths.

```bash
cd E:\zengatrivi-drive-e\catts
npm start              # API Edge lean :59200
npm run health
npm stop               # liberar RAM
npm run stop:heavy     # + Kokoro/STT/XTTS
.\scripts\start_reader_stack.ps1   # CatReader :3002 if :3000 taken
```

Cloud agents: https://cursor.com/agents → `catbox-catts` / `catbox-rosario` / `catbox-catreader` (alias `catboxprime`).  
**Voice hub:** http://100.87.252.18:59200/static/talk.html · docs `PHONE_VOICE_HUB.md`

**Slack when API falls:** Cursor `@cursor` ≠ uptime monitor. Create Slack *Incoming Webhook*, put URL in catts `.env` as `CATTS_SLACK_WEBHOOK_URL`, then `npm run watch:slack` (also auto-started by `start_remote_stack.ps1` if set).

**Panza:** `src/lib/catts.ts` · `VITE_CATTS_URL` / `VITE_CATTS_API_KEY` in `.env`.

Detalle: catts `docs/SESSION_CONTEXT.md` · `docs/CLOUD_AGENTS.md` · `docs/CATREADER_TTS.md`.
