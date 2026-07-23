@echo off
chcp 65001 >nul
title ReVE Upscaler
cd /d "%~dp0"

echo ============================================================
echo                    R e V E   U p s c a l e r
echo ============================================================
echo.

REM --- 1) Verificar que Python este instalado --------------------------------
python -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo [!] No se encontro Python en tu sistema.
  echo.
  echo     Instalalo desde:  https://www.python.org/downloads/
  echo     IMPORTANTE: al instalar, marca la casilla
  echo     "Add python.exe to PATH" antes de apretar "Install".
  echo.
  echo     Cuando termines, volve a hacer doble clic en este archivo.
  echo.
  pause
  exit /b 1
)

REM --- 2) Primera vez: crear entorno e instalar todo -------------------------
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Primera vez detectada. Preparando el entorno...
  echo       Esto tarda unos minutos y SOLO pasa esta vez. No cierres la ventana.
  echo.
  python -m venv .venv
  if errorlevel 1 (
    echo [!] No se pudo crear el entorno. Revisa tu instalacion de Python.
    pause
    exit /b 1
  )
  call ".venv\Scripts\activate.bat"

  echo [2/3] Instalando componentes del servidor...
  python -m pip install --upgrade pip >nul
  pip install -r requirements.txt
  if errorlevel 1 (
    echo [!] Fallo la instalacion de dependencias. Revisa tu conexion a internet.
    pause
    exit /b 1
  )

  echo.
  echo [3/3] Descargando los modelos de IA y ffmpeg...
  echo       (Real-ESRGAN + ffmpeg + RIFE. Puede tardar segun tu conexion.)
  python scripts\setup_tools.py

  echo.
  echo Instalacion completa.
  echo.
) else (
  call ".venv\Scripts\activate.bat"
)

REM --- 3) Iniciar la aplicacion ---------------------------------------------
echo Iniciando ReVE Upscaler...
echo Se abrira solo en tu navegador. Para DETENER la app, cierra esta ventana.
echo.
python run.py

echo.
echo La aplicacion se detuvo.
pause
