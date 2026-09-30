param(
    [ValidateSet('Online', 'Offline', 'ManageCodex', 'Uninstall')]
    [string]$Mode = 'Online'
)

$ErrorActionPreference = 'Stop'
$Repo = 'sfeng13/nyanko-sensei-pet'
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\NyankoSensei'
$UserData = Join-Path $env:LOCALAPPDATA 'NyankoSensei'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NyankoSensei'
$script:Form = $null
$script:Progress = $null
$script:Status = $null

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

function Format-Bytes([long]$Bytes) {
    if ($Bytes -ge 1GB) { return ('{0:N2} GiB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N0} MiB' -f ($Bytes / 1MB)) }
    return ('{0:N0} KiB' -f ($Bytes / 1KB))
}

function New-Window([string]$Title, [int]$Height = 360) {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = $Title
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ClientSize = New-Object System.Drawing.Size(560, $Height)
    $form.Font = [System.Drawing.Font]::new('Microsoft YaHei UI', 9)
    $script:Form = $form
    return $form
}

function Add-Label($Form, [string]$Text, [int]$X, [int]$Y, [int]$Width, [int]$Height = 28) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($Width, $Height)
    $Form.Controls.Add($label)
    return $label
}

function Get-ReleaseInfo {
    $headers = @{ 'User-Agent' = 'NyankoSensei-Pet-Installer'; 'Accept' = 'application/vnd.github+json' }
    $url = "https://api.github.com/repos/$Repo/releases/latest"
    $release = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 30
    $bundle = @($release.assets | Where-Object { $_.name -like '*Windows-x64-Offline.zip' }) | Select-Object -First 1
    $checksums = @($release.assets | Where-Object { $_.name -eq 'SHA256SUMS.txt' }) | Select-Object -First 1
    if (-not $bundle -or -not $checksums) { throw '最新发布缺少 Windows 离线包或校验文件。' }
    return [pscustomobject]@{ Release = $release; Bundle = $bundle; Checksums = $checksums }
}

function Download-File([string]$Url, [string]$Destination) {
    $client = New-Object System.Net.WebClient
    $client.Headers.Add('User-Agent', 'NyankoSensei-Pet-Installer')
    $client.Headers.Add('Accept', 'application/octet-stream')
    $state = @{ Done = $false; Error = $null }
    $progressHandler = [System.Net.DownloadProgressChangedEventHandler]{
        param($sender, $eventArgs)
        if ($script:Progress) { $script:Progress.Value = [Math]::Min(100, [Math]::Max(0, $eventArgs.ProgressPercentage)) }
        if ($script:Status) { $script:Status.Text = "正在下载桌宠运行文件… $($eventArgs.ProgressPercentage)%" }
        if ($script:Form) { $script:Form.Refresh(); [System.Windows.Forms.Application]::DoEvents() }
    }.GetNewClosure()
    $completedHandler = [System.Net.DownloadFileCompletedEventHandler]{
        param($sender, $eventArgs)
        if ($eventArgs.Error) { $state.Error = $eventArgs.Error }
        elseif ($eventArgs.Cancelled) { $state.Error = [Exception]::new('下载已取消。') }
        $state.Done = $true
    }.GetNewClosure()
    $client.add_DownloadProgressChanged($progressHandler)
    $client.add_DownloadFileCompleted($completedHandler)
    try {
        $client.DownloadFileAsync([Uri]$Url, $Destination)
        while (-not $state.Done) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 80
        }
        if ($state.Error) { throw $state.Error }
    }
    finally {
        $client.Dispose()
    }
}

function Get-ExpectedHash([string]$Text, [string]$FileName) {
    $escaped = [Regex]::Escape($FileName)
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line -match "^([0-9a-fA-F]{64})\s+\*?$escaped$") { return $matches[1].ToUpperInvariant() }
    }
    throw "校验文件中没有 $FileName 的 SHA-256。"
}

function New-StartMenuShortcut {
    $menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\猫咪老师桌宠'
    New-Item -ItemType Directory -Force -Path $menu | Out-Null
    $shortcutPath = Join-Path $menu '猫咪老师桌宠.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $InstallRoot 'NyankoSensei.exe'
    $shortcut.WorkingDirectory = $InstallRoot
    $shortcut.IconLocation = Join-Path $InstallRoot 'app\assets\icon.ico'
    $shortcut.Save()
}

function Invoke-CodexHookManager([string]$Action) {
    $python = Join-Path $InstallRoot 'runtime\python313\python.exe'
    $manager = Join-Path $InstallRoot 'scripts\codex_hooks.py'
    if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $manager)) {
        throw '桌宠 Hook 管理文件缺失；为避免留下失效钩子，停止后续操作。'
    }
    $output = & $python $manager $Action --root $InstallRoot 2>&1
    if ($LASTEXITCODE -ne 0) { throw (($output | Out-String).Trim()) }
    return ($output | Out-String).Trim()
}

function Install-Payload([string]$PayloadRoot, [bool]$EnableCodex) {
    if (-not (Test-Path -LiteralPath (Join-Path $PayloadRoot 'NyankoSensei.exe'))) {
        throw '安装包内容不完整，找不到桌宠启动程序。'
    }
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    Copy-Item -Path (Join-Path $PayloadRoot '*') -Destination $InstallRoot -Recurse -Force
    New-StartMenuShortcut

    New-Item -Path $UninstallKey -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayName -Value '猫咪老师桌宠' -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayVersion -Value (Get-Content (Join-Path $InstallRoot 'version.txt') -Raw).Trim() -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name Publisher -Value 'sfeng13' -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name InstallLocation -Value $InstallRoot -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayIcon -Value (Join-Path $InstallRoot 'NyankoSensei.exe') -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name UninstallString -Value ('"' + (Join-Path $InstallRoot 'Uninstall.cmd') + '"') -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name NoRepair -Value 0 -PropertyType DWord -Force | Out-Null

    $hookResult = $null
    if ($EnableCodex) {
        try { $hookResult = Invoke-CodexHookManager 'install' }
        catch { $hookResult = "Codex 联动暂未配置：$($_.Exception.Message)" }
    }
    return $hookResult
}

function Show-InstallDialog([string]$SourceMode, [string]$PayloadPath, [long]$DownloadBytes, [string]$Version) {
    $form = New-Window '猫咪老师桌宠安装' 390
    Add-Label $form '猫咪老师桌宠 · Windows x64' 22 20 510 32 | ForEach-Object { $_.Font = [System.Drawing.Font]::new('Microsoft YaHei UI', 14, [System.Drawing.FontStyle]::Bold) }
    Add-Label $form '安装到当前 Windows 用户，不需要管理员权限。Python 与程序一起安装，目标电脑无需预装 Python。' 22 64 510 48
    Add-Label $form ('安装位置：' + $InstallRoot) 22 116 510 26
    if ($SourceMode -eq 'Online') { $sizeText = '首次下载完整运行文件：' + (Format-Bytes $DownloadBytes) + '（之后可离线启动）' }
    else { $sizeText = '离线安装包已在本地；将安装内置 Python、程序和动画资源。' }
    if ($Version) { $sizeText += "   版本：$Version" }
    Add-Label $form $sizeText 22 145 510 30

    $codex = New-Object System.Windows.Forms.CheckBox
    $codex.Text = '启用 Codex 联动（默认勾选）'
    $codex.Checked = $true
    $codex.AutoSize = $true
    $codex.Location = New-Object System.Drawing.Point(22, 190)
    $form.Controls.Add($codex)
    Add-Label $form '安装后需要在 Codex 的 /hooks 页面审核并信任这三项 Hook。安装器不会替你信任。' 42 218 490 40

    $script:Status = Add-Label $form '准备就绪。' 22 278 510 26
    $script:Progress = New-Object System.Windows.Forms.ProgressBar
    $script:Progress.Location = New-Object System.Drawing.Point(22, 307)
    $script:Progress.Size = New-Object System.Drawing.Size(510, 18)
    $script:Progress.Style = 'Continuous'
    $form.Controls.Add($script:Progress)

    $installButton = New-Object System.Windows.Forms.Button
    $installButton.Text = '安装'
    $installButton.Location = New-Object System.Drawing.Point(352, 340)
    $installButton.Size = New-Object System.Drawing.Size(84, 32)
    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Text = '取消'
    $cancelButton.DialogResult = 'Cancel'
    $cancelButton.Location = New-Object System.Drawing.Point(446, 340)
    $cancelButton.Size = New-Object System.Drawing.Size(84, 32)
    $form.Controls.AddRange(@($installButton, $cancelButton))
    $form.CancelButton = $cancelButton

    $installButton.Add_Click({
        $installButton.Enabled = $false
        $cancelButton.Enabled = $false
        $script:Status.Text = '正在安装桌宠文件…'
        $script:Form.Refresh()
        $tempRoot = $null
        try {
            $effectivePayload = $PayloadPath
            if ($SourceMode -eq 'Online') {
                $tempRoot = Join-Path $env:TEMP ('NyankoSensei-Setup-' + [Guid]::NewGuid().ToString('N'))
                New-Item -ItemType Directory -Path $tempRoot | Out-Null
                $releaseInfo = Get-ReleaseInfo
                $zipName = $releaseInfo.Bundle.name
                $archive = Join-Path $tempRoot $zipName
                $script:Status.Text = '正在下载完整运行包；下载完成后会自动验签并安装。'
                Download-File $releaseInfo.Bundle.browser_download_url $archive
                $script:Progress.Value = 100
                $sumFile = Join-Path $tempRoot 'SHA256SUMS.txt'
                Download-File $releaseInfo.Checksums.browser_download_url $sumFile
                $sumText = Get-Content -Raw -Encoding UTF8 $sumFile
                $expected = Get-ExpectedHash $sumText $zipName
                $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToUpperInvariant()
                if ($actual -ne $expected) { throw '安装包校验失败，文件可能损坏或不完整；没有安装。' }
                $script:Status.Text = '校验通过，正在展开安装文件…'
                $extract = Join-Path $tempRoot 'expanded'
                Expand-Archive -LiteralPath $archive -DestinationPath $extract -Force
                $effectivePayload = Join-Path $extract 'payload'
            }
            $script:Status.Text = '正在复制程序和动画资源…'
            $hookResult = Install-Payload $effectivePayload ([bool]$codex.Checked)
            $script:Progress.Value = 100
            $script:Status.Text = '安装完成。'
            $form.DialogResult = 'OK'
            $form.Close()
            $message = '猫咪老师桌宠已安装。可从开始菜单打开。'
            if ($codex.Checked) {
                if (Get-Command codex -ErrorAction SilentlyContinue) {
                    $message += "`r`n`r`nCodex Hook 已写入用户配置并备份原配置。请在 Codex 中打开 /hooks，审阅并信任后才会运行。"
                } else {
                    $message += "`r`n`r`nCodex CLI 尚未检测到；Hook 配置已准备好。额度查询会在安装并登录 Codex CLI 后可用。首次启动后请在 Codex 的 /hooks 页面审核并信任。"
                }
                if ($hookResult -and $hookResult -like 'Codex 联动暂未配置：*') { $message += "`r`n`r`n$hookResult`r`n可稍后从开始菜单打开 Codex 联动管理修复。" }
            }
            [System.Windows.Forms.MessageBox]::Show($message, '安装完成', 'OK', 'Information') | Out-Null
        }
        catch {
            $script:Status.Text = '安装未完成。'
            [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, '安装失败', 'OK', 'Error') | Out-Null
            $installButton.Enabled = $true
            $cancelButton.Enabled = $true
        }
        finally {
            if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
                $safeTempRoot = [IO.Path]::GetFullPath($tempRoot)
                if ($safeTempRoot.StartsWith([IO.Path]::GetFullPath($env:TEMP), [StringComparison]::OrdinalIgnoreCase)) {
                    Remove-Item -LiteralPath $safeTempRoot -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }.GetNewClosure())
    [void]$form.ShowDialog()
}

function Show-CodexManager {
    if (-not (Test-Path -LiteralPath $InstallRoot)) { throw "桌宠未安装：$InstallRoot" }
    $form = New-Window 'Codex 联动管理' 260
    Add-Label $form 'Codex 联动' 22 18 500 32 | ForEach-Object { $_.Font = [System.Drawing.Font]::new('Microsoft YaHei UI', 14, [System.Drawing.FontStyle]::Bold) }
    Add-Label $form '安装和修复会备份 hooks.json，只管理猫咪老师自己的三项 Hook。关闭联动会移除这三项，保留其他 Hook。' 22 60 510 60
    $status = Add-Label $form '读取当前配置…' 22 124 510 28
    $repair = New-Object System.Windows.Forms.Button
    $repair.Text = '安装 / 修复'
    $repair.Location = New-Object System.Drawing.Point(260, 184)
    $repair.Size = New-Object System.Drawing.Size(120, 34)
    $disable = New-Object System.Windows.Forms.Button
    $disable.Text = '关闭联动'
    $disable.Location = New-Object System.Drawing.Point(394, 184)
    $disable.Size = New-Object System.Drawing.Size(120, 34)
    $form.Controls.AddRange(@($repair, $disable))
    $refresh = {
        $python = Join-Path $InstallRoot 'runtime\python313\python.exe'
        $manager = Join-Path $InstallRoot 'scripts\codex_hooks.py'
        $result = (& $python $manager status --root $InstallRoot | ConvertFrom-Json)
        if ($result.installed) { $status.Text = '状态：已安装三个生命周期 Hook。信任状态由 Codex 管理。' }
        else { $status.Text = '状态：尚未启用 Codex Hook。' }
    }
    try { & $refresh } catch { $status.Text = '无法读取 Hook 状态：' + $_.Exception.Message }
    $repair.Add_Click({
        try {
            Invoke-CodexHookManager 'repair' | Out-Null
            & $refresh
            [System.Windows.Forms.MessageBox]::Show('Hook 已修复并备份原配置。请到 Codex /hooks 审核并信任。', 'Codex 联动', 'OK', 'Information') | Out-Null
        } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Codex 联动', 'OK', 'Error') | Out-Null }
    }.GetNewClosure())
    $disable.Add_Click({
        try {
            Invoke-CodexHookManager 'remove' | Out-Null
            & $refresh
            [System.Windows.Forms.MessageBox]::Show('猫咪老师的 Hook 已移除，其他 Hook 保持不变。', 'Codex 联动', 'OK', 'Information') | Out-Null
        } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Codex 联动', 'OK', 'Error') | Out-Null }
    }.GetNewClosure())
    [void]$form.ShowDialog()
}

function Uninstall-Pet {
    if (-not (Test-Path -LiteralPath $InstallRoot)) { return }
    $answer = [System.Windows.Forms.MessageBox]::Show(
        "将卸载桌宠程序并移除猫咪老师自己的 Codex Hook。`r`n`r`n个人设置和日志会保留在：`r`n$UserData`r`n`r`n请先退出正在运行的桌宠。继续吗？",
        '卸载猫咪老师桌宠', 'YesNo', 'Question')
    if ($answer -ne 'Yes') { return }
    Invoke-CodexHookManager 'remove' | Out-Null
    $expectedRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\NyankoSensei')).TrimEnd('\')
    $actualRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
    if (-not [string]::Equals($actualRoot, $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw '安装目录与预期目录不一致；为防止误删，卸载已停止。'
    }
    Remove-Item -LiteralPath $expectedRoot -Recurse -Force
    Remove-Item -LiteralPath $UninstallKey -Recurse -Force -ErrorAction SilentlyContinue
    $menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\猫咪老师桌宠'
    if (Test-Path -LiteralPath $menu) { Remove-Item -LiteralPath $menu -Recurse -Force }
    [System.Windows.Forms.MessageBox]::Show('桌宠程序和自身 Hook 已卸载。个人设置与日志已保留。', '卸载完成', 'OK', 'Information') | Out-Null
}

try {
    if ($Mode -eq 'ManageCodex') { Show-CodexManager; exit 0 }
    if ($Mode -eq 'Uninstall') { Uninstall-Pet; exit 0 }

    if ($Mode -eq 'Online') {
        $releaseInfo = Get-ReleaseInfo
        $version = [string]$releaseInfo.Release.tag_name
        Show-InstallDialog 'Online' $null ([long]$releaseInfo.Bundle.size) $version
        exit 0
    }

    $offlinePayload = Join-Path $PSScriptRoot 'payload'
    if (-not (Test-Path -LiteralPath (Join-Path $offlinePayload 'NyankoSensei.exe'))) {
        throw '离线包目录不完整。请先完整解压 ZIP，再双击 Setup.cmd。'
    }
    $uncompressedSize = (Get-ChildItem -LiteralPath $offlinePayload -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $versionFile = Join-Path $offlinePayload 'version.txt'
    $offlineVersion = if (Test-Path $versionFile) { (Get-Content -Raw $versionFile).Trim() } else { '当前版本' }
    Show-InstallDialog 'Offline' $offlinePayload ([long]$uncompressedSize) $offlineVersion
}
catch {
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, '猫咪老师桌宠安装', 'OK', 'Error') | Out-Null
    exit 1
}
