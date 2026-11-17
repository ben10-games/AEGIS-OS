"""Offline changes to a disk image file, as an attacker with access to the disk makes them.

Only the EFI system partition is touched, through mtools, which edits the FAT
filesystem inside the image file directly: no mounting, no privileges, and never a
real block device.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ESP_TYPE = "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"


class DiskError(RuntimeError):
    """The disk image could not be read or changed."""


def _run(command: list[str], data: bytes | None = None) -> bytes:
    environment = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    result = subprocess.run(command, input=data, capture_output=True, env=environment, check=False)
    if result.returncode != 0:
        raise DiskError(f"{' '.join(command)} failed: {result.stderr.decode(errors='replace')}")
    return result.stdout


def private_copy(image: Path, destination: Path) -> Path:
    """A sparse copy of a raw disk image for one test to modify."""
    if not image.is_file():
        raise DiskError(f"{image} is not a regular file")
    _run(["cp", "--sparse=always", str(image), str(destination)])
    return destination


def esp_offset(partition_table: dict) -> int:
    """Byte offset of the EFI system partition, from `sfdisk --json` output."""
    table = partition_table["partitiontable"]
    sector = int(table.get("sectorsize", 512))
    for partition in table["partitions"]:
        if partition["type"].upper() == ESP_TYPE:
            return int(partition["start"]) * sector
    raise DiskError("the disk has no EFI system partition")


class Esp:
    """The EFI system partition inside a raw disk image file."""

    def __init__(self, image: Path):
        if not image.is_file():
            raise DiskError(f"{image} is not a regular file; refusing to touch it")
        self.image = image
        table = json.loads(_run(["sfdisk", "--json", str(image)]))
        self._target = f"{image}@@{esp_offset(table)}"

    def files(self) -> list[str]:
        """Every file on the partition, as paths like 'EFI/BOOT/BOOTX64.EFI'."""
        listing = _run(["mdir", "-i", self._target, "-/", "-b", "::"]).decode(errors="replace")
        return sorted(
            line.strip()[3:] for line in listing.splitlines()
            if line.strip().startswith("::/") and not line.strip().endswith("/")
        )  # fmt: skip

    def read(self, path: str) -> bytes:
        return _run(["mcopy", "-i", self._target, f"::/{path}", "-"])

    def write(self, path: str, data: bytes) -> None:
        """Create or replace a file (missing directories are created)."""
        parts = path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            directory = "/".join(parts[:depth])
            subprocess.run(
                ["mmd", "-i", self._target, f"::/{directory}"],
                capture_output=True,
                env=dict(os.environ, MTOOLS_SKIP_CHECK="1"),
                check=False,  # fails harmlessly when the directory exists
            )
        _run(["mcopy", "-o", "-i", self._target, "-", f"::/{path}"], data)
        if self.read(path) != data:
            raise DiskError(f"{path} was not written correctly")


def replace_bytes(image: Path, old: bytes, new: bytes) -> int:
    """Replace every occurrence of `old` in a raw disk image file, in place.

    Reads only the allocated parts of a sparse file. Returns the number of places
    changed. `old` and `new` must have the same length, so no offset moves.
    """
    if len(old) != len(new):
        raise DiskError("replacement must have the same length")
    changed = 0
    chunk = 64 * 1024 * 1024
    overlap = len(old) - 1
    with image.open("r+b") as handle:
        size = image.stat().st_size
        position = 0
        hole_seek = getattr(os, "SEEK_DATA", None)
        while position < size:
            if hole_seek is not None:
                try:
                    position = os.lseek(handle.fileno(), position, os.SEEK_DATA)
                except OSError:
                    break  # no more data
            handle.seek(position)
            block = handle.read(chunk + overlap)
            if not block:
                break
            start = 0
            while (found := block.find(old, start)) != -1:
                handle.seek(position + found)
                handle.write(new)
                changed += 1
                start = found + 1
            position += chunk
    return changed
