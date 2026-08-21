# Auditoría — gis2dgs v0.8.0

## Alcance

Auditoría de la implementación de Fase 8 sobre v0.7.0.

## Resultado

### Suite automatizada

- 209 pruebas aprobadas.
- 1 prueba omitida: PostGIS real sin `GIS2DGS_POSTGIS_TEST_URL`.
- 0 fallos.
- cobertura global: 93%.

### Controles estáticos ejecutables en el entorno

- `python -m compileall -q src tests`: OK.
- 71/71 módulos importados: OK.
- líneas Python > 100 caracteres: 0.
- versión CLI: 0.8.0.
- wheel `gis2dgs-0.8.0-py3-none-any.whl`: construido.
- wheel instalado con `pip --target --no-deps` y cargado utilizando las dependencias
  del entorno de pruebas: OK.
- imports de `DgsMapper`, `DgsWriter`, inspector y configuración desde el wheel: OK.

`ruff` y `mypy` permanecen configurados en `pyproject.toml`; no se reportan como
 ejecutados porque sus binarios no están disponibles en este runtime.

## Hardening adicional

Se corrigió `ForeignKeyFactory` para respetar un máximo por defecto de 40 caracteres.
Los IDs largos se truncan con un digest determinista para conservar unicidad práctica.

## Fase 8 implementada

- modelo `DgsDocument` / `DgsTable` / `DgsRow`;
- perfil DGS configurable;
- transformaciones de valor y referencia;
- `DgsMapper` estricto;
- validador DGS;
- inspector de template Excel;
- `DgsWriter` template-driven para `.xlsx`/`.xlsm`;
- CLI `dgs inspect-template`;
- loader Pydantic de `config/dgs_mapping.yaml`;
- pruebas unitarias e integración completa hasta archivo Excel.

## Limitación explícita

No se declara todavía que un archivo generado sea aceptado por **la instalación real
de PowerFactory del usuario**, porque no se ha proporcionado un DGS exportado desde
esa versión. El repositorio mantiene `configured: false` para impedir una falsa
compatibilidad.

La aceptación de Fase 8 queda en dos niveles:

1. **Implementación del motor:** APROBADA.
2. **Aceptación contra DGS/PowerFactory objetivo:** PENDIENTE DE TEMPLATE REAL.
