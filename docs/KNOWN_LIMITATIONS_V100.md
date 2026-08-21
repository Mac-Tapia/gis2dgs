# Límites conocidos — GIS2DGS 1.0.0

1. La salida implementada en 1.0.0 es **DGS sobre Microsoft Excel**. La arquitectura
   permite añadir carriers ASCII/XML, pero no se declaran implementados en esta release.
2. La interpretación eléctrica de un esquema desconocido requiere `mapping.yaml`.
   Ningún conversor universal puede inferir de forma segura que una columna arbitraria
   representa tensión, potencia o conectividad sin metadatos/reglas.
3. Los drivers PostgreSQL, SQL Server, Oracle, Parquet y Excel `.xls` son extras
   opcionales; deben instalarse en el entorno destino.
4. La prueba PostGIS real necesita una DB accesible mediante
   `GIS2DGS_POSTGIS_TEST_URL`; no estuvo disponible en el entorno de auditoría.
5. El restore de `.bak` está implementado. Restaurar de verdad exige un proceso
   SQL Server (local, LocalDB/Express o Docker vía `scripts/ensure_mssql.ps1`).
   Sin motor, la prueba `mssql` se omite.
6. La aceptación definitiva del archivo DGS requiere importarlo en PowerFactory.
   GIS2DGS valida estructura, referencias y datos, pero no sustituye el importador ni
   el motor de cálculo propietario.
7. El pipeline es in-memory. Para redes de millones de objetos debe utilizarse
   particionamiento/consultas de origen o evolucionar a procesamiento streaming.
