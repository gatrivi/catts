# Runbook del lane de kernel - PTQ1_0 vecq (2026-09-26)

Maquina: RX 6800 8GB + Ryzen 5 3600. Modelo de trabajo:
`data/models/qwen35-27b-ptq1_0/Qwen3.5-27b-Q4K-GPTQ-PTQ1_0.gguf`
Referencia de texto: `Z:\catts\local-coding\data\reference_text.txt`
Binario: `C:/src/llama.cpp/build/bin` (HEAD `e728b26` + 3 archivos sin commitear).

Todo esto requiere **GPU exclusiva y CPU libre** (~30 min). No correr mientras
el usuario usa la maquina: los numeros per-op con la caja ocupada no valen.

## Paso 0 - respaldo de lo irrecuperable (obligatorio, es lo primero)

```powershell
cd C:\src\llama.cpp
git rev-parse --short HEAD   # debe ser e728b26; si no, parar y avisar
git add ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vecq_funcs.glsl `
        ggml/src/ggml-vulkan/vulkan-shaders/mul_mat_vec_ptq1_0.comp `
        src/models/qwen35.cpp
git commit -m 'wip(ptq1_0): triton packing matvec + vecq LUT (build green, vecq off by default)'
git push origin master
```
Si ademas aparece modificado `vulkan-runtime.cpp` o `test-v9-vulkan-die-loop.cpp`,
NO commitearlos sin avisar: pueden ser de otra lane.

## Paso 1 - el oraculo que falta: per-op del 27B PTQ1_0 en esta caja

Nunca medido. El audit de `docs/KERNEL_HEADROOM_2026-09-25.md` (90-100% de roofline)
es de **RX 6600 con TQ2_0**, no de esta caja ni de este cuantizador.

```powershell
cd Z:\catts\local-coding
python scripts/d1_perop_profile.py 8192 f16 48 `
  Z:/catts/local-coding/data/models/qwen35-27b-ptq1_0/Qwen3.5-27b-Q4K-GPTQ-PTQ1_0.gguf
```
El script tiene default `MODEL` de TQ2_0; el 4to argumento lo pisa. Fijarse en la
salida: `MUL_MAT` GB/s y % del paso. Si `MUL_MAT` no domina (>70%), parar el lane
de kernel y reportar que el goal esta en otra parte.

## Paso 2 - barrido WGxROWS (barato, no toca shaders)

```powershell
powershell -File scripts/sweep_mtp2.ps1 -Models Z:\catts\local-coding\data\models\qwen35-27b-ptq1_0\Qwen3.5-27b-Q4K-GPTQ-PTQ1_0.gguf -Rows "2,4" -Wg "4,8"
```
(4 puntos, ~1 min. Si -Rows/-Wg no existen en esa variante del script, usar
`scripts/ab_mtp1.ps1` con las mismas flags.)

## Paso 3 - aplicar el parche repack4 (D1 + D2)

Archivo listo para pegar: `patches/repack4_ptq1_0_CANDIDATO_2026-09-26.txt`
Reemplaza `repack4()` en
`C:\src\llama.cpp\ggml\src\ggml-vulkan\vulkan-shaders\mul_mat_vecq_funcs.glsl`
(lineas 632-684). Deja `.comp` y `.glsl` de acuerdo en el tema de la LUT (D3).

```powershell
cmake --build C:\src\llama.cpp\build --config Release -j 4
# oraculo mecanico: hoy esto FALLA, cuando pasa 68/68 el interleave esta bien
$env:GGML_PTQ1_0_MMVQ='1'
C:\src\llama.cpp\build\test\ggml\test-backend-ops.exe -b Vulkan MUL_MAT
```
`GGML_PTQ1_0_MMVQ` sigue **off por default**: nada de esto cambia la produccion
hasta que pase los gates.

## Paso 4 - gates antes de tocar velocidad

1. `test-backend-ops` MUL_MAT 68/68 (incluye 2x77 y 1x77, el tamano que rompio MTP).
2. Golden Model 7/8 con `GGML_PTQ1_0_MMVQ=1`.
3. Recien ahi: `perop` A/B con el flag 0 vs 1, y `sweep` de t/s.
4. Un commit por paso.

## Paso 5 - lo que NO se toca

- Dispatch tax del 8% (arreglo de 6 lineas documentado; pendiente de medir su
  ganancia real, es el P1 del plan original).
- `-np 3`: ya da 1.99x agregado. Es configuracion, no codigo; no mezclarlo con
  el lane de kernel en la misma corrida o no se sabra que movio la aguja.
