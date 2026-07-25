@echo off
chcp 65001 >nul
title ReVE Upscaler - Crear portable
cd /d "%~dp0"

echo ============================================================
echo      Generar version PORTABLE (para compartir con otros)
echo ============================================================
echo.
echo Crea una carpeta con "ReVE Upscaler.exe" que tus companeros pueden
echo usar SIN instalar Python ni nada: descomprimen y hacen doble clic.
echo.
echo Incluye ffmpeg y los modelos de upscaling que ya tengas descargados.
echo (El relleno de marca de agua con IA NO se incluye por su gran tamano.)
echo.
pause

if not exist ".venv\Scripts\python.exe" echo [!] Primero abri la app con "Iniciar ReVE Upscaler.bat" (crea el entorno) y ejecuta al menos una vez el setup. && echo. && pause && exit /b 1

call ".venv\Scripts\activate.bat"

echo [1/3] Preparando dependencias...
REM IMPORTANTE: si falta alguna dependencia, PyInstaller NO falla: genera un
REM portable al que le faltan funciones (por ejemplo, sin relleno con IA).
REM Por eso nos aseguramos de tenerlas todas antes de empaquetar.
python -m pip install -q -r requirements.txt
if errorlevel 1 echo [!] No se pudieron instalar las dependencias. Revisa tu conexion. && pause && exit /b 1
python -m pip install -q pyinstaller
if errorlevel 1 echo [!] No se pudo instalar PyInstaller. Revisa tu conexion. && pause && exit /b 1

echo.
echo [2/3] Generando el ejecutable (tarda unos minutos)...
REM Borramos restos de builds anteriores para que no se acumule peso.
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
pyinstaller "packaging\reve.spec" --noconfirm
if errorlevel 1 echo [!] Fallo la generacion del ejecutable. && pause && exit /b 1

echo.
echo [3/3] Copiando ffmpeg y modelos al portable...
REM Copiamos SOLO lo que el portable realmente usa:
REM  - ffmpeg/ffprobe (no ffplay: es un reproductor que la app no usa, ~130 MB)
REM  - modelos de upscaling (realesrgan, rife)
REM  - NO copiamos tools\lama (el modelo LaMa pesa ~200 MB y necesita torch,
REM    que el portable no lleva; usa MI-GAN, que ya viene incluido)
set "DEST=dist\ReVE Upscaler\tools"
mkdir "%DEST%" 2>nul

if exist "tools\ffmpeg" (
  mkdir "%DEST%\ffmpeg" 2>nul
  for /r "tools\ffmpeg" %%F in (ffmpeg.exe ffprobe.exe) do @if exist "%%F" copy /Y "%%F" "%DEST%\ffmpeg\" >nul
)
if exist "tools\realesrgan" xcopy "tools\realesrgan" "%DEST%\realesrgan" /E /I /Y >nul

REM RIFE trae ~15 modelos (448 MB) y la app usa solo rife-v4.6 (10 MB, el mas
REM nuevo). Copiamos el ejecutable, sus DLLs y ese unico modelo.
if exist "tools\rife" (
  mkdir "%DEST%\rife" 2>nul
  for /r "tools\rife" %%F in (*.exe *.dll) do @if exist "%%F" copy /Y "%%F" "%DEST%\rife\" >nul
  for /d /r "tools\rife" %%D in (rife-v4.6) do @if exist "%%D" xcopy "%%D" "%DEST%\rife\rife-v4.6" /E /I /Y >nul
)

REM Limpiamos la carpeta de trabajo temporal del empaquetado.
if exist "build" rmdir /s /q "build"

echo.
echo ============================================================
echo  LISTO! Tu portable esta en la carpeta:
echo      dist\ReVE Upscaler\
echo.
echo  Para compartirlo:
echo   1) Clic derecho sobre la carpeta "ReVE Upscaler" (dentro de dist)
echo   2) "Enviar a" -^> "Carpeta comprimida (en zip)"
echo   3) Manda ese .zip a tus companeros.
echo  Ellos lo descomprimen y abren "ReVE Upscaler.exe". Listo.
echo ============================================================
pause
