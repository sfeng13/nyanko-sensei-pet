param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$PythonRuntimeSource = ''
)

$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$BuildRoot = Join-Path $Root 'build\windows'
$DistRoot = Join-Path $Root 'dist'
$Payload = Join-Path $BuildRoot 'payload'
$OfflineDir = Join-Path $BuildRoot 'offline'
$OnlineDir = Join-Path $BuildRoot 'online'
$Runtime = Join-Path $Payload 'runtime\python313'
$OfflineName = "NyankoSensei-$Version-Windows-x64-Offline.zip"
$OnlineName = "NyankoSensei-$Version-Windows-x64-Online-Setup.zip"

function Clear-ProjectBuildDirectory([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $allowed = @([IO.Path]::GetFullPath($BuildRoot).TrimEnd('\'), [IO.Path]::GetFullPath($DistRoot).TrimEnd('\'))
    if (-not ($allowed | Where-Object { $full -eq $_ -or $full.StartsWith($_ + '\', [StringComparison]::OrdinalIgnoreCase) })) {
        throw "Refusing to clear a path outside build/dist: $full"
    }
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
}

function Invoke-Robocopy([string]$Source, [string]$Destination, [string[]]$Extra = @()) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy $Source $Destination /E /NFL /NDL /NJH /NJS /NP @Extra
    if ($LASTEXITCODE -ge 8) { throw "Copy failed ($LASTEXITCODE): $Source" }
}

function Get-TreeBytes([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return 0L }
    return [long](Get-ChildItem -LiteralPath $Path -Recurse -File | Measure-Object -Property Length -Sum).Sum
}

function Format-Bytes([long]$Bytes) {
    if ($Bytes -ge 1GB) { return ('{0:N2} GiB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N0} MiB' -f ($Bytes / 1MB)) }
    return ('{0:N0} KiB' -f ($Bytes / 1KB))
}

function Build-Runtime {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Runtime) | Out-Null
    if ($PythonRuntimeSource) {
        $source = [IO.Path]::GetFullPath($PythonRuntimeSource)
        $excluded = @(
            (Join-Path $source 'Scripts'),
            (Join-Path $source 'Lib\site-packages\pip'),
            (Join-Path $source 'Lib\site-packages\pip-26.2.1.dist-info'),
            (Join-Path $source 'Lib\site-packages\pytest'),
            (Join-Path $source 'Lib\site-packages\pytest-9.1.1.dist-info'),
            (Join-Path $source 'Lib\site-packages\ruff'),
            (Join-Path $source 'Lib\site-packages\ruff-0.16.6.dist-info')
        )
        $copyArgs = @('/XD') + $excluded + @('/XF', '*.pyc')
        Invoke-Robocopy $source $Runtime $copyArgs
    }
    else {
        $download = Join-Path $BuildRoot 'python-3.13.14-embed-amd64.zip'
        if (-not (Test-Path -LiteralPath $download)) {
            Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip' -OutFile $download
        }
        Expand-Archive -LiteralPath $download -DestinationPath $Runtime -Force
        $sitePackages = Join-Path $Runtime 'Lib\site-packages'
        New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null
        $buildPython = (Get-Command python.exe -ErrorAction Stop).Source
        & $buildPython -m pip install --disable-pip-version-check --no-warn-script-location --no-compile --only-binary=:all: --target $sitePackages -r (Join-Path $Root 'requirements-runtime.lock')
        if ($LASTEXITCODE -ne 0) { throw '安装锁定运行依赖失败。' }
        Set-Content -LiteralPath (Join-Path $Runtime 'python313._pth') -Encoding ASCII -Value @('python313.zip', '.', 'Lib/site-packages', 'import site')
    }

    $pth = Join-Path $Runtime 'python313._pth'
    if (-not (Test-Path -LiteralPath $pth)) {
        Set-Content -LiteralPath $pth -Encoding ASCII -Value @('python313.zip', '.', 'Lib/site-packages', 'import site')
    }
    else {
        Set-Content -LiteralPath $pth -Encoding ASCII -Value @('python313.zip', '.', 'Lib/site-packages', 'import site')
    }

    # This application has no QtWebEngine imports. Remove only WebEngine and
    # WebView components/resources; keep Qt Widgets, Multimedia, codecs and plugins.
    $site = Join-Path $Runtime 'Lib\site-packages\PySide6'
    $remove = @(
        'QtWebEngineCore.pyd', 'QtWebEngineCore.pyi', 'QtWebEngineQuick.pyd', 'QtWebEngineQuick.pyi',
        'QtWebEngineWidgets.pyd', 'QtWebEngineWidgets.pyi', 'QtWebEngineProcess.exe',
        'QtWebView.pyd', 'QtWebView.pyi', 'QtWebViewWidgets.pyd', 'QtWebViewWidgets.pyi',
        'Qt6WebEngineCore.dll', 'Qt6WebEngineQuick.dll', 'Qt6WebEngineQuickDelegatesQml.dll',
        'Qt6WebEngineWidgets.dll', 'Qt6WebView.dll', 'Qt6WebViewQuick.dll',
        'Qt6Pdf.dll', 'Qt6PdfQuick.dll', 'Qt6PdfWidgets.dll', 'QtPdf.pyd', 'QtPdf.pyi',
        'QtPdfWidgets.pyd', 'QtPdfWidgets.pyi', 'QtPdfWidgets.dll'
    )
    foreach ($name in $remove) {
        $candidate = Join-Path $site $name
        if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Force }
    }
    foreach ($folder in @('QtWebEngineCore', 'QtWebEngineQuick', 'QtWebView', 'QtPdf')) {
        $candidate = Join-Path $site $folder
        if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Recurse -Force }
    }
    foreach ($folder in @('resources', 'translations', 'qml')) {
        $candidate = Join-Path $site $folder
        if (Test-Path -LiteralPath $candidate) {
            Get-ChildItem -LiteralPath $candidate -Recurse -File | Where-Object {
                $_.Name -match '^qtwebengine_' -or $_.Name -match '^qtwebview_' -or
                $_.Name -in @('icudtl.dat', 'v8_context_snapshot.bin', 'v8_context_snapshot.debug.bin')
            } | Remove-Item -Force
            if ($folder -eq 'qml') {
                foreach ($sub in @('QtWebEngine', 'QtWebView')) {
                    $qmlPath = Join-Path $candidate $sub
                    if (Test-Path -LiteralPath $qmlPath) { Remove-Item -LiteralPath $qmlPath -Recurse -Force }
                }
            }
        }
    }

    $runtimePython = Join-Path $Runtime 'python.exe'
    & $runtimePython -c "import PySide6.QtCore, PySide6.QtWidgets, PySide6.QtMultimedia, numpy, PIL, imageio_ffmpeg; print('runtime smoke ok')"
    if ($LASTEXITCODE -ne 0) { throw '精简后运行环境导入检查失败。' }
}

Clear-ProjectBuildDirectory $BuildRoot
Clear-ProjectBuildDirectory $DistRoot
New-Item -ItemType Directory -Force -Path $Payload, $OfflineDir, $OnlineDir, $DistRoot | Out-Null
Build-Runtime

Invoke-Robocopy (Join-Path $Root 'app\pet') (Join-Path $Payload 'app\pet') @('/XD', '__pycache__', '.pytest_cache', '.ruff_cache', '/XF', '*.pyc')
Invoke-Robocopy (Join-Path $Root 'app\assets') (Join-Path $Payload 'app\assets') @('/XD', '__pycache__', '/XF', '*.pyc')
Invoke-Robocopy (Join-Path $Root 'characters') (Join-Path $Payload 'characters') @('/XD', '__pycache__', '/XF', '*.pyc')
Invoke-Robocopy (Join-Path $Root 'scripts') (Join-Path $Payload 'scripts') @('/XD', '__pycache__', '/XF', '*.pyc')
Copy-Item -LiteralPath (Join-Path $Root 'nyanko_runtime.py'), (Join-Path $Root 'nyanko_choreography.py'), (Join-Path $Root 'nyanko_codex_hook.py'), (Join-Path $Root 'nyanko_codex_link.py'), (Join-Path $Root 'launch.pyw'), (Join-Path $Root 'nyanko_paths.py'), (Join-Path $Root 'requirements-runtime.lock') -Destination $Payload
Copy-Item -LiteralPath (Join-Path $Root 'app\LICENSE'), (Join-Path $Root 'app\THIRD_PARTY_NOTICES.md') -Destination (Join-Path $Payload 'app')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install.ps1'), (Join-Path $PSScriptRoot 'Uninstall.cmd'), (Join-Path $PSScriptRoot 'Manage-Codex-Link.cmd') -Destination $Payload
Set-Content -LiteralPath (Join-Path $Payload 'version.txt') -Encoding UTF8 -Value $Version

$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework 编译器不可用，无法生成启动器和无窗口 Hook 转发器。' }
$launcherExe = Join-Path $Payload 'NyankoSensei.exe'
$hookHostExe = Join-Path $Payload 'HookHost.exe'
& $compiler /nologo /target:winexe "/out:$launcherExe" /reference:System.dll /reference:System.Windows.Forms.dll (Join-Path $PSScriptRoot 'NyankoLauncher.cs')
if ($LASTEXITCODE -ne 0) { throw '编译桌宠启动器失败。' }
& $compiler /nologo /target:winexe "/out:$hookHostExe" /reference:System.dll (Join-Path $PSScriptRoot 'CodexHookHost.cs')
if ($LASTEXITCODE -ne 0) { throw '编译 Codex Hook 转发器失败。' }

$python = Join-Path $Runtime 'python.exe'
& $python -m compileall -q (Join-Path $Payload 'app\pet') (Join-Path $Payload 'scripts')
if ($LASTEXITCODE -ne 0) { throw 'Python 语法检查失败。' }
Push-Location $Payload
try { & $python -c "import os,sys; sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), 'app')); import pet; import nyanko_runtime; print('application smoke ok')" }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw '桌宠应用导入检查失败。' }
Get-ChildItem -LiteralPath $Payload -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

# The offline bundle invokes Install.ps1 from its own root; the online bootstrap
# has the same filename but selects Online mode.
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Setup-Offline.cmd') -Destination (Join-Path $OfflineDir 'Setup.cmd')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install.ps1') -Destination $OfflineDir
$offlinePayload = Join-Path $OfflineDir 'payload'
New-Item -ItemType Directory -Force -Path $offlinePayload | Out-Null
Get-ChildItem -LiteralPath $Payload -Force | Copy-Item -Destination $offlinePayload -Recurse -Force

Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Setup-Online.cmd') -Destination (Join-Path $OnlineDir 'Setup.cmd')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install.ps1') -Destination $OnlineDir

$offlineArchive = Join-Path $DistRoot $OfflineName
$onlineArchive = Join-Path $DistRoot $OnlineName
Compress-Archive -Path (Join-Path $OfflineDir '*') -DestinationPath $offlineArchive -CompressionLevel Optimal
Compress-Archive -Path (Join-Path $OnlineDir '*') -DestinationPath $onlineArchive -CompressionLevel Optimal

$hashOffline = (Get-FileHash -Algorithm SHA256 -LiteralPath $offlineArchive).Hash.ToLowerInvariant()
$hashOnline = (Get-FileHash -Algorithm SHA256 -LiteralPath $onlineArchive).Hash.ToLowerInvariant()
@("$hashOffline  $OfflineName", "$hashOnline  $OnlineName") | Set-Content -LiteralPath (Join-Path $DistRoot 'SHA256SUMS.txt') -Encoding ASCII

$runtimeBytes = Get-TreeBytes $Runtime
$payloadBytes = Get-TreeBytes $Payload
$onlineBytes = [long](Get-Item -LiteralPath $onlineArchive).Length
$offlineBytes = [long](Get-Item -LiteralPath $offlineArchive).Length
$runtimeFormatted = Format-Bytes $runtimeBytes
$payloadFormatted = Format-Bytes $payloadBytes
$onlineFormatted = Format-Bytes $onlineBytes
$offlineFormatted = Format-Bytes $offlineBytes
$report = @"
# Windows x64 package size report

Version: $Version
Generated (UTC): $([DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm:ss'))

| Item | Exact size | Approximate size |
|---|---:|---:|
| Embedded Python + runtime dependencies (installed directory) | $runtimeBytes bytes | $runtimeFormatted |
| Full installed payload directory | $payloadBytes bytes | $payloadFormatted |
| Online setup download | $onlineBytes bytes | $onlineFormatted |
| Offline package download | $offlineBytes bytes | $offlineFormatted |

The online setup is only a bootstrapper; first installation downloads the full offline payload and verifies its SHA-256 against `SHA256SUMS.txt`.
The offline archive includes the same payload and requires no preinstalled Python.
"@
$report | Set-Content -LiteralPath (Join-Path $DistRoot 'SIZE_REPORT.md') -Encoding UTF8

Write-Host "Created: $onlineArchive"
Write-Host "Created: $offlineArchive"
Write-Host "Runtime: $runtimeFormatted; installed payload: $payloadFormatted"
Write-Host "Online zip: $onlineFormatted; offline zip: $offlineFormatted"
