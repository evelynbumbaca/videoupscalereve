"""Configuración central: rutas, límites y descubrimiento de binarios.

Todo se resuelve de forma relativa a la raíz del proyecto para que la
herramienta funcione igual en cualquier máquina y sistema operativo.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# --- Rutas base -----------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
UPLOADS_DIR = ROOT / "uploads"
OUTPUTS_DIR = ROOT / "outputs"
WORK_DIR = ROOT / "work"          # frames temporales de cada job
FRONTEND_DIR = ROOT / "frontend"

for _d in (TOOLS_DIR, UPLOADS_DIR, OUTPUTS_DIR, WORK_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Límites --------------------------------------------------------------
# Tamaño máximo de subida (MB). Los clips de IA suelen ser chicos.
MAX_UPLOAD_MB = int(os.environ.get("REVE_MAX_UPLOAD_MB", "2048"))
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".gif"}

# Cuántos jobs terminados guardamos en memoria antes de olvidarlos.
MAX_JOBS_IN_MEMORY = 50


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
