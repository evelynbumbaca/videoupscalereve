"""Detección de hardware y de las herramientas disponibles.

Sirve para mostrar en la UI qué está listo y para recomendar ajustes
(por ejemplo, avisar si va a correr por CPU y será lento).
"""
from __future__ import annotations

import platform
import shutil
import subprocess

from . import config


def _detect_gpu() -> dict:
    system = platform.system()
    machine = platform.machine().lower()

    # Apple Silicon
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return {"vendor": "apple", "name": "Apple Silicon (GPU integrada)", "accelerated": True}

    # NVIDIA vía nvidia-smi
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            name = out.stdout.strip().splitlines()[0] if out.stdout.strip() else "NVIDIA GPU"
            return {"vendor": "nvidia", "name": name, "accelerated": True}
        except Exception:
            return {"vendor": "nvidia", "name": "NVIDIA GPU", "accelerated": True}

    # AMD (Linux) — heurística simple
    if shutil.which("rocminfo") or shutil.which("rocm-smi"):
        return {"vendor": "amd", "name": "AMD GPU (ROCm)", "accelerated": True}

    return {
        "vendor": "unknown",
        "name": "GPU no detectada (se usará CPU o Vulkan genérico)",
        "accelerated": False,
    }


def system_report() -> dict:
    """Resumen del entorno para el endpoint /api/system."""
    gpu = _detect_gpu()
    ffmpeg = config.ffmpeg_path()
    realesrgan = config.realesrgan_path()
    rife = config.rife_path()

    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "gpu": gpu,
        "tools": {
            "ffmpeg": bool(ffmpeg),
            "ffprobe": bool(config.ffprobe_path()),
            "realesrgan": bool(realesrgan),
            "rife": bool(rife),
        },
        # La app puede operar en modo "fallback" (solo ffmpeg) o "ia" (realesrgan).
        "mode": "ia" if realesrgan else ("fallback" if ffmpeg else "none"),
    }
