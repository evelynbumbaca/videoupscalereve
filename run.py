#!/usr/bin/env python3
"""Lanzador de ReVE Upscaler.

Arranca el servidor local y abre el navegador.

    python run.py            # http://127.0.0.1:8000
    python run.py --port 9000 --no-browser
"""
from __future__ import annotations

import argparse
import threading
import time
import webbrowser


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    try:
        import uvicorn  # noqa: F401
    except ImportError:
        raise SystemExit(
            "Faltan dependencias. Instalalas con:\n    pip install -r requirements.txt"
        )

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        def _open() -> None:
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    print(f"\n  ReVE Upscaler → {url}\n  (Ctrl+C para detener)\n")
    import uvicorn
    uvicorn.run("backend.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
