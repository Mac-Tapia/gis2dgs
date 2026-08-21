$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== GIS2DGS 1.0.0: instalación integral ==" -ForegroundColor Cyan

$pythonCmd = $null
try {
    & py -3.11 --version | Out-Null
    $pythonCmd = @("py", "-3.11")
} catch {
    try {
        & python --version | Out-Null
        $pythonCmd = @("python")
    } catch {
        throw "Python 3.11+ no está disponible. Instálelo y vuelva a ejecutar este script."
    }
}

if (-not (Test-Path ".venv")) {
    if ($pythonCmd.Count -eq 2) { & $pythonCmd[0] $pythonCmd[1] -m venv .venv }
    else { & $pythonCmd[0] -m venv .venv }
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "No se pudo crear .venv correctamente." }

& $py -m pip install --upgrade pip setuptools wheel
& $py -m pip install -r requirements.txt

Write-Host "== Verificación estructural ==" -ForegroundColor Cyan
& $py scripts\verify_integral_project.py

Write-Host "== Suite de pruebas ==" -ForegroundColor Cyan
& $py -m pytest -q

Write-Host "== Ejemplo end-to-end ==" -ForegroundColor Cyan
& $py -m gis2dgs convert examples\minimal\project.yaml --json

Write-Host "== Benchmark de certificación ==" -ForegroundColor Cyan
& $py scripts\benchmark_converter.py

Write-Host "== Instalación completada ==" -ForegroundColor Green
& $py -m gis2dgs --version
Write-Host "Entorno: $PSScriptRoot\.venv"
Write-Host "SQL Server para .bak: .\scripts\ensure_mssql.ps1 (opcional; detecta local o arranca Docker)."
