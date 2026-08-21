# Auditoría de release — gis2dgs v0.8.1

## Alcance de cierre

`v0.8.1` cierra formalmente las **Fases 0–8** del conversor independiente GIS → DGS.
La automatización mediante la API Python de PowerFactory pertenece a la Fase 9 y no
forma parte de este release.

## Corrección arquitectónica principal

La Fase 8 dejó de utilizar un concepto de esquema dependiente de versión. La API
canónica es ahora `DgsSchema`.

La compatibilidad DGS se resuelve por estructura:

- tablas/hojas;
- columnas;
- identidad/foreign keys;
- referencias;
- transformaciones de valores;
- filas de cabecera y datos.

No existen campos `powerfactory_version`, `digsilent_version` ni `dgs_version` en
`DgsSchema` o `DgsSchemaConfig`.

Para mantener compatibilidad con código v0.8.0:

- `DgsMappingProfile` es alias de `DgsSchema`;
- `DgsMappingConfig` es alias de `DgsSchemaConfig`;
- `load_dgs_mapping_profile()` delega a `load_dgs_schema()`.

## Resultado de pruebas

Suite ejecutada sobre el árbol final de fuentes:

- **219 passed**;
- **1 skipped**;
- **0 failed**;
- **4 warnings** de `pyproj`/NumPy en pruebas de reproyección GIS.

La prueba omitida es la aceptación contra PostGIS real y requiere la variable
`GIS2DGS_POSTGIS_TEST_URL`.

## Cobertura

`pytest --cov=gis2dgs --cov-report=term-missing`:

- cobertura global: **93 %**;
- `dgs/mapper.py`: 95 %;
- `dgs/schema.py`: 88 %;
- `dgs/template.py`: 95 %;
- `dgs/validation.py`: 92 %;
- `dgs/writer.py`: 82 %;
- `config/dgs.py`: 93 %.

## Controles ejecutados

- `python -m compileall -q src tests`: **OK**;
- importación de módulos: **72/72 OK**;
- errores de importación: **0**;
- líneas Python mayores a 100 caracteres: **0**;
- versiones `package / pyproject / settings`: **0.8.1 / 0.8.1 / 0.8.1**;
- `pip install -e . --no-deps --no-build-isolation`: **OK**;
- `gis2dgs --version`: **0.8.1**;
- wheel `gis2dgs-0.8.1-py3-none-any.whl`: **construido e importado correctamente**;
- contrato de neutralidad DGS ejecutado por `scripts/audit_release.py`: **APROBADO**.

`ruff` y `mypy` permanecen configurados en `pyproject.toml`, pero sus ejecutables no
estaban instalados en el entorno de auditoría. Por ello no se reportan como
controles ejecutados.

`pip check` sobre el entorno global detectó una incompatibilidad externa entre
`moviepy` y `pillow`; no pertenece a las dependencias de `gis2dgs` y no se utiliza
como criterio de aprobación de este release.

## Estado de `config/dgs_mapping.yaml`

El archivo permanece deliberadamente:

```yaml
configured: false
classes: {}
```

Esto es una **barrera de seguridad**. El motor no debe inventar nombres de columnas
DGS. Para la aceptación con datos reales se debe inspeccionar un DGS de referencia,
completar el esquema y activar `configured: true`.

## Resultado de cierre

**RELEASE v0.8.1: APROBADO para el alcance Fases 0–8.**

Pendientes externos, no defectos del motor:

1. incorporar un DGS de referencia del usuario y ejecutar importación de aceptación
   en PowerFactory;
2. ejecutar la prueba PostGIS real cuando se disponga de una base de prueba;
3. Fase 9: automatización PowerFactory API, si se desea continuar el proyecto.
