# De día no se puede medir (registro 2026-09-26 11:25)

## Hecho
El usuario trabaja con videollamadas en **MS Edge con aceleración de hardware**.
Edge toma **21 %+ de GPU y ~2.8 GB de VRAM sostenidos**. Confirmado desde acá:
el monitor marcó 7 % sostenido con 2802 MB en uso y la puerta de exclusividad
(< 5 % durante 3 s) **nunca abrió**. Mi runner de `--parallel 3` murió en el
preflight: no midió nada, y no dejó `llama-server` cargando (verificado).

## Regla (aplica a todo experimento de este repo)
De día, con Edge vivo, **ningún número absoluto es bankable**:
- el 8.57 t/s del 09-25 y los 17.0 t/s de la curva np de esta mañana se guardan
  como **piso con contaminación**, no como techo;
- la *relación* 1.99× (np=3 vs np=1) es más robusta porque la contaminación
  castiga a los dos brazos por igual, pero igual pide re-medición en ventana limpia;
- o pasa `scripts/wait_gpu_confirm.ps1` (ya existe, sondea ventana libre), o el
  JSON se guarda con `contaminado: true` y **no decide nada**.

Consecuencia de reparto del día: **de día se lee y se parchea; de noche se mide.**

## Qué quedó listo para esa ventana
- `local-coding/patches/repack4_ptq1_0_CANDIDATO_2026-09-26.txt` — reemplazo de
  `repack4` (defectos D1 y D2), con el contrato de orden verificado contra las dos
  fuentes que pasan la suite (`ptq1_0.glsl:15-45`, `mul_mat_vec_ptq1_0.comp:57-61`).
- El oráculo es mecánico: `test-backend-ops` MUL_MAT con `GGML_PTQ1_0_MMVQ=1`
  (hoy falla; 68/68 = interleave correcto). No hay que adivinar.
- Falta el **primer per-op del 27B PTQ1_0 en esta caja**: nunca se midió. Todo el
  juicio de "¿realmente nos quedan +140 % o el vecq ni siquiera es el cuello de
  botella?" cuelga de esos 3 minutos de GPU limpia.

## Nota de proceso (mi error, no del repo)
Tres turnos perdidos por quoting: en este shell, `@'...'@` dentro de un array de
comandos revienta (`Missing type name after '['`). Para escribir texto largo,
usar el editor; dejar PowerShell para comandos cortos.
