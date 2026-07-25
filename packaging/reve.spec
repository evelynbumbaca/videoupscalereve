# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller para el portable de ReVE Upscaler.

Genera una carpeta autocontenida (onedir) con el .exe y todo lo necesario.
Los binarios de ffmpeg/Real-ESRGAN y los datos (uploads/outputs) viven JUNTO
al .exe en tiempo de ejecución; el frontend viaja empaquetado.
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(project_root, "frontend"), "frontend"),
    # Modelo de relleno con IA (MI-GAN, ~26 MB): así el portable también
    # puede borrar marcas de agua con IA, sin depender de torch.
    (os.path.join(project_root, "models"), "models"),
]
binaries = []
hiddenimports = collect_submodules("backend")

# Recolectamos las dependencias del servidor (uvicorn trae muchos submódulos)
# y el motor de inferencia liviano.
for _pkg in ("uvicorn", "fastapi", "starlette", "anyio", "click", "h11", "sniffio",
             "onnxruntime", "numpy", "PIL"):
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
    # torch (~1,1 GB) NO se empaqueta: el relleno con IA del portable usa
    # MI-GAN vía onnxruntime, que hace lo mismo con 20x menos peso.
    # 'cryptography' tampoco hace falta (servimos HTTP en localhost).
    excludes=["torch", "torchvision", "torchaudio", "scipy", "matplotlib",
              "tkinter", "test", "cryptography"],
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
