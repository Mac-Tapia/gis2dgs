# Hermes Agent + GIS2DGS

Hermes Agent ([Nous Research](https://github.com/nousresearch/hermes-agent), MIT) es un agente
autónomo open source. En este repo **no sustituye** a Cursor para edición fina: lo complementa para
tareas largas, cron y memoria entre sesiones, usando el **mismo** skill y harness.

## Arranque rápido (Windows + WSL2)

Ya tienes Ubuntu WSL. Desde la raíz del repo en PowerShell:

```powershell
# 1) Instalar Hermes dentro de WSL + confiar skills del proyecto
.\scripts\install_hermes.ps1

# 2) Configurar proveedor LLM (API key; interactivo, no se guarda en el repo)
.\scripts\hermes.ps1 model

# 3) Comprobar
.\scripts\hermes.ps1 doctor

# 4) Usar el skill GIS2DGS
.\scripts\hermes.ps1 chat -q "/gis2dgs resume el flujo convert + verify gate"
```

Wrapper diario (cualquier subcomando de Hermes, CWD = repo):

```powershell
.\scripts\hermes.ps1 skills list
.\scripts\hermes.ps1 chat
.\scripts\hermes.ps1 doctor
```

## Qué gana el proyecto

| Capacidad | Uso en GIS2DGS |
|-----------|----------------|
| Skill de proyecto | `/gis2dgs` carga las mismas reglas que Cursor (`AGENTS.md` + skill) |
| Terminal + cron | Convertir paquetes, `run_verify_gate.py`, reportar fallos |
| Memoria / skills | Recordar playbooks de conversión sin reexplicar el flujo |

## Ubicación del skill

```text
skills/gis2dgs/SKILL.md                 # fuente de verdad (Cursor + Hermes)
.agents/skills/gis2dgs/SKILL.md         # entrada project-local Hermes
agent/hermes.config.example.yaml        # plantilla (sin secretos)
scripts/install_hermes.ps1              # instala en WSL + skills trust
scripts/hermes.ps1                      # ejecuta hermes vía WSL en el repo
scripts/setup_hermes_skills.ps1         # verifica que el skill exista
```

Comprobar skill sin instalar:

```powershell
.\scripts\setup_hermes_skills.ps1
```

## Instalación manual (alternativa)

Dentro de una terminal Ubuntu WSL:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --skip-browser
cd /mnt/d/converter/gisdgsv1   # ajuste si su ruta difiere
hermes skills trust
hermes model
hermes doctor
```

Nativo Windows (si lo prefiere):

```powershell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
.\scripts\install_hermes.ps1 -NativeWindows
```

## Relación con el harness Cursor

| Capa | Cursor | Hermes |
|------|--------|--------|
| Guías | `AGENTS.md`, `skills/gis2dgs` | Mismo skill vía `.agents/skills` |
| Enforcement | `.cursor/hooks` | No aplica; el skill exige el verify gate |
| Sensor | `scripts/run_verify_gate.py` | Ejecutar el mismo comando al terminar |
| CLI | Agent en IDE | `.\scripts\hermes.ps1 …` |

## Seguridad

- No pegar credenciales en chat de mensajería ni commitear `.env` / `~/.hermes/.env`.
- No sobrescribir `data/reference/real/`.
- Confirmar antes de `git commit` / `git push`.
- `hermes skills trust` autoriza el skill del repo de forma consciente.
