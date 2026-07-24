# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para el portable de ReVE Upscaler.

Genera una carpeta autocontenida (onedir) con el .exe y todo lo necesario.
Los binarios de ffmpeg/Real-ESRGAN y los datos (uploads/outputs) viven JUNTO
al .exe en tiempo de ejecución; el frontend viaja empaquetado.
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [(os.path.join(project_root, "frontend"), "frontend")]
binaries = []
hiddenimports = collect_submodules("backend")

# Recolectamos las dependencias del servidor (uvicorn trae muchos submódulos).
for _pkg in ("uvicorn", "fastapi", "starlette", "anyio", "click", "h11", "sniffio"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    [os.path.join(SPECPATH, "launch_portable.py")],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["torch", "torchvision", "numpy", "PIL"],  # el complemento de IA no se empaqueta (muy pesado)
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ReVE Upscaler",
    console=True,          # mostramos la ventana con la URL / errores
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ReVE Upscaler",
)
