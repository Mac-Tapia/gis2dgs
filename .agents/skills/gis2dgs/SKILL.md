---
name: gis2dgs
version: 1.1.0
description: GIS→DGS PowerFactory; mapping YAML, validate, verify gate
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [gis, powerfactory, dgs, electrical, converter]
    category: devops
    requires_toolsets: [terminal]
---

# GIS2DGS — entrada Hermes

Antes de cualquier cambio o conversión, lea el skill canónico completo:

`skills/gis2dgs/SKILL.md`

Ese archivo es la fuente de verdad compartida con Cursor (`AGENTS.md` + harness).

## Procedure (resumen)

1. CWD = raíz del repo; use `.venv` si existe.
2. Salidas solo bajo `output/`. Mapping por YAML/esquema — nunca `if ArcGIS` / `if IGEA`.
3. No escriba DGS sin `NetworkModel` + validación.
4. Tras cambiar código: `python scripts/run_verify_gate.py`.
5. Pregunte antes de `git commit` / `git push`.

## Slash

`/gis2dgs` → cargar este skill y abrir el canónico en `skills/gis2dgs/SKILL.md` (playbooks §11).

## Verification

`python scripts/run_verify_gate.py` debe terminar en PASS.

Guía de instalación Hermes: `docs/HERMES_AGENT.md`.
