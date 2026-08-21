# Entradas soportadas en GIS2DGS 1.0.0

## Detección automática

| Grupo | Formatos / conexión | Reader |
|---|---|---|
| Excel | `.xlsx`, `.xlsm`, `.xls` | `ExcelInputReader` |
| Delimitado | `.csv`, `.tsv` | `CsvInputReader` |
| Vector | `.shp`, `.gpkg`, `.geojson`, `.json`, `.gml`, `.kml`, `.gdb` | `VectorInputReader` |
| Columnar | `.parquet`, `.pq` | `ParquetInputReader` |
| Local DB | `.sqlite`, `.sqlite3`, `.db` | `SqlAlchemyInputReader` |
| SQL Server backup | `.bak` o archivo sin extensión con cabecera `TAPE` / Microsoft SQL Server | `MssqlBackupReader` (restaura y lee tablas) |
| DB URL | PostgreSQL, SQL Server, Oracle, MySQL/MariaDB, SQLite | `SqlAlchemyInputReader` |

**No soportado como archivo de tablas:** `.sql` (script de sentencias). Las consultas van
en `options.queries` del YAML. Un `.bak` sí se carga: se restaura en SQL Server
(`RESTORE` implementado) y entra al mismo pipeline hacia DGS. Arranque o detección
del motor: `scripts/ensure_mssql.ps1`. Ejemplo completo: `examples/mssql_backup/project.yaml`.

`.gdb` se detecta como directorio File Geodatabase cuando existe con esa extensión.

## Dependencias opcionales

- `.xls`: `pip install -e ".[excel-legacy]"`
- Parquet: `pip install -e ".[parquet]"`
- PostgreSQL/PostGIS: `pip install -e ".[postgresql]"`
- SQL Server: `pip install -e ".[sqlserver]"`
- Oracle: `pip install -e ".[oracle]"`

## Bases de datos

La entrada DB acepta:

- tablas completas;
- consultas SQL explícitas;
- consultas espaciales mediante GeoPandas/PostGIS y columna geométrica configurable;
- aliases de tabla lógica;
- `connect_args` del driver.

Ejemplo:

```yaml
inputs:
  sources:
    - id: network_db
      uri: $GIS2DGS_DB_URL
      kind: database
      options:
        tables: [nodes, lines, transformers]
        aliases:
          nodes: NODOS
          lines: LINEAS
```

## Universalidad

“Universal” significa que el motor está desacoplado del software que creó los
datos. No significa que cualquier conjunto de columnas desconocidas pueda
interpretarse eléctricamente sin mapping. El usuario debe definir cómo su esquema
representa buses, líneas, transformadores, cargas, fuentes, etc.
