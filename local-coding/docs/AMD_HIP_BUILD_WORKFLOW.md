# AMD Developer Cloud: build HIP para gfx1032 (v3, 2026-09-21) — MISION BUILD, NO BENCH

Produce un binario Linux del fork Prism con GGML_HIP compilado para **gfx1032**
(RX 6600), validado en la instancia y contra los goldens de Kaggle, para correr
localmente (WSL2 o USB-boot Linux). NO es el bench de quants (v1, obsoleta) ni
el shader Vulkan (`AMD_CLOUD_VALIDATION_WORKFLOW.ps1` v2 = track alternativo;
no perseguir ambos en paralelo).

Orden correcto: `docs/HIP_PREBUILT_LADDER.md` L1/L2 primero (prebuilts
gratuitos); este runbook solo si aquellos fallan.

## Creditos e instancia
- AMD AI Developer Program -> Developer Cloud, $100 creditos. Solo necesitamos
  **8-12 h ~ $15-25** (sizing heredado de v2), NO 80 h.
- Reservar MI250 o MI300X Ubuntu via la consola/`amdctl`. MI300X = gfx942,
  MI250 = gfx90a; ambos sirven para compilar y validar, ninguno predice la
  velocidad del gfx1032.

## En la instancia (bash)

### 0) De-risk: prebuilt ROCm primero (responde 2 preguntas en 15 min)
```bash
rocminfo | grep -i gfx                       # que GPU somos (gfx942/gfx90a)
mkdir ~/p && cd ~/p
curl -L -o rocm.tar.gz \
  https://github.com/PrismML-Eng/llama.cpp/releases/download/prism-b10709-9a9394a/llama-prism-b10709-9a9394a-bin-ubuntu-rocm-7.2-x64.tar.gz
tar xf rocm.tar.gz
BIN=$(find . -name llama-server | head -1 | xargs dirname)
$BIN/test-backend-ops test -o MUL_MAT | tail -40   # GPU vs CPU, incluye ptq1_0
```
- Si MUL_MAT ptq1_0 **FALLA en gfx942 nativo**: los assets ROCm no traen los
  kernels ternarios sanos -> el problema es del fork, no de gfx1032. Abrir issue
  al fork y pasar directamente a la contingencia hipify.
- Si pasa: los kernels existen bajo HIP; queda solo el target gfx1032 (paso 1).

### 1) Build desde fuente para gfx1032 (+gfx942 para validar en instancia)
```bash
sudo apt update && sudo apt install -y build-essential cmake ninja-build git
git clone https://github.com/PrismML-Eng/llama.cpp && cd llama.cpp
git checkout 9a9394a        # fijar el commit del release probado arriba (b10709)
cmake -B build -DGGML_HIP=ON -DGGML_VULKAN=OFF -DCMAKE_BUILD_TYPE=Release -G Ninja \
      -DAMDGPU_TARGETS=gfx942;gfx1032
cmake --build build -j 2>&1 | tee build.log
```
(En MI250 usar gfx90a;gfx1032. Si hipcc no esta en PATH: source /opt rocm env,
`export PATH=/opt/rocm/bin:$PATH`.)

### 2) Validacion en la instancia (gfx942 nativo, sin override)
```bash
./build/bin/test-backend-ops test -o MUL_MAT | tail -30   # 0 FAILS requerido
./build/bin/llama-bench -m ~/Ternary-Bonsai-2-27B-PTQ1_0.gguf -p 128 -n 32 -ngl 99 -c 2048
# (velocidad de referencia NOMAS; NO aplica a gfx1032)
```

### 3) Paquete para casa
```bash
tar czf prism-hip-gfx1032-5d80cff.tar.gz -C build/bin .
# bajar tambien build.log + CMakeCache.txt (evidencia de flags/targets)
```

## Contingencia hipify (solo si el paso 0/1 muestra kernels ternarios rotos o
ausentes bajo HIP)
Los kernels viven en `ggml/src/ggml-cuda/` (archivos *ptq1*/ternary, matvec
hand-tuned). `hipify-python` sobre esos archivos es mecanico para host code;
las secciones warp/intrinsecos requieren trabajo manual. **Presupuesto: dias,
no horas; tarea separada**, revalidada con test-backend-ops + goldens.

## En casa (L2 local)
Tar a WSL2/USB-Ubuntu; `HSA_OVERRIDE_GFX_VERSION=10.3.0`; server PTQ1_0 del
nuevo runtime + `scripts/golden_capture.py` + `scripts/golden_check.py` contra
`data/kaggle_runs/gold-*/golden.json`; llama-bench para t/s.
**PASS = decode >= 20 t/s sin divergencia** -> MODEL_ROSTER.md:10 cambia
("dead end on AMD" fuera), SESSION_CONTEXT + memory add.

## Honestidad
- Perf MI300X/MI250 NO transfiere a gfx1032; solo build y correccion si.
- gfx1032 fuera de matriz oficial: aun con binario correcto, el runtime WSL2
  puede no exponer la GPU -> fallback USB-boot nativo.
- Aprobacion de creditos no es instantanea; reclamarlos primero (paralelo con
  el golden de Kaggle, que es gratis).
