param([string]$Name = "AnimeCamFX")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ($Name -notmatch '^[A-Za-z][A-Za-z0-9._-]{0,60}$') { throw "Invalid build name." }
$distRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) 'dist'))
$buildTarget = [IO.Path]::GetFullPath((Join-Path $distRoot $Name))
if (-not $buildTarget.StartsWith($distRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Build target is outside dist."
}
$pythonExe = Join-Path (Get-Location) ".venv\Scripts\python.exe"
$env:MPLCONFIGDIR = Join-Path (Get-Location) "artifacts\matplotlib"
if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Run setup.ps1 first." }
& .\scripts\build-native.ps1
& $pythonExe scripts\generate_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }
& $pythonExe -m animecam.models --download
if ($LASTEXITCODE -ne 0) { throw "Models unavailable." }
& $pythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed; build stopped." }
$env:ANIMECAM_BUILD_NAME = $Name
& $pythonExe -m PyInstaller --noconfirm --clean installer\AnimeCamFX.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
Write-Host "Built: $buildTarget\$Name.exe. Distribute the entire $Name folder."
