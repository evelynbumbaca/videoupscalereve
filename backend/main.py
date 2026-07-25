"""Servidor web de ReVE Upscaler.

Expone una API mínima y sirve la interfaz estática. Todo corre en local:
los videos nunca salen de tu máquina.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config, hardware
from .engine import MODELS
from .jobs import run_job_async, store

app = FastAPI(title="ReVE Upscaler", version=__version__)


@app.get("/api/system")
def system() -> dict:
    from .engine import ai_inpaint_available, ai_inpaint_engine
    report = hardware.system_report()
    report["models"] = list(MODELS.keys())
    report["version"] = __version__
    report["ai_watermark"] = ai_inpaint_available()
    report["ai_watermark_engine"] = ai_inpaint_engine()
    return report


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    scale: int = Form(4),
    model: str = Form("animevideo"),
    use_ai: bool = Form(True),
    interpolate: bool = Form(False),
    interp_factor: int = Form(2),
    remove_watermark: bool = Form(False),
    wm_corner: str = Form("br"),
    wm_size: str = Form("medium"),
    wm_x: int = Form(0),
    wm_y: int = Form(0),
    wm_w: int = Form(0),
    wm_h: int = Form(0),
    wm_method: str = Form("fast"),
) -> JSONResponse:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Formato no soportado: {ext or '¿?'}. "
                                 f"Permitidos: {', '.join(sorted(config.ALLOWED_EXTENSIONS))}")
    if model not in MODELS:
        model = "animevideo"
    if scale not in (2, 3, 4):
        scale = 4
    if wm_corner not in ("br", "bl", "tr", "tl"):
        wm_corner = "br"
    if wm_size not in ("small", "medium", "large"):
        wm_size = "medium"
    if wm_method not in ("fast", "ia"):
        wm_method = "fast"

    job = store.create(
        filename=file.filename or "video",
        options={
            "scale": scale,
            "model": model,
            "use_ai": use_ai,
            "interpolate": interpolate,
            "interp_factor": interp_factor if interp_factor in (2, 4) else 2,
            "remove_watermark": remove_watermark,
            "wm_corner": wm_corner,
            "wm_size": wm_size,
            "wm_box": [max(0, wm_x), max(0, wm_y), max(0, wm_w), max(0, wm_h)],
            "wm_method": wm_method,
        },
    )

    dest = config.UPLOADS_DIR / f"{job.id}{ext}"
    await _save_upload(file, dest)
    run_job_async(job, dest)
    return JSONResponse(job.public(), status_code=202)


@app.post("/api/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    scale: int = Form(4),
    model: str = Form("general"),
    use_ai: bool = Form(True),
    remove_watermark: bool = Form(False),
    wm_corner: str = Form("br"),
    wm_size: str = Form("medium"),
    wm_x: int = Form(0),
    wm_y: int = Form(0),
    wm_w: int = Form(0),
    wm_h: int = Form(0),
    wm_method: str = Form("fast"),
) -> JSONResponse:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(400, f"Formato de imagen no soportado: {ext or '¿?'}. "
                                 f"Permitidos: {', '.join(sorted(config.ALLOWED_IMAGE_EXTENSIONS))}")
    if model not in MODELS:
        model = "general"
    if scale not in (2, 3, 4):
        scale = 4
    if wm_corner not in ("br", "bl", "tr", "tl"):
        wm_corner = "br"
    if wm_size not in ("small", "medium", "large"):
        wm_size = "medium"
    if wm_method not in ("fast", "ia"):
        wm_method = "fast"

    job = store.create(
        filename=file.filename or "imagen",
        options={
            "kind": "image",
            "scale": scale,
            "model": model,
            "use_ai": use_ai,
            "remove_watermark": remove_watermark,
            "wm_corner": wm_corner,
            "wm_size": wm_size,
            "wm_box": [max(0, wm_x), max(0, wm_y), max(0, wm_w), max(0, wm_h)],
            "wm_method": wm_method,
        },
    )

    dest = config.UPLOADS_DIR / f"{job.id}{ext}"
    await _save_upload(file, dest)
    run_job_async(job, dest)
    return JSONResponse(job.public(), status_code=202)


async def _save_upload(file: UploadFile, dest: Path) -> None:
    """Guarda la subida en disco por streaming (evita cargar todo en RAM)."""
    size = 0
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    try:
        with dest.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB.")
                f.write(chunk)
    finally:
        await file.close()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado.")
    return job.public()


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [j.public() for j in sorted(store.all(), key=lambda j: j.created_at, reverse=True)]


@app.get("/api/download/{job_id}")
def download(job_id: str) -> FileResponse:
    job = store.get(job_id)
    if not job or job.status != "done" or not job.output_name:
        raise HTTPException(404, "Todavía no hay un resultado disponible para este trabajo.")
    path = config.OUTPUTS_DIR / job.output_name
    if not path.exists():
        raise HTTPException(404, "El archivo de salida ya no está disponible.")
    media = "image/png" if path.suffix.lower() == ".png" else "video/mp4"
    return FileResponse(path, media_type=media, filename=job.output_name)


# --- Frontend estático ----------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (config.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# Servimos css/js. Debe ir al final para no pisar las rutas /api.
if config.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(config.FRONTEND_DIR)), name="static")
