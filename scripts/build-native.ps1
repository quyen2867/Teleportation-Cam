$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vsRoot = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsRoot) { throw 'Visual Studio C++ build tools are required to build the shared camera bridge.' }
& (Join-Path $vsRoot 'Common7\Tools\Launch-VsDevShell.ps1') -Arch amd64 -HostArch amd64 -SkipAutomaticLocation | Out-Null
$nativeBuild = Join-Path $projectRoot 'artifacts\native'
New-Item -ItemType Directory -Path $nativeBuild -Force | Out-Null
Push-Location -LiteralPath $nativeBuild
try {
    & cl.exe /nologo /LD /MD /O2 /EHsc /std:c++17 /DUNICODE /D_UNICODE (Join-Path $projectRoot 'native\shared_camera.cpp') /link /OUT:shared_camera.dll mfplat.lib mf.lib mfuuid.lib mfreadwrite.lib ole32.lib
    if ($LASTEXITCODE -ne 0) { throw 'Shared camera compilation failed.' }
} finally { Pop-Location }
