# REVIEW 2026-09-25 (noche, sesión nueva) — 4 hallazgos, todos verificados en disco

Sesión entrante pidió "qué puedo aportar". Leí HANDOFF -> KERNEL_HEADROOM ->
RGP -> SESSION_CONTEXT y verifiqué el árbol de build. Todo lo de abajo es lectura
de disco + un `ninja -n` + un intento de compile de un solo `.obj`.

## F1 (BLOQUEANTE, nuevo): el árbol NO compila, y el commit "baseline" tampoco

`ninja -C C:/src/llama.cpp/build src/CMakeFiles/llama.dir/models/qwen35.cpp.obj`
muere en vulkan-shaders-gen:

    ERROR: <tmp>.glsl:4911: 'qh0' : undeclared identifier
    ERROR: <tmp>.glsl:4911: '' : missing #endif
    vulkan-shaders-gen: one or more shaders failed to compile

Causa exacta: `ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vecq_funcs.glsl`,
rama `else { // ebase = 112 }` de `repack4`:

- líneas 674-675 declaran `qhw` / `qh_bytes`;
- líneas 681-688 siguen usando `qh0` / `qh1`, que ya no existen;
- los comentarios 678-680 ("Fix: ... need to interleave properly / Reconstruct
  correctly") = edición INCOMPLETA del agente opencode free-tier (`.comp` con
  mtime 15:45; el log del agente se cortó 16:48).

`git status` está limpio => el estado roto está DENTRO de `e728b26` ("baseline
pre-opencode", 16:43). O sea: el commit de referencia no construye.

Reparo propuesto (1 comando, nada más):

    Copy-Item C:\src\llama.cpp\ggml\src\ggml-vulkan\vulkan-shaders\mul_mat_vecq_funcs.glsl.bak-20260925b `
              C:\src\llama.cpp\ggml\src\ggml-vulkan\vulkan-shaders\mul_mat_vecq_funcs.glsl

Los `.bak-20260925[b]` (690 líneas, idénticos entre sí) usan `qh0` 5 veces PERO
lo declaran (compilaban); el actual lo usa 10 veces con la declaración borrada.
El `.comp` de 194 líneas NO rompe el gen (0 `qh0`, `#if` balanceados) -> se queda.
Aclaración: el qh-vecq de PTQ1_0 queda como bug SEMÁNTICO abierto (no de build):
hace falta el interleave correcto de los 8 trits altos, no adivinarlo.

## F2 (el 2× que nunca se midió): el fix de MTP NO estaba compilado

El veredicto "PTQ1_0-mtp-lean + draft-mtp INCOMPATIBLE con nuestro b10709,
requiere el build del autor (rev 285542d, CUDA-linux)" se apoyó sobre un binario
que **nunca tuvo el parche**:

| artefacto | mtime |
|---|---|
| `build/src/CMakeFiles/llama.dir/models/qwen35.cpp.obj` | **22/09 00:30** |
| `build/bin/llama-server.exe` | **25/09 02:18** |
| `src/models/qwen35.cpp` (parche +15 líneas Hadamard-inverse) | **25/09 19:21** |

Ni el `.obj` ni el server contienen el fix. Peor: la slice `MTPLean` que
`HANDOFF` §6.4 deja "ARMADA, corre esta noche" usa ese mismo `llama-server.exe`
de 02:18 -> va a reproducir el falso negativo y la campana va a registrar
`mtp:lean-draft-mtp = server_failed` como si fuera un resultado.

Y la premisa "requiere el build del autor" es **falsa**: `data/campaign/pr-205.json`
trae `state=closed merged=True merged_at=2026-09-21T16:22:58Z
merge_commit=422590f5d4bc`: el maintainer MERGEÓ exactamente este fix (pr-217,
cerrado sin mergear, es la misma idea). Base = `9a9394a89` = nuestro fork. O sea:
15 líneas en `src/models/qwen35.cpp`, ya aplicadas en el tree, que solo
necesitan compilador.

Orden para cobrarlo (sin GPU hasta el paso 4):
1. reparar F1 (si no, nada builda);
2. `ninja -C build` completo -> **relinkear `llama-server.exe`** (la regla ya
   está en HANDOFF §8: "relink llama-server TOO"; esta vez no se cumplió);
3. `llama-server -m <mtp-lean> --spec-type draft-mtp --spec-draft-n-max 2` y leer
   si el error Hadamard desaparece (CPU-only hasta acá);
4. recién entonces el A/B de t/s.

Lo que está en juego (números del autor, PR #221, PTQ1_0 + MTP head en una 4070):
51 -> 60 -> **103 tok/s** greedy (121 en code) por meter el draft head compartido.
En nuestra pared (185 GB/s) no llega a 2×, pero el rho de PR #205 es el argumento:
drafter sidecar = rho 0.43 (aún con 40% de aceptación es PÉRDIDA: 5.16 vs
16.6 t/s); MTP dentro del target = rho 0.06 y el mismo head pasa a ser ganancia.

## F3 (causa raíz de tres veredictos falsos): no hay guard de frescura de build

Evidencia de hoy, midiendo mtimes:

- `test-backend-ops.exe` = **15:04**, `llama-server.exe` = **02:18**. Dos árboles
  distintos, dos sets de kernels, usados en el mismo informe (la tabla vecq A/B
  viene del test-backend-ops; el GPU-sum de 53 ms viene del server).
  `mul_mat_vec_ptq1_0.comp` se editó **15:45**, después de los dos.
- Cuando `ninja` muere en el paso de shaders deja los binarios viejos en su sitio:
  la medición "post-cambio" es en realidad la del binario viejo, sin ningún aviso.
  Misma familia de error que ya costó dos sesiones: vecq-era-dead-code (09-24),
  glsl pegado-dos-veces (09-22), y hoy esto.

Aporte concreto (no toca GPU ni modelos): `scripts/build_fresh.ps1` - compara el
mtime de `src/` y `ggml/src/ggml-vulkan/` (`.comp`/`.glsl` + header generado)
contra `build/bin/llama-server.exe`, `build/bin/test-backend-ops.exe` y los `.obj`.
Salida `FRESH` / `STALE <archivo> más nuevo que <binario>`; exit 1 si STALE.
Enchufable como preflight en `d1_perop_profile.py`, `night_campaign.ps1` y
`rgp_capture.ps1`; y cada JSON de medición guarda mtime/hash del binario usado
(el provenance ya existe, `data/provenance/build-hashes-20260924.txt`, solo falta
el check automático). Regla propuesta: **ningún número entra al knowledge pack si
su binario está STALE**. (Zona reclamada: `local-coding/scripts/*.ps1` es de
`ses_f253`; no lo escribo hasta que el claim cierre.)

## F4 (el multiplicador que las propias notas midieron y no cobraron): `-np >= 2`

`data/campaign/20260925/perf-q4_0*.txt`, mismas formas, mismo binario:

| forma | n=1 | n=2 | n=4 | n=8 |
|---|---|---|---|---|
| m=17408 k=5120 | 236.6 us | **237.9 (+0.5%)** | 366.7 (+55%) | 803.9 (+240%) |
| lm_head 248320x5120 | 3311.7 us | **3325.1 (+0.4%)** | 5187.0 (+57%) | 11296.5 (+241%) |

En una tarjeta colgada de bandwidth, verificar N secuencias en un paso cuesta casi
lo mismo que una: **n=2 = ~2× de throughput agregado; n=4 = ~2.6×**. La sesión de
ayer lo vio y lo usó solo para razonar spec-decode ("batch-2 verification es casi
gratis"). Para el caso de uso real —2 o 3 agentes picando el MISMO server— no hay
que tocar un kernel: es `-np 2` con KV chico. Es el 2-3× que el user intuye, a un
flag de distancia.

Advertencias honestas antes de celebrarlo:
- Solo paga con >=2 secuencias simultáneas. Un agente solo no gana nada (para eso
  está spec-decode; y son multiplicadores que se **multiplican**: verificar k
  drafts ya es n=k).
- Vulkan cambia de kernel cuando n>1: MMVQ/vecq es camino de n=1 (el allowlist
  propio lo cubre solo hasta n=1). A n=2, TQ2_0 puede caer a `mul_mat_vec_f`
  (f32 LUT) y comerse la ganancia. Por eso es **una medición de ~20 min, no una
  promesa**: server con `-np 2 -c 4096 -fa on -ctk q4_0 -ctv q4_0`, dos prompts
  concurrentes, leer `/metrics` + `slots`, y repetir con `GGML_VK_DISABLE_MMVQ`
  para cazar el salto de kernel.
- RAM: la máquina tiene **16 GB totales y 3.4 GB libres ahora**. El gate de la
  slice `MTPLean` pide **11 GB libres** -> casi nunca se va a cumplir mientras el
  user trabaja (otro no-op silencioso). Bajarlo a ~7-8 GB o correrlo de noche.

GPU, ni procesos — hay 3 procesos `opencode` vivos (19:46/20:31) y la regla es
un escritor por árbol. Las únicas acciones con efecto: `ninja -n` (dry-run) y un
intento de compile de un solo `.obj` que abortó en el paso de shaders sin dejar
cambios (los binarios siguen en 02:18/15:04). **Disclosure**: ese intento corrió
la re-configuración de CMake dentro de `C:/src/llama.cpp/build/` (zona reclamada
por `ses_f253` en `BRIEFS/CLAIMS.md`); verificado después: `llama-server.exe`
02:18:50, `test-backend-ops.exe` 15:04:41, `qwen35.cpp.obj` 22/09 00:30 y
`git status` sigue con las mismas 2 modificaciones previas (`opencode.json`,
`src/models/qwen35.cpp`). Ningún archivo de código o shader fue escrito.
Claim propio: una línea appendeada en `BRIEFS/CLAIMS.md` (23:40, DONE).

## F5 (la respuesta a D2 ronda 2 ya está descargada): PR #218 / #221

`data/campaign/pr-218.json` (abierto, del maintainer; CUDA/Ampere; 1.5× decode
PTQ1_0) responde la pregunta que la sesión 09-24 dejó abierta ("el muro es el
patrón de acceso, no el ALU"). Traducible a nuestro GLSL:

- El sobrecosto no es la LUT ternaria ni el int-dot: **son los loads de
  activaciones** ("removing the activation loads makes 1..8 columns cost the same,
  so the loads are the cost") y **la subutilización de lanes** ("88 of every 128
  threads sat idle because one thread owned a column").
- Lo que funcionó: **cambiar el layout** de los bloques PTQ1_0 (8 piezas alineadas
  de 16 B + 1 pieza de 16 B de scales, lanes adyacentes) + kernel dedicado con
  utilización plena de lanes (4 filas/hilo por bloque-K, parciales en shared, un
  warp por fila/columna). Resultado: 201 us para 1/2/3/4 columnas vs Q4_0
  101/102/115/151 — ~2× sobre el kernel anterior del propio fork, en la misma
  forma `ffn` que nosotros medimos.
- Lo que NO funcionó (para no repetir): warp tiles con broadcast, más filas por
  hilo, launch bounds apretados, `mma.sync.m16n8k16.s8` -> no le ganaron a dp4a.
  Nuestro equivalente ya medido y refutado: E2 (más trabajo por hilo) = regresión;
  el footprint tiene que venir de más hilos, no de más trabajo.
- Nuestro síntoma encaja 1:1: bloque PTQ1_0 de **28 bytes** = 56 B/warp
  desalineados. El PR dice: no arregles el walk, arreglá el **layout**.
- #215 (hybrid PTQ1_0 dispatch) y #221 (`GGML_CUDA_BATCH_INVARIANT`, FA q4_0/q8_0
  in-place para 262K) son los otros dos a leer: batch-invariance es lo que hace
  que spec-decode dé salida idéntica a greedy, y el FA in-place es el camino del
  contexto largo sin matar VRAM.

## Qué toqué y qué no

No toqué código ni shaders ni modelos, ni GPU, ni procesos — `C:/src/llama.cpp/**`
está reclamado por `ses_f253` en `BRIEFS/CLAIMS.md` y la regla es un escritor por
árbol. Acciones con efecto: `ninja -n` (dry-run) y un intento de compile de un solo
`.obj` que abortó en shaders. **Disclosure**: ese intento re-corrió CMake dentro de
`C:/src/llama.cpp/build/`; verificado después: `llama-server.exe` 02:18:50,
`test-backend-ops.exe` 15:04:41, `qwen35.cpp.obj` 22/09 00:30 y `git status` con
las mismas 2 modificaciones previas (`opencode.json`, `src/models/qwen35.cpp`).
Escrito: este archivo + una línea appendeada en `BRIEFS/CLAIMS.md` (23:40, DONE).

Tres decisiones del user desbloquean valor real:
1. **"revertí el vecq"** -> aplico el copy de F1 y verifico `ninja` verde (CPU-only).
2. **"relinkeá y probá draft-mtp"** -> F2 pasos 2-3 (termina con un server vivo
   ~5 min; necesita GPU, con el user enterado). Responde también la pregunta
   abierta del `BRIEFS/02` ("¿MTP-lean ahora o en el slice de 02:30?"): ninguna de
   las dos, hasta que el binario tenga el parche.
3. **"dale con build_fresh"** -> escribo `scripts/build_fresh.ps1` (F3) + 3 líneas
   de preflight. Requiere que el claim de `ses_f253` sobre `scripts/*.ps1` cierre.
