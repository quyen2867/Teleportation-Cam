param([string]$Python = "py")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ($Python -eq "py") {
    & py -3.12 -m venv .venv
} else {
    & $Python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw "Cannot create Python 3.12 environment. Install Python 3.12 x64 first." }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& .\.venv\Scripts\python.exe -m animecam.models --download
if ($LASTEXITCODE -ne 0) { throw "Model download failed." }
Write-Host "Ready. Run .\scripts\run.ps1"
