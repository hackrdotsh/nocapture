import argparse
import json
import subprocess
import sys

from .capture import Cancelled, context, screenshot
from .recording import record, request


def bounded(minimum: int, maximum: int):
    def parse(value: str) -> int:
        number = int(value)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"Choose a value from {minimum} to {maximum}.")
        return number

    return parse


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="nocapture-engine")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("context")
    commands.add_parser("status")
    commands.add_parser("stop")
    for name in ("screenshot", "record"):
        capture = commands.add_parser(name)
        capture.add_argument("target", choices=("region", "display", "window"))
        capture.add_argument("--output", default="")
        capture.add_argument(
            "--directory",
            default=("~/Pictures/Nocapture" if name == "screenshot" else "~/Videos/Nocapture"),
        )
        if name == "screenshot":
            capture.add_argument("--window-id", type=int)
            capture.add_argument("--wallpaper", action="store_true")
            capture.add_argument("--shadow", action="store_true")
            capture.add_argument("--padding", type=bounded(0, 512), default=96)
        else:
            capture.add_argument(
                "--audio",
                default="none",
                choices=(
                    "none",
                    "system",
                    "microphone",
                    "both",
                    "application",
                ),
            )
            capture.add_argument("--application", default="")
            capture.add_argument("--format", choices=("mp4", "gif"), default="mp4")
            capture.add_argument("--fps", type=bounded(1, 120), default=30)
            capture.add_argument("--gif-fps", type=bounded(1, 30), default=15)
            capture.add_argument("--gif-width", type=bounded(16, 3840), default=1280)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "context":
            value = context()
        elif args.command in ("status", "stop"):
            value = request(args.command)
        elif args.command == "screenshot":
            value = screenshot(args)
        else:
            value = record(args)
        print(json.dumps(value))
        return 0
    except (Cancelled, KeyboardInterrupt):
        print(json.dumps({"state": "cancelled"}))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
