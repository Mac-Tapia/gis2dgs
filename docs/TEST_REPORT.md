# Reporte de pruebas — GIS2DGS 1.0.0

## Suite completa con referencias reales disponibles

```text
247 passed
1 skipped
0 failed
```

La única prueba omitida es la integración contra PostGIS real porque el entorno de
auditoría no dispone de `GIS2DGS_POSTGIS_TEST_URL`.

## Cobertura

```text
TOTAL: 3442 statements
MISS: 310
COVERAGE: 91%
```

La suite incluye pruebas unitarias e integración para dominio, normalización,
topología, validación, librería eléctrica, modelo PowerFactory, DGS, lectores
universales, configuración, CLI y pipeline end-to-end.

## Referencias reales del usuario

Con:

```text
GIS2DGS_DGS_REFERENCE=/mnt/data/SALIDA_DGS.xlsx
GIS2DGS_REAL_INPUT=/mnt/data/M_ALIMENTAD.xlsx
```

la prueba de referencias reales obtuvo:

```text
2 passed
```

Se verificó DGS format revision 5, hojas/claves reales como `TypLne`, `StaCubic`
y `StaSwitch`, y columnas reales de `M_ALIMENTAD`.
