# Auditoría GIS2DGS 1.0.0

## Estado

**APROBADA** (`audit_passed = true`).

| Control | Resultado |
|---|---|
| Versión package / pyproject / settings | `1.0.0 / 1.0.0 / 1.0.0` |
| compileall | OK |
| módulos importados | 93 / 0 errores |
| líneas Python >100 caracteres | 0 |
| selectores de versión PowerFactory/DIgSILENT en DGS | 0 |
| revisión propia de formato DGS | soportada (`dgs_format_version`) |
| detección universal de entradas | 11 casos / 0 fallos |
| nombres ArcGIS/IGEA/QGIS en `src/` | 0 |
| credenciales DB hardcodeadas detectadas | 0 |
| conversión mínima end-to-end | OK, DGS 9699 bytes |
| referencias reales del usuario | 2 pruebas aprobadas |
| benchmark | 50,000 buses / 49,999 líneas / 2.558 s |

## Suite completa

```text
..........s............................................................. [ 29%]
........................................................................ [ 58%]
........................................................................ [ 87%]
................................                                         [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/test_postgis_real_v061.py:15: GIS2DGS_POSTGIS_TEST_URL is not configured.
247 passed, 1 skipped in 1.27s
```

## Transparencia de controles

`ruff` y `mypy` están configurados en `pyproject.toml`, pero sus ejecutables no
estaban instalados en el entorno de auditoría. No se declaran como ejecutados.
La compilación, importación de módulos, tests, cobertura, pipeline real, wheel y
benchmark sí fueron ejecutados.

## Condiciones externas

- PostGIS real: la prueba existe y queda `skipped` sin `GIS2DGS_POSTGIS_TEST_URL`.
- PowerFactory real: requiere importar el DGS producido en la instalación del
  usuario; esa aceptación no puede emularse localmente.
