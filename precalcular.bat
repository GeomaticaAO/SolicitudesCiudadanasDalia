@echo off
setlocal
cd /d "%~dp0"

if not exist "tools\precalcular.py" (
  echo ERROR: No se encontro tools\precalcular.py
  pause
  exit /b 1
)

python tools\precalcular.py

if errorlevel 1 (
  echo.
  echo ERROR: El precalculo fallo.
  pause
  exit /b 1
)

echo.
echo OK: Archivos generados en archivos\precalculos
pause
