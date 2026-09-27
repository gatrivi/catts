# Techo de capacidad de la caja — PTQ1_0 27B (2026-09-26)

Documento de traspaso. Hecho para que un modelo más grande no tenga que re-derivar
nada: todo lo de abajo está medido o es aritmética, y las hipótesis **marcadas como refutadas** son hipótesis mías que ya quedaron descartadas. No las reintentes.

## 0. Premisas corregidas (leer antes que nada)

| Lo que decía el contexto | Realidad | Cómo se verificó |
|---|---|---|
| GPU = RX 6800, 384 GB/s | **RX 6600** (Navi 23, 28 CU, 1792 SP, wave32, 224 GB/s) | `data/bonsai2-tq2-quantize.log`: `1 = AMD Radeon RX 6600 \| uma: 0 \| warp size: 32`. `Vulkan0` = iGPU UMA (8138 MB = RAM del sistema), `Vulkan1` = la dGPU. Producción usa `--device Vulkan1` ✓ |
| `test-backend-ops` validó el vecq en la GPU | corrió en **Vulkan0 = la iGPU** | el log de la suite solo reporta el device elegido |
| El int-dot se puede optimizar | **muerto por hardware** | `ggml-vulkan.cpp:447` clasifica RDNA2 justamente cuando `integerDotProduct4x8BitPackedMixedSignednessAccelerated` es false. RDNA2 no tiene `dotPacked4x8EXT` nativo |

## 1. Números medidos (los oráculos)

- `data/profile/d1_perop_20260926-185045.json`, producción, 8192 ctx, q4_0 KV:
  **paso 120.53 ms = 8.30 t/s**.
- matvec PTQ1_0: **5.215 GB leídos / 101.09 ms = 55.4 GB/s** (25% del pico de 224).
  Es el 84% del paso. El resto son 19.44 ms (flash_attn 3.19, f32 2.27, GET_ROWS
  1.86, rms_norm 1.65…).
- Formato: `block_ptq1_0` = `d(2 B) + qs[24] + qh[2]` = **28 B / 128 elem = 1.75
  bits/elem**. El ideal ternario es 1.585 → **solo 10% de sobrecarga por el formato**.
  El formato NO es el problema.
- A/B del vecq (`data/profile/ab_mmvq_20260926.json`): vecq 2.55 t/s vs LUT 8.31 t/s.
  El flag `GGML_PTQ1_0_MMVQ` queda **off**; producción intacta.
- Concurrencia (`data/np_curve_ext.json`): np=1 8.14, np=2 13.52, **np=5 19.45,
  np=6 19.50 (codo)**, np=8 18.64 (regresa). Óptimo np=5, no subir más.
- Referencias de la caja: memcpy 185 GB/s, q4_0 217 GB/s, TQ2_0 f32 102 GB/s,
  TQ2_0 vecq (dotPacked) 193 GB/s en lm_head.

## 2. Techo físico (por qué 185 GB/s no es la respuesta)

| matvec | ms | paso | t/s |
|---|---|---|---|
| 55 (hoy) | 101.1 | 120.5 | 8.3 |
| 102 (paridad TQ2_0 f32) | 51.1 | 70.5 | **14.2** |
| 140 | 37.2 | 56.7 | 17.6 |
| 185 (memcpy) | 28.2 | 47.6 | **21.0** |
| 224 (pico) | 23.3 | 42.7 | 23.4 |

**Aunque el kernel fuera infinitamente rápido, el techo es ~21-23 t/s**, porque los
19.44 ms no-matvec quedan como piso. Los "14 t/s" del plan son alcanzables a ~100 GB/s
de matvec, no a 185.

## 3. Una anomalía sin explicar (importante, no la Toqué)

A np=5 el paso de batch tarda 257 ms por 5 tokens contra 123 ms de un paso mono. El
peso se lee una vez por paso, así que el bandwidth efectivo es **21.6 GB/s en batch
contra 45 GB/s en mono**: el camino `NUM_COLS>1` es **2× menos eficiente en bandwidth

## 4. La comparación con TQ2_0 (esto SÍ se sostiene)

Los dos kernels tienen **exactamente la misma estructura**: 16 threads por bloque de
128 elementos, mismo `it_size = gl_WorkGroupSize.x/16`, mismo walk por filas pareadas,
mismo `reduce_result`. Lo único que difiere es el decode:

- **TQ2_0** (2 bits/elem): `(u32 >> shift) & 0x03030303` y **cada lane ya es el
  valor**. Cero unpack. 1 `dotPacked4x8EXT` cada 4 elementos. → 193 GB/s.
- **PTQ1_0** (tritos base-3): necesita un paso **no lineal por elemento**.
  lut[lbase + ba0[l]] -> 8 gathers por 8 elementos -> 55 GB/s.

## 5. Hipótesis REFUTADA (mía, ya gastada — no la reintentes)

**"El kernel está limitado por los 8 gathers de LUT con 8-16 vías de conflicto de
banco, y se arregla vectorizando la lectura del LUT."** Descartada por dos motivos
independientes:

1. **La vectorización es imposible.** El LUT es un gather genuino: la dirección es
   `lut[lbase + ba0[l]]`, o sea **depende del dato**. Las 8 direcciones no son
   consecutivas, así que no se pueden traer con un solo `LDS.32`. No hay "leer 8 bytes
   y unpackear": hay que ir a buscar 8 bytes *elegidos por el dato*.
2. **El grado de conflicto no es 8-16×.** La aritmética de bancos da un ~2× esperado
   (ley de cumpleaños sobre 32 bancos con direcciones aleatorias), no 8-16×. Y con
   datos aleatorios, el padding de stride tampoco ayuda: `256 B = 64 palabras` da
   `64 mod 32 = 0`, sí, pero como el offset intra-plano es aleatorio el resultado es
   el mismo ~2× que con cualquier otro stride. **El padding es una no-op.**

### La aritmética que refuta todo el diagnóstico

Presupuesto por elemento a 224 GB/s con 0.219 B/elem → 1.02e12 elem/s.
Emisión: 56 SIMD × 2.49 GHz = 1.39e11 instr/warp/s × 32 lanes = 4.46e12 elem/s si
fuera 1 instrucción por elemento. El kernel usa ~3.5 (1 gather + 1 cvt + 1 FMA +
0.5 cargas A) → necesitaría el **81% de la capacidad de emisión** para llegar a
pico. Al medir 55.4 GB/s está usando ~**20%**.

**O sea: el kernel no está limitado por throughput de ALU ni de LDS. Está
STALLED.** Eso invalida toda la familia de explicaciones "hay que quitar trabajo".
LDS: 1 acceso/elem pediría 0.85 TB/s contra ~34 TB/s de capacidad (2.5%). ALU: 20%.

Y el dato que lo confirma: **TQ2_0 hace `dotPacked4x8EXT` en una GPU sin int-dot por
hardware y aun así llega a 193 GB/s.** Si el dot emulado costara ~8 instrucciones,
serían 2 instr/elem — el mismo presupuesto que el LUT. O sea el dot no es el problema;
**el problema es el kernel, no la aritmética**. La afirmacion del autor en en
`GPU_SPEEDUP_ASSESSMENT` de que "el win vino de int-dot + 4× menos cargas" mezcla dos
cosas: en TQ2_0 elLayout ya es dot-friendly y hace cero decode.

## 6. Por qué el int-dot está muerto en PTQ1_0 aunque el hardware lo tuviera

`repack4` de PTQ1_0 tiene que *decodificar* base-3 → lanes de byte, que es aritmética
no lineal, ~6-10 ops × 16 bytes cada 4 dots ≈ **9 ops/elem**. Un dot product exige
una representación **lineal**; base-3 no la tiene. TQ2_0 no decodifica nada, por eso
le sale gratis. No es un bug de implementación: es la estructura del formato.
Un `repack` offline tampoco sirve: difundir tritos a 8 bits multiplica ×4 el
bandwidth, y el bandwidth es el recurso que ya falta.

## 7. Cola de experimentos (cada uno con su oráculo)

Todos con el mismo oráculo: `python scripts/d1_perop_profile.py 8192 q4_0 48 <gguf>`
y mirar **GB/s del matvec ptq1_0** (no t/s, no in-suite). Corrección previa: verificar
`ptq1_0 m=17408` ≈ 55 GB/s antes de comparar.

Orden por relación señal/ruido:

| # | Experimento | Cambio | Qué discrimina | Coste |
|---|---|---|---|---|
| **E-0** | Cambiar `-n` de dispatch / `NUM_ROWS` / tamaño de workgroup **sin tocar el shader** | solo `ggml-vulkan.cpp` | ocupación y wave-quantization. lm_head son 136 bloques / 16 = 8.5 iteraciones → la última va a medio llenar. Si esto mueve la aguja, el problema es scheduling, no el código | bajo, sin shader |
| **E-1** | **Romper la dependencia del acumulador.** `temp[j][n] = fma(d0, s0, temp[j][n])` es una cadena serial a lo largo de todo el loop `i`. Desenrollar ×2-4 con acumuladores parciales separados | `mul_mat_vec_ptq1_0.comp`, ~10 líneas | **la hipótesis principal**: si baja el tiempo, es latency-bound y está trouvé. | bajo, es el más informativo |
| **E-2** | Quitar la LUT, usar la forma cerrada `ptq1_0_trit` que ya existe en `ptq1_0.glsl` (~6 int ops, 0 LDS) | idem, ~15 líneas | si LDS/instrucciones importan. Libera 1.25 KB de LDS. **Ojo: es la forma más lenta en aritmética, así que solo es informativo si gana** | medio |
| **E-3** | Vectorizar la carga A: hoy son 4 cargas `uint16` + 2 shifts + 2 ors por 8 elementos. Agregar vista `uint32_t qs32[6]` a `block_ptq1_0_packed16` → 2 cargas de 32 bits alineadas | `types.glsl` + el comp | si el cuello es la carga escalar de 2 bytes. El stride de bloque es 28 B (4-aligned pero no 8) | bajo |
| **E-4** | Padding de stride 256→260 | 1 línea | **esperado: no-op** (§5.2). Medirlo sirve para cerrar el tema con evidencia y no con opinión | bajo |
| **E-5** | `NUM_COLS>1`:Np>1 da 21.6 GB/s contra 45 GB/s en mono | requiere perf logger con np=5 | entender por qué el batch es 2× peor. Es lo que decide si la concurrencia sobrevive al arreglo del kernel | medio |

**No hacer**: (a) más trabajo en la familia int-dot / vecq de PTQ1_0 — está
refutado por medición (3.7× más lento) y por estructura de formato (§6); (b) subir
`np` más allá de 5 — medido, el codo está en 5-6 y np=8 regresa; (c) tocar el formato
del GGUF — 1.75 bits/elem ya está a 10% del ideal.

que el mono**, sin explicación. El multiplicador 2.4× de la concurrencia se debe
precisamente a ese desperdicio, no a paralelismo bien explotado. Si el kernel se
arregla y queda realmente BW-bound, **ese multiplicador cae** — los tracks de kernel y
de concurrencia NO son aditivos.
