from __future__ import annotations

import ctypes
import math
import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse
from uuid import UUID

import yt_dlp


MP4_FORMAT = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]"
    "/best[ext=mp4][vcodec^=avc1][acodec^=mp4a]"
)


def windows_download_folder() -> Path:
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(
        UUID("374DE290-123F-4565-9164-39C4925E467B").bytes_le
    )
    path = ctypes.c_void_p()
    get_path = ctypes.windll.shell32.SHGetKnownFolderPath
    get_path.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    get_path.restype = ctypes.c_long
    free_path = ctypes.windll.ole32.CoTaskMemFree
    free_path.argtypes = [ctypes.c_void_p]
    free_path.restype = None
    try:
        result = get_path(ctypes.byref(folder_id), 0, None, ctypes.byref(path))
        if result != 0:
            raise OSError("Windows could not locate the Downloads folder.")
        return Path(ctypes.wstring_at(path))
    finally:
        free_path(path)


def default_download_folder() -> Path:
    if sys.platform == "win32":
        try:
            return windows_download_folder()
        except OSError:
            pass
    downloads = Path.home() / "Downloads"
    if downloads.exists():
        return downloads
    return Path.cwd()


def sanitize_template(folder: Path) -> str:
    return str(folder).replace("%", "%%") + "/%(title).180B [%(id)s] [H264].%(ext)s"


def ffmpeg_folder() -> str:
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    if all((bundled / name).is_file() for name in ("ffmpeg.exe", "ffprobe.exe")):
        return str(bundled)
    executable = shutil.which("ffmpeg")
    if not executable or not shutil.which("ffprobe"):
        raise ValueError("Faltan FFmpeg y FFprobe. Instálalos y agrégalos al PATH, o usa el ejecutable portable.")
    return str(Path(executable).parent)


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not (
        host in ("youtube.com", "youtu.be") or host.endswith(".youtube.com")
    ):
        raise ValueError("Pega un enlace válido de YouTube, por ejemplo https://www.youtube.com/watch?v=...")


def deno_executable() -> str:
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "deno.exe"
    executable = str(bundled) if bundled.is_file() else shutil.which("deno")
    if not executable:
        raise ValueError("Falta Deno para procesar enlaces de YouTube. Instálalo y agrégalo al PATH, o usa el ejecutable portable.")
    return executable


class DownloadLogger:
    def __init__(self, output_queue: queue.Queue) -> None:
        self.output_queue = output_queue

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        self.output_queue.put(("log", message))

    def error(self, message: str) -> None:
        pass  # DownloadError is reported by the worker.


class DownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube Downloader")
        assets = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets"
        self.app_icon = tk.PhotoImage(file=str(assets / "vvideo.png"))
        self.iconphoto(True, self.app_icon)
        if sys.platform == "win32":
            self.iconbitmap(str(assets / "vvideo.ico"))
        self.brand_icon = self.app_icon.subsample(max(1, self.app_icon.width() // 40))
        self.geometry("1100x760")
        self.minsize(960, 700)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(default_download_folder()))
        self.status_var = tk.StringVar(value="Listo")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self.after(100, self._process_queue)

    def _build_ui(self) -> None:
        bg, panel, stage = "#0f1922", "#192733", "#111d29"
        text, muted, cyan, peach = "#edf1f5", "#a8bed0", "#86c8dc", "#e9ad83"
        self.configure(padx=26, pady=22, background=bg)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 11), background=bg, foreground=text)
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Stage.TFrame", background=stage)
        style.configure("TLabel", background=bg, foreground=text)
        style.configure("Muted.TLabel", foreground=muted)
        style.configure("Eyebrow.TLabel", foreground=muted, font=("Segoe UI", 9))
        style.configure("Panel.TLabel", background=panel, foreground=muted)
        style.configure("Stage.TLabel", background=stage, foreground=muted)
        style.configure("Heading.TLabel", background=stage, foreground=text, font=("Segoe UI", 22, "bold"))
        style.configure("Badge.TLabel", background="#203440", foreground=cyan, padding=(12, 7), font=("Segoe UI", 9))
        style.configure("TEntry", padding=12, fieldbackground="#223340", foreground=text,
                        bordercolor="#344a5c", lightcolor="#344a5c", darkcolor="#344a5c", insertcolor=text)
        style.map("TEntry", bordercolor=[("focus", cyan)],
                  fieldbackground=[("disabled", "#192733")], foreground=[("disabled", "#7f94a5")])
        style.configure("TButton", padding=(16, 10), background="#223340", foreground=text,
                        borderwidth=0, font=("Segoe UI", 10))
        style.map("TButton", background=[("disabled", "#1c2b37"), ("active", "#304455")],
                  foreground=[("disabled", "#7f94a5")])
        style.configure("Accent.TButton", background=peach, foreground="#101923", font=("Segoe UI", 11, "bold"))
        style.map("Accent.TButton", background=[("disabled", "#394754"), ("active", "#f2bf9b")],
                  foreground=[("disabled", "#8b9eae")])
        style.configure("Horizontal.TProgressbar", background=cyan, troughcolor="#344654",
                        borderwidth=0, lightcolor=cyan, darkcolor=cyan, thickness=5)

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 16))
        mark = ttk.Label(header, image=self.brand_icon)
        mark.pack(side="left", padx=(0, 12))
        brand = ttk.Frame(header)
        brand.pack(side="left")
        ttk.Label(brand, text="VINDEX", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(brand, text="Y O U T U B E   D O W N L O A D E R", style="Eyebrow.TLabel").pack(anchor="w")
        ttk.Label(header, text="TUS VIDEOS. A TU RITMO.", style="Eyebrow.TLabel").pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0, minsize=285)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="DESCARGAR VIDEO", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        ttk.Label(body, text="ACTIVIDAD", style="Eyebrow.TLabel").grid(row=0, column=1, sticky="w", padx=(20, 0), pady=(0, 12))

        main = ttk.Frame(body, style="Stage.TFrame", padding=(24, 14))
        main.grid(row=1, column=0, sticky="nsew")
        art = tk.Canvas(main, height=72, bg=stage, highlightthickness=0)
        art.pack(fill="x")

        def draw_rings(event):
            art.delete("all")
            cx, cy = event.width / 2, 35
            for ring in range(6):
                points = []
                for step in range(121):
                    angle = step / 120 * math.tau
                    radius = 21 + ring * 4 + math.sin(angle * 5 + ring * .35) * 3
                    points.extend((cx + math.cos(angle) * radius * 1.5, cy + math.sin(angle) * radius * .72))
                art.create_line(*points, fill=peach if ring >= 4 else "#50889e", width=1, smooth=True)
            art.create_line(cx, cy-17, cx, cy+14, fill=cyan, width=3)
            art.create_line(cx-9, cy+5, cx, cy+14, cx+9, cy+5, fill=cyan, width=3)
            art.create_line(cx-14, cy+23, cx+14, cy+23, fill=cyan, width=2)

        art.bind("<Configure>", draw_rings)
        ttk.Label(main, text="Tu próximo video, aquí.", style="Heading.TLabel").pack(pady=(4, 5))
        ttk.Label(main, text="Pega un enlace y llévalo contigo en MP4.", style="Stage.TLabel").pack(pady=(0, 14))
        ttk.Label(main, text="ENLACE DE YOUTUBE", style="Stage.TLabel", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))
        self.url_entry = ttk.Entry(main, textvariable=self.url_var)
        self.url_entry.pack(fill="x", pady=(0, 12))
        self.url_entry.bind("<Return>", lambda event: self.start_download())
        self.url_entry.focus_set()
        ttk.Label(main, text="GUARDAR EN", style="Stage.TLabel", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))
        folder_row = ttk.Frame(main, style="Stage.TFrame")
        folder_row.pack(fill="x")
        self.folder_entry = ttk.Entry(folder_row, textvariable=self.folder_var)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        self.browse_button = ttk.Button(folder_row, text="Elegir…", command=self.choose_folder)
        self.browse_button.pack(side="left", padx=(10, 0))
        actions = ttk.Frame(main, style="Stage.TFrame")
        actions.pack(fill="x", pady=(12, 8))
        self.download_button = ttk.Button(actions, text="Descargar MP4", style="Accent.TButton", command=self.start_download)
        self.download_button.pack(side="left")
        self.default_button = ttk.Button(actions, text="Usar Descargas", command=self.reset_to_default_folder)
        self.default_button.pack(side="right")
        ttk.Label(main, text="MP4 compatible · H.264 + AAC", style="Stage.TLabel", font=("Segoe UI", 9)).pack(anchor="w")

        activity = ttk.Frame(body, style="Panel.TFrame", padding=18)
        activity.grid(row=1, column=1, sticky="nsew", padx=(20, 0))
        ttk.Label(activity, text="Tu sesión", style="Panel.TLabel", foreground=text, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(activity, text="Cada descarga, paso a paso.", style="Panel.TLabel", font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 18))
        self.log_text = tk.Text(activity, width=26, height=8, wrap="word", font=("Segoe UI", 10),
                                bg=panel, fg=muted, relief="flat", padx=0, pady=4,
                                highlightthickness=0, insertbackground=text, selectbackground="#344a5c")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", "Listo para empezar.\n\nTus descargas aparecerán aquí.\n")
        self.log_text.configure(state="disabled")
        ttk.Button(activity, text="Abrir carpeta", command=self.open_folder).pack(fill="x", pady=(16, 0))

        transport = ttk.Frame(self, style="Panel.TFrame", padding=(20, 16))
        transport.pack(side="bottom", fill="x", pady=(12, 0), before=body)
        status_row = ttk.Frame(transport, style="Panel.TFrame")
        status_row.pack(fill="x", pady=(0, 12))
        ttk.Label(status_row, textvariable=self.status_var, style="Panel.TLabel", foreground=text).pack(side="left")
        ttk.Label(status_row, text="MP4", style="Badge.TLabel").pack(side="right")
        self.progress = ttk.Progressbar(transport, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress.pack(fill="x")
        footer = ttk.Frame(self)
        footer.pack(side="bottom", fill="x", pady=(14, 0), before=transport)
        ttk.Label(footer, text="Un enlace. Un video. Siempre contigo.", style="Eyebrow.TLabel").pack(side="left")
        ttk.Label(footer, text="V I N D E X   L A B S", style="Eyebrow.TLabel").pack(side="right")

    def open_folder(self) -> None:
        try:
            os.startfile(str(Path(self.folder_var.get()).expanduser().resolve()))
        except OSError as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc))

    def close_app(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Descarga en curso", "Espera a que termine la descarga antes de cerrar la aplicación.")
            return
        self.destroy()

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.folder_var.get() or str(default_download_folder()))
        if selected:
            self.folder_var.set(selected)

    def reset_to_default_folder(self) -> None:
        self.folder_var.set(str(default_download_folder()))

    def start_download(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showinfo("Descarga en curso", "Ya hay una descarga en progreso.")
            return

        url = self.url_var.get().strip()

        if not url:
            messagebox.showwarning("Falta la URL", "Pega una URL antes de descargar.")
            return

        try:
            folder = Path(self.folder_var.get().strip() or str(default_download_folder())).expanduser().resolve()
            validate_url(url)
            ffmpeg_folder()
            deno_executable()
            folder.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as exc:
            messagebox.showerror("No se puede iniciar", str(exc))
            return
        self.folder_var.set(str(folder))
        self.progress_var.set(0)
        self.status_var.set("Preparando descarga...")
        self._set_download_enabled(False)
        self._log(f"Iniciando descarga: {url}")
        self._log(f"Destino: {folder}")

        self.worker_thread = threading.Thread(
            target=self._download_worker,
            args=(url, folder),
            daemon=True,
        )
        self.worker_thread.start()

    def _set_download_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.download_button.configure(state=state)
        self.download_button.configure(text="Descargar MP4" if enabled else "Descargando…")
        for widget in (self.url_entry, self.folder_entry, self.browse_button, self.default_button):
            widget.configure(state=state)

    def _download_worker(self, url: str, folder: Path) -> None:
        try:
            completed: list[str] = []
            ydl_opts = {
                "outtmpl": sanitize_template(folder),
                "format": MP4_FORMAT,
                "ffmpeg_location": ffmpeg_folder(),
                "js_runtimes": {"deno": {"path": deno_executable()}},
                "overwrites": False,
                "noplaylist": True,
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
                ],
                "progress_hooks": [self._progress_hook],
                "post_hooks": [completed.append],
                "quiet": True,
                "check_formats": "selected",
                "logger": DownloadLogger(self.output_queue),
            }

            for attempt in range(2):
                completed.clear()
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        result = ydl.download([url])
                    break
                except yt_dlp.utils.DownloadError as exc:
                    if attempt or "HTTP Error 403" not in str(exc):
                        raise
                    self.output_queue.put(("log", "YouTube rechazó el enlace temporal. Obteniendo uno nuevo..."))
                    self.output_queue.put(("status", "Reintentando descarga..."))
                    self.output_queue.put(("progress", "0"))
            if result or not completed or any(
                Path(filename).suffix.lower() != ".mp4" or not Path(filename).is_file()
                for filename in completed
            ):
                raise RuntimeError("No se generó un MP4 completo. Revisa el enlace y vuelve a intentar.")

            self.output_queue.put(("status", "Descarga completada"))
            self.output_queue.put(("log", f"MP4 guardado: {completed[-1]}"))
            self.output_queue.put(("progress", "100"))
        except Exception as exc:  # pragma: no cover - UI error path
            self.output_queue.put(("error", str(exc)))
        finally:
            self.output_queue.put(("enable", "1"))

    def _progress_hook(self, data: dict[str, object]) -> None:
        status = data.get("status")
        if status == "downloading":
            downloaded = float(data.get("downloaded_bytes") or 0.0)
            total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0.0)
            if total > 0:
                percent = min(100.0, (downloaded / total) * 100.0)
                self.output_queue.put(("progress", f"{percent:.2f}"))

            speed = data.get("speed")
            eta = data.get("eta")
            message = "Descargando"
            if speed:
                message += f" | {self._format_speed(float(speed))}"
            if eta is not None:
                message += f" | Restan {int(float(eta))} s"
            self.output_queue.put(("status", message))
        elif status == "finished":
            self.output_queue.put(("status", "Procesando archivo final..."))
            self.output_queue.put(("log", "La descarga terminó y yt-dlp está uniendo/ajustando el archivo."))

    def _process_queue(self) -> None:
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    try:
                        self.progress_var.set(float(payload))
                    except ValueError:
                        pass
                elif kind == "error":
                    self.status_var.set("Error")
                    self._log(payload)
                    self.progress_var.set(0)
                    self._set_download_enabled(True)
                    messagebox.showerror("Error de descarga", payload)
                elif kind == "enable":
                    self._set_download_enabled(True)
        except queue.Empty:
            pass
        self.after(100, self._process_queue)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + os.linesep)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    @staticmethod
    def _format_speed(speed: float) -> str:
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        value = speed
        unit = units[0]
        for candidate in units[1:]:
            if value < 1024:
                break
            value /= 1024
            unit = candidate
        return f"{value:.1f} {unit}"


def main() -> None:
    app = DownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
