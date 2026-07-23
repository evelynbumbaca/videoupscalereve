@echo off
chcp 65001 >nul
title ReVE Upscaler - Actualizar
cd /d "%~dp0"

echo ============================================================
echo            R e V E   U p s c a l e r  -  Actualizar
echo ============================================================
echo.
echo Esto descarga la ultima version del codigo desde GitHub y la
echo aplica SIN tocar tus modelos de IA ni el entorno ya instalado.
echo.

set "ZIPURL=https://github.com/evelynbumbaca/videoupscalereve/archive/refs/heads/claude/ai-video-upscale-tool-72g2m6.zip"
set "TMP=%TEMP%\reve_update"

if exist "%TMP%" rmdir /s /q "%TMP%"
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
xcopy "%SRC%\backend"  "backend"  /E /Y /I >nul
xcopy "%SRC%\frontend" "frontend" /E /Y /I >nul
xcopy "%SRC%\scripts"  "scripts"  /E /Y /I >nul
copy /Y "%SRC%\run.py"            "run.py"            >nul
copy /Y "%SRC%\requirements.txt"  "requirements.txt" >nul
copy /Y "%SRC%\Iniciar ReVE Upscaler.bat" "Iniciar ReVE Upscaler.bat" >nul
copy /Y "%SRC%\README.md"        "README.md"         >nul
copy /Y "%SRC%\GUIA_WINDOWS.md"  "GUIA_WINDOWS.md"   >nul

rmdir /s /q "%TMP%"

echo.
echo ============================================================
echo  Listo! Ya tenes la ultima version.
echo  Cerra esta ventana y abri la app con "Iniciar ReVE Upscaler.bat".
echo ============================================================
pause
