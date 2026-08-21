# Criterios de aceptación — GIS2DGS 1.0.0

## Aprobados en la auditoría local

- versiones de paquete/config consistentes;
- compilación de todos los módulos;
- importación de todos los módulos;
- suite completa de pytest;
- cobertura de código medida;
- ejemplo end-to-end desde CSV hasta DGS Excel;
- inspección del DGS generado;
- inspección del DGS real `SALIDA_DGS.xlsx` cuando se proporciona por variable;
- inspección del input real `M_ALIMENTAD.xlsx` cuando se proporciona por variable;
- esquema DGS sin selector de versión de PowerFactory/DIgSILENT;
- benchmark topológico de red sintética grande;
- benchmark de certificación (`scripts/benchmark_converter.py`): ejemplo mínimo,
  precisión de mapping, tiempos inspect/convert, independencia de LLM/torch y
  detección `.bak` (restore implementado; motor con `scripts/ensure_mssql.ps1`);
- wheel instalable y CLI `gis2dgs`.

## Aceptaciones externas condicionadas

### SQL Server real (restore de `.bak`)

El restore está implementado. La prueba marcada `mssql` requiere un proceso SQL Server
(`GIS2DGS_MSSQL_URL` o el resultado de `scripts/ensure_mssql.ps1`). Sin motor, la
prueba figura como `skipped`; no se sustituye por un restore fingido.

### PostGIS real

Existe una prueba marcada `postgis` que requiere:

```text
GIS2DGS_POSTGIS_TEST_URL
```

Sin credenciales de una base externa, la prueba debe figurar como `skipped`; no se
considera correcto reemplazarla por una afirmación ficticia.

### PowerFactory real

La aceptación funcional final requiere importar el DGS generado en la instalación
PowerFactory objetivo, revisar el log de DGS y ejecutar por lo menos un flujo de
carga. La auditoría local valida estructura y referencias pero no puede simular el
motor propietario de PowerFactory.

## Reglas de release

Una release no se aprueba si falla pytest, compileall, importación de módulos,
conversión mínima end-to-end, consistencia de versiones o contrato DGS neutral
respecto del producto.
