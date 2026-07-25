@echo off
chcp 65001 >nul
title Upscale Eve - Actualizar
cd /d "%~dp0"

echo ============================================================
echo            U p s c a l e   E v e  -  Actualizar
echo ============================================================
echo.
echo Descarga la ultima version del codigo desde GitHub y la aplica
echo SIN tocar tus modelos de IA ni el entorno ya instalado.
echo.

set "ZIPURL=https://github.com/evelynbumbaca/videoupscalereve/archive/refs/heads/claude/ai-video-upscale-tool-72g2m6.zip"
set "TMP=%TEMP%\reve_update"

if exist "%TMP%" rmdir /s /q "%TMP%"

REM La app se llama ahora "Upscale Eve": quitamos el lanzador con el nombre viejo.
if exist "Iniciar ReVE Upscaler.bat" del /q "Iniciar ReVE Upscaler.bat"
mkdir "%TMP%"

echo [1/3] Descargando...
curl -L -o "%TMP%\reve.zip" "%ZIPURL%"
if errorlevel 1 (
  echo [!] No se pudo descargar. Revisa tu conexion a internet.
  pause
  exit /b 1
)

echo [2/3] Extrayendo...
tar -xf "%TMP%\reve.zip" -C "%TMP%"
if errorlevel 1 (
  echo [!] No se pudo extraer el archivo descargado.
  pause
  exit /b 1
)

set "SRC="
for /d %%D in ("%TMP%\videoupscalereve-*") do set "SRC=%%D"
if not defined SRC (
  echo [!] No se encontro el contenido descargado.
  pause
  exit /b 1
)

echo [3/3] Aplicando la actualizacion...
REM Copiamos TODO el codigo nuevo. Las carpetas tools\, uploads\, outputs\ y
REM .venv\ no vienen en la descarga, asi que quedan intactas. /C continua si
REM algun archivo esta en uso (por ejemplo, este mismo .bat mientras corre).
xcopy "%SRC%\*" "." /E /Y /C /I >nul

rmdir /s /q "%TMP%"

REM Una version nueva puede traer dependencias nuevas. Si no las instalamos,
REM la app pierde funciones en silencio (fue lo que paso con onnxruntime).
if exist ".venv\Scripts\python.exe" (
  echo.
  echo Actualizando dependencias...
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
  if errorlevel 1 echo    [!] No se pudieron actualizar (revisa tu conexion^). La app puede quedar sin alguna funcion.
)

echo.
echo ============================================================
echo  Listo! Ya tenes la ultima version, con todos los archivos.
echo  Cerra esta ventana y abri la app con "Iniciar Upscale Eve.bat".
echo ============================================================
pause
