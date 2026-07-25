#!/usr/bin/env python3
"""Descarga los binarios necesarios (ffmpeg, Real-ESRGAN, RIFE) en ./tools.

Uso:
    python scripts/setup_tools.py            # descarga todo lo que falte
    python scripts/setup_tools.py --only realesrgan
    python scripts/setup_tools.py --list     # solo muestra qué hay/falta

Es best-effort: si una descarga falla (por ejemplo, sin internet o una URL
que cambió), imprime instrucciones manuales claras y sigue con el resto.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def _plat() -> str:
    s = platform.system()
    if s == "Windows":
        return "windows"
    if s == "Darwin":
        return "macos"
    return "ubuntu"  # Linux genérico


# URLs de releases oficiales. Editá si querés fijar otra versión.
REALESRGAN = {
    "windows": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
    "macos":   "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip",
    "ubuntu":  "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip",
}
RIFE = {
    "windows": "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip",
    "macos":   "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-macos.zip",
    "ubuntu":  "https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-ubuntu.zip",
}
# ffmpeg estático. En macOS lo más simple es `brew install ffmpeg`.
FFMPEG = {
    "windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "ubuntu":  "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
}
# Modelo LaMa (relleno de marca de agua con IA). Complemento opcional.
LAMA_URL = "https://github.com/Sanster/models/releases/download/add_big_lama/big-lama.pt"


def _download(url: str, dest: Path) -> None:
    print(f"  ↓ {url}")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "reve-upscaler-setup"})
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _extract(archive: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest_dir)
    elif archive.name.endswith(".tar.xz"):
        import tarfile
        with tarfile.open(archive) as t:
            t.extractall(dest_dir)
    else:
        raise RuntimeError(f"Formato de archivo no soportado: {archive.name}")


def _make_executable(folder: Path, names: list[str]) -> None:
    import os
    for name in names:
        for f in folder.rglob(name):
            try:
                f.chmod(f.stat().st_mode | 0o111)
            except OSError:
                pass
        # también aseguramos bit +x en cualquier ejecutable suelto
    _ = os


def install(component: str, urls: dict, subdir: str, exe_names: list[str]) -> bool:
    plat = _plat()
    url = urls.get(plat)
    if not url:
        print(f"⚠️  {component}: no hay descarga automática para {plat}.")
        return False

    target = TOOLS / subdir
    target.mkdir(parents=True, exist_ok=True)
    archive = TOOLS / Path(url).name
    try:
        _download(url, archive)
        _extract(archive, target)
        _make_executable(target, exe_names)
        archive.unlink(missing_ok=True)
        print(f"✅ {component} instalado en {target}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {component}: falló la descarga automática ({exc}).")
        print(f"   Descargalo a mano desde:\n   {url}\n   y descomprimilo en: {target}")
        return False


def status() -> None:
    from importlib import util
    sys.path.insert(0, str(ROOT))
    if util.find_spec("backend") is None:
        print("(Ejecutá esto desde la raíz del proyecto.)")
        return
    from backend import hardware, engine
    rep = hardware.system_report()
    print("\nEstado de las herramientas:")
    for tool, ok in rep["tools"].items():
        print(f"  {'✅' if ok else '⬜'} {tool}")
    ai_wm = engine.ai_inpaint_available()
    print(f"  {'✅' if ai_wm else '⬜'} relleno con IA (motor: {engine.ai_inpaint_engine() or 'ninguno'})")
    print(f"\nModo actual de la app: {rep['mode']}")
    print(f"GPU detectada: {rep['gpu']['name']}\n")


def install_ai_watermark() -> None:
    """Instala el complemento opcional de relleno con IA: dependencias de
    Python (torch, pillow, numpy) + el modelo LaMa (~200 MB)."""
    import subprocess

    print("• Complemento de relleno con IA (marca de agua)\n")
    req = ROOT / "requirements-ai-watermark.txt"
    print("[1/2] Instalando torch + pillow + numpy (puede tardar, ~300 MB)…")
    # Si por algún motivo falta el archivo de requisitos, instalamos por nombre.
    if req.exists():
        pip_cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    else:
        pip_cmd = [sys.executable, "-m", "pip", "install", "torch", "pillow", "numpy"]
    rc = subprocess.call(pip_cmd)
    if rc != 0:
        print("❌ Falló la instalación de dependencias. Revisá tu conexión.")
        return

    print("\n[2/2] Descargando el modelo LaMa (~200 MB)…")
    lama_dir = TOOLS / "lama"
    lama_dir.mkdir(parents=True, exist_ok=True)
    dest = lama_dir / "big-lama.pt"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print("  ✅ El modelo ya estaba descargado.")
    else:
        try:
            _download(LAMA_URL, dest)
            print(f"  ✅ Modelo guardado en {dest}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ Falló la descarga ({exc}).")
            print(f"     Bajalo a mano desde:\n     {LAMA_URL}\n     y guardalo en: {dest}")
            return
    print("\n✅ Complemento de relleno con IA listo.")


def slim_tools() -> None:
    """Borra los modelos de RIFE que la app no usa (~440 MB).

    El paquete de RIFE trae ~15 modelos; nosotros usamos solo rife-v4.6 (el
    más nuevo y el más chico). Los demás son peso muerto tanto en tu disco
    como en el portable que compartís.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from backend import config as cfg
    except Exception:
        print("(Ejecutá esto desde la raíz del proyecto.)")
        return

    binary = cfg.rife_path()
    if not binary:
        print("• RIFE no está instalado: no hay nada que adelgazar.")
        return

    base = Path(binary).parent
    keep = cfg.RIFE_MODEL_NAME
    removed_mb = 0
    for item in base.iterdir():
        if not item.is_dir() or item.name == keep:
            continue
        if not item.name.startswith("rife"):
            continue  # no tocamos nada que no sea un modelo de rife
        size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
        shutil.rmtree(item, ignore_errors=True)
        removed_mb += size / 1048576
        print(f"  – quitado {item.name} ({size/1048576:.0f} MB)")

    if removed_mb:
        print(f"\n✅ Liberados ~{removed_mb:.0f} MB. Se conservó {keep}, que es el que usa la app.")
    else:
        print(f"  Ya estaba adelgazado (solo queda {keep}).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Descarga los binarios de Upscale Eve.")
    ap.add_argument("--only", choices=["ffmpeg", "realesrgan", "rife"], help="instala solo un componente")
    ap.add_argument("--ai-watermark", action="store_true",
                    help="instala el complemento opcional de relleno con IA (torch + modelo LaMa)")
    ap.add_argument("--slim", action="store_true",
                    help="borra los modelos de RIFE que no se usan (~440 MB)")
    ap.add_argument("--list", action="store_true", help="muestra el estado y sale")
    args = ap.parse_args()

    TOOLS.mkdir(parents=True, exist_ok=True)

    if args.list:
        status()
        return

    if args.slim:
        slim_tools()
        return

    if args.ai_watermark:
        install_ai_watermark()
        return

    plat = _plat()
    print(f"Plataforma detectada: {plat}\n")

    want = {args.only} if args.only else {"ffmpeg", "realesrgan", "rife"}

    # Reutilizamos los "buscadores" del backend para detectar lo ya instalado
    # (así una re-ejecución no vuelve a descargar lo que ya está).
    sys.path.insert(0, str(ROOT))
    try:
        from backend import config as _cfg
    except Exception:
        _cfg = None

    # Con --only forzamos la descarga aunque exista (útil para reparar).
    forced = args.only is not None

    if "realesrgan" in want:
        print("• Real-ESRGAN (upscaling con IA)")
        if not forced and _cfg and _cfg.realesrgan_path():
            print("  ✅ Ya instalado, se omite la descarga.")
        else:
            install("Real-ESRGAN", REALESRGAN, "realesrgan",
                    ["realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"])

    if "rife" in want:
        print("• RIFE (interpolación de frames, opcional)")
        if not forced and _cfg and _cfg.rife_path():
            print("  ✅ Ya instalado, se omite la descarga.")
        else:
            install("RIFE", RIFE, "rife",
                    ["rife-ncnn-vulkan", "rife-ncnn-vulkan.exe"])

    if "ffmpeg" in want:
        print("• ffmpeg")
        if not forced and _cfg and _cfg.ffmpeg_path() and _cfg.ffprobe_path():
            print("  ✅ ffmpeg ya está disponible, se omite la descarga.")
        elif shutil.which("ffmpeg") and shutil.which("ffprobe"):
            print("  ✅ ffmpeg ya está en el PATH del sistema, no hace falta descargar.")
        elif plat == "macos":
            print("  ℹ️  En macOS instalalo con Homebrew:  brew install ffmpeg")
        else:
            install("ffmpeg", FFMPEG, "ffmpeg", ["ffmpeg", "ffprobe", "ffmpeg.exe", "ffprobe.exe"])

    status()


if __name__ == "__main__":
    main()
