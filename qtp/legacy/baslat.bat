@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul
title QTP Full-Stack Baslatici (QuickTextPaste + Web/API + Python)
set "LEGACY_DIR=%~dp0"
for %%I in ("%~dp0..") do set "WORK_DIR=%%~fI"
cd /d "%LEGACY_DIR%"

set "PY_CMD="
where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
  where py >nul 2>nul && set "PY_CMD=py -3"
)
if not defined PY_CMD (
  where python3 >nul 2>nul && set "PY_CMD=python3"
)

if not defined PY_CMD (
  echo [HATA] Python 3 bulunamadi!
  echo Lutfen https://www.python.org/downloads/ adresinden Python 3 yukleyin veya:
  echo   winget install Python.Python.3.12
  pause
  exit /b 1
)

if /i "%~1"=="gui" (
  echo [QTP] QuickTextPaste kontrol ediliyor ve Python masaustu arayuzu aciliyor...
  %PY_CMD% "%LEGACY_DIR%qtp_server.py" --work-dir "%WORK_DIR%" --install-qtp >nul 2>nul
  %PY_CMD% "%LEGACY_DIR%qtp_server.py" --work-dir "%WORK_DIR%" --start-qtp >nul 2>nul
  %PY_CMD% "%LEGACY_DIR%qtp_manager.py"
  exit /b %errorlevel%
)

if /i "%~1"=="qtp" (
  echo [QTP] QuickTextPaste kurulum ve baslatma dogrulaniyor...
  %PY_CMD% "%LEGACY_DIR%qtp_server.py" --work-dir "%WORK_DIR%" --install-qtp
  %PY_CMD% "%LEGACY_DIR%qtp_server.py" --work-dir "%WORK_DIR%" --start-qtp
  exit /b %errorlevel%
)

if /i "%~1"=="check" (
  %PY_CMD% "%LEGACY_DIR%qtp_server.py" --work-dir "%WORK_DIR%" --status
  exit /b %errorlevel%
)

echo ==============================================================
echo  QTP ^& Hazir Cevaplar Full-Stack Paneli Baslatiliyor...
echo  1) QuickTextPaste kontrol edilir / eksikse kurulur ve baslatilir
echo  2) data.json ^<-> QuickTextPaste.ini disk senkronizasyonu acilir
echo  3) Yerel Web PWA arayuzu acilir: http://127.0.0.1:8765/
echo ==============================================================
%PY_CMD% "%LEGACY_DIR%qtp_server.py" --work-dir "%WORK_DIR%" --ensure-qtp --open-browser
if %errorlevel% neq 0 (
  echo.
  echo [UYARI] Sunucu hata koduyla kapandi: %errorlevel%
  pause
)
