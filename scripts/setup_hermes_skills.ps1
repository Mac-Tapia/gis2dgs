#Requires -Version 5.1
<#
.SYNOPSIS
  Comprueba el skill de proyecto para Hermes Agent y muestra los siguientes pasos.
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$canonical = Join-Path $root "skills\gis2dgs\SKILL.md"
$hermesEntry = Join-Path $root ".agents\skills\gis2dgs\SKILL.md"

if (-not (Test-Path -LiteralPath $canonical)) {
    throw "Falta skill canónico: $canonical"
}
if (-not (Test-Path -LiteralPath $hermesEntry)) {
    throw "Falta entrada Hermes: $hermesEntry"
}

Write-Host "OK: skill canónico  → $canonical"
Write-Host "OK: entrada Hermes  → $hermesEntry"
Write-Host ""
Write-Host "Instale Hermes (preferible WSL2) y desde la raíz del repo:"
Write-Host "  hermes skills trust"
Write-Host "  hermes chat -q `"/gis2dgs resume el flujo convert + verify gate`""
Write-Host ""
Write-Host "Documentación: docs\HERMES_AGENT.md"
