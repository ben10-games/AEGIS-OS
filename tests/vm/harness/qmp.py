"""Minimal client for QEMU's machine protocol (QMP) over a unix socket."""

from __future__ import annotations

import json
import socket
from pathlib import Path


class QmpError(RuntimeError):
    pass


class QmpClient:
    """Connect, negotiate capabilities, run commands. Asynchronous events are skipped."""

    def __init__(self, path: Path, timeout: float = 10.0):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect(str(path))
        self._reader = self._sock.makefile("r", encoding="utf-8")
        greeting = self._read()
        if "QMP" not in greeting:
            raise QmpError(f"unexpected greeting: {greeting}")
        self.command("qmp_capabilities")

    def __enter__(self) -> QmpClient:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        self._reader.close()
        self._sock.close()

    def _read(self) -> dict:
        line = self._reader.readline()
        if not line:
            raise QmpError("QEMU closed the control socket")
        return json.loads(line)

    def command(self, name: str, **arguments) -> dict:
        self._sock.sendall(encode_command(name, **arguments))
        while True:
            reply = self._read()
            if "return" in reply:
                return reply["return"]
            if "error" in reply:
                raise QmpError(f"{name} failed: {reply['error']}")
            # anything else is an asynchronous event; keep reading


def encode_command(name: str, **arguments) -> bytes:
    message: dict = {"execute": name}
    if arguments:
        message["arguments"] = arguments
    return (json.dumps(message) + "\r\n").encode()
