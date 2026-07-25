# Upscale Eve — ficha técnica para el equipo de IT / Seguridad

Documento para revisar una **alerta de Behavior Monitoring / falso positivo**
generada por esta herramienta. Describe con precisión qué hace la aplicación,
qué procesos ejecuta y qué toca en el disco y en la red.

---

## Qué es

Herramienta de escritorio para **aumentar la resolución de videos e imágenes**
con modelos de IA que corren **localmente**. Es de uso interno y no envía
archivos a ningún servicio externo.

- **Lenguaje:** Python. Interfaz web servida en `localhost`.
- **Código fuente:** disponible y auditable en el repositorio interno.

## Qué procesos ejecuta

La aplicación lanza estos ejecutables de terceros, todos **open source y de
amplio uso**:

| Ejecutable | Proyecto | Para qué |
|---|---|---|
| `ffmpeg.exe`, `ffprobe.exe` | FFmpeg (BtbN builds) | Separar el video en cuadros y volver a armarlo |
| `realesrgan-ncnn-vulkan.exe` | Real-ESRGAN (xinntao) | Aumentar la resolución de cada cuadro (GPU vía Vulkan) |
| `rife-ncnn-vulkan.exe` | RIFE (nihui) | Interpolación de cuadros (opcional) |

Se descargan **una sola vez**, exclusivamente desde `https://github.com/`
(releases oficiales de esos proyectos). No hay descargas durante el uso normal.

> **Nota honesta:** estos binarios **no están firmados digitalmente**, como es
> habitual en herramientas open source de este tipo. Ese es un motivo frecuente
> de detección heurística.

## Red

- El servidor escucha **solo en `127.0.0.1`** (loopback). No acepta conexiones
  desde la red.
- **No hay tráfico saliente** durante el procesamiento: los modelos corren
  localmente. La única salida a internet ocurre durante la instalación
  (descarga desde github.com).
- Ningún archivo del usuario sale del equipo.

## Actividad en disco (el motivo probable de la alerta)

Este es el punto clave para entender la detección:

Para procesar un video, la aplicación **extrae cada cuadro como un archivo PNG**,
los procesa y luego **borra todos los temporales**. Un clip de 10 segundos a 30
fps genera y elimina **~300 archivos** en pocos minutos; un clip más largo, miles.

**Ese patrón — creación y borrado masivo de archivos en poco tiempo — es
justamente el que las reglas de Behavior Monitoring asocian a ransomware.** No
hay cifrado ni modificación de archivos del usuario: los temporales son creados
por la propia aplicación y borrados por ella misma.

Todo ocurre **dentro de la carpeta de la aplicación**:

```
<carpeta de la app>\work\      cuadros temporales (se borran al terminar)
<carpeta de la app>\uploads\   archivo de entrada (se borra al terminar)
<carpeta de la app>\outputs\   resultado final
<carpeta de la app>\tools\     binarios de ffmpeg / modelos
```

No escribe fuera de esa carpeta, no toca el registro, no instala servicios ni
tareas programadas, y no requiere privilegios de administrador.

## Sobre la versión portable (si aplica)

La versión portable se empaqueta con **PyInstaller**. Los ejecutables generados
con PyInstaller son un **falso positivo muy documentado**: como algunos malware
también usan esa herramienta, varios motores marcan el *bootloader* por sí mismo.
El empaquetado se hace sin compresión UPX y en modo carpeta (`onedir`), que son
las configuraciones que menos detecciones generan.

## Qué se solicita

Si tras la revisión se considera aceptable, la solución habitual es una
**exclusión de Behavior Monitoring para la carpeta de la aplicación**, que es
donde ocurre toda la actividad descrita.

Quedamos a disposición para facilitar el código fuente, los hashes de los
binarios o cualquier verificación adicional que necesiten.
