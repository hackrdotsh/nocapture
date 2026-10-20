import fcntl
import json
import os
import select
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from .capture import (
    Cancelled,
    application_names,
    focused_output,
    read_json,
    record_command,
    reserve_path,
    select_region,
)
from .media import gif_command


def runtime_directory() -> Path:
    base = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
    directory = base / f"nocapture-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise RuntimeError("Unsafe Nocapture runtime directory.")
    directory.chmod(0o700)
    return directory


def save_status(directory: Path, value: dict) -> None:
    temporary = directory / "status.tmp"
    temporary.write_text(json.dumps(value))
    temporary.replace(directory / "status.json")


def request(action: str) -> dict:
    directory = runtime_directory()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(directory / "control.sock"))
            client.sendall((action + "\n").encode())
            with client.makefile("r") as response:
                return json.loads(response.readline(65536))
    except (FileNotFoundError, ConnectionRefusedError):
        if action == "stop":
            return {"state": "idle"}
        try:
            value = json.loads((directory / "status.json").read_text())
            if value.get("state") not in ("idle", "saved", "error", "cancelled"):
                return {"state": "error", "error": "Recording worker ended unexpectedly."}
            return value
        except FileNotFoundError:
            return {"state": "idle"}


def record(args) -> dict:
    os.umask(0o077)
    directory = runtime_directory()
    with (directory / "record.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("A Nocapture recording is already running.") from error
        return _record_owned(args, directory)


def _record_owned(args, directory: Path) -> dict:
    source = None
    destination = None
    child = None
    stopped = False
    abort = False
    old_handlers = {}

    def interrupt(signum, _frame):
        nonlocal stopped, abort
        stopped = True
        abort = signum == signal.SIGTERM

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, interrupt)
    control = directory / "control.sock"
    control.unlink(missing_ok=True)
    state = {"state": "selecting", "format": args.format, "started_at": time.time()}

    def publish(**values):
        state.update(values)
        save_status(directory, state)

    try:
        if args.audio == "application" and args.application not in application_names():
            raise RuntimeError(
                "The selected application has no audio stream. Play audio and retry."
            )
        if args.target == "display" and not args.output:
            args.output = focused_output()
        region = select_region() if args.target == "region" else None
        destination = reserve_path(args.directory, args.format, "recording")
        source = destination.with_name(f".{destination.stem}.recording.mp4")
        command = record_command(args, source, region)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(control))
            control.chmod(0o600)
            server.listen(4)
            with (directory / "recording.log").open("w") as log:
                child = subprocess.Popen(command, stdout=log, stderr=log)
                publish(state="starting", path=str(destination), source=str(source))
                phase = "recording"
                deadline = None
                while True:
                    if select.select([server], [], [], 0.1)[0]:
                        with server.accept()[0] as client:
                            client.settimeout(1)
                            action = client.recv(128).decode().strip()
                            if action == "stop" and phase == "recording":
                                stopped = True
                            client.sendall((json.dumps(state) + "\n").encode())
                    if stopped and phase == "recording" and deadline is None:
                        if child.poll() is None:
                            child.send_signal(signal.SIGINT)
                        publish(state="stopping")
                        deadline = time.monotonic() + 15
                    if abort and phase == "converting":
                        child.terminate()
                        child.wait(timeout=5)
                        raise RuntimeError("GIF conversion interrupted; the source video was kept.")
                    if deadline is not None and time.monotonic() > deadline:
                        child.kill()
                        child.wait()
                        raise RuntimeError(
                            "Recorder did not stop in time; the source video was kept."
                        )
                    code = child.poll()
                    if code is None:
                        if (
                            state["state"] == "starting"
                            and source.exists()
                            and source.stat().st_size
                        ):
                            publish(state="recording")
                        continue
                    if code != 0:
                        log.flush()
                        detail = (directory / "recording.log").read_text(errors="replace")[-2000:]
                        if "canceled by the user" in detail or "cancelled by the user" in detail:
                            publish(state="cancelled")
                            return state
                        raise RuntimeError(detail or "Capture failed. Check the recording log.")
                    if phase == "recording":
                        if not source.exists() or source.stat().st_size == 0:
                            publish(state="cancelled")
                            return state
                        streams = read_json(
                            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(source)]
                        )["streams"]
                        if not any(stream["codec_type"] == "video" for stream in streams):
                            raise RuntimeError(
                                "Recorder produced no video stream; the source was kept."
                            )
                        if args.audio != "none" and not any(
                            stream["codec_type"] == "audio" for stream in streams
                        ):
                            raise RuntimeError(
                                "Recorder produced no audio stream; the source was kept."
                            )
                        if args.format == "gif":
                            publish(state="converting")
                            child = subprocess.Popen(
                                gif_command(source, destination, args.gif_fps, args.gif_width),
                                stdout=log,
                                stderr=log,
                            )
                            phase = "converting"
                            deadline = None
                            continue
                        source.replace(destination)
                    else:
                        source.unlink()
                    publish(state="saved", source=None)
                    return state
    except Cancelled:
        publish(state="cancelled")
        return state
    except BaseException as error:
        publish(state="error", error=str(error), source=str(source) if source else None)
        if destination is not None and args.format == "gif":
            destination.unlink(missing_ok=True)
        raise
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if destination is not None and destination.exists() and destination.stat().st_size == 0:
            destination.unlink()
        control.unlink(missing_ok=True)
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
