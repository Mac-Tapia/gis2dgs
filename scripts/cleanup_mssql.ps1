# GIS2DGS — limpieza de sesión Docker/MSSQL
# Elimina el contenedor gis2dgs-mssql y los archivos de sesión de output\mssql\
# para que la próxima ejecución inicie desde cero limpio.
#
# Uso: .\scripts\cleanup_mssql.ps1
# Opcional al cerrar la GUI: .\RUN.ps1 -Cleanup  (por defecto el contenedor se deja activo)

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot

# 1. Detener y eliminar el contenedor via docker compose (volúmenes incluidos)
$composeFile = Join-Path $root "docker-compose.mssql.yml"
if (Test-Path $composeFile) {
    & docker compose -f $composeFile down -v 2>$null | Out-Null
}

# Forzar eliminación directa por si compose no estaba disponible o ya no gestiona el contenedor
cmd.exe /c "docker rm -f gis2dgs-mssql >nul 2>nul"

# 2. Eliminar archivos de sesión de output\mssql\ preservando .sa_password entre sesiones
#    para que la próxima ejecución reutilice la misma contraseña que el contenedor tiene registrada.
$mssqlOut = Join-Path $root "output\mssql"
if (Test-Path $mssqlOut) {
    Get-ChildItem -Path $mssqlOut -Exclude ".sa_password" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Eliminar output\mssql_restore\ si existe
$mssqlRestore = Join-Path $root "output\mssql_restore"
if (Test-Path $mssqlRestore) {
    Remove-Item -Path $mssqlRestore -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Limpieza completada. Próxima ejecución iniciará desde cero." -ForegroundColor Green
