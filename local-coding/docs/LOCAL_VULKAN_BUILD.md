# Local Vulkan build of the Prism fork (2026-09-22): toolchain + dev loop

Mision habilitada: editar `ggml/src/ggml-vulkan/vulkan-shaders/ptq1_0.glsl` (fix
LUT, v2) SIN nube. Todo portatil en C:, ~4.5 GB, sin admin ni installers.

## Layout
- `C:/tools/llvm-mingw/` — clang/llvm-mingw (compilador, 20260908 ucrt x86_64)
- `C:/tools/cmake+ninja` — via pip del venv E: (`python -m cmake`, ninja)
- `C:/tools/glslang/bin/glslangValidator.exe` — copia de glslang.exe renombrada
  (16.6.0; el binario unico despacha modo validator por argv[0])
- `C:/tools/bin/glslc.c/.exe` — SHIM glslc->glslang (ver abajo)
- `C:/tools/Vulkan-Headers/`, `C:/tools/SPIRV-Headers/` (+`spirv-install/`),
  `C:/tools/lib/libvulkan-1.a` (import lib generada de System32/vulkan-1.dll
  via llvm-readobj --coff-exports + llvm-dlltool)
- Fuente: `C:/src/llama.cpp` @ tag prism-b10709-9a9394a (copia aislada)

## Shim glslc (C:/tools/bin/glslc.c)
El build requiere `glslc` (shaderc, solo en Vulkan SDK ~1GB+). El shim traduce
las invocaciones fijas a glslangValidator: -fshader-stage=compute -> -S comp,
--target-env=X -> espacio, come -O/-MD/-MDF (toca depfile), expande #include
(glslc lo trae implicito, glslang NO), silencia stdout/stderr (glslc es mudo;
gen tool trata output != vacio como fallo) y traduce errores de extension al
formato "extension not supported: NAME" que CMake grep-ea. Caveat: sin -O de
shaderc (glslang no optimiza) -> comparar siempre antes/despues con ESTE build.

## Configure + build (recordar)
```
export PATH="/c/tools/bin:/c/tools/llvm-mingw/bin:/c/tools/glslang/bin:/e/zengatrivi-drive-e/catts/.venv/Scripts:$PATH"
cmake -S C:/src/llama.cpp -B C:/src/llama.cpp/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
  -DGGML_VULKAN=ON -DGGML_NATIVE=ON \
  -DVulkan_INCLUDE_DIR=C:/tools/Vulkan-Headers/include \
  -DVulkan_LIBRARY=C:/tools/lib/libvulkan-1.a \
  -DVulkan_GLSLC_EXECUTABLE=C:/tools/bin/glslc.exe \
  -DCMAKE_PREFIX_PATH=C:/tools/spirv-install \
  -DCMAKE_CXX_FLAGS="-D_WIN32_WINNT=0x0A00 -isystem C:/tools/spirv-install/include" \
  -DCMAKE_C_FLAGS="-D_WIN32_WINNT=0x0A00"
```
Parches al source (copia local, minimos): +cstdlib en tools/mtmd/
deprecation-warning.cpp, tests/test-sampling.cpp, examples/rs-rollback/
rs-rollback.cpp; shims setenv/unsetenv en tests/test-dspark-forward.cpp.

**DISCO: C: al 99%. NUNCA `ninja` pelado (relínkea ~50 tests y llena el disco).
Solo targets nombrados:** `ninja -C C:/src/llama.cpp/build llama-server llama-bench test-backend-ops`

## Baseline verificado (2026-09-22, RX 6600, Vulkan1, server bonsai2 coexistiendo)
```
./test-backend-ops.exe perf -b Vulkan1 -o MUL_MAT -p "ptq1_0.*n=1,|tq2_0.*n=1,|q4_0.*n=1,"
ptq1_0: 601.17 us/run, 195.35 GFLOPS   <- kernel roto (doc 2026-09-18: 602us/195)
tq2_0:   94.60 us/run, 1.24 TFLOPS
q4_0:    94.32 us/run, 1.25 TFLOPS
./test-backend-ops.exe test -b Vulkan1 -o MUL_MAT -p "ptq1_0|tq2_0"  -> 39/39 OK
```
El build mingw+shim es fiel al baseline oficial. Objetivo del fix: 602 -> ~100 us.

## Dev loop del fix LUT
1. Editar `C:/src/llama.cpp/ggml/src/ggml-vulkan/vulkan-shaders/ptq1_0.glsl`
   (LUT 256 entradas byte->5 trits, forma de mul_mat_vec_tq2_0.comp).
2. `ninja -C C:/src/llama.cpp/build test-backend-ops` (regen shader+relink, ~1 min).
3. perf de arriba (antes/despues) + test 39/39.
4. Modelo completo: server propio del build + `scripts/golden_capture.py --url ...`
   + `scripts/golden_check.py data/kaggle_runs/gold-20260921/golden.json <dump>`
   (golden CUDA spec 25005c6c2ea1d69c, T4, top-logprobs).
