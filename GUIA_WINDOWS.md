# 🪟 Guía fácil para Windows (paso a paso)

Esta guía es para instalar y usar **ReVE Upscaler** aunque nunca hayas hecho algo así.
Son 3 partes. Tranqui, se hace una sola vez.

---

## Parte 1 — Instalar Python (una sola vez, ~3 min)

Python es el "motor" que hace funcionar la app. Es gratis y seguro.

1. Entrá a 👉 **https://www.python.org/downloads/**
2. Apretá el botón amarillo grande que dice **"Download Python 3.x"**.
3. Abrí el archivo que se descargó (algo como `python-3.x.exe`).
4. ⚠️ **MUY IMPORTANTE**: en la primera pantalla, **marcá la casilla de abajo**
   que dice **"Add python.exe to PATH"**. Es el paso que más se olvida y sin él no
   funciona.
5. Apretá **"Install Now"** y esperá a que termine. Listo.

> Si tu notebook es del trabajo y no te deja instalar programas, avisale a la persona
> de sistemas/IT que necesitás instalar Python — es una herramienta estándar y segura.

---

## Parte 2 — Descargar la app desde GitHub (una sola vez, ~2 min)

El código está en **tu** repositorio de GitHub. Hay dos formas; la **A es la más fácil**.

### ✅ Opción A — Descargar el ZIP (recomendada)

1. Hacé clic en este enlace para bajar todo en un archivo comprimido:

   👉 **https://github.com/evelynbumbaca/videoupscalereve/archive/refs/heads/claude/ai-video-upscale-tool-72g2m6.zip**

2. Se descarga un `.zip`. Buscalo en tu carpeta **Descargas**.
3. Hacé **clic derecho** sobre el `.zip` → **"Extraer todo…"** → **"Extraer"**.
4. Se crea una carpeta (nombre largo tipo `videoupscalereve-claude-...`). Abrila.
   Para que sea más cómodo, podés **renombrarla** a algo simple como `ReVE` y moverla
   a tu **Escritorio**.

### Opción B — Con Git (si ya sabés usarlo)

```bash
git clone https://github.com/evelynbumbaca/videoupscalereve.git
cd videoupscalereve
git checkout claude/ai-video-upscale-tool-72g2m6
```

---

## Parte 3 — Abrir la app (¡doble clic!)

1. Entrá a la carpeta que descargaste.
2. Buscá el archivo **`Iniciar ReVE Upscaler.bat`** y hacele **doble clic**.
3. La **primera vez** se va a abrir una ventana negra que instala todo solo
   (Python, los modelos de IA, ffmpeg). **Tarda unos minutos, es normal.** No la cierres.
4. Cuando termina, **se abre solo tu navegador** con la app lista para usar. 🎉

> **Las próximas veces** ya no instala nada: hacés doble clic y en segundos se abre.

### ⚠️ Si Windows te muestra un aviso azul ("Windows protegió tu PC")

Es normal con archivos `.bat` recién bajados. Hacé clic en **"Más información"** y luego
en **"Ejecutar de todas formas"**. El archivo es local y no hace nada raro (podés abrirlo
con el Bloc de notas para verlo).

---

## 🎬 Cómo usar la app

1. **Arrastrá** tu video a la zona grande (o hacé clic para elegirlo).
2. Elegí el **aumento**: empezá con **2×** para probar rápido; después subí a **4×**.
3. Elegí el **modelo**: para videos hechos con IA, dejá el primero
   (*Video IA / Animado*).
4. *(Opcional)* Si tu video tiene una **marca de agua** (como la estrellita de
   Veo/Gemini), activá **"Quitar marca de agua"**: aparece una previsualización
   del video y **arrastrás con el mouse para dibujar un recuadro justo encima de
   la marca**. Cuanto más ajustado al logo, más limpio queda.
   - **Método de borrado:** *Rápido* (difuminado) o *Relleno con IA*. Para videos
     que vas a mostrar en **pantallas grandes**, conviene el **Relleno con IA**
     (hay que instalarlo una vez — ver abajo).
5. Apretá **"Mejorar video"** y mirá la barra de progreso.
6. Cuando termina, **previsualizás** el resultado y lo **descargás**.

El arriba a la derecha te muestra un cartelito verde **"IA activa"** cuando tu placa
NVIDIA está lista. 👍

---

## ⏹️ Cómo detener la app

Cerrá la **ventana negra** (la que dice "ReVE Upscaler"). Con eso se apaga todo.
Para volver a usarla, doble clic de nuevo en `Iniciar ReVE Upscaler.bat`.

---

## 🪄 Activar el "Relleno con IA" para la marca de agua (opcional)

El borrado *Rápido* difumina la zona; sirve, pero en **pantallas grandes** puede
notarse. El **Relleno con IA** reconstruye la zona de forma inteligente y queda
mucho más limpio. Es opcional porque descarga ~300-400 MB (una sola vez).

Para instalarlo, doble clic en **`Instalar relleno IA (opcional).bat`** y esperá a
que termine. Después, al usar "Quitar marca de agua", vas a poder elegir
**"Relleno con IA"** en *Método de borrado*.

> Corre en tu procesador (no hace falta GPU) y solo trabaja la zona de la marca,
> así que no es tan lento. En fondos muy movidos puede haber un leve parpadeo.

---

## 🔄 Cómo actualizar (cuando haya mejoras o arreglos)

Cuando te pase una versión nueva, **no hace falta reinstalar nada ni volver a bajar los
modelos de IA**. Solo:

1. Doble clic en **`Actualizar.bat`**.
2. Se baja e instala la última versión del código automáticamente (unos segundos).
3. Cuando termina, cerrá esa ventana y abrí la app con `Iniciar ReVE Upscaler.bat`.

Tus modelos de IA, tu entorno y tus videos quedan intactos.

---

## 🆘 Si algo no anda

| Qué ves | Qué hacer |
|---|---|
| "No se encontro Python" | Volvé a la **Parte 1** y asegurate de marcar **"Add python.exe to PATH"**. |
| El cartelito dice "Modo respaldo" | Los modelos de IA no se bajaron. Abrí la carpeta y doble clic en `Iniciar ReVE Upscaler.bat` de nuevo, o corré `python scripts\setup_tools.py`. |
| Error de memoria (out of memory) | Tu placa tiene 4 GB. Ver el README, sección "VRAM y tile": se baja con una línea. |
| Va lento | Probá **2×** en vez de 4×, y usá clips cortos. |

¿Trabado en algún paso? Copiame lo que dice la pantalla y te ayudo. 🙌
