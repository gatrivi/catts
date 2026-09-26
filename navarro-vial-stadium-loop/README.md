# Navarro Vial — stadium loop (8 frames → 12s animation)

**No GPU. No LiteUI.** Solo los PNG del zip + Python/ffmpeg (crossfade).

## Ya generado en repo (tras pull)

Tras merge/pull, en `navarro-vial-stadium-loop/export/`:

| Archivo | Uso |
|---------|-----|
| `hero-navarro-vial-stadium-loop-web.mp4` | Sitio web (~6 MB, 12 s) |
| `hero-navarro-vial-stadium-loop.mp4` | Master |
| `poster-stadium-complete.jpg` | Poster estadio terminado |
| `poster-stadium-loop.jpg` | Poster primer frame del clip |

## Regenerar local

```powershell
cd E:\zengatrivi-drive-e\catts
Expand-Archive navarro-vial-stadium-loop.zip -DestinationPath navarro-vial-stadium-loop -Force
python navarro-vial-stadium-loop\assemble_stadium_loop.py
```

Requiere: **Python 3**, **ffmpeg** en PATH.

## Copiar al sitio

```powershell
$src = E:\zengatrivi-drive-e\catts\navarro-vial-stadium-loop\export
$dst = E:\navarro-vial-dev\public\videos\hero
Copy-Item $src\hero-navarro-vial-stadium-loop-web.mp4 $dst\hero.mp4 -Force
Copy-Item $src\poster-stadium-complete.jpg $dst\poster.jpg -Force
```

## Animación

- Orden: `1→8` (6 s) luego `8→1` (6 s)
- Transición: **crossfade 0.45 s** entre frames (timelapse suave)
- Export: 1920×1080, muted

## Ajustes

```powershell
$env:FADE_SEC = "0.6"      # más morph
$env:WEB_CRF = "26"        # archivo más chico
$env:OUT_DIR = "E:\navarro-vial\export"
python navarro-vial-stadium-loop\assemble_stadium_loop.py
```

## Fuente

Frames en `navarro-vial-stadium-loop.zip` (master). Generados con IA/imagen local — no vídeo IA.
