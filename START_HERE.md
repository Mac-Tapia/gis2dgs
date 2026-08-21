# GIS2DGS — EMPEZAR AQUÍ

Este directorio es **el proyecto completo y único** de GIS2DGS 1.0.0. No hay piezas que deban
buscarse fuera del ZIP para entender, desarrollar, probar o ejecutar el conversor, salvo Python y,
según el motor de base de datos usado, el controlador del sistema correspondiente.

## Propósito

GIS2DGS convierte **datos estructurados de redes eléctricas** provenientes de archivos o bases de
datos compatibles a un modelo DGS importable en DIgSILENT PowerFactory. El motor es universal
respecto de la aplicación que originó los datos: se adapta por **formato**, **esquema** y **mapping**,
no por marca GIS.

## Orden de lectura obligatorio

1. `START_HERE.md` — orientación rápida.
2. `skills/gis2dgs/SKILL.md` — contrato operativo para agentes y desarrolladores.
3. `docs/INTEGRAL_MANUAL.md` — instalación, arquitectura, ejecución y mantenimiento.
4. `README.md` — guía funcional y comandos.
5. `docs/ARCHITECTURE_V100.md` — arquitectura técnica detallada.
6. `docs/GUIA_PASO_A_PASO.md` — archivo real: cargar, verificar y ejecutar.
7. `docs/MANUAL_EJECUCION_CONSOLA.md` — referencia de comandos PowerShell.
8. `docs/TEST_REPORT.md` y `docs/AUDIT_V100.md` — evidencia de verificación.
9. `docs/CERTIFICATION_BENCHMARK.md` — veredicto DL/transformers y benchmark reproducible.

## Instalación recomendada en Windows / VS Code

Abra PowerShell en esta carpeta y ejecute:

```powershell
.\INSTALL_AND_VERIFY.ps1
```

El script crea `.venv`, instala `requirements.txt`, ejecuta las verificaciones y corre el ejemplo
mínimo. La carpeta `.venv` **no se distribuye** dentro del ZIP porque un entorno virtual no es
portable entre equipos; se crea reproduciblemente en el equipo de trabajo.

Instalación manual equivalente:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pytest -q
python scripts/verify_integral_project.py
python scripts/benchmark_converter.py
python -m gis2dgs --version
python -m gis2dgs convert examples/minimal/project.yaml --json
```

## Puntos de entrada

- **Windows (recomendado):** `.\RUN.ps1` — abre la interfaz, carga cualquier archivo/carpeta,
  el detector elige la acción; pulse **Ejecutar** (sin rutas ni casos especiales hardcodeados).
- CLI: `python -m gis2dgs` o `gis2dgs` después de instalar.
- Interfaz gráfica: `python -m gis2dgs` (sin argumentos), `python -m gis2dgs gui` o `.\RUN.ps1`.
- Manual de consola: `docs/MANUAL_EJECUCION_CONSOLA.md`.
- Guía paso a paso (archivo real → verificar → DGS): `docs/GUIA_PASO_A_PASO.md`.
- Código: `src/gis2dgs/`.
- Configuración: `config/` y archivos `project.yaml`.
- Pruebas: `tests/`.
- Ejemplo ejecutable: `examples/minimal/`.
- Ejemplo backup SQL Server: `examples/mssql_backup/` (motor: `.\scripts\ensure_mssql.ps1`).
- Referencias reales: `data/reference/real/`.
- Salidas: `output/` o el directorio `output` del proyecto de conversión.

## Regla de oro

No convertir una tabla aislada directamente a DGS. El flujo correcto es:

`InputDataset → mapping → NetworkModel → topología/validación → PowerFactoryModel → DgsSchema → DGS`.
