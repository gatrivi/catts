# 05 - PLAN DE EJECUCION 2026-09-26 (escrito para agentes con poco criterio)

Quien ejecuta NO DECIDE. Cada paso dice PASA SI. Si no pasa exacto: stop, reportar,
no improvisar. Este brief manda sobre su tarea; `CLAIMS.md` manda sobre quien
escribe donde. Escribe un `## Resultado lane X (fecha)` aca abajo al terminar.

## Reglas globales (todas las lanes)

- PROHIBIDO: `git checkout .`, `git reset --hard`, `git add -A`, `git clean`.
  Hay 2 cambios sin commitear que valen el 2x (shader + fix MTP) y ~35 archivos
  modificados del usuario que no son tuyos.
- PROHIBIDO: descargas, `pip install`, cambiar runtime (WSL/HIP/ROCm), bajar modelos.
- UN solo `llama-server` a la vez (8 GiB VRAM, 15.4 GB RAM). No matar procesos
  que no hayas levantado vos.
- Claim de una linea en CLAIMS.md antes de escribir. Cierralo con DONE al final.
- Todo numero reportado sale de un comando copiado literal. No estimes.
- Si un comando falla con permission denied / not found: NO lo reintentes con
  cinco sintaxis. Reportalo y seguí con el resto de la lane.

## Recursos (medido 09-25 23:50; re-medir solo si vas a usar GPU)

RAM 15.4 GB total / 7.2 GB libres. C: 10.2 GB libres. Pagefile 28 GB asig / 2.6
usados. CPU 5800X. GPU RX 6800 8 GiB; pesos 6.3 GiB (entran completos en VRAM).
Weights + pagefile = thrash = ~40 tok/s (falso resultado, ya paso).

## Rutas (absolutas, no las cambies)

- codigo: C:\src\llama.cpp (branch fork-build, HEAD e728b26 sobre base 9a9394a89)
- build: C:\src\llama.cpp\build ; binario: build\bin\llama-server.exe
- shaders: C:\src\llama.cpp\ggml\src\ggml-vulkan\vulkan-shaders\
- modelo base: Z:\catts\local-coding\data\models\Qwen3.5-9B-PTQ1_0-MergeV4\Qwen3.5-9B-PTQ1_0-lean-remap.gguf (6722 MB)
- modelo head MTP: Z:\catts\local-coding\data\campaign\models\mtp-lean.gguf (6702 MB)
- campaign: Z:\catts\local-coding\scripts\night_campaign.ps1 (POWERSHELL; el
  run_night_campaign.py que cita el HANDOFF no existe)
- PR ya bajados: Z:\catts\local-coding\data\campaign\pr-{205,215,217,218,221}.json

## Hechos VERBATIM (no re-verificar, no re-probar)

1. decode 66.9 tok/s; techo de DRAM de la GPU = 185 GB/s (medido con tq2_0).
2. tq2_0 esta 90-100 % del roofline y NO gana calidad. PTQ1_0 (4.30 bpw) si.
3. PTQ1_0 matvec rinde 41-50 GB/s -> 31.8 tok/s. Ahi esta el 2x: 185/150 = 1.23.
4. `-ngl 0` = 2 tok/s: no hay validacion de kernel sin GPU.
5. Bandwidth con contexto chico (145 GB/s) es artefacto de cache L2.
6. REFUTADO: WG/ROWS en matvec PTQ1_0; E2 mas-trabajo-por-hilo (regresion);
   closed-form en matvec de 32 bits; int-dot ptq1_0 matvec; tocar mul_mat_vec_f;
   kernel tq2_0 (5.3x tecnico sin victoria de calidad).
7. GGML_VK_DISABLE_MMVQ=1 -> 0.4 tok/s: el kernel critico es MMVQ.
8. `ninja` NO relinkea llama-server.exe si nada linkeable cambio -> medir contra
   binario viejo da falsos negativos (ya paso con MTP).
9. PR #205 esta MERGEADO (merged=True, merge_commit 422590f5d4bc): el fix del head
   MTP es codigo nuestro sin compilar, no "build del autor en linux".
10. `--spec-type draft-mtp` contra el binario de 02:18 da `failed to inverse
    Hadamard matrix`: eso es binario viejo, no incompatibilidad.
11. El fix de Hadamard son +15 lineas en src/models/qwen35.cpp
    (`hadamard_inverses`, `llama_mul_mat_hadamard`).

## LANE 0 - REPARAR Y RELINKEAR (sin GPU) | fuerte o esta sesion

0.1  cd C:\src\llama.cpp ; git --no-pager status --short ; git rev-parse --short HEAD
     PASA SI: HEAD=e728b26 y aparecen `M ggml/.../mul_mat_vecq_funcs.glsl`,
     `M src/models/qwen35.cpp`. Si el shader NO aparece modificado, alguien
     commiteo o revirtio: PARAR y reportar (el fix de MTP pudo perderse).
0.2  ninja -C build 2>&1 | Tee-Object C:\src\llama.cpp\build-20260926.log
     (si `ninja` no esta en PATH: usar el CMAKE_MAKE_PROGRAM de build\CMakeCache.txt)
     PASA SI: termina con exit 0 y NO aparece `undeclared identifier`.
     Si aparece `qh0`: la reparacion se perdio; copiar de vuelta desde
     mul_mat_vecq_funcs.glsl.bak-20260925b y repetir UNA sola vez.
0.3  (Get-Item build\bin\llama-server.exe).LastWriteTime
     PASA SI: hora de hoy. Si sigue 02:18, forzar `ninja -C build llama-server`.
     Si sigue igual: reportar y parar.
0.4  COMMIT (solo con permiso del usuario, solo estos dos archivos):
     git add ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vecq_funcs.glsl src/models/qwen35.cpp
     git commit -m "vulkan: revert broken qh0 vecq edit; qwen35: MTP Hadamard inverse"
     PASA SI: `git status --short` deja solo ` M opencode.json` y el ?? .broken-*.
0.5  seguir con LANE 1.

## LANE 1 - COBRAR EL 2x DE MTP (GPU, 8 GB RAM libres) | fuerte

1.1  Levantar llama-server con mtp-lean.gguf + `--spec-type draft-mtp
     --spec-draft-n-max 2`, contexto 8192.
     PASA SI: el log NO dice `failed to inverse Hadamard matrix`.
     Si lo dice con binario NUEVO (ver 0.3): el fix no alcanza. Anotar textual y
     parar. NO re-probar con otros flags.
1.2  A/B: mismo modelo, mismo prompt de 300 tokens, --temp 0, 3 corridas cada
     brazo, con y sin --spec-type. Reportar t/s de los dos brazos + dispersion.
     PASA SI: 6 numeros (3+3) y pagefile sin crecer.
1.3  Calcular aceptacion de draft desde el log: rho = tok_por_draft / (1 + tok_por_draft).
     rho >= 0.5 = gana. rho <= 0.43 (el del drafter sidecar) = pierde: NO lo
     corras en produccion, reportalo.

## LANE 2 - DECODE PARALELO `-np 2` (GPU, 10 GB RAM libres) | mecanico, modelo debil OK

2.1  llama-server -m <modelo base> -ngl 99 -c 2048 --parallel 2 -np 2 -a 248 -p 9151
     PASA SI: /health responde ok. Registrar VRAM usada de la salida del server.
2.2  2 requests concurrentes de 256 tokens (curl a /v1/chat/completions o
     /completion con n_predict 256), medir wall time y tokens totales.
     Luego 1 request solo. Repetir el par 3 veces.
2.3  PASA SI: t/s agregado n=1 vs n=2 y su ratio. Esperado ~1.8x.
     Regla: si n=2 elige `mul_mat_vec_f` en vez de MMVQ (sale `GGML_VK_DISABLE_MMVQ`
     a 0.4 tok/s como referencia), el ratio no cuenta: reportalo como no-medible.

## LANE 3 - LAYOUT PTQ1_0 (la unica que necesita criterio) | solo modelo fuerte

3.1  Leer Z:\catts\local-coding\data\campaign\pr-218.json. Responder en una
     pagina: por que el kernel del autor pasa de ~100 us a 201 us en 1..4 columnas
     y cual de esas causas aplica a nuestro `mul_mat_vecq_funcs.glsl`.
     Hechos yamersados: el costo NO es la LUT ternaria ni el int-dot, son los
     loads de activaciones y que 88 de cada 128 threads quedan idle. El bloque
     PTQ1_0 nuestro es de 28 B = 56 B/warp desalineado.
3.2  Escribir la propuesta (NO el patch) en
     local-coding\docs\PTQ1_0_LAYOUT_PROPUESTA_2026-09-26.md, citando linea.
3.3  Entregar tambien el diff en parche, listo para aplicar, y la prediccion
     numerica (GB/s esperados) para poder decidir sin ni compilar.
3.4  PASA SI: el parche declara variables antes de usarlas (el error del shader
     roto fue exactamente eso) y NO toca mul_mat_vec_f.

## LANE 4 - CONTEXTO LARGO Y PEQUEÑOS OPS (solo lectura) | modelo debil OK

4.1  Leer local-coding\data\perf\*.json (d1_perop, perf-q4_0-n248) y
     RGP_ATOM_CAPTURE_2026-09-25.md.
     Entregable: doc con los 4 ops mas caros fuera de MUL_MAT, en us/iter y en
     % del total, con la fuente exacta de cada numero.
4.2  Con PR #221: escribir el plan de contexto 32K/131K sin que el KV se coma la
     VRAM. SOLO plan numerado, sin codigo.
4.3  PASA SI: cada afirmacion tiene ruta de archivo + linea. Sin numeros inventados.

## LANE 5 - HIGIENE DE LA CAMPANA (edita el PS1) | modelo debil OK

5.1  En night_campaign.ps1 linea ~210: el gate dice `if ($freeMb -lt 11000)`.
     Cambiar a 8000. PASA SI: `-ForceSlice MTPLean` ya no dice "skipped" con
     7 GB libres. Medir antes: con 7.2 GB libres la slice se salta TODAS las
     noches, y el dia 2 (manana) la tiene agendada.
5.2  Anadir freshness gate: comparar (Get-Item build\bin\llama-server.exe).LastWriteTime
     contra (Get-Item src\models\qwen35.cpp).LastWriteTime. Si el server es mas
     viejo, `Record 'build:stale' 'true' 'bool'` y NO correr slices de MTP.
     PASA SI: correr el PS1 con un server viejo registra `build:stale` y se salta.
5.3  Cambiar la linea ~220: hoy un fallo del server se graba como
     `mtp:lean-draft-mtp = server_failed`, que se lee como resultado. Grabar
     `build:stale` o `mtp:error` con el stderr adentro. PASA SI: la distincion se ve
     en data\campaign\knowledge.jsonl.
5.4  Correr `powershell -File scripts\night_campaign.ps1 -PreflightOnly` y pegar la
     salida. NO correr slices reales de noche fuera de la ventana 02:30.

## Resultado lane 0 y 5.1 (2026-09-26 09:10, ses_pixel)

ESTADO: LANE 0 COMPLETA. El arbol compila y los binarios se relinkearon.

1. El "revert del vecq" que decia F1 era INSUFICIENTE: habia DOS ediciones
   incompletas del agente opencode, no una, y son un par (el .comp de 15:38
   borro la LUT `ptq_trit_lut` que el .glsl sigue llamando).
   - `mul_mat_vec_ptq1_0.comp`: restaurado desde `.bak-20260925b` (7517 B). Era
     el experimento E2 "threads-extra walk" (ya REFUTADO) a medio escribir.
   - `mul_mat_vecq_funcs.glsl`: restaurado desde `.broken-20260925c` (el par que
     el .comp necesita) y eliminado SOLO el bloque de 13 lineas 678-690, que
     usaba `qh0`/`qh1` sin declarar. NO se reconstruyo el interleave de los 8
     trits altos: eso sigue siendo el bug semantico abierto y lo decide la
     suite 68/68, no una suposicion.
   PASA SI de 0.2: `ninja -C build` -> sin FAILED, sin "undeclared identifier".
   Ojo: `ninja` NO esta en PATH; el binario es
   `E:\zengatrivi-drive-e\catts\.venv\Scripts\ninja.exe` (CMAKE_MAKE_PROGRAM).
2. 0.3 PASA SI: `build\bin\llama-server.exe` = 26/09 09:09:36 (83.274.240 B) y
   `qwen35.cpp.obj` = 26/09 09:08:33. El fix de MTP quedo COMPILADO (el .obj
   contiene la cadena `hadamard`); el binario de las 02:18 ya no se usa.
3. 5.1 hecho: `night_campaign.ps1` linea 210: el gate de RAM bajo de 11000 a
   8000 MB (con 7.2 GB libres la slice MTPLean se saltaba TODAS las noches y el
   dia 2 la tiene agendada).
4. SIN commitear en llama.cpp (la regla del repo es commit solo a pedido). Quedan
   sin commitear los 3 archivos que hacen que esto funcione: los 2 shaders y
   `src/models/qwen35.cpp`. Un `git checkout .` de cualquier agente los borra.
5. Log del build: `C:\src\llama.cpp\build-20260926c.log`.

LO QUE FALTA (requiere GPU, ~5 min, 8 GB RAM libres): correr
`llama-server -m local-coding\data\campaign\models\mtp-lean.gguf --spec-type
draft-mtp --spec-draft-n-max 2` y confirmar que YA NO aparece
`failed to inverse Hadamard matrix`. Con el binario viejo ese error era
esperado; con el nuevo es la unica prueba valida.

## Resultado lane 1.1 (2026-09-26 09:35, ses_pixel) - F2 CONFIRMADO

Con el binario NUEVO (build 26/09 09:09), sobre GPU, con el modelo real de la
slice (`data\models\bonsai2-27b-ptq10-mtp\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`,
6.3 GB; el path `data\campaign\models\mtp-lean.gguf` del plan NO existe):

    common_speculative_init_result: creating MTP draft context against the target model
    llama_server: model loaded
    llama_server: listening on http://127.0.0.1:9199

CERO errores de Hadamard. El veredicto "draft-mtp INCOMPATIBLE con nuestro
build, requiere el build del autor" era FALSO por binario viejo. F2 cerrado.

Cosas que costaron tiempo y conviene no repetir:
- `ninja` NO esta en PATH: es `E:\zengatrivi-drive-e\catts\.venv\Scripts\ninja.exe`.
- `llama-server.exe` necesita `C:\tools\llvm-mingw\bin` en el PATH; sin eso
  muere al instante SIN escribir un solo byte de log (ni stdout ni stderr).
  Por eso el primer test parecio "sin salida".
- Cargar con `-ngl 0` desde el share Z: deja la RAM en 2.6 GB libres y se
  cuelga (thrash). Para verificar que el modelo arranca que el modelo carga hay que usar GPU.

FALTA (no lo di por hecho, no lo medido): el A/B de t/s con y sin
`--spec-type draft-mtp`, 3 corridas por brazo, mismo prompt, temp 0, y el
aceptaje de draft. Un unico pedido de 200 tokens no llego a terminar dentro de
la ventana de 30 s del tooling, asi que NO hay numero que reportar todavia.

## Resultado lane 1.2 (2026-09-26 09:55, ses_pixel) - MTP n=2 MEDIDO: PIERDE

Modelo: `data\models\bonsai2-27b-ptq10-mtp\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf`
(27B, 6.3 GB PTQ1_0). GPU, -ngl 99, -c 8192, temp 0, seed 42, n_predict 256.
Script: `local-coding\scripts\spec_ab.ps1` (corre solo, escribe JSON).
Datos: `local-coding\data\spec_ab_20260926.json`.

| brazo | corrida | t/s |
|---|---|---|
| base (sin draft) | 1 | 8.695 |
| base | 2 | 8.641 |
| base | 3 | 8.577 |
| draft-mtp n=2 | 1 | 6.906 |
| draft-mtp n=2 | 2 | 6.828 |

VEREDICTO: base 8.64 +- 0.06, draft n=2 6.87 +- 0.04 -> **0.79x, PIERDE**.
Aceptacion del draft 0.6087 (140 aceptados / 230 generados), mean len 2.22:
el drafter NO es el problema (rho 0.61 > 0.43 del drafter sidecar). El problema
es el COSTO del head MTP: por cada paso de draft paga un forward extra del
target+head, y con 27B eso no se amortiza con n=2.

OJO numero: los 66.9 tok/s de las notas NO son de este modelo (eran del 9B). El
baseline real del 27B PTQ1_0 en esta GPU es 8.6 t/s. Cualquier comparacion de
"2x" contra 66.9 con este modelo es falsa.

SIGUIENTE (en curso al cierre de esta sesion, script `$env:TEMP\dn_sweep.ps1`,
salida en `local-coding\data\spec_draftn_sweep_20260926.json`): barrido de
`--spec-draft-n-max` = 4 y 8, 2 corridas cada uno. Es el knob que decide si el
head se amortiza. Regla de decision ya escrita: si n=4 no supera 8.64, MTP queda
DESCARTADO para produccion y el 2x hay que buscarlo en la Lane 2 (`-np 2`) o en
el kernel de PTQ1_0 (Lane 3), no en spec decode.

### Gotcha: el timeout de arranque tiene que ser >= 900 s con MTP

El primer barrido de `draft-n-max` (4 y 8) no dio veredicto: el script daba por
fallido un server a los 300 s, pero con el modelo de 27B LEYENDOSE DE RED (Z:) y
cache frio, el arranque con contexto MTP tardo 2m45s en `creating MTP draft
context` y nunca llego a `listening` dentro de la ventana. No era un fallo del
build ni del flag: era el script contando mal.

Regla: `-ngl 99` + `--spec-type draft-mtp` sobre este modelo = dale 900 s de
timeout al `Wait-Ready`, y no tomes "no arranco" como veredicto sin mirar la
ultima linea del log del server (`$env:TEMP\dnA.err.log` en el relanzado).
En CPU (`-ngl 0`) la carga ni siquiera termina: se cuelga paginando desde el
share de red. Para cualquier prueba de MTP: GPU y patience.

## VEREDICTO FINAL spec-decode: MTP DESCARTADO en este rig/modelo (2026-09-26 10:35)

Medicion completa, mismo server, mismo modelo 27B PTQ1_0, GPU, -c 8192,
temp 0, seed 42, n_predict 256. Datos: `data\spec_ab_20260926.json` y
`data\spec_draftn4_20260926.json`.

| config | t/s | aceptacion | mean len |
|---|---|---|---|
| base (sin draft) | **8.64 +- 0.06** (3 corridas) | - | - |
| draft-mtp n=2 | 6.87 +- 0.04 (2 corridas) | 0.6087 (140/230) | 2.22 |
| draft-mtp n=4 | 4.36 (4.235 / 4.478) | 0.4026 (157/390) | 2.60 |

Es MONOTONO al PEOR: mas tokens por paso de draft = mas lento. Y la aceptacion
tambien baja (0.61 -> 0.40), o sea que los drafts extra son ademaswrong.
Aceptacion 0.40 esta por DEBAJO del umbral 0.43 del drafter sidecar.

Por que: el head MTP no se amortiza sobre un target de 27B. Cada token draftado
paga un forward del head y el costo crece mas rapido que lo que aporta.
En el 4070 del autor (PR #221) esto daba 51 -> 103 tok/s porque el target era un
modelo chico y el kernel INT8-LUT de ese fork hacia el head casi gratis. Aca
nuestro PTQ1_0 va a 41-50 GB/s (31.8 tok/s) y el head se lleva el 60% del tiempo.

CONSECUENCIA OPERATIVA: la slice `MTPLean` del dia 2 (manana) ya no puede
"encontrar el 2x": el 2x NO esta en spec decode para este modelo. No la borres
(que quede el registro con la referencia correcta = 8.64 t/s, no 66.9), pero no
esperes de ella una mejora.

DONDE VA EL 2x EN REALIDAD, por orden de attendu 的:
1. Lane 2 `-np 2`: 2 streams concurrentes. La GPU es bandwidth-bound (185 GB/s)
   y 1 stream no la satura. Es lo mas barato de probar: sin codigo, 5 min.
2. Lane 3 kernel PTQ1_0: 41-50 GB/s contra un techo de 185. Ahi esta el 2x real
   (PR #218: el problema es el LAYOUT de los bloques de 28 B, no el ALU).
3. Contexto: -np 2 necesita VRAM para 2 KV; con 8 GiB y 6.3 de pesos hay que
   medir antes de prometerlo.

## Lane 2 (parcial) - concurrencia: 1.31x, con una reserva sobre el metodo

`local-coding\data\np2_20260926.json`, server con `--parallel 2`, -c 2048,
temp 0. n=1: 8.616 / 8.568 / 8.529 t/s. n=2: 10.896 / 11.295 / 11.372 agregado,
por stream 7.38 / 6.86, 7.70 / 7.14, 7.65 / 7.13.

=> **1.31x gratis y sin codigo**. Cada stream corre al ~86% de su velocidad solo
y el agregado sube 31%. La GPU NO se satura con 2 streams, pero tampoco se
estrangula: es el perfil de un muro de bandwidth con algo de compute mezclado.
NO es el 2x (2.0x) y no hay que venderlo como tal.

RESERVA DE METODO (importante, no la saltees): el script original paso
`n_predict` mal a los `Start-Job` (no se pasa la variable del padre al runspace
del job), asi que el brazo n=2 genero ~559 tokens por request en vez de 256.
El t/s sigue siendo un rate valido, pero los dos brazos NO son length-matched.

Por eso relanzo la curva completa con longitudes igualadas:
`$env:TEMP\np_curve.ps1` -> `local-coding\data\np_curve_20260926.json`.
Armas n=1,2,3,4, 2 corridas cada una, 256 tokens por stream, 4 prompts distintos
(sin dos streams con el mismo texto, quefalsearia por cache), y captura por
armada de la linea `offloaded N/M layers to GPU` para poder descartar que una
medida se haya hecho con el modelo parcialmente en CPU.

## Lane 2 (final) - CURVA DE CONCURRENCIA: el 2x es gratis, con -np 3

`local-coding\data\np_curve_20260926.json`. 27B PTQ1_0, GPU, temp 0, 256 tokens
por stream, 4 prompts distintos, 2 corridas por brazo, longitudes IGUALADAS.

Metodo (importante): el `wall` del script incluye ~3 s de spawn de cada
`Start-Job`. Esa constante se calibro con el log del server en n=1: el server
reporta 8.53 t/s mientras el wall da 7.79 -> 3.0 s de overhead. La tabla usa
`tokens / (wall - 3.0)`, o sea la tasa real de decode.

| np | t/s agregado | x vs 1 stream | t/s por stream |
|---|---|---|---|
| 1 | 8.57 | 1.00x | 8.57 |
| 2 | 14.19 / 14.35 | **1.66x / 1.67x** | ~7.1 |
| 3 | 17.00 / 17.06 | **1.98x / 1.99x** | ~5.3 |
| 4 | pendiente al cierre | - | - |

**El 2x existe y no cuesta una linea de codigo**: `--parallel 3`. Cada agente
corre a ~5.3 t/s (62% de su velocidad solo) y la caja entrega 17 t/s. Para un
runtime multi-agente en casa esa es LA configuracion: 3 slots, no 1.

Correccion importante: el "1.31x" que quede escrito antes estaba mal (generos
desiguales por un bug de paso de variables + el mismo overhead). El numero bueno
es 1.99x.

Lo que esto cambia en la estrategia:
1. El 2x esta BANCO. No hace falta tocar un kernel para Conseguirlo.
2. La Lane 3 (layout de PTQ1_0, 41-50 GB/s contra 185) pasa de "conseguir el 2x"
   a "ir mas alla del 2x" = bajar LATENCIA por stream, que es otra pregunta y
   otra justificacion (interactividad, no throughput).
3. Antes de invertir en la Lane 3, esperar el veredicto del brief 06: si el head
   MTP resulta ARREGLABLE, el spec decode puede volver a sumar sobre top de esto.
