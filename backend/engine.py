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
# clave -> (nombre de modelo para -n, escala nativa, escalas soportadas de forma nativa)
# Nota: animevideov3 puede correr directo en 2x/3x/4x (más rápido); los modelos
# "x4plus" solo saben 4x, así que para 2x/3x corremos en 4x y reducimos después.
MODELS = {
    "animevideo": ("realesr-animevideov3", 4, {2, 3, 4}),  # video IA / animado
    "general": ("realesrgan-x4plus", 4, {4}),              # fotorrealista general
    "anime": ("realesrgan-x4plus-anime", 4, {4}),          # ilustración / anime estático
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
def extract_frames(
    video: Path,
    out_dir: Path,
    progress: ProgressCB | None = None,
    vf: str | None = None,
) -> int:
    """Extrae los frames del video. Si `vf` trae un filtro de ffmpeg (por
    ejemplo, un `delogo` para quitar una marca de agua), se aplica acá, antes
    del upscaling, para que la IA después suavice cualquier resto."""
    ffmpeg = config.ffmpeg_path()
    if not ffmpeg:
        raise EngineError("ffmpeg no está disponible. Ejecutá scripts/setup_tools.py.")
    out_dir.mkdir(parents=True, exist_ok=True)

    base = [ffmpeg, "-y", "-i", str(video)]
    filter_args = ["-vf", vf] if vf else []
    tail = filter_args + [str(out_dir / "frame_%08d.png")]

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


# --- Quitar marca de agua -------------------------------------------------
# Tamaño del recuadro como fracción del ancho/alto del video.
_WM_SIZES = {
    "small":  (0.14, 0.09),
    "medium": (0.20, 0.12),
    "large":  (0.28, 0.16),
}
_WM_CORNERS = {"br", "bl", "tr", "tl"}


def delogo_filter(corner: str, size: str, width: int, height: int) -> str:
    """Construye un filtro `delogo` de ffmpeg para tapar la marca de agua de
    una esquina. `delogo` reconstruye la zona a partir de los píxeles vecinos.

    corner: br (inf. der.), bl (inf. izq.), tr (sup. der.), tl (sup. izq.)
    size:   small | medium | large
    """
    if corner not in _WM_CORNERS:
        corner = "br"
    fw, fh = _WM_SIZES.get(size, _WM_SIZES["medium"])

    w = max(8, int(width * fw))
    h = max(8, int(height * fh))
    margin_x = max(2, int(width * 0.012))
    margin_y = max(2, int(height * 0.012))

    if corner in ("br", "tr"):
        x = width - w - margin_x
    else:  # bl, tl
        x = margin_x
    if corner in ("br", "bl"):
        y = height - h - margin_y
    else:  # tr, tl
        y = margin_y

    # delogo necesita que el recuadro quede al menos 1 px dentro del frame
    # (usa los píxeles de alrededor para reconstruir). Lo ajustamos por las dudas.
    x = min(max(1, x), max(1, width - w - 1))
    y = min(max(1, y), max(1, height - h - 1))
    w = max(4, min(w, width - x - 1))
    h = max(4, min(h, height - y - 1))

    return f"delogo=x={x}:y={y}:w={w}:h={h}"


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

    model_name, native, supported = MODELS.get(model_key, MODELS["animevideo"])
    model_dir = _resolve_model_dir(binary)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Optimización: si el modelo soporta la escala pedida de forma nativa
    # (p. ej. animevideov3 con 2x), la corremos directo → mucho más rápido.
    # Si no (modelos "x4plus" pidiendo 2x/3x), corremos en 4x y reducimos después:
    # más robusto y da un 2x/3x más limpio, a costa de algo más de tiempo.
    if scale in supported:
        run_scale = scale
        needs_resize = False
    else:
        run_scale = native
        needs_resize = True

    raw_dir = out_dir.parent / f"{out_dir.name}_raw" if needs_resize else out_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        binary,
        "-i", str(in_dir),
        "-o", str(raw_dir),
        "-n", model_name,
        "-s", str(run_scale),
        "-f", "png",
        # tile size y GPU: claves para no agotar la VRAM en placas de 4 GB.
        "-t", str(config.REALESRGAN_TILE_SIZE),
        "-g", str(config.REALESRGAN_GPU_ID),
    ]
    if model_dir:
        cmd += ["-m", str(model_dir)]

    # IMPORTANTE: redirigimos la salida del proceso a un ARCHIVO de log, no a una
    # tubería (PIPE). Real-ESRGAN imprime mucho texto de progreso; con PIPE, si no
    # lo vamos leyendo, el búfer del sistema se llena y el proceso queda BLOQUEADO
    # para siempre (deadlock) — sobre todo en Windows, con búferes chicos. Con un
    # archivo esto no puede pasar y el progreso lo medimos contando frames de salida.
    log_path = raw_dir.parent / "realesrgan.log"

    # Reservamos el último tramo para el reescalado final si hace falta.
    ceiling = 0.94 if needs_resize else 0.99
    with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            done = len(list(raw_dir.glob("*.png")))
            if progress and total_frames > 0:
                shown = min(done, total_frames)  # nunca mostramos "28/24"
                progress(min(ceiling, done / total_frames), f"Escalando frames ({shown}/{total_frames})")
            time.sleep(0.5)

    done = len(list(raw_dir.glob("*.png")))
    if proc.returncode != 0 or done == 0:
        raise EngineError(f"El upscaling con IA falló: {_tail_file(log_path)}")

    if needs_resize:
        if progress:
            progress(0.96, f"Ajustando a {scale}×…")
        _resize_frames_dir(raw_dir, out_dir, scale / run_scale)
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
    # Misma precaución que en el upscaling: salida a archivo para evitar deadlocks.
    log_path = out_dir.parent / "rife.log"
    with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            done = len(list(out_dir.glob("*.png")))
            if progress and expected > 0:
                shown = min(done, expected)
                progress(min(0.99, done / expected), f"Interpolando ({shown}/{expected})")
            time.sleep(0.5)
    done = len(list(out_dir.glob("*.png")))
    if proc.returncode != 0 or done == 0:
        raise EngineError(f"La interpolación falló: {_tail_file(log_path)}")
    return done


def _tail_file(path: Path, n: int = 400) -> str:
    """Devuelve el final del archivo de log (para mensajes de error legibles)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(sin detalles)"
    text = text.strip()
    return text[-n:] if text else "(sin salida del proceso)"


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
