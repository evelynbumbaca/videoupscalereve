"""Motor de procesamiento de video.

Envuelve ffmpeg/ffprobe y realesrgan-ncnn-vulkan. Cada paso reporta
progreso a través de un callback para que la UI muestre una barra real.

El diseño evita cargar todo el video en memoria: se trabaja por frames
en disco, que es como operan las herramientas de upscaling serias.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config

# Firma del callback de progreso: (fraccion_0_a_1, mensaje)
ProgressCB = Callable[[float, str], None]


class EngineError(RuntimeError):
    """Error controlado del pipeline, con mensaje apto para mostrar al usuario."""


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float
    n_frames: int
    has_audio: bool


# Modelos de Real-ESRGAN incluidos en el release ncnn-vulkan.
# clave -> (nombre de modelo para -n, escala nativa)
MODELS = {
    "animevideo": ("realesr-animevideov3", 4),   # ideal para video generado por IA / animado
    "general": ("realesrgan-x4plus", 4),          # fotorrealista general
    "anime": ("realesrgan-x4plus-anime", 4),      # ilustración / anime estático
}


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# --- Sondeo del video -----------------------------------------------------
def probe(video: Path) -> VideoInfo:
    ffprobe = config.ffprobe_path()
    if not ffprobe:
        raise EngineError("ffprobe no está disponible. Ejecutá scripts/setup_tools.py.")

    cmd = [
        ffprobe, "-v", "error",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(video),
    ]
    res = _run(cmd)
    if res.returncode != 0:
        raise EngineError(f"No se pudo leer el video: {res.stderr.strip()[:400]}")

    data = json.loads(res.stdout)
    vstream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if vstream is None:
        raise EngineError("El archivo no contiene un stream de video válido.")

    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))

    # fps puede venir como "30000/1001"
    fps = _parse_fraction(vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0/1")
    if fps <= 0:
        fps = 30.0

    duration = float(data.get("format", {}).get("duration") or vstream.get("duration") or 0.0)

    n_frames = int(vstream.get("nb_frames") or 0)
    if n_frames <= 0 and duration > 0:
        n_frames = max(1, round(duration * fps))

    return VideoInfo(
        width=int(vstream.get("width", 0)),
        height=int(vstream.get("height", 0)),
        fps=fps,
        duration=duration,
        n_frames=max(1, n_frames),
        has_audio=has_audio,
    )


def _parse_fraction(text: str) -> float:
    try:
        if "/" in text:
            num, den = text.split("/")
            den = float(den)
            return float(num) / den if den else 0.0
        return float(text)
    except (ValueError, ZeroDivisionError):
        return 0.0


# --- Extracción -----------------------------------------------------------
def extract_frames(video: Path, out_dir: Path, progress: ProgressCB | None = None) -> int:
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        raise EngineError("ffmpeg no está disponible. Ejecutá scripts/setup_tools.py.")
    out_dir.mkdir(parents=True, exist_ok=True)

    base = [ffmpeg, "-y", "-i", str(video)]
    tail = [str(out_dir / "frame_%08d.png")]

    # La opción para "extraer todos los frames sin duplicar" cambió entre
    # versiones de ffmpeg:
    #   • ffmpeg >= 5.1 (y las nuevas 8.x):  -fps_mode passthrough
    #   • ffmpeg antiguos:                   -vsync 0
    # Probamos en orden y, si una opción no existe, pasamos a la siguiente.
    # Así funciona con cualquier build de ffmpeg sin que tengas que hacer nada.
    sync_variants = [["-fps_mode", "passthrough"], ["-vsync", "0"], []]

    last_err = ""
    for sync in sync_variants:
        # Limpiamos cualquier salida parcial de un intento anterior.
        for f in out_dir.glob("frame_*.png"):
            f.unlink(missing_ok=True)

        res = _run(base + sync + tail)
        if res.returncode == 0:
            count = len(list(out_dir.glob("frame_*.png")))
            if count > 0:
                if progress:
                    progress(1.0, f"{count} frames extraídos")
                return count
            last_err = "no se extrajo ningún frame del video"
            continue

        err = (res.stderr or "").strip()
        last_err = err[-400:]
        # Solo reintentamos si el fallo fue por una opción inexistente.
        low = err.lower()
        if "unrecognized option" in low or "option not found" in low:
            continue
        # Cualquier otro error (archivo dañado, formato raro): no insistimos.
        break

    raise EngineError(f"Falló la extracción de frames: {last_err}")


def extract_audio(video: Path, out_path: Path) -> bool:
    """Extrae el audio a AAC. Devuelve True si había audio."""
    ffmpeg = config.ffmpeg_path()
    cmd = [
        ffmpeg, "-y", "-i", str(video),
        "-vn", "-acodec", "aac", "-b:a", "192k",
        str(out_path),
    ]
    res = _run(cmd)
    return res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0


# --- Upscaling con IA -----------------------------------------------------
def upscale_frames_ai(
    in_dir: Path,
    out_dir: Path,
    model_key: str,
    scale: int,
    total_frames: int,
    progress: ProgressCB | None = None,
) -> None:
    binary = config.realesrgan_path()
    if not binary:
        raise EngineError("realesrgan-ncnn-vulkan no está instalado.")

    model_name, native = MODELS.get(model_key, MODELS["animevideo"])
    model_dir = _resolve_model_dir(binary)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Real-ESRGAN siempre corre a la escala nativa del modelo (todos son x4).
    # Si el usuario pidió 2x o 3x, escalamos con IA a 4x y luego reducimos:
    # es más robusto (evita errores de -s no soportado) y da un 2x/3x más limpio.
    needs_resize = scale != native
    raw_dir = out_dir.parent / f"{out_dir.name}_raw" if needs_resize else out_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        binary,
        "-i", str(in_dir),
        "-o", str(raw_dir),
        "-n", model_name,
        "-s", str(native),
        "-f", "png",
        # tile size y GPU: claves para no agotar la VRAM en placas de 4 GB.
        "-t", str(config.REALESRGAN_TILE_SIZE),
        "-g", str(config.REALESRGAN_GPU_ID),
    ]
    if model_dir:
        cmd += ["-m", str(model_dir)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Progreso por conteo de archivos de salida (robusto entre versiones).
    # Reservamos el último 5% para el reescalado final si hace falta.
    ceiling = 0.94 if needs_resize else 0.99
    while proc.poll() is None:
        done = len(list(raw_dir.glob("*.png")))
        if progress and total_frames > 0:
            progress(min(ceiling, done / total_frames), f"Escalando frames ({done}/{total_frames})")
        time.sleep(0.5)

    _, stderr = proc.communicate()
    done = len(list(raw_dir.glob("*.png")))
    if proc.returncode != 0 or done == 0:
        raise EngineError(f"El upscaling con IA falló: {(stderr or '').strip()[-400:]}")

    if needs_resize:
        if progress:
            progress(0.96, f"Ajustando a {scale}×…")
        _resize_frames_dir(raw_dir, out_dir, scale / native)
        import shutil as _sh
        _sh.rmtree(raw_dir, ignore_errors=True)

    if progress:
        progress(1.0, f"{done} frames escalados")


def _resize_frames_dir(src_dir: Path, dst_dir: Path, factor: float) -> None:
    """Reescala una secuencia de frames por un factor (con lanczos)."""
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        raise EngineError("ffmpeg no está disponible para el reescalado.")
    dst_dir.mkdir(parents=True, exist_ok=True)
    pattern = _frame_pattern(src_dir)
    cmd = [
        ffmpeg, "-y",
        "-i", str(src_dir / pattern),
        "-vf", f"scale=iw*{factor}:ih*{factor}:flags=lanczos",
        str(dst_dir / pattern),
    ]
    res = _run(cmd)
    if res.returncode != 0:
        raise EngineError(f"Falló el ajuste de escala: {res.stderr.strip()[-400:]}")


def _resolve_model_dir(binary: str) -> Path | None:
    """El release trae una carpeta `models` junto al binario."""
    base = Path(binary).parent
    for cand in (base / "models", base):
        if cand.is_dir() and any(cand.glob("*.param")):
            return cand
    return None


# --- Upscaling de respaldo (sin IA) --------------------------------------
def upscale_frames_fallback(
    in_dir: Path,
    out_dir: Path,
    scale: int,
    info: VideoInfo,
    progress: ProgressCB | None = None,
) -> None:
    """Escala con el filtro lanczos de ffmpeg. No es IA, pero permite probar
    el flujo completo sin descargar los modelos. Se marca como 'respaldo'."""
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        raise EngineError("ffmpeg no está disponible.")
    out_dir.mkdir(parents=True, exist_ok=True)

    target_w = info.width * scale
    target_h = info.height * scale
    cmd = [
        ffmpeg, "-y",
        "-i", str(in_dir / "frame_%08d.png"),
        "-vf", f"scale={target_w}:{target_h}:flags=lanczos",
        str(out_dir / "frame_%08d.png"),
    ]
    if progress:
        progress(0.1, "Escalando (modo respaldo, sin IA)…")
    res = _run(cmd)
    if res.returncode != 0:
        raise EngineError(f"Falló el escalado de respaldo: {res.stderr.strip()[-400:]}")
    if progress:
        progress(1.0, "Frames escalados (respaldo)")


# --- Interpolación de frames (opcional) ----------------------------------
def interpolate_frames(
    in_dir: Path,
    out_dir: Path,
    factor: int,
    total_frames: int,
    progress: ProgressCB | None = None,
) -> int:
    """Duplica/cuadruplica los frames con RIFE para suavizar el movimiento.
    Devuelve el nuevo total de frames."""
    binary = config.rife_path()
    if not binary:
        raise EngineError("rife-ncnn-vulkan no está instalado.")
    out_dir.mkdir(parents=True, exist_ok=True)

    expected = total_frames * factor
    cmd = [
        binary, "-i", str(in_dir), "-o", str(out_dir), "-n", str(expected),
        "-g", str(config.REALESRGAN_GPU_ID),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while proc.poll() is None:
        done = len(list(out_dir.glob("*.png")))
        if progress and expected > 0:
            progress(min(0.99, done / expected), f"Interpolando ({done}/{expected})")
        time.sleep(0.5)
    _, stderr = proc.communicate()
    done = len(list(out_dir.glob("*.png")))
    if proc.returncode != 0 or done == 0:
        raise EngineError(f"La interpolación falló: {(stderr or '').strip()[-400:]}")
    return done


# --- Reensamblado ---------------------------------------------------------
def assemble(
    frames_dir: Path,
    output: Path,
    fps: float,
    audio: Path | None,
    crf: int = 17,
    progress: ProgressCB | None = None,
) -> None:
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        raise EngineError("ffmpeg no está disponible.")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Los frames pueden llamarse frame_00000001.png o 00000001.png según la herramienta.
    pattern = _frame_pattern(frames_dir)

    cmd = [
        ffmpeg, "-y",
        "-framerate", f"{fps:.6f}",
        "-i", str(frames_dir / pattern),
    ]
    if audio and audio.exists():
        cmd += ["-i", str(audio)]

    cmd += [
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        # yuv420p exige dimensiones pares; forzamos por si el reescalado dio impar.
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-movflags", "+faststart",
    ]
    if audio and audio.exists():
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]

    cmd.append(str(output))

    if progress:
        progress(0.2, "Codificando el video final…")
    res = _run(cmd)
    if res.returncode != 0:
        raise EngineError(f"Falló la codificación final: {res.stderr.strip()[-400:]}")
    if not output.exists() or output.stat().st_size == 0:
        raise EngineError("El video final se generó vacío.")
    if progress:
        progress(1.0, "Video listo")


def _frame_pattern(frames_dir: Path) -> str:
    sample = next(iter(sorted(frames_dir.glob("*.png"))), None)
    if sample is None:
        raise EngineError("No hay frames para reensamblar.")
    name = sample.name
    if name.startswith("frame_"):
        return "frame_%08d.png"
    # RIFE suele emitir 00000001.png
    digits = len(name.split(".")[0])
    return f"%0{digits}d.png"
