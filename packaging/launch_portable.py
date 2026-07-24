"""Punto de entrada del ejecutable portable (PyInstaller).

Arranca el servidor local y abre el navegador, igual que run.py, pero
pensado para correr dentro del .exe empaquetado. Importa la app como objeto
(no como string) para que PyInstaller la incluya sin problemas.
"""
from __future__ import annotations

import socket
import threading
import time
import webbrowser


def _find_free_port(host: str, preferred: int, attempts: int = 30) -> int | None:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    return None


def main() -> None:
    import uvicorn
    from backend.main import app  # importa la app y crea las carpetas de datos

    host = "127.0.0.1"
    port = _find_free_port(host, 8000) or 8000
    url = f"http://{host}:{port}"

    def _open() -> None:
        time.sleep(1.4)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()

    print(f"\n  ReVE Upscaler -> {url}")
    print("  (Cerra esta ventana para detener la app)\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
