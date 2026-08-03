# Cloud Agents from phone/web (no Termius)

**Goal:** kick audiobook / TTS prayer jobs from [cursor.com/agents](https://cursor.com/agents) while the home PC (`catboxprime`) does the work.

## How it works

**My Machines** worker on this Windows box. Agent loop = Cursor cloud; **shell/edits/TTS run here** (E: models, `:59200`, VibeVoice paths). No inbound ports.

| Piece | Command / URL |
|---|---|
| Start stack | `.\scripts\start_remote_stack.ps1` |
| API | `http://127.0.0.1:59200` · Tailscale `http://100.87.252.18:59200` |
| Worker name | `catboxprime` |
| Web UI | https://cursor.com/agents → env dropdown → **catboxprime** |
| Logs | `data/cloud_agents/` |

## Before you leave

1. PC plugged in, Tailscale Running, lid OK to close if sleep-on-lid is off (stack sets AC sleep/hibernate = 0).
2. Run once: `.\scripts\start_remote_stack.ps1`
3. Confirm API: `npm run health` or open `/health`
4. On phone: open agents → select **catbox-catts** / **catbox-rosario** / **catbox-catreader** (alias **catboxprime** → catts)
5. **Voice hub:** http://100.87.252.18:59200/static/talk.html — docs `PHONE_VOICE_HUB.md`. Multi workers: `.\scripts\start_cloud_workers.ps1`

## Prompt crib (paste into cloud agent)

```
Read docs/SESSION_CONTEXT.md then docs/AUDIO_ENGINE.md (or EXTERNAL_TTS.md).
Use local CatTS API http://127.0.0.1:59200 (already on this machine).
Engine default: edge (ES HQ). For VV library jobs follow SESSION_CONTEXT task queue.
Do not leave heavy workers hot after batch — docs/HEAVY_PROCESSES.md.
Prefer .\.venv\Scripts\python.exe. No PR unless asked.
```

### Example tasks

- **Prayer clip:** `POST /tts/speak` lang=es via curl, or `scripts/generate_audio_work.py` for Oraciones pack.
- **Audiobook chapter:** existing `scripts/build_*.py` / `build_vv_chapters.py` — check SESSION_CONTEXT queue.
- **Engine switch:** `PUT /tts/engine` `{"engine":"edge"}` (or melotts / fish when RAM free).

## Auth / secrets

- Local auth gate is **off** (`api/deps.py` no-op). Fine while worker is on-box only.
- Do **not** paste `.env` into chat. Cloud Secrets tab only if you later use managed VMs + Tailscale.

## Restart after reboot

```powershell
cd E:\zengatrivi-drive-e\catts
.\scripts\start_remote_stack.ps1
```

Optional: Task Scheduler → At log on → that script (user left one registered if setup succeeded).

## Failures

| Symptom | Fix |
|---|---|
| Machine missing in agents UI | `agent worker debug`; re-run `start_cloud_worker.ps1`; confirm `agent login` |
| TTS fails | API down → `start_api.ps1`; Edge needs net |
| OOM / chatterbox | Kill STT/Cursor extras; use edge/melotts |
| Wrong repo | Worker must start in `gatrivi/catts` checkout |

## Out of scope (on purpose)

- Enterprise Self-Hosted **Pool** (needs team plan).
- Managed Cloud Agent + Tailscale userspace (extra dashboard secrets) — only if My Machines dies.
