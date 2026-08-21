# GIS2DGS 1.0.0 — Auditoría del paquete integral

## Alcance

Esta auditoría corresponde al paquete único que incluye código fuente, configuración, pruebas,
ejemplos, documentación, manual para agentes, referencias reales, scripts de instalación/verificación
y el wheel de la release 1.0.0.

## Resultado ejecutado

- Suite de pruebas: **250 passed, 1 skipped, 0 failed**.
- Único `skip`: aceptación contra un servidor PostGIS real; requiere `GIS2DGS_POSTGIS_TEST_URL`.
- Las dos referencias reales incluidas en el ZIP (`SALIDA_DGS.xlsx` y `M_ALIMENTAD.xlsx`) se ejecutan en
  la suite y no requieren variables externas.
- Cobertura de `gis2dgs`: **91 %** en el entorno de auditoría.
- `compileall`: aprobado.
- Importación dinámica de módulos: **93 módulos, 0 errores**.
- Detección universal: **12 casos, 0 fallos**, incluidos Excel, CSV/TSV, formatos vectoriales,
  Parquet, SQLite, PostgreSQL, SQL Server, Oracle y MySQL/MariaDB mediante URL SQLAlchemy.
- Dependencias de marca (`ArcGIS`, `IGEA`, `QGIS`) en `src/`: **0**.
- Selector de versión de producto PowerFactory/DIgSILENT en el contrato DGS: **0**.
- Conversión mínima end-to-end: aprobada y genera `minimal_dgs.xlsx`.
- Prueba de wheel incluido: `python -m gis2dgs --version` devuelve **1.0.0**.
- Benchmark de auditoría: red radial sintética de 50 000 buses analizada correctamente; el tiempo se
  registra en `docs/INTEGRAL_AUDIT.json` y no constituye un SLA contractual.

## Herramientas de calidad

`ruff` y `mypy` forman parte de `requirements.txt` y están configurados en `pyproject.toml`. En el
contenedor usado para empaquetar esta entrega no estaban preinstalados y no se descargaron paquetes
externos durante el cierre; por ello no se declara una ejecución que no ocurrió. El script de instalación
los instala en el entorno `.venv` del usuario junto con el resto del contrato Python.

## Reproducibilidad

El ZIP no contiene `.venv` ni dependencias binarias copiadas de otro equipo. Esto es intencional: esos
entornos no son portables. `INSTALL_AND_VERIFY.ps1` crea el entorno local, instala `requirements.txt`,
ejecuta las verificaciones y corre el ejemplo de punta a punta.

## Límite externo

La validación final de ingeniería sigue requiriendo importar el DGS resultante en una instalación real
de DIgSILENT PowerFactory y ejecutar el estudio requerido. El test PostGIS real también requiere un
servidor accesible. Estas dos dependencias externas no se simulan como si estuvieran aprobadas.
