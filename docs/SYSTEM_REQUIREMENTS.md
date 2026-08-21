# Requisitos del sistema

## Obligatorios

- Windows 10/11 recomendado para el flujo VS Code + PowerFactory.
- Python 3.11 o superior de 64 bits.
- Acceso a `pip` para instalar `requirements.txt`.
- Espacio de trabajo con permisos de escritura para `.venv` y `output/`.

## Opcionales según la fuente

- SQL Server: paquete Python `pyodbc` (incluido en `requirements.txt`) y un Microsoft ODBC Driver
  17 u 18 instalado en Windows. El restore de `.bak` está implementado (`MssqlBackupReader`).
  El motor se comprueba o arranca con `.\scripts\ensure_mssql.ps1` (localhost / LocalDB /
  Express, o Docker `docker-compose.mssql.yml`). También puede fijar `GIS2DGS_MSSQL_URL`
  hacia `master`. La contraseña SA de Docker va en `GIS2DGS_MSSQL_SA_PASSWORD`, nunca en git.
  Con ODBC 18 el contenedor Docker se conecta con `UID=sa`, `Authentication=SqlPassword`,
  `Encrypt=yes` y `TrustServerCertificate=yes` (no usar `Trusted_Connection` contra Linux).
- PostgreSQL/PostGIS: `psycopg[binary]` incluido en `requirements.txt`; el servidor/PostGIS es externo.
- Oracle: `oracledb` incluido. Su modo thin no exige Oracle Client para los casos compatibles.
- MySQL/MariaDB: `PyMySQL` incluido.
- Parquet: `pyarrow` incluido.
- `.xls` legado: `xlrd` incluido.
- SHP/GPKG/GeoJSON/FileGDB: la lectura depende de los drivers GDAL/OGR disponibles mediante
  GeoPandas/pyogrio en el entorno instalado.

## PowerFactory

PowerFactory no es una dependencia pip del conversor. GIS2DGS genera el DGS; la aceptación industrial
se realiza importando ese archivo en una instalación legítima de DIgSILENT PowerFactory.
