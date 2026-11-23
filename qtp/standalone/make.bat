@echo off
setlocal
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if "%~1"=="" goto build
if /I "%~1"=="build" goto build
if /I "%~1"=="all" goto all
if /I "%~1"=="test" goto test
if /I "%~1"=="docs" goto docs

echo Kullanim: make.bat [build^|all^|test^|docs]
exit /b 1

:build
"%PY%" -m qtp_app.build.build_windows
exit /b %ERRORLEVEL%

:all
"%PY%" -m qtp_app.build.build_windows
if errorlevel 1 exit /b %ERRORLEVEL%
echo [UYARI] Windows uzerinde qtp.bin hedefi atlandi: Linux/macOS ikili dosyasi kendi isletim sisteminde derlenmelidir.
exit /b 0

:test
"%PY%" -m pytest -q
exit /b %ERRORLEVEL%

:docs
echo docs\ altindaki Turkce Markdown belgeleri tek kaynaklidir.
exit /b 0
