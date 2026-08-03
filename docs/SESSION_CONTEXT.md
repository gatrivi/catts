# NEVER feed hard-wrapped lines to TTS — unwrap soft breaks first or you get mid-sentence pauses that sound like echo. (`scripts/tts_text_prep.py`)

# CATTS session context (token-cheap)

Last updated: 2026-07-31 (Fish ZLUDA working; Our Fathers ES+EN). Read this instead of re-crawling the repo.

## Goals
1. **Book:** OCR PDF → preprocess → TTS with user voice (EN/ES)
2. **Live:** STT EN/ES → translate → TTS EN/ES, breath/period/comma chunks

## TTS pipeline tiers (binding)
**Topic:** [`docs/TTS_PIPELINE_TIERS.md`](./TTS_PIPELINE_TIERS.md)

| Tier | Engine | Use |
|------|--------|-----|
| Bulk books | **Pocket** (CPU) | Idle overnight; `overnight_books_pocket.py` → `KEEP_*_Pocket` |
| Permanent local short | **Kokoro** | Live clips |
| Showcase only | **VibeVoice** | Prayers / intros — **not** whole books |
| Banned for books | **Edge** | Do not bake albums (needs `CATTS_ALLOW_EDGE_BOOKS=1`) |

Topic: [`docs/TTS_PIPELINE_TIERS.md`](./TTS_PIPELINE_TIERS.md).  
Pocket resume: `scripts/bake_book_pocket_resume.py`. **VV book queue stays STOPPED.**

## Voice clone preference (binding)
**Not zero-shot.** Train hours/days OK. Live *soundbites* need speed; training/audiobooks do not. See `docs/VOICE_CLONE_PREFERENCE.md` + `docs/COMMERCIAL_VOICE_DEPLOYMENT.md`. Target commercial: Chatterbox Multilingual / Qwen3-TTS / GPT-SoVITS on cloud NVIDIA. Stop XTTS tuning.

## Machine
- Ryzen 5 PRO 4650G, RX 6600 8 GB, **16 GB RAM**, tight disk on **C:** — all model caches under `data/` on **E:** (`HF_HOME`, `TORCH_HOME`, etc. via `scripts/_local_cache.py`)
- Cursor ~4 GB; leave headroom for real work (~3 GB). Do **not** leave heavy workers hot after batch.

## Engines (current truth)
| Piece | Status | Notes |
|---|---|---|
| **Pocket (book default)** | **Bake + API** | `CATTS_TTS_ENGINE=pocket`. Albums: `overnight_books_pocket.py`. |
| **Edge** | **Banned for books** | Opt-in only `CATTS_ALLOW_EDGE_BOOKS=1`. Not default. |
| **MeloTTS** | Verified ES preset | Local offline ES; `PUT` engine `melotts`. Sample `/tts/samples/melotts-es.wav`. |
| FastKokoro | Ready `:8880` | EN+ES `ef_dora`. Sample: `/tts/samples/kokoro-es.wav`. Kill when idle. |
| Piper es_MX | Disabled | Legacy only. |
| XTTS | Discarded | CPML + poor quality here. |
| Fish/ZLUDA | **Working + voice-locked** | Root `../fish-speech-zluda`. gfx1032 in HIP Program Files. Cold+warmup ~9 min; warm OF ~2 min. **Must lock one ref wav** or chunks randomize speakers — see `docs/FISH_VOICE_LOCK.md`. Our Fathers: `/static/fish/`. |
| Chatterbox | Installed, **OOM** @16GB | Best clone quality; needs ~8 GB free (kill STT/Cursor). Voice `0b0ad49fcac94af4`. |
| GPT-SoVITS | Next | Train-once; needs worker/NVIDIA. |
| OmniVoice | Missing | — |
| Pocket-TTS | Installed, EN only | Slower than Supertonic. Do **not** use for ES. |
| **Supertonic 3** | **EN prayers live** | ONNX CPU ~2× RT. Pack: `/static/st/*.wav` · short index `/static/z.html`. Hail Mary also `/static/am.wav`. |
| RVC (Fausto/gaston) | **Prep ready** | 18/~28 min @40k; DML venv + pretrained; `data/rvc/gaston/READY.md`. Launch `start_rvc_train_tonight.ps1` → `:7865`. Accent: `ACCENT_CORDOBA.md`. |
| STT / Translate | Ready | Kill STT after batch. |
| OCR | Dual-path | **`docs/OCR.md`** — fast=tesseract; batch=omniroute. Candidate OvisOCR2 = NVIDIA/vLLM only (not this PC). |

## UI (v0.7.6)
`static/index.html` — dark default; tabs About / Books / Voice / Live / STT·Translate / More; ES/EN (default ES). Hard refresh `/`.

## Lift API
`npm start` → uvicorn `:59200` (Edge default, no STT warm unless `CATTS_STT_WARMUP=1`).  
`npm stop` · `npm run stop:heavy` (also Kokoro/STT/XTTS). `npm run health`.  
**Daily cost (Edge lean):** ~50–150 MB RAM idle; TTS is cloud (no GPU). Electricity ≈ noise vs PC-on. Auto boot: Startup `CatTS-CloudRemote.cmd` / `start_remote_stack.ps1`.

## Phone apps (no Termius URL hell)
Topic crib: **`docs/PHONE_STACK.md`**. `.\scripts\start_reader_stack.ps1` once:
- **Books:** http://100.87.252.18:3002 (CatReader — `:3000` often stolen; stack auto-picks)
- **Prayers:** http://100.87.252.18:3001 (Rosario)
- **API:** http://100.87.252.18:59200 · `GET /books` → 9 KEEP albums  
- **Panza TTS client:** `C:\zengatrivi\REACTJS\panza-encuentra-perro\src\lib\catts.ts` (`VITE_CATTS_URL`)  
Cassian cassette → `KEEP_Cassian_Conferences` (23 ch). **Phone zip DL:** http://100.87.252.18:59200/static/ab.html  
**Prod** `catreader.gatrivi.com` still missing `cattsBookId` + needs Funnel HTTPS (enable at login.tailscale.com/f/funnel).

## Slack API down alerts
**Not** Cursor Slack (`@cursor`). Needs Incoming Webhook → `CATTS_SLACK_WEBHOOK_URL` in `.env`.  
`npm run watch:slack` · auto with `start_remote_stack.ps1` when webhook set. Script: `scripts/watch_api_slack.ps1`.

## Cloud Agents (web / phone — no Termius)
**My Machines** worker on this PC. Topic: **`docs/CLOUD_AGENTS.md`**.  
**Voice hub (hold-to-talk):** [`docs/PHONE_VOICE_HUB.md`](./PHONE_VOICE_HUB.md) · `http://100.87.252.18:59200/static/talk.html`  
Start: `.\scripts\start_remote_stack.ps1` → API + multi workers (`catbox-catts` / `catbox-rosario` / `catbox-catreader`, alias `catboxprime`).  
UI: https://cursor.com/agents → pick worker / repo. Tools run here (TTS/E:).  
Boot: Startup `CatTS-CloudRemote.cmd` + task `CatTS-CloudRemoteStack` (logon). AC sleep off. Smoke: `data/cloud_agents/remote_smoke.wav`.

## Switch TTS without .env
UI Live tab → engine dropdown, or `PUT /tts/engine` `{"engine":"fish"}`. Docs: `TTS_ENGINE_SWITCH.md`.

## External apps (readings / audiobooks)
`POST /tts/speak` · `POST /jobs/audiobook` on `:59200` — `docs/EXTERNAL_TTS.md`.  
ES books/readings: default **edge** (HQ LatAm). Local: `PUT /tts/engine` `{"engine":"melotts"}`. Clone HQ: `chatterbox` only with free RAM. Samples: `/tts/samples`. **API key off** (`api/deps.py` no-op; re-enable before LAN).
Regen ñ/tildes comparison: `.\.venv\Scripts\python.exe scripts\regen_es_comparison_samples.py`  
Phrase in `data/tts_tests/comparison_text.txt`. Ready: **edge** (live), kokoro, melotts; chatterbox when RAM free.

## Audio Engine (manifest v1) — CatTS producer
Spec `CAT_AUDIO_ENGINE_SPEC.md`. Topic: **`docs/AUDIO_ENGINE.md`**.  
`contracts/` + `generator/` + `fixtures/` + `scripts/generate_audio_work.py`.  
SPA tab **Oraciones** · `GET /works` · files `/works-files/audio/...` · ES rosary pack: `ave-maria`, `decena-ave`, `rosario-core-es`, `rosario-apertura-cierre-es`, `rosario-misterios-es` (20), `rosario-cierre-extra-es` (LL+Papa).
Sample still **falta**: `chatterbox-latam-v3` (OOM @16GB — skip unless RAM free).
NarrationDocument → MP3 + cues/VTT + `AudioManifestV1` (incremental, immutable URLs). TS player packages = later / apps.
UI: `CATTS_API_KEY` blank → no auth locally. Set only for LAN/Tailscale. Auth also no-op in `api/deps.py`.

## Abogen (Kokoro GUI / WebUI)
**Rosary album RE-RENDER overnight:** full text per track, title stripped from body (no double-speak), empty titles not spoken. Script `run_abogen_rosary_album.py`; log `data/abogen/rosary_album_rerender.log`; pid `rosary_album.pid`. Out → `KEEP_…/album/`.

## CatReader / external TTS
`docs/CATREADER_TTS.md` — key **`catts-local`**, `GET /books` + chapter audio/srt, `POST /tts/speak`. API `:59200` up.
```powershell
.\scripts\start_kokoro.ps1   # :8880 EN + ES (fastkokoro ONNX)
.\.venv\Scripts\python.exe scripts\_tts_onnx_smoke.py
```
DirectML bonus: stop servers, `pip install onnxruntime-directml`, `FASTKOKORO_ONNX_AUTO_PROVIDERS=true` in `start_kokoro.ps1`.


## After batch / free RAM
`docs/HEAVY_PROCESSES.md`. Kill heavy leftovers.  
After Cassian bake-off: `npm run stop:heavy` (Kokoro if it was up). Pocket is in-process only.

## Budget
Read `SESSION_CONTEXT` + one topic doc (`OCR.md`, etc.). No repo crawls. Warn before 500k+ tokens. No PR noise; push when asked.

## Free LLM gateways (2026-07-08)
- **React / other apps (hosted, one key):** [OpenRouter](https://openrouter.ai) free models (`*:free` / `openrouter/free`). CORS OK; still proxy keys in prod.
- **CATTS local hub (npm):** [OmniRoute](https://omniroute.online) `localhost:20128/v1` — stacks 90+ free tiers + NVIDIA/Cerebras/etc, auto-fallback. Alt lighter: FreeLLMAPI `:3001`.
- **Skip for us:** Kimchi = Cast AI enterprise, not free-tier aggregator.
- **Direct providers:** NVIDIA NIM / Mistral / Groq = good upstreams *into* OmniRoute; alone they burst. NIM no browser CORS.
- Book OCR cleanup/translate: batch via CATTS→OmniRoute (long context). Live React cleanup: OpenRouter free first.

## LLM hub for other apps (notes, etc.)
- **Notes UI** owns tidy/summarize/thumb prompts — not CATTS.
- **CATTS role:** run OmniRoute (or fall back OpenRouter) and expose OpenAI-compat `POST /v1/chat/completions` (+ optional `/v1/models`) on `:59200`, auth with `CATTS_API_KEY`. Phone/PC via Tailscale.
- Keys stay on CATTS box; notes only needs `baseURL=http://<tailscale-catts>:59200/v1` + CATTS key.

## Bonsai (local LLM) — 4B on E: (2026-07-26)
`external/Bonsai-demo` **real on E:** (moved off D:). Backend **Vulkan / RX 6600** (HIP zip has no exes). Live `:8080` with `-c 4096 -np 1 --device Vulkan1`. Smoke ~110 tok/s. Kill when idle. Topic: **`docs/BONSAI.md`**.

## Disk (2026-07-29)
**C: must stay ≥10 GB free.** CatTS caches on **E:** only (`scripts/_local_cache.py` → `HF_HOME`, `SUPERTONIC_CACHE_DIR`, `TORCH_HOME`).  
Tonight: freed ~1 GB by deleting C: `~/.cache/{huggingface,supertonic3}` (dupes). Edge overnight rewrite floods C: temp — **stopped**. Prefer Supertonic/Kokoro/Pocket local for new audio; Edge only with C: headroom.

## Task queue (2026-07-28 handoff)
1. **DONE Cassian full Edge album:** 23 tracks `KEEP_Cassian_Conferences` (skip Conf 12/22). CatReader cassette. Script `build_cassian_album.py --part 1|2`.
2. **DONE VV rosary 4 mystery-set folders:** `books/vv_rosary/` + `/static/rosary_vv_4sets.zip` · `build_vv_rosary_4sets.py`.
3. **DONE Liber AUTO fixes (Rosario):** EN guide text on AUTO, stop/ref race, AUTO_SKIP, glass chrome, gloriosos→MGl*, WAV error≠ended. Topic: `rosario-cards-v1/.docs/libro/voice-autoplay.md`. **Open:** Liber ▶ not on `/rosario` bead view; LL/Papa still skip-delay.
4. **DONE phone stack scripts:** `start_reader_stack.ps1` · `start_remote_stack.ps1` (My Machines `catboxprime`) · `sync_rosario_voice.ps1`.
5. **Deleted earlier:** Secret of the Rosary KEEP album + Salzmann KEEP (user request). Decade/prayer packs kept.
6. **STOPPED VV chapter albums (user 2026-07-28, confirmed 2026-07-29):** Cassian → Core → Right → Salzmann → Nicoll. **Do not resume** for bulk library — use Edge (`bake_book_edge_resume.py`). VV = showcase/prayers only. See `TTS_PIPELINE_TIERS.md`.
7. **Three-tier + bake-off (2026-07-29):** Edge bulk · Kokoro/Pocket/Supertonic local · VV showcase.
8. **EN rosary Supertonic** + **ES rosary+LOH DONE** (`overnight_es_rosary_loh.py`). `/static/es/` + `/static/loh/2026-07-29/`.
9. **Books Edge overnight (2026-07-29):** `overnight_books_edge.py` — TEMP on E:`data/tmp_edge`, abort if C:<8GB. Queue: Core → Right → Reality → Nicoll. **Prep:** `prep_book_tts.py` strips running headers + heals mid-word PDF spaces before Edge (hash change → re-synth).
10. **Cathedral:** `:3002` · TTS→CatTS `/tts/speak`. Phone `http://100.87.252.18:3002`.
8. **Letanía Sangre VV EN clips on disk** (`LPB_*.wav` + `static/letania_sangre.zip`) — Liber EN-only when glass shows EN. Loreto `LL_*` VV = prayer showcase lane.

## Handoff crib (phone)
| App | URL |
|---|---|
| CatReader (books) | http://100.87.252.18:3000 |
| Rosario (prayers) | http://100.87.252.18:3001 |
| CatTS API | http://100.87.252.18:59200 |
| Cloud agents | https://cursor.com/agents → **catboxprime** |

Python: `.\.venv\Scripts\python.exe` only. Auth gate off locally.

## Rioplatense @ VibeVoice quality (2026-07-25 research)
**Verdict: no off-the-shelf model matches VibeVoice quality *and* true Rioplatense.** We make one.

| Candidate | Gap |
|---|---|
| VibeVoice TTS | EN/ZH strong; ES experimental only — not Rioplatense. Community LoRA fine-tune exists → viable *base* to train. |
| `franclarke/chatterbox-es-ar` | **Best existing AR accent LoRA** (Orpheus LATAM-AR). Cached under HF hub. Quality ≈ Chatterbox, **below** VibeVoice long-form bar; OOM @16GB here. |
| UNRN XTTS-AR / MMS-AR / F5-ES | Accent OK-ish; quality/license not VibeVoice-class (XTTS already discarded). |
| Edge `es-AR-TomasNeural` | Usable LatAm/AR interim — not VibeVoice tier. |
| SpeechGen Abegail/Tomas | Cloud proprietary Rioplatense — not ours. |

**Path to make it:** (1) cloud NVIDIA, (2) multi-speaker pretrain on `Kukedlc/arg-spanish-tts` (~12h AR) **or** VibeVoice LoRA on that set, (3) fine-tune on Córdoba corpus (`data/rvc/gaston`, ~28 min → aim 45–60). Prefer **VibeVoice LoRA** if we keep VV as quality floor; else **Chatterbox-es-ar → further SoVITS/Chatterbox train** on gaston. RVC alone ≠ accent.

## Train / AR accents vs this rig (2026-07-26)
**Cannot train VV-class on RX6600/16GB.** VV LoRA ≥16 GB **NVIDIA**; CosyVoice3 LoRA ~24 GB; Chatterbox already OOM here. AR off-shelf (`chatterbox-es-ar`, Orpheus Rioplatense, Qwen3 AR refs) < VV long-form → **do not train those for “VV qual” goal.**

**Go for Rioplatense @ ≤$5 (user 2026-07-26):** only **VibeVoice 1.5B LoRA** on AR data (same quality floor). Free first: Colab T4 + [sruckh/VibeVoice-finetune-easy](https://github.com/sruckh/VibeVoice-finetune-easy) notebook, checkpoints→Drive (session kills risk). Failover: Vast/RunPod 4090 ~$0.27–0.40/hr → **~$1–5** for a full LoRA run. Data: `Kukedlc/arg-spanish-tts` / Orpheus LATAM-AR (+ optional gaston). Local = inference only after download. GH [#10](https://github.com/gatrivi/catts/issues/10) = Qwen3 Colab smoke (≠ VV train).

## Hail Mary A/B + Bonsai after audio
- **Ready:** Edge Tomas ES smoke → `static/samples/hail_mary_edge_tomas.wav` (+ older `hail_mary_B_edge_*`)
- Chatterbox OOM skipped @16GB.

## Cassian audiobook (2026-07-24)
Part I album script: `build_cassian_album.py` (CCEL — footnotes/wrap issues). **Conf 1 better path:** `scripts/build_cassian_conf1.py` ← New Advent HTML, linted, Andrew voice −8%, replaces album track 02. Clean text: `data/books/cassian_conf1_clean.txt`. Phone: `…/static/listen-cassian.html` · book `KEEP_Cassian_Conferences`.

## Phone / omp
Termius → SSH Tailscale → `omp.exe` (not `omp.sh`). Crib: **`docs/OMP_MOVIL.md`**. LM Studio detail: `docs/LMSTUDIO_PHONE.md`.
**Termius URL wrap:** bookmark `http://100.87.252.18:59200/static/z.html` (short aliases `am/d/a/m/o/c` — see `AUDIO_ENGINE.md` § Phone). Never `127.0.0.1` from phone.
