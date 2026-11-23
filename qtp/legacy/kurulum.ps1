#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallDir = $(if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $env:LOCALAPPDATA "QuickTextPaste" }),
    [switch]$StartServer
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "=== QuickTextPaste Kurulum ve Başlatma Yardımcısı ===" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$ExeNames = @("QuickTextPaste_x64_p.exe", "QuickTextPaste_p.exe", "QuickTextPaste_x64.exe", "QuickTextPaste.exe")
$ExePath = $null
foreach ($name in $ExeNames) {
    $cand = Join-Path $InstallDir $name
    if (Test-Path -LiteralPath $cand) { $ExePath = $cand; break }
}

if (-not $ExePath) {
    $is64 = [Environment]::Is64BitOperatingSystem
    $url = if ($is64) {
        "https://www.softwareok.com/Download/QuickTextPaste_x64_Portable.zip"
    } else {
        "https://www.softwareok.com/Download/QuickTextPaste_Portable.zip"
    }
    $zipFile = Join-Path $env:TEMP ("qtp_portable_" + [guid]::NewGuid().ToString("N") + ".zip")
    Write-Host "İndiriliyor: $url" -ForegroundColor Yellow
    Invoke-WebRequest -Uri $url -OutFile $zipFile -UseBasicParsing
    Expand-Archive -Path $zipFile -DestinationPath $InstallDir -Force
    Remove-Item -LiteralPath $zipFile -Force -ErrorAction SilentlyContinue

    foreach ($name in $ExeNames) {
        $cand = Join-Path $InstallDir $name
        if (Test-Path -LiteralPath $cand) { $ExePath = $cand; break }
    }
}

if (-not $ExePath) {
    throw "QuickTextPaste çalıştırılabilir dosyası kurulum dizininde bulunamadı: $InstallDir"
}

$IniPath = Join-Path (Split-Path $ExePath -Parent) "QuickTextPaste.ini"
if (-not (Test-Path -LiteralPath $IniPath)) {
    $defaultIni = "[Program]`r`nm_show_tree=1`r`nlng=21`r`nstart_tray=1`r`n[list_text]`r`n[list_order]`r`n[list_label]`r`n"
    [System.IO.File]::WriteAllBytes($IniPath, [byte[]](0xFF, 0xFE) + [System.Text.Encoding]::Unicode.GetBytes($defaultIni))
    Write-Host "Taşınabilir QuickTextPaste.ini oluşturuldu: $IniPath" -ForegroundColor Green
}

$running = Get-Process -Name "QuickTextPaste*" -ErrorAction SilentlyContinue
if (-not $running) {
    Write-Host "QuickTextPaste başlatılıyor: $ExePath -bg" -ForegroundColor Green
    Start-Process -FilePath $ExePath -ArgumentList "-bg" -WorkingDirectory (Split-Path $ExePath -Parent)
} else {
    Write-Host "QuickTextPaste zaten çalışıyor (PID: $($running.Id -join ', '))." -ForegroundColor Green
}

if ($StartServer -and (Test-Path -LiteralPath (Join-Path $InstallDir "qtp_server.py"))) {
    $parentIni = Join-Path (Split-Path $InstallDir -Parent) "QuickTextPaste.ini"
    $workTarget = if (Test-Path -LiteralPath $parentIni) { Split-Path $InstallDir -Parent } else { $InstallDir }
    python (Join-Path $InstallDir "qtp_server.py") --work-dir $workTarget --open-browser
}
