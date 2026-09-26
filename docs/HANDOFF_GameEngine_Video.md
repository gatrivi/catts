# Handoff — Game Engine + Navarro Vial Video (local work)

**Date:** 2026-08-02  
**CATTS version:** `v0.7` (unchanged — no code touched)  
**Status:** planning only; docs written, no implementation started

---

## 1) Two parallel tracks (do NOT mix with CatTS runtime)

| Track | Goal | Where to work |
|-------|------|---------------|
| **A — Retro game engine** | Small games, pre-rendered look (AoE2, DKC2, Metroid, LTTP…) | New folder, e.g. `E:\game-engine\` or repo subfolder `game/` later |
| **B — Navarro Vial hero video** | 10–12 s website hero, construction → stadium → reverse | New folder, e.g. `E:\navarro-vial\` |

**CatTS stays at:** `e:\zengatrivi-drive-e\catts` — port `59200`, Kokoro `8880`, worker `59201`.  
**Rule:** never run CatTS + ComfyUI/Blender heavy jobs at the same time (16 GB RAM).

---

## 2) Hardware (user rig)

| Spec | Value |
|------|-------|
| OS | Windows |
| CPU | Ryzen 5 |
| GPU | RX 6600 (8 GB VRAM) |
| RAM | 16 GB |
| Budget for CatTS while interpreting | ~30–40% system; CatTS should not exceed 50–60% |

**Verdict:** rig is enough for both tracks with correct **method**, not one-shot AI video.

---

## 3) Track A — Game engine

### Core stack (Frank's Laboratory × 3)

| Pillar | Course | Role |
|--------|--------|------|
| **JS Engine** | [Build a Reusable 2D Game Engine](https://www.udemy.com/course/build-a-reusable-2d-game-engine-in-javascript/) | Core: loop, scenes, sprites, assets, input, UI |
| **Pixel Rain** | [Pixels, Particles & Physics](https://www.udemy.com/course/learn-html-canvas-pixels-particles-physics/) | VFX, transitions, image→particles |
| **Music Visualizer** | [Audio Crash Course (YT)](https://www.youtube.com/watch?v=VXWvfrmpapI) | Web Audio + FFT, reactive menus/boss |

Full reference: **`docs/GAME_ENGINE_REFERENCE.md`** (PR #19).

### Visual targets (inspiration DNA)

| Game | Steal |
|------|-------|
| AoE2 / RA2 | 3D→isometric prerender, team-color swap, damage states |
| DKC2 | Prerender + 4–6 parallax layers |
| MMX5 / PS1 | Prerender BG + sprite hero, depth desaturation |
| Super Metroid | Room graph, doors, zone palettes |
| LTTP | 16×16 tiles, 3 layers (floor/obj/overhead) |

### Asset pipeline (local)

```
Blender (low-poly, batch ortho/isometric render)
  → ComfyUI + DirectML (SD 1.5, textures/polish, 512²)
  → spritesheets (Aseprite or script)
  → Frank JS Engine asset loader
  → optional display shader per “era”
```

### brickboy (GB display QA only)

- App: https://sonohoka.sakura.ne.jp/brickboy/
- Methodology article: https://note.com/kathoc/n/n5ceb773a3dbc  
- Use for 160×144 games; steal “measure hardware → bake texture → multiply not add” for PS1/SNES shaders.

### Pending (user action)

- [ ] Copy course final code → `vendor/franks-lab/{engine,pixel-rain,visualizer}/`
- [ ] Pick first game style (isometric vs platformer vs top-down)
- [ ] Define spritesheet naming + resolution
- [ ] More inspiration refs when ready

### LiteUI in CatTS repo (optional image/video workstation)

CatTS already has LiteUI integration (`docs/HANDOFF_LiteUI_Integration.md`):
- `external/LiteUI-Studio/` — ComfyUI on `8188`, Gradio on `7860`
- **For game assets:** use LiteUI/ComfyUI for stills/textures, not full engine
- **Do not** use cloud agent for GPU generation (burns tokens; no user GPU)

---

## 4) Track B — Navarro Vial hero video

### Brief (frozen)

- **Client:** Navarro Vial — Argentine earthmoving / heavy equipment
- **Format:** 16:9, 10–12 s, muted, premium commercial
- **Palette:** near-black, charcoal, warm amber/gold
- **Composition:** left 35% dark negative space for web text; action center-right
- **Act 1:** empty GBA construction site at dawn → timelapse (excavator, loaders, trucks, dozer, grader, roller) → generic modern football stadium at golden hour; hold 1 s
- **Act 2:** perfect temporal reverse to empty field
- **Camera:** one smooth elevated drone orbit, no cuts
- **Forbidden:** logos, flags, readable text, named stadium, disasters, warped machines, cuts, flicker

### What does NOT work

| Approach | Why |
|----------|-----|
| Cloud agent generates video | No GPU, no video models |
| One-shot local AI video prompt | Inconsistent machines, no perfect reverse, not “premium” |
| Running alongside heavy CatTS jobs | RAM/VRAM contention |

### What DOES work on user PC

| Approach | Tool | Notes |
|----------|------|-------|
| **Recommended** | Stock construction footage + **DaVinci Resolve** (free) | Grade, crop for 35% left space, reverse clip for act 2 |
| **Higher craft** | **Blender** timelapse | Low-poly site + stadium; user GPU OK |
| **Assist only** | ComfyUI / LiteUI | Mood stills, not full video |

### Resolve workflow (minimal)

1. Import forward timelapse (~5–6 s)
2. Color: lift shadows to charcoal, highlights amber/gold
3. Crop/reframe: action center-right; darken left 35% (power window or matte)
4. Hold final stadium frame 1 s
5. Duplicate clip → **Reverse Speed** 100% for second half
6. Export H.264, 16:9, no audio

### Pending (user action)

- [ ] Choose: stock vs Blender
- [ ] Source clips (Pexels: construction, excavator, stadium build) or model in Blender
- [ ] Resolve project in `E:\navarro-vial\`
- [ ] Export for web (target ~1080p or 4K per site spec)

---

## 5) Resource cheat sheet (one heavy job at a time)

| Task | RAM | VRAM |
|------|-----|------|
| CatTS API + Kokoro | 4–8 GB | 0–2 GB |
| Frank engine (browser) | 2–4 GB | 0 |
| Blender render | 4–8 GB | 4–6 GB |
| ComfyUI SD 1.5 | 8–12 GB | 6–8 GB |
| DaVinci Resolve | 8 GB | 0 |

---

## 6) Docs index

| File | Content |
|------|---------|
| `docs/GAME_ENGINE_REFERENCE.md` | Frank's Lab 3 pillars, pipeline, checklists |
| `docs/HANDOFF_LiteUI_Integration.md` | CatTS ↔ LiteUI ComfyUI |
| `docs/HANDOFF_GameEngine_Video.md` | **this file** |
| `docs/CONTEXT.md` | CatTS audiobook/voice (unchanged) |

---

## 7) Clarifications from conversation

- User **can** reach AoE2/DKC2/PS1 **asset quality** locally; bottleneck is pipeline discipline, not hardware.
- User **can** make the Navarro Vial video locally; bottleneck is **editing/3D/stock**, not RX 6600.
- Cloud agent: docs + code only; **no** video generation, **no** ComfyUI runs.

---

## 8) Suggested next session

1. User drops Frank course code into `vendor/franks-lab/` **or** starts Navarro Vial Resolve project.
2. If games: scaffold `game/` with engine skeleton from Udemy course.
3. If video: deliver storyboard frames + Resolve step list (already outlined above).

**Branch with game docs:** `cursor/franks-lab-game-engine-docs-b582` → PR #19
