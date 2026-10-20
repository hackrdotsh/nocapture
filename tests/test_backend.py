import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nocapture_backend.__main__ import parser
from nocapture_backend.capture import Cancelled, record_command, reserve_path, select_region
from nocapture_backend.media import compose_window, gif_command
from PIL import Image


def options(**overrides):
    values = dict(
        target="display", output="DP-1", audio="none", application="", format="mp4", fps=30
    )
    values.update(overrides)
    return argparse.Namespace(**values)


class Commands(unittest.TestCase):
    def test_cli_bounds_and_help(self):
        args = parser().parse_args(
            ["record", "window", "--audio", "application", "--application", "Music app"]
        )
        self.assertEqual(args.application, "Music app")
        self.assertLess(len(parser().format_help()), 2000)

    def test_audio_modes(self):
        for name, value in {
            "system": "default_output",
            "microphone": "default_input",
            "both": "default_output|default_input",
        }.items():
            command = record_command(options(audio=name), Path("out.mp4"))
            self.assertEqual(command[command.index("-a") + 1], value)
        self.assertNotIn("-a", record_command(options(), Path("out.mp4")))

    def test_window_audio_is_one_explicit_application(self):
        command = record_command(
            options(target="window", audio="application", application="Music app"), Path("out.mp4")
        )
        self.assertIn("app:Music app", command)
        self.assertIn("portal", command)
        for value in ("", "Music|default_output"):
            with self.assertRaises(ValueError):
                record_command(
                    options(target="window", audio="application", application=value),
                    Path("out.mp4"),
                )
        with self.assertRaises(ValueError):
            record_command(options(target="window", audio="system"), Path("out.mp4"))

    def test_gif_rejects_audio(self):
        with self.assertRaises(ValueError):
            record_command(options(format="gif", audio="system"), Path("out.mp4"))

    def test_region_and_output_arguments(self):
        command = record_command(options(target="region"), Path("a file.mp4"), "600x400+-20+40")
        self.assertIn("600x400+-20+40", command)
        self.assertEqual(command[-1], "a file.mp4")
        with self.assertRaises(ValueError):
            record_command(options(target="region"), Path("out.mp4"))

    def test_cancelled_region_is_not_an_error(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "")):
            with self.assertRaises(Cancelled):
                select_region()

    def test_unique_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            first = reserve_path(directory, "png")
            second = reserve_path(directory, "png")
            self.assertNotEqual(first, second)
            self.assertEqual(first.stat().st_mode & 0o777, 0o600)


class Images(unittest.TestCase):
    def test_wallpaper_and_shadow_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (80, 50), "red").save(root / "window.png")
            Image.new("RGB", (400, 300), "white").save(root / "wallpaper.png")
            compose_window(root / "window.png", root / "out.png", root / "wallpaper.png", True, 96)
            with Image.open(root / "out.png") as image:
                self.assertEqual(image.size, (272, 242))
                self.assertEqual(image.getpixel((136, 120)), (255, 0, 0, 255))
                self.assertEqual(image.getpixel((0, 0)), (255, 255, 255, 255))
                self.assertLess(image.getpixel((136, 156))[0], 255)

    def test_shadow_without_wallpaper_has_transparency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGBA", (40, 30), "blue").save(root / "window.png")
            compose_window(root / "window.png", root / "out.png", None, True, 0)
            with Image.open(root / "out.png") as image:
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertGreater(image.getpixel((92, 108))[3], 0)

    def test_gif_is_animated_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=128x80:rate=10:duration=1",
                    "-c:v",
                    "libx264",
                    str(root / "source.mp4"),
                ],
                check=True,
            )
            subprocess.run(gif_command(root / "source.mp4", root / "out.gif", 5, 64), check=True)
            with Image.open(root / "out.gif") as image:
                self.assertEqual(image.width, 64)
                self.assertGreater(image.n_frames, 1)


class Worker(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.env = dict(
            os.environ, XDG_RUNTIME_DIR=str(self.root), PYTHONPATH=str(Path("backend").resolve())
        )
        self.env["PATH"] = str(self.root) + os.pathsep + self.env["PATH"]
        self.processes = []
        self.video = self.root / "fixture.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=128x80:rate=10:duration=1",
                "-c:v",
                "libx264",
                str(self.video),
            ],
            check=True,
        )
        script = self.root / "gpu-screen-recorder"
        script.write_text(f"""#!{sys.executable}
import shutil, signal, sys, time
shutil.copyfile({str(self.video)!r}, sys.argv[sys.argv.index("-o") + 1])
signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
while True: time.sleep(0.01)
""")
        script.chmod(0o755)

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.communicate()
        self.temporary.cleanup()

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "nocapture_backend", *arguments],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def start(self, output_format):
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "nocapture_backend",
                "record",
                "display",
                "--output",
                "DP-1",
                "--directory",
                str(self.root),
                "--format",
                output_format,
                "--gif-width",
                "64",
            ],
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.processes.append(process)
        end = time.monotonic() + 10
        while time.monotonic() < end:
            result = self.cli("status")
            if result.returncode == 0 and json.loads(result.stdout).get("state") == "recording":
                return process
            if process.poll() is not None:
                self.fail(process.communicate())
            time.sleep(0.02)
        self.fail("Worker did not become ready")

    def test_single_owner_and_graceful_stop(self):
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.processes.append(unrelated)
        process = self.start("mp4")
        duplicate = self.cli("record", "display", "--output", "DP-1", "--directory", str(self.root))
        self.assertEqual(duplicate.returncode, 1)
        self.assertIn("already running", duplicate.stderr)
        self.assertEqual(self.cli("stop").returncode, 0)
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr)
        result = json.loads(stdout)
        self.assertTrue(Path(result["path"]).is_file())
        self.assertEqual(result["state"], "saved")
        self.assertEqual(json.loads(self.cli("status").stdout)["state"], "saved")
        self.assertIsNone(unrelated.poll(), "Stopping Nocapture signalled an unrelated process")

    def test_gif_finalization(self):
        process = self.start("gif")
        self.cli("stop")
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr)
        result = json.loads(stdout)
        with Image.open(result["path"]) as image:
            self.assertGreater(image.n_frames, 1)
        self.assertFalse(list(self.root.glob("*.recording.mp4")))

    def test_conversion_failure_keeps_source_video(self):
        script = self.root / "ffmpeg"
        script.write_text(f"#!{sys.executable}\nimport sys\nsys.exit(3)\n")
        script.chmod(0o755)
        process = self.start("gif")
        self.cli("stop")
        process.communicate(timeout=10)
        self.assertEqual(process.returncode, 1)
        state = json.loads(self.cli("status").stdout)
        self.assertEqual(state["state"], "error")
        self.assertTrue(Path(state["source"]).is_file())
        self.assertFalse(Path(state["path"]).exists())


if __name__ == "__main__":
    unittest.main()
