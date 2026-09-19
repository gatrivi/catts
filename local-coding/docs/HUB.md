# CATTS local (hub)

Un solo terminal para todo: **CATTS.cmd** (o el acceso directo *CATTS local*).
No abre ventanas nuevas: cada modelo o app se lanza oculto, con su log en
`data/hub/logs/`. Los lanzadores viejos (SMOL.cmd, TALLER.cmd, MODELS.cmd)
siguen existiendo, pero el menu del hub es el camino normal.

## Menu

```
s N [preset]   arrancar     w N [preset]   cambiar de modelo (apaga y arranca)
x N            apagar       a              apagar todos los modelos
c N            chat directo l N            ver log
z N            que elegir en Zed           t / m  sesion Taller / Smol
r              refrescar    q salir        qa  salir y apagar todo
```

La lista tiene 19 numeros: 1-5 modelos con puerto propio (Bonsai-2 :9103,
Spark :9105, NeoHorse :9107, Qwen3.5 :9102, Qwen3.8-27B :9101), 6-16 la ranura
Smol (:9104, un modelo a la vez) y 17-19 las apps (CATTS API :59200,
Chores API :9111, gateway de voz :9110).

## Sin menu (para scripts)

```powershell
CATTS.cmd status                    # que esta vivo, RAM libre
CATTS.cmd check                     # valida runtimes, modelos, manifiestos y argv
CATTS.cmd list                      # numeros y claves
CATTS.cmd start bonsai2 --preset low
CATTS.cmd switch qwen35             # apaga lo que haya y arranca el otro
CATTS.cmd stop all                  # modelos y apps
CATTS.cmd chat mini                 # chat de terminal contra :9104
```

## Reglas del sistema

- La GPU es exclusiva para modelos: el hub se niega a arrancar dos a la vez
  (`--force` lo permite, con aviso). Para cambiar de modelo, usa `w`, no `s`.
- `switch` espera a que el anterior libere VRAM antes de cargar el siguiente.
- Pisos de RAM por modelo (6,2 GB para el 27B Q3, 3 GB para Bonsai-2; 1,5 GB el
  resto). Si no hay RAM libre, el hub no arranca nada.
- El hub reconoce modelos ya arrancados por otros scripts (por puerto/alias/
  ruta) y los muestra como ENCENDIDO; a los desconocidos no los toca.
- `q` sale dejando los modelos arriba; `qa` apaga todo antes de salir.

## Un solo lugar para los datos

`scripts/local_models.py` es la fuente de verdad: modelos, rutas, puertos,
alias, runtime por modelo, presets y pisos de RAM. Lo usan `scripts/hub.py` y
`scripts/smol.py`. Para agregar o cambiar un modelo se edita ese archivo
(`register_local_model.py` sigue sirviendo para generar el `.verified.json`).
