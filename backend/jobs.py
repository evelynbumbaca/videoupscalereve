"""Registro de trabajos en memoria y ejecución en segundo plano.

Cada job corre en su propio hilo para no bloquear el servidor web.
La UI consulta el estado por polling en /api/jobs/{id}.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from . import config


@dataclass
class Job:
    id: str
    filename: str
    status: str = "queued"          # queued | running | done | error
    stage: str = "En cola"          # texto legible del paso actual
    progress: float = 0.0           # 0..1 global
    message: str = ""
    output_name: str | None = None  # nombre del archivo en outputs/
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    options: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("options", None)
        d["download_url"] = f"/api/download/{self.id}" if self.status == "done" else None
        return d


class JobStore:
    def __init__(self) -> None:
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._lock = threading.Lock()

    def create(self, filename: str, options: dict) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], filename=filename, options=options)
        with self._lock:
            self._jobs[job.id] = job
            self._evict_if_needed()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def _evict_if_needed(self) -> None:
        while len(self._jobs) > config.MAX_JOBS_IN_MEMORY:
            _id, old = self._jobs.popitem(last=False)
            # limpieza best-effort del output viejo
            if old.output_name:
                try:
                    (config.OUTPUTS_DIR / old.output_name).unlink(missing_ok=True)
                except OSError:
                    pass


store = JobStore()


# --- Ejecución en segundo plano ------------------------------------------
def run_job_async(job: Job, input_path: Path) -> None:
    """Lanza el pipeline del job en un hilo daemon."""
    # Import diferido para evitar ciclos de importación.
    from .pipeline import process

    def _worker() -> None:
        try:
            job.status = "running"
            output = process(job, input_path)
            job.output_name = output.name
            job.status = "done"
            job.stage = "Completado"
            job.progress = 1.0
            job.message = "¡Video listo para descargar!"
        except Exception as exc:  # noqa: BLE001 — mostramos el error al usuario
            job.status = "error"
            job.error = str(exc)
            job.stage = "Error"
            job.message = str(exc)
        finally:
            # borramos la subida original para no acumular basura
            try:
                input_path.unlink(missing_ok=True)
            except OSError:
                pass

    threading.Thread(target=_worker, name=f"job-{job.id}", daemon=True).start()
