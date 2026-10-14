param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$ffmpeg = (Get-Command ffmpeg -ErrorAction Stop).Source
$ffprobe = (Get-Command ffprobe -ErrorAction Stop).Source
$deno = (Get-Command deno -ErrorAction Stop).Source
$assets = Join-Path $PSScriptRoot "assets"
$icon = Join-Path $assets "vvideo.ico"

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}

$venvPython = Join-Path (Resolve-Path ".venv").Path "Scripts\python.exe"

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar pip." }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }
& $venvPython -m PyInstaller --noconfirm --noconsole --onefile --icon "$icon" --add-data "$assets;assets" --name YoutubeDownloader --add-binary "$ffmpeg;." --add-binary "$ffprobe;." --add-binary "$deno;." --distpath dist --workpath build --specpath build main.py
if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el ejecutable." }

Write-Host ""
Write-Host "Ejecutable generado en dist\YoutubeDownloader.exe"
