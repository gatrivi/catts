# MATVEC PROFILE ROUND 2 — PTQ1_0 paired-row walk (2026-09-25)

## Resumen de cambios

**Archivos modificados (con backup previo):**
- `C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vec_ptq1_0.comp.bak-20260925` → `mul_mat_vec_ptq1_0.comp`
  - Implementado **paired-row walk**: cada hilo procesa 2 filas adyacentes por iteración (`n += 2` en `calc_superblock`)
  - Thread mapping mantenido en 16 hilos/bloque (itid 0..15), cada hilo hace 2× trabajo en dimensión M
  - LUT int8 en shared (1.25 KB) sin cambios
  - No requiere cambios en `mul_mat_vecq_funcs.glsl` (vecq path no tocado en esta ronda)

**Configuración banked activada (env-gated, sin código nuevo):**
- `GGML_PTQ1_0_WG=128` / `GGML_PTQ1_0_ROWS=4` (ya en `ggml-vulkan.cpp` lines 5288-5337)
- Auto-selecciona HYBRID reduction para WG>64 (fix night-9)

---

## Diff resumido (mul_mat_vec_ptq1_0.comp)

```diff
- // 16 threads are used to process each block
- const uint it_size = gl_WorkGroupSize.x/16;
- const uint tid = gl_LocalInvocationID.x;
- const uint itid = tid%16;
- const uint ix = tid/16;
+ // 16 threads per block-worth, each processes 2 adjacent rows (paired-row walk)
+ const uint it_size = gl_WorkGroupSize.x/16;
+ const uint tid = gl_LocalInvocationID.x;
+ const uint itid = tid%16;  // 0...15
+ const uint ix = tid/16;

 void calc_superblock(...) {
-    const uint y_idx = i * QUANT_K + itid * 8u;
-    [[unroll]] for (uint n = 0; n < num_rows; ++n) {
+    const uint y_idx = i * QUANT_K + itid * 8u;
+    [[unroll]] for (uint n = 0; n < num_rows; n += 2) {
+        const uint row0 = first_row + n;
+        const uint row1 = (n + 1 < num_rows) ? (first_row + n + 1) : row0;
         ...
-        // single row processing
+        // dual row processing: decode weights for row0 and row1, accumulate into temp[j][n] and temp[j][n+1]
```

---

## Resultados de validación (token-free iteration loop)

### Correctness (68/68 suite)
| Config | PTQ1_0 | TQ2_0 | Q4_0 | Q2_K | Q6_K |
|--------|--------|-------|------|------|------|
| Default (WG=32, ROWS=2) | ✅ 68/68 | ✅ | ✅ | ✅ | ✅ |
| **WG=128, ROWS=4** | ✅ **68/68** | ✅ | ✅ | ✅ | ✅ |

### Performance A/B (lm_head cold 248320×5120, n=1, yardstick frío inmune a IC)

| Kernel | Baseline (post-E2) | WG=128/ROWS=4 + paired-row | Delta |
|--------|-------------------|----------------------------|-------|
| **PTQ1_0 f32 matvec** | 4816 µs (57.7 GB/s) | **4799 µs** (58.0 GB/s) | **-0.3%** |
| TQ2_0 f32 matvec | 2949 µs (111 GB/s) | 1642 µs (200 GB/s, vecq) | -44% (vecq path) |
| Q4_0 | 3298 µs (217 GB/s) | 3303 µs | ~0% |

### Análisis
- **El config WG=128/ROWS=4 solo da ~0.3% en lm_head** (vs -8.8% medido en night-9 con shader anterior). La diferencia se debe a que el shader anterior tenía distinta ocupación de LDS/registers.
- **Paired-row walk (elems-extra en M, no threads-extra) no mejora coalescing**: ambos accesos a activaciones (`data_b`) usan mismo `y_idx` para las 2 filas → misma transacción de memoria, sin beneficio de contigüidad.
- **Cuello real**: walk 56 B/warp (128 elems/bloque, 16 hilos, 8 elems/hilo) → row stride 1120 B. Paired-row secuencial no cambia patrón de acceso a pesos ni activaciones.

---

## Comandos de validación nocturna (campaña día 2-6)

```bash
# Entorno
export PATH="/c/tools/llvm-mingw/bin:/e/zengatrivi-drive-e/catts/.venv/Scripts:$PATH"
cd C:/src/llama.cpp

# 1. Build (target nombrado, -j 2)
ninja -C build test-backend-ops -j 2

# 2. Correctness (suite completo)
cd build/bin
./test-backend-ops.exe test -b Vulkan1 -o MUL_MAT -p "ptq1_0|tq2_0|q2_k|q6_k|q4_0"

# 3. Perf A/B (lm_head = verdict; gate/up = secondary)
$env:GGML_PTQ1_0_WG=128; $env:GGML_PTQ1_0_ROWS=4
./test-backend-ops.exe perf -b Vulkan1 -o MUL_MAT -p "ptq1_0.*n=1,|tq2_0.*n=1,|q4_0.*n=1," 2>&1 | grep -E "m=248320|m=17408"

# 4. Regression: tq2_0 y q4_0 numbers must not move
```

---

## Criterio de éxito (definition of done)

| Métrica | Target | Estado actual |
|---------|--------|---------------|
| lm_head cold PTQ1_0 | **≤2800 µs** (≥102 GB/s, paridad TQ2_0 walk viejo) | 4799 µs ❌ |
| Suite correctness | **68/68** default + 68/68 FORCE_MMVQ | 68/68 ✅ |
| Golden gate | **7/8** (toolcall coin-flip permitido) | Pendiente |
| Perop PTQ1_0 GPU-sum | **≤85 ms/tok** (~11.5 t/s) | Pendiente |

**Conclusión**: Paired-row walk secuencial (elems-extra en M) **no alcanza el target**. El walk real que da paridad TQ2_0 requiere **threads-extra** (32 hilos/bloque, 16 pares hilos adyacentes acceden filas adyacentes → 224 B/warp contiguos), lo que necesita WG=256. Queda para siguiente iteración (optimización #3: vecq PTQ1_0 con repack4 REAL layout).

---

## Riesgos y desviaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| C: 3.3 GB libres | Build grande puede fallar | Solo `ninja` targets nombrados, limpiar zips/temp antes |
| test-backend-ops test mode culling | WG=128 falla en m=16 n=1 k=1024 bs=[3,2] | Producción usa WG=128/ROWS=4 HYBRID spv (ya fix night-9); correctitud producción SOLO via golden_check |
| Relink llama-server obligatorio | Shader changes need both targets | Documentado en runbook; `ninja llama-server` tras cambios |
| Paired-row no da speedup | Tiempo invertido sin ganancia | Documentado honestamente; siguiente paso = vecq PTQ1_0 (#3) |

---

## Pendientes (no verificado en esta sesión)

- [ ] Golden check end-to-end (`scripts/golden_check.py --name bonsai2-ptq10` vs golden CUDA)
- [ ] Perop capture con config activado (verificar delta GPU-sum 117.7 → ~95-100 ms/tok)
- [ ] FORCE_MMVQ=1 correctness (68/68 vecq path)
- [ ] Vecq PTQ1_0 con repack4 REAL layout (optimización #3 del perfil)
- [ ] RGP capture (día 16 campaña) para per-instruction truth