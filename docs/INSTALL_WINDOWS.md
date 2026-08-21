# Instalación Windows / VS Code — GIS2DGS 1.0.0

## Opción A: desde el proyecto fuente

Abra PowerShell en la carpeta del proyecto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

Luego:

```powershell
.\.venv\Scripts\Activate.ps1
gis2dgs --version
pytest -q
```

## Opción B: desde el wheel

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install gis2dgs-1.0.0-py3-none-any.whl

gis2dgs --version
```

Instale extras del driver requerido cuando corresponda.

## VS Code

1. Abrir la carpeta del proyecto.
2. `Ctrl+Shift+P` → `Python: Select Interpreter`.
3. Seleccionar `.venv\Scripts\python.exe`.
4. Puede ejecutar las tareas incluidas en `.vscode/tasks.json`.
5. Para la ventana de carga de archivo: `.\RUN.ps1` o `python -m gis2dgs`.
