@echo off
chcp 65001 >nul
title ReVE Upscaler - Limpiar espacio
cd /d "%~dp0"

echo ============================================================
echo             Limpiar espacio de ReVE Upscaler
echo ============================================================
echo.
echo Carpeta: %CD%
echo.
echo Espacio que ocupa cada parte:
echo.

call :show "work"    "Frames temporales (basura de trabajos cortados)"
call :show "uploads" "Archivos subidos a medio procesar"
call :show "build"   "Restos del empaquetado (no sirven para nada)"
call :show "dist"    "Portable ya generado (se puede volver a crear)"
call :show "outputs" "TUS RESULTADOS (ya mejorados)"
call :show "tools"   "ffmpeg y modelos (hacen falta para funcionar)"
call :show ".venv"   "Entorno de Python (hace falta para funcionar)"

echo.
echo ------------------------------------------------------------
echo  Se puede borrar SIN PERDER NADA importante:
echo     work, uploads, build   (temporales / basura)
echo.
echo  Opcional:
echo     dist     = el portable; se puede volver a generar
echo     outputs  = tus resultados; borralos solo si ya los guardaste
echo ------------------------------------------------------------
echo.
echo  Que queres hacer?
echo     [1] Limpiar solo lo temporal   (RECOMENDADO, no perdes nada)
echo     [2] Temporal + el portable (dist)
echo     [3] Todo lo anterior + tus resultados (outputs)
echo     [4] Adelgazar modelos que la app no usa (libera ~440 MB)
echo     [0] Salir sin borrar nada
echo.
set "OPC="
set /p "OPC=Elegi una opcion y presiona Enter: "

if "%OPC%"=="0" goto :fin
if "%OPC%"=="4" goto :slim
if "%OPC%"=="1" goto :limpiar
if "%OPC%"=="2" goto :limpiar
if "%OPC%"=="3" goto :limpiar
echo.
echo Opcion no valida. No se borro nada.
goto :fin

:slim
echo.
echo  Quitando los modelos de RIFE que la app no usa...
echo  (se conserva rife-v4.6, que es el mas nuevo y el que usamos)
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\setup_tools.py --slim
) else (
  python scripts\setup_tools.py --slim
)
echo.
echo  Tambien se limpio lo temporal:
call :del "work"
call :del "uploads"
call :del "build"
echo.
echo ============================================================
echo  Listo! Volve a crear el portable con "Crear portable.bat"
echo  para que quede mas liviano tambien.
echo ============================================================
goto :fin

:limpiar
echo.
call :del "work"
call :del "uploads"
call :del "build"
if not "%OPC%"=="1" call :del "dist"
if "%OPC%"=="3" call :del "outputs"

echo.
echo ============================================================
echo  Listo! Espacio liberado.
echo  La app sigue funcionando: abrila con
echo  "Iniciar ReVE Upscaler.bat".
echo ============================================================
goto :fin

REM ---------------- utilidades ----------------
:show
if not exist %1 (
  echo    %~1 : -            %~2
  exit /b
)
for /f %%S in ('powershell -NoProfile -Command "try{'{0:N0}' -f ((Get-ChildItem -LiteralPath '%~1' -Recurse -Force -ErrorAction SilentlyContinue ^| Measure-Object -Property Length -Sum).Sum/1MB)}catch{'?'}" 2^>nul') do set "MB=%%S"
if not defined MB set "MB=?"
echo    %~1 : %MB% MB        %~2
set "MB="
exit /b

:del
if exist %1 (
  echo    Borrando %~1 ...
  rmdir /s /q %1 2>nul
)
exit /b

:fin
echo.
pause
