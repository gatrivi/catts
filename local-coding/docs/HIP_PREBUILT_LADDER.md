# HIP prebuilt ladder (2026-09-21): probar los binarios del fork ANTES de construir en la nube

Meta: PTQ1_0 (tipo 143, kernels empaquetados ternarios) corriendo en el RX 6600
(gfx1032) **sin compilar nada**. El fork Prism publica assets HIP/ROCm y los
builds HIP compilan las fuentes CUDA hipificadas, asi que los prebuilts
deberian incluir los kernels ternarios; lo unico dudoso es el target gfx1032
(fuera de la matriz oficial de ROCm, sobre todo en Windows).

## L0 - GPU enumerado (OK 2026-09-21)
`Win32_VideoController`: "AMD Radeon RX 6600", Status OK, driver 32.0.21043.19003.
Superpuesta la nota "GPU vanished" del 2026-09-20 en SESSION_CONTEXT.md.
Re-chequear cuando haga falta: `scripts/hip_prebuilt_test.ps1` lo hace solo.

## L1 - prebuilt win-hip en Windows (minutos) — RESULTADO 2026-09-21: FAIL (cerrado)
Descargado `llama-prism-b10709-9a9394a-bin-win-hip-radeon-x64.zip` (307 MB) a
`Z:/Models/runtime/llama-prism-hip-win`. Evidencia:
- `llama-server --list-devices` -> `(none)`, con y sin `HSA_OVERRIDE_GFX_VERSION=10.3.0`.
- `ggml-hip.dll` NO CARGA: LoadLibrary err=126 (dependencia insatisfecha).
  El runtime HIP del sistema es `C:/Windows/System32/amdhip64.dll` v10.0.3584.0
  (ROCm 5.x-era, viejo); el paquete trae libhipblas/hipblaslt pero no el runtime
  que su ggml-hip.dll necesita.
- Aunque se instalara el HIP SDK actual (~GBs), gfx1032 no esta en la matriz
  Windows (override verificado solo en Linux). NO instalar el SDK; escalon cerrado.
`scripts/hip_prebuilt_test.ps1` queda para re-verificar si algun dia cambia la
matriz (defaults ya apuntan a b10709-9a9394a).

## L2 - prebuilt ubuntu-rocm-7.2 en Linux (SIGUIENTE; el escalon con chance real)
Mismo release, asset `llama-prism-b10709-9a9394a-bin-ubuntu-rocm-7.2-x64.tar.gz`.
El override gfx1032 esta verificado en Linux (ROCm#1797 / ollama#4464), no en
Windows. Estado 2026-09-21: WSL2 sin distros instaladas (`wsl -l -v` vacio).
- **WSL2**: Ubuntu + `amdgpu-install --usecase=wsl` + ROCm libs. RIESGO: el
  driver WSL de AMD expone pocas consumer cards; si gfx1032 no aparece en
  `rocminfo`, el override nunca se aplica. Probar ~30 min antes de invertir mas.
- **USB-boot Ubuntu nativo** (fallback mas confiable): driver amdgpu del kernel
  + `HSA_OVERRIDE_GFX_VERSION=10.3.0`.
Validacion local en cualquiera de los dos: `llama-server` PTQ1_0 de ese runtime +
`scripts/golden_capture.py --url http://127.0.0.1:PORT --name bonsai2-ptq10-hip` +
`scripts/golden_check.py <golden_kaggle.json> <dump>`; bench con llama-bench.
**PASS = decode >= 20 t/s** -> actualizar MODEL_ROSTER.md:10 ("dead end on AMD").

## L3 - solo si L1+L2 fallan: construir en AMD Developer Cloud
Ver `docs/AMD_HIP_BUILD_WORKFLOW.md` (build desde fuente con
AMDGPU_TARGETS=gfx1032 en MI250/MI300X, ~$15-25, mas hipify solo como
contingencia).

Por que escalones: el reframe pide "cloud como build farm"; los binarios ya
publicados son gratis y cubren el 90% del riesgo antes de gastar creditos.
