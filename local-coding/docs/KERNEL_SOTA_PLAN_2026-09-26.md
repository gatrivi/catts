# PLAN SOTA kernel/matvec - 2026-09-26 (tarde, budget 15% CPU)

Leido antes de escribir: `KERNEL_HEADROOM_2026-09-25.md` (auditoria per-op),
`REVIEW_2026-09-25_LATE_4_FINDINGS.md`, dispatch real en
`ggml/src/ggml-vulkan/ggml-vulkan.cpp`. No re-derivo lo ya medido ahi.

## Correccion a mi propio framing de hoy

Yo dije "PTQ1_0 a 41-50 GB/s contra un techo de 185 => 2.7x en la mesa". Mal
enmarcado. El techo de 185 GB/s (copia fria) aplica, pero la auditoria per-op ya
mostro que en tq2_0 el matvec caliente esta al **90-100% del roofline** y que el
techo kernel restante es **~4.3 ms (8%)** de tax de dispatch, no el matvec.

Nuestro 27B PTQ1_0 (8.64 t/s, ~5.5 GB/token = 47 GB/s) NO esta al roofline, pero
la causa no es "falta de kernel": es que **el camino vecq (int-dot) de PTQ1_0
esta semantic roto y apagado por default**.

## El arbol YA tiene lo que yo crea que faltaba

- `ggml-vulkan.cpp:5345` crea `mul_mat_vec_ptq1_0_f32_f32`: matvec dedicado,
  spec constants `ptq_spec[0]=WG` (default 128) y `ptq_spec[1]=NUM_ROWS`, mode
  de reduccion HYBRID cuando WG > subgroup.
- Knobs **sin recompilar**: `GGML_PTQ1_0_MATVEC=stdq|sub16|sub16hyb` (v5253),
  `GGML_PTQ1_0_WG=64|128|256` (v5288), `GGML_PTQ1_0_ROWS=1|2|4` (v5296),
  `GGML_VK_DMMV_REDUC=0|1|2` (v5269), `GGML_PTQ1_0_MMVQ=1` (v9722, opt-in al
  vecq), `GGML_TQ2_0_NO_MMVQ` (v9723).
- `mul_mat_vecq` esta referenciado 0 veces en los `.cpp`: mi fix del `qh0` de
  esta manana **desbloqueo el build pero no toca el runtime**. Honestidad de
  registro: el fix de build fue necesario, no fue un fix de performance.

## El gap real, con linea y columna

`vulkan-shaders/mul_mat_vecq_funcs.glsl`, funcion `repack4`, rama `else`
(ebase == 112, linea 666-678):

    const uint qhw = uint(data_a_packed16[ib].qh[0]);
    const uvec4 qh_bytes = uvec4(qhw & 0xFFu, qhw >> 8u, qhw & 0xFFu, qhw >> 8u);
    hi0 = trits4(qh_bytes, 0u); // trits 0,0 for qh0,qh1
    hi1 = trits4(qh_bytes, 1u); // trits 1,1 for qh0,qh1

Reconstruye los 8 trits altos con un placeholder: lee solo `qh[0]`, duplica el
mismo byte y usa indices fijos 0/1. El comentario lo admite. El resto de la
funcion (ebase<=96, linea 655-665) si hace el walk correcto de `qs`.
Y `mul_mat_vecq.comp:29-30` dice "No LUT needed" porque le borraron
`ptq_trit_lut` (ver REVIEW F1 punto 2): el `.comp` y el `.glsl` están
desincronizados.

Por eso `ggml-vulkan.cpp:9719-9721` mide vecq PTQ1_0 MAS lento (lm_head
5319 -> 5440 us) y lo deja OFF, mientras TQ2_0 vecq vuela (2949 -> 1637 us,
~200 GB/s). Un vecq con los trits altos mal da resultados MALOS, no solo lentos:
hay que chequiar si hoy alguien corre con `GGML_PTQ1_0_MMVQ=1` puesto.

## Ranking de trabajo hasta SOTA (por收益/CPU)

1. **Arreglar el interleave de los 8 trits altos** (`repack4`, ebase==112) y
   resincronizar `mul_mat_vecq.comp` con `ptq_trit_lut`. Oracle: el dot CPU de
   referencia de PTQ1_0 (ggml-impl/vec), no adivinar. Gate: `test-backend-ops`
   68/68 + golden PTQ1_0 7/8 + perop 2 corridas. Payoff esperado: las ratios de
   TQ2_0 como analogueo (1.16-1.80x por forma) => 8.64 -> ~12-14 t/s por stream.
   Task completa en `BRIEFs/07`.
2. **Barrido de knobs sin recompilar** (WG x ROWS x MATVEC x REDUC) sobre
   perop de produccion. Barato, y puede dar unos % sin tocar un shader.
3. **Tax de dispatch 4.3 ms (8%)**: GET_ROWS MoE (1.6), rms_norm n=1 (1.4),
   MoE mul_mat_id batching (0.5), MUL (0.6). Reales pero pequenos.
4. **Lo que YA esta banco y no es kernel**: `-np 3` = 1.99x agregado gratis
   (`data/np_curve_20260926.json`); MTP medido y REFUTADO aca (0.79x n=2,
   0.50x n=4). La frase del doc anterior "spec decode es el 2x" no aplica a
   PTQ1_0 en esta caja.

## Regla de metodo que me saltee y no hay que saltear mas

`KERNEL_HEADROOM` S5: los numeros in-suite mienten (IC-warm): 186-277 GB/s in-suite
vs 156-179 en produccion. Solo el perop de produccion es oraculo de velocidad;
in-suite sirve para ratios. Y todo cambio exige relinkear **llama-server**, no
solo test-backend-ops.
