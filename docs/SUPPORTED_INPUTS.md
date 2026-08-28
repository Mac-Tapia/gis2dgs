# Entradas soportadas en GIS2DGS 1.0.0

## Detección automática

| Grupo | Formatos / conexión | Reader | Estado |
|---|---|---|---|
| Excel | `.xlsx`, `.xlsm`, `.xls` | `ExcelInputReader` | listo |
| Delimitado | `.csv`, `.tsv` | `CsvInputReader` | listo |
| Vector | `.shp`, `.gpkg`, `.geojson`, `.json`, `.gml`, `.kml`, carpeta `.gdb` | `VectorInputReader` | listo (`.gdb` vía GDAL OpenFileGDB) |
| Columnar | `.parquet`, `.pq` | `ParquetInputReader` | listo (extra `parquet`) |
| Texto de red seccionado | `.txt` con secciones `[SECTION…]` / `FORMAT_…` (export CYMDIST) | `CymdistTextInputReader` | listo |
| Local DB | `.sqlite`, `.sqlite3`, `.db` | `SqlAlchemyInputReader` | listo |
| SQL Server backup | `.bak` o archivo sin extensión con cabecera `TAPE` / Microsoft SQL Server | `MssqlBackupReader` | listo (requiere motor SQL) |
| DB URL | `postgresql://`, `mssql://`, `oracle://`, `mysql://`, `mariadb://`, `sqlite://` (+ PostGIS vía `read_postgis`) | `SqlAlchemyInputReader` | listo (extras por motor) |

**No soportado como archivo de tablas:** `.sql` (script de sentencias). Las consultas van
en `options.queries` del YAML. Un `.bak` sí se carga: se restaura en SQL Server
(`RESTORE` implementado) y entra al mismo pipeline hacia DGS. Arranque o detección
del motor: `scripts/ensure_mssql.ps1`. Ejemplo completo: `examples/mssql_backup/project.yaml`.

`.gdb` se detecta como directorio File Geodatabase cuando existe con esa extensión.
Los `.txt` de configuración CYMDIST (sin secciones de red) no son datos: cargue la
carpeta con `RED_*.txt` + `CARGA_*.txt` (ej. `examples/cymdist_030826`).

## Exportaciones típicas → formato físico (sin ramas de marca)

El conversor **no** pregunta si el origen es IGEA, QGIS u otro. Solo detecta el
archivo/URL. Mapee su exportación al formato físico y declare columnas en YAML:

| Origen habitual | Qué suele exportar | Qué cargar en GIS2DGS |
|---|---|---|
| IGEA / CYMDIST | `RED_*.txt`, `CARGA_*.txt`, opcional equipo | Carpeta o `project.yaml` con `kind: cymdist_text` |
| QGIS | Shapefile, GeoPackage, GeoJSON, GML/KML, CSV con WKT | Archivo(s) vector / CSV; carpeta mixta OK |
| ArcGIS / FileGDB | `.gdb`, shapefile, CSV, Excel | Carpeta `.gdb` o capas exportadas |
| Tablas / oficina | Excel, CSV/TSV | Archivo o carpeta de tablas |
| BD corporativa | PostGIS, SQL Server, `.bak`, SQLite | URL en `project.yaml`, `.bak` o `.db` |

Tras cargar: `suggest-mapping` / **Proponer mapping** → `mapping.yaml` → `convert` /
**Ejecutar**.

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
