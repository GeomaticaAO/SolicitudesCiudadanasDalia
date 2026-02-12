@echo off
setlocal
cd /d "%~dp0"

set "SERVICE_ACCOUNT=tools\serviceAccountKey.json"
set "SCRIPT=tools\exportar_accesos_csv.py"
set "OUTPUT=accesos.csv"
set "INTERVALO_SEGUNDOS=300"

if not exist "%SCRIPT%" (
  echo [ERROR] No existe %SCRIPT%
  pause
  exit /b 1
)

if not exist "%SERVICE_ACCOUNT%" (
  echo [ERROR] No existe %SERVICE_ACCOUNT%
  echo Descarga la llave desde Firebase Console ^> Configuracion del proyecto ^> Cuentas de servicio.
  pause
  exit /b 1
)

if /I "%~1"=="once" goto run_once

echo [INFO] Iniciando exportacion automatica de accesos cada %INTERVALO_SEGUNDOS% segundos...
echo [INFO] Se actualizara %OUTPUT% en esta misma carpeta.
echo [INFO] Para detenerlo, cierra esta ventana o presiona CTRL + C.

goto loop

:loop
python "%SCRIPT%" --service-account "%SERVICE_ACCOUNT%" --output "%OUTPUT%"
if errorlevel 1 (
  echo [WARN] Error en la exportacion. Reintentando en %INTERVALO_SEGUNDOS% segundos...
) else (
  echo [OK] Exportacion completada: %date% %time%
)
timeout /t %INTERVALO_SEGUNDOS% /nobreak >nul
goto loop

:run_once
python "%SCRIPT%" --service-account "%SERVICE_ACCOUNT%" --output "%OUTPUT%"
if errorlevel 1 (
  echo [ERROR] No se pudo generar el CSV.
  exit /b 1
)
echo [OK] CSV generado correctamente.
exit /b 0
