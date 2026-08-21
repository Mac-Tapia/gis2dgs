# Release notes — GIS2DGS 1.0.0

GIS2DGS 1.0.0 es la primera release estable del conversor universal de datos de
red eléctrica hacia DGS Excel para DIgSILENT PowerFactory.

## Hitos

- neutral respecto al producto de origen;
- lectores por formato/DB;
- mapping YAML;
- dominio eléctrico canónico;
- topología y tracing;
- validación multinivel;
- biblioteca eléctrica;
- modelo PowerFactory node-breaker;
- DGS estructural y neutral respecto de versión de PowerFactory;
- CLI, wheel, ejemplo reproducible, auditoría y benchmark.

## Evidencia de release

- 247 pruebas aprobadas, 1 prueba PostGIS omitida por ausencia de credenciales;
- 91% de cobertura global;
- referencias reales `SALIDA_DGS.xlsx` y `M_ALIMENTAD.xlsx` verificadas en tests;
- 93 módulos importados sin error;
- conversión mínima end-to-end aprobada;
- benchmark topológico de 50.000 buses aprobado;
- wheel `gis2dgs-1.0.0-py3-none-any.whl` construido y ejecutado fuera del árbol `src`.
