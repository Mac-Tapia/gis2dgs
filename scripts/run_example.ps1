$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path .venv\Scripts\Activate.ps1) { & .\.venv\Scripts\Activate.ps1 }
gis2dgs convert examples/minimal/project.yaml --json
