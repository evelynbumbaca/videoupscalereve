"""Pipeline completo: video de entrada -> video escalado.

Orquesta las etapas del motor y reparte el progreso global (0..1) entre
ellas con pesos, de modo que la barra de la UI avance de forma coherente.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from . import config, engine
from .jobs import Job


# Pesos relativos de cada etapa para el progreso global.
# Se normalizan según qué etapas estén activas en cada job.
_STAGE_WEIGHTS = {
    "probe": 0.02,
    "extract": 0.08,
    "inpaint": 0.30,
    "upscale": 0.60,
    "interpolate": 0.15,
    "assemble": 0.15,
}


def process(job: Job, input_path: Path) -> Path:
    opts = job.options
    scale = int(opts.get("scale", 4))
    model_key = opts.get("model", "animevideo")
    use_ai = bool(opts.get("use_ai", True)) and config.realesrgan_path() is not None
    interpolate = bool(opts.get("interpolate", False)) and config.rife_path() is not None
    interp_factor = int(opts.get("interp_factor", 2))
    remove_wm = bool(opts.get("remove_watermark", False))
    wm_corner = opts.get("wm_corner", "br")
    wm_size = opts.get("wm_size", "medium")
    wm_box = opts.get("wm_box", [0, 0, 0, 0])
    wm_method = opts.get("wm_method", "fast")  # fast (delogo) | ia (relleno LaMa)
    bx, by, bw, bh = (list(wm_box) + [0, 0, 0, 0])[:4]
    has_box = bw > 0 and bh > 0
    # El relleno con IA requiere el complemento instalado y un recuadro marcado.
    use_ia_wm = remove_wm and wm_method == "ia" and has_box and engine.lama_available()

    work = config.WORK_DIR / job.id
    frames_in = work / "in"
    frames_up = work / "up"
    frames_final = work / "final"
    audio_path = work / "audio.m4a"
    work.mkdir(parents=True, exist_ok=True)

    # Qué etapas correrán (para normalizar los pesos del progreso).
    active = ["probe", "extract"]
    if use_ia_wm:
        active.append("inpaint")
    active.append("upscale")
    if interpolate:
        active.append("interpolate")
    active.append("assemble")
    total_weight = sum(_STAGE_WEIGHTS[s] for s in active)

    base = {"acc": 0.0}  # progreso acumulado de etapas ya completadas

    def stage_progress(stage: str, label: str):
        weight = _STAGE_WEIGHTS[stage] / total_weight

        def cb(frac: float, msg: str) -> None:
            job.stage = label
            job.message = msg
            job.progress = round(base["acc"] + weight * max(0.0, min(1.0, frac)), 4)

        return cb, weight

    try:
        # 1) Sondeo
        cb, w = stage_progress("probe", "Analizando el video")
        cb(0.5, "Leyendo metadatos…")
        info = engine.probe(input_path)
        cb(1.0, f"{info.width}x{info.height} · {info.fps:.2f} fps · {info.n_frames} frames")
        base["acc"] += w

        # 2) Extracción de frames + audio.
        # Si se quita la marca con el modo rápido (delogo), se aplica acá durante
        # la extracción. Si es con IA (LaMa), se extrae limpio y se rellena aparte.
        wm_filter = None
        if remove_wm and not use_ia_wm:
            if has_box:
                wm_filter = engine.delogo_filter_box(bx, by, bw, bh, info.width, info.height)
            else:
                wm_filter = engine.delogo_filter(wm_corner, wm_size, info.width, info.height)
        extract_label = "Extrayendo frames y quitando marca" if wm_filter else "Extrayendo frames"
        cb, w = stage_progress("extract", extract_label)
        n_frames = engine.extract_frames(input_path, frames_in, progress=cb, vf=wm_filter)
        has_audio = engine.extract_audio(input_path, audio_path) if info.has_audio else False
        base["acc"] += w

        # 2.5) Relleno de marca de agua con IA (LaMa), antes del upscaling.
        if use_ia_wm:
            cb, w = stage_progress("inpaint", "Borrando marca con IA")
            cb(0.0, "Cargando modelo de IA… (la primera vez tarda unos segundos)")
            engine.inpaint_frames_lama(frames_in, (bx, by, bw, bh), n_frames, progress=cb)
            base["acc"] += w

        # 3) Upscaling
        if use_ai:
            cb, w = stage_progress("upscale", "Escalando con IA")
            engine.upscale_frames_ai(frames_in, frames_up, model_key, scale, n_frames, progress=cb)
        else:
            cb, w = stage_progress("upscale", "Escalando (modo respaldo)")
            engine.upscale_frames_fallback(frames_in, frames_up, scale, info, progress=cb)
        base["acc"] += w

        current_frames_dir = frames_up
        out_fps = info.fps

        # 4) Interpolación opcional
        if interpolate:
            cb, w = stage_progress("interpolate", "Suavizando movimiento")
            engine.interpolate_frames(frames_up, frames_final, interp_factor, n_frames, progress=cb)
            current_frames_dir = frames_final
            out_fps = info.fps * interp_factor
            base["acc"] += w

        # 5) Reensamblado + audio
        cb, w = stage_progress("assemble", "Codificando video final")
        output = _output_path(job.filename, scale, use_ai)
        engine.assemble(
            current_frames_dir,
            output,
            fps=out_fps,
            audio=audio_path if has_audio else None,
            progress=cb,
        )
        base["acc"] += w

        return output
    finally:
        # limpieza de frames temporales (pueden ser muchos GB)
        _safe_rmtree(work)


def process_image(job: Job, input_path: Path) -> Path:
    """Pipeline para una sola imagen: (quitar marca) -> upscale -> PNG.
    Reutiliza el mismo motor que el video, tratando la imagen como 1 frame."""
    opts = job.options
    scale = int(opts.get("scale", 4))
    model_key = opts.get("model", "general")
    use_ai = bool(opts.get("use_ai", True)) and config.realesrgan_path() is not None
    remove_wm = bool(opts.get("remove_watermark", False))
    wm_corner = opts.get("wm_corner", "br")
    wm_size = opts.get("wm_size", "medium")
    wm_box = opts.get("wm_box", [0, 0, 0, 0])
    wm_method = opts.get("wm_method", "fast")
    bx, by, bw, bh = (list(wm_box) + [0, 0, 0, 0])[:4]
    has_box = bw > 0 and bh > 0
    use_ia_wm = remove_wm and wm_method == "ia" and has_box and engine.lama_available()

    work = config.WORK_DIR / job.id
    frames_in = work / "in"
    frames_up = work / "up"
    work.mkdir(parents=True, exist_ok=True)

    def set_stage(stage: str, frac: float, msg: str = "") -> None:
        job.stage = stage
        job.message = msg
        job.progress = round(max(0.0, min(1.0, frac)), 4)

    try:
        set_stage("Analizando la imagen", 0.05, "Leyendo…")
        info = engine.probe(input_path)

        # Preparación (+ quitar marca con el modo rápido si corresponde).
        wm_filter = None
        if remove_wm and not use_ia_wm:
            if has_box:
                wm_filter = engine.delogo_filter_box(bx, by, bw, bh, info.width, info.height)
            else:
                wm_filter = engine.delogo_filter(wm_corner, wm_size, info.width, info.height)
        set_stage("Preparando la imagen", 0.12)
        engine.extract_frames(input_path, frames_in, vf=wm_filter)

        # Relleno de marca con IA (LaMa).
        if use_ia_wm:
            set_stage("Cargando modelo de IA…", 0.14, "La primera vez tarda unos segundos")
            engine.inpaint_frames_lama(
                frames_in, (bx, by, bw, bh), 1,
                progress=lambda f, m: set_stage("Borrando marca con IA", 0.15 + 0.30 * f, m),
            )

        # Upscaling.
        if use_ai:
            engine.upscale_frames_ai(
                frames_in, frames_up, model_key, scale, 1,
                progress=lambda f, m: set_stage("Escalando con IA", 0.5 + 0.45 * f, m),
            )
        else:
            engine.upscale_frames_fallback(
                frames_in, frames_up, scale, info,
                progress=lambda f, m: set_stage("Escalando (modo respaldo)", 0.5 + 0.45 * f, m),
            )

        out_frame = next(iter(sorted(frames_up.glob("*.png"))), None)
        if out_frame is None:
            raise engine.EngineError("No se generó la imagen de salida.")
        output = _output_path(job.filename, scale, use_ai, ext="png")
        shutil.copyfile(out_frame, output)
        set_stage("Completado", 1.0, "¡Imagen lista!")
        return output
    finally:
        _safe_rmtree(work)


def _output_path(original: str, scale: int, use_ai: bool, ext: str = "mp4") -> Path:
    stem = Path(original).stem or ("imagen" if ext == "png" else "video")
    tag = f"x{scale}" + ("" if use_ai else "-respaldo")
    ts = time.strftime("%Y%m%d-%H%M%S")
    name = f"{stem}_{tag}_{ts}.{ext}"
    # sanea el nombre
    name = "".join(c for c in name if c.isalnum() or c in "._-")
    return config.OUTPUTS_DIR / name


def _safe_rmtree(path: Path) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass
