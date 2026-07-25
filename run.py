#!/usr/bin/env python3
"""Lanzador de Upscale Eve.

Arranca el servidor local y abre el navegador. Si el puerto elegido está
ocupado (por ejemplo, quedó una copia anterior abierta), busca uno libre
automáticamente en vez de fallar.

    python run.py            # http://127.0.0.1:8000 (o el primero libre)
    python run.py --port 9000 --no-browser
"""
from __future__ import annotations

import argparse
import socket
import threading
import time
import webbrowser


def _find_free_port(host: str, preferred: int, attempts: int = 30) -> int | None:
    """Devuelve el primer puerto libre a partir de `preferred`."""
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue  # ocupado, probamos el siguiente
    return None


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

    port = _find_free_port(args.host, args.port)
    if port is None:
        raise SystemExit(
            f"No se encontro un puerto libre entre {args.port} y {args.port + 29}.\n"
            "Cerra otras ventanas de ReVE que puedan estar abiertas y volve a intentar."
        )

    if port != args.port:
        print(f"\n  (El puerto {args.port} estaba ocupado; uso el {port} en su lugar.)")

    url = f"http://{args.host}:{port}"
    if not args.no_browser:
        def _open() -> None:
            time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    print(f"\n  Upscale Eve → {url}\n  (Ctrl+C para detener)\n")
    import uvicorn
    uvicorn.run("backend.main:app", host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
