# Componentes de terceros

La licencia MIT de este repositorio no reemplaza las licencias de sus dependencias.

| Componente | Uso | Documentación y licencias originales |
| --- | --- | --- |
| Python y Tcl/Tk | Ejecución e interfaz | [Python](https://docs.python.org/3/license.html), [Tcl/Tk](https://www.tcl-lang.org/software/tcltk/license.html) |
| yt-dlp | Extracción y descarga | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| yt-dlp-ejs | Resolución de desafíos JavaScript | [EJS](https://github.com/yt-dlp/ejs) |
| FFmpeg y FFprobe | Unión y procesamiento del MP4 | [FFmpeg](https://ffmpeg.org/legal.html) |
| Deno | Ejecución de JavaScript | [Deno](https://github.com/denoland/deno) |
| PyInstaller | Creación del ejecutable | [PyInstaller](https://pyinstaller.org/en/stable/license.html) |

## Distribución del portable

El script incluye los binarios de FFmpeg, FFprobe y Deno instalados en el equipo que compila, además del runtime de Python y las dependencias de yt-dlp. La licencia aplicable a FFmpeg depende de la distribución y de sus opciones de compilación.

Antes de publicar un portable, revisa las licencias de las versiones efectivamente incluidas y acompaña la distribución con los avisos, textos de licencia y acceso al código fuente que correspondan. Este documento identifica los componentes principales; no sustituye los avisos originales ni enumera todas las dependencias transitivas.
