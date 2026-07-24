"""Configuración central: rutas, límites y descubrimiento de binarios.

Todo se resuelve de forma relativa a la raíz del proyecto para que la
herramienta funcione igual en cualquier máquina y sistema operativo.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# --- Rutas base -----------------------------------------------------------
# Soporta dos escenarios:
#  • Normal (código fuente): rutas relativas a la raíz del proyecto.
#  • Empaquetado (PyInstaller / portable): los datos escribibles viven junto
#    al .exe, y el frontend (solo lectura) viaja dentro del paquete.
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent          # carpeta del .exe (escribible)
    _BUNDLE = Path(getattr(sys, "_MEIPASS", ROOT))        # recursos empaquetados
    FRONTEND_DIR = _BUNDLE / "frontend"
else:
    ROOT = Path(__file__).resolve().parent.parent
    FRONTEND_DIR = ROOT / "frontend"

TOOLS_DIR = ROOT / "tools"
UPLOADS_DIR = ROOT / "uploads"
OUTPUTS_DIR = ROOT / "outputs"
WORK_DIR = ROOT / "work"          # frames temporales de cada job

for _d in (TOOLS_DIR, UPLOADS_DIR, OUTPUTS_DIR, WORK_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Límites --------------------------------------------------------------
# Tamaño máximo de subida (MB). Los clips de IA suelen ser chicos.
MAX_UPLOAD_MB = int(os.environ.get("REVE_MAX_UPLOAD_MB", "2048"))
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".gif"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

# Cuántos jobs terminados guardamos en memoria antes de olvidarlos.
MAX_JOBS_IN_MEMORY = 50

# --- Ajustes de Real-ESRGAN (rendimiento / VRAM) --------------------------
# Tamaño de "tile": Real-ESRGAN procesa cada frame en bloques para no llenar
# la memoria de la GPU. En placas con poca VRAM (p. ej. 4 GB, como la RTX 500
# Ada Laptop) conviene un valor moderado para evitar errores de "out of memory".
#   0 = automático · 256 = buen equilibrio para ~4 GB · bajá a 128/100 si hay OOM.
REALESRGAN_TILE_SIZE = int(os.environ.get("REVE_TILE_SIZE", "256"))

# GPU a utilizar: 0 = la primera (tu RTX). -1 fuerza el uso de CPU (muy lento).
REALESRGAN_GPU_ID = os.environ.get("REVE_GPU_ID", "0")


def _find_binary(names: list[str], subfolders: list[str] | None = None) -> str | None:
    """Busca un ejecutable primero en tools/ y luego en el PATH del sistema.

    `names` incluye variantes (con y sin .exe). `subfolders` son carpetas
    dentro de tools/ donde suelen quedar los releases descomprimidos.
    """
    candidates: list[Path] = []
    search_roots = [TOOLS_DIR]
    if subfolders:
        search_roots += [TOOLS_DIR / s for s in subfolders]

    for root in search_roots:
        if not root.exists():
            continue
        for name in names:
            candidates.append(root / name)
        # búsqueda recursiva por si el release trae subcarpetas
        for name in names:
            candidates.extend(root.rglob(name))

    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)

    # Fallback: PATH del sistema
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def ffmpeg_path() -> str | None:
    return _find_binary(["ffmpeg", "ffmpeg.exe"], subfolders=["ffmpeg"])


def ffprobe_path() -> str | None:
    return _find_binary(["ffprobe", "ffprobe.exe"], subfolders=["ffmpeg"])


def realesrgan_path() -> str | None:
    return _find_binary(
        ["realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"],
        subfolders=["realesrgan"],
    )


def rife_path() -> str | None:
    return _find_binary(
        ["rife-ncnn-vulkan", "rife-ncnn-vulkan.exe"],
        subfolders=["rife"],
    )


def lama_model_path() -> str | None:
    """Modelo LaMa (big-lama.pt) para el relleno de marca de agua con IA.
    Es un complemento opcional que se instala aparte."""
    for cand in (TOOLS_DIR / "lama" / "big-lama.pt", TOOLS_DIR / "big-lama.pt"):
        if cand.is_file():
            return str(cand)
    return None


def torch_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("torch") is not None
