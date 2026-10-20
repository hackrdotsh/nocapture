"""Minimal test client for the wlr virtual-pointer protocol."""

import os
import socket
import struct
import time
from pathlib import Path


def uints(*values):
    return struct.pack("=" + "I" * len(values), *values)


def string(value):
    data = value.encode() + b"\0"
    return uints(len(data)) + data + b"\0" * (-len(data) % 4)


class Pointer:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(5)
        display = Path(os.environ["WAYLAND_DISPLAY"])
        if not display.is_absolute():
            display = Path(os.environ["XDG_RUNTIME_DIR"]) / display
        self.socket.connect(str(display))
        self.buffer = b""
        self.next_id = 3
        self.globals = {}
        self.send(1, 1, uints(2))
        self.roundtrip()
        interface = "zwlr_virtual_pointer_manager_v1"
        if interface not in self.globals:
            self.socket.close()
            raise RuntimeError("The test compositor has no virtual-pointer protocol.")
        self.send(2, 0, uints(self.globals[interface]) + string(interface) + uints(1, 4))
        self.send(4, 0, uints(0, 5))
        self.next_id = 6
        self.roundtrip()

    def send(self, object_id, opcode, payload=b""):
        self.socket.sendall(uints(object_id, ((len(payload) + 8) << 16) | opcode) + payload)

    def receive(self):
        while len(self.buffer) < 8:
            self.read_more()
        object_id, header = struct.unpack("=II", self.buffer[:8])
        size, opcode = header >> 16, header & 0xFFFF
        while len(self.buffer) < size:
            self.read_more()
        payload, self.buffer = self.buffer[8:size], self.buffer[size:]
        if object_id == 1 and opcode == 0:
            raise RuntimeError(f"Wayland protocol error: {payload!r}")
        if object_id == 2 and opcode == 0:
            name, length = struct.unpack("=II", payload[:8])
            self.globals[payload[8 : 8 + length - 1].decode()] = name
        return object_id, opcode

    def read_more(self):
        chunk = self.socket.recv(65536)
        if not chunk:
            raise RuntimeError("The Wayland test connection closed.")
        self.buffer += chunk

    def roundtrip(self):
        callback = self.next_id
        self.next_id += 1
        self.send(1, 0, uints(callback))
        while self.receive() != (callback, 0):
            pass

    def move(self, x, y):
        self.send(5, 1, uints(int(time.monotonic() * 1000) % 2**32, x, y, self.width, self.height))
        self.send(5, 4)
        self.roundtrip()

    def button(self, pressed):
        self.send(5, 2, uints(int(time.monotonic() * 1000) % 2**32, 272, int(pressed)))
        self.send(5, 4)
        self.roundtrip()

    def click(self, x, y):
        self.move(x, y)
        self.button(True)
        self.button(False)

    def drag(self, x1, y1, x2, y2):
        self.move(x1, y1)
        time.sleep(0.1)
        self.button(True)
        time.sleep(0.1)
        self.move(x2, y2)
        time.sleep(0.1)
        self.button(False)

    def close(self):
        self.socket.close()
