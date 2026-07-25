# Upscale Eve

Herramienta local para hacer **upscale de videos** (especialmente los generados con IA)
y llevarlos de calidad media/baja a **HD, 2K o 4K** — con una interfaz web limpia y
sin que tus archivos salgan de tu equipo.

El upscaling lo hace **Real-ESRGAN** (IA) por debajo, orquestado con **ffmpeg**.
No necesita instalar PyTorch ni CUDA: usa binarios `ncnn-vulkan` que funcionan con
cualquier GPU (NVIDIA, AMD, Intel o Apple) e incluso por CPU.

> 🪟 **¿Usás Windows y nunca hiciste esto?** Seguí la **[Guía fácil paso a paso
> (GUIA_WINDOWS.md)](GUIA_WINDOWS.md)** — está pensada para arrancar de cero con
> un doble clic.

---

## ✨ Qué hace

- Dos modos en una interfaz limpia con pestañas: **🎬 Video** y **🖼️ Imagen**.
- Sube un video o una imagen, elegí el aumento (**2× / 3× / 4×**) y el modelo, y descargá el resultado.
- Modelos pensados para **video de IA / animación**, **fotorrealista** e **ilustración**.
- **Quitar marca de agua** marcando la zona exacta sobre una previsualización. Dos
  modos: **rápido** (difuminado con `delogo`) o **relleno con IA** (modelo LaMa,
  reconstrucción inteligente, ideal para pantallas grandes — complemento opcional).
- Opción de **suavizar el movimiento** interpolando frames (RIFE) para más fps.
- Barra de progreso real (frame por frame) y previsualización del resultado.
- **Modo respaldo**: si todavía no descargaste los modelos de IA, la app igual
  funciona escalando con `ffmpeg` (lanczos), así podés probar todo el flujo de una.

---

## 🚀 Puesta en marcha (rápida)

Requisito: **Python 3.10+**. En Windows, instalá Python desde python.org marcando
"Add python.exe to PATH".

```bash
# 1) Instalar dependencias del servidor (livianas)
pip install -r requirements.txt

# 2) Descargar los binarios de IA + ffmpeg
python scripts/setup_tools.py

# 3) Arrancar
python run.py
```

> **No necesitás ninguna API ni clave de IA.** Todo el modelo corre localmente en tu
> GPU con Real-ESRGAN. No hay costo por uso, no hace falta internet para procesar, y
> los videos nunca salen de tu equipo.

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

### VRAM y tamaño de "tile"

Real-ESRGAN procesa cada frame en bloques ("tiles") para no llenar la memoria de la
GPU. En placas con **4 GB de VRAM** (como una RTX 500 Ada Laptop) el valor por defecto
(`256`) está pensado para andar cómodo. Si alguna vez ves un error de *out of memory*,
bajalo:

```bash
# Windows (PowerShell)
$env:REVE_TILE_SIZE = "128"   # o 100 si hace falta
python run.py
```

Para forzar una GPU concreta usá `REVE_GPU_ID` (0 = la primera). `-1` fuerza CPU.

---

## 🪄 Relleno de marca de agua con IA

El modo **rápido** (`delogo`) reconstruye difuminando desde los bordes: sirve para
logos chicos, pero en pantallas grandes puede notarse. El modo **relleno con IA**
reconstruye la zona de forma inteligente (mucho más limpio).

Hay **dos motores** y la app elige solo el mejor disponible:

| Motor | Peso | Velocidad | Cuándo se usa |
|---|---|---|---|
| **MI-GAN** (ONNX) | ~85 MB | ~0,8 s/frame | Incluido por defecto. También va en el portable. |
| **LaMa** (torch) | ~1,3 GB | ~2 s/frame | Opcional. Un poco más prolijo en fondos complejos. |

MI-GAN viene incluido: **no hay que instalar nada** para usar el relleno con IA.
Si querés el motor de máxima calidad (LaMa), se instala aparte:

```bash
python scripts/setup_tools.py --ai-watermark      # o "Instalar relleno IA (opcional).bat"
```

Ambos corren en CPU (no necesitan GPU) y procesan solo un recorte alrededor de la
marca, así que son rápidos. En fondos muy movidos puede haber un leve parpadeo
entre cuadros (limitación del relleno cuadro-a-cuadro).

## 📦 Crear un portable para compartir (Windows)

Podés generar una versión **portable**: una carpeta con `Upscale Eve.exe` que
tus compañeros usan **sin instalar Python ni nada** (descomprimen y doble clic).

```bash
# opción A (Windows): doble clic en
#   "Crear portable.bat"

# opción B: manualmente
pip install pyinstaller
pyinstaller "packaging/reve.spec" --noconfirm
# luego copiá la carpeta tools/ dentro de dist/Upscale Eve/ para incluir ffmpeg y modelos
```

El resultado queda en `dist/Upscale Eve/`. Comprimí esa carpeta en un `.zip` y
compartila.

> 💡 Antes de generarlo, corré `python scripts/setup_tools.py --slim` (u opción 4
> de `Limpiar espacio.bat`): el paquete de RIFE trae ~15 modelos y la app usa solo
> `rife-v4.6`, así que eso libera **~440 MB** en tu disco y en el portable.

Notas:
- **Incluye todo**: upscaling con IA, borrado de marca de agua con IA (MI-GAN),
  imágenes y video. Pesa ~250 MB + ffmpeg y modelos de `tools/`.
- No incluye el motor LaMa (torch, 1,3 GB). El portable usa MI-GAN, que da
  calidad equivalente con 16x menos peso.
- Si la PC de destino no tiene GPU compatible, la app **sigue funcionando**:
  detecta el fallo y pasa sola al modo respaldo en vez de cortar el trabajo.
- Al ser un `.exe` sin firmar, Windows puede mostrar el aviso de SmartScreen
  ("Más información" → "Ejecutar de todas formas").

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
