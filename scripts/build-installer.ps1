param([switch]$SkipAppBuild, [string]$Makensis = "")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$pythonExe = Join-Path (Get-Location) '.venv\Scripts\python.exe'
$version = (& $pythonExe -c 'from animecam import __version__; print(__version__)').Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid version.' }
$payloadName = "AnimeCamFX-v$version"
if (-not $SkipAppBuild) {
    & .\scripts\build.ps1 -Name $payloadName
    if ($LASTEXITCODE -ne 0) { throw 'App build failed.' }
}
$payload = [IO.Path]::GetFullPath((Join-Path (Get-Location) "dist\$payloadName"))
if (-not (Test-Path -LiteralPath (Join-Path $payload "$payloadName.exe"))) { throw 'App payload missing.' }
if (-not $Makensis) {
    $Makensis = Join-Path (Get-Location) 'artifacts\toolchain\nsis-3.12\makensis.exe'
    if (-not (Test-Path -LiteralPath $Makensis)) {
        & $pythonExe tools\fetch_nsis.py
        if ($LASTEXITCODE -ne 0) { throw 'Compiler download failed.' }
    }
}
$output = Join-Path (Get-Location) "dist\AnimeCamFX-Setup-$version.exe"
& $Makensis /INPUTCHARSET UTF8 "/DPAYLOAD=$payload" "/DSOURCE_EXE=$payloadName.exe" "/DOUTPUT=$output" "/DAPP_VERSION=$version" installer\AnimeCamFX.nsi
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
Write-Host "Installer ready: $output"
