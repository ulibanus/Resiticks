@echo off
setlocal
echo ============================================================
echo   Actualizador Resiticks - GitHub (ulibanus/Resiticks)
echo ============================================================

set "RESITICKS_DIR=%~dp0"
where git >nul 2>nul
if %errorlevel%==0 (
  if exist "%RESITICKS_DIR%..\.git" (
    echo Repositorio Git detectado. Ejecutando git pull...
    git -C "%RESITICKS_DIR%.." pull --ff-only
    echo Actualizacion completada.
    pause
    exit /b 0
  )
)

echo Descargando ultima version desde GitHub via PowerShell...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$tmp = Join-Path $env:TEMP 'resiticks_upd'; " ^
  "if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }; " ^
  "New-Item -ItemType Directory -Path $tmp | Out-Null; " ^
  "$zip = Join-Path $tmp 'main.zip'; " ^
  "Invoke-WebRequest -Uri 'https://github.com/ulibanus/Resiticks/archive/refs/heads/main.zip' -OutFile $zip; " ^
  "Expand-Archive -Path $zip -DestinationPath $tmp -Force; " ^
  "$src = Join-Path $tmp 'Resiticks-main\Resiticks'; " ^
  "Copy-Item -Path (Join-Path $src 'profiles\*.json') -Destination '%RESITICKS_DIR%profiles\' -Force; " ^
  "Copy-Item -Path (Join-Path $src '2_Windows\*') -Destination '%RESITICKS_DIR%2_Windows\' -Force; " ^
  "Remove-Item -Recurse -Force $tmp"

echo Actualizacion finalizada.
pause
