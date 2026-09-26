# 06 - VERIFICAR POR QUE MTP PIERDE (lectura pura, sin GPU) | 2026-09-26

Para un segundo agente identico a la sesion que midio. Canal: `00_LEEME.md`.
NO DECIDAS: responde 6 preguntas con `archivo:linea` o "NO ENCONTRADO".

## Por que esta tarea (contexto, no re-derivar)

Se midio spec-decode MTP sobre `Bonsai-2-27B-PTQ1_0-mtp-lean.gguf` (27B, 6.3 GB)
en esta RX 6800, GPU, -ngl 99, -c 8192, temp 0, seed 42, 256 tokens:

| config | t/s | draft acceptance | mean len |
|---|---|---|---|
| base (sin draft) | 8.64 +- 0.06 (3) | - | - |
| draft-mtp n=2 | 6.87 +- 0.04 (2) | 0.6087 (140/230) | 2.22 |
| draft-mtp n=4 | 4.36 (2) | 0.4026 (157/390) | 2.60 |

MTP PIERDE y empeora al subir n. La aceptacion es alta (0.61 con n=2), asi que
el drafter no es el problema. La sesion que midio INFERIO que "el head MTP no se
amortiza" pero NO verifico el codigo. Tu trabajo es esa verificacion.

Datos: `local-coding\data\spec_ab_20260926.json`, `spec_draftn4_20260926.json`.
Logs: `$env:TEMP\ab_draft.err.log` y `$env:TEMP\dnA.err.log` (lineas
`draft acceptance = ...` y `print_timing`).

## Las 6 preguntas (esta es toda la tarea)

P1. Donde esta implementado el forward del head MTP y corre UNA VEZ por paso de
    decode (batched, todos los tokens draftados juntos) o UNA VEZ POR TOKEN
    draftado (secuencial)? Archivo y linea. Si es secuencial, ese es el bug.

P2. La inversa de Hadamard (`llama_mul_mat_hadamard`, `hadamard_inverses`, el
    patch de `src/models/qwen35.cpp`) se RECALCULA en cada paso o se cachea una
    vez? Si se recalcula por token, es un desperdicio trivial de arreglar.

P3. El head esta en GPU o en CPU? Evidencia: en los logs hay
    `failed to fit params to free device memory` y el server arranca con
    `-ngl 99`. El head puede quedar fuera de las capas que suben a VRAM. Como lo
    demuestra el codigo, no por el log.

P4. Cuantos matvecs extra agrega el head por paso de decode, comparado con los
    del target? El head es una capa transformer completa o un solo matvec? Con
    numeros.

P5. `mean len = 2.22` con `n=2` y `2.60` con `n=4` son consistentes con que la
    implementacion procese el draft en batch? Si con n=4 solo se ACCEPTAN 2.60 de
    media,decime donde se descartan los sobrantes y si ese descarte es trabajo
    tirado.

P6. (la importante) El PR upstream del que viene este fix ya esta descargado:
    `local-coding\data\campaign\pr-205.json` (mergeado, `422590f5d4bc`) y
    `pr-217.json`. Comparar la implementacion upstream contra la de nuestro fork
    (`C:\src\llama.cpp\src\`, simbolos `mtp`, `hadamard`, `speculative`).
    RESPONDE: upstream batchea el head y nuestro fork no? Si upstream lo hace
    distinto, ese es el patch que falta.

## Entregable

Appendear al final de ESTE archivo:

    ## Resultado MTP-verify (fecha hora)

- Una tabla: P1..P6 -> respuesta de una linea + `archivo:linea`.
- Una linea final con exactamente uno de estos tres:
  `VEREDICT: INTRINSICO` (el head es caro de por si, no hay arreglo)
  `VEREDICT: ARREGLABLE` (dame el parche minimo en 5 lineas, SIN escribirlo)
  `VEREDICT: BUG` (hay un error concreto, cual y donde)
- Si una pregunta no la podes responder con `archivo:linea`, ponele
  `NO ENCONTRADO` + los 3 archivos donde mas probablemente este. NO adivines.

## Reglas duras (esta lane es de LECTURA)

- PROHIBIDO escribir en `C:\src\llama.cpp\**` (otro escritor esta en ese arbol y
  hay 3 archivos sin commitear que son el fix de MTP). PROHIBIDO `ninja`,
  PROHIBIDO `git checkout/reset/clean/stash`.
- PROHIBIDO arrancar `llama-server`, `test-backend-ops` o cualquier cosa que
  toque la GPU: la sesion que mide la tiene ocupada. PROHIBIDO benchmark.
- PROHIBIDO descargas, `pip install`, y buscar en la red lo que este en el repo.
- Solo se escribe: este archivo (`BRIEFS/06_*.md`) y tu linea en `CLAIMS.md`.
- Appendea tu claim en CLAIMS.md antes de empezar:
  `AAAA-MM-DD HH:MM | <tu-id> | BRIEFS/06_*.md | +2h | verificar por que MTP pierde | ACTIVO`
  y cerralo con DONE al terminar.
- Leelo todo antes de responder. Cita todo. Si algo no esta, decilo.

## Dato nuevo (10:12) que acota tu tarea

La concurrencia YA se midio: `-np 2` da 11.19 t/s agregado contra 8.57 de un
stream solo = **1.31x, gratis**. O sea que el 2x NO sale de correr dos streams
sino del KERNEL (PTQ1_0 a 41-50 GB/s contra un techo de 185 GB/s). Eso hace que
tu tarea sea la bisagra: si el head MTP se puede arreglar, el 2x vuelve a estar
disponible sin tocar el kernel; si es INTRINSICO, el 2x depende de Space Bunny
en la Lane 3 y tu veredicto decide si esa lane vale la pena. Por eso las 6
preguntas, y sobre todo P1, P2 y P6.
