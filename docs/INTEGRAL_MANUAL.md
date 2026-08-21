# Manual integral de implementación, ejecución y mantenimiento — GIS2DGS 1.0.0

## 1. Objetivo

GIS2DGS es un conversor universal de datos de redes eléctricas a DGS. Acepta fuentes tabulares,
geoespaciales y bases de datos, descubre sus tablas/campos, aplica un mapping configurable y crea un
modelo eléctrico canónico antes de generar la representación PowerFactory/DGS.

No depende de ArcGIS, IGEA, QGIS ni otra marca. Dos fuentes con nombres de columnas diferentes pueden
producir el mismo `NetworkModel` mediante mappings YAML distintos.

## 2. Sistema único

Todo lo necesario para desarrollar el software está bajo esta raíz:

```text
GIS2DGS/
├── START_HERE.md
├── AGENTS.md
├── requirements.txt
├── requirements-lock.txt
├── pyproject.toml
├── config/
├── data/
├── docs/
├── examples/
├── scripts/
├── skills/gis2dgs/SKILL.md
├── src/gis2dgs/
└── tests/
```

No se distribuye `.venv`: el entorno virtual se crea en cada estación de trabajo para evitar
incompatibilidades de rutas, sistema operativo y binarios.

## 3. Instalación del entorno

### Windows / VS Code

1. Instalar Python 3.11 o superior.
2. Descomprimir el proyecto sin separar carpetas.
3. Abrir la carpeta raíz en VS Code.
4. Ejecutar:

```powershell
.\INSTALL_AND_VERIFY.ps1
```

El instalador crea `.venv`, instala `requirements.txt`, ejecuta pruebas, verifica la estructura y corre
el ejemplo mínimo.

### Manual

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

## 4. Dependencias

El archivo raíz `requirements.txt` es el punto único de instalación Python. Incluye el paquete editable,
herramientas de desarrollo y extras para PostgreSQL, SQL Server, Oracle, Parquet, Excel legado y
MySQL/MariaDB. `requirements-lock.txt` conserva las versiones ejercitadas durante la auditoría; no
reemplaza a `requirements.txt` como contrato de instalación universal.

Los prerrequisitos que no pueden ser instalados por pip se documentan en `SYSTEM_REQUIREMENTS.md`.

## 5. Entrada

El subsistema `input/` selecciona el reader por formato o URL. Puede trabajar con múltiples fuentes en
un mismo proyecto. El resultado es `InputDataset`; aún no es una red eléctrica.

Luego `schema discovery` identifica tablas/campos y el mapping YAML traduce roles físicos a entidades
canónicas: `Bus`, `Line`, `Transformer`, `Switch`, `Load`, `Generator`, `Source`, etc.

## 6. Dominio eléctrico

`domain/` es independiente de formatos, bases de datos y PowerFactory. Esta separación permite cambiar
la fuente sin reescribir la lógica eléctrica.

`electrical/` conserva los tipos de línea y transformador y sus parámetros. Cuando el origen sólo
entrega un código de tipo, la biblioteca completa los parámetros necesarios para estudios.

## 7. Topología

`topology/` construye `networkx.MultiGraph` para conservar elementos paralelos. Implementa componentes
conectadas, islas, tracing desde fuentes, feeders, ramales, ciclos, switches abiertos y solapamientos.

La lógica geoespacial de reconexión por coordenadas se mantiene en `gis/` porque usa CRS y geometrías;
no se mezcla con el dominio.

## 8. Validación

Antes de generar DGS se comprueban integridad de referencias, datos faltantes/no finitos, coherencia de
tensión, conectividad, energización, tipos eléctricos y readiness según el estudio.

Un modelo que no supera las reglas críticas no debe pasar silenciosamente a producción.

## 9. PowerFactory y DGS

`powerfactory/` genera un modelo semántico node-breaker. `dgs/` lo transforma a un documento DGS según
un esquema estructural. El DGS no se condiciona a una marca de origen ni a una selección manual de
versión de PowerFactory.

La revisión declarada por un archivo DGS (por ejemplo `General → Version`) se preserva como metadato del
formato cuando existe.

## 10. Configuración de un proyecto real

1. Reunir archivos/DB exportados.
2. `inspect-input` para descubrir tablas/campos.
3. `suggest-mapping` (opcional) para proponer el YAML de columnas; revisar antes de convertir.
4. Definir `project.yaml` y mapping.
5. Completar biblioteca eléctrica cuando el origen no incluya parámetros.
6. Inspeccionar un DGS real con `dgs inspect-template` para confirmar el esquema de salida.
7. Ejecutar `convert`.
8. Revisar `validation.json/csv`.
9. Importar DGS en PowerFactory y ejecutar el estudio.

## 11. Ejemplo incluido

```powershell
python -m gis2dgs convert examples/minimal/project.yaml --json
. .\scripts\ensure_mssql.ps1
python -m gis2dgs convert examples/mssql_backup/project.yaml --json
```

El ejemplo CSV cubre lectura → mapping → modelo → validación → PowerFactoryModel → DGS.
El ejemplo `mssql_backup` restaura un `.bak` y recorre el mismo pipeline.

Para cargar un archivo desde ventana:

```powershell
python -m gis2dgs
.\RUN.ps1
```

El detalle de cada comando de PowerShell está en `docs/MANUAL_EJECUCION_CONSOLA.md`.
La secuencia **archivo real → verificar (`inspect-input`) → ejecutar (`convert`)** está en `docs/GUIA_PASO_A_PASO.md`.

## 12. Desarrollo mantenible

- Un nuevo formato se implementa como reader y se registra.
- Un nuevo esquema de empresa se resuelve con YAML.
- Una nueva regla eléctrica se agrega a `validation/` con pruebas.
- Un nuevo objeto eléctrico atraviesa explícitamente dominio, mapping, validación, PowerFactory y DGS.
- No duplicar pipelines.
- No crear scripts sueltos fuera de `scripts/`.
- No generar archivos de salida en la raíz.

## 13. Pruebas

```powershell
python -m pytest -q
python -m pytest --cov=gis2dgs --cov-report=term-missing
python scripts/verify_integral_project.py
python scripts/benchmark_converter.py
```

Pruebas externas que requieren infraestructura real (PostGIS, SQL Server) se marcan y
se ejecutan al proporcionar sus variables de entorno. El restore de `.bak` está
implementado; `scripts/ensure_mssql.ps1` detecta o arranca el motor.

## 14. Seguridad

Nunca incluir secretos en YAML, código, ejemplos ni ZIP. Use variables de entorno. Las referencias
reales incluidas son datos de esquema/prueba suministrados para el proyecto y deben conservarse en
`data/reference/real/`.

## 15. Aceptación final

La calidad local demuestra que el software compila, importa, pasa pruebas y genera DGS reproducible.
El veredicto de diseño es **no** usar deep learning ni transformers locales en el runtime;
el detalle está en `docs/CERTIFICATION_BENCHMARK.md`.
La aceptación de ingeniería requiere además importar el DGS generado en PowerFactory y comprobar que
el estudio requerido (flujo, cortocircuito, pérdidas, etc.) se ejecuta con los datos reales.
