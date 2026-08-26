param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
}

function Write-Info([string]$Message) {
    if ($Quiet) { return }
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    if ($Quiet) { return }
    Write-Host $Message -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    if ($Quiet) { return }
    Write-Host $Message -ForegroundColor Yellow
}

function Get-PythonJson([string]$Code) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $py -c $Code 2>$null
        if (-not $raw) { return $null }
        return ($raw | Out-String).Trim() | ConvertFrom-Json
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Get-DockerMasterUrl {
    return Get-PythonJson @"
import json
from gis2dgs.input.readers.mssql_backup import docker_master_url
print(json.dumps({"url": docker_master_url()}))
"@
}

function Remove-Gis2dgsContainer {
    # docker rm writes to stderr when the container is already gone; with
    # $ErrorActionPreference=Stop that aborts the script before compose up.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        cmd.exe /c "docker rm -f gis2dgs-mssql >nul 2>nul"
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-ModernOdbc {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $py -c "from gis2dgs.input.readers.mssql_backup import has_modern_odbc_driver; print('yes' if has_modern_odbc_driver() else 'no')"
        return ("$raw" -match "yes")
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Install-ModernOdbc {
    if (Test-ModernOdbc) { return $true }
    Write-Warn "No hay Microsoft ODBC Driver 17/18. SQL Server 2022 en Docker lo requiere."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "Descarga: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
        return $false
    }
    Write-Info "Instalando Microsoft ODBC Driver 18 (puede pedir permisos de administrador)..."
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & winget install --id Microsoft.msodbcsql.18 -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    } finally {
        $ErrorActionPreference = $prev
    }
    if (Test-ModernOdbc) {
        Write-Ok "ODBC Driver 18 instalado."
        return $true
    }
    Write-Host "Si winget pidio admin, acepte UAC y reintente. Manual:"
    Write-Host "  winget install --id Microsoft.msodbcsql.18 -e"
    return $false
}

function Wait-MssqlHealthy {
    $deadline = (Get-Date).AddMinutes(3)
    do {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        try {
            $status = (& docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" gis2dgs-mssql 2>$null | Out-String).Trim()
        } finally {
            $ErrorActionPreference = $prev
        }
        if ($status -eq "healthy") { return $true }
        if ($status -eq "exited" -or $status -eq "dead") { return $false }
        if (-not $Quiet) {
            Write-Host "Esperando a que SQL Server arranque dentro de Docker ($status)..."
        }
        Start-Sleep -Seconds 4
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Test-SaLogin {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $py -c @"
from gis2dgs.input.readers.mssql_backup import docker_master_url, probe_sql_server
url = docker_master_url()
print('ok' if url and probe_sql_server(url) else 'fail')
"@ 2>&1 | Out-String
        return $raw
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Save-MssqlSession {
    param([string]$SessionPath)
    New-Item -ItemType Directory -Force (Split-Path $SessionPath) | Out-Null
    if (-not $env:GIS2DGS_MSSQL_PORT) { $env:GIS2DGS_MSSQL_PORT = "1433" }
    if (-not $env:GIS2DGS_MSSQL_DOCKER) { $env:GIS2DGS_MSSQL_DOCKER = "true" }
    @(
        "`$env:GIS2DGS_MSSQL_URL = '$($env:GIS2DGS_MSSQL_URL)'"
        "`$env:GIS2DGS_MSSQL_HOST_STAGE_DIR = '$($env:GIS2DGS_MSSQL_HOST_STAGE_DIR)'"
        "`$env:GIS2DGS_MSSQL_SERVER_BACKUP_DIR = '$($env:GIS2DGS_MSSQL_SERVER_BACKUP_DIR)'"
        "`$env:GIS2DGS_MSSQL_DATA_DIRECTORY = '$($env:GIS2DGS_MSSQL_DATA_DIRECTORY)'"
        "`$env:GIS2DGS_MSSQL_PORT = '$($env:GIS2DGS_MSSQL_PORT)'"
        "`$env:GIS2DGS_MSSQL_SA_PASSWORD = '$($env:GIS2DGS_MSSQL_SA_PASSWORD)'"
        "`$env:GIS2DGS_MSSQL_DOCKER = '$($env:GIS2DGS_MSSQL_DOCKER)'"
    ) | Set-Content -Path $SessionPath -Encoding UTF8
}

function New-DevSaPassword {
    $chars = @('A','B','C','D','E','F','G','H','J','K','M','N','P','Q','R','T','W','X','Y')
    $nums = 2..9
    $tail = -join (1..8 | ForEach-Object {
        if (Get-Random -Maximum 2) { $chars | Get-Random } else { $nums | Get-Random }
    })
    return "Gis2dgs_$tail!"
}

if (-not $Quiet) {
    Write-Info "== GIS2DGS: comprobar o arrancar SQL Server =="
    Write-Host "El restore de .bak YA esta implementado. Este script solo garantiza el motor."
}

# La password en disco es la fuente de verdad para el contenedor gis2dgs-mssql.
$passwordFile = Join-Path $PWD "output\mssql\.sa_password"
if (-not $env:GIS2DGS_MSSQL_SA_PASSWORD -and (Test-Path $passwordFile)) {
    $env:GIS2DGS_MSSQL_SA_PASSWORD = (Get-Content -Raw $passwordFile).Trim()
    Write-Info "Password SA leida de output\mssql\.sa_password (no se versiona)."
}

# Limpiar restos de sesión anterior: si existe session.env.ps1 pero el contenedor no está corriendo
$sessionCheck = Join-Path $PWD "output\mssql\session.env.ps1"
if (Test-Path $sessionCheck) {
    $dockerCmd2 = Get-Command docker -ErrorAction SilentlyContinue
    $containerRunning = $false
    if ($dockerCmd2) {
        $prevPs = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $containerRunning = [bool](& docker ps --filter "name=gis2dgs-mssql" --format "{{.Names}}" 2>$null | Select-String "gis2dgs-mssql")
        $ErrorActionPreference = $prevPs
    }
    if (-not $containerRunning) {
        # Limpiar archivos de sesión pero preservar .sa_password para reutilizar la misma contraseña
        $mssqlOutDir = Join-Path $PWD "output\mssql"
        Get-ChildItem -Path $mssqlOutDir -Exclude ".sa_password" -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Info "Sesión anterior limpiada (contenedor no estaba corriendo)."
    }
}

$probeCode = @"
import json
from gis2dgs.input.readers.mssql_backup import probe_report
print(json.dumps(probe_report()))
"@
$probe = Get-PythonJson $probeCode
if ($probe -and $probe.ok) {
    $probeUrl = [string]$probe.url
    $env:GIS2DGS_MSSQL_URL = $probeUrl

    # Restaurar dirs Docker desde la sesion, pero no pisar la URL ya saneada.
    $sessionEarly = Join-Path $PWD "output\mssql\session.env.ps1"
    if (Test-Path $sessionEarly) {
        $savedUrl = $env:GIS2DGS_MSSQL_URL
        . $sessionEarly
        Write-Info "Variables de sesion cargadas desde output\mssql\session.env.ps1"
        $env:GIS2DGS_MSSQL_URL = $savedUrl
    }
    if (Test-Path $passwordFile) {
        $env:GIS2DGS_MSSQL_SA_PASSWORD = (Get-Content -Raw $passwordFile).Trim()
    }
    $rebuilt = Get-DockerMasterUrl
    if ($rebuilt -and $rebuilt.url) {
        $env:GIS2DGS_MSSQL_URL = [string]$rebuilt.url
    } else {
        $env:GIS2DGS_MSSQL_URL = $probeUrl
    }

    # Detect if gis2dgs-mssql Docker container is running and set vars accordingly
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerCmd) {
        $prevPs = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $running = & docker ps --filter "name=gis2dgs-mssql" --filter "status=running" -q 2>$null
        $ErrorActionPreference = $prevPs
        if ($running) {
            $loginCheck = Test-SaLogin
            if ($loginCheck -notmatch '(?m)^ok' -and -not (Test-ModernOdbc)) {
                Install-ModernOdbc | Out-Null
                $loginCheck = Test-SaLogin
            }
            if ($loginCheck -notmatch '(?m)^ok' -and (Test-ModernOdbc)) {
                Write-Warn "Contenedor Docker activo pero la password no coincide. Recreando contenedor..."
                Remove-Gis2dgsContainer
                # Fall through to the provisioning block below
            } elseif ($loginCheck -notmatch '(?m)^ok') {
                Write-Warn "SQL Server esta en Docker pero Windows no tiene ODBC 17/18."
                Write-Host "winget install --id Microsoft.msodbcsql.18 -e"
                Save-MssqlSession (Join-Path $PWD "output\mssql\session.env.ps1")
                exit 4
            } else {
                $backupHost = Join-Path $PWD "output\mssql\backup"
                New-Item -ItemType Directory -Force $backupHost | Out-Null
                if (-not $env:GIS2DGS_MSSQL_HOST_STAGE_DIR) {
                    $env:GIS2DGS_MSSQL_HOST_STAGE_DIR = $backupHost
                }
                if (-not $env:GIS2DGS_MSSQL_SERVER_BACKUP_DIR) {
                    $env:GIS2DGS_MSSQL_SERVER_BACKUP_DIR = "/var/opt/mssql/backup"
                }
                if (-not $env:GIS2DGS_MSSQL_DATA_DIRECTORY) {
                    $env:GIS2DGS_MSSQL_DATA_DIRECTORY = "/var/opt/mssql/data"
                }
                $env:GIS2DGS_MSSQL_DOCKER = "true"
                Save-MssqlSession (Join-Path $PWD "output\mssql\session.env.ps1")
                Write-Info "Contenedor Docker gis2dgs-mssql detectado. Variables Docker configuradas."
                Write-Ok "SQL Server accesible."
                Write-Host "GIS2DGS_MSSQL_URL=$($env:GIS2DGS_MSSQL_URL)"
                Write-Host "Siguiente: python -m gis2dgs inspect-input <archivo.bak>"
                exit 0
            }
        }
    } else {
        Write-Ok "SQL Server accesible."
        Write-Host "GIS2DGS_MSSQL_URL=$($env:GIS2DGS_MSSQL_URL)"
        Write-Host "Siguiente: python -m gis2dgs inspect-input <archivo.bak>"
        exit 0
    }
}

Write-Warn "No hay SQL Server alcanzable en localhost / LocalDB / GIS2DGS_MSSQL_URL."

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Warn "Docker no esta instalado. Instale SQL Server Express/LocalDB o Docker Desktop."
    Write-Host "Documentacion: docs\SYSTEM_REQUIREMENTS.md y docs\GUIA_PASO_A_PASO.md"
    exit 2
}

function Test-DockerEngineReady {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & docker info 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Start-DockerDesktopAndWait {
    param([int]$TimeoutSeconds = 180)

    $candidates = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $exe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $exe) {
        return $false
    }

    Write-Info "Docker instalado pero el motor no corre. Arrancando Docker Desktop..."
    Start-Process -FilePath $exe | Out-Null
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-DockerEngineReady) { return $true }
        if (-not $Quiet) {
            Write-Host "Esperando a que Docker Desktop quede listo..."
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    return $false
}

if (-not (Test-DockerEngineReady)) {
    if (-not (Start-DockerDesktopAndWait)) {
        Write-Warn "Docker esta instalado pero el motor no corre. Inicie Docker Desktop y reintente."
        exit 3
    }
    Write-Ok "Docker Desktop listo."
}

New-Item -ItemType Directory -Force (Split-Path $passwordFile) | Out-Null
if (-not $env:GIS2DGS_MSSQL_SA_PASSWORD) {
    if (Test-Path $passwordFile) {
        $env:GIS2DGS_MSSQL_SA_PASSWORD = (Get-Content -Raw $passwordFile).Trim()
        Write-Info "Password SA leida de output\mssql\.sa_password (no se versiona)."
    } else {
        $env:GIS2DGS_MSSQL_SA_PASSWORD = New-DevSaPassword
        Set-Content -Path $passwordFile -Value $env:GIS2DGS_MSSQL_SA_PASSWORD -NoNewline
        Write-Info "Password SA de desarrollo generada en output\mssql\.sa_password."
    }
}

if (-not $env:GIS2DGS_MSSQL_PORT) {
    $env:GIS2DGS_MSSQL_PORT = "1433"
}

$backupHost = Join-Path $PWD "output\mssql\backup"
New-Item -ItemType Directory -Force $backupHost | Out-Null
$env:GIS2DGS_MSSQL_HOST_STAGE_DIR = $backupHost
$env:GIS2DGS_MSSQL_SERVER_BACKUP_DIR = "/var/opt/mssql/backup"
$env:GIS2DGS_MSSQL_DATA_DIRECTORY = "/var/opt/mssql/data"

$mssqlImage = "mcr.microsoft.com/mssql/server:2022-CU16-ubuntu-22.04"
$composeFile = "docker-compose.mssql.yml"

function Test-DockerImagePresent([string]$Image) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        # Discard inspect JSON so it never becomes the function return value.
        $null = & docker image inspect $Image 2>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Ensure-MssqlImage {
    param(
        [string]$Image,
        [int]$Attempts = 3
    )
    if (Test-DockerImagePresent $Image) {
        Write-Info "Imagen local presente: $Image"
        return $true
    }
    Write-Info "Descargando imagen $Image (puede tardar; reintentos=$Attempts)..."
    for ($i = 1; $i -le $Attempts; $i++) {
        Write-Info "docker pull intento $i/$Attempts ..."
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            # Out-Host keeps docker progress visible without polluting return values.
            & docker pull $Image 2>&1 | ForEach-Object { Write-Host $_ }
            $code = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $prev
        }
        if (($code -eq 0) -and (Test-DockerImagePresent $Image)) {
            Write-Ok "Imagen lista: $Image"
            return $true
        }
        # Image may already be local after a partial/failed progress stream.
        if (Test-DockerImagePresent $Image) {
            Write-Ok "Imagen local usable tras intento ${i}: $Image"
            return $true
        }
        Write-Warn "Pull fallido (intento $i). Si ve TLS timeout o commit/rename, reintente o reinicie Docker Desktop."
        Start-Sleep -Seconds ([Math]::Min(15 * $i, 45))
    }
    return $false
}

if (-not (Ensure-MssqlImage -Image $mssqlImage)) {
    Write-Warn "No se pudo descargar $mssqlImage desde mcr.microsoft.com."
    Write-Host "Opciones:"
    Write-Host "  1) Reintente en otra red/VPN: docker pull $mssqlImage"
    Write-Host "  2) Use SQL Server local y defina GIS2DGS_MSSQL_URL hacia master"
    Write-Host "Documentacion: docs\SYSTEM_REQUIREMENTS.md"
    exit 5
}

Write-Info "Arrancando contenedor $mssqlImage ..."
Remove-Gis2dgsContainer
Install-ModernOdbc | Out-Null
$pullPolicy = if (Test-DockerImagePresent $mssqlImage) { "never" } else { "missing" }
& docker compose -f $composeFile up -d --pull $pullPolicy
if ($LASTEXITCODE -ne 0) {
    Write-Warn "docker compose up fallo. Revise Docker Desktop, puerto $($env:GIS2DGS_MSSQL_PORT) y GIS2DGS_MSSQL_SA_PASSWORD."
    exit 5
}

$env:GIS2DGS_MSSQL_DOCKER = "true"
$urlInfo = Get-DockerMasterUrl
if ($urlInfo -and $urlInfo.url) {
    $env:GIS2DGS_MSSQL_URL = [string]$urlInfo.url
}

Write-Info "Conectando con usuario sa por ODBC (sin autenticacion de Windows)..."
$waitCode = @"
import json
from gis2dgs.input.readers.mssql_backup import wait_for_docker_odbc
print(json.dumps(wait_for_docker_odbc(timeout_seconds=120)))
"@
$waited = Get-PythonJson $waitCode
$ready = $false
if ($waited -and $waited.ok) {
    $env:GIS2DGS_MSSQL_URL = [string]$waited.url
    $ready = $true
}

$env:GIS2DGS_MSSQL_DOCKER = "true"
$session = Join-Path $PWD "output\mssql\session.env.ps1"
Save-MssqlSession $session

if (-not $ready) {
    Write-Warn "El contenedor arranco pero Windows no pudo conectar por ODBC con sa."
    if (-not (Test-ModernOdbc)) {
        Write-Host "Falta Microsoft ODBC Driver 17/18. En una consola elevada:"
        Write-Host "  winget install --id Microsoft.msodbcsql.18 -e"
        Write-Host "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
    }
    if ($waited -and $waited.error) {
        Write-Host "Detalle ODBC: $($waited.error)"
    }
    Write-Host "Variables guardadas en output\mssql\session.env.ps1"
    exit 4
}

Write-Ok "SQL Server listo (Docker)."
Write-Host "GIS2DGS_MSSQL_URL=$($env:GIS2DGS_MSSQL_URL)"
Write-Host "Para reutilizar esta sesion: . .\output\mssql\session.env.ps1"
Write-Host "Fixture opcional: python scripts\mssql_backup_roundtrip.py --convert"
Write-Host "Convertir un .bak: `$env:GIS2DGS_MSSQL_BACKUP='C:\ruta\red.bak'; python -m gis2dgs convert examples\mssql_backup\project.yaml --json"
exit 0
