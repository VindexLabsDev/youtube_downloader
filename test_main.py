import queue
import unittest
from pathlib import Path
from unittest.mock import patch

from main import MP4_FORMAT, yt_dlp, DownloaderApp, default_download_folder, deno_executable, ffmpeg_folder, sanitize_template, validate_url


class DownloadTests(unittest.TestCase):
    def test_redirected_download_folder(self):
        expected = Path("F:/Users/Example/Downloads")
        with patch("main.sys.platform", "win32"), patch("main.windows_download_folder", return_value=expected), patch("main.Path.home", return_value=Path("C:/Users/Example")):
            self.assertEqual(default_download_folder(), expected)
            app = DownloaderApp()
            try:
                self.assertEqual(Path(app.folder_var.get()), expected)
                app.folder_var.set("C:/Other")
                app.reset_to_default_folder()
                self.assertEqual(Path(app.folder_var.get()), expected)
            finally:
                app.destroy()

    def test_download_folder_fallback_on_windows_error(self):
        home = Path("C:/Users/Example")
        with patch("main.sys.platform", "win32"), patch("main.windows_download_folder", side_effect=OSError), patch("main.Path.home", return_value=home):
            with patch("main.Path.exists", return_value=True):
                self.assertEqual(default_download_folder(), home / "Downloads")
            with patch("main.Path.exists", return_value=False):
                self.assertEqual(default_download_folder(), Path.cwd())

    def test_urls(self):
        for url in ("https://youtu.be/abc", "https://www.youtube.com/watch?v=abc", "https://m.youtube.com/shorts/abc"):
            validate_url(url)
        for url in ("", "file:///video", "https://youtube.com.evil.org/video", "https://example.com"):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_template_escapes_folder_and_keeps_id(self):
        template = sanitize_template(Path("100% videos"))
        self.assertIn("100%% videos", template)
        self.assertIn("%(id)s", template)

    def test_missing_ffmpeg(self):
        with patch("main.shutil.which", return_value=None), patch("main.Path.is_file", return_value=False):
            with self.assertRaises(ValueError):
                ffmpeg_folder()
            with self.assertRaises(ValueError):
                deno_executable()

    def test_worker_checks_final_file(self):
        app = object.__new__(DownloaderApp)
        app.output_queue = queue.Queue()
        directory = str(Path(__file__).parent)
        folder = Path(directory)
        for extension in ("mp4", "webm", "missing.mp4"):
            with self.subTest(extension=extension):
                filename = folder / ("video." + extension)
                with patch("main.ffmpeg_folder", return_value=directory), patch("main.deno_executable", return_value="deno.exe"), patch("main.Path.is_file", return_value=extension != "missing.mp4"), patch("main.yt_dlp.YoutubeDL") as ydl:
                    options = {}

                    def create(opts):
                        options.update(opts)
                        return ydl.return_value

                    def download(urls):
                        options["post_hooks"][0](str(filename))
                        return 0

                    ydl.side_effect = create
                    ydl.return_value.__enter__.return_value.download.side_effect = download
                    app._download_worker("https://youtu.be/abc", folder)
                events = []
                while not app.output_queue.empty():
                    events.append(app.output_queue.get_nowait())
                self.assertEqual(any(kind == "error" for kind, _ in events), extension != "mp4")
                self.assertEqual(events[-1], ("enable", "1"))
                self.assertEqual(options["format"], MP4_FORMAT)

    def test_format_selection_requires_h264_and_aac(self):
        def format_entry(identifier, vcodec, acodec, ext):
            return {"format_id": identifier, "vcodec": vcodec, "acodec": acodec,
                    "ext": ext, "url": "https://example.com/" + identifier,
                    "protocol": "https"}

        av1 = format_entry("av1", "av01.0.08M.08", "none", "mp4")
        h264 = format_entry("h264", "avc1.640028", "none", "mp4")
        aac = format_entry("aac", "none", "mp4a.40.2", "m4a")
        opus = format_entry("opus", "none", "opus", "webm")
        combined = format_entry("combined", "avc1.42001E", "mp4a.40.2", "mp4")
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            select = ydl.build_format_selector(MP4_FORMAT)
            for formats, expected in (
                ([aac, opus, h264, av1], ["h264+aac"]),
                ([combined, opus, av1], ["combined"]),
                ([aac, opus, av1], []),
            ):
                with self.subTest(expected=expected):
                    result = list(select({"formats": formats, "incomplete_formats": False, "has_merged_format": False}))
                    self.assertEqual([entry["format_id"] for entry in result], expected)

    def test_worker_refreshes_links_once_on_403(self):
        for failures in (1, 2):
            with self.subTest(failures=failures):
                app = object.__new__(DownloaderApp)
                app.output_queue = queue.Queue()
                calls = []
                with patch("main.ffmpeg_folder", return_value="."), patch("main.deno_executable", return_value="deno.exe"), patch("main.Path.is_file", return_value=True), patch("main.yt_dlp.YoutubeDL") as ydl:
                    def create(options):
                        calls.append(options)
                        return ydl.return_value

                    def download(urls):
                        if len(calls) <= failures:
                            raise yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")
                        calls[-1]["post_hooks"][0]("video.mp4")
                        return 0

                    ydl.side_effect = create
                    ydl.return_value.__enter__.return_value.download.side_effect = download
                    app._download_worker("https://youtu.be/abc", Path("."))
                events = list(app.output_queue.queue)
                self.assertEqual(len(calls), 2)
                self.assertEqual(any(kind == "error" for kind, _ in events), failures == 2)
                self.assertEqual(events[-1], ("enable", "1"))

    def test_worker_does_not_retry_other_errors(self):
        app = object.__new__(DownloaderApp)
        app.output_queue = queue.Queue()
        with patch("main.ffmpeg_folder", return_value="."), patch("main.deno_executable", return_value="deno.exe"), patch("main.yt_dlp.YoutubeDL") as ydl:
            ydl.return_value.__enter__.return_value.download.side_effect = yt_dlp.utils.DownloadError("Video unavailable")
            app._download_worker("https://youtu.be/abc", Path("."))
            self.assertEqual(ydl.call_count, 1)
        self.assertTrue(any(kind == "error" for kind, _ in app.output_queue.queue))

    def test_error_releases_controls_before_dialog(self):
        app = DownloaderApp()
        try:
            app._set_download_enabled(False)
            app.progress_var.set(35)
            app.output_queue.put(("error", "HTTP Error 403: Forbidden"))
            with patch("main.messagebox.showerror") as dialog:
                def check_controls(*args):
                    self.assertEqual(str(app.download_button["state"]), "normal")
                    self.assertEqual(app.progress_var.get(), 0)
                dialog.side_effect = check_controls
                app._process_queue()
                dialog.assert_called_once()
        finally:
            app.destroy()

    def test_ui_success_status_is_preserved(self):
        app = DownloaderApp()
        try:
            app.output_queue.put(("status", "Descarga completada"))
            app.output_queue.put(("enable", "1"))
            app._process_queue()
            app.update_idletasks()
            self.assertEqual(app.status_var.get(), "Descarga completada")
            self.assertEqual(str(app.download_button["state"]), "normal")
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
