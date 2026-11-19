import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nocapture_backend.__main__ import parser
from nocapture_backend.capture import Cancelled, context, screenshot
from PIL import Image

WINDOW_ID = "a4e60eb029d14c7f8e324281956d312c"
WINDOW = {"id": WINDOW_ID, "title": "Fixture", "app_id": "test", "focused": True}
OUTPUTS = [
    {"name": "DP-2", "enabled": False, "focused": False},
    {"name": "DP-1", "enabled": True, "focused": True},
]


class Umbriel(unittest.TestCase):
    def setUp(self):
        self.windows = [
            dict(
                WINDOW,
                output="DP-2",
                x=-200,
                y=20,
                w=160,
                h=100,
                visible=True,
                pinned=False,
                fullscreen=False,
                floating=False,
                scratchpad="",
            )
        ]
        self.enterContext(patch.dict(os.environ, {"UMBRIEL_SOCKET": "/fixture.sock"}, clear=True))
        self.commands = self.enterContext(patch("subprocess.run", side_effect=self.run_command))

    def run_command(self, args, **kwargs):
        match args:
            case ["umbriel", "windows", "--json"]:
                stdout = json.dumps(self.windows)
            case ["umbriel", "focused-window", "--json"]:
                stdout = json.dumps(WINDOW)
            case ["umbriel", "outputs", "--json"]:
                stdout = json.dumps(OUTPUTS)
            case ["grim", "-g", "-200,30 160x90", path]:
                Image.new("RGB", (160, 90), "gold").save(path)
                stdout = ""
            case ["gpu-screen-recorder", "--list-application-audio"]:
                stdout = "Music\n"
            case ["slurp", "-o", "-r", *flags] if flags[-2:] == ["-f", "%l"]:
                stdout = "HDMI-A-1\n"
            case ["slurp", "-p", *flags] if flags[-2:] == ["-f", "%x %y %o"]:
                stdout = "-150 40 DP-2\n"
            case ["grim", "-T", window_id, path] if window_id == WINDOW_ID:
                Image.new("RGB", (20, 20), "red").save(path)
                stdout = ""
            case ["grim", "-o", "DP-1" | "HDMI-A-1", path]:
                Image.new("RGB", (20, 20), "red").save(path)
                stdout = ""
            case ["grim", "-T", "closed", _]:
                return subprocess.CompletedProcess(args, 1, "", "Window not found")
            case ["wl-copy", "--type", "image/png"]:
                stdout = ""
            case _:
                self.fail(f"Unexpected command: {args}")
        return subprocess.CompletedProcess(args, 0, stdout, "")

    def test_context_uses_enabled_outputs_and_normalizes_window_focus(self):
        value = context()
        self.assertEqual(value["outputs"], ["DP-1"])
        self.assertEqual(value["focused_output"], "DP-1")
        self.assertEqual(value["applications"], ["Music"])
        self.assertEqual(value["windows"][0]["id"], WINDOW_ID)
        self.assertTrue(value["windows"][0]["is_focused"])

    def test_window_capture_uses_selected_or_focused_id(self):
        for flags in (["--window-id", WINDOW_ID], []):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as directory:
                self.commands.reset_mock()
                args = parser().parse_args(
                    ["screenshot", "window", "--directory", directory, *flags]
                )
                value = screenshot(args)
                with Image.open(value["path"]) as image:
                    self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))
                self.assertTrue(value["clipboard"])
                commands = [call.args[0] for call in self.commands.call_args_list]
                self.assertEqual(["umbriel", "focused-window", "--json"] in commands, not flags)

    def test_closed_window_leaves_no_capture_and_does_not_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(
                ["screenshot", "window", "--directory", directory, "--window-id", "closed"]
            )
            with self.assertRaisesRegex(RuntimeError, "Window not found"):
                screenshot(args)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(len(self.commands.call_args_list), 1)

    def test_window_picker_uses_clicked_output_and_ignores_hidden_windows(self):
        self.windows.extend(
            [
                dict(self.windows[0], id="hidden", visible=False),
                dict(self.windows[0], id="other-output", output="DP-1"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(
                ["screenshot", "window", "--pick-window", "--directory", directory]
            )
            self.assertTrue(Path(screenshot(args)["path"]).is_file())
        self.assertEqual(self.commands.call_args_list[2].args[0][:3], ["grim", "-T", WINDOW_ID])

    def test_ambiguous_window_click_leaves_no_capture(self):
        self.windows.append(dict(self.windows[0], id="overlap"))
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(
                ["screenshot", "window", "--pick-window", "--directory", directory]
            )
            with self.assertRaisesRegex(RuntimeError, "Windows overlap"):
                screenshot(args)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_display_capture_defaults_to_focused_output(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(["screenshot", "display", "--directory", directory])
            self.assertTrue(Path(screenshot(args)["path"]).is_file())

    def test_as_shown_captures_visible_window_bounds_from_the_screen(self):
        output = dict(
            OUTPUTS[0],
            enabled=True,
            position={"x": -300, "y": 30},
            logical_size={"width": 300, "height": 180},
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "nocapture_backend.capture.compositor_json", side_effect=[self.windows, [output]]
            ),
        ):
            args = parser().parse_args(
                ["screenshot", "window", "--pick-window", "--as-shown", "--directory", directory]
            )
            with Image.open(screenshot(args)["path"]) as image:
                self.assertEqual(image.size, (160, 90))
                self.assertEqual(image.getpixel((0, 0)), (255, 215, 0))

    def test_display_capture_uses_the_clicked_screen_not_the_focused_output(self):
        with tempfile.TemporaryDirectory() as directory:
            args = parser().parse_args(
                ["screenshot", "display", "--pick-output", "--directory", directory]
            )
            self.assertTrue(Path(screenshot(args)["path"]).is_file())
        commands = [call.args[0] for call in self.commands.call_args_list]
        self.assertEqual(
            [args[:3] for args in commands[:2]], [["slurp", "-o", "-r"], ["grim", "-o", "HDMI-A-1"]]
        )


class Niri(unittest.TestCase):
    def test_window_capture_keeps_niri_ipc_in_nested_session(self):
        def run_command(args, **kwargs):
            match args:
                case ["niri", "msg", "--json", "pick-window"]:
                    return subprocess.CompletedProcess(args, 0, '{"id": 42}', "")
                case [
                    "niri",
                    "msg",
                    "action",
                    "screenshot-window",
                    "--id",
                    "42",
                    "--path",
                    path,
                    "--show-pointer",
                    "false",
                ]:
                    Image.new("RGB", (20, 20), "blue").save(path)
                case ["wl-copy", "--type", "image/png"]:
                    pass
                case _:
                    self.fail(f"Unexpected command: {args}")
            return subprocess.CompletedProcess(args, 0, "", "")

        env = {"XDG_CURRENT_DESKTOP": "Noctalia:Niri", "UMBRIEL_SOCKET": "/parent.sock"}
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, env, clear=True),
            patch("subprocess.run", side_effect=run_command),
        ):
            for flags in (["--window-id", "42"], ["--pick-window"]):
                args = parser().parse_args(
                    ["screenshot", "window", "--directory", directory, *flags]
                )
                with Image.open(screenshot(args)["path"]) as image:
                    self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))

    def test_cancelling_native_window_picker_leaves_no_capture(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "niri"}, clear=True),
            patch(
                "subprocess.run", return_value=subprocess.CompletedProcess([], 0, "null", "")
            ) as command,
        ):
            args = parser().parse_args(
                ["screenshot", "window", "--pick-window", "--directory", directory]
            )
            with self.assertRaises(Cancelled):
                screenshot(args)
            self.assertEqual(list(Path(directory).iterdir()), [])
            command.assert_called_once()
