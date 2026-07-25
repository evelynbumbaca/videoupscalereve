@echo off
chcp 65001 >nul
title Upscale Eve - Instalar relleno con IA
cd /d "%~dp0"

echo ============================================================
echo      Complemento OPCIONAL: relleno de marca de agua con IA
echo ============================================================
echo.
echo Agrega el borrado de marca con RELLENO INTELIGENTE (modelo LaMa),
echo ideal para videos que se ven en pantallas grandes.
echo.
echo Descarga ~300-400 MB (torch + el modelo). Es de una sola vez y puede
echo tardar VARIOS MINUTOS. No cierres la ventana aunque parezca detenida.
echo.

if not exist ".venv\Scripts\python.exe" echo [!] No encontre el entorno (.venv) en esta carpeta. Corre este archivo en la MISMA carpeta donde abris la app con "Iniciar Upscale Eve.bat" (y abri la app al menos una vez antes). && echo. && pause && exit /b 1

echo Instalando... (vas a ver el progreso de la descarga aca abajo)
echo.
".venv\Scripts\python.exe" scripts\setup_tools.py --ai-watermark

echo.
echo ============================================================
echo  Proceso terminado.
echo  - Si arriba dice "listo", ya podes usar "Relleno con IA".
echo  - Si aparecio un error, copialo y avisame.
echo ============================================================
echo.
pause
