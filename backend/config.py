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


# Caché de rutas ya resueltas: la búsqueda recorre tools/ recursivamente y se
# llama en cada request; con ffmpeg instalado (cientos de archivos) eso se nota.
_BINARY_CACHE: dict[str, str | None] = {}


def clear_binary_cache() -> None:
    """Olvida las rutas cacheadas (tras instalar herramientas nuevas)."""
    _BINARY_CACHE.clear()


def cleanup_temp_dirs() -> int:
    """Borra los temporales huérfanos al arrancar y devuelve los MB liberados.

    Los trabajos viven solo en memoria: si la app se cerró a mitad de un
    procesamiento, quedaron frames sueltos en work/ y el archivo original en
    uploads/. Al iniciar no hay ningún trabajo en curso, así que todo lo que
    haya ahí es basura segura de borrar (los resultados van a outputs/, que
    no se toca).
    """
    freed = 0
    for base in (WORK_DIR, UPLOADS_DIR):
        if not base.is_dir():
            continue
        for item in base.iterdir():
            try:
                if item.is_dir():
                    freed += sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    freed += item.stat().st_size
                    item.unlink(missing_ok=True)
            except OSError:
                pass  # si algo está en uso, lo dejamos para la próxima
    return round(freed / (1024 * 1024))


def _find_binary(names: list[str], subfolders: list[str] | None = None) -> str | None:
    """Busca un ejecutable primero en tools/ y luego en el PATH del sistema.

    `names` incluye variantes (con y sin .exe). `subfolders` son carpetas
    dentro de tools/ donde suelen quedar los releases descomprimidos.
    El resultado se cachea (incluso cuando no se encuentra nada).
    """
    cache_key = "|".join(names)
    if cache_key in _BINARY_CACHE:
        found = _BINARY_CACHE[cache_key]
        # Revalidamos barato: si el archivo desapareció, volvemos a buscar.
        if found is None or Path(found).is_file():
            return found

    result = _search_binary(names, subfolders)
    _BINARY_CACHE[cache_key] = result
    return result


def _search_binary(names: list[str], subfolders: list[str] | None = None) -> str | None:
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


# Modelo de RIFE que usamos. El binario trae ~15 modelos (448 MB) y por defecto
# usa rife-v2.3, que es viejo. rife-v4.6 es el más nuevo y mejor, y pesa 10 MB:
# lo elegimos explícitamente y así el resto ni hace falta distribuirlo.
RIFE_MODEL_NAME = "rife-v4.6"


def rife_model_dir() -> str | None:
    """Carpeta del modelo rife-v4.6, si está disponible."""
    binary = rife_path()
    if not binary:
        return None
    base = Path(binary).parent
    for cand in (base / RIFE_MODEL_NAME, base / "models" / RIFE_MODEL_NAME):
        if cand.is_dir():
            return str(cand)
    # por si el release quedó en una subcarpeta
    for found in base.rglob(RIFE_MODEL_NAME):
        if found.is_dir():
            return str(found)
    return None


def lama_model_path() -> str | None:
    """Modelo LaMa (big-lama.pt): relleno de marca de agua de máxima calidad.
    Complemento opcional y pesado (requiere torch). Si no está, se usa MI-GAN."""
    for cand in (TOOLS_DIR / "lama" / "big-lama.pt", TOOLS_DIR / "big-lama.pt"):
        if cand.is_file():
            return str(cand)
    return None


def migan_model_path() -> str | None:
    """Modelo MI-GAN en ONNX: relleno de marca de agua liviano (~26 MB).
    Viene incluido con la app, así que el portable también lo lleva."""
    roots = [ROOT / "models"]
    if getattr(sys, "frozen", False):
        roots.insert(0, Path(getattr(sys, "_MEIPASS", ROOT)) / "models")
    for root in roots:
        cand = root / "migan.onnx"
        if cand.is_file():
            return str(cand)
    return None


def torch_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("torch") is not None


def onnxruntime_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("onnxruntime") is not None
