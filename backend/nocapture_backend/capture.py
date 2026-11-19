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


def is_umbriel() -> bool:
    desktops = os.getenv("XDG_CURRENT_DESKTOP", "").lower().split(":")
    for desktop in desktops:
        if desktop in ("umbriel", "niri"):
            return desktop == "umbriel"
    return bool(os.getenv("UMBRIEL_SOCKET") and not os.getenv("NIRI_SOCKET"))


def compositor_json(command: str, umbriel: bool):
    if umbriel:
        return read_json(["umbriel", command, "--json"])
    return read_json(["niri", "msg", "--json", command])


def umbriel_displays() -> tuple[list[str], str | None]:
    outputs = [output for output in compositor_json("outputs", True) if output["enabled"]]
    focused = next((output["name"] for output in outputs if output["focused"]), None)
    return [output["name"] for output in outputs], focused


def focused_output() -> str:
    if is_umbriel():
        _, name = umbriel_displays()
    else:
        output = compositor_json("focused-output", False)
        name = output["name"] if output else None
    if not name:
        raise RuntimeError("No focused display. Select a display and try again.")
    return name


def application_names() -> list[str]:
    names = run(["gpu-screen-recorder", "--list-application-audio"], timeout=10).stdout
    # GSR treats | as a mixer separator even inside a single argv item.
    return sorted({name for name in names.splitlines() if name and "|" not in name})


def context() -> dict:
    umbriel = is_umbriel()
    windows = compositor_json("windows", umbriel)
    if umbriel:
        windows = [dict(window, is_focused=window["focused"]) for window in windows]
        outputs, focused = umbriel_displays()
    else:
        outputs = list(compositor_json("outputs", False))
        focused = focused_output()
    try:
        applications = application_names()
        audio_error = ""
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        applications = []
        audio_error = str(error)
    return {
        "windows": windows,
        "outputs": outputs,
        "focused_output": focused,
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


def capture_window(window_id: str | None, source: Path) -> None:
    umbriel = is_umbriel()
    if window_id is None:
        window = compositor_json("focused-window", umbriel)
        if not window:
            raise RuntimeError("No focused window to capture.")
        window_id = str(window["id"])
    if umbriel:
        run(["grim", "-T", window_id, str(source)], timeout=10)
        return
    if not re.fullmatch(r"[0-9]+", window_id):
        raise ValueError("Niri window IDs must be numeric.")
    run(
        [
            "niri",
            "msg",
            "action",
            "screenshot-window",
            "--id",
            window_id,
            "--path",
            str(source),
            "--show-pointer",
            "false",
        ],
        timeout=10,
    )
    deadline = time.monotonic() + 5
    while source.stat().st_size == 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    if source.stat().st_size == 0:
        raise RuntimeError("Window capture produced no image. The window may have closed.")


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
            capture_window(args.window_id, source)
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
