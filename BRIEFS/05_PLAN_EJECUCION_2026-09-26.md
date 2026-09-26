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
