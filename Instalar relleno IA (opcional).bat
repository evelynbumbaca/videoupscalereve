@echo off
chcp 65001 >nul
title ReVE Upscaler - Instalar relleno con IA
cd /d "%~dp0"

echo ============================================================
echo      Complemento OPCIONAL: relleno de marca de agua con IA
echo ============================================================
echo.
echo Esto agrega el borrado de marca de agua con RELLENO INTELIGENTE
echo (modelo LaMa), ideal para videos que se ven en pantallas grandes.
echo.
echo Descarga unos ~300-400 MB (torch + el modelo). Es de una sola vez.
echo.
pause

if not exist ".venv\Scripts\python.exe" (
  echo [!] Primero instala y abri la app al menos una vez con
  echo     "Iniciar ReVE Upscaler.bat" (crea el entorno).
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo.
echo Instalando el complemento de IA...
python scripts\setup_tools.py --ai-watermark

echo.
echo ============================================================
echo  Listo. Abri la app con "Iniciar ReVE Upscaler.bat" y, al
echo  quitar la marca de agua, vas a poder elegir "Relleno con IA".
echo ============================================================
pause
