# 07 - PTQ1_0 vecq: arreglar el interleave de los trits altos (SOTA per-stream)

Zona: `C:\src\llama.cpp\ggml\src\ggml-vulkan\**`. Read-only hasta que el usuario
diga "maquina libre" (hoy tope 15% de CPU: nada de `ninja`, nada de GPU).

## Por que esta es la tarea

Nuestro 27B PTQ1_0 corre a 8.64 t/s = ~47 GB/s. En el mismo fork, TQ2_0 por el
camino vecq (int-dot) mueve a ~180-200 GB/s y esa auditoria
(`local-coding/docs/KERNEL_HEADROOM_2026-09-25.md`) lo deja al 90-100% del
roofline. La diferencia de camino no de hardware: **PTQ1_0 vecq esta apagado por
default** (`ggml-vulkan.cpp:9719-9725`) porque medido, da MAS LENTO (lm_head
5319 -> 5440 us). Y medido mas lento tiene sentido: esta MAL, no solo lento.

Si sale bien: las ratios de TQ2_0 son el mejor proxy (1.16x-1.80x por forma,
`KERNEL_HEADROOM` S2) => 8.64 -> ~11-14 t/s **por stream**, y se multiplica con
el `-np 3` (1.99x agregado, ya medido en `data/np_curve_20260926.json`).

## El bug, con linea

`vulkan-shaders/mul_mat_vecq_funcs.glsl`, `repack4`, rama `else` (ebase == 112),
lineas 666-678. Los elementos 120..127 de cada bloque salen de `qh`, y el
comentario de la propia funcion dice el mapa:

    // ebase = 112: e 112..119 = qs[16+k] p=4; e 120..127 = qh[(k-8)&1] p=(k-8)>>1

O sea para el elemento j (0..7) dentro del grupo alto:
byte = `(j)&1`, posicion = `j>>1`. El codigo actual hace otra cosa:

    const uint qhw = uint(data_a_packed16[ib].qh[0]);
    const uvec4 qh_bytes = uvec4(qhw & 0xFFu, qhw >> 8u, qhw & 0xFFu, qhw >> 8u);
    hi0 = trits4(qh_bytes, 0u); // trits 0,0 for qh0,qh1
    hi1 = trits4(qh_bytes, 1u); // trits 1,1 for qh0,qh1

Duplica el par de bytes y fija `p` en 0 y 1, asi que las 4 lanes de `hi0`
repiten los mismos 2 trits. La constraint del shader: `trits4(vec, p)` extrae la
misma posicion `p` de las 4 lanes, y aca `p` CAMBIA por lane. La forma de
resolverlo sin cambiar la firma es **dos llamadas con p par/impar y mezclar
lanes a mano**, p.ej. para hi0 (j=0..3 -> (b,p) = (0,0),(1,0),(0,1),(1,1)):

    t0 = trits4(qh_bytes, 0u);   // lanes con p=0
    t1 = trits4(qh_bytes, 1u);   // lanes con p=1
    hi0 = uvec4(t0.x, t0.y, t1.z, t1.w);

y analogo para hi1 con p=2,3. **NO es esto a ciegas**: confirmar contra el
referencial CPU antes de escribir una linea.

## Pasos

1. Leer el mapa real en el oraculo CPU: `grep -rn "ptq1_0" ggml/src/*.c ggml/src/*.cpp`
   y leer `dequantize_ptq1_0` + el `vec_dot` PTQ1_0 x q8_1. Ahi esta el orden de
   bits correcto; el shader tiene que replicarlo, no inventarlo.
2. Confirmar tamano/semantica de `qh` en la struct del bloque
   (`vulkan-shaders/ptq1_0.glsl`) y cuanto pesa cada byte.
3. **Resincronizar el par**: `mul_mat_vecq.comp:29-30` dice "No LUT needed" porque
   le borraron `ptq_trit_lut`; el `.glsl` la llamaba (ver
   `REVIEW_2026-09-25_LATE_4_FINDINGS.md` F1 punto 2 y mi correccion de las 09:20).
   Decidir UN camino (LUT o aritmetica) y dejar los dos archivos de acuerdo.
   El `ptq_trit_lut` esta en `mul_mat_vecq_funcs.glsl.bak-20260925b` si hace falta.
4. Aplicar el fix, `ninja -C build` y relinkear **llama-server.exe** (no solo
   test-backend-ops: es la regla que ya se rompio una vez).
5. Gate de validacion, en este orden y sin saltarse:
   - `test-backend-ops` MUL_MAT 68/68;
   - golden PTQ1_0 7/8 (el gate de calidad del modelo);
   - A/B de velocidad con `GGML_PTQ1_0_MMVQ=1` on/off en perop de produccion,
     2 corridas por brazo.
   - **Unicamente si 68/68 + golden pasan** se merece pensar en on-by-default.
6. Si el camino vecq resulta ser un callejon (ej: el layout de PTQ1_0 no lo
   permite sin repack en warmup), decirlo como veredicto y proponer el repack
   offline en cuantizacion. "No se pudo, y por que" es un resultado valido.

## Barato y sin recompilar (hacer antes que nada, 0 CPU)

Barrido de knobs que ya existen, midiendo en produccion (in-suite miente, S5):

| knob | valores | linea |
|---|---|---|
| `GGML_PTQ1_0_WG` | 64,128,256 | ggml-vulkan.cpp:5288 |
| `GGML_PTQ1_0_ROWS` | 1,2,4 | :5296 |
| `GGML_PTQ1_0_MATVEC` | stdq,sub16,sub16hyb | :5253 |
| `GGML_VK_DMMV_REDUC` | 0,1,2 | :5269 |

`$env:VAR = "..."` antes de levantar el server. Empezar por WG x ROWS (9 combos),
temperatura 0, 256 tokens, 2 corridas. Un combo que gane >3% es free win sin
tocar un shader.

## Reglas

- Un escritor por arbol; claim vigente antes de escribir (protocolo en `03_`).
- Los 3 archivos sin commitear (2 shaders + `src/models/qwen35.cpp`) son los que
  hacen funcionar esto: **nunca** `git checkout .` / `git clean -fd` sin permiso.
- No tocar `night_campaign.ps1` ni los modelos.

## Addendum (11:10) - no es un bug de 6 lineas: son TRES, y hay oraculo

Derivado contra las dos fuentes VALIDADAS que leen los mismos bloques:
`ptq1_0.glsl:15-45` (lo usan dequant/mul_mm, pasa 68/68) y
`mul_mat_vec_ptq1_0.comp:57-61` (el matvec LUT que hoy da los 8.64 t/s).
Ambas coinciden: para e>=120, `b = qh[t & 1]`, `n = t >> 1` (t = e-120).

### D1 - mapa de lanes mal (lineas 666-678)
Los 8 tritos altos son **2 por posicion alternando bytes**, no 4 con el mismo
indice. `trits4(bytes, n)` fija `n` para las 4 lanes, así que NO se puede
expresar en una sola llamada. El codigo actual (`hi0 = trits4(qh_bytes, 0)`,
`hi1 = trits4(qh_bytes, 1)`) acierta las lanes 0-1 y falla las 2-3 de cada uno.
Forma correcta: 4 llamadas (n=0..3) y mezclar lanes a mano.

### D2 - packing SIN mascara de 8 bits (lineas 680-683) - el peor
`trits4` devuelve `i32vec4(...) - 1` => valores CON SIGNO {-1, 0, 1}
(linea 629 y el `- 1` de 624-628). Y el packing es
`lo0.x | (lo0.y << 8) | (lo0.z << 16) | (lo0.w << 24)` sin `& 0xFF`.
`-1` es `0xFFFFFFFF`, entonces un solo trit 0 en cualquier lane convierte la
palabra entera en `0xFFFFFFFF` => las 4 lanes valen -1. **Cualquier bloque con
un trit=0 da mal**, no solo los elementos 120..127. Fix: `(v & 0xFF)` por lane
antes del `|`.

### D3 - `.comp` y `.glsl` desincronizados
`mul_mat_vecq.comp:29-30` dice "No LUT needed" porque le borraron
`ptq_trit_lut`; el `.glsl` la seguia llamando (eso fue el error de build de
esta manana). Elegir UN camino (LUT o aritmetica) y dejar los dos de acuerdo.

### Alcance real y oraculo (no adivinar)
`repack4` (633-684) necesita reescritura, no un parche de 6 lineas: hay que
respetar el contrato de orden que define `ebase = (ib_a & 3) * 32 + b_qs * 16`
y el layout de `cache_b_qs` (B = q8_1 firmado, `dot4packed_i8x4`).
Oraculo mecanico, cero adivinanza: correr `test-backend-ops` MUL_MAT con
`GGML_PTQ1_0_MMVQ=1`. Hoy eso falla; cuando pase 68/68 el interleave esta bien.
El diff de la suite dice QUE lane esta mal, asi que se itera por datos.

### Impacto en la decision
Esto no cambia el ranking (sigue siendo la tarea 1), pero sube el costo real de
"6 lineas" a "re-escribir repack4 + validar". Y refuerza lo otro: con `-np 3`
en 1.99x ya hay 2x banco sin tocar un shader.
