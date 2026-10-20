"""Isolated desktop fixture and evidence commands; never enables the user's plugin."""

import argparse
import array
import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw
from wayland_pointer import Pointer

ENVIRONMENT_KEYS = (
    "HOME",
    "PATH",
    "WAYLAND_DISPLAY",
    "NIRI_SOCKET",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_DATA_DIRS",
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_TYPE",
    "PIPEWIRE_RUNTIME_DIR",
    "PIPEWIRE_REMOTE",
    "PULSE_SERVER",
)


def start_time(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2))


def run(root, env, command, label):
    result = subprocess.run(command, env=env, capture_output=True, timeout=60)
    record = {
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout.decode(errors="replace"),
        "stderr": result.stderr.decode(errors="replace"),
        "time": time.time(),
    }
    write_json(root / f"{label}.json", record)
    if result.returncode:
        raise RuntimeError(record["stderr"] or f"Command failed: {command}")
    return result.stdout


def spawn(root, env, name, command):
    with (root / f"{name}.log").open("w") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
    path = root / "processes.json"
    processes = json.loads(path.read_text()) if path.exists() else []
    processes.append({"name": name, "pid": process.pid, "start_time": start_time(process.pid)})
    write_json(path, processes)
    return process


def wait_for(callback, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = callback()
        if value:
            return value
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {description}")


def launch(root, package):
    root.mkdir(parents=True, exist_ok=False)
    for name in ("runtime", "config/noctalia", "state", "data", "captures"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "runtime").chmod(0o700)
    env = {key: os.environ[key] for key in ENVIRONMENT_KEYS if key in os.environ}
    display = Path(env["WAYLAND_DISPLAY"])
    env["WAYLAND_DISPLAY"] = str(
        display if display.is_absolute() else Path(env["XDG_RUNTIME_DIR"]) / display
    )
    for key, folder in (
        ("XDG_RUNTIME_DIR", "runtime"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_STATE_HOME", "state"),
        ("XDG_DATA_HOME", "data"),
    ):
        env[key] = str(root / folder)
    bus = subprocess.check_output(
        ["dbus-daemon", "--session", "--fork", "--print-address=1", "--print-pid=1"], text=True
    ).splitlines()
    env["DBUS_SESSION_BUS_ADDRESS"] = bus[0]
    write_json(
        root / "processes.json",
        [{"name": "dbus", "pid": int(bus[1]), "start_time": start_time(int(bus[1]))}],
    )
    env["PATH"] = str(package / "bin") + ":" + env["PATH"]
    env["XDG_CURRENT_DESKTOP"] = "niri"
    env["XDG_SESSION_TYPE"] = "wayland"
    env["PIPEWIRE_RUNTIME_DIR"] = env["XDG_RUNTIME_DIR"]
    env["PULSE_SERVER"] = "unix:" + str(root / "runtime/pulse/native")
    config = root / "niri.kdl"
    config.write_text(
        "debug { dbus-interfaces-in-non-session-instances; }\n"
        "layout { gaps 16; }\n"
        "hotkey-overlay { skip-at-startup; }\n"
        "gestures { hot-corners { off; }; }\n"
    )
    spawn(root, env, "niri", ["niri", "-c", str(config)])
    sockets = wait_for(lambda: list((root / "runtime").glob("niri.*.sock")), "nested Niri")
    env["NIRI_SOCKET"] = str(sockets[0])
    env["WAYLAND_DISPLAY"] = next(
        path.name
        for path in (root / "runtime").glob("wayland-*")
        if not path.name.endswith(".lock")
    )
    write_json(root / "env.json", env)
    write_json(
        root / "identity.json",
        {
            "package": str(package),
            "revision": subprocess.check_output(
                ["jj", "log", "-r", "@", "--no-graph", "-T", "commit_id"], text=True
            ),
            "created": time.time(),
        },
    )
    (root / "config/noctalia/config.toml").write_text(f'''
[shell]
telemetry_enabled = false
polkit_agent = false
clipboard_enabled = false
[notification]
enable_daemon = false
[weather]
enabled = false
[location]
auto_locate = false
[wallpaper]
enabled = true
directory = "{root}"
[bar.main]
start = []
center = []
end = []
[plugins]
enabled = ["hackrdotsh/nocapture"]
auto_update = "none"
[[plugins.source]]
name = "verification"
kind = "path"
location = "{package}/share/noctalia/plugins"
[plugin_settings."hackrdotsh/nocapture"]
screenshot_directory = "{root}/captures"
recording_directory = "{root}/captures"
''')
    spawn(root, env, "noctalia", ["noctalia"])
    wait_for(lambda: list((root / "runtime").glob("noctalia-*.sock")), "Noctalia IPC")
    image = Image.new("RGB", (1500, 1125), "#18344a")
    draw = ImageDraw.Draw(image)
    for y in range(0, image.height, 75):
        draw.rectangle((0, y, image.width, y + 35), fill="#23465b")
    draw.text((60, 60), "NOCAPTURE ISOLATED TEST DESKTOP", fill="white", font_size=36)
    image.save(root / "wallpaper.png")
    run(root, env, ["noctalia", "msg", "wallpaper-set", str(root / "wallpaper.png")], "wallpaper")
    run(
        root,
        env,
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x400:rate=30:duration=10",
            "-c:v",
            "libx264",
            str(root / "pattern.mp4"),
        ],
        "generate-pattern",
    )
    spawn(
        root,
        env,
        "pattern",
        [
            "mpv",
            "--no-config",
            "--no-audio",
            "--loop-file=inf",
            "--title=Nocapture test pattern",
            "--wayland-app-id=nocapture-test-pattern",
            str(root / "pattern.mp4"),
        ],
    )
    wait_for(
        lambda: json.loads(subprocess.check_output(["niri", "msg", "--json", "windows"], env=env)),
        "pattern window",
    )
    run(root, env, ["niri", "msg", "action", "close-overview"], "close-overview")
    print(root)


def cleanup(root):
    for process in reversed(json.loads((root / "processes.json").read_text())):
        try:
            if start_time(process["pid"]) != process["start_time"]:
                continue
            if process["name"] == "dbus":
                os.kill(process["pid"], signal.SIGTERM)
            else:
                os.killpg(process["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    if (
                        Path(f"/proc/{process['pid']}/stat")
                        .read_text()
                        .rsplit(")", 1)[1]
                        .split()[0]
                        == "Z"
                    ):
                        break
                    if start_time(process["pid"]) != process["start_time"]:
                        break
                except FileNotFoundError:
                    break
                time.sleep(0.05)
            else:
                if process["name"] == "dbus":
                    os.kill(process["pid"], signal.SIGKILL)
                else:
                    os.killpg(process["pid"], signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass
    write_json(root / "cleanup.json", {"time": time.time(), "evidence_retained": True})


def spectrum(root, env, file):
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            "1",
            "-i",
            str(file),
            "-t",
            "1",
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            "8000",
            "-",
        ],
        env=env,
    )
    samples = array.array("f")
    samples.frombytes(raw)
    if not samples:
        raise RuntimeError("No audio samples decoded")
    levels = {}
    for frequency in (440, 880, 1320):
        real = sum(
            value * math.cos(2 * math.pi * frequency * i / 8000) for i, value in enumerate(samples)
        )
        imag = sum(
            value * math.sin(2 * math.pi * frequency * i / 8000) for i, value in enumerate(samples)
        )
        levels[frequency] = math.hypot(real, imag) / len(samples)
    write_json(root / f"{file.stem}-spectrum.json", {"file": str(file), "amplitudes": levels})
    print(json.dumps(levels))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    launch_parser = commands.add_parser("launch")
    launch_parser.add_argument("--package", type=Path, default=os.getenv("NOCAPTURE_TEST_PACKAGE"))
    commands.add_parser("cleanup")
    commands.add_parser("doctor")
    execute = commands.add_parser("exec")
    execute.add_argument("arguments", nargs=argparse.REMAINDER)
    pointer = commands.add_parser("pointer")
    pointer.add_argument("coordinates", type=int, nargs="+")
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("name")
    audio = commands.add_parser("spectrum")
    audio.add_argument("file", type=Path)
    args = parser.parse_args()
    root = args.instance.resolve()
    if args.command == "launch":
        launch(root, args.package.resolve())
        return
    if args.command == "cleanup":
        cleanup(root)
        return
    env = json.loads((root / "env.json").read_text())
    if args.command == "doctor":
        result = run(root, env, ["nocapture-engine", "context"], "doctor")
        print(result.decode())
    elif args.command == "exec":
        command = args.arguments
        if command and command[0] == "--":
            command = command[1:]
        print(run(root, env, command, "exec-" + str(time.time_ns())).decode())
    elif args.command == "snapshot":
        if Path(args.name).name != args.name:
            raise ValueError("Snapshot name must be a plain filename")
        run(root, env, ["grim", str(root / args.name)], "snapshot-" + args.name)
    elif args.command == "pointer":
        output = json.loads(
            subprocess.check_output(["niri", "msg", "--json", "focused-output"], env=env)
        )["logical"]
        os.environ.update(env)
        pointer = Pointer(output["width"], output["height"])
        try:
            if len(args.coordinates) == 2:
                pointer.click(*args.coordinates)
            elif len(args.coordinates) == 4:
                pointer.drag(*args.coordinates)
            else:
                raise ValueError("Provide x y for click or x1 y1 x2 y2 for drag")
        finally:
            pointer.close()
    elif args.command == "spectrum":
        spectrum(root, env, args.file)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Live verification failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
