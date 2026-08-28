# GIS2DGS — punto de entrada universal (Windows)
# Si no existe .venv, ejecuta .\INSTALL_AND_VERIFY.ps1 automaticamente (primera vez).
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
# SQL Server (Docker) se deja corriendo al cerrar la GUI para poder cargar .bak
# en la siguiente sesión. Limpieza opcional:
#   .\RUN.ps1 -Cleanup
#   $env:GIS2DGS_MSSQL_CLEANUP = "1"; .\RUN.ps1
#
# Para generar DGS desde datos nuevos: inspeccione, proponga mapping, configure
# project.yaml y vuelva a cargarlo antes de Ejecutar.

param(
    [switch]$Cleanup
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No existe .venv; ejecutando instalacion integral (solo la primera vez)..." -ForegroundColor Yellow
    & "$PSScriptRoot\INSTALL_AND_VERIFY.ps1"
    if (-not (Test-Path $py)) {
        throw "No se pudo crear .venv. Revise Python 3.11+ e INSTALL_AND_VERIFY.ps1"
    }
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
} else {
    Write-Host "SQL Server listo para restaurar .bak." -ForegroundColor DarkGray
}

# Cargar variables de sesión que ensure_mssql.ps1 pudo haber creado/actualizado
$sessionEnv = Join-Path $PSScriptRoot "output\mssql\session.env.ps1"
if (Test-Path $sessionEnv) {
    . $sessionEnv
}

Write-Host "Abriendo GIS2DGS. Cargue un archivo o carpeta y pulse Ejecutar." -ForegroundColor Cyan
Write-Host "Backup .bak: al pulsar Ejecutar se restaura en SQL Server (Docker/local)." -ForegroundColor DarkGray
try {
    & $py -m gis2dgs
} finally {
    $doCleanup = $Cleanup -or (
        ($env:GIS2DGS_MSSQL_CLEANUP -as [string]) -match '^(1|true|yes)$'
    )
    if ($doCleanup) {
        Write-Host "Limpiando sesión Docker (-Cleanup)..." -ForegroundColor DarkGray
        & "$PSScriptRoot\scripts\cleanup_mssql.ps1"
    } else {
        Write-Host "SQL Server Docker se mantiene activo para el próximo .bak." -ForegroundColor DarkGray
        Write-Host "Para apagarlo: .\scripts\cleanup_mssql.ps1   o   .\RUN.ps1 -Cleanup" -ForegroundColor DarkGray
    }
}
