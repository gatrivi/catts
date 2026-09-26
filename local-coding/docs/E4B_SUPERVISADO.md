# E4B supervisado (experimental)

Prueba de proyecto rechazada:6/12 tests originales y cambios indebidos en tests del fixture. No recomendado como editor habitual. Usar solo con revision cuidadosa de cada escritura; ver [informe](E4B_PROJECT_TRIAL_2026-09-06.md).

Desde Z:\catts\local-coding:

```powershell
.\E4B.cmd "C:\ruta\al\proyecto" --pause-qwen
```

Tambien: `npm run e4b -- "C:\ruta\al\proyecto" --pause-qwen`.

El editor usa E4B QAT sin MTP, autoaprueba sus acciones (modo yolo) y limita sus herramientas a leer, buscar y escribir archivos completos. Pedi una tarea pequena. Ejecuta vos los tests que indique. `/exit` cierra el editor y apaga E4B.

`--pause-qwen` pausa el Qwen2.5 conocido del puerto8123 y lo restaura con los mismos argumentos al salir. Puede interrumpir solicitudes en ese servidor; omiti la opcion si ya esta apagado. Otros servidores llama activos se preservan y bloquean el arranque para evitar competir por VRAM.

Comprobacion sin cargar modelos: `npm run e4b:check`.

Perfil separado: `data/e4b-omp/`. Registros: `data/e4b-session-*/`. No modifica el perfil anterior ni el menu Taller.

Configuracion: RX6600 Vulkan1, contexto16384, KV q8_0, flash attention, --no-mmap, batch256/ubatch128, una secuencia. Maximo6min por sesion del editor; requiere los pesos ya verificados y el OMP instalado. No descarga nada.

Resultados previos: docs/SOLO_CANDIDATE_RESULTS_2026-09-06.md. La integracion OMP todavia es experimental: la primera prueba agoto8K y la segunda no escribio cambios. Ver E4B_PROJECT_TRIAL_2026-09-06.md para el resultado final. No promoverlo a editor por defecto basandose en los tests pequenos.


