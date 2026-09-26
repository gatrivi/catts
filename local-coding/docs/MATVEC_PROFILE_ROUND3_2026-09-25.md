# MATVEC PROFILE ROUND 3 — PTQ1_0 threads-extra walk + vecq REAL layout (2026-09-25)

## Resumen de cambios

**Archivos modificados (con backup previo):**
- `C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vecq_funcs.glsl.bak-20260925b` → `mul_mat_vecq_funcs.glsl`
  - Optimización #3: rama vecq PTQ1_0 (`GGML_PTQ1_0_MMVQ=1`) con **repack4 vectorizado por aritmética** (sin LUT) para el layout REAL PTQ1_0
  - Nuevo helper `trits4(uvec4 bytes, uint n)` que calcula 4 trits en paralelo via closed-form
  - Eliminado LUT compartido (1.25 KB) y `fill_ptq_lut()` de `mul_mat_vecq.comp`
- `C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vec_ptq1_0.comp.bak-20260925b` → `mul_mat_vec_ptq1_0.comp`
  - **Threads-extra walk**: 32 hilos/bloque-worth (antes 16), cada hilo 4 elementos contiguos
  - Warp de 32 hilos cubre 128 elementos contiguos = 256 B contiguos en activaciones
  - Mapeo: `itid = tid%32`, `ix = tid/32`, `y_idx = i*QUANT_K + itid*4`
  - Requiere `GGML_PTQ1_0_WG=256`, `GGML_PTQ1_0_ROWS=4` (HYBRID reduction)

---

## Resultados de validación (token-free iteration loop)

### Correctness (68/68 suite)
| Config | PTQ1_0 | TQ2_0 | Q4_0 |
|--------|--------|-------|------|
| Default (WG=32, ROWS=2) | ✅ 68/68 | ✅ | ✅ |
| **WG=256, ROWS=4 + threads-extra** | ✅ **68/68** | ✅ | ✅ |
| Vecq PTQ1_0 (GGML_PTQ1_0_MMVQ=1) | ✅ 68/68 | ✅ | ✅ |

### Performance A/B (lm_head cold 248320×5120, n=1, yardstick frío)

| Kernel | Baseline (post-E2) | Round 2 (paired-row) | Round 3a (vecq real layout) | Round 3b (threads-extra f16) | Delta vs baseline |
|--------|-------------------|----------------------|----------------------------|------------------------------|-------------------|
| **PTQ1_0 f32 matvec** | 5112 µs (54.4 GB/s) | 4799 µs (58.0 GB/s) | 5491 µs (50.6 GB/s) | **5044 µs** (55.1 GB/s) | **-1.3%** |
| PTQ1_0 gate/up 17408×5120 | 381 µs | 365 µs | 373 µs | **328 µs** | **-14%** |
| TQ2_0 vecq (ref) | 2949 µs | 1642 µs | 1643 µs | 1643 µs | -44% |
| Q4_0 (ref) | 3298 µs | 3303 µs | 3332 µs | 3332 µs | ~0% |

---

## Análisis

### Vecq PTQ1_0 con repack4 REAL layout (optimización #3)
- **5491 µs en lm_head** — **PEOR que f16 LUT** (5112 µs), confirma hallazgo night-9 (5440 vs 5319 µs)
- El repack4 vectorizado elimina LUT pero la aritmética closed-form (6 mul/shift por trit) no compensa
- Cuello real **no es el decode** (ALU/LDS) sino el **walk de memoria**: 56 B/warp contiguos en pesos PTQ1_0
- TQ2_0 vecq gana porque su layout da 132 B/warp contiguos + int-dot nativo; PTQ1_0 no mapea limpio a dot 4×int8

### Threads-extra walk (f16 LUT, WG=256)
- **5044 µs en lm_head** — solo **-1.3% vs baseline** (5112 µs)
- Gate/up mejora **-14%** (381→328 µs) al tener activaciones contiguas (256 B/warp)
- **lm_head no mejora proporcionalmente**: row stride 1120 B domina; 40 bloques/fila × 28 B = 1120 B salto entre bloques
- TQ2_0 logra 200 GB/s porque sus bloques de 66 B + walk nativo dan ~448 B/warp efectivos; PTQ1_0 28 B/bloque limita a ~56 B/warp

### Techo identificado
El **layout PTQ1_0 en disco (GGUF)** impide coalescing de pesos:
- 128 elems = 28 B (qs[24] + qh[2] + f16 d) → 0.22 B/elem vs 0.5 B/elem (TQ2_0) vs 1 B/elem (q4_0 nibble)
- Cualquier walk sobre este layout da ≤56 B/warp contiguos en pesos → latency-bound a ~55 GB/s
- La optimización #2 (repack element-major CONTIGUO en load, GGUF-side) es el **único camino** a paridad TQ2_0
- Requiere sesión propia con golden gate estricto (toca layout en disco + loader)

---

## Criterio de parada cumplido

| Diseño probado | lm_head (µs) | <3000 µs? |
|----------------|--------------|-----------|
| Round 2: paired-row (elems-extra) | 4799 | ❌ |
| Round 3a: vecq PTQ1_0 real layout | 5491 | ❌ |
| Round 3b: threads-extra (WG=256) | 5044 | ❌ |

**3 diseños consecutivos sin mover lm_head <3000 µs → CIERRE DEL TRACK PTQ1_0**

El techo físico del layout PTQ1_0 actual es **~55 GB/s (5000-5100 µs en lm_head)**. La tarjeta SÍ streamea a 200+ GB/s (TQ2_0 vecq, q4_0) — el problema es el layout de pesos, no el hardware.

---

## Pendientes (no ejecutados — track cerrado)

- [ ] Golden check end-to-end (omitido: no hay mejora de fidelidad)
- [ ] Perop capture con config activado
- [ ] Repack GGUF element-major CONTIGUO (optimización #2 — requiere sesión dedicada + golden 7/8)
- [ ] RGP capture (día 16 campaña)

---

## Conclusión

**PTQ1_0 en RX 6600 tiene techo duro en ~55 GB/s por layout de pesos**. La fidelidad verificada de PTQ1_0 no compensa el 4× penalty vs TQ2_0/q4_0. 

**Recomendación**: usar **TQ2_0 como daily driver** (12.2 t/s techo, vecq funcional a 200 GB/s) y perseguir **requant TQ2_0** (Colab runbook `COLAB_TQ2_REQUANT_JOB.md`) para producción. El track PTQ1_0 se cierra aquí.

---
*Escrito por sesión local-coding (2026-09-25). Datos: suite 68/68, perf token-free, yardstick lm_head frío.*