# Game Engine — Reference Doc (v0.1)

> **Status:** planning / pre-implementation  
> **Hardware:** Windows, Ryzen 5, RX 6600 (8 GB VRAM), 16 GB RAM  
> **Stack core:** Frank's Laboratory × 3 cursos + pipeline assets retro

---

## 1. Frank's Laboratory

| Campo | Valor |
|-------|-------|
| **Autor** | Frank Dvorak |
| **Marca** | Frank's Laboratory |
| **YouTube** | https://www.youtube.com/c/Frankslaboratory |
| **CodePen** | https://codepen.io/franksLaboratory |
| **Assets** | https://www.frankslaboratory.co.uk/downloads/ |
| **Filosofía** | Vanilla JS + HTML5 Canvas. Sin frameworks ni librerías. Código línea a línea. |

**Otros cursos útiles (no core):**
- *Learn Game Development with JavaScript* — 9 proyectos → juego final (sprites, parallax, colisiones, state pattern). freeCodeCamp ~10 h.
- *Learn Creative Coding with Vanilla JavaScript* — fractal rain, OOP, canvas transforms.
- *Remake Retro Games with JavaScript* — relevancia directa para Metroid/Zelda/GB.

---

## 2. Los 3 pilares del proyecto

### A) Pixel Rain — *Learn HTML Canvas: Pixels, Particles & Physics*

| | |
|---|---|
| **Udemy** | https://www.udemy.com/course/learn-html-canvas-pixels-particles-physics/ |
| **YouTube (preview)** | https://www.youtube.com/watch?v=vAJEHf92tV0 (~1h17) |
| **Duración** | ~2h15, 35 lecciones |

**Qué enseña:**
- Canvas 2D: rectángulos, `drawImage`, centrado
- **Particle systems** con clases JS
- `getImageData` → extraer coords + color por píxel
- Imagen → partículas con física (friction, easing)
- Reacción al mouse; desensamblar/reensamblar imagen (4 modos)
- Transiciones animadas entre estados de partículas

**Rol en nuestro engine:**
| Uso | Ejemplo |
|-----|---------|
| Transiciones de escena | Logo → partículas → nivel |
| Efectos de muerte/impacto | Sprite prerender → explosión de píxeles |
| Preview de assets | ComfyUI/Blender export → animación de reveal |
| UI retro | Menús que “materializan” desde imagen |

**APIs clave:** `CanvasRenderingContext2D`, `getImageData`, `putImageData`, clases `Particle` / `Effect`.

---

### B) Music Visualizer — *JavaScript Audio CRASH COURSE*

| | |
|---|---|
| **YouTube** | https://www.youtube.com/watch?v=VXWvfrmpapI (~1h) |

**Qué enseña:**
- Reproducir audio (`<audio>`, eventos media, base64)
- **Web Audio API:** `AudioContext`, osciladores, generación procedural
- **AnalyserNode + FFT** → `getByteFrequencyData`
- Visualizadores: barras, círculos, color animado a música
- Cargar archivos largos en analyser

**Rol en nuestro engine:**
| Uso | Ejemplo |
|-----|---------|
| Menús / pausa | Visualizer de fondo |
| Boss fights | UI reactiva al OST |
| Debug audio | Verificar stems exportados |
| Ambiente | Sala con “respiración” visual al track |

**APIs clave:** `AudioContext`, `AnalyserNode`, `fftSize`, `frequencyBinCount`.

---

### C) JS Engine — *Build a Reusable 2D Game Engine in JavaScript*

| | |
|---|---|
| **Udemy** | https://www.udemy.com/course/build-a-reusable-2d-game-engine-in-javascript/ |
| **Duración** | ~1h42 |

**Qué enseña (sistemas del engine):**
| Sistema | Función |
|---------|---------|
| Game loop | `requestAnimationFrame`, delta time |
| Renderer | Canvas 2D |
| Sprite animation | Estados + frames |
| Asset loader | Async: imágenes, audio, JSON |
| Input manager | Teclado, mouse, touch |
| Scene/state manager | Menú → juego → pausa |
| UI layer | Desacoplado de game logic |
| Arquitectura | Data-driven, reutilizable |

**Rol en nuestro engine:** **esqueleto principal**. Todos los mini-juegos (AoE2-style, DKC2-style, Metroid, LTTP) corren sobre este framework.

---

## 3. Cómo encajan los 3 pilares

```
┌─────────────────────────────────────────────────────────┐
│  JS ENGINE (core)                                       │
│  loop · scenes · input · assets · sprites · UI          │
├─────────────────────────────────────────────────────────┤
│  PIXEL RAIN          │  MUSIC VISUALIZER                │
│  VFX / transiciones  │  audio reactivo / ambiente       │
│  preview assets      │  menús / boss / debug            │
└─────────────────────────────────────────────────────────┘
         ▲                           ▲
         │                           │
   Blender + ComfyUI            OST / SFX locales
   spritesheets prerender       (sin servicios externos)
```

---

## 4. Inspiraciones visuales (targets)

| Juego | Técnica a robar | Rama engine |
|-------|-----------------|-------------|
| AoE2 / RA2 | 3D→isométrico, team colors, sombras | RTS scene + palette shader |
| DKC2 | Prerender + parallax 4–6 capas | Platformer scene |
| MMX5 / PS1 | BG prerender + sprite hero | Action scene + depth desat |
| Super Metroid | Room graph, puertas, zona palette | Metroidvania scene |
| LTTP | Tilemap 16×16, 3 capas | Top-down scene |
| Game Boy | 160×144, paleta fija | GBDK o escena GB + **brickboy** QA |

**brickboy** (display fidelity GB): https://sonohoka.sakura.ne.jp/brickboy/  
Artículo metodología display: https://note.com/kathoc/n/n5ceb773a3dbc

---

## 5. Pipeline de assets (local, RX 6600)

1. **Blender** — modelos low-poly, batch render ortho/isométrico → PNG sequences
2. **ComfyUI + DirectML** — texturas, polish, img2img (SD 1.5, 512² cómodo)
3. **Spritesheet** — grid en Aseprite o script; naming convention documentada
4. **Engine** — asset loader de Frank carga sheets + JSON de animación
5. **QA** — brickboy (GB), shaders “era” (PS1/SNES) medidos como brickboy hace con reflector

---

## 6. Cómo compartir los cursos con el agente

No hace falta subir vídeos. Opciones:

| Método | Qué poner |
|--------|-----------|
| **A — Código fuente** | Carpeta `vendor/franks-lab/` con los 3 proyectos finales del curso |
| **B — ZIP local** | `assets/courses/franks-lab.zip` en repo (gitignore si pesan mucho) |
| **C — Manifest** | `vendor/franks-lab/MANIFEST.md` listando archivos + qué curso es cada uno |
| **D — Snippets** | Pegar en chat las clases que quieras portar primero |

**Prioridad de import:** Engine → Pixel Rain → Visualizer (en ese orden).

---

## 7. Checklist pre-arranque

- [ ] Copiar código final de los 3 cursos a `vendor/franks-lab/`
- [ ] Elegir primer target visual (¿isométrico AoE2 o platformer DKC2?)
- [ ] Definir resolución nativa + escala entera
- [ ] Convención spritesheet: `{entity}_{anim}_{frame}.png` o JSON atlas
- [ ] Un shader “display era” por estilo (GB / SNES / PS1)
- [ ] ROM/test scene para brickboy si rama GB
- [ ] ComfyUI workflow guardado para texturas del primer juego

---

## 8. Decisiones pendientes

| Pregunta | Opciones |
|----------|----------|
| ¿Todo en browser (Canvas) o export a Electron? | Browser primero (cursos son web) |
| ¿GB nativo (GBDK) o emulado en engine? | TBD |
| ¿Godot más adelante o solo Frank engine? | Frank engine para prototipos; Godot si crece scope |
| ¿Un repo o monorepo con TTS? | Separar `game/` cuando arranquemos |

---

## 9. Links rápidos

| Recurso | URL |
|---------|-----|
| Frank's Lab YT | https://www.youtube.com/c/Frankslaboratory |
| Pixel Rain Udemy | https://www.udemy.com/course/learn-html-canvas-pixels-particles-physics/ |
| JS Engine Udemy | https://www.udemy.com/course/build-a-reusable-2d-game-engine-in-javascript/ |
| Audio Visualizer YT | https://www.youtube.com/watch?v=VXWvfrmpapI |
| Game Dev full course (freeCodeCamp) | https://www.freecodecamp.org/news/learn-javascript-game-development-full-course/ |
| brickboy | https://sonohoka.sakura.ne.jp/brickboy/ |

---

*Última actualización: 2026-08-02 — añadir inspiraciones y paths de curso cuando el usuario los comparta.*
