#Requires -Version 5.1
<#
.SYNOPSIS
  Instala Hermes Agent (preferible en WSL2 Ubuntu) y prepara el skill GIS2DGS.

.DESCRIPTION
  1) Verifica WSL Ubuntu
  2) Ejecuta el instalador oficial de Hermes dentro de WSL
  3) Confía el skill de este repo (hermes skills trust)
  4) Muestra cómo configurar el modelo (API key)

  No escribe secretos. Tras instalar, configure el proveedor con:
    .\scripts\hermes.ps1 model
#>
param(
    [switch]$SkipBrowser,
    [switch]$NativeWindows,
    [string]$Distro = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-DefaultWslDistro {
    $raw = & wsl -l -v 2>$null | Out-String
    $clean = $raw -replace "`0", ""
    foreach ($line in ($clean -split "`r?`n")) {
        if ($line -match '^\*\s*(\S+)') {
            return $Matches[1]
        }
    }
    foreach ($line in ($clean -split "`r?`n")) {
        if ($line -match 'Ubuntu') {
            $tok = ($line.Trim() -split "\s+")[0]
            if ($tok -and $tok -ne "NAME") { return $tok.TrimStart("*") }
        }
    }
    return "Ubuntu"
}

function Test-WslDistro([string]$Name) {
    $raw = & wsl -l -q 2>$null | Out-String
    $clean = ($raw -replace "`0", "")
    foreach ($line in ($clean -split "`r?`n")) {
        if ($line.Trim() -eq $Name) { return $true }
    }
    return $false
}

if (-not $Distro) {
    $Distro = Get-DefaultWslDistro
}

Write-Host "== GIS2DGS · instalar Hermes =="
Write-Host "Repo: $root"
Write-Host "Distro WSL: $Distro"
Write-Host ""

& (Join-Path $PSScriptRoot "setup_hermes_skills.ps1")

if ($NativeWindows) {
    Write-Host "Instalación nativa Windows (experimental/oficial según build)..."
    Write-Host "Ejecute manualmente en PowerShell:"
    Write-Host '  iex (irm https://hermes-agent.nousresearch.com/install.ps1)'
    Write-Host "Luego: hermes skills trust `"$root`""
    exit 0
}

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    throw "WSL no está disponible. Instale WSL2 (`wsl --install -d Ubuntu`) o use -NativeWindows."
}

if (-not (Test-WslDistro $Distro)) {
    throw "Distro WSL '$Distro' no encontrada. Use -Distro <nombre> (wsl -l -v)."
}

$wslRoot = & wsl -d $Distro -- bash -lc "wslpath -a '$($root -replace "'","'\\''")'"
$wslRoot = ($wslRoot | Select-Object -Last 1).Trim()
if (-not $wslRoot) {
    # Fallback típico D:\ → /mnt/d/
    $wslRoot = "/mnt/" + $root.Substring(0, 1).ToLower() + ($root.Substring(2) -replace "\\", "/")
}

Write-Host "Ruta WSL del repo: $wslRoot"
Write-Host "Descargando e instalando Hermes en WSL ($Distro)..."
Write-Host "(puede tardar varios minutos)"

$installCmd = @"
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export PATH="`$HOME/.hermes/bin:`$HOME/.local/bin:`$PATH"
if command -v hermes >/dev/null 2>&1; then
  echo "Hermes ya instalado: `$(hermes --version 2>/dev/null || echo ok)"
else
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh
  # Solo --skip-browser (flags no documentados rompen el instalador).
  bash /tmp/hermes-install.sh --skip-browser
fi
[ -f "`$HOME/.bashrc" ] && . "`$HOME/.bashrc" || true
export PATH="`$HOME/.hermes/bin:`$HOME/.local/bin:`$PATH"
command -v hermes
hermes --version || true
cd "$wslRoot"
hermes skills trust "$wslRoot" || hermes skills trust
echo TRUST_OK
"@

& wsl -d $Distro -- bash -lc $installCmd
if ($LASTEXITCODE -ne 0) {
    throw "Falló la instalación / trust de Hermes en WSL (exit $LASTEXITCODE)."
}

Write-Host ""
Write-Host "Siguiente paso (obligatorio): configurar modelo LLM"
Write-Host "  .\scripts\hermes.ps1 model"
Write-Host "  # o: .\scripts\hermes.ps1 setup"
Write-Host ""
Write-Host "Probar skill del proyecto:"
Write-Host '  .\scripts\hermes.ps1 chat -q "/gis2dgs resume el verify gate"'
Write-Host ""
Write-Host "Diagnóstico:"
Write-Host "  .\scripts\hermes.ps1 doctor"
