# LM Studio + phone SSH (v0.1)

PC: LM Studio :42, model `ornith-1.0-9b`. Phone: Termius → SSH → Tailscale.

## Componentes

| Tool | Path | Notas |
|------|------|-------|
| omp | `~/.bun/bin/omp.exe` | No es `omp.sh`; en Windows es `.exe` |
| Hermes | `hermes` | Cron + `--yolo` para autonomía nocturna |
| LM Studio | `127.0.0.1:42` / Tailscale `100.87.252.18:42` | Auth requerido |
| Modelo | `ornith-1.0-9b` | Tool use, context 8192 |

## Setup (una vez)

1. LM Studio → Developer → Server Settings → Manage Tokens → Create Token
2. Copiar token (solo se muestra una vez)
3. Desde catts:

```powershell
cd e:\zengatrivi-drive-e\catts
.\scripts\setup-lmstudio.ps1 -Token "TU_TOKEN"
.\scripts\setup-lmstudio.ps1 -TestOnly
```

Token se guarda en `%USERPROFILE%\.secrets\lm-api-token` y en env user `LM_API_KEY`.

## omp (SSH desde teléfono)

```powershell
omp -p --model ornith-1.0-9b --auto-approve "lista los .py en scripts/"
```

Cambiar modelo: cargar otro en LM Studio (`lms load <id>`) y usar su API identifier.

## Hermes — loops nocturnos

```powershell
# Tarea única
hermes -z "Revisa docs/PROJECT_AUDIT.md y propone 3 fixes" --yolo --provider lmstudio -m ornith-1.0-9b

# Cola nocturna
.\scripts\overnight-queue.ps1

# Cron recurrente
hermes cron create "every 2h" "Corre check_env y resume errores" --workdir "e:\zengatrivi-drive-e\catts"
hermes cron tick
```

Desde Termius: SSH → `cd e:\zengatrivi-drive-e\catts` → lanzar script → desconectar.

## PATH / SSH

- User PATH incluye `~/.bun/bin`
- Profile: `Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` carga token
- Si `omp` no se encuentra: `where omp` o abrir nueva sesión SSH

## Config aplicada

- `~/.omp/agent/models.yml` — baseUrl `127.0.0.1:42/v1`
- `~/.omp/agent/config.yml` — default `lmstudio/ornith-1.0-9b`
- `~/.hermes/config.yaml` — provider `lmstudio`
- `~/.hermes/.env` — `LM_BASE_URL`
