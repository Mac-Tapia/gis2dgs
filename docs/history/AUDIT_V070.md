# Auditoría de implementación — gis2dgs v0.7.0

## Alcance

Fase 7: `NetworkModel + ElectricalLibrary -> PowerFactoryModel`.

## Implementación añadida

- clases PowerFactory configurables;
- foreign keys deterministas;
- modelo intermedio PowerFactory version-neutral;
- jerarquía `ElmNet / ElmSubstat / ElmTerm`;
- node-breaker con `StaCubic` explícitos;
- mapping de líneas, transformadores, switches, cargas, DER/generadores y fuentes;
- mapping de `TypLne` y `TypTr2`;
- validación de padres y referencias;
- configuración `powerfactory_mapping.yaml`;
- asociación opcional `Bus -> Substation`;
- DGS exacto mantenido como frontera de Fase 8.

## Resultado automatizado

- 192 pruebas aprobadas;
- 1 prueba PostGIS omitida por falta de `GIS2DGS_POSTGIS_TEST_URL`;
- 0 pruebas fallidas;
- cobertura global: 94%;
- `compileall`: correcto;
- 67 módulos importados correctamente usando `PYTHONPATH=src`;
- 0 líneas Python mayores a 100 caracteres;
- CLI desde código fuente: `0.7.0`.
- wheel `gis2dgs-0.7.0-py3-none-any.whl`: construido e instalado en entorno de humo.
- CLI desde wheel instalado: `0.7.0`.

## Limitaciones pendientes

- No se ha ejecutado importación en una instalación real de PowerFactory.
- No se ha validado todavía un archivo DGS concreto porque falta un DGS patrón de la
  esquema DGS de referencia.
- `ruff` y `mypy` no están instalados en el entorno de generación y no se reportan
  como ejecutados.

## Estado

Fase 7 implementada a nivel de mapping canónico PowerFactory. La Fase 8 debe cerrar
la traducción a columnas/tablas DGS exactas usando un export de referencia.
