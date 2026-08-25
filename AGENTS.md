# AGENTS.md — Contrato de trabajo para cualquier agente

Antes de modificar o ejecutar este proyecto, lea `skills/gis2dgs/SKILL.md` completo.

## Agent harness (Model + Harness)

Este repositorio incluye un **agent harness** para Cursor:

| Capa | Ubicación | Rol |
|------|-----------|-----|
| Guías | `AGENTS.md`, `skills/gis2dgs/SKILL.md`, `.cursor/rules/` | Instrucciones y límites |
| Enforcement | `.cursor/hooks.json` + `.cursor/hooks/` | Bloquea shell peligroso; marca verify pendiente; stop-gate |
| Sensores | `scripts/agent_harness/verify_gate.py` | `pytest` + `verify_integral_project.py` |
| Estado | `agent/progress.json`, `.cursor/harness/` | Progreso y veredicto (runtime; no commitear estado) |
| Hermes (opcional) | `.agents/skills/gis2dgs`, `docs/HERMES_AGENT.md` | Agente autónomo open source; mismo skill / verify gate |

Comando del sensor:

```powershell
python scripts/run_verify_gate.py
python scripts/run_verify_gate.py --quick
$env:GIS2DGS_HARNESS_STRICT = "1"   # stop-gate ejecuta la suite completa
```

Copie `agent/progress.example.json` → `agent/progress.json` y marque `passes: true` sólo con evidencia.

### Always / Ask / Never

**Always**

- Un solo repo; conversor universal por formato/esquema.
- Pruebas en `tests/` equivalentes al cambio.
- Salidas bajo `output/`.
- Cerrar el gate con `python scripts/run_verify_gate.py` antes de dar por terminado un cambio de código.

**Ask first**

- `git commit` / `git push`
- Destruir contenedores Docker o restaurar SQL fuera de ejemplos

**Never**

- `git push --force`, `git reset --hard`, `rm -rf` / `Remove-Item -Recurse -Force` destructivo
- Sobrescribir `data/reference/real/`
- Hardcodear credenciales, rutas personales o IDs de empresa
- Lógica `if ArcGIS` / `if IGEA` / versión PowerFactory hardcodeada

## Reglas obligatorias

- Este repositorio es la **única fuente de verdad**. No cree proyectos paralelos ni copias funcionales.
- El conversor es universal por formato/esquema. No introduzca lógica `if ArcGIS`, `if IGEA`, etc.
- `domain/` no debe depender de pandas/geopandas, bases de datos ni DGS.
- `input/` lee formatos y bases; `gis/` conserva sólo lógica geoespacial especializada.
- Las diferencias entre proveedores se resuelven mediante YAML/configuración y adaptadores.
- `dgs/` no debe conocer el software de origen de los datos.
- No seleccione una versión de PowerFactory para mapear DGS. Preserve la revisión DGS si el propio
  archivo la declara, pero la compatibilidad se evalúa por esquema/columnas/referencias.
- Nunca hardcodee credenciales, rutas personales o IDs de una empresa.
- Todo cambio de código debe incluir pruebas en la carpeta equivalente de `tests/`.
- Antes de considerar terminado un cambio ejecute `python -m pytest -q` y
  `python scripts/verify_integral_project.py` (o el gate unificado del harness).
- No sobrescriba archivos de referencia reales. Genere resultados bajo `output/`.

## Hermes Agent (opcional)

Para tareas autónomas largas (convertir paquetes, cron, reportes) use
[Hermes Agent](https://github.com/nousresearch/hermes-agent) con el skill del repo.

```powershell
.\scripts\install_hermes.ps1          # una vez (WSL2)
.\scripts\hermes.ps1 model            # API key / proveedor
.\scripts\hermes.ps1 chat -q "/gis2dgs resume el verify gate"
```

Detalle: `docs/HERMES_AGENT.md`. No sustituye el harness de Cursor.

## Comando de recuperación rápida

```powershell
.\INSTALL_AND_VERIFY.ps1
```
