# 🎬 ReVE Upscaler

Herramienta local para hacer **upscale de videos** (especialmente los generados con IA)
y llevarlos de calidad media/baja a **HD, 2K o 4K** — con una interfaz web limpia y
sin que tus archivos salgan de tu equipo.

El upscaling lo hace **Real-ESRGAN** (IA) por debajo, orquestado con **ffmpeg**.
No necesita instalar PyTorch ni CUDA: usa binarios `ncnn-vulkan` que funcionan con
cualquier GPU (NVIDIA, AMD, Intel o Apple) e incluso por CPU.

---

## ✨ Qué hace

- Sube un video, elegí el aumento (**2× / 3× / 4×**) y el modelo, y descargá el resultado.
- Modelos pensados para **video de IA / animación**, **fotorrealista** e **ilustración**.
- Opción de **suavizar el movimiento** interpolando frames (RIFE) para más fps.
- Barra de progreso real (frame por frame) y previsualización del resultado.
- **Modo respaldo**: si todavía no descargaste los modelos de IA, la app igual
  funciona escalando con `ffmpeg` (lanczos), así podés probar todo el flujo de una.

---

## 🚀 Puesta en marcha (rápida)

Requisito: **Python 3.10+**.

```bash
# 1) Instalar dependencias del servidor (livianas)
pip install -r requirements.txt

# 2) Descargar los binarios de IA + ffmpeg
python scripts/setup_tools.py

# 3) Arrancar
python run.py
```

Se abre solo en `http://127.0.0.1:8000`. Arrastrás un video, elegís las opciones
y listo.

> ¿Ya tenés `ffmpeg` instalado en el sistema? El script lo detecta y no lo vuelve a bajar.
> En macOS, si hace falta: `brew install ffmpeg`.

Para ver qué herramientas están instaladas:

```bash
python scripts/setup_tools.py --list
```

---

## 🖥️ Sobre el rendimiento

El upscaling con IA es intensivo. Orientativo:

| Hardware              | Velocidad aproximada          |
|-----------------------|-------------------------------|
| GPU NVIDIA moderna    | Muy rápido                    |
| Apple Silicon (M1+)   | Rápido                        |
| AMD / Intel (Vulkan)  | Aceptable                     |
| Solo CPU              | Lento (minutos por segundo)   |

Como los clips de IA suelen durar pocos segundos, incluso en equipos modestos es usable.
Consejo: empezá con **2×** para probar y subí a **4×** cuando el resultado te convenza.

---

## 🧠 Cómo funciona por dentro

```
video → [ffmpeg] extrae frames + audio
      → [Real-ESRGAN] escala cada frame con IA
      → [RIFE] (opcional) interpola para más fps
      → [ffmpeg] rearma el video + audio (H.264, alta calidad)
      → resultado en outputs/
```

---

## 📂 Estructura

```
backend/          servidor FastAPI + pipeline de procesamiento
  main.py         endpoints de la API y archivos estáticos
  pipeline.py     orquesta las etapas y el progreso
  engine.py       envoltorios de ffmpeg y Real-ESRGAN
  jobs.py         trabajos en segundo plano
  hardware.py     detección de GPU/herramientas
  config.py       rutas y descubrimiento de binarios
frontend/         interfaz (HTML/CSS/JS, sin frameworks)
scripts/
  setup_tools.py  descarga ffmpeg / Real-ESRGAN / RIFE
run.py            lanzador
tools/            binarios descargados (ignorado por git)
uploads/ outputs/ archivos de trabajo (ignorados por git)
```

---

## 🔒 Privacidad

Todo corre en tu máquina. El servidor escucha solo en `127.0.0.1` y los videos
no se suben a ningún servicio externo.

---

## 🛠️ Solución de problemas

- **"Faltan herramientas"** en el badge → corré `python scripts/setup_tools.py`.
- **Descarga automática falló** → el script imprime la URL para bajar el binario a
  mano y la carpeta donde descomprimirlo (`tools/…`).
- **Va muy lento** → probá 2× en vez de 4×, o verificá que la GPU esté siendo usada
  (badge superior derecho).
- **El resultado se ve "plástico"** → probá otro modelo (p. ej. *Fotorrealista* en
  vez de *Video IA*), según el tipo de contenido.
