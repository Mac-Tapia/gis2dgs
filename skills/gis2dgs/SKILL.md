---
name: gis2dgs
version: 1.1.0
description: GIS→DGS PowerFactory; mapping YAML, validate, verify gate
summary: Convertidor universal y configurable de datos de redes eléctricas a DGS para DIgSILENT PowerFactory.
entrypoint: python -m gis2dgs
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [gis, powerfactory, dgs, electrical, converter]
    category: devops
    requires_toolsets: [terminal]
---

# Skill operativo — GIS2DGS

## When to Use

- Cambios de código o config en el conversor GIS2DGS.
- Inspección, mapping sugerido o conversión a DGS de un paquete de red.
- Diagnóstico de fallos de pipeline / verify gate.
- Tareas autónomas (Hermes): convertir paquete → validar → reportar bajo `output/`.

## 1. Misión

Mantener y ejecutar GIS2DGS como un único sistema integrado que transforma datos estructurados de
redes eléctricas, provenientes de archivos o bases de datos, en un DGS validado para importación en
DIgSILENT PowerFactory.

El origen se identifica por **formato físico y esquema**, nunca por la marca de la aplicación que lo
exportó.

## 2. Flujo canónico

```text
Archivos / DB
    ↓
Input adapters + schema discovery
    ↓
InputDataset
    ↓
Configurable mapping
    ↓
NetworkModel
    ↓
TopologyEngine + ElectricalLibrary + ValidationEngine
    ↓
PowerFactoryModel (node-breaker)
    ↓
DgsSchema
    ↓
DgsMapper → DgsDocument → DgsWriter
    ↓
DGS Excel
    ↓
Importación en DIgSILENT PowerFactory
```

Nunca salte `NetworkModel` ni la validación para escribir DGS directamente desde una tabla.

## 3. Mapa del código

- `src/gis2dgs/assist/`: propuesta de mapping YAML (NSGA-II + TOPSIS, LLM opcional),
  modalidades de decisión (`decision.py`) y estrategias multimodales de conversión
  (`strategies.py`). No escribe DGS.
- `src/gis2dgs/input/`: detección, readers universales, DB, merge, descubrimiento de esquema.
- `src/gis2dgs/gis/`: CRS, geometría y reconstrucción espacial especializada.
- `src/gis2dgs/domain/`: modelo eléctrico canónico independiente de infraestructura.
- `src/gis2dgs/electrical/`: tipos y biblioteca de parámetros eléctricos.
- `src/gis2dgs/topology/`: grafo, tracing, islas, ciclos, ramales y límites.
- `src/gis2dgs/validation/`: reglas y reportes de calidad/readiness.
- `src/gis2dgs/powerfactory/`: modelo semántico PowerFactory node-breaker.
- `src/gis2dgs/dgs/`: esquema DGS, parser de columnas, mapper y writer.
- `src/gis2dgs/config/`: modelos/carga de configuración.
- `src/gis2dgs/cli/`: interfaz de línea de comandos.
- `src/gis2dgs/pipeline.py`: orquestación integral.

## 4. Instalación

Desde la raíz:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

`requirements.txt` instala el proyecto editable y los extras de desarrollo y conectividad. Los
controladores de sistema que no son paquetes Python (por ejemplo Microsoft ODBC Driver para SQL
Server) se describen en `docs/SYSTEM_REQUIREMENTS.md`.

## 5. Comandos de uso

```powershell
python -m gis2dgs --version
python -m gis2dgs
python -m gis2dgs gui
python -m gis2dgs inspect-input <fuente> --output output/input_schema.yaml
python -m gis2dgs load <fuente> --json
python -m gis2dgs load <fuente> --strategy network_core --modality nsga_topsis --json
python -m gis2dgs suggest-mapping <fuente> --output output/suggested_mapping.yaml
python -m gis2dgs suggest-mapping <fuente> --modality pareto --pareto-index 0 --output output/suggested_mapping.yaml
python -m gis2dgs dgs inspect-template <dgs_real.xlsx> --output output/dgs_schema.yaml
python -m gis2dgs convert <project.yaml> --json
```

Flujo de decisión → convert:

1. `suggest-mapping` (o GUI **Proponer mapping**) → frente Pareto + pesos TOPSIS.
2. Elegir modalidad / índice Pareto / pesos (GUI **Usar selección** o flags CLI).
3. `load` / **Ejecutar** aplica estrategia multimodal (`auto|full_mapped|network_core|compact_lines`)
   y escribe `output/loaded/<run>/output/decision_report.yaml` antes del DGS.

Sin argumentos se abre la interfaz principal; el usuario carga archivo/carpeta y ejecuta.
El detalle de comandos de consola está en `docs/MANUAL_EJECUCION_CONSOLA.md`. La secuencia de
**archivo real → verificar (`inspect-input`) → ejecutar (`convert`)** está en
`docs/GUIA_PASO_A_PASO.md`.

Ejemplo reproducible:

```powershell
python -m gis2dgs convert examples/minimal/project.yaml --json
. .\scripts\ensure_mssql.ps1
$env:GIS2DGS_MSSQL_BACKUP = "C:\ruta\red.bak"
python -m gis2dgs convert examples/mssql_backup/project.yaml --json
```

## 6. Protocolo de modificación

1. Identifique la capa responsable (`input/`, `assist/`, `gis/`, `domain/`, `dgs/`, …).
2. Cambie sólo esa capa y contratos estrictamente necesarios.
3. Si agrega un formato, implemente un reader/adaptador y regístrelo; no toque el dominio.
4. Si cambia el mapping de una empresa, modifique YAML (`config/layer_profiles.yaml`, `mapping.yaml`); no hardcodee columnas ni marcas GIS.
5. Si agrega un objeto eléctrico, extienda dominio → mapping → topología/validación → PowerFactory → DGS.
6. Añada pruebas unitarias y, cuando corresponda, una prueba de integración.
7. Ejecute las verificaciones del §7.
8. Actualice documentación si cambia el comportamiento público.

### Backlog por capa (robustez universal)

| Capa | Responsabilidad | Extensión sin código |
|------|-----------------|----------------------|
| `input/` | Lectura física, detección de formato | Nuevo reader + registro |
| `assist/layer_classifier.py` | Rol eléctrico por firma de esquema | `config/layer_profiles.yaml` |
| `assist/catalog.py` | Alias léxicos de campos/tablas | Entradas en catálogo |
| `config/mapping.yaml` | Mapeo confirmado por proyecto | Edición YAML tras `suggest-mapping` |
| `gis/mapping/` | Tabla → `NetworkModel` | Mapping + defaults/units |
| `validation/` | Reglas de readiness | `validation.yaml` profile |

Salida de inspección: `output/.../layer_classification.yaml` documenta qué tabla se interpretó como nodo/tramo/alimentador/carga antes del mapping NSGA-II.

Referencias externas alineadas: [Power Grid Model tabular mapping](https://power-grid-model-io.readthedocs.io/en/stable/converters/tabular_converter.html), [LinkML Map](https://github.com/linkml/linkml-map/blob/main/docs/index.md) (YAML declarativo, independiente del runtime).

## 7. Verificación obligatoria

Gate unificado del agent harness (recomendado tras cambios de código):

```powershell
python scripts/run_verify_gate.py
python scripts/run_verify_gate.py --quick
```

Equivalente manual:

```powershell
python -m pytest -q
python -m pytest --cov=gis2dgs --cov-report=term-missing
python -m compileall -q src tests scripts
python scripts/verify_integral_project.py
python scripts/benchmark_converter.py
python -m gis2dgs convert examples/minimal/project.yaml --json
```

El harness de Cursor (`.cursor/hooks.json`) bloquea shell destructivo, marca
verify pendiente tras editar código y puede reinyectar un follow-up en `stop`
si el gate sigue abierto. Modo estricto: `$env:GIS2DGS_HARNESS_STRICT=1`.

Si `ruff` y `mypy` están instalados por `requirements.txt`:

```powershell
ruff check .
mypy src
```

## 8. Invariantes arquitectónicas

- No dependencia de marca GIS.
- No credenciales en repositorio.
- No mutar archivos de referencia.
- IDs/foreign keys deterministas.
- Conservar circuitos paralelos con `MultiGraph`.
- Switch abierto no conduce en grafo eléctrico.
- La reconstrucción espacial propone antes de aplicar.
- DGS es schema-driven; no es `if PowerFactoryVersion`.
- Toda salida debe poder trazarse a su entrada y configuración.
- `convert` es offline: no depende de GPU, torch, transformers ni un LLM.
- El asistente de mapping (NSGA-II + TOPSIS; LLM HTTP opcional y fail-open) no escribe DGS.

## 9. Referencias internas reales

`data/reference/real/SALIDA_DGS.xlsx` es una referencia real de estructura DGS proporcionada por el
usuario. `data/reference/real/M_ALIMENTAD.xlsx` es una muestra real de una tabla de entrada. Se usan
para comprender/validar esquemas, **no** para hardcodear el conversor a esos archivos.

## 10. Criterio de terminado

Una tarea sólo está terminada cuando código, configuración, pruebas y documentación están dentro del
mismo proyecto y la suite no introduce regresiones. La aceptación final de un DGS en PowerFactory
requiere además importarlo en una instalación real y ejecutar el estudio eléctrico correspondiente.

## 11. Playbooks Hermes (autónomos)

Usar el venv del repo (`.venv`). CWD = raíz del git checkout. Salidas siempre bajo `output/`.

### Convertir un paquete tabular / GIS

```powershell
.\.venv\Scripts\python.exe -m gis2dgs load "<ruta_paquete>" --json
# O GUI / load-and-run según el caso; no hardcodear rutas personales en commits.
```

Tras convertir, comprobar `output/loaded/<proyecto>/output/` (`red_dgs.xlsx`, `validation.json`,
`connectivity.yaml`). Si el mapping auto es pobre, regenerar mapping (no reutilizar un
`mapping.yaml` obsoleto a ciegas).

### Cerrar cambio de código

```powershell
.\.venv\Scripts\python.exe scripts/run_verify_gate.py
```

### Pitfalls

- No escribir DGS saltando `NetworkModel` / validación.
- No descartar archivos permitidos del paquete cargado; el filtro por nombre es sólo heurística informativa.
- Extender `config/layer_profiles.yaml` antes de añadir reglas ad hoc en `assist/service.py`.
- Pedir confirmación antes de `git commit` / `git push`.

### Verification

- `python scripts/run_verify_gate.py` → PASS.
- DGS generado existe bajo `output/` y el informe de validación es legible.
