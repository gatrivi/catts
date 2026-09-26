# MATVEC PROFILE — PTQ1_0 en RX 6600 (2026-09-25, task-3 supervision)

**Motivación**: "120M tokens is a real R&D budget lol. **profile the matvec first** —
that's where mine took the 3060 from 26 to 40 tok/s." → Este doc perfila el matvec
PTQ1_0 con datos YA medidos en el rig (cero tokens, cero GPU usada hoy) y ordena
las optimizaciones por impacto esperado.

**Reglas respetadas**: no se levantaron modelos, no se tocó la GPU, no se borró nada,
todo número citado existe en `data/` o `docs/`. Lo medido se etiqueta MEDIDO; lo
inferido por eliminación A/B se etiqueta INFERIDO.

---

## 1. Fuente de datos (todas previas, en el rig)

| Fuente | Qué da |
|---|---|
| `data/profile/d1_perop_20260924-231105.json` | per-op capture del ÚLTIMO decode step (PTQ1_0 model, ctx 8192, build C:/src post-E2, GGML_VK_PERF_LOGGER). **117.7 ms/tok GPU-sum** (total exacto de la tabla) |
| `data/campaign/20260925/bandwidth-cpy.txt` + knowledge.jsonl día 1 | **bandwidth REAL de copia: 185 GB/s** (64-256 MB), 644 GB/s dentro de Infinity Cache (16 MB) |
| `data/shader_sweep/*.json` | v0_scalar 438.7 µs / v1_packed16 460.5 / v2_lut 248.1 (shape micro 4096×14336) |
| `docs/GPU_SPEEDUP_ASSESSMENT_2026-09-22.md` (D1/D2/E2/V-C/night-9) | eliminaciones A/B single-variable |
| `docs/D2_ROUND2_RUNBOOK_2026-09-24.md` | yardstick lm_head frío, calibración 41/103/217 GB/s |
| Night-9 (SESSION_CONTEXT) | TQ2_0 vecq real-layout: lm_head 2949→1637 µs (~200 GB/s); PTQ1_0 vecq PIERDE vs f16 LUT |

---

## 2. Desglose per-op del decode step (MEDIDO, capture 23:11 post-E2)

Total step: **117 728 µs** (= suma exacta de la tabla → la tabla ES un step completo).

**MUL_MAT = 106 377 µs = 90.4 % del step.** Todo lo no-matmul (attention, GDN, norms,
copies) = 11.35 ms (9.6 %). La hipótesis "el cuello está fuera del matmul" ya estaba
refutada (D1); aquí se confirma con la capture post-E2.

Matvec PTQ1_0 por instancia (pesos = m·k·28/128 bytes; MEDIDO):

| Op | calls/step | µs/inst | MB/inst | GB/s |
|---|---|---|---|---|
| gate/up m=17408 k=5120 | 128 | 342.0 | 19.5 | **57.0** |
| down m=5120 k=17408 | 64 | 346.6 | 19.5 | **56.1** |
| qkv m=10240 k=5120 | 48 | 207.2 | 11.5 | 55.1 |
| GDN-in m=6144 k=5120 | 48 | 129.3 | 6.9 | 53.1 |
| attn-out m=5120 k=6144 | 48 | 129.8 | 6.9 | 52.6 |
| GDN-qkv m=12288 k=5120 | 16 | 245.6 | 13.8 | 56.1 |
| GDN-out m=5120 k=6144 | 16 | 132.3 | 6.9 | 51.6 |
| embed-scope m=1024 k=5120 | 32 | 32.2 | 1.1 | 36.1 (latencia-pura, chico) |
| **lm_head m=248320 k=5120** | 1 | **4816** | **278** | **57.7** |

**Todas las instancias de producción corren a 52-58 GB/s** — el déficit es uniforme,
no de una shape puntual. La shape lm_head (fría, 280 MB, inmune a IC) = 57.7 GB/s,
consistente con el yardstick del runbook (41 GB/s in-suite frío vs ~57 warm/perop).

---

## 3. Byte-traffic real por token (MEDIDO, derivado del perop)

- Pesos PTQ1_0 leídos por token: **5.60 GB** (suma de la tabla; el archivo es 5.95 GB
  → 94 %, consistente: embeddings restantes y mmproj no entran al decode step).
  - MLP (gate+up+down): **3.74 GB = 67 %**
  - attention + GDN (qkv/out/in): **1.54 GB = 28 %**
  - lm_head: **0.28 GB = 5 %**
- Activaciones x: lógicas ~0.5 GB (re-lecturas por bloque de fila) pero viven en
  Infinity Cache → DRAM ≈ decenas de MB/token: despreciable.
- **Tiempo piso por token a bandwidth de copia (185 GB/s): 30.3 ms → techo físico
  ~33 t/s** (match con el 34.5 del findings doc, misma física).
- **BW efectiva actual del matvec: 52.7 GB/s = 28 % del techo de copia real**
  (y el techo de copia ya es el 83 % del pico teórico — el yardstick correcto).
- TQ2_0 comparación (mismo rig): ~85 GB/s promedio hoy; **200 GB/s** con vecq
  real-layout en lm_head (night-9). q4_0: 217 GB/s. → **la tarjeta SÍ streama a
  ~200+ GB/s con el walk correcto**; PTQ1_0 está a 1/4 de lo que el mismo hardware
  hace con q4_0.

---

## 4. Perfil por grupo de instrucciones (el 106 ms del matvec)

Metodología honesta: no hay capture RGP aún (día 16 de campaña; installer en C:
riesgoso). Este perfil se deriva de las eliminaciones A/B single-variable ya medidas
+ el shader fuente (`mul_mat_vec_ptq1_0.comp`). Cada % tiene su evidencia.

| Grupo | % del matvec (post-E2) | Estado | Evidencia |
|---|---|---|---|
| **Memoria: latencia/ocupancia del walk** (56 B contiguos/warp, row stride 1120 B, 8 elems/hilo) | **~50-55 %** | dominante | TODAS las variantes de cómputo EMPATAN (v0/v1, f32-vs-q8_1, stdq/sub16, V-C): si ALU/LDS dominaran, alguna se habría movido. Lo único que movió la aguja fue paralelismo: E2 (LDS↓ → occupancy) −18 %; WG=128/ROWS=4 −8.8 %. 52.7 GB/s con 3 loads/hilo = cadena load→unpack→LUT→FMA latency-bound, pocas wavefronts en vuelo |
| LDS: lookup LUT (8/thread/iter) + fill (1×/WG, 1280 int8) + barrier | ~8-10 % (era ~18-20 % pre-E2) | mitigado | E2 int8 LUT: 5 KB→1.25 KB = **−18 % step MEDIDO** (157.8→129.2 ms; hoy 117.7 con RAM sana). Offsets lbase múltiplos de 64 bancos → sin bank conflicts estructurales |
| ALU decode + FMA (unpack8 + 8 FMA + d·s) | ~10 % | descartado como cuello | closed-form vs LUT EMPATAN en lm_head; packed16 (más ALU) = +5 % PEOR → ALU sobrante |
| Reducción (SHMEM tree por NUM_ROWS×NUM_COLS) + barriers | ~8-10 % | pendiente de atacar | HYBRID vs SHMEM empata a WG≤64; sub16hyb crasheaba (fixed night-9); sin A/B positivo aún → % INFERIDO |
| Loads x-vector + d + acumulación temp | ~5-8 % | menor | x IC-residente; d = 2 B/128 elems |

**Conclusión del perfil**: el matvec PTQ1_0 NO es ALU-bound ni LDS-bound (eso quedó
arreglado con E2) ni bandwidth-bound puro — es **latency/occupancy-bound por el
walk**: cada warp toca solo 56 B contiguos de A (vs 132 B en TQ2_0, vs ~448 B
efectivos en q4_0 con int-dot) y el hilo encadena 3 loads → decode → 1 cadena FMA
corta por 8 elementos, con pocas wavefronts para tapar la latencia. El 72 % del
tiempo de matvec que excede el piso de copia (106 − 30 ms) se lo lleva eso.

Referencia del experto (3060: 26→40 t/s perfilando): mismo patrón — el win no estuvo
en reescribir la aritmética sino en el patrón de acceso/paralelismo del matvec.

---

## 5. Las 3 optimizaciones candidatas (ordenadas por ejecución e impacto)

### #1 — Activar el config banked WG=128/ROWS=4 + paired-row walk
- **Qué**: (a) activar el config banked E1/night-9 (GGML_PTQ1_0_WG=128,
  GGML_PTQ1_0_ROWS=4, HYBRID spv auto, suite 28/28, **−8.8 % lm_head MEDIDO**);
  (b) mismo mecanismo de threads-extra — NO elems-extra (E2-16elems fue +12.6 %
  REGRESIÓN, lección night-9) — con cada thread-par leyendo bloques de 2 filas
  adyacentes → 4 filas en vuelo por warp = 224 B por transacción-warp y 2×
  occupancy de loads.
- **Impacto estimado**: config solo = −8.8 %; walk 2-filas encima → objetivo
  lm_head 4816→~3600-3000 µs (65-80 GB/s), step 117.7→~95-100 ms →
  **8.5→10-10.5 t/s GPU-sum** (wall hoy 7.4-7.9). Riesgo BAJO (env-gated,
  reversible, no toca layout en disco).
- **Coste**: iteración token-free del runbook (~10 min por ciclo: edit → ninja
  test-backend-ops → lm_head perf → 68/68 → golden 7/8).

### #2 — Repack element-major CONTIGUO en load (E3-repack con premisa CORREGIDA)
- **Qué**: E3 fue SKIPped porque su premisa original (ahorrar loads redundantes)
  quedó refutada por el gate V-C — pero el perfil de hoy muestra que su beneficio
  real sería OTRO: contigüidad. Repack al cargar el GGUF (una pasada CPU por
  tensor, cacheada en Z:) reordenando los 28 B de cada bloque a forma
  [4×(32 elems consecutivos en 7 B trit-packed)] → el warp toca 112-448 B
  contiguos y el decode LUT se hace con u32 unpack sin shared.
- **Impacto estimado**: es el único camino que ataca el 50-55 % de una vez;
  objetivo paridad del walk TQ2_0 (102-200 GB/s) = **lm_head ~2800-1400 µs,
  step →~60-75 ms → 13-16 t/s**. Riesgo MEDIO-ALTO (toca layout en disco +
  loader, exige golden 7/8 estricto).
- **Nota**: NO confundir con el E3 original ni con el vecq int-dot de night-9
  (5440 vs 5319 µs = pierde): el int-dot NO es el win para PTQ1_0 — la
  contigüidad sí.

### #3 — Vecq PTQ1_0 con repack4 del REAL layout (clon TQ2_0, corregido)
- **Qué**: rehacer la rama vecq PTQ1_0 (GGML_PTQ1_0_MMVQ=1) con el unpack del
  layout real (byte b = elems {b, b+32, b+64, b+96}, shift 2·(ib%8%4)) en vez
  del repack4 de 16-bytes-consecutivos asumido que usó night-9 (causa probable
  de que perdiera).
- **Impacto estimado**: si el fallo de night-9 era el layout, techo ~int-dot con
  x q8_1: similar a #1 (10-11 t/s) pero con menos LDS; si era estructural (los
  trits no mapean limpio a dot 4×int8), queda en empate y se descarta
  definitivo. Riesgo MEDIO, valor informativo ALTO (cierra la pregunta vecq).

**Orden de ejecución recomendado**: #1 (hoy, casi gratis, banked) → #3 (A/B
informativo, misma infraestructura) → #2 (el win grande, sesión propia con golden
gate). **La #2 es la de mayor impacto total del track** (contigüidad), pero #1 se
ejecuta primero porque ya está medida y paga ~9-18 % sin riesgo — mismo orden en
que procedió el experto del 3060: perfilar → quick win → rediseño del walk.

---

## 6. Confirmación pendiente (para el knowledge pack / campaña nocturna)

- **RGP capture** (día 16 de campaña): convierte la tabla de §4 de INFERIDO a
  MEDIDO por-instrucción (occupancy, wavefronts, stall reasons). Alternativa
  token-free más barata: query pools de VK pipeline-statistics vía
  GGML_VK_PERF_LOGGER — la infraestructura ya existe en el fork.
- Repetir perop capture con el config #1 activado para verificar el delta −8.8 %
  en E2E (no solo in-suite).
- La curva n=1,2,4,8 de q4_0 (día 2, knowledge.jsonl) ya muestra que batch-2
  verification es casi gratis → alimenta el caso spec-decode (ngram +10 % día 2).

---

*Escrito por la sesión de supervisión ZCode (2026-09-25 ~14:20 GMT-3). Datos: rutas
en §1. Coordinación: ver entrada correspondiente en docs/SESSION_CONTEXT.md.*
