# GIS2DGS 1.0.0

> **Paquete integral:** para una instalación desde cero lea primero `START_HERE.md`.
> Para agentes de IA/desarrolladores, el contrato operativo está en `skills/gis2dgs/SKILL.md`.


**Conversor universal, configurable y auditable de datos de redes eléctricas a DGS para DIgSILENT PowerFactory.**

GIS2DGS no depende del producto que originó los datos. La entrada se define por el
**formato físico** (archivo o base de datos) y por un **mapping de esquema**. El
núcleo eléctrico, la topología, la validación, el modelo PowerFactory y la salida
DGS permanecen desacoplados del origen.

```text
XLSX / XLS / CSV / TSV / Parquet
SHP / GPKG / GeoJSON / GML / KML / FileGDB
SQLite / PostgreSQL / SQL Server / Oracle / MySQL / MariaDB / SQLAlchemy URL
                         │
                         ▼
                  InputDataset
                         │
                 schema discovery
                         │
                 mapping configurable
                         │
                         ▼
                   NetworkModel
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          topology   electrical   validation
             └───────────┼───────────┘
                         ▼
                PowerFactoryModel
                         ▼
                     DgsSchema
                         ▼
                    DgsMapper
                         ▼
                   DgsDocument
                         ▼
                    DgsWriter
                         ▼
                 DGS Excel (.xlsx)
                         ▼
              DIgSILENT PowerFactory
```

## Alcance de la release 1.0.0

- Entrada universal por adaptadores de formato, no por marca GIS.
- Múltiples fuentes simultáneas y merge por nombre lógico de tabla.
- Descubrimiento de esquema antes del mapping.
- Mapping externo YAML hacia un modelo eléctrico canónico.
- Normalización de unidades, estados, IDs y coordenadas.
- Modelo de dominio: barras, líneas, transformadores, switches, cargas,
  generación/DER, fuentes y subestaciones.
- Motor topológico con `networkx.MultiGraph`: islas, tracing, ramales, ciclos,
  elementos paralelos, límites por switches abiertos y solapamientos de feeders.
- Biblioteca eléctrica configurable para tipos de línea y transformador.
- Validación estructural, calidad de datos, eléctrica, topológica, readiness y
  referencias a librería.
- Modelo PowerFactory node-breaker con `ElmTerm`/`StaCubic` y switches de cubículo
  opcionales (`StaSwitch`).
- DGS basado en esquema estructural, **sin selector de versión de PowerFactory**.
- Inspección de DGS Excel real y parsing tipado de encabezados DGS (`a`, `r`, `i`, `p`).
- Writer DGS Excel template-driven.
- CLI instalable `gis2dgs`.
- Suite de pruebas unitarias, integración, referencias reales opcionales y
  aceptación PostGIS condicionada a credenciales externas.

## Instalación en Windows / VS Code

Requiere Python 3.11 o superior.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Para PostgreSQL/PostGIS:

```powershell
pip install -e ".[dev,postgresql]"
```

Para SQL Server (restore de `.bak` incluido):

```powershell
pip install -e ".[dev,sqlserver]"
. .\scripts\ensure_mssql.ps1
gis2dgs convert examples/mssql_backup/project.yaml --json
```

Para Oracle:

```powershell
pip install -e ".[dev,oracle]"
```

## Uso mínimo

### Interfaz gráfica (cargar archivo y ejecutar)

```powershell
python -m gis2dgs
.\RUN.ps1
```

Se abre una ventana: **Cargar archivo…** y **Ejecutar**. Un `project.yaml` genera DGS;
un Excel/CSV/SHP se inspecciona. Manual de consola: `docs/MANUAL_EJECUCION_CONSOLA.md`.

### 1. Inspeccionar una fuente

```powershell
gis2dgs inspect-input M_RED.xlsx --output output/input_schema.yaml
gis2dgs suggest-mapping M_RED.xlsx --output output/suggested_mapping.yaml
```

También puede inspeccionarse un SHP/GPKG/GeoJSON o una URL de base de datos.

### 2. Definir mapping

El archivo YAML asocia los nombres reales de tablas/columnas con el modelo
canónico. No se modifica Python por cada empresa o sistema de origen.

### 3. Convertir

```powershell
gis2dgs convert project.yaml --json
```

### 4. Inspeccionar un DGS real de referencia

```powershell
gis2dgs dgs inspect-template SALIDA_DGS.xlsx \
  --output output/dgs_schema.yaml
```

El DGS de referencia define estructura, columnas y convención DGS. No selecciona
una versión de PowerFactory.

## Ejemplo ejecutable incluido

```powershell
gis2dgs convert examples/minimal/project.yaml --json
```

Genera:

- `examples/minimal/output/minimal_dgs.xlsx`
- `validation.json`
- `validation.csv`
- `input_schema.yaml`

## Calidad y auditoría

```powershell
pytest
pytest --cov=gis2dgs --cov-report=term-missing
python scripts/audit_release.py --output docs/AUDIT_V100.json
python scripts/benchmark_topology.py --buses 50000
python scripts/benchmark_converter.py
python scripts/verify_integral_project.py
```

`ruff` y `mypy` están configurados en `pyproject.toml` para el entorno de
desarrollo. El informe de auditoría distingue entre controles ejecutados y
controles únicamente configurados.

## Seguridad

- No guardar credenciales en YAML.
- Las URLs de base de datos admiten variables de entorno, por ejemplo
  `$GIS2DGS_DB_URL`.
- El writer no sobrescribe el DGS de referencia: genera un archivo de salida.
- La reconstrucción geométrica propone conectividad antes de aplicarla.

## Documentación

- `docs/ARCHITECTURE_V100.md`
- `docs/SUPPORTED_INPUTS.md`
- `docs/USER_GUIDE.md`
- `docs/GUIA_PASO_A_PASO.md`
- `docs/MANUAL_EJECUCION_CONSOLA.md`
- `docs/WEB_RESEARCH_BASIS.md`
- `docs/ACCEPTANCE_V100.md`
- `docs/PERFORMANCE_V100.md`
- `SECURITY.md`

## Límite de certificación

La release 1.0.0 es una **release de software auditada**. La aceptación final de
un DGS generado en una instalación concreta de PowerFactory requiere ejecutar
`File > Import > DGS` en dicha instalación con el DGS y la biblioteca eléctrica
reales del usuario. Esa comprobación externa no puede sustituirse por una prueba
unitaria local.
