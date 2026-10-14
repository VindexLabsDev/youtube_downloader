# Vindex YouTube Downloader

Aplicación de escritorio para Windows que descarga un video de YouTube por vez en **MP4 con H.264 y AAC**, con una interfaz oscura al estilo Vindex.

## Funciones

- Mejor calidad disponible en H.264 + AAC; no descarga AV1 ni VP9.
- Progreso, velocidad, tiempo restante y registro de actividad.
- Detección de la carpeta Descargas real de Windows, incluso en otro disco.
- Selección y apertura de la carpeta de destino.
- Comprobación de formatos descargables y un reintento con enlaces nuevos ante HTTP 403.
- Reanudación de archivos parciales y protección de archivos existentes.

La resolución puede ser menor que la ofrecida en AV1 o VP9. Si no existe un formato compatible, la app muestra un error.

## Ejecutar desde el código

Necesitas **Python 3.10 o posterior** con Tkinter, FFmpeg/FFprobe y Deno.

En PowerShell:

```powershell
git clone https://github.com/VindexLabsDev/youtube_downloader.git
cd youtube_downloader
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
winget install Gyan.FFmpeg
winget install DenoLand.Deno
```

Abre una nueva terminal para actualizar el PATH y ejecuta, desde la carpeta del repo:

```powershell
.\.venv\Scripts\python.exe main.py
```

Pega el enlace, elige el destino y pulsa **Descargar MP4** o Enter. Espera a que termine la descarga antes de cerrar la app.

## Portable Windows

Para generar el ejecutable:

```powershell
.\build_portable.ps1
```

FFmpeg, FFprobe y Deno deben estar en el PATH al compilar. El script crea el entorno virtual si hace falta e instala las dependencias.

El resultado es `dist\YoutubeDownloader.exe`: un solo archivo que incluye Python, FFmpeg, FFprobe, Deno y los scripts EJS. El usuario final no necesita instalarlos.

Los ejecutables no se guardan en Git; se pueden distribuir mediante [GitHub Releases](https://github.com/VindexLabsDev/youtube_downloader/releases). Consulta [THIRD_PARTY.md](THIRD_PARTY.md) antes de distribuir un portable.

## Carpeta y nombres de archivos

En Windows se usa la carpeta Descargas configurada en el sistema. **Usar Descargas** vuelve a esa ubicación. Si Windows no puede obtenerla, se intenta `Downloads` del usuario y, si no existe, la carpeta actual.

Los nombres incluyen el título, el identificador de YouTube y `[H264]`. Esta marca evita reutilizar una descarga anterior en AV1. Los archivos existentes no se sobrescriben ni se convierten automáticamente.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Las pruebas no acceden a Internet. Verifican enlaces, rutas redirigidas de Descargas, selección de H.264/AAC, comprobación del MP4 final, reintento del 403 y estado de la interfaz.

## Estructura

```text
assets/                 Iconos PNG e ICO
main.py                 Interfaz y descarga
test_main.py            Pruebas
requirements.txt        Dependencias
build_portable.ps1      Compilación para Windows
LICENSE                 Licencia MIT
THIRD_PARTY.md          Dependencias y distribución
```

`.venv/`, `build/`, `dist/` y las cachés son locales y se excluyen de Git.

## Licencia

El código de este proyecto se distribuye bajo la [licencia MIT](LICENSE). Las dependencias y los componentes incluidos en el portable conservan sus propias licencias.
