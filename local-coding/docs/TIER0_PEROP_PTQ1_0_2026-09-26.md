# TIER-0 medido: primer per-op del 27B PTQ1_0 en esta caja (2026-09-26 18:50)

Ejecutado con `scripts/tier0_ptq10.ps1 -Reps 2` sobre GPU quieta
(`-QuietConfirmed`: utilization <1% medida desde la sesion madre, porque
`Get-Counter` no funciona dentro de un powershell oculto -> el gate interno
siempre daba -1). Datos: `data/profile/d1_perop_20260926-185045.json`.

## Resultado

| rep | load_s | paso de decode | t/s (tiempo de ops) |
|-----|--------|----------------|---------------------|
| 1 | 108.7 (compila pipelines Vulkan en frio) | 120.53 ms | 8.30 |
| 2 | 17.2 (caliente)                        | 120.27 ms | 8.31 |

Desglose del paso de 120.27 ms:

| op | ms | % |
|----|----|---|
| MUL_MAT_VEC ptq1_0 | 78.08 | 64.9 |
| MUL_MAT_ADD MUL_MAT_VEC ptq1_0 | 22.99 | 19.1 |
| **vecq PTQ1_0 (suma)** | **101.07** | **84.0** |
| MUL_MAT_VEC f32 | 3.51 | 2.9 |
| FLASH_ATTN_EXT | 3.15 | 2.6 |
| resto | ~5.6 | 4.7 |

## Que decide

1. **El vecq PTQ1_0 es el cuello de botella, con numero.** Amdahl: 2x en ese
   kernel -> paso ~70 ms -> **14.3 t/s**; 3x -> ~51 ms -> **19.6 t/s**. El
   objetivo SOTA (12-14 t/s) esta exactamente a un factor 2 del kernel.
2. **Correccion del doc KERNEL_HEADROOM:** el "90-100% de roofline" era de un
   run de **RX 6600 + TQ2_0**, no de esta caja ni de este cuantizador. Aqui:
   ~46 GB/s (5.5 GB x 8.3 t/s) contra una 6800 que copia a ~300 GB/s. El
   kernel NO esta en el techo -> el "dispatch tax" (1.5%) es ruido, se ignora.
   Prioridad: kernel primero.
3. **No hay overhead de server medible**: el tiempo de ops da 8.3 t/s, mas
   lento que el end-to-end medido. Es 100% GPU-bound; no hay payload que arreglar.
4. **Regla de medicion:** el primer arranque paga ~91 s de compilacion de
   pipelines Vulkan (108.7 s vs 17.2 s caliente). Nunca decidir con una corrida
   fria; agrupar rep en una sola ventana.

## Estado de la tarea 1 (fix del vecq)

- 3 defectos derivados contra las dos fuentes que pasan la suite
  (`ptq1_0.glsl:15-45`, `mul_mat_vec_ptq1_0.comp:57-61`): D1 mapa de lanes de los
  tritos altos, D2 packing sin mascara de 8 bits sobre valores con signo,
  D3 `.comp`/`.glsl` desincronizados.
- Parche escrito y NO aplicado: `patches/repack4_ptq1_0_CANDIDATO_2026-09-26.txt`.
- `GGML_PTQ1_0_MMVQ` sigue en 0: hoy no hay riesgo de corrupcion en produccion.
- Al ser 84% del paso, el criterio de exito es concreto: bajar los 78.08 ms de
  `MUL_MAT_VEC ptq1_0` a ~39 ms.

## Propuesta de orden para la proxima ventana (la define el usuario)

1. `test-backend-ops` MUL_MAT con `GGML_PTQ1_0_MMVQ=1` (oraculo mecanico; hoy falla).
2. Si 68/68, medir A/B del vecq contra el mismo baseline de 8.3 t/s.
3. Re-medir en ventana limpia la curva np (1.99x) y MTP (hoy no decidibles).
