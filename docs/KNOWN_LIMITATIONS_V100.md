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
   el motor de cálculo propietario. Las hojas `IntGrfnet` / `IntGrf` / `IntGrfcon` se
   generan con coordenadas de diagrama (origen + escala); no hay librería open source
   que sustituya al importador DGS de DIgSILENT.
7. El pipeline es in-memory. Para redes de millones de objetos debe utilizarse
   particionamiento/consultas de origen o evolucionar a procesamiento streaming.
8. Formatos GIS “más usados” ya cubiertos por readers: Excel/CSV, vector OGR
   (shp/gpkg/geojson/gml/kml/gdb), Parquet, DB URL/PostGIS, `.bak`, texto CYMDIST.
   **No** hay readers dedicados (ni ramas de marca) para DXF/DWG, MapInfo TAB,
   servicios Feature Server REST, ni binarios propietarios IGEA distintos del
   export de texto seccionado. Exporte a un formato de la tabla en
   `docs/SUPPORTED_INPUTS.md` y mapee columnas en YAML.
