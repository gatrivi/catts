# Navarro Vial — stadium loop (from still frames)

8 AI/still frames → **12 s** forward+reverse loop via **ffmpeg** (no GPU, no LiteUI).

## Contents (from `navarro-vial-stadium-loop.zip` on repo root)

| File | Stage |
|------|-------|
| `frame-01-terreno.png` | Empty site |
| `frame-02-nivelacion.png` | Leveling |
| `frame-03-fundaciones.png` | Foundations |
| `frame-04-gradas-bajas.png` | Low stands |
| `frame-05-estructura.png` | Structure |
| `frame-06-techo.png` | Roof |
| `frame-07-finales.png` | Floodlights / finish |
| `frame-08-estadio.png` | Golden-hour stadium |
| `sequence.json` | Timing + playback order |

Playback: `1→8` (6 s) then `8→1` (6 s). Canvas **1672×941** → export **1920×1080**.

## Build (local)

```powershell
# Unzip from repo root if needed
Expand-Archive -Path E:\zengatrivi-drive-e\catts\navarro-vial-stadium-loop.zip -DestinationPath E:\navarro-vial\stadium-loop -Force
cd E:\navarro-vial\stadium-loop
# copy assemble-stadium-loop.ps1 here from repo after pull
powershell -File assemble-stadium-loop.ps1
```

Requires **ffmpeg** in PATH. Outputs:

- `export/hero-navarro-vial-stadium-loop.mp4` — master (~9 MB, CRF 18)
- `export/hero-navarro-vial-stadium-loop-web.mp4` — web (~5.5 MB, CRF 23)

Poster: `ffmpeg -i export\hero-navarro-vial-stadium-loop-web.mp4 -vframes 1 export\poster-stadium-loop.jpg`

## Site wiring

Copy web mp4 + poster to `navarro-vial-dev/public/videos/hero/` and point `Hero.astro` at the loop (muted, `prefers-reduced-motion` → poster).

## vs stock hero

| | Stock `assemble-hero.ps1` | This loop |
|--|---------------------------|-----------|
| Source | Mixkit clips | 8 graded stills |
| Motion | Real machines | Timelapse cuts / morph steps |
| License | Check ATTRIBUTION | Your frames |
| Drone orbit | No (cuts) | No (dissolve-like via H.264 between holds) |

## Tune

```powershell
$env:FORWARD_SEC = "6"
$env:REVERSE_SEC = "6"
$env:WEB_CRF = "26"   # smaller file
$env:OUT_DIR = "E:\navarro-vial\export"
```
