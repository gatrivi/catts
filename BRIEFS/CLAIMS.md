# CLAIMS — quién está escribiendo qué zona

Una línea por claim. **Append only**: nunca reescribir el archivo.
Formato:
`AAAA-MM-DD HH:MM | <agente/sesion> | <zona> | <vence> | <motivo>`

Reglas: una zona sin claim no se escribe. Claim vigente = los demás leen y
siguen en su propia zona. Sin `DONE` por más de 2 h = caduca: preguntar al
usuario antes de escribir. Ver `03_PROTOCOLO_ANTI_CHOQUE_2026-09-25.md`.

| timestamp | agente | zona | vence | motivo | estado |
|---|---|---|---|---|---|
| 09-25 22:45 | ses_f24d (esta sesión) | `BRIEFS/**` + `AGENTS.md` raíz | 09-26 02:00 | documentación y traspaso; sin código | ACTIVO |
| 09-25 19:46 | ses_f253 (agente GPU) | `C:\src\llama.cpp\**`, `local-coding\scripts\*.ps1`, `local-coding\docs\HANDOFF_2026-09-25.md`, `SESSION_CONTEXT.md` | — | track GPU + armado de la noche 02:30 | ACTIVO (último write 22:38) |
| 09-25 20:31 | ses_f251 (voz/STT) | `C:\zengatrivi\REACTJS\catintassist\**` | — | fix Deepgram CONNECT, v4.153.0 | ENTREGADO 21:56 |
| 09-25 22:55 | ses_f24d (esta sesión) | `BRIEFS/**` | — | wrap up: docs 01-04 | **DONE** |

---

**Historial de cambios de esta sesión (append):**
- 22:45→22:55: docs `01` (estado GPU), `02` (findings de agentes), `03`
  (protocolo anti-choque), `04` (eval fafstmobel). Zona cerrada: **no seguir
  escribiendo en `local-coding/**` sin nuevo claim del usuario.**
| 09-25 23:05 | ses_eval_asis (esta sesion) | `local-coding/docs/AGENTE_PERSONAL_EVAL_2026-09-25.md`, `local-coding/data/models/qwen3vl-4b/**`, `local-coding/tmp/vl_*` | 09-26 00:00 | eval + doc del agente personal local; sin GPU, sin descargas | ACTIVO |

| 09-25 23:20 | ses_eval_asis (esta sesion) | idem zona anterior | - | eval+doc entregado: `local-coding/docs/AGENTE_PERSONAL_EVAL_2026-09-25.md` (193 lineas) + vision instalada/verificada en `data/models/qwen3vl-4b/`; sin GPU, sin descargas nuevas; `SESSION_CONTEXT.md` restaurado | DONE |
| 09-25 23:40 | ses_pixel (esta sesion) | `local-coding/docs/REVIEW_2026-09-25_LATE_4_FINDINGS.md` (solo ese archivo nuevo) | 09-26 00:30 | review del track GPU pedido por el usuario: 4 hallazgos (arbol no compila; fix MTP nunca compilado; falta guard de frescura de build; `-np>=2` sin medir). Sin edits en `C:\src\llama.cpp`, sin GPU, sin descargas | DONE |

| 09-25 23:55 | ses_pixel (esta sesion) | `C:\src\llama.cpp\ggml\src\ggml-vulkan\vulkan-shaders\mul_mat_vecq_funcs.glsl` (solo revert F1) + `build\` (ninja, CPU) + `BRIEFS\05_*` | 09-26 03:00 | el usuario dio sole command ("sos el unico agente"): reparar el arbol roto y relinkear para que la campana de 02:30 mida MTP con el parche compilado. Sin GPU | ACTIVO |


| 09-26 00:05 | ses_pixel (esta sesion) | `BRIEFS/05_PLAN_EJECUCION_2026-09-26.md`, `local-coding/scripts/night_campaign.ps1` (gate RAM), `C:\src\llama.cpp\build\` (solo binarios) | 09-26 06:00 | plan de ejecucion para agentes sin criterio + desbloquear build/MTP; commit pendiente de OK del usuario | ACTIVO |
| 09-26 09:12 | ses_pixel (esta sesion) | lane 0 DONE (build verde, binarios 09:09) + lane 5.1 DONE (gate RAM 8000). Sin commitear en llama.cpp: 2 shaders + qwen35.cpp | 09-26 12:00 | falta test de GPU de draft-mtp y commit | ACTIVO (build desclaimed) |
