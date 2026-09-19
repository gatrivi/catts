# Local coding

**CATTS.cmd** (acceso directo *CATTS local*): un solo terminal para arrancar,
cambiar y apagar modelos y apps, sin ventanas nuevas. Guia: [docs/HUB.md](docs/HUB.md).

Lanzadores directos que siguen funcionando: **SMOL.cmd** / **TALLER.cmd**
(desktop *Smol local* / *Taller local*). Guia de Smol: [docs/SMOL.md](docs/SMOL.md).
Read `docs/SESSION_CONTEXT.md` for the paused experiment status.

- `npm run hub`: menu del centro de control; `npm run hub:status`, `npm run hub:check`.
- `npm run check`: validate Taller paths without loading a model.
- `npm test`: 19 host tests with mocked inference; no models loaded.
- Existing `npm run qwen35`, `npm run bonsai` and other coding commands are available.
  These start workloads only when you invoke them.

Modelos, puertos, presets y pisos de RAM viven en `scripts/local_models.py`
(unica fuente de verdad, compartida por el hub y Smol).

Source/config now live here. Python and the existing private OMP profile remain
shared from E:; models remain at their existing locations. See `docs/SPLIT.md`.
This migration does not make the local models reliable autonomous coders.

Experimental E4B access (project trial failed; review every write): E4B.cmd PROJECT --pause-qwen. See [usage](docs/E4B_SUPERVISADO.md).

