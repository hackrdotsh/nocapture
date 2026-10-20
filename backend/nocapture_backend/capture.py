import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .media import compose_window


class Cancelled(Exception):
    pass


def run(arguments: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(arguments, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"{arguments[0]} failed.")
    return result


def read_json(arguments: list[str]):
    return json.loads(run(arguments, timeout=10).stdout)


def focused_output() -> str:
    output = read_json(["niri", "msg", "--json", "focused-output"])
    if not output:
        raise RuntimeError("No focused display. Select a display and try again.")
    return output["name"]


def application_names() -> list[str]:
    names = run(["gpu-screen-recorder", "--list-application-audio"], timeout=10).stdout
    # GSR treats | as a mixer separator even inside a single argv item.
    return sorted({name for name in names.splitlines() if name and "|" not in name})


def context() -> dict:
    windows = read_json(["niri", "msg", "--json", "windows"])
    outputs = read_json(["niri", "msg", "--json", "outputs"])
    try:
        applications = application_names()
        audio_error = ""
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        applications = []
        audio_error = str(error)
    return {
        "windows": windows,
        "outputs": list(outputs),
        "focused_output": focused_output(),
        "applications": applications,
        "audio_error": audio_error,
    }


def reserve_path(directory: str, extension: str, prefix: str = "capture") -> Path:
    folder = Path(directory).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.{extension}"
    path = folder / name
    path.touch(mode=0o600, exist_ok=False)
    return path


def select_region() -> str:
    result = subprocess.run(["slurp", "-f", "%wx%h+%x+%y"], capture_output=True, text=True)
    if result.returncode:
        message = result.stderr.strip()
        if (
            result.returncode == 1
            and not result.stdout.strip()
            and message.lower() in ("", "selection cancelled", "selection canceled")
        ):
            raise Cancelled()
        raise RuntimeError(message or "Region selection failed.")
    region = result.stdout.strip()
    if not re.fullmatch(r"[1-9]\d*x[1-9]\d*\+-?\d+\+-?\d+", region):
        raise RuntimeError("The region picker returned invalid geometry.")
    return region


def screenshot(args) -> dict:
    destination = reserve_path(args.directory, "png")
    descriptor, name = tempfile.mkstemp(suffix=".png", dir=destination.parent)
    os.close(descriptor)
    source = Path(name)
    try:
        if args.target == "region":
            geometry = select_region()
            match = re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geometry)
            width, height, x, y = match.groups()
            run(["grim", "-g", f"{x},{y} {width}x{height}", str(source)])
        elif args.target == "display":
            run(["grim", "-o", args.output or focused_output(), str(source)])
        else:
            window_id = args.window_id
            if window_id is None:
                window = read_json(["niri", "msg", "--json", "focused-window"])
                if not window:
                    raise RuntimeError("No focused window to capture.")
                window_id = window["id"]
            run(
                [
                    "niri",
                    "msg",
                    "action",
                    "screenshot-window",
                    "--id",
                    str(window_id),
                    "--path",
                    str(source),
                    "--show-pointer",
                    "false",
                ]
            )
            deadline = time.monotonic() + 5
            while source.stat().st_size == 0 and time.monotonic() < deadline:
                time.sleep(0.05)
            if source.stat().st_size == 0:
                raise RuntimeError("Window capture produced no image. The window may have closed.")
        wallpaper = None
        if args.wallpaper:
            output = args.output or focused_output()
            value = run(["noctalia", "msg", "wallpaper-get", output], timeout=10).stdout.strip()
            wallpaper = Path(value).expanduser()
            if not wallpaper.is_file():
                raise RuntimeError("No readable Noctalia wallpaper on the selected display.")
        if args.target == "window" and (args.shadow or args.wallpaper):
            compose_window(source, destination, wallpaper, args.shadow, args.padding)
        else:
            source.replace(destination)
        with destination.open("rb") as image:
            # wl-copy forks a provider; it must not retain the caller's IPC pipes.
            clipboard = subprocess.run(
                ["wl-copy", "--type", "image/png"],
                stdin=image,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return {"path": str(destination), "clipboard": clipboard.returncode == 0}
    except BaseException:
        if destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)
        raise
    finally:
        source.unlink(missing_ok=True)


def record_command(args, output: Path, region: str | None = None) -> list[str]:
    if args.format == "gif" and args.audio != "none":
        raise ValueError("GIF cannot contain audio. Select silent recording.")
    if args.target == "window" and args.audio not in ("none", "application"):
        raise ValueError("Window recordings allow only application audio or no audio.")
    if args.audio == "application":
        if args.target != "window" or not args.application or "|" in args.application:
            raise ValueError("Select one application audio source for the window recording.")
    command = ["gpu-screen-recorder", "-w"]
    if args.target == "region":
        if not region:
            raise ValueError("Select a region before recording.")
        command += ["region", "-region", region]
    elif args.target == "window":
        command += ["portal", "-restore-portal-session", "no"]
    else:
        if not args.output:
            raise ValueError("Select a display before recording.")
        command += [args.output]
    audio = {
        "system": "default_output",
        "microphone": "default_input",
        "both": "default_output|default_input",
        "application": f"app:{args.application}",
    }
    if args.audio != "none":
        command += ["-a", audio[args.audio], "-ac", "aac"]
    return command + [
        "-f",
        str(args.fps),
        "-k",
        "h264",
        "-encoder",
        "gpu",
        "-fallback-cpu-encoding",
        "yes",
        "-fm",
        "cfr",
        "-o",
        str(output),
    ]
