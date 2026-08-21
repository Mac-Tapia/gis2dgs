# Manual de ejecución por consola — GIS2DGS 1.0.0

Este documento describe cómo instalar, inspeccionar y convertir desde PowerShell.
Para la secuencia **archivo real → verificar → ejecutar conversión**, use
`docs/GUIA_PASO_A_PASO.md`.
La interfaz gráfica se documenta al final; no sustituye estos comandos.

## 1. Requisitos

- Windows con Python 3.11 o superior (`py -3.11 --version`).
- Proyecto descomprimido sin separar carpetas.
- PowerShell abierto en la raíz del repositorio (`D:\converter\gisdgsv1` o la ruta local).

## 2. Crear el entorno (solo la primera vez)

```powershell
.\INSTALL_AND_VERIFY.ps1
```

Equivalente manual:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

En cada sesión posterior active el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
python -m gis2dgs --version
```

Debe imprimir `1.0.0`.

## 3. Interfaz gráfica (cargar archivo y ejecutar)

Sin argumentos, o con el comando `gui`, se abre una ventana. El usuario carga el
archivo y pulsa **Ejecutar**.

```powershell
python -m gis2dgs
python -m gis2dgs gui
.\RUN.ps1
```

Qué hace **Ejecutar** según el archivo cargado:

| Archivo | Acción |
| --- | --- |
| `project.yaml` | Conversión completa a DGS |
| `.bak` / backup SQL Server | Flujo completo: inspección + mapping + NetworkModel + validación + DGS (requiere SQL Server disponible) |
| CSV / Excel / SHP / GPKG / GeoJSON / Parquet | Flujo completo: inspección + mapping + NetworkModel + validación + DGS |
| Excel DGS de referencia (`General` + `ElmNet`) | Inspección del esquema DGS |

Cuando la entrada no es `project.yaml`, `load`/`RUN` genera un `project.yaml`
temporal en `output\loaded\<nombre>\` y ejecuta el pipeline completo con
validación estricta. Si faltan conexiones o referencias críticas, falla con
error claro; no inventa objetos ni enlaces.

## 4. Inspeccionar una fuente

Descubre tablas, columnas y tipos. No genera DGS.

```powershell
python -m gis2dgs inspect-input datos.xlsx --output output\input_schema.yaml
python -m gis2dgs inspect-input red.bak --output output\input_schema.yaml
python -m gis2dgs inspect-input examples\minimal\input\buses.csv --output output\input_schema.yaml
python -m gis2dgs inspect-input data\reference\real\M_ALIMENTAD.xlsx --output output\input_schema.yaml
```

Para una base de datos use una URL en variable de entorno, nunca credenciales en YAML:

```powershell
$env:GIS2DGS_DB_URL = "postgresql+psycopg://usuario:clave@servidor:5432/base"
python -m gis2dgs inspect-input $env:GIS2DGS_DB_URL --kind database --output output\input_schema.yaml
```

Para archivos grandes use `--sample-rows` (0 = todas las filas). El valor por defecto es 100000
o `GIS2DGS_SAMPLE_ROWS`.

## 4b. Proponer mapping (no genera DGS)

Alinea tablas/columnas al modelo canónico con un algoritmo genético multiobjetivo (NSGA-II)
y una selección multicriterio (TOPSIS). El conjunto Pareto es multimodal. Opcionalmente un LLM
compatible con OpenAI puede refinar el YAML si define `GIS2DGS_LLM_URL` y `GIS2DGS_LLM_API_KEY`.

```powershell
python -m gis2dgs suggest-mapping examples\minimal\input --output output\suggested_mapping.yaml
python -m gis2dgs suggest-mapping datos.xlsx --output output\suggested_mapping.yaml --llm
```

La interfaz tiene el botón **Proponer mapping**. Después hay que revisar el YAML y ejecutar
`convert` con un `project.yaml`.

## 4c. Cargar y convertir (flujo completo en un comando)

Detecta el tipo, inspecciona, propone mapping, genera un `project.yaml` bajo
`output\loaded\<nombre>\` y recorre NetworkModel → validación → DGS.

```powershell
python -m gis2dgs load "C:\ruta\al\archivo" --json
python -m gis2dgs load examples\minimal\input --json
python -m gis2dgs load examples\minimal\project.yaml --json
python -m gis2dgs load "E:\ELOR25_V1\ELOR25_V1" --json
```

Un `project.yaml` se convierte tal cual. Cualquier otro archivo soportado se andamia
con las plantillas eléctricas/DGS universales. El DGS queda en
`output\loaded\<nombre>\output\red_dgs.xlsx` (salvo que ya fuera un proyecto).
Si un `project.yaml` declara fuentes inexistentes/no soportadas, el comando
falla antes de convertir y reporta qué fuente debe corregirse.

## 5. Inspeccionar una plantilla DGS real

```powershell
python -m gis2dgs dgs inspect-template data\reference\real\SALIDA_DGS.xlsx --output output\dgs_schema.yaml
```

La revisión leída (`General/Version`) es del formato DGS, no de una versión de PowerFactory.

## 6. Convertir (flujo completo)

El comando de conversión recibe un **proyecto YAML**, no una tabla suelta.

```powershell
python -m gis2dgs convert examples\minimal\project.yaml --json
```

Salidas del ejemplo:

- `examples\minimal\output\minimal_dgs.xlsx`
- `examples\minimal\output\validation.json`
- `examples\minimal\output\validation.csv`
- `examples\minimal\output\input_schema.yaml`

Para un caso real:

1. Copie `examples\minimal\` como plantilla de proyecto.
2. Ajuste `inputs` en `project.yaml` a sus archivos.
3. Ajuste `config\mapping.yaml` a los nombres reales de tablas y columnas.
4. Complete `config\electrical_library.yaml` con tipos de línea/transformador.
5. Ejecute:

```powershell
python -m gis2dgs convert ruta\a\project.yaml --json
```

Si falla la validación, revise `validation.json` antes de reintentar. No ignore
errores `STRUCTURE`, `ELECTRICAL` o `READINESS`.

## 7. Ayuda de comandos

```powershell
python -m gis2dgs --help
python -m gis2dgs load --help
python -m gis2dgs convert --help
python -m gis2dgs inspect-input --help
python -m gis2dgs suggest-mapping --help
python -m gis2dgs dgs inspect-template --help
python -m gis2dgs gui --help
```

## 8. Verificación de que el software funciona

```powershell
python -m pytest -q
python scripts\verify_integral_project.py
python scripts\benchmark_converter.py
python -m gis2dgs convert examples\minimal\project.yaml --json
```

Resultado esperado de pytest en este entorno: pruebas en verde y, si no hay
PostGIS ni SQL Server configurados, esas pruebas de infraestructura `skipped`.

## 9. Importación en PowerFactory

La consola no simula DIgSILENT. Con el Excel DGS generado:

1. Abra PowerFactory.
2. `File > Import > DGS`.
3. Revise el log de importación.
4. Ejecute al menos un flujo de carga.

## 10. Dónde no escribir

- No sobrescriba `data\reference\real\`.
- No ponga contraseñas en YAML.
- Las salidas van a `output\` o a la carpeta `output` del proyecto de conversión.
