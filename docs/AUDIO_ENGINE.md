# Audio Engine (CatTS producer)

Spec: `CAT_AUDIO_ENGINE_SPEC.md` v1. CatTS owns **generation + contracts**; apps own UI + TS player.

## CatTS map (audit)

| Existing | Role vs spec |
|---|---|
| `POST /jobs/audiobook` + `services/job_runner.py` | Legacy book pipeline (chapters.json → mp3 zip/m4b). No manifest v1 / locators. |
| `GET /books/.../chapters/N/audio\|subtitles` | Album folders mp3+srt for CatReader. SRT cues = chapter-local; **no SourceRange**. |
| `POST /tts/speak` | Live / ad-hoc TTS — not for app playback of prebuilt works. |
| **New** `contracts/` + `generator/` | NarrationDocument → immutable MP3 + cues/VTT + AudioManifestV1. |

## Layout

```
contracts/          # JSON Schema + .d.ts
fixtures/           # prayer-brief, prayer-repeated, chapter-locators
generator/          # Python models, hash, build, validate
scripts/generate_audio_work.py
scripts/validate_audio_manifest.py
```

## CLI

```powershell
.\.venv\Scripts\python.exe scripts\validate_audio_manifest.py --kind narration fixtures\prayer-brief\narration.json
.\.venv\Scripts\python.exe scripts\generate_audio_work.py fixtures\prayer-brief\narration.json --dry-run
.\.venv\Scripts\python.exe scripts\generate_audio_work.py fixtures\prayer-brief\narration.json -o data\audio_works
```

Out: `data/audio_works/audio/<workId>/<assetId>.<rev>.mp3` + `.cues.json` + `.vtt` + `manifest.<rev>.json` + `manifest.json`.

SPA: tab **Oraciones** → `GET /works` → Play queues first chapter. Files at `/works-files/audio/...`.

## Prayer base (ES, Edge Tomas)

| Work | Assets | Notes |
|---|---|---|
| `ave-maria` | 1 | single prayer |
| `decena-ave` | 1 | chapter lists A×10 → same file |
| `rosario-core-es` | 5 (SC,P,A,G,F) | chapters: núcleo + decena |
| `rosario-apertura-cierre-es` | 3 (AC,C,S) | Contrición, Credo, Salve |
| `rosario-misterios-es` | 20 | goz/dol/glo/luz contemplative lines |
| `rosario-cierre-extra-es` | 2 (LL,Papa) | Letanía completa + oración Papa |

```powershell
.\.venv\Scripts\python.exe scripts\generate_audio_work.py fixtures\prayer-core\narration.json -o data\audio_works
.\.venv\Scripts\python.exe scripts\generate_audio_work.py fixtures\prayer-apertura-cierre\narration.json -o data\audio_works
.\.venv\Scripts\python.exe scripts\generate_audio_work.py fixtures\prayer-misterios\narration.json -o data\audio_works
.\.venv\Scripts\python.exe scripts\generate_audio_work.py fixtures\prayer-cierre-extra\narration.json -o data\audio_works
```

Rosary ES pack complete (core + apertura/cierre + misterios + letanía/Papa).

- **prayer/devotion:** one MP3 per unique block; chapter `assetIds` may repeat (×10 Ave → 1 file).
- **book:** one MP3 per chapter (blocks concatenated).
- Incremental: same speech+voice+`GENERATOR_VERSION` → skip TTS.
- Atomic: write revisioned manifest, then replace `manifest.json`.

## Not in this slice

- `packages/audio-engine` (TS player) — apps / later phase.
- Wiring Cathedral/Rosario/CatReader adapters.
- Replacing legacy `/books` album API (keep until CatReader migrates to manifest).

## Phone / Termius (short URLs)

Long paths wrap in Termius and jam paste. **One bookmark:**

`http://100.87.252.18:59200/static/z.html`

| short | file |
|---|---|
| `/static/z.html` | pack index |
| `/static/am.wav` | Hail Mary |
| `/static/d.html` | decade player |
| `/static/d.zip` | decade+mystery |
| `/static/a.zip` | Ángelus |
| `/static/m.zip` | Magnificat |
| `/static/o.zip` | Ofrendas |
| `/static/c.zip` | Corona Sangre |
| `/static/r.zip` | Rosary open/close |
| `/static/dm.zip` | Divine Mercy |
| `/static/vc.zip` | Vía Crucis |
| `/static/vl.zip` | Vía Lucis |

Never paste `127.0.0.1` from phone (that's the phone). Use Tailscale `100.87.252.18`.

## Rosario Cards devotion packs (VibeVoice Carter EN)

Bundled clips under rosario `public/voice/en/` + `BUNDLED_VOICE_BY_ID`. ES text on screen, EN audio. Building smallest-first.

| Devotion | Clips | ZIP (long) | short |
|---|---|---|---|
| Decade (Joyful 1) | MG1,P,A×10,G,F | `/voice/en/decade.zip` · `/static/dec.zip` | `d.zip` |
| **Ángelus** | ANG_* + Ave→A | `/voice/en/angelus.zip` · `/static/angelus.zip` | `a.zip` |
| **Magnificat** | MAG_1..7; SC→ANG_SC; DOX→G | `/voice/en/magnificat.zip` · `/static/magnificat.zip` | `m.zip` |
| **Siete Ofrendas** | SC + PBO_1..7 | `/voice/en/ofrendas.zip` · `/static/ofrendas.zip` | `o.zip` |
| **Corona Sangre** | PBContrition, PB, PBClosing; PB_P→P; PB_G→G | `/voice/en/corona_sangre.zip` · `/static/corona_sangre.zip` | `c.zip` |

Render: `vibevoice-cli tts --voice voice-en-Carter_man.gguf` per unique block. Chaplet step ids `${base}_${idx}` strip to base. ZIP m3u expands full 7-shedding chaplet from 5 WAVs. Next: Letanía Sangre (many verses) or Vía Crucis.

## Decade EN (VibeVoice Carter) — navigable tracks

One decade = **12 separate files** (player can skip/seek per prayer). Not one blob.

| # | file | prayer |
|---|---|---|
| 01 | `static/d/01.wav` | Our Father |
| 02–11 | `static/d/02.wav` … `11.wav` | Hail Mary 1–10 (same Carter take) |
| 12 | `static/d/12.wav` | Glory Be |

- **Phone UI:** `/static/listen-decade.html` — tap prayer, auto-next.
- **Playlist:** `/static/d/decade.m3u` (VLC / audiobook apps).
- **ZIP (mystery+decade):** `/static/dec.zip` · Rosario Estudio de voz → **Descargar decade EN + misterio** → `/voice/en/decade.zip`
  - `01` Annunciation · `02` Our Father · `03–12` Hail Mary ×10 · `13` Glory · `14` Fatima
- **Short single bead:** `/static/am.wav` (Hail Mary only).
- **Concat blob (legacy):** `/static/dec.wav` — avoid for navigation.
- Voice: `voice-en-Carter_man` · text EN (do not mix ES text + EN voice).
- **Rosario Cards:** Liber ▶ plays these via `public/voice/en/{P,A,G,F}.wav` + `BUNDLED_VOICE_BY_ID` (same A reused per Ave step; auto-next = decade navigation).
- Rebuild parts: `vibevoice.cpp/out/decade/{of,gb}.wav` + `static/am.wav` → copy into `static/d/` and rosario `public/voice/en/`.

Tailscale: `http://100.87.252.18:59200/static/listen-decade.html`

## Status

Phase 1 contracts + Phase 3 generator: **done** (2026-07-21). Phase 2/4–6: other repos.
Decade VV EN tracks: **done** (2026-07-26).
