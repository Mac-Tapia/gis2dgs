#Requires -Version 5.1
<#
.SYNOPSIS
  Ejecuta Hermes Agent en el contexto del repo GIS2DGS (vía WSL2).

.EXAMPLE
  .\scripts\hermes.ps1 doctor
  .\scripts\hermes.ps1 skills list
  .\scripts\hermes.ps1 chat -q "/gis2dgs describe el flujo convert"
  .\scripts\hermes.ps1 model
#>
param(
    [string]$Distro = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$HermesArgs
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $HermesArgs -or $HermesArgs.Count -eq 0) {
    $HermesArgs = @("--help")
}

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

function Convert-ToWslPath([string]$WinPath, [string]$DistroName) {
    $converted = & wsl -d $DistroName -- bash -lc "wslpath -a '$($WinPath -replace "'","'\\''")'" 2>$null
    $converted = ($converted | Select-Object -Last 1)
    if ($converted) { return $converted.Trim() }
    return "/mnt/" + $WinPath.Substring(0, 1).ToLower() + ($WinPath.Substring(2) -replace "\\", "/")
}

if (-not $Distro) {
    $Distro = Get-DefaultWslDistro
}

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    if (Get-Command hermes -ErrorAction SilentlyContinue) {
        Push-Location $root
        try {
            & hermes @HermesArgs
            exit $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
    throw "WSL no disponible y 'hermes' no está en PATH. Ejecute .\scripts\install_hermes.ps1"
}

$wslRoot = Convert-ToWslPath $root $Distro
$escaped = foreach ($a in $HermesArgs) {
    $safe = $a -replace "'", "'\''"
    "'$safe'"
}
$argLine = [string]::Join(" ", $escaped)

$bash = @"
set -euo pipefail
export PATH="`$HOME/.hermes/bin:`$HOME/.local/bin:`$PATH"
if ! command -v hermes >/dev/null 2>&1; then
  echo "Hermes no está instalado en WSL. Ejecute: .\scripts\install_hermes.ps1" >&2
  exit 127
fi
cd '$($wslRoot -replace "'","'\''")'
exec hermes $argLine
"@

& wsl -d $Distro -- bash -lc $bash
exit $LASTEXITCODE
