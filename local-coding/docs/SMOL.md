# Smol local

Ayuda en terminal: `SMOL.cmd --docs`, o `?` en el menu. No carga modelos.
Opciones de CLI: `SMOL.cmd --help`.

Abrir **CATTS local** (o `CATTS.cmd`): el hub maneja todos los modelos y apps en
un solo terminal. Guia: [HUB.md](HUB.md). Smol sigue funcionando igual y comparte
el registro de modelos con el hub (`scripts/local_models.py`).

Abrir **Smol local** en el escritorio o `SMOL.cmd`.
**Enter abre MiniCPM en Chat rapido**, sin mas preguntas. Para configurar:

1. Elegir modelo. MiniCPM5 es el mas rapido; Nanbeige piensa mas.
2. Chat para conversar; Proyecto para trabajar en una carpeta.
3. Rapido o Pensar. Nanbeige usa Pensar por defecto.
4. Nueva conversacion o continuar la anterior.

OMP arranca solo cuando el modelo esta listo. `/exit` vuelve al menu y descarga
el modelo de memoria. Esc interrumpe una respuesta. `/resume` recupera sesiones;
`/new` empieza otra. Cambiar modelo: `/exit`, elegir otro en el menu.
Se recuerda la ultima carpeta. Tambien podes arrastrar una carpeta sobre SMOL.cmd.

Proyecto incluye lectura, edicion, busqueda y comandos para ejecutar pruebas.
OMP pide aprobacion para escrituras y comandos. Las herramientas actuan en la
carpeta elegida; aprobar un comando puede permitirle acceder a otras rutas.
Chat no tiene herramientas. No hace falta una API key.

Sin limite de minutos ni corte experimental de 8192 tokens por respuesta.
El contexto por defecto es 32K (Nanbeige 16K): incluye archivos, historial,
razonamiento y respuesta. Los 7 modelos cargan y generan a 32K (sonda
2026-09-10, tabla mas abajo); `--context 16384` acelera sesiones que llegan
profundo. OMP compacta automaticamente al 65%; una respuesta
puede detenerse si llena el contexto disponible. Usar tareas acotadas y
conversaciones nuevas cuando haga falta. Cambiar Rapido/Pensar desde el
launcher, ya que ese ajuste se aplica al servidor.

Modelos: MiniCPM5-2B Q8, Nanbeige4.2-3B Q8, Gemma E4B QAT, Bonsai27B Q1,
Qwen3.5 9B, Qwen2.5 Coder 7B, Gemma12B coder Q3, NeoHorse-1-4B Q8,
Bonsai-2 27B TQ2, Spark-X2.5-4B Q8, Qwen3.8 27B Q3. Los Qwen viven en
Z:\Models\coding. Todos ya instalados; no hay descargas automaticas.

Bonsai-2, Spark y Qwen3.8-27B usan runtimes propios (prism fork / b10964)
y ofrecen presets de arranque (estilo esfuerzo bajo/medio/alto):

- bonsai2: mid = todo GPU 8K (~12-13 tok/s medido); low = 40 capas GPU, 4K,
  KV q4 (~1 tok/s, convive con otros); high = 32K ctx (cae a ~3 tok/s).
- spark: fast = 16K (16.5 tok/s medido); balanced = 64K; max = 131K KV q4.
- qwen27: mid = 56 capas GPU, 4K (perfil consultor medido); low = 32 capas,
  KV q4. Pide 6,2 GB de RAM libre.

Los presets se eligen en el menu o con `--preset nombre`; el primero es el
recomendado. `--context` explicito pisa el contexto del preset.
Para Proyecto usar Qwen3.5 9B: en el humo de edicion 2026-09-10 hizo la tarea
(mover un div, con autocorreccion) y Qwen2.5 Coder 7B emitio la llamada a
herramienta como texto plano en vez de llamada real. Son herramientas
supervisadas; los ensayos anteriores no establecieron fiabilidad para editar
proyectos sin revision.

## Comandos directos

```powershell
.\SMOL.cmd --model mini --mode chat
.\SMOL.cmd --model nanbeige --mode chat --thinking on
.\SMOL.cmd --model bonsai2 --preset low --mode chat
.\SMOL.cmd --model spark --preset max --mode project
.\SMOL.cmd "C:\mi proyecto" --model e4b --mode project
.\SMOL.cmd "C:\mi proyecto" --model e4b --mode project --continue
npm run smol:check
```

Perfiles y sesiones: local-coding/data/smol/profiles/.
Registros: local-coding/data/smol/runs/.
Solo un launcher/modelo a la vez. Se detiene su servidor al salir, incluso al
cerrar la ventana. Si habia un Qwen2.5 conocido en8123, se pausa y se restaura
al salir normalmente; cerrar forzadamente puede impedir esa restauracion.
Los perfiles de OMP anteriores permanecen disponibles.

## Como funciona y como aprender usandolo

SMOL inicia llama-server en tu PC (GPU Vulkan, puerto local 9104) y luego
OMP, la interfaz de terminal. El modelo genera texto; OMP administra historial,
herramientas y aprobaciones. Al salir, SMOL descarga su modelo.

Primera practica: Enter para Chat, pedi una explicacion breve, pulsa Esc para
interrumpir, proba /new y termina con /exit. En Proyecto, empieza por pedir
que lea un archivo y explique una funcion antes de autorizar cambios.

32K es la mesa de trabajo compartida por entrada y salida, no una cuota paga.
Un contexto anunciado de 131K/250K no significa que entre en tu GPU con esta
configuracion. Guardar sesiones en disco tampoco amplia la memoria del modelo.
La pregunta interactiva sobre que conservar todavia no esta implementada;
la compactacion actual es automatica. Para cambiar de tema, usa /new.

## Limites de salida de herramientas (activos)

El launcher escribe `limits.json` en cada perfil y lo pasa a OMP con
`--config`. Valores vigentes para todos los modelos: `read` devuelve 250 lineas
por defecto (un componente React chico entra en una lectura); la salida de
herramientas que pasa de 8 KB se guarda como artefacto
y deja en linea 2 KB iniciales + 4 KB finales (maximo 60 lineas de cola); bash
recorta su captura a 64 KB; la compactacion conserva ~3000 tokens recientes
(6000 con 32K) en vez de los 20000 por defecto, que excedian la ventana.
El modelo puede pedir mas con offset/limit; el tope evita que una sola lectura
o comando consuma el contexto.

## Idea de desarrollo para RX 6600: contexto con contratos

Propuesta, no funcion instalada ni afirmacion de novedad mundial:
antes de cada paso, construir un paquete pequeno con objetivo, restricciones,
fragmentos relevantes y una prueba verificable. Guardar el resto fuera del
contexto. Cada dato retenido lleva fuente (archivo y version) y condicion de
caducidad; si cambia el archivo, se invalida y se vuelve a leer.

Cuando falta espacio, preguntar que objetivo conservar; reconstruir el paquete
con esas fuentes, en vez de resumir reiteradamente toda la charla. Dar al modelo
un cambio pequeno por vez y devolverle el error concreto de la prueba.

La hipotesis: en 8GB conviene gastar memoria y tokens en evidencia vigente y
verificacion. Esto no aumenta la inteligencia del modelo ni garantiza aciertos.
Medir tareas resueltas por minuto y errores, no solo tokens por segundo.

## Desde el telefono (Termius / PowerShell)

```powershell
cd Z:\catts\local-coding
.\SMOL.cmd
# Ayuda sin cargar la GPU:
.\SMOL.cmd --docs
# Verificar archivos instalados sin cargar modelos:
.\SMOL.cmd --check
```

El telefono es la terminal; el calculo ocurre en la PC. La PC debe estar
encendida y accesible por SSH. No hace falta publicar el puerto del modelo.
Cerrar Termius no garantiza que la sesion siga viva: este launcher no instala
un servicio persistente. Para terminar ordenadamente: /exit y luego 0.
Si se corta la conexion, reconecta y comprueba si Smol sigue abierto antes de
intentar iniciar otro. No borres archivos de bloqueo ni mates procesos ajenos.

## Pedidos que ayudan al modelo

Una tarea concreta por turno. Ejemplo para Proyecto:

> Lee archivo.py y explica la funcion calcular_total. Todavia no edites.
> Luego corrige solo el caso de lista vacia. Conserva la interfaz publica.
> Ejecuta esta prueba: [comando]. Informa el resultado real y lo pendiente.

Indica archivo, comportamiento esperado y como comprobarlo. Si falla, pasa el
error exacto y el fragmento relevante. Una afirmacion de "funciona" no reemplaza
una prueba ejecutada. Revisa el diff antes de aceptar el resultado; trabajar en
una copia o rama facilita deshacer cambios. No pegues claves ni credenciales.

## Cuando la conversacion se vuelve larga

Antes de cambiar de tema, pedi este relevo y guarda el resultado:

> Resume objetivo actual, restricciones, decisiones, archivos modificados,
> pruebas ejecutadas con resultados y siguiente paso. Marca dudas como dudas.
> Incluye rutas para volver a leer las fuentes. Omite intentos ya descartados.

Usa /new y pega ese relevo. En Proyecto, pedi que vuelva a leer los archivos
pertinentes: el resumen puede omitir detalles. Si ya no queda espacio para
resumir, usa /resume para consultar la sesion y arma un relevo breve manual.
La compactacion automatica no garantiza evitar un desborde si una sola entrada,
salida de herramienta o respuesta consume el espacio restante.

## Si algo anda mal

| Sintoma | Primer paso |
| --- | --- |
| Piensa mucho sin responder | Esc; volver con /exit y elegir Rapido. |
| Contexto lleno o respuesta cortada | /new con un relevo corto; reducir archivos y logs pegados. |
| Smol ya esta abierto | Volver a la terminal anterior y salir con /exit y 0. |
| Falta un archivo del modelo | Ejecutar SMOL.cmd --check; guardar el error. No descarga solo. |
| Error al cargar o falta de memoria | Salir de Smol; liberar aplicaciones que usan GPU y reintentar. |
| No encuentra el proyecto | Pasar ruta absoluta entre comillas. |
| Resultado incorrecto | Dar un caso minimo y el error; revisar antes de autorizar otro cambio. |

Para pedir ayuda, copia el error y la ruta del registro que imprime el launcher.
Evita pegar registros completos si contienen datos privados.

## RX 6600: prioridades practicas

No hace falta cerrar todas las aplicaciones de antemano. Si falta memoria,
libera primero juegos, otros modelos o aplicaciones que esten usando GPU.
El ajuste instalado es 32K por defecto (Nanbeige 16K); llenarlo de sobra
consume minutos de prefill y no corrige errores de razonamiento. Mas tokens de
pensamiento tampoco garantizan una mejor respuesta. Compara resultados
comprobables en tus propias tareas.

Siguiente desarrollo propuesto, por orden:

1. Mostrar ocupacion del contexto y preguntar que conservar antes del limite.
2. Guardar objetivo y decisiones aparte, con referencias a archivos vigentes.
3. Preparar solo los fragmentos necesarios para cada cambio.
4. Verificar cada cambio con pruebas y devolver errores concretos al modelo.

Estos cuatro puntos son propuestas; esta ampliacion agrega documentacion.

## Repo complejo y JSX grande: receta de uso

Estado actual: 32K por defecto (Nanbeige 16K), validado en los 7 modelos;
`--context 16384` para menos prefill en sesiones profundas. La pregunta
interactiva antes de compactar sigue sin implementar. Las instrucciones
siguientes ayudan, pero el modelo puede incumplirlas.

1. Trabaja en una copia o rama y revisa primero tus cambios pendientes.
2. Abre el proyecto desde PowerShell:

```powershell
cd Z:\catts\local-coding
.\SMOL.cmd "C:\ruta\a\tu-repo" --model qwen35 --mode project --thinking off
```

3. Pega este pedido, reemplazando los nombres y la tarea:

> Objetivo: corregir [comportamiento] en [componente]. Primero lee las
> instrucciones del proyecto. No leas el JSX completo ni recorras todo el repo.
> Busca el nombre del componente en [carpeta concreta]; devuelve solo rutas y
> coincidencias necesarias. Lee ventanas de hasta 80 lineas alrededor de la
> funcion relevante usando offset/limit si la herramienta lo permite.
> Excluye node_modules, dist, build, archivos generados y lockfiles salvo que
> sean necesarios para esta tarea. Explica que falta antes de editar.
> Si un fragmento es enorme o esta minificado, no lo vuelques entero.

4. Revisa su diagnostico. Pide un cambio pequeno, conservando interfaces y
pruebas existentes. Autoriza solo comandos cuyo alcance entiendas.
5. Pide la prueba relevante y revisa su salida real y el diff. Para JSX,
comprueba tambien el comportamiento visual en tu aplicacion: compilar no
prueba que botones, estado y estilos funcionen correctamente.
6. Antes de acumular otra tarea, guarda el relevo descrito arriba y usa /new.

### Si necesitas controlar vos lo que entra

Chat no puede abrir archivos por su cuenta: podes pegar solo el fragmento
seleccionado. Esta es una forma manual de controlar la entrada si Proyecto
insiste en leer demasiado. Para sacar una ventana en PowerShell:

```powershell
# Cambia la ruta. Muestra lineas 201 a 260, limitadas a 12000 caracteres.
$smolFragment = (Get-Content -LiteralPath 'C:\ruta\Componente.jsx' |
    Select-Object -Skip 200 -First 60) -join "`n"
if ($smolFragment.Length -gt 12000) {
    $smolFragment = $smolFragment.Substring(0, 12000)
}
$smolFragment
```

El corte puede dejar una funcion incompleta: indica al modelo que es un
fragmento y agrega imports, props o helpers relevantes por separado.
12000 caracteres NO equivalen a 12000 tokens. Es un limite manual de salida,
no un calculo de capacidad ni una garantia. Este comando puede leer mucho del
archivo en la PC, pero solo el fragmento que pegues entra en el chat.

### Problemas y como resolverlos

| Problema | Que hacer |
| --- | --- |
| Lee todo pese al pedido | Esc. Los topes de salida ya recortan lecturas y comandos; si aun asi llena el contexto, usa Chat con fragmentos manuales. |
| Una sola linea ocupa muchisimo | Puede ser codigo minificado o datos incrustados. Busca el fuente original; limita tambien caracteres. |
| No entiende el fragmento | Agrega la firma, imports, props y la definicion del helper que falta. No pegues todo por reflejo. |
| Cambia algo y rompe otro componente | Revisa usos/importaciones del simbolo cambiado y ejecuta pruebas relacionadas antes de ampliar el cambio. |
| Contexto lleno | Esc si sigue generando; guarda un relevo breve y /new. Recupera fuentes desde disco. |
| Se equivoca reiteradamente | Reduce a un caso reproducible. Si sigue fallando, conserva el diagnostico y resuelve ese paso manualmente o con un modelo mas capaz. |
| Modifico algo incorrecto | Revisa el diff y deshaz solo ese cambio. No uses reset --hard ni descartes archivos con trabajo previo. |
| Muy lento o error de memoria | /exit; libera otras cargas GPU. Si estabas experimentando con mas contexto, vuelve a 16K y reinicia. |

### Contexto: 32K validado para los 7 modelos (sonda 2026-09-10)

`--context 16384|24576|32768` ajusta a la vez el servidor y la ventana
anunciada a OMP; no hay modo mixto. Reservar KV para 32K no cuesta velocidad
hasta que el contexto se llena: el costo real es el prefill al llenarlo.
Medido con `scripts/probe_load.py` (KV q8_0, todo en VRAM, --no-mmap,
data/smol/probes/20260910-132121/rows.jsonl):

| Modelo | Carga | VRAM modelo | KV 32K | RAM proceso | 8 tokens (1a respuesta) |
|---|---|---|---|---|---|
| MiniCPM5 2B | 50 s | 2,3 GB | 0,7 GB | 0,5 GB | 0,3 s |
| Nanbeige 3B | 72 s | 3,7 GB | 3,0 GB | 0,7 GB | 0,8 s |
| Gemma E4B | 80 s | 2,5 GB | 0,3 GB | 2,2 GB (embeddings en RAM) | 4,3 s |
| Bonsai 27B Q1 | 77 s | 3,4 GB | 1,1 GB | 0,5 GB | 1,5 s |
| Qwen2.5 Coder 7B | 81 s | 4,2 GB | 0,9 GB | 0,6 GB | 0,4 s |
| Qwen3.5 9B | 100 s | 4,9 GB | 0,5 GB | 0,9 GB | 1,0 s |
| Gemma 12B Q3 | 126 s | 5,8 GB | 0,5 GB | 1,2 GB | 18,5 s (incluye warmup) |

Nanbeige queda en 16K por defecto: a 32K suma 6,7 GB de VRAM y el escritorio
tambien usa la GPU. Gemma 12B carga pero su primera respuesta es lenta.

Medido en esta RX 6600 el 2026-09-08 sobre MiniCPM
(data/smol32k-trial-20260908-101203/report.json), vigente como referencia de
velocidad a contexto profundo:

- Carga en 32K: 3,57 GB de VRAM del proceso; 3,7 GB en total dedicado de la
  GPU. Queda margen sobrado en 8 GB; la memoria no es el limite.
- Prompt de 23.878 tokens: recordo 3 marcadores exactos (inicio, medio, fin),
  sin errores. Lectura y respuesta correctas tambien via OMP con 32K anunciado.
- Velocidad: prefill ~79 tok/s (llenar 24K la primera vez tarda ~5 minutos),
  decodificacion ~33 tok/s a esa profundidad (48-60 tok/s con contexto corto).
  El tiempo de prefill, no la VRAM, es lo que desaconseja pasar de 32K.
- Tarea pequena real (corregir una funcion con prueba): fallo sin llamar
  herramientas, igual que en los ensayos de codigo previos. 32K no mejora el
  razonamiento; solo amplia cuanto material puede sostener.

Uso sensato: 32K para leer un archivo grande o relevar contexto en una sesion
larga, sabiendo que cada llenado nuevo cuesta minutos de prefill. Para chat y
tareas acotadas, 16K sigue siendo mejor opcion porque responde mas rapido.

## Sin internet

Todo el circuito es local: llama-server en 127.0.0.1:9104, OMP con
`--no-extensions --no-skills` y los GGUF en disco. Un corte de internet no
afecta ninguna funcion de Smol, ni Chat ni Proyecto.

## Disco y tiempos de carga

Politica: modelos, runtimes y demas archivos pesados van en Z:. Nada de
20 GB en C: (poco espacio libre); C: no es destino para pesos ni descargas.

Z: es un HDD (~34 MB/s secuencial medidos). Smol usa `--no-mmap`: la lectura
secuencial carga ~2x mas rapido que paginar por mmap, y con todo el modelo en
VRAM (-ngl 999) el proceso queda por debajo de 1 GB de RAM (876 MB pico con
5,7 GB de modelo). Piso de RAM libre por modelo: 2,8 GB para E4B (mantiene
1,9 GB de embeddings en RAM), 1,8 GB para Gemma 12B, 1,5 GB para el resto.
El tiempo de espera de carga se calcula por tamano de archivo; el launcher
avisa cuantos minutos puede tardar. No mover modelos a C: como atajo de
velocidad: C: no tiene margen para archivos de GB.

## Agregar un modelo ya descargado

Destino siempre en Z: (data/models o Z:/Models/coding). Nada en C:.

1. `python scripts/register_local_model.py RUTA\MODELO.gguf` escribe el
   `.verified.json` (bytes + sha256 local; no prueba procedencia de HF).
2. Sumar la entrada a `MODELS` en scripts/smol.py (ruta absoluta o relativa a
   data/models).
3. `npm run smol:check` verifica. Hasta ~6,5 GB entra entero en la RX 6600.

`smol.py --check` tambien lista todo GGUF de Z: con su estado: Smol, cabe en
VRAM, solo carga parcial, blob Ollama (27 GB sin ollama.exe), duplicado o
demasiado chico (descarga incompleta, p. ej. Ornith-1.5-9B-Official de 0,5 GB).
No borra nada; el duplicado de Qwen2.5 Coder en Z:\AI\models es el que usa el
servidor previo de 8123, asi que queda para decision manual.

## Bucles de herramientas

Al cerrar una sesion de Proyecto, el launcher revisa las sesiones escritas y
avisa si hubo 3+ llamadas identicas seguidas o 3+ turnos con error seguidos.
`python scripts/smol_loops.py [registro.jsonl]` lo corre a mano. El prompt de
Proyecto ademas pide al modelo detenerse y explicar tras dos fallos iguales.
Interrumpir en vivo requeriria cambiar OMP; no esta hecho.

## Humo de edicion (mover un div)

`python scripts/smol_fixture.py --models qwen35 coder7` carga cada modelo,
le pide mover un div en un App.jsx minimo con `--approval-mode write` y
verifica que el archivo cambio. Resultado 2026-09-10 a 32K: Qwen3.5 9B paso
(leyo, edito, corrigio su primer intento, verifico: 6,6K tokens);
Qwen2.5 Coder 7B fallo emitiendo la llamada `edit` como texto en un bloque
```json y citando un index.html inexistente. Es verificacion del launcher y
del prompt, no un ensayo comparativo de modelos.
