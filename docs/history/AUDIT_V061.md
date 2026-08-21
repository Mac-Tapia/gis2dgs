# Auditoría de cierre — gis2dgs v0.6.1

## Alcance

Esta auditoría revisa las Fases 0–6 antes de iniciar el mapping DGS/PowerFactory.

## Correcciones solicitadas

### 1. Generación / DER

IMPLEMENTADA.

Se añadió el modelo canónico `Generator`, `GeneratorId`, almacenamiento en
`NetworkModel`, mapping GIS `generators`, validación de referencia a bus y calidad de
datos. La generación no crea aristas topológicas: representa una inyección conectada a
un bus.

### 2. Consistencia de versión

CORREGIDA.

`pyproject.toml`, `gis2dgs.__version__` y `config/settings.yaml` usan `0.6.1`.
Existe una prueba automática que impide divergencias entre esas tres fuentes.

### 3. Ejemplo de secuencia cero de transformador

CORREGIDO.

Se eliminó del ejemplo de producción la recomendación inválida `uk0_percent: 0.0` y
`ur0_percent: 0.0`. Los valores opcionales deben provenir de datos técnicos
verificados.

### 4. Aceptación PostGIS real

INFRAESTRUCTURA DE PRUEBA IMPLEMENTADA.

Se añadió `tests/integration/test_postgis_real_v061.py`, que cuando existe
`GIS2DGS_POSTGIS_TEST_URL`:

1. se conecta a PostgreSQL/PostGIS real;
2. ejecuta `PostGIS_Version()`;
3. crea una tabla temporal con `geometry(Point, 4326)`;
4. inserta un punto mediante funciones PostGIS;
5. lo lee con `GeoPandas.read_postgis` a través de `PostGisReader`;
6. verifica ID, CRS y coordenadas.

También se añadió el extra `.[postgis]` con `psycopg[binary]` y la guía
`docs/POSTGIS_ACCEPTANCE.md`.

En el entorno de generación de v0.6.1 no existe una URL/credencial PostGIS real. Por
seguridad no se inventó ni almacenó ninguna credencial. En consecuencia, esta prueba
queda **SKIPPED** durante la auditoría local. Esto no es una simulación aprobada como
prueba real: la aceptación contra la base de datos de destino debe ejecutarse en el
entorno que disponga de `GIS2DGS_POSTGIS_TEST_URL`.

## Resultado de pruebas de v0.6.1

- Suite completa local: `168 passed, 1 skipped, 0 failed`.
- El único `skipped` es la prueba PostGIS real por ausencia de URL de prueba.
- Cobertura: 94% (`1890` statements, `111` no cubiertos).
- `python -m compileall -q src tests`: OK.
- Configuraciones YAML principales: validadas correctamente.
- Importación dinámica: 59 módulos, 0 errores.
- Líneas Python mayores a 100 caracteres en `src/` y `tests/`: 0.
- Instalación editable en el entorno disponible: OK.
- CLI: `gis2dgs --version` devuelve `0.6.1`.
- Advertencias: 4 `DeprecationWarning` provenientes de `pyproj`; no generan fallos.
- `ruff` y `mypy`: configurados, pero no instalados en este entorno, por lo que no se
  reportan como ejecutados.

## Cierre de fases

A nivel de **implementación, estructura y pruebas automatizadas reproducibles**, las
Fases 0–6 quedan cerradas en v0.6.1.

La prueba PostGIS real queda como **prueba de aceptación del entorno de integración**.
Antes de desplegar contra una GIS DB real debe ejecutarse:

```powershell
pip install -e ".[dev,postgis]"
$env:GIS2DGS_POSTGIS_TEST_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
pytest -m postgis -v
```

No debe iniciarse la escritura DGS suponiendo que esta prueba fue ejecutada si la URL
no estuvo disponible.
