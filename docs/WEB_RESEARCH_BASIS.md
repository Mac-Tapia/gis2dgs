# Base técnica y revisión web — GIS2DGS 1.0.0

Consulta realizada para contrastar la arquitectura con fuentes primarias y un
trabajo académico de referencia.

## DIgSILENT

- GIS Integration White Paper: https://www.digsilent.de/en/paper-reader-pf-en/gis-integration.html
  - distingue integración basada en archivos y en base de datos;
  - permite enriquecer GIS con otras fuentes;
  - exige crear un modelo eléctrico topológicamente conectado;
  - contempla validación/corrección por reglas y network tracing;
  - lista nodos, estaciones, cargas/generación, transformadores, líneas y switches
    como datos relevantes;
  - define DGS como salida del conversor e interfaz abierta legible por máquina.
- Data Converters: https://www.digsilent.de/en/data-converter.html
  - DGS es una interfaz flexible de intercambio y admite varios carriers.
- DGS import example: https://www.digsilent.de/en/faq-reader-powerfactory/how-can-i-import-dynamic-models-via-dgs.html
  - muestra importación DGS mediante Microsoft Excel y remite a la documentación
    DGS incluida en PowerFactory.

## Bibliotecas utilizadas

- GeoPandas I/O: https://geopandas.org/en/stable/docs/user_guide/io.html
  - `read_file()` permite cubrir una amplia familia de formatos vectoriales.
- SQLAlchemy engines/dialects: https://docs.sqlalchemy.org/en/latest/core/engines.html
  - desacopla el lector de DB mediante dialecto + driver.
- NetworkX MultiGraph: https://networkx.org/documentation/stable/reference/classes/multigraph.html
  - preserva múltiples aristas entre las mismas barras, necesarias para circuitos
    paralelos.
- Python Packaging: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
  - la release utiliza `pyproject.toml` y `src/` layout.
- pytest good practices: https://docs.pytest.org/en/stable/explanation/goodpractices.html
  - pruebas separadas y reproducibles con `src` layout.

## Microsoft SQL Server / ODBC (restore de `.bak`)

- ODBC Driver 18 connection keywords:
  https://learn.microsoft.com/en-us/sql/connect/odbc/dsn-connection-string-attribute
  - `Authentication=SqlPassword` fuerza autenticación SQL (`SQL_AU_PASSWORD`);
    en un host unido a dominio, ODBC 18 ignora UID/PWD y usa Windows/SSPI,
    lo que contra SQL Server Linux (Docker) produce el error 18452
    (*untrusted domain / Integrated authentication*).
  - `Encrypt` por defecto es obligatorio en el Driver 18; para el certificado
    autofirmado del contenedor se usa `TrustServerCertificate=yes`.
- SQL Server en contenedor:
  https://learn.microsoft.com/en-us/sql/linux/sql-server-linux-docker-container-deployment
  - autenticación `sa` (`MSSQL_SA_PASSWORD`); no hay autenticación integrada
    de Windows dentro de Linux.
- BACKUP/RESTORE sobre ODBC:
  pyodbc issue 471 (https://github.com/mkleehammer/pyodbc/issues/471) y
  SQL Server error 3021. El servidor envía paquetes TDS de progreso; si el
  cliente cierra el cursor sin `SQLMoreResults`/`cursor.nextset()`, el BACKUP
  se aborta en silencio y el `.bak` no queda en disco. SQLAlchemy no expone
  bien ese modo: hay que usar la conexión DBAPI (`engine.raw_connection()` /
  `connection.connection.dbapi_connection`) en autocommit.

## CIM / PowerFactory (modelo eléctrico)

- IEC 61970-301 CIM: modelo semántico independiente de implementación para
  EMS/SCADA; tesis Politecnico di Milano (Umer, 2019) sobre CIM relacional y
  PowerFactory como procesador de red.
- DIgSILENT CIM/CGMES: PowerFactory es node-breaker; bus-branch es un caso
  reducido. GIS2DGS no emite CIM: emite DGS, alineado con el white paper GIS.

## Decisiones derivadas

- adaptadores de input por formato/DB en vez de por marca GIS;
- modelo intermedio canónico;
- multigrafo para topología;
- validación previa a DGS;
- biblioteca eléctrica separada;
- modelo PowerFactory node-breaker;
- DGS basado en esquema real y no en versión de producto.
