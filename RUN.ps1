# GIS2DGS — punto de entrada universal (Windows)
# Requisito: .venv (ejecute .\INSTALL_AND_VERIFY.ps1 si no existe).
#
# Uso:
#   .\RUN.ps1
#   → Cargar archivo… / Cargar carpeta… (cualquier ruta, cualquier formato soportado)
#   → El detector clasifica automáticamente (sin casos especiales por usuario)
#   → Ejecutar recorre el flujo completo:
#       project.yaml     → conversión a DGS validado
#       Excel/CSV/SHP/…  → inspect + mapping + DGS (output/loaded/<nombre>/)
#       .bak SQL Server  → restaura, mapping y DGS (SQL Server local/Docker)
#       plantilla DGS    → inspección del esquema Excel DGS
#   → Proponer mapping (opcional): sugiere YAML de columnas; no escribe DGS
#
# Para generar DGS desde datos nuevos: inspeccione, proponga mapping, configure
# project.yaml y vuelva a cargarlo antes de Ejecutar.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "No existe .venv. Ejecute primero .\INSTALL_AND_VERIFY.ps1"
}

Write-Host "Verificando SQL Server (necesario para archivos .bak)..." -ForegroundColor DarkGray
$ensureExit = 0
try {
    & "$PSScriptRoot\scripts\ensure_mssql.ps1"
    $ensureExit = $LASTEXITCODE
} catch {
    $ensureExit = 1
}
if ($ensureExit -ne 0) {
    Write-Host "SQL Server no disponible (se requiere solo para .bak). Otros formatos funcionan sin él." -ForegroundColor DarkGray
    if ($ensureExit -eq 5) {
        Write-Host "Hint .bak: docker pull mcr.microsoft.com/mssql/server:2022-CU16-ubuntu-22.04" -ForegroundColor DarkYellow
        Write-Host "  o defina GIS2DGS_MSSQL_URL hacia un SQL Server local (docs\SYSTEM_REQUIREMENTS.md)." -ForegroundColor DarkYellow
    }
}

# Cargar variables de sesión que ensure_mssql.ps1 pudo haber creado/actualizado
$sessionEnv = Join-Path $PSScriptRoot "output\mssql\session.env.ps1"
if (Test-Path $sessionEnv) {
    . $sessionEnv
}

Write-Host "Abriendo GIS2DGS. Cargue un archivo o carpeta y pulse Ejecutar." -ForegroundColor Cyan
Write-Host "Backup .bak: al pulsar Ejecutar se comprueba SQL Server (local o Docker)." -ForegroundColor DarkGray
try {
    & $py -m gis2dgs
} finally {
    Write-Host "Limpiando sesión Docker..." -ForegroundColor DarkGray
    & "$PSScriptRoot\scripts\cleanup_mssql.ps1"
}
